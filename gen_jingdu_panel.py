#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重生成首页「精读」面板的卡片：覆盖所有有整书精读页(mindmap.html)的书。

背景：精读面板原本只精选了少量「日期笔记」卡（11 张），而仓库里 73 本已有
整书精读页(mindmap.html)。本脚本把这些书的精读页做成统一卡片，让精读页签不再空荡。

卡片来源字段（全部取自各书的 mindmap.html，不伪造内容）：
  - 书名：<title>《X》｜精读</title> 或 <h1>《X》精读</h1>
  - 摘要：<p class="mmx-claim">…</p>（全书核心论点）
  - 时间：mindmap.html 的修改时间（mtime），转 ISO，用于倒序（新书在上）
  - 链接：mindmap.html（精读页）

data-ts / data-search / data-mode 与书架面板卡片对齐，复用首页已有的排序与搜索逻辑。

用法：
    python gen_jingdu_panel.py            # 预演（打印将生成的卡片数与前 3 张）
    python gen_jingdu_panel.py --write   # 落盘
"""
import argparse
import os
import re
import sys
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "index.html")
BOOKS = os.path.join(HERE, "reading-notes", "books")
TZ = timezone(timedelta(hours=8))


def strip_tags(s):
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip()


def extract(slug):
    """从 mindmap.html 提取卡片字段；失败返回 None。"""
    mp = os.path.join(BOOKS, slug, "mindmap.html")
    if not os.path.exists(mp):
        return None
    html = open(mp, encoding="utf-8", errors="ignore").read()
    # 书名
    title = None
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    if m:
        title = m.group(1).replace("｜精读", "").replace("|精读", "").replace("精读", "").strip(" 《》")
    if not title:
        m = re.search(r"<h1>(.*?)</h1>", html, re.S)
        if m:
            title = m.group(1).replace("精读", "").strip(" 《》")
    if not title:
        return None
    # 摘要（全书核心论点）
    claim = ""
    m = re.search(r'<p class="mmx-claim">(.*?)</p>', html, re.S)
    if m:
        claim = strip_tags(m.group(1))
    if len(claim) > 64:
        claim = claim[:63].rstrip("，。、") + "…"
    # 时间
    mt = os.path.getmtime(mp)
    ts = datetime.fromtimestamp(mt, TZ).strftime("%Y-%m-%dT%H:%M:%S")
    date = ts[:10]
    return {
        "slug": slug,
        "title": title,
        "claim": claim,
        "ts": ts,
        "date": date,
    }


def build_card(d):
    href = f"reading-notes/books/{d['slug']}/mindmap.html"
    search = f"{d['title']} 精读 {d['claim']}"
    return (
        f'      <article class="archive-card" data-ts="{d["ts"]}" '
        f'data-search="{search}" data-mode="whole jingdu archive">\n'
        f'        <div class="card-top"><span class="type-tag type-tag-gold">精读</span>'
        f'<time datetime="{d["date"]}">{d["date"][5:]}</time></div>\n'
        f'        <h3><a class="book-jd-link" href="{href}">{d["title"]}</a></h3>\n'
        f'        <p>{d["claim"]}</p>\n'
        f'      </article>\n'
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    books = sorted(p for p in os.listdir(BOOKS)
                   if os.path.isdir(os.path.join(BOOKS, p)))
    rows = []
    for slug in books:
        d = extract(slug)
        if d:
            rows.append(d)
    rows.sort(key=lambda x: x["ts"], reverse=True)  # 倒序：新书在上
    cards = "".join(build_card(d) for d in rows)

    html = open(INDEX, encoding="utf-8").read()
    # 定位精读面板内第一个 archive-grid（用括号配对找真实闭合，避免卡片内嵌套 div 干扰）
    panel_start = html.find('<section id="reading-panel-close"')
    if panel_start < 0:
        print("! 找不到 reading-panel-close 面板"); sys.exit(1)
    grid_start = html.find('<div class="archive-grid"', panel_start)
    if grid_start < 0:
        print("! 精读面板内找不到 archive-grid"); sys.exit(1)

    def find_grid_close(h, open_tag_start):
        depth = 1  # grid 自身算一层
        j = h.find(">", open_tag_start) + 1
        n = len(h)
        while j < n:
            lt = h.find("<", j)
            if lt < 0:
                return -1
            if h.startswith("</div>", lt):
                depth -= 1
                if depth == 0:
                    return lt
                j = lt + 6
            elif h.startswith("<div", lt):
                depth += 1
                j = lt + 4
            else:
                j = lt + 1
        return -1

    grid_open_end = html.find(">", grid_start) + 1
    grid_close = find_grid_close(html, grid_start)
    if grid_close < 0:
        print("! 找不到 archive-grid 闭合标签"); sys.exit(1)
    new_html = html[:grid_open_end] + "\n" + cards + "      " + html[grid_close:]

    if not args.write:
        print(f"预演：将生成 {len(rows)} 张精读卡片（原 {html[grid_open_end:grid_close].count('<article')} 张）")
        for d in rows[:3]:
            print(f"  {d['ts']}  {d['title']}  — {d['claim'][:30]}")
        print("（加 --write 落盘）")
        return
    open(INDEX, "w", encoding="utf-8", newline="\n").write(new_html)
    print(f"已写入：精读面板 {len(rows)} 张卡片")


if __name__ == "__main__":
    main()
