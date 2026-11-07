#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""comm_watch.py —— 监听 we-read 协调通道，别人一提交我立刻知道。

监听的通道（都在 origin/main 上）：
  skills/luoyu-reading/references/agent-communication/      日文件（规范要求的事件落点）
  skills/luoyu-reading/references/agent-communication.md    旧索引（仍有 agent 在读）
  skills/luoyu-reading/references/agent-roster.json         角色运行状态
  skills/luoyu-reading/references/book-registry.json        场次/书目注册表

判定：只把"非自己发的"新条目当事件。自己 = 标题里含 weread-auto。
`--watch` 模式下抓到外部新条目就打印全文并退出（后台任务退出才会通知到我），
所以它天生就是"一有回复立刻唤醒"的钩子。

用法：
  python comm_watch.py --baseline      # 建立基线，把现状全标记为已读，不报
  python comm_watch.py --once          # 只检查一次，有新条目就打印
  python comm_watch.py --watch         # 轮询（默认 20s），抓到外部条目即退出
  python comm_watch.py --watch --max-wait 1800
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "data" / "comm_watch_state.json"
INBOX = ROOT / "data" / "comm_inbox.md"
LOG = ROOT / "logs" / "comm_watch.log"

REPO = Path("C:/Users/ROG/we-read")
URL = "https://github.com/ae6623/we-read.git"

COMM_PREFIX = "skills/luoyu-reading/references/agent-communication"
WATCH_FILES = [
    "skills/luoyu-reading/references/agent-communication.md",
    "skills/luoyu-reading/references/agent-roster.json",
    "skills/luoyu-reading/references/book-registry.json",
]

BLOCK_RE = re.compile(r"^### \[\d{4}-\d{2}-\d{2}[ T]\d{2}:?\d{2}\]", re.M)
SELF_MARK = "weread-auto"
RUN_RE = re.compile(r"(\d{4}-\d{2}-\d{2}-[a-z]+-[\w]+)")


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str) -> None:
    line = f"[{now()}] {msg}"
    print(line, flush=True)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def git(args: list[str], timeout: int = 45) -> str:
    p = subprocess.run(["git"] + args, cwd=str(REPO), capture_output=True,
                       timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or b"").decode("utf-8", "replace")[:300])
    return p.stdout.decode("utf-8", "replace")


def remote_sha(retries: int = 3) -> str:
    last = ""
    for i in range(retries):
        try:
            out = git(["ls-remote", URL, "refs/heads/main"])
            parts = out.split()
            if parts and len(parts[0]) == 40:
                return parts[0]
            last = "空返回"
        except Exception as e:  # 沙箱出口抖动：GnuTLS -110 / 443 超时
            last = str(e)
        if i < retries - 1:
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"ls-remote 失败：{last}")


def has_object(sha: str) -> bool:
    try:
        git(["cat-file", "-e", f"{sha}^{{commit}}"])
        return True
    except Exception:
        return False


def ensure_objects(sha: str) -> None:
    """远端有新提交时，本地仓库未必有这些对象。

    只做 ls-remote 而不 fetch，`git log prev..sha` / `git show sha:path`
    会报 Invalid revision range，一整轮提交清单就丢了（2026-10-19 04:23 实撞）。
    先 fetch，拿不到再按 sha 直取，都不行就抛错让调用方下一轮重试。
    """
    if has_object(sha):
        return
    for args in (["fetch", "origin", "main", "--quiet"],
                 ["fetch", URL, "refs/heads/main:refs/watch/main", "--quiet"],
                 ["fetch", "--depth", "1", URL, "main", "--quiet"]):
        try:
            git(args, timeout=120)
        except Exception as e:
            log(f"fetch 失败（{args[1]}）：{str(e)[:80]}")
        if has_object(sha):
            return
    raise RuntimeError(f"本地缺少对象 {sha[:7]}，fetch 后仍不可用")


def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"last_sha": "", "seen": [], "last_check": ""}


def save_state(st: dict) -> None:
    st["last_check"] = now()
    st["seen"] = sorted(set(st.get("seen", [])))
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def comm_paths(sha: str) -> list[str]:
    try:
        out = git(["ls-tree", "-r", "--name-only", sha])
    except Exception:
        return []
    paths = []
    for p in out.splitlines():
        if p.startswith(COMM_PREFIX) and p.endswith(".md"):
            paths.append(p)
        elif p in WATCH_FILES:
            paths.append(p)
    return paths


def read_at(sha: str, path: str) -> str:
    try:
        return git(["show", f"{sha}:{path}"])
    except Exception:
        return ""


