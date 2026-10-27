#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""从站点 HTML 回补 SQLite：自测问答（quiz）、AI 问书（ai_qa）、精读笔记（note）。

站内这些内容早就渲染在页面里，但库里没有——「网站有内容、库里没有」。
本脚本只做**解析 + 入库**，不改任何页面、不发布。

三类来源：
  quiz    reading-notes/books/<slug>/overview.html 的「读完自测 3 问」+ .quiz-ans
  ai_qa   reading-notes/books/<slug>/notes/<date>.html 的 <section class="aiqa">
  note    reading-notes/books/<slug>/notes/<date>.html 整页

用法：
  python backfill_store_from_site.py            # 只报告，不写库
  python backfill_store_from_site.py --write    # 写库
  python backfill_store_from_site.py --write --only quiz
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import gen_outline_full as G  # noqa: E402
import weread_store as S  # noqa: E402

BOOKS = HERE / "reading-notes" / "books"
STAMP = "backfill:2026-10-28"


def _soup(html_text: str):
    from bs4 import BeautifulSoup
    return BeautifulSoup(html_text, "html.parser")


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


# ------------------------------------------------------------------ quiz
def parse_quiz(html_text: str):
    """返回 (items, warn)：items=[{q,a}]，warn 为对不上的题目。"""
    soup = _soup(html_text)
    host = None
    for sec in soup.find_all(["section", "div"]):
        h2 = sec.find("h2", recursive=False)
        if h2 and "读完自测" in h2.get_text():
            host = sec
            break
    if host is None:
        return [], []
    qs = [_norm(li.get_text(" ", strip=True)) for li in host.select("ol li")]
    qs = [q for q in qs if q]
    # 答案：quiz-ans 里每个 aiqa-item 的 h3(截断问题) + p/正文
    pairs = []
    for it in host.select(".quiz-ans .aiqa-item"):
        h3 = it.find("h3")
        head = _norm(h3.get_text(" ", strip=True)) if h3 else ""
        body = it.find_all(["p", "ul", "ol"])
        ans = "\n".join(b.decode_contents().strip() for b in body).strip()
        if not ans:
            ans = it.get_text("\n", strip=True)
        pairs.append((head, ans))

    items, warns = [], []
    used = set()
    for q in qs:
        hit = None
        for i, (head, ans) in enumerate(pairs):
            if i in used or not head:
                continue
            # h3 被截断：双向前缀匹配，且要求足够长以免误配
            k = min(len(head), len(q), 40)
            if k >= 12 and head[:k] == q[:k]:
                hit = i
                break
        if hit is None:
            warns.append(q[:40])
            continue
        used.add(hit)
        items.append({"q": q, "a": pairs[hit][1], "at": STAMP})
    return items, warns


# ------------------------------------------------------------------ ai_qa
def parse_aiqa(html_text: str):
    """解析笔记页 <section class="aiqa"> 的问答。返回 [{q,a}]。"""
    soup = _soup(html_text)
    sec = soup.find("section", class_="aiqa")
    if sec is None:
        return []
    out = []
    for it in sec.select(".aiqa-item"):
        h3 = it.find("h3")
        q = h3.get_text(" ", strip=True) if h3 else ""
        if not q:
            continue
        parts = []
        for el in it.find_all(["p", "ul", "ol"]):
            parts.append(el.decode_contents().strip())
        a = "\n".join(p for p in parts if p).strip()
        if a:
            out.append({"q": q, "a": a})
    return out


# ------------------------------------------------------------------ 主流程
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--only", choices=["quiz", "aiqa", "note"], help="只做一类")
    a = ap.parse_args(argv)

    want = lambda k: a.only in (None, k)  # noqa: E731
    sq = sa = sn = 0
    q_books = qa_books = n_books = 0
    warns_all = []

    for d in sorted(BOOKS.iterdir()):
        if not d.is_dir():
            continue
        slug = d.name
        title = G._title_of(str(d), slug)

        if want("quiz"):
            ov = d / "overview.html"
            if ov.exists():
                items, warns = parse_quiz(ov.read_text(encoding="utf-8", errors="ignore"))
                if warns:
                    warns_all.append((slug, warns))
                if items:
                    q_books += 1
                    sq += len(items)
                    if a.write:
                        S.save_quiz(title, items)
                    print("  quiz %-44s %d 题%s" % (
                        slug[:44], len(items), ("  警告 %d" % len(warns)) if warns else ""))

        notes = sorted((d / "notes").glob("*.html")) if (d / "notes").is_dir() else []
        for np in notes:
            t = np.read_text(encoding="utf-8", errors="ignore")
            date = np.stem
            if want("aiqa"):
                qa = parse_aiqa(t)
                if qa:
                    qa_books += 1
                    sa += len(qa)
                    if a.write:
                        S.save_aiqa(title, qa, date=date, backfill=True)
                    print("  aiqa %-44s %s %d 问" % (slug[:44], date, len(qa)))
            if want("note"):
                sn += 1
                if a.write:
                    m = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", t)
                    h1 = re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else ""
                    S.save_note(slug, date, h1, t, has_aiqa=('class="aiqa"' in t))
        if notes:
            n_books += 1

    print("\n=== 汇总 ===")
    print("  quiz  %d 本 / %d 题" % (q_books, sq))
    print("  aiqa  %d 本 / %d 问" % (qa_books, sa))
    print("  note  %d 本 / %d 篇" % (n_books, sn))
    if warns_all:
        print("  ! 题目对不上答案：")
        for slug, w in warns_all:
            for x in w:
                print("    %-40s %s" % (slug[:40], x))
    if not a.write:
        print("  （未写库，加 --write 落盘）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
