#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量抓微信读书「AI 大纲」（HTTP 直连，无需浏览器登录态）。

2026-11-03 实测：`POST https://weread.qq.com/web/book/outline` 只带
`bookId + chapterUids` 就能返回 level 1-4（章 / 小节 / 要点 / 原句），
不需要 cookie，也不需要页面内 fetch（页面内是老办法，慢且要开浏览器）。

产物（与 gen_outline_full.py 的消费格式一致）：
  reading-notes/books/<slug>/outline.html   标准大纲页（覆盖降级壳）
  data/outline/<slug>.json                  结构化缓存（gitignore，可以不管）
  data/we_read.db book_outline 表           入库

用法：
  python tools/fetch_outline_api.py --limit 5 --dry     # 试跑
  python tools/fetch_outline_api.py                     # 全量，已完成自动跳过
  python tools/fetch_outline_api.py --only slug-a,slug-b
"""
from __future__ import annotations

import argparse
import html as H
import json
import os
import re
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOKS = ROOT / "reading-notes" / "books"
OUT_JSON = ROOT / "data" / "outline"
DB = ROOT / "data" / "we_read.db"
TPL = BOOKS / "wen-hua-ku-lv" / "outline.html"   # 只用它的 head/tail 骨架
CST = timezone(timedelta(hours=8))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
GATEWAY = "https://i.weread.qq.com/api/agent/gateway"
KEY_FILE = Path.home() / ".weread-auto-api-key"
KEY_LOCAL = ROOT / "weread-api-key.txt"
MIN_INTERVAL = 1.2
_last = 0.0


def load_key() -> str | None:
    k = os.environ.get("WEREAD_API_KEY")
    if k:
        return k.strip()
    for f in (KEY_FILE, KEY_LOCAL):
        if f.exists():
            try:
                return f.read_text(encoding="utf-8").strip() or None
            except Exception:
                continue
    return None


def gw(api_name: str, **params) -> dict:
    """官方 Agent 网关（取章节目录用）。499 是限流，指数退避。"""
    global _last
    key = load_key()
    if not key:
        raise RuntimeError("缺少 WEREAD_API_KEY")
    body = json.dumps({"api_name": api_name, "skill_version": "1.0.5", **params},
                      ensure_ascii=False).encode()
    for attempt in range(4):
        gap = time.monotonic() - _last
        if gap < MIN_INTERVAL:
            time.sleep(MIN_INTERVAL - gap)
        req = urllib.request.Request(GATEWAY, data=body, method="POST",
                                     headers={"Authorization": "Bearer " + key,
                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.loads(r.read().decode())
            _last = time.monotonic()
            if d.get("errcode") not in (0, None):
                raise RuntimeError(d.get("errmsg") or "gateway error")
            return d
        except urllib.error.HTTPError as e:
            _last = time.monotonic()
            if e.code != 499 or attempt == 3:
                raise
            time.sleep(6 * (2 ** attempt))
    return {}


def chapters(book_id: str) -> list[dict]:
    d = gw("/book/chapterinfo", bookId=book_id)
    return d.get("chapters") or (d.get("data") or {}).get("chapters") or []


def fetch_outline(book_id: str, uids: list[int]) -> list[dict]:
    body = json.dumps({"bookId": str(book_id), "chapterUids": uids}).encode()
    req = urllib.request.Request(
        "https://weread.qq.com/web/book/outline", data=body, method="POST",
        headers={"Content-Type": "application/json;charset=UTF-8",
                 "Accept": "application/json, text/plain, */*",
                 "User-Agent": UA, "Referer": "https://weread.qq.com/"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read().decode("utf-8"))
    flat: list[dict] = []
    for blk in d.get("itemsArray") or []:
        flat.extend(blk.get("items") or [])
    return flat


def to_chapters(items: list[dict]) -> list[dict]:
    """level: 1=章 2=小节 3=要点 4=原句"""
    chs: list[dict] = []
    ch = sec = pt = None
    for it in items:
        lv, tx = it.get("level"), (it.get("text") or "").strip()
        if not tx:
            continue
        if lv == 1:
            ch = {"no": len(chs) + 1, "title": tx, "secs": []}
            chs.append(ch)
            sec = pt = None
        elif lv == 2 and ch is not None:
            sec = {"h": tx, "points": []}
            ch["secs"].append(sec)
            pt = None
        elif lv == 3 and ch is not None:
            if sec is None:
                sec = {"h": "", "points": []}
                ch["secs"].append(sec)
            pt = {"text": tx, "quotes": []}
            sec["points"].append(pt)
        elif lv == 4 and pt is not None:
            pt["quotes"].append(tx)
    return [c for c in chs if any(s["points"] for s in c["secs"])]


def _norm(s: str) -> str:
    return re.sub(r"[\s·・:：\-—_/\\'\"（）()【】\[\]《》]+", "", (s or "")).lower()


def overlap(a: list[str], b: list[str]) -> float:
    sa = {_norm(x) for x in a if _norm(x)}
    sb = {_norm(x) for x in b if _norm(x)}
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / min(len(sa), len(sb))


def tpl_parts():
    s = TPL.read_text(encoding="utf-8")
    i = s.index('<div class="toc">')
    j = s.rindex("</details>") + len("</details>")
    return s[:i], s[j:]


def render(title: str, author: str, chapters: list[dict], prefix: str, suffix: str) -> str:
    n_ch = len(chapters)
    n_item = sum(len(p["quotes"]) + 1 for c in chapters for s in c["secs"] for p in s["points"])
    head = re.sub(r"<title>.*?</title>", "<title>《%s》｜AI 大纲</title>" % H.escape(title), prefix, count=1, flags=re.S)
    head = re.sub(r'(<meta name="description" content=")[^"]*(">)',
                  lambda m: m.group(1) + H.escape(title) + " AI 大纲" + m.group(2), head, count=1)
    head = re.sub(r"<h1>.*?</h1>", "<h1>《%s》AI 大纲</h1>" % H.escape(title), head, count=1, flags=re.S)
    head = re.sub(r'<p class="meta">.*?</p>',
                  '<p class="meta">作者：%s　·　共 %d 章 / %d 条　·　AI 读书 · 全书大纲</p>'
                  % (H.escape(author or "—"), n_ch, n_item), head, count=1, flags=re.S)
    toc, body = ['<div class="toc"><b>章节目录</b><ul>'], []
    for i, c in enumerate(chapters):
        toc.append('<li><a href="#ch%d">%s</a></li>' % (i, H.escape(c["title"])))
        body.append('<details class="ch" id="ch%d"><summary>%s</summary>' % (i, H.escape(c["title"])))
        for s in c["secs"]:
            body.append('<div class="sec">')
            if s["h"]:
                body.append("<h4>%s</h4>" % H.escape(s["h"]))
            body.append('<ul class="point">')
            for p in s["points"]:
                body.append("<li><b>%s</b>" % H.escape(p["text"]))
                if p["quotes"]:
                    body.append('<ul class="quote">' +
                                "".join("<li>%s</li>" % H.escape(q) for q in p["quotes"]) + "</ul>")
                body.append("</li>")
            body.append("</ul></div>")
        body.append("</details>")
    toc.append("</ul></div>")
    return head + "\n".join(toc) + "\n" + "\n".join(body) + suffix


def db_init():
    DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB)
    db.execute("""CREATE TABLE IF NOT EXISTS book_outline (
           slug TEXT NOT NULL, book TEXT NOT NULL, ch_no INTEGER NOT NULL,
           chapter TEXT NOT NULL, sec_no INTEGER NOT NULL DEFAULT 0, sec TEXT,
           point_no INTEGER NOT NULL DEFAULT 0, point TEXT,
           quote_no INTEGER NOT NULL DEFAULT 0, quote TEXT,
           updated_at TEXT NOT NULL,
           PRIMARY KEY (slug, ch_no, sec_no, point_no, quote_no))""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_outline_book ON book_outline(book)")
    db.commit()
    return db


