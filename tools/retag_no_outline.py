#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给「没有官方 AI 大纲」的书改口径：把模块说明里「取自 AI 大纲 / 热门划线」的措辞，
换成本书真实来源（官方章节目录 + 公开书评），避免页面宣称有并不存在的一手依据。

用法：python tools/retag_no_outline.py --slug zhu-xiao-fang-zi-de-nv-ren
"""
from __future__ import annotations

import argparse
from pathlib import Path

BOOKS = Path(__file__).resolve().parent.parent / "reading-notes" / "books"

PAIRS = [
    ("每章的要点与原句均逐字取自本书 AI 大纲，未做人工解读。",
     "每章的要点据原书章节目录与公开书评整理；微信读书暂无本书官方 AI 大纲，故不列原句。"),
    ("本页「一句话主旨」由 AI 大纲结构重算",
     "本页「一句话主旨」由原书章节目录结构重算"),
    ("（取自大纲结构，非读后感）",
     "（取自章节目录与公开书评，非读后感）"),
    ("章节目录与 AI 大纲融合为一棵树：篇章分组即目录，展开各章即骨架与逐节 AI 大纲（要点 · 原句摘录）。",
     "章节目录即骨架：篇章分组即目录，展开各章即逐节读点（据官方简介与公开书评整理，不列原句）。"),
    ("据本书 AI 大纲与热门划线自主整理、未亲读原书",
     "据本书章节目录与公开书评自主整理、未亲读原书"),
    ("基于全书大纲与热门划线撰写",
     "基于本书章节目录与公开书评撰写"),
    ("基于本书 AI 大纲与热门划线原文的自测追问",
     "基于本书章节目录与公开书评的自测追问"),
    ("全书篇目（AI 大纲顺序）", "全书篇目（原书目录顺序）"),
    ("（Agent 兜底生成 · 基于大纲、未亲读）",
     "（Agent 兜底 · 无官方大纲，据目录与公开书评整理）"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    a = ap.parse_args()
    page = BOOKS / a.slug / "combined-data.html"
    if not page.exists():
        print("✗ 缺少", page)
        return 1
    s = page.read_text(encoding="utf-8")
    hit = 0
    for old, new in PAIRS:
        c = s.count(old)
        if c:
            s = s.replace(old, new)
            hit += c
    page.write_text(s, encoding="utf-8")
    print("✓ %s 改口径 %d 处" % (a.slug, hit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
