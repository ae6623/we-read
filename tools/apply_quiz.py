#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""apply_quiz.py — 把 gen_quiz 产出的自测三问写进通读页（**只换 quiz 区块**）。

为什么不用 overview_gen 整页重渲染：
  2026-10-30 踩过——books.py 里没有配置的精修页（如 1984、白夜行），
  整页重渲染会用 derive_cfg 把人工写的主旨/三问冲成自动派生版。
  通读页是逐本精修的，重渲染 = 降级。所以这里只做外科手术：
  定位 <section class="card quiz-card">…</section>，整块替换，其余一字不动。

替换规则（保守）：
  · 现有三问是通用元信息废话（「本书 AI 大纲共列出多少章节条目？」）→ 一律替换
  · 现有三问已是具体内容（人工精修或已改过）→ 只有 src=ai（微信 Ai 问书）才覆盖，
    local 自构题不如人工精修，覆盖等于降级

用法：
    python tools/apply_quiz.py            # 预览
    python tools/apply_quiz.py --write    # 落盘
    python tools/apply_quiz.py --slug 1984
"""
from __future__ import annotations

import argparse
import html as _html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOKS = ROOT / "reading-notes" / "books"

# 区块定位：按「读完自测」标题找，再向前回溯到所属 <section>。
# 只认 class="card quiz-card" 会漏掉精修页——它们写作 <section class="card">
# （实测《西施泪》就是，且已有具体三问），那批恰好最不该被覆盖。
QUIZ_H2 = re.compile(r"<h2[^>]*>\s*读完自测[^<]*")

# 通用元信息题：出现即说明这批是占位废话
GENERIC_HINTS = ("共列出多少章节", "你能用自己的话讲清", "第一章最让你意外",
                 "AI 大纲共列出")

QUIZ_SRC_TITLE = {
    "ai": "AI 出题并作答（微信读书 Ai 问书，带书内引源）",
    "gemini": "AI 出题并作答（Gemini 依据本书大纲）",
    "local": "参考答案（依据本书 AI 大纲整理，未经 AI 问答）",
}


def esc(t):
    return _html.escape(t or "", quote=False)


def _section_span(s: str, start: int) -> tuple[int, int]:
    """从 start 起做 <section>/</section> 配平，返回 (start, end)。"""
    i, depth = start, 0
    pat = re.compile(r"<section\b|</section>")
    while i < len(s):
        mo = pat.search(s, i)
        if not mo:
            raise ValueError("section 未闭合")
        if mo.group(0) == "</section>":
            depth -= 1
            if depth == 0:
                return start, mo.end()
        else:
            depth += 1
        i = mo.end()
    raise ValueError("section 未闭合")


def quiz_block(items: list[dict]) -> str:
    src = (items[0].get("src") or "").lower()
    title = QUIZ_SRC_TITLE.get(src, "参考答案")
    lis = "".join("<li>%s</li>\n" % esc(i.get("q") or "") for i in items)
    out = ['<section class="card quiz-card"><h2 id="quiz-title">读完自测 3 问</h2>\n<ol>\n',
           lis, "</ol>\n", '<div class="quiz-ans"><h3>%s</h3>' % title]
    for i in items:
        out.append('<div class="aiqa-item"><h3>%s</h3><p>%s</p></div>'
                   % (esc(i.get("q") or ""),
                      esc(i.get("a") or "").replace("\n", "<br>")))
    out.append("</div></section>\n")
    return "".join(out)


def quiz_span(html: str):
    """定位「读完自测」所在 section，返回 (start, end)；找不到返回 None。"""
    m = QUIZ_H2.search(html)
    if not m:
        return None
    si = html.rfind("<section", 0, m.start())
    if si < 0:
        return None
    try:
        return _section_span(html, si)
    except ValueError:
        return None


def current_questions(html: str) -> list[str]:
    span = quiz_span(html)
    if not span:
        return []
    a, b = span
    return [re.sub(r"<[^>]+>", "", q).strip()
            for q in re.findall(r"<li>(.*?)</li>", html[a:b], re.S)]


def apply_page(path: Path, items: list[dict], write: bool = True) -> tuple[str, str]:
    """返回 ('replaced'|'skipped'|'no-quiz-section', 说明)。

    write=False 时必须**不碰磁盘**——第一版在预览分支也调了 write_text，
    等于跑一次预览就把站改了（2026-10-30）。
    """
    html = path.read_text(encoding="utf-8")
    span = quiz_span(html)
    if not span:
        return "no-quiz-section", "页面没有「读完自测」区块"
    a, b = span
    cur = current_questions(html)
    if cur and cur[0] == (items[0].get("q") or ""):
        return "skipped", "内容一致，跳过"
    is_generic = any(any(h in q for h in GENERIC_HINTS) for q in cur)
    src = (items[0].get("src") or "").lower()
    if cur and not is_generic and src != "ai":
        return "skipped", "现有三问已是具体内容，local 题不覆盖（防降级）"
    new = quiz_block(items)
    if write:
        path.write_text(html[:a] + new + html[b:], encoding="utf-8", newline="\n")
    tag = "通用题→替换" if is_generic else ("AI 题覆盖精修" if src == "ai" else "替换")
    return "replaced", f"{tag}（原 {len(cur)} 问）"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--slug")
    a = ap.parse_args()

    pool = ([BOOKS / a.slug] if a.slug
            else sorted(p for p in BOOKS.iterdir() if p.is_dir()))
    stat = {"replaced": 0, "skipped": 0, "no-quiz-section": 0}
    for d in pool:
        qj = d / "quiz.json"
        ov = d / "overview.html"
        if not qj.is_file() or not ov.is_file():
            continue
        try:
            items = json.loads(qj.read_text(encoding="utf-8")).get("items") or []
        except Exception:
            continue
        if not items:
            continue
        kind, msg = apply_page(ov, items, write=a.write)
        stat[kind] = stat.get(kind, 0) + 1
        mark = {"replaced": "REPLACE", "skipped": "SKIP  ",
                "no-quiz-section": "NOSEC "}.get(kind, kind)
        print("%s %-46s %s" % (mark, d.name[:46], msg))
        if not a.write and kind == "replaced":
            pass
    total = sum(stat.values())
    print("替换 %d，跳过 %d，无区块 %d，共 %d%s"
          % (stat.get("replaced", 0), stat.get("skipped", 0),
             stat.get("no-quiz-section", 0), total,
             "（预览，未落盘）" if not a.write else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
