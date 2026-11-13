#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一条命令把站点新产出的书同步进 IMA 知识库「we-read / 书卡笔记」。

为什么要有这个脚本
------------------
书卡是站点的派生物：站点新增一本 combined-data.html，IMA 里就该多一张卡。
手动记「改了哪几本、传哪几张」迟早出错，所以把「导出 → 上传 → 刷索引」
串成一条命令，靠 ima/manifest.json 的 hash 判断增量。

用法
  python3 tools/ima_sync.py                 # 增量同步（推荐，日常就跑这个）
  python3 tools/ima_sync.py --full          # 强制全部重生成 + 补传缺失
  python3 tools/ima_sync.py --book <slug>   # 只同步一本（新书产出后单独补）
  python3 tools/ima_sync.py --dry-run       # 只算增量，不写不打

同步规则（重要）
  1. 只上传台账里「没有 ima_media_id」或「hash 变了」的卡；
  2. 上传永远用 SAVE，且先用 --skip-existing 跳过文件夹里已有同名文件 ——
     REPLACE 会让服务端把旧条目清空、新条目另立，列表里留下
     「当前内容已删除」的空壳（2026-11-14 踩过，512 条里 328 条中招）；
  3. 索引（00-总索引 / 00-字段说明）每次都刷，保持导航最新。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMA_DIR = ROOT / "ima"
TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))


def run(args: list[str]) -> int:
    print(f"\n$ {' '.join(args)}", flush=True)
    return subprocess.call([sys.executable, "-u"] + args, cwd=str(ROOT))


def pending_count() -> int:
    p = IMA_DIR / "pending.json"
    if not p.exists():
        return 0
    return int(json.loads(p.read_text("utf-8")).get("count") or 0)


def push_index() -> None:
    """把两份索引刷到知识库根目录（同名时 SAVE 会生成副本，所以先看有没有）。"""
    import ima_client as ima
    import ima_upload as up

    ima.init()
    kb = up.resolve_kb()
    have = up.folder_titles(kb, "")          # 根层
    for name in ("00-总索引.md", "00-字段说明.md"):
        p = IMA_DIR / name
        if not p.exists():
            continue
        if name in have:
            print(f"  索引 {name} 已在库内，跳过（内容更新请先在 App 删除旧版）")
            continue
        r = up.upload_one(kb, "", p, replace=False)
        print(f"  索引 {name} -> {r['media_id'][-12:]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="强制全量重生成")
    ap.add_argument("--book", default="", help="只同步指定 slug")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--workers", type=int, default=10)
    args = ap.parse_args()

    exp = [str(TOOLS / "ima_export.py"), "--workers", str(args.workers)]
    if args.full:
        exp.append("--force")
    if args.book:
        exp += ["--only-slug", args.book]
    if args.dry_run:
        exp.append("--dry-run")

    if run(exp) != 0:
        raise SystemExit("导出失败，已中止")

    n = pending_count()
    print(f"\n增量：待上传 {n} 张")
    if args.dry_run or n == 0:
        print("没有需要上传的书卡，结束")
        return

    up = [str(TOOLS / "ima_upload.py"), "--replace", "--skip-existing",
          "--workers", "2"]
    if run(up) != 0:
        raise SystemExit("上传失败，请查看上面的日志")

    push_index()
    print("\n同步完成。若刚传完立刻搜索不到，等 IMA 解析（media_state 1→2）再问。")


if __name__ == "__main__":
    main()
