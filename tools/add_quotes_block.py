#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""add_quotes_block.py — 在通读页插入「原文摘录」板块。

数据源：we-read-auto/data/we_read.db 的 book_outline 表（quote 字段），
库里没有的书回落到同目录 outline.json 的 level 4。

体量保护：单本超过 900 句时按章配额（每章至少 3 句），章尾注明总句数，
完整清单仍在本书 AI 大纲页。

幂等：已有 <section id="quotes"> 的页面跳过。用法：
    python3.11 tools/add_quotes_block.py           # 预览
    python3.11 tools/add_quotes_block.py --write   # 落盘
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = Path('/workspace/we-read-auto/data/we_read.db')
sys.path.insert(0, '/workspace/we-read-auto/overview_gen')
import mindmap_render as M  # noqa: E402

BOOKS = ROOT / 'reading-notes' / 'books'
GUIDE = re.compile(r'<section[^>]*aria-labelledby="chapter-guide-title"[^>]*>')
BUDGET = 900
WX = re.compile(r'微信读书|微信')


def esc(t: str) -> str:
    t = WX.sub(lambda m: 'AI 读书' if m.group(0) == '微信读书' else 'AI', t or '')
    return html.escape(t, quote=False)


def from_db() -> dict:
    if not DB.exists():
        return {}
    c = sqlite3.connect(DB)
    rows = c.execute(
        'select slug,ch_no,chapter,sec_no,sec,point,quote from book_outline '
        'where quote is not null and quote<>"" '
        'order by slug,ch_no,sec_no,point_no,quote_no')
    data: dict = {}
    for slug, ch_no, chapter, sec_no, sec, point, quote in rows:
        chs = data.setdefault(slug, {})
        ch = chs.setdefault(int(ch_no), {'name': chapter or '', 'items': []})
        seen = {it[0] for it in ch['items']}
        q = (quote or '').strip()
        if q and q not in seen:
            ch['items'].append((q, int(sec_no or 0), (sec or '').strip(), (point or '').strip()))
    return data


def from_json(book_dir: Path) -> dict:
    js = book_dir / 'outline.json'
    if not js.exists():
        return {}
    try:
        items = json.loads(js.read_text(encoding='utf-8'))
    except Exception:  # noqa: BLE001
        return {}
    chs: dict = {}
    cur = None
    sec, point = '', ''
    for it in items:
        lv = it.get('level') or 1
        txt = (it.get('text') or '').strip()
        if not txt:
            continue
        if lv == 1:
            no, name = M.split_chapter((it.get('display') or txt), len(chs) + 1)
            cur = chs.setdefault(len(chs) + 1, {'name': name, 'items': [], 'no': no})
            sec = point = ''
        elif lv == 2:
            sec, point = txt, ''
        elif lv == 3:
            point = txt
        elif lv >= 4 and cur is not None:
            seen = {it[0] for it in cur['items']}
            if txt not in seen:
                cur['items'].append((txt, 0, sec, point))
    return {k: v for k, v in chs.items() if v['items']}


def quote_char(t: str) -> str:
    t = t.strip()
    if t.startswith('「') or t.startswith('“') or t.startswith('"'):
        return t
    return '「%s」' % t


