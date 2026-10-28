#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""rebuild_tree_blocks.py — 把「全书骨架」里退化成静态概览行的书，重建为可折叠章节树。

背景：早期为了控制体积，把章数多 / 原文只有概览行的书渲染成不可点击的静态行
（`li.mm-ch.mm-row`），移动端点了没反应。这里用同目录 outline.json 重新生成
完整的折叠树（章 → 小节），单章小节仍受 30 条上限保护。

幂等：已有 `<li class="mm-ch …"><details>` 的页面跳过。用法：
    python3.11 tools/rebuild_tree_blocks.py           # 预览
    python3.11 tools/rebuild_tree_blocks.py --write   # 落盘
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, '/workspace/we-read-auto/overview_gen')
import mindmap_render as M  # noqa: E402

BOOKS = ROOT / 'reading-notes' / 'books'
BLOCK = re.compile(r'<div class="card mindmap">(.*?)</div>\s*</section>', re.S)
HAS_DETAILS = re.compile(r'<li class="mm-ch [^"]*"><details>')
BY = re.compile(r'<p class="mm-t">.*?<small>(.*?)</small>', re.S)


def rebuild(ov: Path) -> tuple[str, int, int] | None:
    html = ov.read_text(encoding='utf-8')
    m = BLOCK.search(html)
    if not m or 'data-k="tree"' not in m.group(1):
        return None
    if HAS_DETAILS.search(m.group(1)):
        return None  # 已经可折叠
    js = ov.parent / 'outline.json'
    if not js.exists():
        return None
    try:
        items = json.loads(js.read_text(encoding='utf-8'))
    except Exception:  # noqa: BLE001
        return None
    by = BY.search(m.group(1))
    st = M.from_outline_json(items, '', by.group(1) if by else '')
    chapters = st['groups'][0]['chapters']
    if len(chapters) < 3:
        return None
    frag = M.render(st)
    new = html[:m.start()] + '<div class="card mindmap">\n' + frag + '\n</div></section>' + html[m.end():]
    return new, len(chapters), len(frag) // 1024


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--only', default='')
    a = ap.parse_args(argv)
    n = 0
    for ov in sorted(BOOKS.glob('*/overview.html')):
        if a.only and a.only not in ov.parent.name:
            continue
        r = rebuild(ov)
        if not r:
            continue
        new, chs, kb = r
        n += 1
        print('  %s %-42s %3d 章  %3dKB' % ('+' if a.write else '·', ov.parent.name[:42], chs, kb))
        if a.write:
            ov.write_text(new, encoding='utf-8')
    print('共 %d 本%s' % (n, '已写入' if a.write else '（预览，加 --write 落盘）'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
