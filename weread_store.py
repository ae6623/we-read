"""微信读书 AI 数据的统一存储（SQLite）。

此前 AI 问书（ai_qa）与读完自测补答（quiz）散落在 data/ai_qa/*.json（gitignore，仅本地）。
本模块把它们收口到单个 SQLite 文件 data/we_read.db，作为「入库」的落地：

- 本地（有微信读书登录态）跑完问书后，把结果推到云端 API；
- 云端 API 写入本库（we_read.db）；
- 通读页渲染时从本库读取，无数据则回退到旧 JSON 文件（向后兼容）。

库是云端运行目录里的单个文件；本地机器通过 /api/ingest/* 写入，不直接碰库文件。
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "we_read.db"
CST = timezone(timedelta(hours=8))

_conn = None


def _slug(title: str) -> str:
    s = "".join(c if (c.isalnum() or "\u4e00" <= c <= "\u9fa5") else "-" for c in (title or "").strip())
    return s.strip("-")[:60] or "book"


def get_db():
    global _conn
    if _conn is None:
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


# ---------------------------------------------------------------- 精读笔记（2026-10-28 补）
# 站内 15 本 / 22 篇精读笔记此前没有表承接：它们是「AI 大纲（机器产物）」与
# 「人读后的判断」之间唯一的桥，跨书对照最值钱的一层就在这里。
# 表是懒建的（不改进 _init），避免与并行改动冲突。
_NOTE_DDL = """CREATE TABLE IF NOT EXISTS note (
       slug       TEXT NOT NULL,   -- 站点 slug
       date       TEXT NOT NULL,   -- 笔记日期 YYYY-MM-DD
       title      TEXT,            -- 当篇标题
       html       TEXT,            -- 正文 HTML（整页）
       bytes      INTEGER NOT NULL DEFAULT 0,
       has_aiqa   INTEGER NOT NULL DEFAULT 0,  -- 含 AI 问书区块
       updated_at TEXT NOT NULL,
       PRIMARY KEY (slug, date)
   )"""


def save_note(slug: str, date: str, title: str | None, html: str,
              has_aiqa: bool = False) -> int:
    """写入一篇精读笔记（按 slug+date 幂等）。返回字节数。"""
    db = get_db()
    db.execute(_NOTE_DDL)
    now = datetime.now(CST).isoformat(timespec="seconds")
    b = len((html or "").encode("utf-8"))
    db.execute(
        """INSERT INTO note (slug, date, title, html, bytes, has_aiqa, updated_at)
           VALUES (?,?,?,?,?,?,?)
           ON CONFLICT(slug, date) DO UPDATE SET
             title=excluded.title, html=excluded.html, bytes=excluded.bytes,
             has_aiqa=excluded.has_aiqa, updated_at=excluded.updated_at""",
        (slug, date, title, html, b, 1 if has_aiqa else 0, now),
    )
    db.commit()
    return b


def load_notes(slug: str) -> list:
    """返回某书的全部精读笔记（按日期升序）。"""
    db = get_db()
    db.execute(_NOTE_DDL)
    rows = db.execute(
        "SELECT date, title, html, bytes, has_aiqa FROM note"
        " WHERE slug=? ORDER BY date ASC", (slug,)
    ).fetchall()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    print("DB:", DB_PATH)
    for c in counts():
        print(c)
