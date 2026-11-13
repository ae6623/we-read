#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「修不好的书」从首页书架挪到归档 Tab，首页只留能读的。

背景（2026-11-13）
------------------
assets/data/template-audit.json 把全站详情页分了五档，其中 empty（连
combined-data 都没有）和 dump（还挂着几百 KB 旧版脑图 dump）两类，
在首页就是「点进去没啥可读」的死链。用户要求：能修的放主页，修不好的
放归档。

本脚本只动 DOM 位置，不删信息：
  - 从 #panel-whole 的 .archive-grid 里「整块搬走」对应 article（连前面
    的 preread-card 注释一起），原样插入归档面板新建的 #pending-grid。
  - 卡片 HTML 一字不改，所以封面/链接/搜索词都保真，随时可搬回来。

用法
  python3 tools/archive_unfixable.py --dry-run
  python3 tools/archive_unfixable.py
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, "index.html")
AUDIT = os.path.join(ROOT, "assets", "data", "template-audit.json")

PENDING_ANCHOR = 'id="pending-grid"'


def find_block(h, start_marker):
    """返回 (content_start, content_end)：start_marker 所在 div 的内容区间。"""
    i = h.find(start_marker)
    if i < 0:
        raise SystemExit("找不到 %s" % start_marker)
    open_end = h.find(">", i) + 1
    depth, p = 1, open_end
    while p < len(h):
        m = re.compile(r"<div\b|</div>").search(h, p)
        if not m:
            break
        depth += 1 if m.group(0).startswith("<div") else -1
        if depth == 0:
            return open_end, m.start()
        p = m.end()
    raise SystemExit("div 不配对：%s" % start_marker)


def cut_article(h, slug):
    """从整页里切出一张卡片（含紧邻的 preread-card 注释），返回 (新 html, 卡片 html)。"""
    pat = re.compile(
        r'(?:[ \t]*<!--\s*preread-card:%s\s*-->\s*)?<article\b[^>]*data-slug="%s"[^>]*>.*?</article>'
        % (re.escape(slug), re.escape(slug)), re.S)
    ms = list(pat.finditer(h))
    if not ms:
        return h, None
    if len(ms) > 1:
        raise SystemExit("slug 重复出现 %d 次：%s" % (len(ms), slug))
    m = ms[0]
    return h[:m.start()] + h[m.end():], m.group(0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--slugs", nargs="*", help="覆盖默认清单")
    args = ap.parse_args()

    audit = json.load(open(AUDIT, encoding="utf-8"))
    slugs = args.slugs or audit["archiveSlugs"]

    h = open(HTML, encoding="utf-8").read()
    before = {
        "article": len(re.findall(r"<article\b", h)),
        "div_open": len(re.findall(r"<div\b", h)),
        "div_close": h.count("</div>"),
        "h3": len(re.findall(r"<h3\b", h)),
    }

    whole_start, whole_end = find_block(h, 'id="panel-whole"')
    whole = h[whole_start:whole_end]
    books = audit["books"]

    cut, kept = [], []
    for s in slugs:
        if 'data-slug="%s"' % s not in whole:
            continue
        if PENDING_ANCHOR in h and 'data-slug="%s"' % s in h[h.find(PENDING_ANCHOR):]:
            continue
        whole, card = cut_article(whole, s)
        if card:
            cut.append((s, card))
    h = h[:whole_start] + whole + h[whole_end:]

    # 归档面板里追加「待补全」分区（已有就不重复加）
    if cut and PENDING_ANCHOR not in h:
        a_start, a_end = find_block(h, 'id="archive-grid"')
        block = (
            '<p class="panel-intro">待补全 · 以下 %d 本还缺整书笔记，或仍是旧版脑图 dump，'
            "先收在这里；补好内容再放回书架。</p>"
            '<div class="archive-grid" id="pending-grid" aria-label="待补全书目">%s</div>'
            % (len(cut), "".join(c for _s, c in cut))
        )
        # archive-grid 的 div 闭合标签之后插入
        insert_at = a_end + len("</div>")
        h = h[:insert_at] + block + h[insert_at:]
    elif cut:
        # 已有 pending-grid：直接追加
        p_start, p_end = find_block(h, PENDING_ANCHOR)
        h = h[:p_end] + "".join(c for _s, c in cut) + h[p_end:]

    after = {
        "article": len(re.findall(r"<article\b", h)),
        "div_open": len(re.findall(r"<div\b", h)),
        "div_close": h.count("</div>"),
        "h3": len(re.findall(r"<h3\b", h)),
    }

    print("搬走 %d 本：" % len(cut))
    for s, _c in cut:
        print("   -", s, "|", books.get(s, {}).get("status"), "|",
              (books.get(s, {}).get("title") or "")[:26])

    # ── 断言：只搬位置，不损内容 ──────────────────────────────
    assert after["article"] == before["article"], "article 数量变了 %s -> %s" % (before["article"], after["article"])
    assert after["h3"] == before["h3"], "h3 数量变了"
    assert after["div_open"] == after["div_close"], "div 不平衡 %s/%s" % (after["div_open"], after["div_close"])
    assert after["div_open"] - before["div_open"] in (0, 1), "div 增量异常：%d" % (after["div_open"] - before["div_open"])
    assert h.count('id="panel-whole"') == 1
    assert h.count('id="archive-grid"') == 1
    print("断言通过：article=%d h3=%d div=%d/%d" % (after["article"], after["h3"], after["div_open"], after["div_close"]))

    if args.dry_run:
        print("(dry-run，未写文件)")
        return
    open(HTML, "w", encoding="utf-8").write(h)
    print("已写入", HTML)


if __name__ == "__main__":
    main()
