#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""补齐某本书 combined-data.html 的全部领读模块。

设计（2026-11-04 续接「人类简史三册补齐」）：
  站点仓 reading-notes/books/<slug>/combined-data.html 是「全书领读」页的数据层，
  由 10 个 <section data-key="..."> 组成（顺序见 ORDER）。三册（人类简史）目前
  只有 aiask，缺其余 9 个。

  模块分两类：
    1) 结构化（无 LLM，纯脚本）：svg / oneline / merged_guide / views
       - 数据 100% 取自本书 outline.html 的章节树 + 热门划线原文，
       - 复用 rebuild_guide_from_outline.parse_page / build_section，
       - oneline/views/svg 的「按章序机械切块」逻辑与 gen_mindmap.structural_batch
         同口径，诚实标注「结构提要，非读后感」。
    2) LLM（Agent 兜底，免登录）：coreask / higher / verify / thennow / quiz
       - 由 Agent 基于 outline 真实内容撰写、诚实标注「基于大纲、未亲读」，
       - 通过 --llm <json> 传入内容后注入（不编造、cite 命中大纲原文）。

用法：
  python3 tools/fill_combined_modules.py --slug <slug>            # 仅补结构化 4 模块
  python3 tools/fill_combined_modules.py --all                  # 三册全补结构化
  python3 tools/fill_combined_modules.py --slug <slug> --llm drafts/<slug>-llm.json  # 再注入 LLM 5 模块
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
sys.path.insert(0, str(ROOT / "tools"))
import rebuild_guide_from_outline as rbg  # parse_page / build_section / DEFAULT_STYLE

STRUCT_KEYS = ["svg", "oneline", "merged_guide", "views"]
LLM_KEYS = ["coreask", "higher", "verify", "thennow", "quiz"]
# 标准顺序：svg → oneline → merged_guide → views → aiask → 其余 LLM 模块
ORDER = ["svg", "oneline", "merged_guide", "views", "aiask",
         "coreask", "higher", "verify", "thennow", "quiz"]

GROUP = 7  # 每多少章切一段主干（与 gen_mindmap.structural_batch 默认一致）


# ---------------------------------------------------------------- 解析
def chapters_of(slug: str) -> list[dict]:
    p = BOOKS / slug / "outline.html"
    if not p.exists():
        return []
    return rbg.parse_page(p)


def meta_of(slug: str) -> dict:
    p = BOOKS / slug / "outline.html"
    title = slug
    if p.exists():
        m = re.search(r"<title>《(.+?)》", p.read_text(encoding="utf-8", errors="ignore"))
        if m:
            title = m.group(1)
    return {"title": title}


# ---------------------------------------------------------------- 结构化模块
def build_spine(chs: list[dict], group: int = GROUP) -> list[dict]:
    groups, cur = [], []
    for c in chs:
        cur.append(c)
        if len(cur) >= group:
            groups.append(cur)
            cur = []
    if cur:
        if groups and len(cur) <= 2:
            groups[-1].extend(cur)
        else:
            groups.append(cur)
    ids = "ABCDEFGHIJ"
    spine = []
    for i, g in enumerate(groups):
        sid = ids[i] if i < len(ids) else "G%d" % i
        first, last = g[0], g[-1]
        label = ("第 %d–%d 章" % (first["no"], last["no"])
                 if first["no"] != last["no"] else "第 %d 章" % first["no"])
        why = "含「%s」至「%s」" % (first["title"][:12], last["title"][:12])
        spine.append({"id": sid, "label": label,
                      "why": why, "chapters": [c["no"] for c in g]})
    return spine


def render_oneline(chs: list[dict], title: str) -> str:
    n = len(chs)
    spine = build_spine(chs)
    head = "、".join(s["label"] for s in spine[:3])
    claim = ("《%s》共 %d 章，按章序折成 %d 段主干（%s）；"
             "每章的要点与原句均逐字取自本书 AI 大纲，未做人工解读。"
             % (title, n, len(spine), head))
    note = "本页「一句话主旨」由 AI 大纲结构重算：主干按章序机械切分，非语义聚类；" \
           "命题只陈述结构事实，不构成读后感。"
    return ('<section class="mmx-mod" aria-labelledby="oneline" data-key="oneline">'
            '<h2 id="oneline">一句话主旨</h2>'
            '<p class="mmx-mod-note">%s</p>'
            '<p class="mmx-oneline">%s</p></section>' % (H.escape(note), H.escape(claim)))