def db_save(db, slug: str, title: str, chapters: list[dict]) -> int:
    now = datetime.now(CST).isoformat(timespec="seconds")
    db.execute("DELETE FROM book_outline WHERE slug=?", (slug,))
    n = 0
    for c in chapters:
        for si, s in enumerate(c["secs"]):
            for pi, p in enumerate(s["points"]):
                for qi, q in enumerate(p["quotes"] or [""]):
                    db.execute("INSERT INTO book_outline (slug,book,ch_no,chapter,sec_no,sec,"
                               "point_no,point,quote_no,quote,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                               (slug, title, c["no"], c["title"], si, s["h"], pi, p["text"], qi, q, now))
                    n += 1
    db.commit()
    return n


def title_of(slug: str) -> str:
    for f in ("outline.html", "overview.html"):
        p = BOOKS / slug / f
        if not p.exists():
            continue
        s = p.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"<h1>\s*《?([^》<]+)》?", s)
        if m:
            t = re.sub(r"\s*AI 大纲\s*$", "", m.group(1).strip())
            if t:
                return t
    return slug


def author_of(slug: str) -> str:
    for f in ("outline.html", "overview.html"):
        p = BOOKS / slug / f
        if not p.exists():
            continue
        m = re.search(r"作者：\s*([^　<·|]+)", p.read_text(encoding="utf-8", errors="ignore"))
        if m:
            return m.group(1).strip()
    return ""


