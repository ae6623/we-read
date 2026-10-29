#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""统一单书页的「精读」入口：只留「从这里开始」导航块里的一处（2026-10-29）。

背景：本轮先给通读页顶部补过 mm-entry 一行，后来发现云端的 IA-05 方案已经在首屏
插了 `.start-here` 导航块（含「下一步：精读 · 全书主干」），两处重复。本工具：
  1) 有 mindmap.html 但 start-here 里没有精读链接的，把链接补进 sh-links 首位；
  2) 删掉顶部的 mm-entry（含它内联的 <style>），全站只保留导航块一处入口。
幂等：跑第二遍 diff 为空。用法：python tools/fix_jingdu_entry.py [--write]
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
BOOKS = HERE / "reading-notes" / "books"

SPAN = '<span><a href="mindmap.html">下一步：精读 · 全书主干 →</a></span>'
MM_ENTRY = re.compile(
    r'<style>\.mm-entry\{[^<]*</style>\s*<p class="mm-entry">.*?</p>\s*', re.S)
MM_ENTRY_LOOSE = re.compile(r'<p class="mm-entry">.*?</p>\s*', re.S)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    n_link = n_del = 0
    for d in sorted(BOOKS.iterdir()):
        ov = d / "overview.html"
        if not ov.exists():
            continue
        t = ov.read_text(encoding="utf-8", errors="ignore")
        old = t
        if (d / "mindmap.html").exists():
            m = re.search(r'<p class="sh-links">(.*?)</p>', t, re.S)
            if m and "mindmap.html" not in m.group(1):
                t = t[:m.start(1)] + SPAN + m.group(1) + t[m.end(1):]
                n_link += 1
        t2 = MM_ENTRY.sub("", t)
        if t2 == t:
            t2 = MM_ENTRY_LOOSE.sub("", t)
        if t2 != t:
            n_del += 1
        if a.write and t2 != old:
            ov.write_text(t2, encoding="utf-8", newline="\n")
    print("补导航块精读链接 %d 本；删顶部重复入口 %d 本%s"
          % (n_link, n_del, "" if a.write else "（未写，加 --write）"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