def render_views(chs: list[dict]) -> str:
    spine = build_spine(chs)
    if not spine:
        return ""
    note = "按全书主干分组，归纳各段在论证中的位置（取自大纲结构，非读后感）。"
    items = []
    for s in spine:
        label = s["label"]
        why = s["why"]
        items.append("<li><b>%s</b>——%s</li>" % (H.escape(label), H.escape(why)))
    return ('<section class="mmx-mod" aria-labelledby="views" data-key="views">'
            '<h2 id="views">核心观点初判</h2>'
            '<p class="mmx-mod-note">%s</p>'
            '<ul class="mmx-views">%s</ul></section>' % (H.escape(note), "".join(items)))


def render_svg(chs: list[dict], title: str) -> str:
    spine = build_spine(chs)
    if not spine:
        return ""
    n = len(spine)
    W = max(760, n * 180 + 40)
    HGT = 150
    gap = W / n
    parts = ['<svg class="mmx-svg" viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg"'
             ' preserveAspectRatio="xMinYMin meet" role="img" aria-label="%s 结构导图">'
             % (W, HGT, H.escape(title))]
    parts.append('<style>.mmx-svg text{font-family:"Noto Serif SC",Georgia,serif;fill:#3a342b}'
                '.mmx-svg .rt{font-size:13px;font-weight:600}'
                '.mmx-svg .rc{fill:#fbf7ee;stroke:#d8cdb4;stroke-width:1.4}'
                '.mmx-svg .ln{stroke:#cfc6b4;stroke-width:1.6;fill:none}'
                '.mmx-svg .sm{font-size:10.5px;fill:#8a8272}</style>')
    cy = HGT / 2
    bw, bh = 150, 64
    xs = [gap * (i + 0.5) for i in range(n)]
    for i, s in enumerate(spine):
        cx = xs[i]
        x0 = cx - bw / 2
        y0 = cy - bh / 2
        parts.append('<rect class="rc" x="%.1f" y="%.1f" width="%d" height="%d" rx="9"/>'
                     % (x0, y0, bw, bh))
        parts.append('<text class="rt" x="%.1f" y="%.1f" text-anchor="middle">%s</text>'
                     % (cx, cy - 6, H.escape(s["label"])))
        parts.append('<text class="sm" x="%.1f" y="%.1f" text-anchor="middle">%s</text>'
                     % (cx, cy + 14, H.escape(s["why"][:18])))
        if i < n - 1:
            parts.append('<path class="ln" d="M%.1f %.1f L%.1f %.1f"/>'
                         % (x0 + bw, cy, xs[i + 1] - 75, cy))
    parts.append('</svg>')
    return ('<section class="mmx-svgwrap" data-key="svg">'
            '<h2 id="mod-svg" class="sr-only">结构导图</h2>'
            + "".join(parts) + '</section>')


def render_merged(chs: list[dict]) -> str:
    return rbg.build_section(rbg.DEFAULT_STYLE, chs)