def is_shell(slug: str) -> bool:
    p = BOOKS / slug / "outline.html"
    if not p.exists():
        return True
    s = p.read_text(encoding="utf-8", errors="ignore")
    return ('<details class="ch"' not in s) or ("章级目录" in s)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--only", default="")
    a = ap.parse_args()

    hero = json.loads((ROOT / "assets/data/hero.json").read_text(encoding="utf-8"))
    ids = hero.get("ids") or {}
    slugs = sorted(d.name for d in BOOKS.iterdir() if d.is_dir() and is_shell(d.name))
    if a.only:
        keep = {x.strip() for x in a.only.split(",") if x.strip()}
        slugs = [s for s in slugs if s in keep]
    if a.limit:
        slugs = slugs[:a.limit]
    print("待补 %d 本" % len(slugs))

    prefix, suffix = tpl_parts()
    db = None if a.dry else db_init()
    ok = fail = 0
    failed = []
    for i, slug in enumerate(slugs, 1):
        title, bid = title_of(slug), ids.get(slug, "")
        print("[%d/%d] %s  id=%s" % (i, len(slugs), title, bid or "-"), flush=True)
        if not bid:
            failed.append((title, "无 bookId"))
            fail += 1
            continue
        try:
            chs = to_chapters(fetch_outline(bid, [c["chapterUid"] for c in chapters(bid)]))
        except Exception as e:
            failed.append((title, "抓取失败:%s" % str(e)[:60]))
            fail += 1
            continue
        if not chs:
            failed.append((title, "接口无大纲"))
            fail += 1
            continue
        old = []
        p = BOOKS / slug / "outline.html"
        if p.exists():
            old = re.findall(r"<li><b>\d+</b>\s*([^<]+)</li>", p.read_text(encoding="utf-8", errors="ignore"))
        ov = overlap(old, [c["title"] for c in chs]) if old else 1.0
        if old and ov < 0.3:
            failed.append((title, "重合度过低 %.0f%%（疑似错配）" % (ov * 100)))
            fail += 1
            continue
        if a.dry:
            ok += 1
            continue
        p.write_text(render(title, author_of(slug), chs, prefix, suffix), encoding="utf-8", newline="\n")
        OUT_JSON.mkdir(parents=True, exist_ok=True)
        (OUT_JSON / (slug + ".json")).write_text(json.dumps(
            {"slug": slug, "book": title, "bookId": bid,
             "generated_at": datetime.now(CST).isoformat(timespec="seconds"),
             "chapters": chs}, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
        db_save(db, slug, title, chs)
        ok += 1
    print("\n完成 %d 本，失败 %d 本" % (ok, fail))
    for t, why in failed:
        print("  ", t, "—", why)
    return 0


if __name__ == "__main__":
    sys.exit(main())
