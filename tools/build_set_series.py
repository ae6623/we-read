#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""套装 → 单册 → AI 大纲 → 系列页（一条命令跑完整流程）。

背景（2026-11-03）：微信读书对「套装合集」本身不提供 AI 大纲，但合集目录的
一级标题就是各分册书名。按分册名逐本搜索 bookId 后，单册都能拿到官方大纲
（章 / 小节 / 要点 / 原句）。

流程：
  series-sets.json（套装登记：合集 slug + 系列信息）
    → /book/chapterinfo 取合集 level1 → 分册名（过滤封面/版权等噪声）
    → /store/search 逐个匹配 bookId（归一化书名，score>=60 才认）
    → /web/book/outline 抓四层大纲
    → reading-notes/books/<slug>/outline.html + data/outline/<slug>.json + book_outline
    → reading-notes/series/<series>/index.html（分册清单页）
    → 回写 series-sets.json 的 total / with_outline

用法：
  python tools/build_set_series.py --list
  python tools/build_set_series.py --set byzantium-trilogy
  python tools/build_set_series.py --all
  python tools/build_set_series.py --set currency-wars --dry
"""
from __future__ import annotations

import argparse
import html as H
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOKS = ROOT / "reading-notes" / "books"
SERIES = ROOT / "reading-notes" / "series"
SETS_JSON = ROOT / "assets" / "data" / "series-sets.json"
HERO = ROOT / "assets" / "data" / "hero.json"

spec = importlib.util.spec_from_file_location("fo", str(Path(__file__).resolve().parent / "fetch_outline_api.py"))
fo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fo)

NOISE = re.compile(r"^(封面|版权信息|总目录|前折页|文前辅文|书名页|文前彩插|本书获誉|目录|关于作者|"
                   r"序言|前言|后记|译后记|附录|出版说明|献词|题记|扉页|彩插|插图|地图|大事记|"
                   r"注释|参考文献|索引|致谢|导读|中文版序|自序|推荐序)")

PAGE_TPL = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{desc}">
<title>{name}（套装 {total} 种）｜系列</title>
<link rel="stylesheet" href="../../../assets/css/site.css">
<link rel="stylesheet" href="../series.css">
<link rel="stylesheet" href="../../../assets/css/share.css">
</head>
<body>
<main class="series-page" id="main">
<nav class="series-nav" aria-label="阅读导航"><a href="../../../index.html">首页</a><a href="../../index.html">阅读归档</a><a href="../index.html">系列</a></nav>
<header class="series-head">
  <p class="eyebrow">套装 · 按册拆解</p>
  <h1>{name}</h1>
  <p>{sub}</p>
  <p>{desc}</p>
  <p><span class="type-tag">{total} 种</span><span class="type-tag">来源合集《{src_title}》</span></p>
</header>
<section class="series-boundary">
  <p><strong>为什么拆成单册：</strong>套装在阅读器里是一整本，目录按册分组。这里按册拆开，逐册整理章节结构（章 / 小节 / 要点 / 原句），方便单册翻阅。</p>
  <p>单册页只放章节大纲，不复制读书笔记。点书名在阅读器里打开该册。</p>{note}
</section>
<section class="topic-group" aria-labelledby="units-title">
<h2 id="units-title">分册清单</h2>
{entries}
</section>
<footer>共 {total} 种。<a href="../index.html">返回系列总览</a></footer>
</main>
<script src="../../../assets/js/vendor/qrcode.min.js" defer></script>
<script src="../../../assets/js/share.js" defer></script>
<script src="../../../assets/js/weread-link.js" defer></script>
</body>
</html>
"""

ENTRY_OK = """<article class="book-entry" id="{i}">
<h3><a href="{deep}" data-weread-id="{bid}">{title}</a></h3>
<p>{author}{stat}</p>
<p class="entry-links"><a href="../../books/{slug}/outline.html">章节大纲 →</a></p>
</article>"""

ENTRY_NO = """<article class="book-entry" id="{i}">
<h3><a href="{deep}" data-weread-id="{bid}">{title}</a></h3>
<p>{author}</p>
</article>"""


def deep_of(book_id: str) -> str:
    """书籍详情里的官方深链：移动端唤起 App，PC 端打开网页版。"""
    try:
        d = fo.gw("/book/info", bookId=book_id)
        return d.get("deepLink") or ""
    except Exception:
        return ""


def slugify(t: str) -> str:
    try:
        from pypinyin import lazy_pinyin
        s = "-".join(lazy_pinyin((t or "").strip()))
        s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
        if s:
            return s[:64]
    except Exception:
        pass
    import zlib
    return ("book-" + "%08x" % (zlib.crc32((t or "").encode()) & 0xffffffff))[:64]


def norm(t: str) -> str:
    t = (t or "").strip().lower()
    t = re.sub(r"[（(【\[].*?[）)】\]]", "", t)
    return re.sub(r"[\s·・:：\-—_/\\'\"，。！？、]+", "", t)


def search_one(title: str) -> dict | None:
    head = re.split(r"[：:—]", title)[0]
    kw = head if len(head) >= 2 else title
    try:
        d = fo.gw("/store/search", keyword=kw, scope=0, count=8)
    except Exception:
        return None
    books = []
    for g in d.get("results") or []:
        if isinstance(g, dict):
            for b in g.get("books") or []:
                bi = b.get("bookInfo") or {}
                if bi.get("bookId"):
                    books.append(bi)
    best, score = None, 0
    for bi in books:
        nt, nti, nh = norm(bi.get("title")), norm(title), norm(head)
        s = 100 if nt == nti else 90 if nt == nh else 70 if nh and nh in nt else 65 if nt and nt in nti else 0
        if s > score:
            best, score = bi, s
    return best if score >= 60 else None