# ---------------------------------------------------------------- LLM 模块
def render_llm(key: str, data) -> str:
    if key == "coreask":
        items = data if isinstance(data, list) else []
        body = '<div class="mmx-ask">%s</div>' % "".join(
            '<div class="aiqa-item"><h3>%s</h3><p>%s</p></div>'
            % (H.escape(it.get("q", "")), H.escape(it.get("a", ""))) for it in items)
        return _mmx(key, "核心追问（来自深读）",
                    "跨章主题的深读追问，基于全书大纲与热门划线撰写；逐章的追问收在每个章条目里。", body)
    if key == "quiz":
        items = data if isinstance(data, list) else []
        body = '<div class="mmx-ask">%s</div>' % "".join(
            '<div class="aiqa-item"><h3>%s</h3><p>%s</p></div>'
            % (H.escape(it.get("q", "")), H.escape(it.get("a", ""))) for it in items)
        return ('<section class="card quiz-card" data-key="quiz">'
                '<h2 id="quiz">读完自测</h2>'
                '<p class="mmx-mod-note">基于本书 AI 大纲与热门划线原文的自测追问，不编答案。%s</p>%s</section>'
                % (FALLBACK_TAG, body))
    # higher / verify / thennow：段落或列表
    paras = data if isinstance(data, list) else []
    if all(isinstance(x, str) for x in paras):
        body = "".join("<p>%s</p>" % H.escape(x) for x in paras)
    else:
        body = '<ul class="mmx-views">%s</ul>' % "".join(
            "<li>%s</li>" % H.escape(x) for x in paras)
    title_map = {"higher": "用更高维度的知识看这本书",
                 "verify": "阅读时要验证的问题",
                 "thennow": "当年与今天 · 初步对照"}
    note_map = {
        "higher": "把本书放回知识史与理论框架中重读，区分书中主张、外部证据与综合分析。",
        "verify": "读时需核对的原文、数字与论点（关键数据出处、个案代表性、类比限度）。",
        "thennow": "区分作者当年所能知晓与后来才显现的事实，给出今日可迁移的启发。",
    }
    return _mmx(key, title_map[key], note_map[key], body)


FALLBACK_TAG = "（Agent 兜底生成 · 基于大纲、未亲读）"


def _mmx(key: str, title: str, note: str, body: str) -> str:
    note2 = (note or "") + FALLBACK_TAG
    return ('<section class="mmx-mod" aria-labelledby="%s" data-key="%s">'
            '<h2 id="%s">%s</h2><p class="mmx-mod-note">%s</p>%s</section>'
            % (key, key, key, H.escape(title), H.escape(note2), body))


# ---------------------------------------------------------------- 组装
SEC_RE = re.compile(r'<section[^>]*data-key="([a-z_]+)"[^>]*>.*?</section>', re.S)


def existing_sections(txt: str) -> dict:
    out = {}
    for m in SEC_RE.finditer(txt):
        out[m.group(1)] = m.group(0)
    return out


def assemble(slug: str, struct: bool, llm_data: dict | None) -> int:
    page = BOOKS / slug / "combined-data.html"
    if not page.exists():
        print("✗ %s 无 combined-data.html" % slug)
        return 1
    chs = chapters_of(slug)
    if not chs:
        print("✗ %s 无 outline 章节" % slug)
        return 1
    meta = meta_of(slug)

    sections = existing_sections(page.read_text(encoding="utf-8", errors="ignore"))

    if struct:
        sections["svg"] = render_svg(chs, meta["title"])
        sections["oneline"] = render_oneline(chs, meta["title"])
        sections["views"] = render_views(chs)
        sections["merged_guide"] = render_merged(chs)

    if llm_data:
        for k in LLM_KEYS:
            if k in llm_data and llm_data[k]:
                sections[k] = render_llm(k, llm_data[k])

    ordered = [sections[k] for k in ORDER if k in sections]
    meta_line = "<!--META %s-->" % json.dumps(
        {"slug": slug, "title": meta.get("title", slug)}, ensure_ascii=False)
    page.write_text(meta_line + "\n" + "\n".join(ordered) + "\n", encoding="utf-8")
    print("✓ %s 补齐完成：%s" % (slug, ", ".join(k for k in ORDER if k in sections)))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--llm", help="Agent 兜底的 LLM 模块 JSON（coreask/higher/verify/thennow/quiz）")
    a = ap.parse_args()

    targets = []
    if a.all:
        targets = ["ren-lei-jian-shi-xin-ban-cong-dong-wu-dao-shang-di",
                   "wei-lai-jian-shi",
                   "jin-ri-jian-shi-ren-lei-ming-yun-da-yi-ti"]
    elif a.slug:
        targets = [a.slug]
    else:
        ap.print_help()
        return 1

    llm_data = None
    if a.llm:
        llm_data = json.loads(Path(a.llm).read_text(encoding="utf-8"))

    for slug in targets:
        assemble(slug, struct=not bool(llm_data), llm_data=llm_data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
