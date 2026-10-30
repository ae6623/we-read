"""微信读书 AI 数据的统一存储（SQLite）。

此前 AI 问书（ai_qa）与读完自测补答（quiz）散落在 data/ai_qa/*.json（gitignore，仅本地）。
本模块把它们收口到单个 SQLite 文件 data/we_read.db，作为「入库」的落地：

- 本地（有微信读书登录态）跑完问书后，把结果推到云端 API；
- 云端 API 写入本库（we_read.db）；
- 通读页渲染时从本库读取，无数据则回退到旧 JSON 文件（向后兼容）。

库是云端运行目录里的单个文件；本地机器通过 /api/ingest/* 写入，不直接碰库文件。
"""
from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
# 2026-10-31：库原来放 data/we_read.db，而部署会把本机 data/ 整目录传上去
# （本机那份是空库），每次部署就把沙箱里攒的数据冲光——实测回填 76 本精读后
# 一次部署归零。weread-data/ 是运行时目录（compose.json 在里面能跨部署留存），
# 所以库也搬过去；首次启动时若新库不存在而旧库有数据，自动迁移一次。
DB_PATH = BASE_DIR / "weread-data" / "we_read.db"
_LEGACY_DB = BASE_DIR / "data" / "we_read.db"
CST = timezone(timedelta(hours=8))

_conn = None


def _slug(title: str) -> str:
    s = "".join(c if (c.isalnum() or "\u4e00" <= c <= "\u9fa5") else "-" for c in (title or "").strip())
    return s.strip("-")[:60] or "book"


def _migrate_legacy() -> None:
    """旧库 data/we_read.db → 新库 weread-data/we_read.db（只在新库缺失时搬一次）。"""
    try:
        if DB_PATH.exists() or not _LEGACY_DB.exists():
            return
        if _LEGACY_DB.stat().st_size <= 40960:      # 空库/骨架，没必要搬
            return
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        DB_PATH.write_bytes(_LEGACY_DB.read_bytes())
    except Exception:
        pass


def get_db():
    global _conn
    if _conn is None:
        _migrate_legacy()
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _init()
    return _conn


def _init():
    db = _conn
    db.execute(
        """CREATE TABLE IF NOT EXISTS ai_qa (
               book      TEXT NOT NULL,
               date      TEXT NOT NULL,
               q         TEXT NOT NULL,
               a         TEXT,
               backfill  INTEGER NOT NULL DEFAULT 0,
               asked_at  TEXT,
               at        TEXT,
               updated_at TEXT NOT NULL,
               PRIMARY KEY (book, date, q)
           )"""
    )
    db.execute(
        """CREATE TABLE IF NOT EXISTS quiz (
               book      TEXT NOT NULL,
               q         TEXT NOT NULL,
               a         TEXT,
               at        TEXT,
               updated_at TEXT NOT NULL,
               PRIMARY KEY (book, q)
           )"""
    )
    db.execute(
        """CREATE TABLE IF NOT EXISTS book_outline (
               slug      TEXT NOT NULL,
               book      TEXT NOT NULL,
               ch_no     INTEGER NOT NULL,
               chapter   TEXT NOT NULL,
               sec_no    INTEGER NOT NULL DEFAULT 0,
               sec       TEXT,
               point_no  INTEGER NOT NULL DEFAULT 0,
               point     TEXT,
               quote_no  INTEGER NOT NULL DEFAULT 0,
               quote     TEXT,
               updated_at TEXT NOT NULL,
               PRIMARY KEY (slug, ch_no, sec_no, point_no, quote_no)
           )"""
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_outline_book ON book_outline(book)"
    )
    # 精读结构入库（2026-10-31）：以前只落 data/mindmap/<slug>.json 与页面，
    # 换环境/重建沙箱就查不到「这本书精读做到哪一步、用的什么通道」。
    db.execute(
        """CREATE TABLE IF NOT EXISTS book_mindmap (
               slug      TEXT PRIMARY KEY,
               book      TEXT,
               mode      TEXT,
               chapters  INTEGER DEFAULT 0,
               spine     INTEGER DEFAULT 0,
               density   REAL DEFAULT 0,
               missing   INTEGER DEFAULT 0,
               payload   TEXT,
               built_at  TEXT
           )"""
    )
    db.commit()


