#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把「全书导图」入口挂到首页卡片上（幂等）。

背景：mindmap.html 生成后只在 overview.html 页面内部有 mm-entry 入口，
首页 index.html 里一个 mindmap 链接都没有，读者从首页点不进去。

本工具做两处挂载：
  1) 通读 tab 的 preread-card（`<!-- preread-card:<slug> -->` 注释包裹）：在该卡的
     .card-actions 末尾追加「全书导图」链接。55 本有导图的书全部有通读卡。
  2) 精读 tab 的日期笔记卡（archive-card，靠 notes/ 链接识别 slug）：在 .card-dates
     之前插入一行「全书导图」链接。读者看完某天笔记想跳去看全书结构。

两处都只补缺，不覆盖已有链接；跑第二遍 diff 为空。

用法：
    python tools_link_mindmap_index.py            # 预演
    python tools_link_mindmap_index.py --write    # 落盘
"""
import argparse
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE / "index.html"
BOOKS = HERE / "reading-notes" / "books"

LINK = ('<a class="card-link card-link-strong" href="reading-notes/books/%s/mindmap.html">'
        '全书导图 <span aria-hidden="true">↗</span></a>')
NOTE_LINK = ('<a class="mm-note-link" href="reading-notes/books/%s/mindmap.html">'
             '本书全书导图 <span aria-hidden="true">↗</span></a>')


def mindmap_slugs():
    return {p.parent.name for p in BOOKS.glob("*/mindmap.html")}


def patch_preread(html, have):
    """通读卡：在 .card-actions 的收尾 </div> 前追加导图链接。"""
    added = []
    out = []
    pos = 0
    for m in re.finditer(r"<!-- preread-card:([^\s]+) -->", html):
        slug = m.group(1)
        out.append(html[pos:m.start()])
        # 该卡的 </article> 位置
        end = html.find("</article>", m.end())
        if end < 0:
            out.append(html[m.start():m.end()])
            pos = m.end()
            continue
        block = html[m.start():end + len("</article>")]
        if slug in have and "mindmap.html" not in block:
            # 找该块内最后一个 </div> 之前的 card-actions 收口
            act = block.rfind('</div>')
            if act > 0:
                head = block[:act].rstrip()
                block = head + "\n          " + (LINK % slug) + "\n        " + block[act:]
                added.append(slug)
        out.append(block)
        pos = end + len("</article>")
    out.append(html[pos:])
    return "".join(out), added


def patch_notes(html, have):
    """精读卡：在 .card-dates 之前插一行导图链接（只处理有导图且有日期笔记的书）。"""
    added = []
    # 逐张 archive-card 处理：块内若含 notes/<slug>/ 且有 mindmap，则插链接
    out = []
    pos = 0
    for m in re.finditer(r'<article class="archive-card"', html):
        if m.start() < pos:
            continue
        end = html.find("</article>", m.start())
        if end < 0:
            continue
        block = html[m.start():end + len("</article>")]
        slug_m = re.search(r"reading-notes/books/([^/\"]+)/notes/", block)
        if slug_m:
            slug = slug_m.group(1)
            if slug in have and "mindmap.html" not in block:
                cd = block.rfind('<div class="card-dates"')
                if cd > 0:
                    block = block[:cd] + (NOTE_LINK % slug) + "\n        " + block[cd:]
                    added.append(slug)
        out.append(html[pos:m.start()])
        out.append(block)
        pos = end + len("</article>")
    out.append(html[pos:])
    return "".join(out), added


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    have = mindmap_slugs()
    html = INDEX.read_text(encoding="utf-8")
    n0 = len(html)

    html, a1 = patch_preread(html, have)
    html, a2 = patch_notes(html, have)

    print("有导图的书：%d 本" % len(have))
    print("通读卡新增入口：%d 张" % len(a1))
    print("精读卡新增入口：%d 张" % len(a2))
    if not a1 and not a2:
        print("无需改动（幂等）")
        return
    print("长度变化：%+d 字节" % (len(html) - n0))
    if a.write:
        INDEX.write_text(html, encoding="utf-8")
        print("已写入 index.html")
    else:
        print("预演模式，未落盘。加 --write 生效")


if __name__ == "__main__":
    main()