def split_blocks(text: str, path: str) -> list[tuple[str, str]]:
    """返回 [(key, 全文)]；key 用标题行（时间+角色+主题足够唯一）。"""
    idx = [m.start() for m in BLOCK_RE.finditer(text)]
    if not idx:
        return []
    out = []
    for i, start in enumerate(idx):
        end = idx[i + 1] if i + 1 < len(idx) else len(text)
        body = text[start:end].rstrip() + "\n"
        key = body.splitlines()[0].strip() + " @ " + Path(path).name
        out.append((key, body))
    return out


def is_self(key: str) -> bool:
    """只匹配标题里的发件人段（`### [ts] <sender> / <subject> ...`）。

    不能用 `SELF_MARK in key` 朴子串：所有外部来帖都以
    `→ TO workbuddy-cloud-luoyu` 结尾，会被误判为自发帖而静默。
    """
    m = re.match(r"^###\s*\[[^\]]*\]\s*(.*?)\s+/\s+", key)
    sender = m.group(1).strip() if m else ""
    if not sender:
        return False
    return sender == SELF_MARK or SELF_MARK in sender


def scan(sha: str) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    self_blocks, ext_blocks = [], []
    for path in comm_paths(sha):
        for key, body in split_blocks(read_at(sha, path), path):
            (self_blocks if is_self(key) else ext_blocks).append((key, body))
    return self_blocks, ext_blocks


# ---------------- HTTP 模式：没有 git / 没有本地克隆时也能监听 ----------------
# 为什么要有：云端沙箱（另一个 agent 那侧，以及我们自己的 agent-1 云端）没有
# `C:/Users/ROG/we-read` 这个本地克隆，也可能没有 git 二进制，`--watch` 直接跑不起来。
# 但 we-read 是**公开仓库**，raw.githubusercontent.com 零凭据可读，够用了。
# 代价：只看最近 N 天的通信日文件（默认 2 天，覆盖跨零点），历史文件被改看不到 ——
# 监听本来只关心"有没有人新发给我"，这个粒度正好。

RAW_BASE = "https://raw.githubusercontent.com/ae6623/we-read/main"
HTTP_DAYS = 2


def _http_get(url: str, timeout: int = 25, retries: int = 2) -> str:
    """读 raw 文件。404 直接返回空串（当天还没人发帖是常态，不重试）；网络抖动重试 2 次。"""
    import urllib.error
    import urllib.request
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "weread-comm-watch",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            })
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return ""
            last = e
        except Exception as e:
            last = e
        if i < retries:
            time.sleep(2 * (i + 1))
    raise last if last else RuntimeError("未知读取失败")


def http_paths(days: int = HTTP_DAYS) -> list[str]:
    """按日期直接拼路径（不调目录 API：省配额、免令牌、CDN 更快）。"""
    from datetime import timedelta
    today = datetime.now()
    return [f"{COMM_PREFIX}/{(today - timedelta(days=i)).year}/"
            f"{(today - timedelta(days=i)).month:02d}/"
            f"{(today - timedelta(days=i)):%Y-%m-%d}.md"
            for i in range(max(1, days))]


def scan_http(days: int = HTTP_DAYS) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    self_blocks, ext_blocks = [], []
    for path in http_paths(days):
        try:
            text = _http_get(f"{RAW_BASE}/{path}?_={int(time.time())}")
        except Exception as e:
            log(f"读取失败（跳过）：{Path(path).name} {str(e)[:80]}")
            continue
        for key, body in split_blocks(text, path):
            (self_blocks if is_self(key) else ext_blocks).append((key, body))
    return self_blocks, ext_blocks


def check_http_once(st: dict, baseline: bool = False,
                    days: int = HTTP_DAYS) -> tuple[list, list, list]:
    """HTTP 版检查：不比 sha（省一次 fetch），直接按条目 key 去重。

    key = 条目标题行 + 文件名，新增条目必然产生新 key；旧条目被"编辑"时不报，
    这个取舍是刻意的——监听要的是"有人发了新消息"，不是文件审计。
    """
    seen = set(st.get("seen", []))
    self_blocks, ext_blocks = scan_http(days)
    all_keys = {k for k, _ in self_blocks + ext_blocks}
    if baseline or not seen:
        st["seen"] = sorted(all_keys)
        st["last_http"] = now()
        log(f"HTTP 基线已建立：{len(all_keys)} 条")
        return [], [], []
    new_self = [(k, b) for k, b in self_blocks if k not in seen]
    new_ext = [(k, b) for k, b in ext_blocks if k not in seen]
    st["seen"] = sorted(seen | all_keys)
    st["last_http"] = now()
    return new_ext, new_self, []


