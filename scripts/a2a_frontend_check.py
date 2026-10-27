#!/usr/bin/env python3
"""
Agent2Agent 前端协作监听助手。

监听 skills/luoyu-reading/references/frontend-a2a.md 的提交事件：
每次会话开始 / 推送前端改动前运行，读取写给自己的新消息并按约定回复。

用法：
    python3 scripts/a2a_frontend_check.py --alias <你的别名> [--update] [--peek N] [--watch SECONDS]

    # 一次性检查（会话开始 / 推送前）
    python3 scripts/a2a_frontend_check.py --alias luoyu-content --update --peek 3

    # 常驻监听（后台挂着，命中写给自己/ALL 的消息就打全文并退出）
    python3 scripts/a2a_frontend_check.py --alias luoyu-content --watch 60 --peek 3

--alias    本 Agent 的别名（如 frontend-mod / luoyu-content / ALL）。必填。
--update   处理完后把"已读游标"更新到最新提交哈希（建议每次都带）。
--peek N   兜底：无视游标，额外打印板上最后 N 条消息（含不是写给自己的）。
           游标追上最新后会走「已是最新」短路，此时仍有漏读风险
           （2026-10-27 实测两边各漏过一条）。定长轮询里请带 --peek 3。
--board    通信板路径（默认 skills/luoyu-reading/references/frontend-a2a.md）。
--seen-dir 本地游标目录（默认 .a2a，已被 .gitignore 忽略，不提交）。

机制：通信板是追加式。本地游标存"上次见过的提交哈希"；本脚本取远端(或本地)板文件最新哈希，
若与游标不同，取两者内容做前缀差，得到新增消息块，再按 TO 过滤后打印。
"""
import argparse
import os
import re
import subprocess
import sys

DEFAULT_BOARD = "skills/luoyu-reading/references/frontend-a2a.md"
SEEN_RELPATH = "frontend-a2a.seen"


def run(cmd, check=True):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if check and r.returncode != 0:
            raise RuntimeError(f"command failed: {' '.join(cmd)}\n{r.stderr}")
        return r
    except FileNotFoundError as e:
        raise RuntimeError(f"git 不可用: {e}")


def git(*args, check=True):
    return run(["git", *args], check=check)


def resolve_latest(ref, board):
    """取 board 在 ref 下的最新提交哈希；取不到返回 None。"""
    r = git("log", "-1", "--format=%H", ref, "--", board, check=False)
    h = r.stdout.strip()
    return h or None


def file_at(ref, board):
    """取 board 在 ref 时的完整内容；取不到返回 ''。"""
    r = git("show", f"{ref}:{board}", check=False)
    return r.stdout if r.returncode == 0 else ""


def new_blocks_since(seen_content, latest_content):
    """追加式：若 seen_content 是 latest_content 的前缀，返回新增后缀；否则回退返回全文。"""
    if seen_content and latest_content.startswith(seen_content):
        return latest_content[len(seen_content):]
    return latest_content


def split_blocks(text):
    """按 ### 切成消息块（不做 TO 过滤）。"""
    return [("### [" + b).strip() for b in re.split(r'(?m)^###\s+\[', text)[1:]]


def parse_blocks(text, alias):
    """解析 ### 消息块，过滤 TO 命中 alias 或 ALL。"""
    out = []
    for block in split_blocks(text):
        m = re.search(r'^###\s+\[[^\]]+\]\s+FROM\s+(\S+)\s*→\s*TO\s+(\S+)', block)
        if not m:
            continue
        _frm, to = m.group(1), m.group(2)
        if to == "ALL" or to == alias:
            out.append(block)
    return out


