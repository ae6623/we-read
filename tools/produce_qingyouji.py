#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""produce_qingyouji.py — 单本「猴面包的树」轻游记一键生产（复用既有 pipeline）。

给定 slug/bookId/title，产出与现有 23 本同形态的完整 AI 阅读笔记站点页：
  reading-notes/books/<slug>/outline.html        官方 AI 大纲（fetch_outline_api.render）
  reading-notes/books/<slug>/outline.json        大纲结构化存档
  reading-notes/books/<slug>/combined-data.html  10 模块领读（fill_combined_modules.assemble）
  reading-notes/books/<slug>/combined.html       reader 页（gen_reader_page）
  _data/books/<slug>.json                        书架/系列登记
  assets/data/hero.json                          ids 登记（slug→bookId）

前置：
  /tmp/outline_cache/<bookId>.json   （probe_and_cache.py 拉的官方 AI 大纲缓存，含 chapters）
可选：
  drafts/<slug>-llm.json            （子 Agent 精写的 LLM 6 模块；缺省用 gen_auto_llm 兜底）
  data/mm-graph/<slug>.json         （有则 svg 出真导图；无则按项目规范留占位）

用法：
  python3 tools/produce_qingyouji.py --slug X --book-id Y --title "书名" [--llm drafts/X-llm.json]
  python3 tools/produce_qingyouji.py --manifest /tmp/qingyouji_manifest.json --batch 01   # 批量跑一批
