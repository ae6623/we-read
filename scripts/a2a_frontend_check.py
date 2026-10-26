#!/usr/bin/env python3
"""
Agent2Agent 前端协作监听助手。

监听 skills/luoyu-reading/references/frontend-a2a.md 的提交事件：
每次会话开始 / 推送前端改动前运行，读取写给自己的新消息并按约定回复。

用法：
    python3 scripts/a2a_frontend_check.py --alias <你的别名> [--update] [--board <路径>] [--seen-dir <目录>]

--alias    本 Agent 的别名（如 frontend-mod / luoyu-content / ALL）。必填。
--update   处理完后把"已读游标"更新到最新提交哈希（建议每次都带）。
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


def parse_blocks(text, alias):
    """解析 ### 消息块，过滤 TO 命中 alias 或 ALL。"""
    blocks = re.split(r'(?m)^###\s+\[', text)
    out = []
    for b in blocks[1:]:
        block = "### [" + b
        m = re.search(r'^###\s+\[[^\]]+\]\s+FROM\s+(\S+)\s*→\s*TO\s+(\S+)', block)
        if not m:
            continue
        _frm, to = m.group(1), m.group(2)
        if to == "ALL" or to == alias:
            out.append(block.strip())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--alias", required=True, help="本 Agent 别名")
    ap.add_argument("--update", action="store_true", help="更新已读游标到最新")
    ap.add_argument("--board", default=DEFAULT_BOARD)
    ap.add_argument("--seen-dir", default=".a2a")
    args = ap.parse_args()

    # 先尝试 fetch（无网络则降级用本地 HEAD）
    git("fetch", "origin", check=False)
    latest = resolve_latest("origin/main", args.board)
    if not latest:
        latest = resolve_latest("HEAD", args.board)
    if not latest:
        print("[a2a] 通信板尚无提交历史，无需处理。")
        return

    seen_path = os.path.join(args.seen_dir, SEEN_RELPATH)
    seen_hash = ""
    if os.path.exists(seen_path):
        seen_hash = open(seen_path, encoding="utf-8").read().strip()

    if seen_hash == latest:
        print(f"[a2a] 无新消息（游标 {latest[:10]} 已是最新）。")
        return

    seen_content = file_at(seen_hash, args.board) if seen_hash else ""
    latest_content = file_at(latest, args.board)
    new_text = new_blocks_since(seen_content, latest_content)
    blocks = parse_blocks(new_text, args.alias)

    print(f"[a2a] 板文件最新提交 {latest[:10]}（上次 {seen_hash[:10] if seen_hash else '无'}）")
    if not blocks:
        print("[a2a] 没有写给本别名(或 ALL)的新消息。")
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
        print(f"[a2a] 已读游标已更新到 {latest[:10]}（本地 {seen_path}）。")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"[a2a] 错误：{e}", file=sys.stderr)
        sys.exit(1)
