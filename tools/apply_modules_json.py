#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把精读页的模块区整段换成「JSON 渲染出来的」版本。

为什么要有这个工具：精读页里除了模块，还有逐章追问（第 3 批从 deep-read 合并的
2631 条 `details.mmx-ask`）——它不在任何 JSON 里，整页重渲染会把它冲掉。
所以这里只动模块区：从第一个 `<section class="mmx-mod"` 到 `<footer class="site-footer">`
之前最后一个 `</section>`，整段替换。

改文案的流程：
  1) 全站共用的标题/说明/占位 → 改 docs/mindmap-module-text.json
  2) 某本书的真内容 → 改 data/mindmap/<slug>.json 的 modules 字段
  3) 跑 `python tools/apply_modules_json.py --write`
不用再碰任何 html。

用法：
  python tools/apply_modules_json.py            # 试运行，只报每本模块数与变化
  python tools/apply_modules_json.py --write    # 落盘
  python tools/apply_modules_json.py --slug xx  # 只处理一本
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

import gen_mindmap as G  # noqa: E402

BOOKS = HERE / "reading-notes" / "books"
DB_OUT = HERE / "data" / "mindmap"
FOOT = '<footer class="site-footer">'
MOD_OPEN = '<section class="mmx-mod"'


def new_modules(slug: str) -> str:
    p = DB_OUT / ("%s.json" % slug)
    if not p.exists():
        return ""
    d = json.loads(p.read_text(encoding="utf-8"))
    return G._extra_modules(d).strip()


def patch(html: str, mods: str) -> str:
    i = html.find(MOD_OPEN)
    j = html.find(FOOT)
    if i < 0:
        # 页面还没有模块区：插到 footer 前
        return html.replace(FOOT, (mods + "\n" if mods else "") + FOOT, 1)
    if j < 0:
        return html
    k = html.rfind("</section>", i, j)
    if k < 0:
        return html
    k += len("</section>")
    return html[:i] + (mods + "\n" if mods else "") + html[k:].lstrip("\n")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--slug")
    a = ap.parse_args(argv)

    pages = ([BOOKS / a.slug / "mindmap.html"] if a.slug
             else sorted(BOOKS.glob("*/mindmap.html")))
    changed = same = skipped = 0
    for p in pages:
        if not p.exists():
            continue
        slug = p.parent.name
        if not (DB_OUT / ("%s.json" % slug)).exists():
            print("  - %-50s 无 data/mindmap/%s.json，跳过" % (slug[:50], slug))
            skipped += 1
            continue
        t = p.read_text(encoding="utf-8")
        mods = new_modules(slug)
        t2 = patch(t, mods)
        nmod = mods.count(MOD_OPEN)
        if t2 == t:
            same += 1
            continue
        changed += 1
        print("  %s %-50s 模块 %d 处（%+d 字节）"
              % ("✎" if a.write else "·", slug[:50], nmod, len(t2) - len(t)))
        if a.write:
            p.write_text(t2, encoding="utf-8", newline="\n")
    print("\n共 %d 页：%s %d，无变化 %d，跳过 %d"
          % (len(pages), "已写入" if a.write else "将改动", changed, same, skipped))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