"""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import fetch_outline_api as fo          # noqa: E402
import fill_combined_modules as F        # noqa: E402

BOOKS = ROOT / "reading-notes" / "books"
DATA_BOOKS = ROOT / "_data" / "books"
HERO = ROOT / "assets" / "data" / "hero.json"
CACHE = Path("/tmp/outline_cache")
CST = timezone(timedelta(hours=8))


def today() -> str:
    return datetime.now(CST).strftime("%Y-%m-%d")


def load_chapters(book_id: str) -> list:
    cf = CACHE / f"{book_id}.json"
    if not cf.exists():
        return []
    d = json.loads(cf.read_text(encoding="utf-8"))
    return d.get("chapters", [])


def write_outline(slug: str, title: str, book_id: str, chapters: list) -> int:
    d = BOOKS / slug
    d.mkdir(parents=True, exist_ok=True)
    prefix, suffix = fo.tpl_parts()
    (d / "outline.html").write_text(
        fo.render(title, "猴面包的树", chapters, prefix, suffix),
        encoding="utf-8", newline="\n")
    (d / "outline.json").write_text(json.dumps(
        {"slug": slug, "book": title, "bookId": book_id,
         "generated_at": datetime.now(CST).isoformat(timespec="seconds"),
         "chapters": chapters}, ensure_ascii=False, indent=1),
        encoding="utf-8", newline="\n")
    return len(chapters)


def write_book_meta(slug: str, title: str, book_id: str) -> None:
    DATA_BOOKS.mkdir(parents=True, exist_ok=True)
    eyebrow_ov = "轻游记 · AI阅读笔记。"
    eyebrow_fi = "轻游记 · AI阅读完读汇编。"
    meta_line = "猴面包的树 · 阅读员-轻游记读书员 · AI问答 · %s。" % today()
    header = ('<p class="eyebrow">%s</p><h1>%s</h1><p class="meta">%s</p>\n'
              '<div class="card"><span class="tag">AI问答</span>'
              '<span class="tag">AI阅读完读 · 不等于亲读</span>'
              '<p class="notice">本书依据官方 AI 大纲与公开信息自主整理，未逐页亲读正文；'
              'AI 阅读完成与亲读事实分开，相关细节与数字不补造确定答案。</p></div>')
    def page(fname, eyebrow):
        return {"file": fname, "eyebrow": eyebrow, "title": title,
                "meta_line": meta_line,
                "header_html": header % (eyebrow, title, meta_line),
                "sections": []}
    obj = {"schema_version": 2, "slug": slug,
           "book": {"title": title, "author": "猴面包的树",
                    "meta_line": meta_line, "series": "qingyouji"},
           "ai_outline": None,
           "texts": {"overview": page("overview.html", eyebrow_ov),
                     "final": page("final.html", eyebrow_fi)}}
    (DATA_BOOKS / f"{slug}.json").write_text(
        json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


def register_hero(slug: str, book_id: str) -> None:
    d = json.loads(HERO.read_text(encoding="utf-8"))
    ids = d.setdefault("ids", {})
    if ids.get(slug) != book_id:
        ids[slug] = book_id
        HERO.write_text(json.dumps(d, ensure_ascii=False, indent=1),
                        encoding="utf-8", newline="\n")


def load_llm(slug: str, llm_path: str | None):
    p = Path(llm_path) if llm_path else (ROOT / "drafts" / f"{slug}-llm.json")
    if p.is_absolute() and p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    q = ROOT / p
    if q.exists():
        return json.loads(q.read_text(encoding="utf-8"))
    return None


def produce(slug: str, book_id: str, title: str, llm_path: str | None = None,
            no_hero: bool = False) -> dict:
    chapters = load_chapters(book_id)
    if not chapters:
        return {"slug": slug, "ok": False, "why": "无可用官方AI大纲缓存"}
    n_ch = write_outline(slug, title, book_id, chapters)
    write_book_meta(slug, title, book_id)
    if not no_hero:
        register_hero(slug, book_id)
    # 组装 10 模块：struct 4 + LLM 6（精写草稿优先，缺省兜底合成）
    ld = load_llm(slug, llm_path)
    polished = ld is not None
    if ld is None:
        chs = F.chapters_of(slug)
        ld = F.gen_auto_llm(slug, chs, {"title": title})
    rc = F.assemble(slug, struct=True, llm_data=ld, auto_llm=False)
    F.gen_reader_page(slug)
    F.inject_outline_link(slug)
    # 精写本不该带「Agent 兜底生成」字样：换成与现有 24 本一致的中性标注（仍诚实说明未亲读）
    if polished:
        cp = BOOKS / slug / "combined-data.html"
        ct = cp.read_text(encoding="utf-8", errors="ignore")
        ct = ct.replace(F.FALLBACK_TAG, "（基于本书 AI 大纲自主整理 · 未亲读原书）")
        cp.write_text(ct, encoding="utf-8", newline="\n")
    # 校验
    cd = (BOOKS / slug / "combined-data.html").read_text(encoding="utf-8", errors="ignore")
    import re
    keys = re.findall(r'data-key="([a-z_]+)"', cd)
    reader_exists = (BOOKS / slug / "combined.html").exists()
    ok = rc == 0 and len(set(keys)) >= 9 and reader_exists
    return {"slug": slug, "ok": ok, "chapters": n_ch,
            "data_keys": sorted(set(keys)), "n_keys": len(set(keys)),
            "reader": reader_exists,
            "llm": "精写" if load_llm(slug, llm_path) else "兜底"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug")
    ap.add_argument("--book-id")
    ap.add_argument("--title")
    ap.add_argument("--llm")
    ap.add_argument("--manifest")
    ap.add_argument("--batch", help="只跑 manifest 里该批次号")
    ap.add_argument("--no-hero", action="store_true", help="跳过 hero 登记（并行派工时用，避免写冲突）")
    ap.add_argument("--register-hero-only", action="store_true", help="仅按 manifest 一次性登记全部 hero")
    a = ap.parse_args()

    if a.manifest:
        m = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
        rows = m["books"] if isinstance(m, dict) else m
        if a.register_hero_only:
            for r in rows:
                register_hero(r["slug"], str(r["bookId"]))
            print(f"已登记 hero.json：{len(rows)} 本")
            return 0
        if a.batch:
            rows = [r for r in rows if str(r.get("batch")) == a.batch]
        ok = 0
        for r in rows:
            res = produce(r["slug"], str(r["bookId"]), r["title"], no_hero=True)
            ok += 1 if res["ok"] else 0
            print(("[OK] " if res["ok"] else "[FAIL] ") + json.dumps(res, ensure_ascii=False), flush=True)
        print(f"\n批次 {a.batch or 'ALL'}：成功 {ok}/{len(rows)}")
        return 0

    assert a.slug and a.book_id and a.title, "需 --slug --book-id --title"
    res = produce(a.slug, a.book_id, a.title, a.llm, no_hero=a.no_hero)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
