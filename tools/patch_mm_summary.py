#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""patch_mm_summary.py — 给「全书结构」章节卡的 summary 内层加 span.mm-line。

背景：summary 直接 display:flex 时，iOS Safari 会丢掉点击热区（点章节名不展开）。
修法是把行内布局移到内层元素，summary 本身保持 list-item。

幂等：已含 mm-line 的跳过。用法：
    python3.11 tools/patch_mm_summary.py           # 预览
    python3.11 tools/patch_mm_summary.py --write   # 落盘
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOKS = ROOT / 'reading-notes' / 'books'
# 只动章节卡的 summary（<li class="mm-ch"><details><summary>…</summary>）
PAT = re.compile(r'(<li class="mm-ch[^"]*"><details><summary>)(.*?)(</summary>)', re.S)


def wrap(html: str) -> tuple[str, int]:
    hits = {'n': 0}

    def repl(m):
        inner = m.group(2)
        if 'mm-line' in inner:
            return m.group(0)
        hits['n'] += 1
        return m.group(1) + '<span class="mm-line">' + inner + '</span>' + m.group(3)

    return PAT.sub(repl, html), hits['n']


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args(argv)
    files = changed = total = 0
    for ov in sorted(BOOKS.glob('*/overview.html')):
        t = ov.read_text(encoding='utf-8')
        if 'class="mm"' not in t:
            continue
        new, n = wrap(t)
        if n:
            files += 1
            total += n
            if a.write:
                ov.write_text(new, encoding='utf-8')
                changed += 1
    print('%s：%d 个文件，%d 个章节卡' % ('已写入' if a.write else '待处理', files, total))
    if a.write:
        print('实际写入 %d 个文件' % changed)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
