#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为「LLM 归纳思维导图」导出每本书的紧凑素材包。

产出 data/mindmap-material/<slug>.txt，供 LLM（本 Agent / 云端批处理）逐本归纳成
data/mindmap/<slug>.json。素材只取自站内已有内容，不联网、不臆测。

用法：
  python tools/export_mindmap_material.py                 # 全站
  python tools/export_mindmap_material.py --slug a,b
  python tools/export_mindmap_material.py --missing      # 只导还没归纳的
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import fill_combined_modules as F  # noqa: E402

BOOKS = ROOT / "reading-notes" / "books"
OUT = ROOT / "data" / "mindmap-material"
MIND = ROOT / "data" / "mm-graph"


def _txt(html: str) -> str:
    s = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", s).strip()


def _section(s: str, key: str) -> str:
    m = re.search(r'<section[^>]*data-key="%s"[^>]*>(.*?)</section>' % key, s, re.S)
    return _txt(m.group(1)) if m else ""


def _questions(s: str, key: str, limit: int = 8) -> list[str]:
    m = re.search(r'<section[^>]*data-key="%s"[^>]*>(.*?)</section>' % key, s, re.S)
    if not m:
        return []
    out = []
    for raw in re.findall(r"<h3[^>]*>(.*?)</h3>", m.group(1), re.S):
        t = _txt(raw).strip()
        if t:
            out.append(t[:70])
        if len(out) >= limit:
            break
    return out


def material(slug: str) -> str | None:
    chs = F.chapters_of(slug)
    page = BOOKS / slug / "combined-data.html"
    if not page.exists():
        return None
    s = page.read_text(encoding="utf-8", errors="ignore")
    title = F.meta_of(slug)["title"]
    lines = ["# 《%s》（%s）" % (title, slug), "共 %d 章" % len(chs), "", "## 章节与要点"]
    for c in chs[:38]:
        pts = [p["text"] for sec in c["secs"] for p in sec["points"] if p.get("text")]
        brief = " / ".join(p[:42] for p in pts[:1])
        lines.append("%d. %s%s" % (c["no"], c["title"][:32],
                                   (" | " + brief) if brief else ""))
    oneline = _section(s, "oneline")
    if oneline:
        lines += ["", "## 已有主旨", oneline[-200:]]
    qs = _questions(s, "aiask", 5) + _questions(s, "quiz", 4)
    if qs:
        lines += ["", "## 已有追问 / 自测问句"] + ["- " + q for q in qs[:9]]
    higher = _section(s, "higher")
    if higher:
        lines += ["", "## 已有更高维度解读", higher[:300]]
    views = _section(s, "views")
    if views:
        lines += ["", "## 已有观点", views[:180]]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", default="")
    ap.add_argument("--missing", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    slugs = ([x.strip() for x in a.slug.split(",") if x.strip()] if a.slug
             else sorted(d.name for d in BOOKS.iterdir() if d.is_dir()))
    n = skip = 0
    for slug in slugs:
        if a.missing and (MIND / (slug + ".json")).exists():
            continue
        try:
            t = material(slug)
        except Exception as e:
            print("  ! %s %s" % (slug, str(e)[:80]))
            skip += 1
            continue
        if not t:
            skip += 1
            continue
        (OUT / (slug + ".txt")).write_text(t, encoding="utf-8")
        n += 1
        if a.limit and n >= a.limit:
            break
    print("导出 %d 本，跳过 %d 本 → %s" % (n, skip, OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
