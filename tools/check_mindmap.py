#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 data/mindmap/*.json 是否符合「LLM 归纳导图」的格式与内容红线。

用法：
  python tools/check_mindmap.py            # 全站汇总
  python tools/check_mindmap.py --bad      # 只列不合格明细
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "mm-graph"
MAT = ROOT / "data" / "mindmap-material"
RELS = {"因果", "并列", "递进", "包含", "对比"}
CHNO = re.compile(r"第\s*[0-9一二三四五六七八九十百]+\s*[–~\-至]?\s*[0-9]*\s*章")
META = ("下方内容", "本页", "Agent 兜底", "非微信读书", "初步对照", "核心观点初判")


def check(slug: str, d: dict) -> list[str]:
    errs = []
    if d.get("source") != "llm":
        errs.append("source!=llm")
    th = d.get("thesis") or ""
    th = th.strip() if isinstance(th, str) else ""
    if not (8 <= len(th) <= 34):
        errs.append("thesis 长度 %d" % len(th))
    if any(x in th for x in META):
        errs.append("thesis 是模块说明")
    brs = d.get("branches") or []
    if not (3 <= len(brs) <= 6):
        errs.append("分支数 %d" % len(brs))
    for i, b in enumerate(brs):
        lab = b.get("label") or ""
        lab = lab.strip() if isinstance(lab, str) else ""
        if not (2 <= len(lab) <= 14):
            errs.append("B%d label 长度 %d" % (i, len(lab)))
        if CHNO.search(lab):
            errs.append("B%d label 是章号" % i)
        if (b.get("rel") or "") not in RELS:
            errs.append("B%d rel=%s" % (i, b.get("rel")))
        pts = [str(x).strip() for x in (b.get("points") or []) if str(x).strip()]
        if not (1 <= len(pts) <= 3):
            errs.append("B%d points 数 %d" % (i, len(pts)))
        if any(len(x) > 16 for x in pts):
            errs.append("B%d point 超长" % i)
        note = b.get("note") or ""
        note = note.strip() if isinstance(note, str) else ""
        if len(note) > 40:
            errs.append("B%d note 超长" % i)
    return errs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bad", action="store_true")
    a = ap.parse_args()
    slugs = sorted(p.stem for p in MAT.glob("*.txt"))
    ok = bad = miss = 0
    details = []
    for slug in slugs:
        p = DATA / (slug + ".json")
        if not p.exists():
            miss += 1
            details.append((slug, "缺文件"))
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            bad += 1
            details.append((slug, "JSON 坏:" + str(e)[:40]))
            continue
        e = check(slug, d)
        if e:
            bad += 1
            details.append((slug, "; ".join(e)))
        else:
            ok += 1
    print("素材 %d 本 | 合格 %d | 不合格 %d | 缺失 %d" % (len(slugs), ok, bad, miss))
    if a.bad:
        for s, e in details[:60]:
            print("  !", s, "→", e)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
