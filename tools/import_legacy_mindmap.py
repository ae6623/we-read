#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""复用仓库里已有的 Gemini 归纳数据（data/mindmap/*.json 中带 thesis/spine 的那批），
转换成新导图格式 data/mm-graph/<slug>.json。已有 LLM 精修结果的不覆盖。

这些旧数据是 gen_mindmap.py 用 LLM 归纳出的「全书命题 + 5-7 条语义主干 + 每章概念」，
spine.label 本身就是议题名，不是章号；之前 combined-data.html 完全没用到它。
"""
from __future__ import annotations
import json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "mindmap"
DST = ROOT / "data" / "mm-graph"
RELS = ("因果", "并列", "递进", "包含", "对比", "递进", "对比")

def conv(slug: str, d: dict) -> dict | None:
    thesis = (d.get("thesis") or {}).get("claim") or ""
    spine = [s for s in (d.get("spine") or []) if (s.get("label") or "").strip()]
    chs = d.get("chapters") or []
    if not thesis or len(spine) < 3:
        return None
    bysp = {}
    for c in chs:
        bysp.setdefault(c.get("spine"), []).append(c)
    brs = []
    for i, s in enumerate(spine[:5]):
        pts = []
        for c in bysp.get(s.get("id"), [])[:12]:
            for x in (c.get("concepts") or []):
                x = str(x).strip()[:12]
                if x and x not in pts:
                    pts.append(x)
                if len(pts) >= 3:
                    break
            if len(pts) >= 3:
                break
        if len(pts) < 2:
            for c in bysp.get(s.get("id"), [])[:4]:
                g = re.split(r"[，,。；;]", str(c.get("gist") or ""))[0].strip()[:12]
                if g and g not in pts:
                    pts.append(g)
                if len(pts) >= 2:
                    break
        brs.append({"id": chr(65 + i), "label": s["label"].strip()[:10],
                    "rel": RELS[i % len(RELS)], "points": pts[:3],
                    "note": str(s.get("why") or "")[:34]})
    if len(brs) < 3:
        return None
    return {"title": d.get("title") or slug, "thesis": thesis.strip()[:28],
            "branches": brs, "source": "llm"}

def main():
    DST.mkdir(parents=True, exist_ok=True)
    ok = skip = 0
    for p in sorted(SRC.glob("*.json")):
        try: d = json.loads(p.read_text(encoding="utf-8"))
        except Exception: continue
        if not d.get("spine"): continue
        dst = DST / p.name
        if dst.exists(): skip += 1; continue
        got = conv(p.stem, d)
        if not got: skip += 1; continue
        dst.write_text(json.dumps(got, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        ok += 1
    print("复用旧归纳 %d 本，跳过 %d 本" % (ok, skip))

if __name__ == "__main__":
    main()
