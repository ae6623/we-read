#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验收守卫：站点每有一张书卡，IMA 就必须有对应 md。

产出流程收尾跑这个（或 CI 里跑），漏同步会直接点名并退出码 1，
避免「书上线了、知识库里查不到」拖到很久以后才发现。

  python3 scripts/ima/ima_check.py              # 离线核对本地台账
  python3 scripts/ima/ima_check.py --strict      # 站点有卡但台账无记录也算失败
  python3 scripts/ima/ima_check.py --online     # 额外连 IMA 核对实际条数
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ima_export as E  # noqa: E402  复用同一套 index.html 解析口径

MANIFEST = ROOT / "ima" / "manifest.json"
CARDS = ROOT / "ima" / "cards"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--online", action="store_true", help="连 IMA 核对实际条数")
    ap.add_argument("--strict", action="store_true",
                    help="站点有书卡但台账无记录也判失败（CI 用）")
    args = ap.parse_args()

    site = {c["slug"]: c["title"] for c in E.load_index_cards()}
    mf = json.loads(MANIFEST.read_text("utf-8")) if MANIFEST.exists() else {}
    cards = mf.get("cards", {})
    md_files = list(CARDS.glob("*.md")) if CARDS.exists() else []

    missing_file = sorted(s for s, v in cards.items()
                          if v.get("file") and not (ROOT / v["file"]).exists())
    not_uploaded = sorted(s for s, v in cards.items()
                          if not v.get("ima_media_id") and not v.get("duplicate_of")
                          and v.get("file"))
    untracked = sorted(set(site) - set(cards))

    print(f"站点书卡 {len(site)} 本｜台账 {len(cards)} 本｜"
          f"本地 md {len(md_files)} 张｜已入库 "
          f"{sum(1 for v in cards.values() if v.get('ima_media_id'))} 本")

    hard_fail = False
    if missing_file:
        hard_fail = True
        print(f"\n❌ 台账有记录、md 文件却不在（{len(missing_file)} 本）：")
        for s in missing_file[:15]:
            print("   -", s, site.get(s, ""))
    if not_uploaded:
        hard_fail = True
        print(f"\n❌ 已导出但未上传 IMA（{len(not_uploaded)} 本）：")
        for s in not_uploaded[:15]:
            print("   -", s, site.get(s, ""))
        print("   补跑：python3 scripts/ima/ima_sync.py")
    if untracked:
        flag = "❌" if args.strict else "⚠️"
        print(f"\n{flag} 站点有书卡、台账里没有（{len(untracked)} 本）："
              f"多为无 combined-data.html 的归档书，也可能就是漏同步的新书")
        for s in untracked[:12]:
            print("   -", s, site.get(s, ""))
        if len(untracked) > 12:
            print(f"   … 另 {len(untracked) - 12} 本")
        if args.strict:
            hard_fail = True
            print("   新书补跑：python3 scripts/ima/ima_sync.py --book <slug>")

    if args.online:
        import ima_client as ima
        import ima_upload as up
        ima.init()
        kb = up.resolve_kb()
        folder = up.resolve_folder(kb)
        r = ima.call("get_knowledge_list", {
            "knowledge_base_id": kb, "folder_id": folder, "limit": 50})
        total = json.loads(ima.text_of(r)).get("total_size")
        done = sum(1 for v in cards.values() if v.get("ima_media_id"))
        print(f"\nIMA「{up.FOLDER_NAME}」实际条数：{total}（台账已入库 {done}）")
        if isinstance(total, int) and total < done:
            print(f"❌ 线上比台账少 {done - total} 条，可能有条目被删或解析失败")
            hard_fail = True

    print("\n✅ 全部对齐" if not hard_fail else "\n需补同步后再验收")
    return 1 if hard_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