def write_inbox(items: list[tuple[str, str]], sha: str) -> None:
    if not items:
        return
    INBOX.parent.mkdir(parents=True, exist_ok=True)
    with INBOX.open("a", encoding="utf-8") as f:
        f.write(f"\n## 抓取 {now()} · {sha[:7]}\n\n")
        for _, body in items:
            f.write(body + "\n")


def print_items(items: list[tuple[str, str]]) -> None:
    for key, body in items:
        print("-" * 72, flush=True)
        print(body.rstrip(), flush=True)
    print("-" * 72, flush=True)


def check_once(st: dict, baseline: bool = False) -> tuple[list, list, list]:
    """返回 (新增外部条目, 新增自有条目, 新提交清单)。

    新提交清单按读书管理员口径取 main 上的提交原文——事件判定看提交，
    不靠索引文件。会就地更新 st。
    """
    sha = remote_sha()
    seen = set(st.get("seen", []))
    prev_sha = st.get("last_sha") or ""

    if baseline or not seen:
        try:
            ensure_objects(sha)
        except Exception as e:
            log(f"基线失败：{e}")
            return [], [], []
        self_blocks, ext_blocks = scan(sha)
        st["seen"] = [k for k, _ in self_blocks + ext_blocks]
        st["last_sha"] = sha
        return [], [], []

    if sha == prev_sha:
        return [], [], []

    log(f"远端有新提交 {prev_sha[:7] or '(空)'} → {sha[:7]}")
    try:
        ensure_objects(sha)
    except Exception as e:
        log(f"本轮跳过（对象未就绪，下轮重试）：{e}")
        return [], [], []
    commits = commits_since(prev_sha, sha)
    for c in commits:
        mark = "★场次事件" if c["session"] else "  普通提交"
        log(f"  {mark} {c['sha']} {c['when']} {c['subject']}")
    self_blocks, ext_blocks = scan(sha)
    new_self = [(k, b) for k, b in self_blocks if k not in seen]
    new_ext = [(k, b) for k, b in ext_blocks if k not in seen]

    st["seen"] = sorted(seen | {k for k, _ in new_self + new_ext})
    st["last_sha"] = sha
    return new_ext, new_self, commits


def commits_since(prev: str, sha: str) -> list[dict]:
    """读音读书管理员口径取 main 上的新提交。事件判定看提交标题是否 reading-state:。"""
    args = ["log", "--pretty=%h\x1f%ad\x1f%s", "--date=format:%Y-%m-%d %H:%M"]
    if prev and prev != sha:
        args.append(f"{prev}..{sha}")
    else:
        args += ["-1", sha]
    try:
        out = git(args)
    except Exception as e:
        log(f"读提交失败：{e}")
        return []
    rows = []
    for line in out.splitlines():
        parts = line.split("\x1f")
        if len(parts) != 3:
            continue
        h, when, subject = parts
        m = RUN_RE.search(subject)
        rows.append({"sha": h, "when": when, "subject": subject,
                     "session": subject.startswith("reading-state:"),
                     "run_id": m.group(1) if m else ""})
    return rows


