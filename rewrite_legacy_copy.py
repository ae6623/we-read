#!/usr/bin/env python3
"""IA-06 全站旧词统一（2026-10-29，信息架构改版第 2 批）。

映射（产品经理方案 IA-06：全站可见文案旧词 0 次）：
  读前通读  → 全书视角（页面 meta/title/标题；date-note 的 preread-bar 标题）
  全书导图  → 精读（mindmap 页自称与 overview 入口链接；保留「全书主干」表述）
  精读深读  → 精读
  尚未开读/未开读 → 尚未亲读/未亲读（provenance 事实陈述，仅换口径字面）
  已完读（index 状态标签）→ 删除标签（归档卡已有「整书汇编」类型标签）
  AI读书在读数 → AI读书平台阅读人数（统计事实，清「在读」口径字面）

注意：正文自然语言里的「正在读 / 在读书 / 在读仪表盘」等**不是口径词**，本脚本不动。
用法：python3 rewrite_legacy_copy.py [--write]；不带 --write 仅 dry-run。
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BOOKS = HERE / "reading-notes" / "books"

GLOBS = [
    "reading-notes/books/*/overview.html",
    "reading-notes/books/*/mindmap.html",
    "reading-notes/books/*/notes/deep-read.html",
    "reading-notes/books/*/outline.html",
    "index.html",
]

# (旧, 新, 说明) —— 顺序敏感：先长后短
RULES = [
    ("全书视角 · 读前通读", "全书视角", "meta/副标题"),
    ("读前通读 · 全书结构", "全书视角 · 全书结构", "overview 章节 h2"),
    ("（读前通读）", "", "title 后缀"),
    (" · 读前通读", "", "meta 描述后缀"),
    ("<h2>读前通读</h2>", "<h2>全书视角</h2>", "date-note preread-bar"),
    ("先看通读再读本篇", "先看全书视角再读本篇", "date-note 提示句"),
    ("读前通读", "全书视角", "兜底"),
    ("｜全书导图", "｜精读", "mindmap title"),
    ("全书导图</h1>", "精读 · 全书主干</h1>", "mindmap h1"),
    ("→ 全书导图：", "→ 精读：", "overview 入口链接"),
    ("全书导图", "精读 · 全书主干", "兜底"),
    ("精读深读 →", "精读 →", "overview 导航"),
    ("精读深读", "精读", "兜底"),
    ("尚未开读", "尚未亲读", "provenance 事实"),
    ("未开读", "未亲读", "provenance 事实"),
    ("AI读书在读数", "AI读书平台阅读人数", "统计口径"),
    ('<span class="type-tag">已完读</span>', "", "index 状态标签"),
]


def process_file(path: Path):
    try:
        html = path.read_text(encoding="utf-8")
    except Exception:
        return None
    orig = html
    hits = {}
    for old, new, _ in RULES:
        n = html.count(old)
        if n:
            html = html.replace(old, new)
            hits[old] = n
    if html != orig:
        path.write_text(html, encoding="utf-8", newline="\n")
    return hits


def main():
    write = "--write" in sys.argv
    files = []
    for g in GLOBS:
        files.extend(sorted(HERE.glob(g)))
    total_hits = {}
    changed = 0
    for f in files:
        hits = process_file(f) or {}
        if not hits:
            continue
        if not write:
            # dry-run：临时模拟
            pass
        changed += 1
        for k, v in hits.items():
            total_hits[k] = total_hits.get(k, 0) + v
        if write:
            print("✎", f.relative_to(HERE), {k: v for k, v in hits.items()})
    print("\n=== %s（文件 %d 个）===" % ("已写入" if write else "DRY-RUN 预览", changed))
    for k, v in sorted(total_hits.items(), key=lambda x: -x[1]):
        print("  %-28s %d 处" % (k, v))
    if not write:
        print("\n（dry-run 未写入；加 --write 执行）")


if __name__ == "__main__":
    main()
