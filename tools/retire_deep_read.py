#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""退休 deep-read 页：内容已并入精读页，把原页换成轻量迁移页。

配套 tools/merge_deep_ask.py：那条把 2879 条逐章追问 + 181 条核心追问搬进
`books/<slug>/mindmap.html`，本工具负责收尾——
  1) 有精读页的书：`notes/deep-read.html` 换成一句「已并入精读」+ 跳转；
     没有精读页的书（7 本）保留原页，不动；
  2) 通读页、归档索引里指向 `notes/deep-read.html` 的入口改指精读页。

用法：
  python tools/retire_deep_read.py            # 试运行
  python tools/retire_deep_read.py --write
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
BOOKS = HERE / "reading-notes" / "books"

PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<meta name="description" content="{title} 的逐章深读已并入精读页">
<title>{title}｜深读已并入精读</title>
<link rel="stylesheet" href="../../../../assets/css/site.css">
<link rel="stylesheet" href="../../../../assets/css/reading-deep.css">
</head>
<body>
<main class="page">
  <header class="note-head">
    <p class="eyebrow">DEEP READ · 已并入精读</p>
    <h1>{title}</h1>
    <p class="meta">逐章追问 {asks} 条 · 核心追问 {cores} 条 · 精选原文已随章归位</p>
  </header>
  <article>
    <p>这一页的内容已经并进 <a href="../mindmap.html">精读页</a>：每一章展开后，末尾就是该章的追问；跨章的主题追问在页尾「核心追问」。原来的精选原文摘录同样按章归在精读页里。</p>
    <p><a href="../mindmap.html">→ 打开精读</a></p>
    <p class="meta">其他入口：<a href="../overview.html">全书视角</a>　<a href="../../../../index.html">首页</a></p>
  </article>
</main>
</body>
</html>
"""


def page_title(mp: Path) -> str:
    t = mp.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"<h1[^>]*>(.*?)</h1>", t, re.S)
    if not m:
        return Path(mp).parent.name
    s = re.sub(r"<[^>]+>", "", m.group(1)).strip()
    s = re.sub(r"[\s·—-]*精读$", "", s).strip()
    return s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    done = keep = 0
    for dp in sorted(BOOKS.glob("*/notes/deep-read.html")):
        mp = dp.parent.parent / "mindmap.html"
        if not mp.exists():
            keep += 1
            continue
        asks = len(re.findall(r"<details class=\"mmx-ask\"", mp.read_text(encoding="utf-8")))
        jp = HERE / "data" / "mindmap" / (dp.parent.parent.name + ".json")
        cores = 0
        if jp.exists():
            try:
                d = json.loads(jp.read_text(encoding="utf-8"))
                cores = len(((d.get("modules") or {}).get("coreask") or {}).get("pairs") or [])
            except Exception:
                cores = 0
        html = PAGE.format(title=page_title(mp),
                           asks=mp.read_text(encoding="utf-8").count('<details class="mmx-ask"'),
                           cores=cores)
        if args.write:
            dp.write_text(html, encoding="utf-8", newline="\n")
        done += 1

    # 入口改指精读页
    patched = 0
    targets = list(BOOKS.glob("*/overview.html")) + [HERE / "reading-notes" / "index.html"]
    for f in targets:
        if not f.exists():
            continue
        t = f.read_text(encoding="utf-8", errors="ignore")
        orig = t
        t = t.replace('href="notes/deep-read.html">逐章深读（含 AI 追问） →',
                      'href="mindmap.html">精读（含逐章追问） →')
        t = t.replace('href="notes/deep-read.html">逐章深读（含 AI 追问）',
                      'href="mindmap.html">精读（含逐章追问）')
        t = t.replace('href="notes/deep-read.html">精读 →', 'href="mindmap.html">精读 →')
        t = t.replace('href="books/tou-guo-di-li-kan-li-shi-xi-lie--quan-3-ce-/notes/deep-read.html">精读深读（按大纲）',
                      'href="books/tou-guo-di-li-kan-li-shi-xi-lie--quan-3-ce-/mindmap.html">精读（按主干重排）')
        if t != orig:
            patched += 1
            if args.write:
                f.write_text(t, encoding="utf-8", newline="\n")

    left = 0
    for f in list(BOOKS.glob("*/overview.html")) + [HERE / "reading-notes" / "index.html", HERE / "index.html"]:
        if f.exists() and "notes/deep-read.html" in f.read_text(encoding="utf-8", errors="ignore"):
            left += 1

    print("迁移页 %s %d 张 / 无精读页保留原文 %d 张 / 入口改指 %d 处 / 仍指向 deep-read 的页 %d"
          % ("已写入" if args.write else "将写入", done, keep, patched, left))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