def audit_run(run_id: str) -> int:
    """核对某 run 在 main 上是否有唯一 start / close 提交，并与 registry、日文件对账。

    这是读书管理员给的口径：以 main 提交为准，registry 与当天日文件互相印证。
    """
    sha = remote_sha()
    try:
        ensure_objects(sha)
    except Exception as e:
        log(f"审计前取对象失败：{e}")
        return 2
    log(f"审计 run={run_id} @ main {sha[:7]}")
    try:
        out = git(["log", "--pretty=%h\x1f%ad\x1f%s", "--date=format:%Y-%m-%d %H:%M",
                   f"--grep={run_id}", sha])
    except Exception as e:
        log(f"取提交失败：{e}")
        return 2
    starts, ends, others = [], [], []
    for line in out.splitlines():
        parts = line.split("\x1f")
        if len(parts) != 3 or run_id not in line:
            continue
        h, when, subject = parts
        if not subject.startswith("reading-state:"):
            others.append((h, when, subject))
            continue
        if re.search(r"开始|认领", subject):
            starts.append((h, when, subject))
        elif re.search(r"收尾|结束|close", subject, re.I):
            ends.append((h, when, subject))
        else:
            others.append((h, when, subject))

    # registry
    active = ""
    try:
        reg = json.loads(read_at(sha, "skills/luoyu-reading/references/book-registry.json") or "{}")
        a = reg.get("active_session")
        active = (a or {}).get("run_id") or "" if isinstance(a, dict) else str(a or "")
    except Exception as e:
        log(f"读 registry 失败：{e}")

    # 当天日文件
    day = run_id[:10]
    day_path = f"{COMM_PREFIX}/{day[:4]}/{day[5:7]}/{day}.md"
    day_txt = read_at(sha, day_path)
    in_day = run_id in day_txt

    print(f"\n=== 审计 {run_id} ===")
    print(f"start 提交（reading-state: 且含开始/认领）：{len(starts)} 条")
    for h, w, s in starts:
        print(f"  {h} {w} {s}")
    print(f"close 提交（reading-state: 且含收尾/结束）：{len(ends)} 条")
    for h, w, s in ends:
        print(f"  {h} {w} {s}")
    if others:
        print(f"同 run_id 的其他提交（不计事件）：{len(others)} 条")
        for h, w, s in others:
            print(f"  {h} {w} {s}")
    print(f"registry.active_session.run_id：{active or '(空)'}")
    print(f"当日日文件含该 run_id：{'是' if in_day else '否'}（{day_path}）")

    ok = len(starts) == 1 and len(ends) <= 1
    if starts and not ends and active == run_id:
        print("结论：已开始、仍在进行（registry 与提交一致）")
        return 0
    if starts and ends and active != run_id:
        print("结论：场次完整（start + close 各一条，registry 已释放）")
        return 0
    if not starts:
        print("结论：main 上没有该 run 的开始提交——事件未送达")
        return 1
    print("结论：状态不一致，需人工核对（条数、registry、日文件）")
    return 1 if not ok else 0


def main() -> int:
    global SELF_MARK
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", action="store_true", help="建立基线，现有条目全部标为已读")
    ap.add_argument("--once", action="store_true", help="只查一次")
    ap.add_argument("--watch", action="store_true", help="轮询直到出现外部新条目")
    ap.add_argument("--interval", type=int, default=20)
    ap.add_argument("--max-wait", type=int, default=1800)
    ap.add_argument("--http", action="store_true",
                    help="纯 HTTP 模式：不依赖 git 与本地克隆（云端沙箱用这个）")
    ap.add_argument("--days", type=int, default=HTTP_DAYS, help="HTTP 模式看最近几天的日文件")
    ap.add_argument("--self", dest="self_mark", default=SELF_MARK,
                    help="自己的标识；标题里含它就当自己发的，不唤醒（每个 agent 填自己的名字）")
    ap.add_argument("--audit", metavar="RUN_ID", help="核对某场次在 main 上的 start/close 提交")
    args = ap.parse_args()

    # 自己的标识可在运行时改：云端 agent 不是 weread-auto，必须各自声明，否则会把自己的
    # 帖子当成"外部新消息"唤醒自己，来回刷。
    SELF_MARK = (args.self_mark or SELF_MARK).strip()

    if args.audit:
        return audit_run(args.audit)

    def _check(st, baseline=False):
        if args.http:
            return check_http_once(st, baseline=baseline, days=args.days)
        return check_once(st, baseline=baseline)

    st = load_state()

    if args.baseline:
        _check(st, baseline=True)
        save_state(st)
        log(f"基线已建立：{len(st['seen'])} 条，sha={st['last_sha'][:7]}，self={SELF_MARK}")
        return 0

    if not (args.watch or args.once):
        args.once = True

    if args.once:
        ext, mine, _c = _check(st)
        save_state(st)
        if ext:
            write_inbox(ext, st["last_sha"])
            log(f"外部新增 {len(ext)} 条")
            print_items(ext)
        if mine:
            log(f"自己新增 {len(mine)} 条（不报）")
        if not ext and not mine:
            log("无新增")
        return 0

    started = time.time()
    while True:
        try:
            ext, mine, _c = _check(st)
        except Exception as e:
            log(f"检查失败（继续）：{e}")
            ext, mine = [], []
        save_state(st)
        if ext:
            write_inbox(ext, st["last_sha"])
            log(f"抓到外部新条目 {len(ext)} 条，退出以便唤醒")
            print_items(ext)
            return 0
        if mine:
            log(f"自己新增 {len(mine)} 条（不唤醒）")
        if time.time() - started > args.max_wait:
            log(f"监听窗口到期（{args.max_wait}s 无外部新条目），正常退出")
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
