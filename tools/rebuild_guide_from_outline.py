#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用已入库的 AI 大纲重建「AI 领读」模块（combined-data.html 的 merged_guide）。

背景：2026-11-03 之前有 176 本的 AI 领读是「章目录 + 热门划线」的降级版
（只有 ul.quote，没有要点），点开只有一堆划线。本脚本把 merged_guide
换成大纲原生树：章（details.mmx-cn）→ 小节（div.sec）→ 要点（ul.point>li>b）
→ 原句（ul.quote）+ 本小节汇总原句（ul.quote.quote-node）。

数据源优先 data/outline/<slug>.json，缺失时直接解析 books/<slug>/outline.html。

用法：
  python tools/rebuild_guide_from_outline.py --dry
  python tools/rebuild_guide_from_outline.py --only slug-a,slug-b
  python tools/rebuild_guide_from_outline.py
"""
from __future__ import annotations

import argparse
import html as H
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOKS = ROOT / "reading-notes" / "books"
OUT_JSON = ROOT / "data" / "outline"
TPL_SLUG = "wen-hua-ku-lv"

SEC_RE = re.compile(
    r'<section class="card merged-guide ai-lead"[^>]*data-key="merged_guide">.*?</section>', re.S)

DEFAULT_STYLE = """<style>
.merged-guide .sec{margin:10px 0 14px;padding-left:6px;border-left:2px solid #e5e0d6}
.merged-guide .sec h4{font:600 .98rem/1.6 "Noto Serif SC","Songti SC",Georgia,serif;color:#315e50;margin:.6em 0 .3em}
.merged-guide ul.point{margin:.3em 0;padding-left:20px}
.merged-guide ul.point>li{margin:.35em 0}
.merged-guide ul.quote{margin:.25em 0 .25em 20px;padding-left:18px;list-style:none}
.merged-guide ul.quote::before{content:"原句";display:block;font-size:.72rem;color:#bf8247;
  letter-spacing:.1em;margin:.15em 0 .1em;font-weight:600}
.merged-guide ul.quote.quote-node{margin-top:.5em;padding-top:.4em;border-top:1px dashed #eadfc9}
.merged-guide ul.quote.quote-node::before{content:"原句 · 本小节汇总"}
.merged-guide ul.quote>li{color:#4a4436;font-size:.93rem;margin:.2em 0;padding-left:10px;border-left:2px solid #bf8247}
</style>"""


def parse_page(path: Path) -> list[dict]:
    """outline.html → chapters（无 bs4 依赖）"""
    s = path.read_text(encoding="utf-8", errors="ignore")
    chs = []
    for m in re.finditer(r'<details class="ch"[^>]*>\s*<summary>(.*?)</summary>(.*?)</details>', s, re.S):
        title = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        inner = m.group(2)
        secs = []
        for sm in re.finditer(r'<div class="sec">(.*?)</div>', inner, re.S):
            blk = sm.group(1)
            hm = re.search(r"<h4>(.*?)</h4>", blk, re.S)
            head = re.sub(r"<[^>]+>", "", hm.group(1)).strip() if hm else ""
            points = []
            for pm in re.finditer(r"<li><b>(.*?)</b>(.*?)</li>", blk, re.S):
                txt = re.sub(r"<[^>]+>", "", pm.group(1)).strip()
                quotes = []
                qm = re.search(r'<ul class="quote">(.*?)</ul>', pm.group(2), re.S)
                if qm:
                    quotes = [re.sub(r"<[^>]+>", "", q).strip()
                              for q in re.findall(r"<li>(.*?)</li>", qm.group(1), re.S)]
                if txt:
                    points.append({"text": txt, "quotes": [q for q in quotes if q]})
            if points:
                secs.append({"h": head, "points": points})
        if secs:
            chs.append({"no": len(chs) + 1, "title": title, "secs": secs})
    return chs


def build_section(style: str, chapters: list[dict]) -> str:
    out = ['<section class="card merged-guide ai-lead" aria-labelledby="merged-guide-title" '
           'data-key="merged_guide"><h2 id="merged-guide-title">AI领读</h2>', style,
           '<p class="small">章节目录与 AI 大纲融合为一棵树：篇章分组即目录，'
           '展开各章即骨架与逐节 AI 大纲（要点 · 原句摘录）。</p>',
           '  <div class="toc-part"><span class="part-label">全书篇目（AI 大纲顺序）</span>']
    for i, c in enumerate(chapters, 1):
        secs = c.get("secs") or []
        n_point = sum(len(s.get("points") or []) for s in secs)
        n_quote = sum(len(p.get("quotes") or []) for s in secs for p in (s.get("points") or []))
        out.append('    <details class="mmx-cn"><summary>\n'
                   '        <span class="mmx-no">%d</span><span class="mmx-name">%s</span>\n'
                   '        <span class="mmx-caret">›</span>\n'
                   '      </summary>\n      <div class="mmx-body">'
                   % (i, H.escape(c["title"])))
        out.append('<p class="mmx-stat">共 %d 个小节 · %d 条要点 · %d 句原句摘录</p>'
                   % (len(secs), n_point, n_quote))
        for s in secs:
            out.append('<div class="sec">')
            if s.get("h"):
                out.append("<h4>%s</h4>" % H.escape(s["h"]))
            out.append('<ul class="point">')
            for p in s.get("points") or []:
                out.append("<li><b>%s</b>" % H.escape(p["text"]))
                qs = p.get("quotes") or []
                if qs:
                    out.append('<ul class="quote">' +
                               "".join("<li>%s</li>" % H.escape(q) for q in qs) + "</ul>")
                out.append("</li>")
            out.append("</ul>")
            all_q = [q for p in (s.get("points") or []) for q in (p.get("quotes") or [])]
            if all_q:
                out.append('<ul class="quote quote-node">' +
                           "".join("<li>%s</li>" % H.escape(q) for q in all_q) + "</ul>")
            out.append("</div>")
        out.append("</div></details>")
    out.append("  </div>\n</section>")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--only", default="")
    a = ap.parse_args()

    tpl = (BOOKS / TPL_SLUG / "combined-data.html").read_text(encoding="utf-8")
    m = SEC_RE.search(tpl)
    style = DEFAULT_STYLE
    if m:
        sm = re.search(r"<style>.*?</style>", m.group(0), re.S)
        if sm and "merged-guide" in sm.group(0):
            style = sm.group(0)

    if OUT_JSON.exists():
        slugs = sorted(p.stem for p in OUT_JSON.glob("*.json"))
    else:
        slugs = sorted(d.name for d in BOOKS.iterdir() if d.is_dir())
    if a.only:
        # 显式点名的书不受 JSON 清单限制：没缓存就回退解析 outline.html
        keep = [x.strip() for x in a.only.split(",") if x.strip()]
        slugs = [s for s in keep if (BOOKS / s).is_dir()]
    if a.limit:
        slugs = slugs[:a.limit]

    done = skip = 0
    for slug in slugs:
        page = BOOKS / slug / "combined-data.html"
        if not page.exists():
            skip += 1
            continue
        jf = OUT_JSON / (slug + ".json")
        if jf.exists():
            chs = (json.loads(jf.read_text(encoding="utf-8")).get("chapters") or [])
        elif (BOOKS / slug / "outline.html").exists():
            chs = parse_page(BOOKS / slug / "outline.html")
        else:
            skip += 1
            continue
        if not chs:
            skip += 1
            continue
        s = page.read_text(encoding="utf-8")
        old = SEC_RE.search(s)
        if not old:
            skip += 1
            continue
        new_sec = build_section(style, chs)
        if a.dry:
            print("%-46s %d 章 → %d 字节" % (slug, len(chs), len(new_sec)))
            done += 1
            continue
        page.write_text(s[:old.start()] + new_sec + s[old.end():], encoding="utf-8", newline="\n")
        done += 1
    print("\n重建 %d 本，跳过 %d 本" % (done, skip))
    return 0


if __name__ == "__main__":
    sys.exit(main())
