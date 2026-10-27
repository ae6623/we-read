#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""AI 大纲入库体检：把站点仓 82 本书的 outline.html 全量解析，核对 DB 覆盖情况。

只做「解析 + 对账 + 可选的入库补齐」，不动 overview.html、不发布。

用法：
  python audit_outline_db.py                 # 只体检，打印矩阵
  python audit_outline_db.py --write         # 解析并写入 data/we_read.db（book_outline）
  python audit_outline_db.py --write --json out.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import gen_outline_full as G  # noqa: E402
import weread_store as S  # noqa: E402

BOOKS = HERE / "reading-notes" / "books"


def has_sec_block(path: Path) -> bool:
    """通读页是否有「章节导读」区块（注入目标）。"""
    try:
        t = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    return ("章节导读" in t) or ('class="ch-item"' in t)


def db_stats() -> dict:
    if not S.DB_PATH.exists():
        return {}
    con = sqlite3.connect(str(S.DB_PATH))
    con.row_factory = sqlite3.Row
    out = {}
    try:
        for r in con.execute(
            "SELECT slug, book, COUNT(*) n, COUNT(DISTINCT ch_no) ch,"
            " COUNT(DISTINCT sec_no || '/' || ch_no) sec,"
            " SUM(CASE WHEN quote_no>0 THEN 1 ELSE 0 END) q"
            " FROM book_outline GROUP BY slug"
        ):
            out[r["slug"]] = dict(r)
        out["__total__"] = dict(
            con.execute("SELECT COUNT(*) n, COUNT(DISTINCT slug) books FROM book_outline").fetchone()
        )
    except sqlite3.OperationalError:
        pass
    con.close()
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="写入 book_outline")
    ap.add_argument("--json", help="把矩阵写到 JSON 文件")
    a = ap.parse_args(argv)

    prev = db_stats()
    rows = []
    for d in sorted(BOOKS.iterdir()):
        if not d.is_dir():
            continue
        slug = d.name
        ol, ov = d / "outline.html", d / "overview.html"
        rec = {
            "slug": slug,
            "title": G._title_of(str(d), slug),
            "outline": ol.exists(),
            "overview": ov.exists(),
            "sec_block": has_sec_block(ov) if ov.exists() else False,
            "chapters": 0,
            "points": 0,
            "quotes": 0,
            "db_rows": (prev.get(slug) or {}).get("n", 0),
            "db_ch": (prev.get(slug) or {}).get("ch", 0),
            "err": "",
        }
        if ol.exists():
            try:
                chs = G.parse_full_outline(str(ol))
            except Exception as e:
                chs, rec["err"] = [], str(e)[:120]
            rec["chapters"] = len(chs)
            rec["points"] = sum(len(s["points"]) for c in chs for s in c["secs"])
            rec["quotes"] = sum(len(p.get("quotes") or [])
                                for c in chs for s in c["secs"] for p in s["points"])
            if a.write and chs:
                rec["db_rows"] = S.save_book_outline(slug, rec["title"], chs)
                rec["db_ch"] = len(chs)
        rows.append(rec)

    # ---- 打印
    print("%-46s %-3s %-4s %-4s %5s %6s %6s %6s" %
          ("slug", "ol", "ov", "sec", "章", "要点", "原句", "DB行"))
    for r in rows:
        flag = ""
        if r["outline"] and r["chapters"] == 0:
            flag = "  ← 大纲解析为空"
        elif r["db_rows"] == 0 and r["chapters"] > 0:
            flag = "  ← 未入库"
        print("%-46s %-3s %-4s %-4s %5d %6d %6d %6d%s" % (
            r["slug"][:46], "Y" if r["outline"] else "-", "Y" if r["overview"] else "-",
            "Y" if r["sec_block"] else "-", r["chapters"], r["points"], r["quotes"],
            r["db_rows"], flag))

    tot = {
        "books": len(rows),
        "with_outline": sum(1 for r in rows if r["outline"]),
        "with_overview": sum(1 for r in rows if r["overview"]),
        "with_sec_block": sum(1 for r in rows if r["sec_block"]),
        "parsed_ok": sum(1 for r in rows if r["chapters"] > 0),
        "empty_parse": [r["slug"] for r in rows if r["outline"] and r["chapters"] == 0],
        "no_sec_block": [r["slug"] for r in rows if r["overview"] and not r["sec_block"]],
        "chapters": sum(r["chapters"] for r in rows),
        "points": sum(r["points"] for r in rows),
        "quotes": sum(r["quotes"] for r in rows),
        "db_rows": sum(r["db_rows"] for r in rows),
    }
    print("\n=== 汇总 ===")
    for k in ("books", "with_outline", "with_overview", "with_sec_block", "parsed_ok",
              "chapters", "points", "quotes", "db_rows"):
        print("  %-14s %s" % (k, tot[k]))
    print("  解析为空       %s" % (tot["empty_parse"] or "无"))
    print("  无章节导读区块 %s" % (tot["no_sec_block"] or "无"))
    if a.json:
        Path(a.json).write_text(json.dumps({"rows": rows, "summary": tot},
                                           ensure_ascii=False, indent=1), encoding="utf-8")
        print("  → %s" % a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
