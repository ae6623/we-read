#!/usr/bin/env python3
"""以服务端最新 main 的 tree 为底，覆盖指定文件，构造 commit 并推送。

用于 main 被其它流水线高频推送、本地大对象同步困难的场景：
不需要本地有完整历史，也不做 git merge，直接以服务端快照为基线。

用法：
  python3 tools/push_snapshot.py --files /tmp/final_files.txt \
      --message "feat: xxx" [--main] [--backup-branch ditu-5-7] [--rounds 15]

要点：
- **不要复用 SSH 连接**（不要 ControlMaster/ControlPath）：复用会让 ls-remote
  读到缓存的旧 ref，构造出的 commit parent 永远落后，push 必然 non-fast-forward。
- 清单里以 combined-data.html 结尾的文件按「段级合并」处理：只替换
  data-key="svg" 段，保留服务端版本里其它流水线新增的模块。
- 段合并结果按 (服务端 blob sha, 路径) 缓存，tip 变化但页面未变时直接复用。
"""
import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # /tmp/we-read
REPO = Path("/tmp/mergerepo")                          # partial clone 工作仓
SEC = re.compile(r'<section class="mmx-svgwrap" data-key="svg">.*?</section>', re.S)
# 每轮都用全新连接，禁止 ControlMaster 缓存
SSH = "ssh -o ConnectTimeout=8 -o ConnectionAttempts=2 -o ServerAliveInterval=10"

# 注意：不要设 GIT_NO_LAZY_FETCH=1。partial clone(blob:none) 在 push 时
# 需要按需补齐对象，禁掉会让 push 连「强制推全新分支」都失败（曾白跑 14 轮）。
E = dict(os.environ,
         GIT_INDEX_FILE=str(REPO / ".git" / "snapshot-index"),
         GIT_AUTHOR_NAME="WorkBuddy Agent", GIT_AUTHOR_EMAIL="agent@workbuddy.local",
         GIT_COMMITTER_NAME="WorkBuddy Agent", GIT_COMMITTER_EMAIL="agent@workbuddy.local",
         GIT_SSH_COMMAND=SSH)
EF = dict(os.environ, GIT_SSH_COMMAND=SSH)             # 允许 lazy fetch


def run(args, cwd=REPO, env=E, inp=None, to=120):
    return subprocess.run(["git"] + args, cwd=cwd, env=env, input=inp,
                          capture_output=True, text=True, timeout=to)


def g(*a, **kw):
    r = run(list(a), **kw)
    if r.returncode:
        raise RuntimeError(f"git {a[:2]}: {(r.stderr or r.stdout)[:300]}")
    return r.stdout.strip()


def ls_remote():
    r = run(["ls-remote", "origin", "refs/heads/main"], env=E, to=40)
    if r.returncode:
        raise RuntimeError("ls-remote 失败: " + r.stderr[-200:])
    return r.stdout.strip().split("\t")[0]


def tree_map(tip):
    out = g("ls-tree", "-r", tip, env=EF, to=90)
    m = {}
    for line in out.splitlines():
        if "\t" not in line:
            continue
        meta, path = line.split("\t", 1)
        m[path] = meta.split()[2]
    return m


