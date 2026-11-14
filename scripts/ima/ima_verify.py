#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 IMA 知识库里书卡的解析状态（media_state / parse_progress / content 是否为空）。

背景：IMA 的 md 解析是异步慢队列。刚传完一大批时大量条目停在 media_state=1、
parse_progress=0，看起来像失败，其实 5~10 分钟后会自己转成 2/100。
这个脚本就是用来「等够了再看」的，别凭刚传完的状态判生死。

用法：
  python3 scripts/ima/ima_verify.py                 # 看一眼当前状态分布
  python3 scripts/ima/ima_verify.py --wait 20       # 最多等 20 分钟，边等边报
  python3 scripts/ima/ima_verify.py --list-bad      # 列出仍失败的条目名
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ima_client as ima  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
KB = "ima_kb_Z69gwh6y"
FOLDER_NAME = "书卡笔记v2"


def folder_id(kb: str) -> str:
    r = ima.call("get_knowledge_list", {"knowledge_base_id": kb, "limit": 50})
    d = json.loads(ima.text_of(r))
    for it in d.get("knowledge_list", []):
        if it.get("media_type") == 99 and it.get("title") == FOLDER_NAME:
            return it["media_id"]
    raise SystemExit(f"没找到文件夹 {FOLDER_NAME}")


def items(kb: str, fid: str) -> list[dict]:
    out, cur, pages = [], "", 0
    while pages < 40:
        a = {"knowledge_base_id": kb, "folder_id": fid, "limit": 50}
        if cur:
            a["cursor"] = cur
        d = json.loads(ima.text_of(ima.call("get_knowledge_list", a)))
        out += [x for x in d.get("knowledge_list", []) if x.get("media_type") != 99]
        pages += 1
        if d.get("is_end"):
            break
        cur = d.get("next_cursor") or ""
        if not cur:
            break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait", type=int, default=0, help="最多等多少分钟（每 60s 复查一次）")
    ap.add_argument("--list-bad", action="store_true")
    args = ap.parse_args()

    ima.init()
    fid = folder_id(KB)
    deadline = time.time() + args.wait * 60
    while True:
        rows = items(KB, fid)
        c = Counter(r.get("media_state") for r in rows)
        bad = [r for r in rows if r.get("media_state") != 2]
        print(f"[{time.strftime('%H:%M:%S')}] 共 {len(rows)} 条｜state 分布 {dict(c)}｜未完成 {len(bad)}")
        if not bad or time.time() >= deadline or not args.wait:
            break
        time.sleep(60)

    if args.list_bad and bad:
        print("\n未完成条目：")
        for r in bad[:60]:
            print(f"  state={r.get('media_state')} {r.get('title')}")


if __name__ == "__main__":
    main()
