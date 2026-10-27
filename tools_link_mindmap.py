#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""给有 mindmap.html 的书，在通读页顶部加一行「全书导图」入口（幂等）。

只插一行，插在 <main> 之后；已有 mm-entry 就跳过，不碰其他区块。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BOOKS = HERE / "reading-notes" / "books"
LINE = ('<p class="mm-entry"><a href="mindmap.html">→ 全书导图：主干重排 · 章节功能 · 证据密度</a></p>')
STYLE = ('<style>.mm-entry{margin:.2em 0 1em;font-size:.82rem}'
         '.mm-entry a{color:#6b7a4e;text-decoration:none;border-bottom:1px dotted #8a9b6e}'
         '</style>')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    n = 0
    for mm in sorted(BOOKS.glob("*/mindmap.html")):
        slug = mm.parent.name
        ov = mm.parent / "overview.html"
        if not ov.exists():
            continue
        t = ov.read_text(encoding="utf-8", errors="ignore")
        if "mm-entry" in t:
            print("  = %-46s 已有入口" % slug[:46])
            continue
        m = re.search(r"<main[^>]*>", t)
        if not m:
            print("  ! %-46s 找不到 <main>" % slug[:46])
            continue
        ins = m.end()
        new = (t[:ins] + "\n" + STYLE + LINE + t[ins:])
        print("  + %-46s 插入入口" % slug[:46])
        n += 1
        if a.write:
            ov.write_text(new, encoding="utf-8")
    print("插入 %d 本%s" % (n, "" if a.write else "（未写，加 --write）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