def batch_blobs(shas):
    p = subprocess.Popen(["git", "cat-file", "--batch"], cwd=REPO, env=EF,
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    p.stdin.write(("\n".join(shas) + "\n").encode())
    p.stdin.close()
    out = {}
    for s in shas:
        h = p.stdout.readline().decode().strip()
        if not h or "missing" in h:
            out[s] = None
            continue
        n = int(h.split()[2])
        out[s] = p.stdout.read(n)
        p.stdout.read(1)
    p.wait()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", required=True, help="待覆盖文件路径清单，每行一个")
    ap.add_argument("--message", required=True)
    ap.add_argument("--main", action="store_true", help="尝试 fast-forward 推到 main")
    ap.add_argument("--backup-branch", default="", help="先推到该分支保底（新分支必成功）")
    ap.add_argument("--rounds", type=int, default=12)
    a = ap.parse_args()

    allf = [p for p in Path(a.files).read_text(encoding="utf-8").split("\n") if p]
    htmls = [p for p in allf if p.endswith("combined-data.html")]
    others = [p for p in allf if p not in htmls]
    print(f"清单 {len(allf)}（html {len(htmls)} / 其它 {len(others)}）", flush=True)

    # 非 html 文件的 blob 与 tip 无关，先算好
    sha_map = {}
    for p in others:
        f = ROOT / p
        if f.exists():
            sha_map[p] = g("hash-object", "-w", str(f))
    print(f"预计算 {len(sha_map)} 个 blob", flush=True)

    cache = {}          # (服务端 blob sha, path) -> 段合并后的 blob sha
    last = None
    tmap = {}
    seg = Path("/tmp/snapshot-seg")
    saved = None

    for attempt in range(1, a.rounds + 1):
        tip = ls_remote()
        if tip != last:
            r = run(["-c", "protocol.version=2", "fetch", "--filter=blob:none",
                     "--depth=1", "origin", "main"], env=E, to=110)
            if r.returncode:
                print(f"[{attempt:02}] fetch 失败，重试", flush=True)
                last = None
                time.sleep(0.5)
                continue
            tmap = tree_map(tip)
            need = [(p, tmap.get(p)) for p in htmls
                    if tmap.get(p) and (tmap[p], p) not in cache]
            if need:
                got = batch_blobs([s for _, s in need])
                bad = 0
                for p, s in need:
                    txt = got.get(s)
                    if not txt:
                        bad += 1
                        continue
                    remote = txt.decode("utf-8")
                    mine = (ROOT / p).read_text(encoding="utf-8")
                    m1, m2 = SEC.search(mine), SEC.search(remote)
                    if not m1 or not m2:
                        bad += 1
                        continue
                    merged = remote[:m2.start()] + m1.group(0) + remote[m2.end():]
                    fp = seg / p
                    fp.parent.mkdir(parents=True, exist_ok=True)
                    fp.write_text(merged, encoding="utf-8")
                    cache[(s, p)] = g("hash-object", "-w", str(fp))
                if bad:
                    print(f"[{attempt:02}] 段合并异常 {bad} 本", flush=True)
            last = tip

        # 构造 index：一次批量写入
        g("read-tree", tip)
        entries = [f"100644 {sha_map[p]}\t{p}" for p in others if p in sha_map]
        entries += [f"100644 {cache[(tmap[p], p)]}\t{p}" for p in htmls
                    if tmap.get(p) and (tmap[p], p) in cache]
        r = run(["update-index", "--index-info"], env=E,
                inp="\n".join(entries) + "\n", to=60)
        if r.returncode:
            print("index-info 失败", r.stderr[-200:], flush=True)
            last = None
            continue
        tree = g("write-tree", "--missing-ok")
        commit = g("commit-tree", tree, "-p", tip, "-m", a.message)

        # 保底：推到独立分支（新分支或强制更新，必成功）
        if a.backup_branch and attempt == 1:
            b = run(["push", "-f", "-q", "origin",
                     f"{commit}:refs/heads/{a.backup_branch}"], env=E, to=150)
            print(f"保底分支 {a.backup_branch}: {'ok' if b.returncode == 0 else 'FAIL'}",
                  flush=True)

        if not a.main:
            saved = commit
            print(f"✅ 构造完成 {commit}（未推 main）", flush=True)
            break

        r = run(["push", "origin", f"{commit}:refs/heads/main"], env=E, to=150)
        print(f"[{attempt:02}] tip={tip[:8]} main_push={r.returncode} {commit[:8]}",
              flush=True)
        if r.returncode == 0:
            saved = commit
            print("✅ 已并入 main " + commit, flush=True)
            break
        if not any(k in (r.stderr or "") for k in
                   ("fetch first", "non-fast-forward", "rejected")):
            print("  非预期错误:", (r.stderr or "")[-300:], flush=True)
        time.sleep(0.2)

    if saved:
        Path("/tmp/snapshot_commit").write_text(saved)
        print("COMMIT=" + saved, flush=True)
        return 0
    print(f"!! {a.rounds} 轮未抢到 main 窗口；成果在保底分支", flush=True)
    return 9


if __name__ == "__main__":
    sys.exit(main())