def build_block(slug: str, chs: dict) -> tuple[str, int, int]:
    keys = sorted(chs)
    total = sum(len(chs[k]['items']) for k in keys)
    per = max(3, BUDGET // len(keys)) if total > BUDGET else 0
    rows, shown = [], 0
    for i, k in enumerate(keys, 1):
        c = chs[k]
        items = c['items'] if not per else c['items'][:per]
        if not items:
            continue
        li = []
        for q, sec_no, sec, point in items:
            src = ''
            if sec:
                src = '第 %d 节 · %s' % (sec_no, sec) if sec_no else sec
            elif point:
                src = point
            elif point:
                src = point
            li.append('<li class="q-item"><p class="q-text">%s</p>%s</li>'
                      % (esc(quote_char(q)),
                         ('<p class="q-from">%s</p>' % esc(src[:60])) if src else ''))
        shown += len(items)
        more = ''
        if len(c['items']) > len(items):
            more = ('<p class="q-more">本章共 %d 句，此处列前 %d 句；完整清单见本书 AI 大纲页。</p>'
                    % (len(c['items']), len(items)))
        name = c.get('name') or ''
        _, clean = M.split_chapter(name, i)
        no = c.get('no') or k  # 章号用库里的真实序号，避免「第三分」被重排成 1、2、3
        rows.append(
            '<details class="q-ch" id="q-%s"%s><summary><span class="q-line">'
            '<span class="q-no">%s</span><span class="q-name">%s</span>'
            '<span class="q-cnt">%d 句</span></span></summary>'
            '<div class="q-body"><ol class="q-list">%s</ol>%s</div></details>'
            % (k, ' open' if i == 1 else '', esc(str(no)), esc(clean),
               len(c['items']), ''.join(li), more))
    intro = ('<p class="q-intro">AI 大纲讲到原句的地方，按章归拢在这里：共 <b>%d</b> 句，'
             '覆盖 <b>%d</b> 章（只列有原句的章，序号与上方骨架一致）。'
             '展开看原文，灰色小字是出处小节。'
             % (total, len(keys)))
    if per:
        intro += '（单本篇幅大，每章展示前 %d 句，完整清单见 AI 大纲页。）' % per
    intro += '</p>'
    block = ('\n<section id="quotes" aria-labelledby="quotes-title">\n'
             '<h2 id="quotes-title">原文摘录</h2>\n%s\n<div class="q-wrap">\n%s\n</div>\n</section>\n'
             % (intro, '\n'.join(rows)))
    return block, total, shown


def find_section_end(html_text: str, start: int) -> int:
    """从 <section ...> 的结束位置起，找与之配对的 </section>（考虑嵌套）。"""
    depth, i = 1, start
    pat = re.compile(r'</?section\b', re.I)
    while True:
        m = pat.search(html_text, i)
        if not m:
            return -1
        if html_text[m.start():m.start() + 2] == '</':
            depth -= 1
            i = m.end()
            if depth == 0:
                return html_text.find('>', m.start()) + 1
        else:
            depth += 1
            i = m.end()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--only', default='')
    ap.add_argument('--rebuild', action='store_true', help='删掉已有模块再重插')
    a = ap.parse_args(argv)
    db = from_db()
    n = skipped = 0
    for ov in sorted(BOOKS.glob('*/overview.html')):
        slug = ov.parent.name
        if a.only and a.only not in slug:
            continue
        t = ov.read_text(encoding='utf-8')
        if 'id="quotes"' in t:
            if not a.rebuild:
                skipped += 1
                continue
            m0 = re.search(r'<section id="quotes"[^>]*>', t)
            end0 = find_section_end(t, m0.end()) if m0 else -1
            if end0 < 0:
                skipped += 1
                continue
            t = t[:m0.start()].rstrip('\n') + '\n' + t[end0:].lstrip('\n')
        chs = db.get(slug) or from_json(ov.parent)
        if not chs:
            continue
        block, total, shown = build_block(slug, chs)
        m = GUIDE.search(t)
        if m:
            end = find_section_end(t, m.end())
            if end < 0:
                print('  ! %-40s 找不到章节导读结束位置' % slug[:40])
                continue
            new = t[:end] + block + t[end:]
        else:
            i = t.rfind('</main>')
            if i < 0:
                continue
            new = t[:i] + block + t[i:]
        n += 1
        if n <= 6 or n % 15 == 0:
            print('  %s %-40s %4d 句 / %d 章  展示 %d  块 %3dKB'
                  % ('+' if a.write else '·', slug[:40], total, len(chs), shown, len(block) // 1024))
        if a.write:
            ov.write_text(new, encoding='utf-8')
    print('共 %d 本%s，已存在 %d 本' % (n, '已写入' if a.write else '（预览）', skipped))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