# ---------------------------------------------------------------- ai_qa
def save_aiqa(book_title: str, items: list, date: str | None = None,
              backfill: bool = False) -> int:
    """写入一批 AI 问书问答（按 book+date+q 幂等 upsert）。返回写入条数。"""
    db = get_db()
    now = datetime.now(CST).isoformat(timespec="seconds")
    if date is None:
        date = datetime.now(CST).date().isoformat()
    n = 0
    for it in items or []:
        q = (it.get("q") or "").strip()
        a = it.get("a")
        if not q or not a:
            continue
        d_i = it.get("date") or date
        db.execute(
            """INSERT INTO ai_qa (book, date, q, a, backfill, asked_at, at, updated_at)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(book, date, q) DO UPDATE SET
                 a=excluded.a, backfill=excluded.backfill,
                 asked_at=excluded.asked_at, at=excluded.at,
                 updated_at=excluded.updated_at""",
            (book_title, d_i, q, a,
             1 if (backfill or it.get("backfill")) else 0,
             it.get("asked_at"), it.get("at") or now, now),
        )
        n += 1
    db.commit()
    return n


def load_aiqa(book_title: str, limit: int = 6) -> list:
    """返回该书已答的 AI 问书条目（同一问保留最新一条，按时间升序最多 limit 条）。
    库为空时回退到旧 JSON（weread_ai.load_store）。"""
    db = get_db()
    rows = db.execute(
        """SELECT q, a, backfill, asked_at, at FROM ai_qa WHERE book=? AND a IS NOT NULL
           ORDER BY at ASC""",
        (book_title,),
    ).fetchall()
    if not rows:
        return _fallback_aiqa(book_title, limit)
    latest = {}
    for r in rows:
        latest[r["q"]] = dict(r)
    out = list(latest.values())[-limit:]
    return [
        {"q": r["q"], "a": r["a"], "backfill": bool(r["backfill"]),
         "asked_at": r["asked_at"], "at": r["at"]}
        for r in out
    ]


def _fallback_aiqa(book_title: str, limit: int) -> list:
    try:
        import weread_ai
        items = [i for i in weread_ai.load_store(book_title)["items"] if i.get("a")]
    except Exception:
        return []
    if not items:
        return []
    latest = {}
    for i in sorted(items, key=lambda x: (x.get("date") or "", x.get("at") or "")):
        latest[i.get("q")] = i
    return list(latest.values())[-limit:]


# ---------------------------------------------------------------- quiz
def save_quiz(book_title: str, items: list) -> int:
    """写入读完自测 3 问的补答（按 book+q 幂等 upsert，同一题只留最新）。"""
    db = get_db()
    now = datetime.now(CST).isoformat(timespec="seconds")
    n = 0
    for it in items or []:
        q = (it.get("q") or "").strip()
        a = it.get("a")
        if not q or not a:
            continue
        db.execute(
            """INSERT INTO quiz (book, q, a, at, updated_at)
               VALUES (?,?,?,?,?)
               ON CONFLICT(book, q) DO UPDATE SET
                 a=excluded.a, at=excluded.at, updated_at=excluded.updated_at""",
            (book_title, q, a, it.get("at") or now, now),
        )
        n += 1
    db.commit()
    return n


def load_quiz(book_title: str) -> list:
    """返回该书自测补答列表（库空时回退旧 JSON）。"""
    db = get_db()
    rows = db.execute(
        "SELECT q, a, at FROM quiz WHERE book=? AND a IS NOT NULL ORDER BY at ASC",
        (book_title,),
    ).fetchall()
    if not rows:
        try:
            import weread_ai
            return weread_ai.load_quiz_items(book_title)
        except Exception:
            return []
    return [{"q": r["q"], "a": r["a"], "at": r["at"]} for r in rows]


def save_book_outline(slug: str, book_title: str, chapters: list) -> int:
    """写入某本书的 AI 大纲全文通读（章节→小节→要点→原句摘录），按 slug 先清后写。

    chapters: [{"no":int, "title":str,
                "secs":[{"h":str, "points":[{"text":str, "quotes":[str]}]}]}]
    返回写入的要点条数。
    """
    db = get_db()
    now = datetime.now(CST).isoformat(timespec="seconds")
    db.execute("DELETE FROM book_outline WHERE slug=?", (slug,))
    n = 0
    for c in chapters or []:
        ch_no = int(c.get("no") or 0)
        chapter = (c.get("title") or "").strip()
        for si, s in enumerate(c.get("secs") or [], 1):
            sec = (s.get("h") or "").strip()
            for pi, p in enumerate(s.get("points") or [], 1):
                text = (p.get("text") if isinstance(p, dict) else p or "").strip()
                if not text:
                    continue
                quotes = [q.strip() for q in (p.get("quotes") or []) if q and q.strip()]
                if quotes:
                    for qi, q in enumerate(quotes, 1):
                        db.execute(
                            """INSERT INTO book_outline
                               (slug, book, ch_no, chapter, sec_no, sec,
                                point_no, point, quote_no, quote, updated_at)
                               VALUES (?,?,?,?,?,?,?,?,?,?,?)
                               ON CONFLICT(slug,ch_no,sec_no,point_no,quote_no)
                               DO UPDATE SET point=excluded.point, quote=excluded.quote,
                                             updated_at=excluded.updated_at""",
                            (slug, book_title, ch_no, chapter, si, sec,
                             pi, text, qi, q, now),
                        )
                else:
                    db.execute(
                        """INSERT INTO book_outline
                           (slug, book, ch_no, chapter, sec_no, sec,
                            point_no, point, quote_no, quote, updated_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?)
                           ON CONFLICT(slug,ch_no,sec_no,point_no,quote_no)
                           DO UPDATE SET point=excluded.point, quote=NULL,
                                         updated_at=excluded.updated_at""",
                        (slug, book_title, ch_no, chapter, si, sec,
                         pi, text, 0, None, now),
                    )
                n += 1
    db.commit()
    return n


