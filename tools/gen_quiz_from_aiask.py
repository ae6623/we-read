#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给缺「读完自测」模块的书补上 quiz —— 题目取自本页已有的「AI 问书」问句。

背景：这批书微信读书没有官方 AI 大纲（合集 / 杂志 / 本地导入），跑不了
fill_combined_modules 的 LLM 生成；但它们已有手写的 aiask 问答，把其中的
问句抽出来就是一套现成的自测清单（合上书本回答，不给答案）。

幂等：已有 data-key="quiz" 的书直接跳过。

用法：
  python tools/gen_quiz_from_aiask.py --dry
  python tools/gen_quiz_from_aiask.py
"""
from __future__ import annotations

import argparse
import html as H
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOKS = ROOT / "reading-notes" / "books"


def quiz_html(questions: list[str], src: str) -> str:
    body = "".join(
        '<div class="aiqa-item"><h3>%s</h3>'
        '<p class="quiz-blank">（合上书本自测，不在此给答案）</p></div>' % H.escape(q)
        for q in questions)
    note = ("题目取自本页「%s」的问题，翻回去之前先自己答一遍；"
            "（Agent 兜底 · 未亲读原书）" % src)
    return ('<section class="card quiz-card" data-key="quiz">'
            '<h2 id="quiz">读完自测</h2>'
            '<p class="mmx-mod-note">%s</p>'
            '<div class="mmx-ask">%s</div></section>' % (H.escape(note), body))


def questions_of(s: str) -> tuple[list[str], str]:
    m = re.search(r'data-key="aiask".*?</section>', s, re.S)
    if m:
        qs = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", x)).strip()
              for x in re.findall(r'<div class="aiqa-item"><h3>(.*?)</h3>', m.group(0), re.S)]
        qs = [q for q in qs if q]
        if len(qs) >= 3:
            return qs[:7], "AI 问书"
    # 退路：用核心追问的问题
    m = re.search(r'data-key="coreask".*?</section>', s, re.S)
    if m:
        qs = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", x)).strip()
              for x in re.findall(r'<div class="aiqa-item"><h3>(.*?)</h3>', m.group(0), re.S)]
        qs = [q for q in qs if q]
        if len(qs) >= 3:
            return qs[:7], "核心追问"
    return [], ""


def is_shell(slug: str) -> bool:
    """没有官方 AI 大纲的书：outline.html 里没有章级 <details class="ch">"""
    p = BOOKS / slug / "outline.html"
    if not p.exists():
        return True
    s = p.read_text(encoding="utf-8", errors="ignore")
    return '<details class="ch"' not in s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--all", action="store_true", help="全站缺 quiz 的都补（默认只补无大纲的壳书）")
    a = ap.parse_args()
    ok = skip = fail = 0
    for d in sorted(p for p in BOOKS.iterdir() if p.is_dir()):
        if not a.all and not is_shell(d.name):
            continue
        p = d / "combined-data.html"
        if not p.exists():
            continue
        s = p.read_text(encoding="utf-8", errors="ignore")
        if 'data-key="quiz"' in s:
            continue
        if 'data-key="aiask"' not in s and 'data-key="coreask"' not in s:
            print("– 跳过（无问答可取材）：", d.name)
            skip += 1
            continue
        qs, src = questions_of(s)
        if not qs:
            print("– 跳过（问句不足 3 条）：", d.name)
            skip += 1
            continue
        print("+ %s（%d 题，取自%s）" % (d.name, len(qs), src))
        if a.dry:
            ok += 1
            continue
        s = s.rstrip() + "\n" + quiz_html(qs, src) + "\n"
        p.write_text(s, encoding="utf-8")
        ok += 1
    print("完成：补 %d 本，跳过 %d 本" % (ok, skip))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
