#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 data/mm-graph/<slug>.json 是否符合「知识框架」标准（防编造 / 防模板化）。

用法：
  python3 tools/verify_mm_graph.py 1984            # 单本，打印逐项结果
  python3 tools/verify_mm_graph.py --all           # 全站汇总
  python3 tools/verify_mm_graph.py --batch a,b,c   # 批量，只打印失败项

判定标准（与 AGENTS/导图规范一致）：
  1. thesis ≤ 40 字，且以句末标点结尾（不允许半句）
  2. branches 数量按素材字数分档：≥2500→8-10，1800-2500→7-9，1200-1800→6-8，<1200→5-6
  3. 每个 branch：label ≤ 10 字且不是章节/序言类；note ≤ 45 字；points 3-5 个
  4. 每个概念 ≤ 12 字；不允许纯人名式概念（与素材「章节与要点」中人名高度重合且无实义后缀）
  5. 每个概念必须有 2-3 条 evidence，每条 ≤ 40 字
  6. evidence 必须有据：与素材的 2-gram 命中率 ≥ 0.45（防凭空编造）
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MM = ROOT / "data" / "mm-graph"
MAT = ROOT / "data" / "mindmap-material"

BAN_LABEL = re.compile(r"第[一二三四五六七八九十百\d]+[章节部篇回]|序言|译序|前言|后记|尾声|引言|附录|作者简介|封面|目录")
SENT_END = ("。", "！", "？", "」", "”", "…", "；")
RELS = {"因果", "并列", "递进", "包含", "对比"}


def tier(n_chars: int) -> tuple[int, int]:
    if n_chars >= 2500: return (8, 10)
    if n_chars >= 1800: return (7, 9)
    if n_chars >= 1200: return (6, 8)
    return (5, 6)


def _bigrams(s: str) -> set[str]:
    s = re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", s or "")
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) >= 2 else set()


def check(slug: str, verbose: bool = True) -> list[str]:
    errs: list[str] = []
    jp = MM / (slug + ".json")
    mp = MAT / (slug + ".txt")
    if not jp.exists():
        return [f"{slug}: 缺 mm-graph/{slug}.json"]
    try:
        d = json.loads(jp.read_text(encoding="utf-8"))
    except Exception as e:
        return [f"{slug}: json 解析失败 {e}"]
    if not mp.exists():
        return [f"{slug}: 缺素材文件"]
    mat = mp.read_text(encoding="utf-8", errors="ignore")
    mat_bg = _bigrams(mat)

    th = (d.get("thesis") or "").strip()
    if not th:
        errs.append("thesis 为空")
    elif len(th) > 40:
        errs.append(f"thesis {len(th)} 字 > 40")
    elif not th.endswith(SENT_END):
        errs.append(f"thesis 未以句末标点结尾（疑似截断）：…{th[-10:]}")

    brs = d.get("branches") or []
    lo, hi = tier(len(mat))
    if not (lo <= len(brs) <= hi):
        errs.append(f"分支 {len(brs)} 个，素材 {len(mat)} 字应 {lo}-{hi} 个")

    ev = d.get("evidence") or {}
    all_pts = []
    for i, b in enumerate(brs):
        tag = f"分支{chr(65+i) if i < 26 else i}"
        lb = (b.get("label") or "").strip()
        if not lb:
            errs.append(f"{tag} label 为空")
        elif len(lb) > 10:
            errs.append(f"{tag} label「{lb}」{len(lb)} 字 > 10")
        if BAN_LABEL.search(lb):
            errs.append(f"{tag} label「{lb}」是章节/序言类，应为论证维度")
        note = (b.get("note") or "").strip()
        if not note:
            errs.append(f"{tag} note 为空")
        elif len(note) > 45:
            errs.append(f"{tag} note {len(note)} 字 > 45")
        if b.get("rel") and b["rel"] not in RELS:
            errs.append(f"{tag} rel「{b['rel']}」非法")
        pts = [str(x).strip() for x in (b.get("points") or []) if str(x).strip()]
        if not (3 <= len(pts) <= 5):
            errs.append(f"{tag} 概念 {len(pts)} 个，应 3-5")
        all_pts.extend(pts)
        for p in pts:
            if len(p) > 12:
                errs.append(f"{tag} 概念「{p}」{len(p)} 字 > 12")

    for p in all_pts:
        items = ev.get(p)
        if not items:
            errs.append(f"概念「{p}」无 evidence")
            continue
        if isinstance(items, str):
            items = [items]
        if not (1 <= len(items) <= 3):
            errs.append(f"概念「{p}」依据 {len(items)} 条，应 1-3")
        for e in items:
            e = str(e).strip()
            if len(e) > 40:
                errs.append(f"概念「{p}」依据 {len(e)} 字 > 40：{e[:16]}…")
            bg = _bigrams(e)
            if bg:
                hit = len(bg & mat_bg) / len(bg)
                if hit < 0.45:
                    errs.append(f"概念「{p}」依据疑无出处（素材命中 {hit:.0%}）：{e[:20]}")

    extra = set(ev) - set(all_pts)
    if extra:
        errs.append(f"evidence 有 {len(extra)} 个 key 不在 points 里（应删除或改名对齐）")

    if verbose:
        print(f"\n=== {slug} ===")
        print(f"素材 {len(mat)} 字 → 分支应 {lo}-{hi}，实际 {len(brs)}")
        print(f"概念 {len(all_pts)} 个，依据 {sum(len(v) if isinstance(v, list) else 1 for v in ev.values())} 条")
        if errs:
            for e in errs:
                print("  ✗", e)
        else:
            print("  ✓ 全部通过")
    return errs


def main() -> int:
    args = sys.argv[1:]
    if "--all" in args:
        slugs = sorted(p.stem for p in MM.glob("*.json"))
        bad = 0
        for s in slugs:
            e = check(s, verbose=False)
            if e:
                bad += 1
        print(f"全站 {len(slugs)} 本，不合格 {bad} 本")
        return 0
    if "--batch" in args:
        i = args.index("--batch")
        slugs = [x.strip() for x in args[i + 1].split(",") if x.strip()]
        total = 0
        for s in slugs:
            e = check(s, verbose=False)
            if e:
                total += len(e)
                print(f"\n✗ {s}（{len(e)} 项）")
                for x in e:
                    print("   -", x)
        print(f"\n{len(slugs)} 本，问题 {total} 项")
        return 0
    if not args:
        print(__doc__)
        return 1
    return 1 if check(args[0]) else 0


if __name__ == "__main__":
    sys.exit(main())