def load_book_outline(slug: str) -> list:
    """读回某本书的大纲全文，重建为 chapters 结构（无数据返回 []）。"""
    db = get_db()
    rows = db.execute(
        """SELECT ch_no, chapter, sec_no, sec, point_no, point, quote_no, quote
           FROM book_outline WHERE slug=?
           ORDER BY ch_no, sec_no, point_no, quote_no""",
        (slug,),
    ).fetchall()
    chs, ch_i, sec_i, pt_i = [], {}, {}, {}
    for r in rows:
        key = r["ch_no"]
        if key not in ch_i:
            ch_i[key] = {"no": r["ch_no"], "title": r["chapter"], "secs": []}
            chs.append(ch_i[key])
            sec_i[key] = {}
            pt_i[key] = {}
        ch = ch_i[key]
        skey = r["sec_no"]
        if skey not in sec_i[key]:
            sec_i[key][skey] = {"h": r["sec"] or "", "points": []}
            ch["secs"].append(sec_i[key][skey])
        sec = sec_i[key][skey]
        pkey = (skey, r["point_no"])
        if pkey not in pt_i[key]:
            pt_i[key][pkey] = {"text": r["point"], "quotes": []}
            sec["points"].append(pt_i[key][pkey])
        if r["quote"]:
            pt_i[key][pkey]["quotes"].append(r["quote"])
    return chs


# ---------------------------------------------------------------- 精读结构
def save_mindmap(slug: str, book: str, d: dict, mode: str = "") -> bool:
    """把一份精读结构（refine/import/from-outline 的产物）写进 book_mindmap。

    同时保留整份 JSON 到 payload 列：页面渲染用文件，查询/统计用库，
    两边不打架。mode 记录来源通道（llm / import / from-outline）。
    """
    if not isinstance(d, dict) or not d.get("chapters"):
        return False
    db = get_db()
    ev = d.get("evidence") or {}
    db.execute(
        """INSERT INTO book_mindmap(slug, book, mode, chapters, spine, density,
                                    missing, payload, built_at)
           VALUES(?,?,?,?,?,?,?,?,?)
           ON CONFLICT(slug) DO UPDATE SET
             book=excluded.book, mode=excluded.mode, chapters=excluded.chapters,
             spine=excluded.spine, density=excluded.density, missing=excluded.missing,
             payload=excluded.payload, built_at=excluded.built_at""",
        (slug, book or d.get("title") or "", mode or d.get("mode") or "",
         len(d.get("chapters") or []), len(d.get("spine") or []),
         float(ev.get("density") or 0), len(d.get("bad_anchor") or []),
         json.dumps(d, ensure_ascii=False),
         d.get("built_at") or time.strftime("%Y-%m-%dT%H:%M:%S")))
    db.commit()
    return True


def load_mindmap(slug: str) -> dict | None:
    db = get_db()
    row = db.execute("SELECT payload FROM book_mindmap WHERE slug=?", (slug,)).fetchone()
    if not row:
        return None
    try:
        return json.loads(row["payload"])
    except Exception:
        return None


def list_mindmaps() -> list:
    """每本已入库精读的一行摘要（控制台/统计用）。"""
    db = get_db()
    rows = db.execute(
        """SELECT slug, book, mode, chapters, spine, density, missing, built_at
           FROM book_mindmap ORDER BY built_at DESC""").fetchall()
    return [dict(r) for r in rows]


def counts() -> list:
    """每本书的入库统计，供 /api/ingest/status 展示。"""
    db = get_db()
    rows = db.execute(
        """SELECT book,
                  COUNT(*) AS qa,
                  SUM(backfill) AS backfill,
                  (SELECT COUNT(*) FROM quiz q WHERE q.book = ai_qa.book) AS quiz
           FROM ai_qa GROUP BY book ORDER BY book""",
    ).fetchall()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    print("DB:", DB_PATH)
    for c in counts():
        print(c)
