#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把「精读」（原全书导图，2026-10-28 改名）入口挂到首页卡片上（幂等）。

背景：mindmap.html 生成后只在 overview.html 页面内部有 mm-entry 入口，
首页 index.html 里一个 mindmap 链接都没有，读者从首页点不进去。

本工具做两处挂载：
  1) 通读 tab 的 preread-card（`<!-- preread-card:<slug> -->` 注释包裹）：在该卡的
     .card-actions 最前插入「精读」绿色链接（用户要求精读置前）。
  2) 精读 tab 的日期笔记卡（archive-card，靠 notes/ 链接识别 slug）：在 .card-dates
     书名改为链接（不再用胶囊），点书名直接进精读页。

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

LINK = ('<a class="card-link card-link-green" href="reading-notes/books/%s/mindmap.html">'
        '精读 <span aria-hidden="true">↗</span></a>')
# 精读卡不再插胶囊：书名 <h3> 直接包链接（book-jd-link），点书名即进精读页。
BOOK_NAME_LINK = '<h3><a class="book-jd-link" href="reading-notes/books/%s/mindmap.html">%s</a></h3>'


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
            # 2026-10-28：精读放 action 行最前（用户要求），插在 card-actions 开头
            anchor = '<div class="card-actions">\n'
            i = block.find(anchor)
            if i >= 0:
                j = i + len(anchor)
                block = block[:j] + "          " + (LINK % slug) + "\n" + block[j:]
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
                h3 = re.search(r"<h3>(.*?)</h3>", block)
                if h3:
                    block = (block[:h3.start()]
                             + BOOK_NAME_LINK % (slug, h3.group(1))
                             + block[h3.end():])
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
