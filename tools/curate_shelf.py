#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""书架策展：老模板移归档 + 归档里的新模板回书架。

背景（2026-11-21 用户反馈）
--------------------------
用户看到「邓小平时代」有两张卡：一张 0 章 + AI 大纲入口的老模板，
一张「全书视角初版」老模板，都混在书架上。书架上共 7 个 slug 各有
「正式版 + 全书视角初版」两张并存卡；归档里另有几本已有章节统计的
新模板书（有真封），应回到书架。

规则（严格，按 slug 精确匹配，绝不误伤正常 0 章的轻游记）
--------------------------------------------------------
1. 书架 → 归档：只移「标题含『全书视角初版』」的老模板卡。若同 slug
   有正式版且正式版内容更多，则保留正式版；否则保留分高的那张。
2. 归档 → 书架：归档(#pending-grid / #archive-grid)里带「共 N 章 / M 条」
   章节统计的新模板卡搬回书架。

全程只搬 DOM（连 preread-card 注释整块），一字不改卡片 HTML。带断言：
article/h3 总数不变、div 平衡。

用法
  python3 tools/curate_shelf.py --dry-run
  python3 tools/curate_shelf.py
  python3 tools/curate_shelf.py --shelf-to-archive slug1 slug2   # 覆盖自动判定
  python3 tools/curate_shelf.py --archive-to-shelf slug3        # 覆盖自动判定
"""
import argparse
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, "index.html")

TAG_RE = re.compile(r"</?(?:section|div)\b")
CARD_RE_TMPL = (r'(?:[ \t]*<!--\s*preread-card:[^\s]*\s*-->\s*)?'
                r'<article\b[^>]*data-slug="%s"[^>]*>.*?</article>')


def section_bounds(h, marker, end_marker):
    """返回 [marker 开标签结束, end_marker 起始) 区间。
    panel-whole 内嵌复杂 section，不用标签配对，直接用下一同级面板 id 划界。"""
    i = h.find(marker)
    if i < 0:
        raise SystemExit("找不到 %s" % marker)
    open_end = h.find(">", i) + 1
    e = h.find(end_marker, open_end)
    if e < 0:
        raise SystemExit("找不到结束标记 %s" % end_marker)
    return open_end, e


def div_bounds(h, marker):
    """返回 marker 所在 <div> 的 (content_start, content_end)。"""
    i = h.find(marker)
    if i < 0:
        raise SystemExit("找不到 %s" % marker)
    tag_start = h.rfind("<div", 0, i)
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
    raise SystemExit("div 不配对：%s" % marker)


def card_info(block):
    a = re.search(r"<article\b([^>]*)>", block)
    a = a.group(1) if a else ""
    tm = re.search(r"<h3[^>]*>(.*?)</h3>", block, re.S)
    title = re.sub(r"<[^>]+>", "", tm.group(1)).strip() if tm else "?"
    slug = (re.search(r'data-slug="([^"]*)"', a) or [None, ""])[1]
    ds = (re.search(r'data-search="([^"]*)"', a) or [None, ""])[1]
    ch = re.search(r"共\s*(\d+)\s*章\s*/\s*(\d+)\s*条", ds)
    chapters = int(ch.group(1)) if ch else 0
    items = int(ch.group(2)) if ch else 0
    return {
        "slug": slug, "title": title, "chapters": chapters, "items": items,
        "has_ch": bool(ch), "view_init": "全书视角初版" in title,
        "score": chapters * 100000 + items,
    }


def cut_cards(seg, slug):
    """从片段切出该 slug 的所有卡片，返回 (剩余, [卡片...])。"""
    pat = re.compile(CARD_RE_TMPL % re.escape(slug), re.S)
    found = list(pat.finditer(seg))
    cards = [m.group(0) for m in found]
    out, last = [], 0
    for m in found:
        out.append(seg[last:m.start()])
        last = m.end()
    out.append(seg[last:])
    return "".join(out), cards


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--shelf-to-archive", nargs="*")
    ap.add_argument("--archive-to-shelf", nargs="*")
    args = ap.parse_args()

    h = open(HTML, encoding="utf-8").read()
    before = {
        "article": len(re.findall(r"<article\b", h)),
        "h3": len(re.findall(r"<h3\b", h)),
        "div": len(re.findall(r"<div\b", h)) - h.count("</div>"),
    }

    # 容器区间（用绝对字符位置，边操作边重算）
    ws, we = section_bounds(h, 'id="panel-whole"', 'id="panel-soon"')
    whole = h[ws:we]
    ps, pe = div_bounds(h, 'id="pending-grid"')
    pending = h[ps:pe]
    ags, age = div_bounds(h, 'id="archive-grid"')
    archive = h[ags:age]

    # 书架卡片按 slug 分组
    shelf_cards = list(re.finditer(r"<article\b[^>]*data-slug=\"[^\"]*\"[^>]*>.*?</article>", whole, re.S))
    groups = {}
    for m in shelf_cards:
        info = card_info(m.group(0))
        groups.setdefault(info["slug"], []).append(m.group(0))

    # ── 判定书架→归档 ──────────────────────────────────────
    if args.shelf_to_archive is not None:
        move_cards = {s: groups.get(s, []) for s in args.shelf_to_archive}
    else:
        move_cards = {}
        for s, blocks in groups.items():
            infos = [card_info(b) for b in blocks]
            init_idx = [i for i, x in enumerate(infos) if x["view_init"]]
            if not init_idx:
                continue
            if len(blocks) == 1:
                move_cards[s] = blocks
                continue
            i_init = max(init_idx, key=lambda i: infos[i]["score"])
            formal = [i for i in range(len(blocks)) if i not in init_idx]
            if not formal:
                continue
            i_formal = max(formal, key=lambda i: infos[i]["score"])
            drop_idx = [i_formal] if infos[i_init]["score"] > infos[i_formal]["score"] else [i_init]
            move_cards[s] = [blocks[i] for i in drop_idx]

    print("=== 书架 → 归档 ===")
    moved = []
    for s, blocks in move_cards.items():
        whole, cut = cut_cards(whole, s)
        # cut 含该 slug 的全部卡；只把 blocks 移走，其余（正式版）插回原位
        keep = [c for c in cut if c not in blocks]
        for b in blocks:
            info = card_info(b)
            print("  %-46s ch=%-4d %s" % (s[:46], info["chapters"], info["title"][:30]))
            moved.append(b)
        if keep:
            whole = whole + "".join(keep)
    # 移走的卡追加进归档 pending-grid
    pending = pending + "".join(moved)
    print("小计:", len(moved))

    # ── 判定归档→书架 ──────────────────────────────────────
    arc_all = (list(re.finditer(r"<article\b[^>]*data-slug=\"[^\"]*\"[^>]*>.*?</article>", pending, re.S))
               + list(re.finditer(r"<article\b[^>]*data-slug=\"[^\"]*\"[^>]*>.*?</article>", archive, re.S)))
    if args.archive_to_shelf is not None:
        back_slugs = set(args.archive_to_shelf)
    else:
        back_slugs = {card_info(m.group(0))["slug"] for m in arc_all
                      if card_info(m.group(0))["has_ch"]}

    print("\n=== 归档 → 书架 ===")
    backed = []
    for s in back_slugs:
        pending, cp = cut_cards(pending, s)
        archive, ca = cut_cards(archive, s)
        for c in cp + ca:
            info = card_info(c)
            if info["has_ch"] or s in (args.archive_to_shelf or []):
                print("  %-46s ch=%-4d %s" % (s[:46], info["chapters"], info["title"][:30]))
                whole = whole + c
                backed.append(c)
    print("小计:", len(backed))

    # ── 拼回（按起始坐标从大到小，避免位置漂移）───────────
    # 坐标: ws(书架) < ags(archive-grid) < ps(pending-grid)
    order = sorted([(ws, we, whole), (ags, age, archive), (ps, pe, pending)],
                   key=lambda x: -x[0])
    for s0, e0, content in order:
        h = h[:s0] + content + h[e0:]

    after = {
        "article": len(re.findall(r"<article\b", h)),
        "h3": len(re.findall(r"<h3\b", h)),
        "div": len(re.findall(r"<div\b", h)) - h.count("</div>"),
    }
    print("\n=== 断言 ===")
    print("before:", before)
    print("after: ", after)
    assert before["article"] == after["article"], "article 数量变了"
    assert before["h3"] == after["h3"], "h3 数量变了"
    assert before["div"] == after["div"] == 0, "div 不平衡"
    assert h.count('id="panel-whole"') == 1
    assert h.count('id="archive-grid"') == 1
    assert h.count('id="pending-grid"') == 1
    print("断言通过")

    if args.dry_run:
        print("\n(dry-run，未写文件)")
        return
    open(HTML, "w", encoding="utf-8").write(h)
    print("\n已写入", HTML)


if __name__ == "__main__":
    main()
