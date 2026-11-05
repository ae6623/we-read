#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 json 里的 evidence_ref（章号）展开成素材原文，写回 evidence 并删除 ref。

为什么要有这一步：
  手写 evidence 要复制长句，容易改字、容易超 40 字、容易记错出处。
  改成只写「哪一章」，由脚本取该章要点原文（自动截到 40 字内），
  命中率必然 100%，也省掉大量复制粘贴的 token。

json 写法：
  {
    "branches": [...],
    "evidence_ref": {
      "强势文化循规律": [12, 15],
      "王庙村格律诗": [3, 8]
    }
  }
  → 展开后 evidence_ref 被删除，evidence 写入对应原文。

用法：
  python3 tools/expand_evidence.py <slug>
  python3 tools/expand_evidence.py --batch a,b,c
  python3 tools/expand_evidence.py --all      # 只处理含 evidence_ref 的
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MM = ROOT / "data" / "mm-graph"
MAT = ROOT / "data" / "mindmap-material"

SEC = re.compile(r"##\s*章节与要点\s*\n(.*?)(?=\n##\s|\Z)", re.S)
# 行首条目号 + 行内可能还有章节号（1. 7 | 要点 / 1. 1 · 章名 | 要点），
# 统一只认行首序号，要点取最后一个 | 之后的部分。
LINE = re.compile(r"^\s*(\d+)\s*[.、]\s*(.*)$")
MAXLEN = 40
END = "。！？；，：、…）」”"


def parse_items(slug: str) -> dict[int, str]:
    """条目号（行首）→ 该行要点原文。"""
    p = MAT / (slug + ".txt")
    if not p.exists():
        raise FileNotFoundError(f"缺素材 {p}")
    text = p.read_text(encoding="utf-8", errors="ignore")
    m = SEC.search(text)
    body = m.group(1) if m else text
    out: dict[int, str] = {}
    for line in body.splitlines():
        g = LINE.match(line)
        if not g or "|" not in g.group(2):
            continue
        out[int(g.group(1))] = g.group(2).rsplit("|", 1)[-1].strip()
    return out


def clip(s: str, n: int = MAXLEN) -> str:
    """截到 n 字内，优先收在句末，退而收在逗号前，避免半句断在标点上。"""
    s = (s or "").strip()
    if len(s) <= n:
        return s
    cut = s[:n]
    for marks in ("。！？；…", "，、："):
        pos = max((cut.rfind(c) for c in marks), default=-1)
        if pos >= 12:
            return cut[:pos] if marks == "，、：" else cut[:pos + 1]
    return cut


def expand(slug: str, dry: bool = False) -> tuple[int, list[str]]:
    jp = MM / (slug + ".json")
    if not jp.exists():
        return 0, [f"{slug}: 缺 json"]
    d = json.loads(jp.read_text(encoding="utf-8"))
    ref = d.get("evidence_ref")
    if not ref:
        return 0, []
    chs = parse_items(slug)
    ev = d.get("evidence") or {}
    errs: list[str] = []
    n = 0
    for concept, nums in ref.items():
        items: list[str] = []
        for x in (nums if isinstance(nums, list) else [nums]):
            try:
                no = int(x)
            except (TypeError, ValueError):
                errs.append(f"{slug}「{concept}」条目号非法：{x!r}")
                continue
            if no not in chs:
                errs.append(f"{slug}「{concept}」引用第 {no} 条，素材里没有")
                continue
            txt = clip(chs[no])
            if txt and txt not in items:
                items.append(txt)
        if items:
            ev[concept] = items[:3]
            n += 1
    if errs:
        return n, errs
    d["evidence"] = ev
    d.pop("evidence_ref", None)
    if not dry:
        jp.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return n, []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--slug", dest="slug_opt", default="",
                    help="slug 以 - 开头时用这个（argparse 会把 -xxx 当选项）")
    ap.add_argument("--batch", default="")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    if a.all:
        slugs = [p.stem for p in sorted(MM.glob("*.json"))
                 if "evidence_ref" in p.read_text(encoding="utf-8", errors="ignore")]
    elif a.batch:
        slugs = [x.strip() for x in a.batch.split(",") if x.strip()]
    else:
        one = a.slug_opt or a.slug
        slugs = [one] if one else []
    if not slugs:
        ap.print_help()
        return 1

    total = bad = 0
    for s in slugs:
        n, errs = expand(s, a.dry)
        total += n
        if errs:
            bad += 1
            print(f"✗ {s}")
            for e in errs:
                print("   -", e)
    print(f"展开 {len(slugs)} 本 / {total} 个概念，失败 {bad} 本" + ("（dry-run 未写盘）" if a.dry else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
