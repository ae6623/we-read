#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""补抓「AI 大纲」并落库（给还没有精读的书用）。

背景：2026-10-26 之前跑的书只存了「全书视角」通读页，没有逐章大纲；
这些书的 outline.html 是通读笔记改写出来的桩页（0 个 details.ch），
所以 gen_mindmap.py 拿不到章节数据。本脚本复用阅读器的页面内接口
（weread_outline.fetch，必须页面内 fetch，ctx.request 会被 wpa 签名拦）
把 AI 大纲抓回来，落成 book_outline 行 + outline.json。

用法：
  python tools/fetch_missing_outlines.py --slug shi-shi --book-id 3300083256
  python tools/fetch_missing_outlines.py --auto --limit 3      # 按书名搜 bookId
  python tools/fetch_missing_outlines.py --slug X --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.append(str(HERE.parent / "weread-auto"))
sys.path.insert(0, str(HERE))

BOOKS = HERE / "reading-notes" / "books"
DB = HERE / "data" / "we_read.db"
PROFILE = Path.home() / ".weread-auto-profile"
READER = "https://weread.qq.com/web/reader/%s"


def title_of(slug: str) -> str:
    p = BOOKS / slug / "overview.html"
    if not p.exists():
        return slug
    t = p.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"<title>(.*?)</title>", t, re.S)
    s = (m.group(1) if m else slug).strip()
    return re.sub(r"｜.*$", "", s).strip("《》 ")


def items_to_chapters(items: list[dict]) -> list[dict]:
    """扁平大纲条目（level 1..4）→ parse_full_outline 同构结构。

    level 1/2 开新章或新小节；level 3 是要点；level 4 是原句，挂到上一个要点。
    """
    chapters: list[dict] = []
    cur_ch = None
    cur_sec = None
    cur_pt = None
    for it in items:
        lv = int(it.get("level") or 0)
        text = (it.get("text") or "").strip()
        if not text:
            continue
        if lv <= 2:
            # level1 有子标题时当章，level2 当小节；两者都出现的书按层级走
            if lv == 1:
                cur_ch = {"no": len(chapters) + 1, "title": text, "secs": []}
                chapters.append(cur_ch)
                cur_sec = None
            else:
                if cur_ch is None:
                    cur_ch = {"no": 1, "title": text, "secs": []}
                    chapters.append(cur_ch)
                    cur_sec = None
                    continue
                cur_sec = {"h": text, "points": []}
                cur_ch["secs"].append(cur_sec)
            cur_pt = None
            continue
        if cur_ch is None:                       # 没有章层级，兜底成第一章
            cur_ch = {"no": 1, "title": "全书", "secs": []}
            chapters.append(cur_ch)
        if lv == 3:
            if cur_sec is None:
                cur_sec = {"h": "", "points": []}
                cur_ch["secs"].append(cur_sec)
            cur_pt = {"text": text, "quotes": []}
            cur_sec["points"].append(cur_pt)
        else:                                    # level 4 = 原文摘录
            if cur_pt is None:
                if cur_sec is None:
                    cur_sec = {"h": "", "points": []}
                    cur_ch["secs"].append(cur_sec)
                cur_pt = {"text": "", "quotes": []}
                cur_sec["points"].append(cur_pt)
            cur_pt["quotes"].append(text)
    # 丢掉空章/空小节，重排章号
    out = []
    for ch in chapters:
        secs = [s for s in ch["secs"] if s["points"]]
        if secs:
            out.append({"no": len(out) + 1, "title": ch["title"], "secs": secs})
    return out


def search_book_id(title: str) -> str | None:
    import weread_api as w
    try:
        d = w.search(title, count=5)
    except Exception as e:
        print("  ! 搜索失败 %s: %s" % (title, str(e)[:80]))
        return None
    for group in (d.get("results") or []):
        for b in (group.get("books") or []):
            info = b.get("bookInfo") or {}
            if not info.get("bookId"):
                continue
            name = (info.get("title") or "").strip()
            if name and (name in title or title in name):
                return str(info["bookId"])
    return None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", action="append", default=[])
    ap.add_argument("--book-id", action="append", default=[],
                    help="slug=bookId，可多次")
    ap.add_argument("--auto", action="store_true", help="按书名搜索 bookId")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    ids = {}
    for pair in a.book_id:
        if "=" in pair:
            s, b = pair.split("=", 1)
            ids[s.strip()] = b.strip()
    slugs = a.slug or list(ids)
    if a.auto:
        have_mm = {p.parent.name for p in BOOKS.glob("*/mindmap.html")}
        cand = [d.name for d in sorted(BOOKS.iterdir())
                if d.is_dir() and (d / "overview.html").exists()
                and d.name not in have_mm]
        slugs = [s for s in cand if s not in ids]
    if a.limit:
        slugs = slugs[:a.limit]
    if not slugs:
        print("没有要处理的书")
        return 1

    import weread_outline
    import weread_store as S
    from playwright.sync_api import sync_playwright

    done = 0
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE), headless=True,
            args=["--no-proxy-server", "--disable-blink-features=AutomationControlled"],
            viewport={"width": 1280, "height": 900})
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        for slug in slugs:
            bid = ids.get(slug)
            if not bid and a.auto:
                t = title_of(slug)
                bid = search_book_id(t)
                print("[%s] 搜到 bookId=%s（%s）" % (slug, bid, t[:28]))
            if not bid:
                print("! %s 没有 bookId，跳过" % slug)
                continue
            page.goto(READER % bid, wait_until="domcontentloaded", timeout=60000)
            time.sleep(3.0)
            items = weread_outline.fetch(page, bid)
            print("[%s] 条目 %d" % (slug, len(items)))
            if not items:
                continue
            chs = items_to_chapters(items)
            print("[%s] 章 %d 小节 %d 要点 %d" % (
                slug, len(chs), sum(len(c["secs"]) for c in chs),
                sum(len(s["points"]) for c in chs for s in c["secs"])))
            if a.dry_run or not chs:
                continue
            d = BOOKS / slug
            (d / "outline.json").write_text(
                json.dumps(items, ensure_ascii=False), encoding="utf-8")
            n = S.save_book_outline(slug, title_of(slug), chs)
            print("[%s] 落库 %d 行" % (slug, n))
            done += 1
        ctx.close()
    print("完成 %d / %d" % (done, len(slugs)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
