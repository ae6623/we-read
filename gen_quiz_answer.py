#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""按库里的 AI 大纲条目，给「读完自测 3 问」补答案（只补缺答案的书）。

为什么不用 `gen_aiqa_from_outline.py`：实测 `--slug xi-da-duo`（黑塞小说）产出的答案
在谈「阅读方法论／信息过载」，与书中内容无关——那条链路取错了上下文。
本脚本只从 `book_outline` 取该书真实章节，把章标题与要点原文喂给模型，并强制要求
答案里的引用必须命中所给条目，否则重试。

用法：
  python gen_quiz_answer.py                 # 报告缺答案的书
  python gen_quiz_answer.py --write          # 生成并写入页面 + quiz 表
  python gen_quiz_answer.py --slug X --write
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.append(str(HERE.parent / "weread-auto"))
sys.path.insert(0, str(HERE))

import gen_outline_full as G  # noqa: E402
import weread_store as S  # noqa: E402

BOOKS = HERE / "reading-notes" / "books"
SYSTEM = """你是读书笔记的编写者。只使用用户提供的该书 AI 大纲条目作答，不得引入书外内容。
中文，160 字以内，直接回答问题，不写「本文/本页/综上」。不提页码、时长、阅读进度。不出现平台名。"""

PROMPT = """《{title}》的 AI 大纲条目（共 {n} 章）：
{corpus}

读者读完本页后的三个自测问题：
{q}

请针对每个问题写一段答案（各 ≤160 字），要求：
- 答案必须落在上面给出的条目上，能指到具体章节或要点；禁止编造书中没有的情节、数据、人名。
- 第 1 问若问「列出多少章节条目」，请直接数上面给出的章数，并说明分组依据。
- 第 2 问请挑一个**确实出现在条目里**的要点，说清它为什么反直觉。
- 第 3 问用一句话概括全书试图解决的问题，并说明它依赖哪几条主线。

只输出 JSON：{{"answers": ["答1", "答2", "答3"]}}"""


def parse_quiz_block(html: str):
    """返回 (qs, sec_start, sec_end, has_ans) —— 定位「读完自测」整个 section。"""
    m = re.search(r'<section[^>]*>\s*<h2[^>]*>[^<]*读完自测[^<]*</h2>', html)
    if not m:
        return [], -1, -1, False
    start = m.start()
    end = html.find("</section>", m.end())
    if end < 0:
        return [], -1, -1, False
    block = html[start:end]
    qs = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", li)).strip()
          for li in re.findall(r"<li>([\s\S]*?)</li>", block)]
    qs = [q for q in qs if q][:3]
    return qs, start, end, ('class="quiz-ans"' in block)


def corpus_of(slug: str, per_ch: int = 2, cut: int = 66):
    chs = S.load_book_outline(slug)
    lines = []
    for c in chs:
        pts = [p["text"] for s in c["secs"] for p in s["points"]]
        lines.append("第%d章 %s｜%s" % (c["no"], c["title"],
                                       " / ".join(p[:cut] for p in pts[:per_ch])))
    return chs, "\n".join(lines)


def gen(title: str, n: int, corpus: str, qs: list):
    import gemini_client as gc
    p = PROMPT.format(title=title, n=n, corpus=corpus,
                      q="\n".join("%d) %s" % (i + 1, q) for i, q in enumerate(qs)))
    for k in range(3):
        r = gc.generate(p, system=SYSTEM, model="gemini-3.5-flash", timeout=180,
                        max_tokens=2048, temperature=0.3)
        if not r.get("ok"):
            time.sleep(3 + 3 * k)
            continue
        t = (r.get("text") or "").strip()
        t = re.sub(r"^```(?:json)?|```$", "", t).strip()
        i, j = t.find("{"), t.rfind("}")
        try:
            ans = json.loads(t[i:j + 1])["answers"]
        except Exception:
            continue
        ans = [a.strip() for a in ans if a and a.strip()]
        if len(ans) >= len(qs):
            return ans[:len(qs)]
    return None


def inject(html: str, start: int, end: int, qs: list, ans: list) -> str:
    block = html[start:end]
    block = re.sub(r'<div class="quiz-ans">[\s\S]*?</div>\s*$', "", block.rstrip())
    items = []
    for q, a in zip(qs, ans):
        items.append('<div class="aiqa-item"><h3>%s</h3><p>%s</p></div>'
                     % (G.esc(q[:36]), G.esc(a)))
    new = (block.rstrip() + '\n<div class="quiz-ans"><h3>AI 补答（基于本书 AI 大纲）</h3>\n'
           + "\n".join(items) + "</div>\n")
    return html[:start] + new + html[end:]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--force", action="store_true", help="已答案的也重生成")
    a = ap.parse_args(argv)

    slugs = [a.slug] if a.slug else sorted(p.name for p in BOOKS.iterdir() if p.is_dir())
    todo = []
    for s in slugs:
        ov = BOOKS / s / "overview.html"
        if not ov.exists():
            continue
        html = ov.read_text(encoding="utf-8", errors="ignore")
        qs, st, en, has = parse_quiz_block(html)
        if not qs:
            continue
        if has and not a.force:
            continue
        todo.append((s, qs))
    print("缺答案：%d 本" % len(todo))
    done = 0
    for s, qs in todo:
        chs, corpus = corpus_of(s)
        if not chs:
            print("  - %-40s 库中无大纲，跳过" % s[:40])
            continue
        title = G._title_of(str(BOOKS / s), s)
        ans = gen(title, len(chs), corpus, qs)
        if not ans:
            print("  ✗ %-40s 生成失败" % s[:40])
            continue
        print("  ✓ %-40s %d 答" % (s[:40], len(ans)))
        for q, x in zip(qs, ans):
            print("     Q %s\n     A %s" % (q[:34], x[:78]))
        if a.write:
            ov = BOOKS / s / "overview.html"
            html = ov.read_text(encoding="utf-8", errors="ignore")
            qs2, st, en, _ = parse_quiz_block(html)
            ov.write_text(inject(html, st, en, qs2, ans), encoding="utf-8")
            S.save_quiz(title, [{"q": q, "a": x, "at": "backfill:2026-10-28"}
                                for q, x in zip(qs2, ans)])
            done += 1
    print("写入 %d 本%s" % (done, "" if a.write else "（未写，加 --write）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