def units_of(book_id: str) -> list[str]:
    ch = fo.chapters(book_id)
    tops = [c["title"].strip() for c in ch if c.get("level") == 1 and c.get("title")]
    return [t for t in tops if not NOISE.match(t)]


def build_one(title: str, bid: str, dry: bool) -> dict:
    sl = slugify(title)
    page = BOOKS / sl / "outline.html"
    if page.exists() and '<details class="ch"' in page.read_text(encoding="utf-8", errors="ignore"):
        chs = (json.loads((fo.OUT_JSON / (sl + ".json")).read_text(encoding="utf-8")).get("chapters") or []) \
            if (fo.OUT_JSON / (sl + ".json")).exists() else []
        return {"slug": sl, "title": title, "bookId": bid, "has_outline": True, "reused": True,
                "chapters": len(chs), "points": sum(len(p["quotes"]) + 1 for c in chs for s in c["secs"] for p in s["points"])}
    if dry:
        return {"slug": sl, "title": title, "bookId": bid, "dry": True}
    try:
        chs = fo.to_chapters(fo.fetch_outline(bid, [c["chapterUid"] for c in fo.chapters(bid)]))
    except Exception as e:
        return {"slug": sl, "title": title, "bookId": bid, "why": "抓取失败:%s" % str(e)[:50]}
    if not chs:
        return {"slug": sl, "title": title, "bookId": bid, "why": "无 AI 大纲"}
    prefix, suffix = fo.tpl_parts()
    html = fo.render(title, "", chs, prefix, suffix)
    html = re.sub(r'\s*<a href="outline\.epub" download>下载 EPUB ↓</a>', "", html)
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(html, encoding="utf-8", newline="\n")
    fo.OUT_JSON.mkdir(parents=True, exist_ok=True)
    (fo.OUT_JSON / (sl + ".json")).write_text(json.dumps(
        {"slug": sl, "book": title, "bookId": bid, "chapters": chs},
        ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    fo.db_save(fo.db_init(), sl, title, chs)
    return {"slug": sl, "title": title, "bookId": bid, "has_outline": True,
            "chapters": len(chs), "points": sum(len(p["quotes"]) + 1 for c in chs for s in c["secs"] for p in s["points"])}


def render_page(st: dict, units: list[dict]) -> str:
    entries, wo = [], 0
    for i, u in enumerate(units, 1):
        bid = u.get("bookId", "")
        deep = deep_of(bid) if bid else ""
        if not deep:
            deep = "../../books/%s/outline.html" % u["slug"]
        if u.get("has_outline"):
            wo += 1
            entries.append(ENTRY_OK.format(i="unit-%d" % i, slug=u["slug"], title=H.escape(u["title"]),
                                           author="", bid=H.escape(bid), deep=H.escape(deep),
                                           stat="%d 章 / %d 条" % (u.get("chapters", 0), u.get("points", 0))))
        else:
            entries.append(ENTRY_NO.format(i="unit-%d" % i, title=H.escape(u["title"]),
                                           author="", bid=H.escape(bid), deep=H.escape(deep)))
    note = "  <p>《伟大的海》为全二册，此处按书名计 1 个条目。</p>" if st["slug"] == "oracle-world-history-set" else ""
    return PAGE_TPL.format(name=H.escape(st["name"]), sub=H.escape(st.get("sub", "")),
                           desc=H.escape(st.get("desc", "")), total=len(units), with_outline=wo,
                           src_title=H.escape(st.get("src_title", "")), note=note,
                           entries="\n".join(entries))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    data = json.loads(SETS_JSON.read_text(encoding="utf-8"))
    sets = data.get("sets") or []
    if a.list or (not a.set and not a.all):
        for s in sets:
            print("%-30s %-24s %d 种 / %d 有大纲" % (s["slug"], s["name"], s.get("total", 0), s.get("with_outline", 0)))
        return 0

    ids = json.loads(HERO.read_text(encoding="utf-8")).get("ids") or {}
    todo = [s for s in sets if a.all or s["slug"] == a.set]
    if not todo:
        print("没有匹配的系列，用 --list 看可选项")
        return 1

    for st in todo:
        src = st.get("src_slug")
        bid = ids.get(src, "")
        if not bid:
            print("! %s 缺合集 bookId（%s）" % (st["name"], src))
            continue
        names = units_of(bid)
        print("\n== %s：合集目录 %d 个分册" % (st["name"], len(names)))
        units = []
        for t in names:
            hit = search_one(t)
            if not hit:
                print("   ✗ %s（搜不到）" % t[:36])
                units.append({"title": t, "slug": "", "has_outline": False})
                continue
            u = build_one(t, str(hit["bookId"]), a.dry)
            units.append(u)
            print("   %s %s → %s 章" % ("✓" if u.get("has_outline") else "✗", t[:30], u.get("chapters", "-")))
        ok = sum(1 for u in units if u.get("has_outline"))
        st["total"], st["with_outline"] = len(units), ok
        if not a.dry:
            out = SERIES / st["slug"]
            out.mkdir(parents=True, exist_ok=True)
            (out / "index.html").write_text(render_page(st, units), encoding="utf-8", newline="\n")
            st["units"] = [{k: u.get(k) for k in ("title", "slug", "bookId", "has_outline", "chapters", "points")}
                           for u in units]
        print("   → %d/%d 有页" % (ok, len(units)))

    if not a.dry:
        SETS_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