def print_peek(latest_content, n, alias):
    """兜底：无视游标打印板尾 N 条标题行。游标短路时靠它捞漏读。"""
    if n <= 0:
        return
    blocks = split_blocks(latest_content)
    if not blocks:
        return
    tail = blocks[-n:]
    print(f"[a2a] --- 兜底 peek：板上最后 {len(tail)} 条（★=写给你的）---")
    for blk in tail:
        head = blk.splitlines()[0] if blk else ""
        m = re.search(r'TO\s+(\S+)', head)
        mine = bool(m and m.group(1) in ("ALL", alias))
        print(("  ★ " if mine else "    ") + head[:120])
    print("[a2a] --- peek 结束；正文读板尾 ---")


def check_once(args, quiet=False) -> int:
    """跑一轮检查，返回「写给自己（或 ALL）的新消息条数」。quiet=True 时成功无消息不打印。"""
    say = (lambda *a: None) if quiet else print

    # 先尝试 fetch（无网络则降级用本地 HEAD）
    git("fetch", "origin", check=False)
    latest = resolve_latest("origin/main", args.board)
    if not latest:
        latest = resolve_latest("HEAD", args.board)
    if not latest:
        say("[a2a] 通信板尚无提交历史，无需处理。")
        return 0

    seen_path = os.path.join(args.seen_dir, SEEN_RELPATH)
    seen_hash = ""
    if os.path.exists(seen_path):
        seen_hash = open(seen_path, encoding="utf-8").read().strip()

    if seen_hash == latest:
        say(f"[a2a] 无新消息（游标 {latest[:10]} 已是最新）。")
        if not quiet:
            print_peek(file_at(latest, args.board), args.peek, args.alias)
        return 0

    seen_content = file_at(seen_hash, args.board) if seen_hash else ""
    latest_content = file_at(latest, args.board)
    new_text = new_blocks_since(seen_content, latest_content)
    blocks = parse_blocks(new_text, args.alias)

    say(f"[a2a] 板文件最新提交 {latest[:10]}（上次 {seen_hash[:10] if seen_hash else '无'}）")
    if not blocks:
        say("[a2a] 没有写给本别名(或 ALL)的新消息。")
    else:
        print(f"[a2a] 收到 {len(blocks)} 条新消息：\n")
        for i, blk in enumerate(blocks, 1):
            print(f"----- 消息 {i} -----")
            print(blk)
            print()

    if args.update:
        os.makedirs(args.seen_dir, exist_ok=True)
        with open(seen_path, "w", encoding="utf-8") as f:
            f.write(latest)
        say(f"[a2a] 已读游标已更新到 {latest[:10]}（本地 {seen_path}）。")

    if not quiet:
        print_peek(latest_content, args.peek, args.alias)
    return len(blocks)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--alias", required=True, help="本 Agent 别名")
    ap.add_argument("--update", action="store_true", help="更新已读游标到最新")
    ap.add_argument("--peek", type=int, default=0,
                    help="兜底：无视游标额外打印板上最后 N 条消息")
    ap.add_argument("--watch", type=int, default=0, metavar="SECONDS",
                    help="常驻轮询：每 N 秒查一次，命中写给自己/ALL 的消息就打印并退出")
    ap.add_argument("--board", default=DEFAULT_BOARD)
    ap.add_argument("--seen-dir", default=".a2a")
    args = ap.parse_args()

    if not args.watch:
        check_once(args)
        return

    import time
    print(f"[a2a] 监听已开：alias={args.alias}，每 {args.watch}s 查一次，命中即退出。Ctrl+C 停止。",
          flush=True)
    while True:
        # 探测轮不移动游标：否则先静默跑一遍把游标推到最新，紧接着的正文轮就无消息可打了
        want_update, args.update = args.update, False
        n = check_once(args, quiet=True)
        args.update = want_update
        if n:
            check_once(args, quiet=False)      # 正文轮：打印全文并推进游标
            print(f"[a2a] 命中 {n} 条写给你的消息，监听退出。", flush=True)
            return
        time.sleep(max(10, args.watch))


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"[a2a] 错误：{e}", file=sys.stderr)
        sys.exit(1)
