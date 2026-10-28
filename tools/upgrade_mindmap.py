#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""upgrade_mindmap.py — 把通读页「全书结构与主题关系」的纯文本树，就地升级成
章节折叠卡（章号色块 + 小节胶囊 + 全部展开/收起）。

数据来源优先级：
  1. 同目录 outline.json（level 1/2/3/4 层级完整，小节名不会被 48 字截断）
  2. 页面里原有的文本（├─ 树 / 分组要点 / 散文式）

幂等：已是新版（含 class="mm"）的区块跳过。用法：
    python3.11 tools/upgrade_mindmap.py            # 预览
    python3.11 tools/upgrade_mindmap.py --write    # 落盘
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUTO = Path('/workspace/we-read-auto')
sys.path.insert(0, str(AUTO / 'overview_gen'))
import mindmap_render as M  # noqa: E402

BOOKS = ROOT / 'reading-notes' / 'books'
BLOCK = re.compile(r'<div class="card mindmap">(.*?)</div>', re.S)
H1 = re.compile(r'<h1>《(.+)》\s*</h1>')
META = re.compile(r'作者：([^　<·]+)')
SCRIPT = '<script src="../../../assets/js/mindmap.js" defer></script>'


def build_block(ov_html: str, book_dir: Path) -> tuple[str, str]:
    """返回 (新 HTML 片段, 来源说明)。"""
    h1 = H1.search(ov_html)
    title = h1.group(1) if h1 else ''
    meta = META.search(ov_html)
    author = (meta.group(1).strip() if meta else '')
    m = BLOCK.search(ov_html)
    raw = m.group(1) if m else ''
    text_st = M.parse_text(raw) if raw else None
    # 手写分组（一、/《篇名》· N 节）自带语义分段，比 JSON 的扁平章节更有信息量，保留原文结构
    if text_st and text_st['kind'] == 'flat':
        text_st['title'] = text_st['title'] or title
        text_st['by'] = author
        return M.render(text_st), 'text'
    js = book_dir / 'outline.json'
    if js.exists():
        try:
            items = json.loads(js.read_text(encoding='utf-8'))
            st = M.from_outline_json(items, title, author)
            chs = st['groups'][0]['chapters']
            n_json = len(chs)
            n_text = len(text_st['groups'][0]['chapters']) if text_st and text_st['kind'] == 'tree' else 0
            # 原文树和 JSON 同源（根节点数一致）才用 JSON 补全小节名；
            # 不一致说明原文是人工/生成时做过的聚类概览（如「5 卷」对「295 章」），保留原文更可读
            ok = n_json >= 2 and (n_text == 0 or abs(n_json - n_text) <= 1)
            if ok:
                return M.render(st), 'json'
            print('    - %-40s JSON %d 章 vs 原文 %d → 保留原文概览' % (book_dir.name[:40], n_json, n_text))
        except Exception as e:  # noqa: BLE001
            print('    ! json 解析失败 %s: %s' % (book_dir.name, e))
    if not text_st:
        return '', 'none'
    text_st['title'] = text_st['title'] or title
    text_st['by'] = author
    return M.render(text_st), text_st['kind']


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--only', default='', help='只处理 slug 含该子串的书')
    a = ap.parse_args(argv)
    n_ok = n_skip = 0
    for ov in sorted(BOOKS.glob('*/overview.html')):
        slug = ov.parent.name
        if a.only and a.only not in slug:
            continue
        t = ov.read_text(encoding='utf-8')
        m = BLOCK.search(t)
        if not m:
            n_skip += 1
            continue
        if 'class="mm"' in m.group(1):
            print('  = %-44s 已是新版' % slug[:44])
            n_skip += 1
            continue
        frag, src = build_block(t, ov.parent)
        if not frag:
            print('  ! %-44s 无结构文本' % slug[:44])
            n_skip += 1
            continue
        new = t[:m.start()] + '<div class="card mindmap">\n' + frag + '\n</div>' + t[m.end():]
        if 'assets/js/mindmap.js' not in new:
            new = new.replace('</body>', SCRIPT + '\n</body>', 1)
        print('  + %-44s %-5s %5.1fKB' % (slug[:44], src, len(frag) / 1024))
        n_ok += 1
        if a.write:
            ov.write_text(new, encoding='utf-8')
    print('升级 %d 本，跳过 %d 本%s' % (n_ok, n_skip, '' if a.write else '（预览，加 --write 落盘）'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
