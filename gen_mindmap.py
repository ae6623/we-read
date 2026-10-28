#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""二次提炼：AI 大纲 → 全书主干 / 章节定位 / 跨章张力 → 思维导图页。

不是把目录换个画法。输入是 `book_outline`（章 → 小节 → 要点 → 原句），
LLM 只做三件纯机器做不到的事：

  1. thesis  全书一条命题 + 它成立的边界
  2. spine   把章重新分成 5–7 条主干（不等同于书的目录分卷）
  3. role    每章在全书的**功能**（铺垫/立论/反证/案例/收束），不是内容摘要

其余全部由脚本算：证据密度、要点数、原句数、锚点校验（防止编造引文）。

两段式调用（长书也不炸上下文）：
  pass1 章标题 + 要点摘录 → thesis + spine（章区间）
  pass2 每 80 章一批 → gist / role / concepts / anchor

产出：
  data/mindmap/<slug>.json          结构化结果（含校验信息）
  reading-notes/books/<slug>/mindmap.html   站点页面（内联 SVG，无运行时依赖）

用法：
  python gen_mindmap.py --slug wei-cheng --write
  python gen_mindmap.py --all --write --limit 5
  python gen_mindmap.py --slug X --dry-run      # 只调 LLM 打印 JSON，不落盘
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
# HERE 必须优先于 weread-auto：两个仓库各有一个 weread_store.py，
# 本脚本要的是 we-read 版（含 book_outline / note），weread-auto 只提供 gemini_client。
sys.path.append(str(HERE.parent / "weread-auto"))
sys.path.insert(0, str(HERE))

import gen_outline_full as G  # noqa: E402
import weread_store as S  # noqa: E402

DB_OUT = HERE / "data" / "mindmap"
BOOKS = HERE / "reading-notes" / "books"
MODEL = "gemini-3.5-flash"
BATCH = 80

SYSTEM = """你是读书笔记的结构分析师。用户提供的是某本书的 AI 大纲条目（不是原文，是别人对原书的逐章梳理）。
你的任务是**结构化重构**，不是复述、不是评价文笔、不是写读后感。

铁律：
1. 只使用给出的条目内容。不得引入书外知识、不得推断原书没说的观点。
2. 不出现平台名（微信/得到/樊登等），一律写「AI」。
3. 不提页码、页数、阅读时长、翻页次数、进度百分比。
4. 中文，术语克制，不用「赋能/抓手/闭环」这类空话。
5. 只输出 JSON，不要 markdown 代码块，不要解释。
"""

PROMPT_SPINE = """《{title}》共 {n} 章。下面是每章的标题与前几条大纲要点：

{corpus}

请输出 JSON：
{{
  "thesis": {{"claim": "全书一条命题，≤50字", "boundary": "这条命题在什么条件下成立/什么范围内不成立，≤60字"}},
  "spine": [
    {{"id": "A", "label": "主干名，≤8字", "chapters": [1,2,3], "why": "为什么这几章构成一条主干，≤40字"}}
  ]
}}

要求：
- spine 为 5–7 条，必须覆盖全部 {n} 章，不重不漏；章号用给出的数字。
- label 要概括「这条线在论证什么」，不能是「第一章到第五章」这种位置描述。
- 如果书本身有明确的分卷/部，可沿用，但仍是 5–7 条。
"""

PROMPT_CH = """《{title}》的主干结构如下：
{spine}

下面是第 {lo}–{hi} 章的标题与要点摘录：

{corpus}

请逐章输出 JSON：
{{
  "chapters": [
    {{"no": {lo}, "gist": "这章在论证什么，≤40字", "role": "铺垫|立论|反证|案例|收束",
      "concepts": ["概念1", "概念2"], "anchor": "该章最代表性的一句原句（逐字抄，≤60字）"}}
  ]
}}

要求：
- 覆盖第 {lo}–{hi} 章全部章号，一章不漏。
- gist 写「这章做了什么论证」，不写「介绍了……」。不要每章都套「通过……论证……」的句式，
  直接写这章的动作与对象（谁、争什么、把哪一步拆开了）。
- 多章讲同一件事时，要写每章相比上一章推进了什么，不能同义改写。
- role 只能取给定五值之一。
- anchor 必须逐字来自该章的「原句」；该章没有原句时，逐字抄该章一条要点（≤60字），不要自己造句。
"""


# ------------------------------------------------------------------ 上下文
def build_ctx(slug: str):
    chs = S.load_book_outline(slug)
    if not chs:
        return None
    title = G._title_of(str(BOOKS / slug), slug)
    out = []
    for c in chs:
        pts = [p for s in c["secs"] for p in s["points"]]
        quotes = [q for s in c["secs"] for p in s["points"] for q in p["quotes"]]
        brief = " / ".join(p["text"][:70] for p in pts[:3])
        out.append({
            "no": c["no"], "title": c["title"], "brief": brief,
            "pts": len(pts), "with_q": sum(1 for p in pts if p["quotes"]),
            "quotes": quotes,
            "anchor_pool": quotes[:6] + [p["text"] for p in pts[:6]],
        })
    return {"slug": slug, "title": title, "chapters": out}


def _corpus(chapters, lo=0, hi=10 ** 6, max_brief=110):
    lines = []
    for c in chapters:
        if not (lo <= c["no"] <= hi):
            continue
        lines.append("第%d章 %s | %s" % (c["no"], c["title"], c["brief"][:max_brief]))
    return "\n".join(lines)


def _json_of(text: str):
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    i, j = t.find("{"), t.rfind("}")
    if i < 0 or j <= i:
        return None
    try:
        return json.loads(t[i:j + 1])
    except Exception:
        # 常见：尾逗号
        try:
            return json.loads(re.sub(r",\s*([}\]])", r"\1", t[i:j + 1]))
        except Exception:
            return None


def llm(prompt: str, max_tokens: int = 4096, retry: int = 2):
    import gemini_client as gc
    for k in range(retry + 1):
        r = gc.generate(prompt, system=SYSTEM, model=MODEL, timeout=180,
                        max_tokens=max_tokens, temperature=0.35)
        if r.get("ok"):
            d = _json_of(r["text"])
            if d is not None:
                return d, None
            err = "JSON 解析失败：" + (r.get("text") or "")[:120]
        else:
            err = str(r.get("error"))[:160]
        if k < retry:
            time.sleep(3 + 4 * k)
    return None, err


# ------------------------------------------------------------------ 提炼
def refine(ctx: dict, log=print):
    chs = ctx["chapters"]
    n = len(chs)
    d1, err = llm(PROMPT_SPINE.format(title=ctx["title"], n=n,
                                      corpus=_corpus(chs)), max_tokens=2048)
    if not d1:
        return None, "pass1 失败：%s" % err
    thesis = d1.get("thesis") or {}
    spine = [s for s in (d1.get("spine") or []) if s.get("chapters")]
    if not spine:
        return None, "pass1 未给出主干"

    # 主干归属：章号 → 主干 id（补漏：未覆盖的章挂到最近的前一条主干）
    owner = {}
    for s in spine:
        for no in s["chapters"]:
            try:
                owner[int(no)] = s["id"]
            except Exception:
                pass
    last = spine[0]["id"]
    for c in chs:
        if c["no"] in owner:
            last = owner[c["no"]]
        else:
            owner[c["no"]] = last

    # pass2：分批拿章级定位
    chmap = {}
    for lo in range(1, n + 1, BATCH):
        hi = min(lo + BATCH - 1, n)
        part = [c for c in chs if lo <= c["no"] <= hi]
        if not part:
            continue
        sp_txt = "\n".join("%s %s：第 %s 章" % (
            s["id"], s.get("label", ""),
            ",".join(str(x) for x in sorted(set(int(i) for i in s["chapters"] if str(i).isdigit()))))
            for s in spine)
        got, err2 = llm(PROMPT_CH.format(title=ctx["title"], spine=sp_txt,
                                         lo=lo, hi=hi, corpus=_corpus(chs, lo, hi)),
                        max_tokens=8192)
        if not got:
            log("    ! pass2 %d-%d 失败：%s" % (lo, hi, err2))
            continue
        for it in got.get("chapters") or []:
            try:
                chmap[int(it.get("no"))] = it
            except Exception:
                pass
        log("    pass2 %d-%d → %d 章" % (lo, hi, len(chmap)))

    # 锚点校验：必须能在该章原句/要点里找到
    bad = []
    out_ch = []
    for c in chs:
        it = chmap.get(c["no"]) or {}
        gist = (it.get("gist") or "").strip()
        role = (it.get("role") or "").strip()
        if role not in ("铺垫", "立论", "反证", "案例", "收束"):
            role = "立论"
        anchor = (it.get("anchor") or "").strip()
        pool = [re.sub(r"\s+", "", x) for x in c["anchor_pool"]]
        ok_anchor = bool(anchor) and any(
            re.sub(r"\s+", "", anchor)[:40] in p for p in pool if p)
        if anchor and not ok_anchor:
            bad.append(c["no"])
            anchor = ""
        out_ch.append({
            "no": c["no"], "title": c["title"],
            "spine": owner.get(c["no"]),
            "gist": gist or "(未生成)",
            "role": role,
            "concepts": [x for x in (it.get("concepts") or []) if x][:4],
            "anchor": anchor,
            "anchor_ok": ok_anchor,
            "pts": c["pts"], "with_q": c["with_q"],
        })

    pts = sum(c["pts"] for c in out_ch)
    wq = sum(c["with_q"] for c in out_ch)
    return ({
        "slug": ctx["slug"], "title": ctx["title"],
        "thesis": {"claim": (thesis.get("claim") or "").strip(),
                   "boundary": (thesis.get("boundary") or "").strip()},
        "spine": [s for s in (
            {"id": s["id"], "label": (s.get("label") or "").strip(),
             "why": (s.get("why") or "").strip(),
             "chapters": [c["no"] for c in out_ch if c["spine"] == s["id"]]}
            for s in spine) if s["chapters"]],
        "chapters": out_ch,
        "evidence": {"points": pts, "with_quote": wq,
                     "density": round(wq / pts, 3) if pts else 0.0},
        "bad_anchor": bad,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
    }, None)


# ------------------------------------------------------------------ 渲染
E = G.esc
ROLE_CLS = {"铺垫": "r-pre", "立论": "r-th", "反证": "r-cnt", "案例": "r-case", "收束": "r-end"}


def _svg_spine(d: dict) -> str:
    """全书主干图：书名 → 5–7 条主干。规模恒定，长书也不会糊。"""
    sp = d["spine"]
    n = len(sp)
    row_h = 62
    top = 30
    h = top * 2 + row_h * n + 40
    w = 1120
    cx0, cw = 28, 250
    sx, sw = 400, 250
    bx, bw = 700, 380
    cy = top + (row_h * n) / 2

    out = ['<svg class="mm-svg" viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg"'
           ' role="img" aria-label="%s 全书主干导图">' % (w, h, E(d["title"])),
           '<rect x="0" y="0" width="%d" height="%d" fill="none"/>' % (w, h),
           '<style>'
           '.mm-svg text{font-family:"Noto Serif SC",Georgia,serif}'
           '.mm-svg .t1{font-size:15px;fill:#2f2a24;font-weight:600}'
           '.mm-svg .t2{font-size:12px;fill:#5c5347}'
           '.mm-svg .t3{font-size:10.5px;fill:#8a8272}'
           '.mm-svg .rt{font-size:13px;fill:#f7f3ea;font-weight:600}'
           '.mm-svg .ln{stroke:#cfc6b4;stroke-width:1.4;fill:none}'
           '</style>']

    # root
    out.append('<rect x="%d" y="%d" width="%d" height="62" rx="10" fill="#3d372e"/>'
               % (cx0, cy - 31, cw))
    out.append('<text class="rt" x="%d" y="%d">%s</text>'
               % (cx0 + 16, cy - 6, E(d["title"][:12])))
    out.append('<text class="t3" x="%d" y="%d" style="fill:#c9c0ae">%d 章 · 主干 %d 条</text>'
               % (cx0 + 16, cy + 14, len(d["chapters"]), n))

    for i, s in enumerate(sp):
        y = top + i * row_h + row_h / 2
        out.append('<path class="ln" d="M%d %d C%d %d,%d %d,%d %d"/>'
                   % (cx0 + cw, cy, cx0 + cw + 60, cy, sx - 60, y, sx, y))
        out.append('<rect x="%d" y="%d" width="%d" height="46" rx="8" fill="#f4efe3"'
                   ' stroke="#d9d0bd"/>' % (sx, y - 23, sw))
        out.append('<rect x="%d" y="%d" width="5" height="46" rx="2.5" fill="#8a9b6e"/>'
                   % (sx, y - 23))
        out.append('<text class="t1" x="%d" y="%d">%s %s</text>'
                   % (sx + 16, y - 4, E(s["id"]), E(s["label"][:10])))
        out.append('<text class="t3" x="%d" y="%d">%d 章</text>'
                   % (sx + 16, y + 13, len(s["chapters"])))
        out.append('<text class="t2" x="%d" y="%d">%s</text>'
                   % (bx, y - 4, E(s["why"][:26])))
        if len(s["why"]) > 26:
            out.append('<text class="t2" x="%d" y="%d">%s</text>'
                       % (bx, y + 12, E(s["why"][26:52])))
        out.append('<path class="ln" d="M%d %d L%d %d"/>' % (sx + sw, y, bx - 14, y))
    out.append("</svg>")
    return "\n".join(out)


def render(d: dict) -> str:
    sp = d["spine"]
    chs = d["chapters"]
    by_id = {}
    for c in chs:
        by_id.setdefault(c["spine"], []).append(c)
    density = d["evidence"]["density"]
    bar = int(round(density * 100))

    body = []
    body.append('<section class="mm-thesis">')
    body.append('<p class="mm-kicker">THIS BOOK ARGUES</p>')
    body.append('<p class="mm-claim">%s</p>' % E(d["thesis"]["claim"] or "（未生成）"))
    if d["thesis"]["boundary"]:
        body.append('<p class="mm-bound"><b>边界</b> %s</p>' % E(d["thesis"]["boundary"]))
    body.append('<p class="mm-evi">证据密度 <b>%d%%</b> · %d 条要点中 %d 条带原句 '
                '（结构由 AI 大纲条目重算，非读后感）</p>'
                % (bar, d["evidence"]["points"], d["evidence"]["with_quote"]))
    body.append('<div class="mm-bar"><i style="width:%d%%"></i></div>' % bar)
    body.append('</section>')

    body.append('<section class="mm-svgwrap">%s</section>' % _svg_spine(d))

    for s in sp:
        items = by_id.get(s["id"]) or []
        body.append('<details class="mm-spine"%s>' % (" open" if s is sp[0] else ""))
        body.append('<summary><span class="mm-id">%s</span>'
                    '<span class="mm-label">%s</span>'
                    '<span class="mm-cnt">%d 章</span></summary>'
                    % (E(s["id"]), E(s["label"]), len(items)))
        body.append('<p class="mm-why">%s</p>' % E(s["why"]))
        body.append('<ol class="mm-tree">')
        for c in items:
            chips = "".join('<span class="mm-chip">%s</span>' % E(x) for x in c["concepts"])
            quote = ('<span class="mm-anchor">「%s」</span>' % E(c["anchor"])) if c["anchor"] else ""
            body.append('<li class="%s"><p class="mm-ch"><b>%d</b> %s'
                        '<span class="mm-role %s">%s</span></p>'
                        '<p class="mm-gist">%s</p>%s%s</li>'
                        % (ROLE_CLS.get(c["role"], "r-th"), c["no"], E(c["title"]),
                           ROLE_CLS.get(c["role"], "r-th"), E(c["role"]),
                           E(c["gist"]), chips, quote))
        body.append('</ol>')
        body.append('</details>')

    html = PAGE % {
        "title": E(d["title"]),
        "slug": E(d["slug"]),
        "body": "\n".join(body),
        "n": len(chs),
        "bad": len(d["bad_anchor"]),
    }
    return html


def _digest(ctx, cut=42, max_ch=0):
    """紧凑摘要：章号 + 标题 + 首条要点。给人（或另一个模型）读的最小充分输入。"""
    out = ["《%s》%d 章" % (ctx["title"], len(ctx["chapters"]))]
    for c in ctx["chapters"][:max_ch or None]:
        out.append("%d. %s | %s" % (c["no"], c["title"], c["brief"][:cut]))
    return "\n".join(out)


def first_anchor(c: dict) -> str:
    """章内第一句原句（没有原句时用首条要点），保证逐字来自大纲。"""
    for q in c["quotes"]:
        if q and len(q) >= 6:
            return q[:60]
    pool = c["anchor_pool"]
    return (pool[0][:60] if pool else "")


def from_batch(slug: str, raw: dict, ctx: dict):
    """把人工/模型给出的 {thesis, spine, chapters:[{no,role,gist}]} 补全为完整结果。

    anchor 一律由脚本从该书原句里取（拒绝编造），evidence 由数据库算。
    """
    chs = ctx["chapters"]
    by_no = {c["no"]: c for c in chs}
    owner = {}
    for s in raw.get("spine") or []:
        for no in s.get("chapters") or []:
            try:
                owner[int(no)] = s["id"]
            except Exception:
                pass
    given = {int(c["no"]): c for c in (raw.get("chapters") or [])
             if str(c.get("no", "")).strip().isdigit()}
    last = (raw.get("spine") or [{}])[0].get("id", "A")
    out_ch = []
    for c in chs:
        g = given.get(c["no"]) or {}
        role = (g.get("role") or "").strip()
        if role not in ("铺垫", "立论", "反证", "案例", "收束"):
            role = "立论"
        gist = (g.get("gist") or "").strip() or (c["brief"][:40] or "(未生成)")
        sp = owner.get(c["no"], last)
        last = sp
        out_ch.append({
            "no": c["no"], "title": c["title"], "spine": sp,
            "gist": gist, "role": role,
            "concepts": [x for x in (g.get("concepts") or []) if x][:4],
            "anchor": first_anchor(c), "anchor_ok": True,
            "pts": c["pts"], "with_q": c["with_q"],
        })
    pts = sum(c["pts"] for c in out_ch)
    wq = sum(c["with_q"] for c in out_ch)
    th = raw.get("thesis") or {}
    return {
        "slug": slug, "title": ctx["title"],
        "thesis": {"claim": (th.get("claim") or "").strip(),
                   "boundary": (th.get("boundary") or "").strip()},
        "spine": [{"id": s["id"], "label": (s.get("label") or "").strip(),
                   "why": (s.get("why") or "").strip(),
                   "chapters": [c["no"] for c in out_ch if c["spine"] == s["id"]]}
                  for s in (raw.get("spine") or [])
                  if [c["no"] for c in out_ch if c["spine"] == s["id"]]],
        "chapters": out_ch,
        "evidence": {"points": pts, "with_quote": wq,
                     "density": round(wq / pts, 3) if pts else 0.0},
        "bad_anchor": [],
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "source": raw.get("_by") or "manual-llm",
    }


PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="《%(title)s》全书主干导图 · 章节定位 · 跨章张力（由 AI 大纲条目结构化重算）">
<title>《%(title)s》｜全书导图</title>
<link rel="stylesheet" href="../../../assets/css/reading-overview.css">
<style>
.mm-wrap{max-width:1120px}
.mm-kicker{font-size:.7rem;letter-spacing:.18em;color:var(--muted);margin:0 0 .3em}
.mm-claim{font-size:1.16rem;line-height:1.75;margin:.1em 0 .5em;color:var(--ink)}
.mm-bound{font-size:.86rem;color:#5c5347;line-height:1.8;margin:.2em 0}
.mm-evi{font-size:.76rem;color:var(--muted);margin:.6em 0 .3em}
.mm-bar{height:5px;background:#e6dfcf;border-radius:3px;overflow:hidden;margin-bottom:1.2em}
.mm-bar i{display:block;height:100%%;background:linear-gradient(90deg,#8a9b6e,#c2b280)}
.mm-svgwrap{overflow-x:auto;padding:.4em 0 1em;border-bottom:1px solid var(--line)}
.mm-svg{width:100%%;height:auto;min-width:760px}
.mm-spine{margin:.9em 0;border-left:3px solid #d9d0bd;padding:.1em 0 .1em .9em}
.mm-spine[open]{border-left-color:#8a9b6e}
.mm-spine>summary{display:flex;gap:.6em;align-items:baseline;cursor:pointer;
  list-style:none;padding:.35em 0}
.mm-spine>summary::-webkit-details-marker{display:none}
.mm-id{font-family:Georgia,serif;font-size:.8rem;color:#8a9b6e;border:1px solid #cfd8bd;
  border-radius:4px;padding:0 .35em}
.mm-label{font-weight:600;font-size:1rem;color:var(--ink)}
.mm-cnt{margin-left:auto;font-size:.74rem;color:var(--muted)}
.mm-why{font-size:.8rem;color:var(--muted);margin:.1em 0 .8em;line-height:1.7}
.mm-tree{list-style:none;padding:0;margin:0}
.mm-tree li{position:relative;padding:.42em 0 .42em 1.1em;border-left:1px dotted #cfc6b4;
  margin-left:.5em}
.mm-tree li:before{content:"";position:absolute;left:0;top:1.05em;width:.7em;
  border-top:1px dotted #cfc6b4}
.mm-ch{margin:0;font-size:.92rem;color:var(--ink)}
.mm-ch b{color:#a9a08d;font-weight:500;font-size:.8rem;margin-right:.4em}
.mm-role{font-size:.68rem;padding:.05em .4em;border-radius:3px;margin-left:.5em;
  vertical-align:.1em;white-space:nowrap}
.r-pre{background:#eef0e6;color:#6b7a4e}.r-th{background:#eae7f0;color:#5f5578}
.r-cnt{background:#f6e9e4;color:#946350}.r-case{background:#e8eff1;color:#4f7380}
.r-end{background:#f2ecdf;color:#8a7442}
.mm-gist{margin:.18em 0 .3em;font-size:.84rem;line-height:1.75;color:#4a443b}
.mm-chip{display:inline-block;font-size:.68rem;color:#6b6152;background:#f2ecdf;
  border-radius:9px;padding:.05em .5em;margin:.15em .25em .15em 0}
.mm-anchor{display:block;font-size:.78rem;color:#8a8272;line-height:1.7;
  border-left:2px dotted #d9d0bd;padding-left:.7em;margin-top:.3em}
@media(max-width:720px){.mm-svg{min-width:640px}}
</style>
</head>
<body>
<main class="wrap mm-wrap">
<header class="note-head">
  <p class="eyebrow">MIND MAP · AFTER THINKING</p>
  <h1>《%(title)s》全书导图</h1>
  <p class="meta">%(n)d 章 · 主干重排 · 章节功能定位 · 由本书 AI 大纲条目重算</p>
  <p class="links"><a href="../../../index.html">← 返回首页</a>
     <a href="../../index.html">阅读归档索引</a>
     <a href="overview.html">全书视角</a>
     <a href="outline.html">AI 大纲</a></p>
</header>
%(body)s
<footer class="site-footer">
  <p class="small">口径：主干由 AI 依章节要点重新归纳，章的功能（铺垫/立论/反证/案例/收束）是结构判断而非原文自述；
  引文逐字来自 AI 大纲的原句摘录，未命中原句的章不标注引文（本次 %(bad)d 处）。</p>
  <p><a href="../../../index.html">← 返回首页</a>　<a href="overview.html">全书视角</a></p>
</footer>
</main>
</body>
</html>
"""


# ------------------------------------------------------------------ 主流程
def run_one(slug: str, write: bool, dry: bool, log=print):
    ctx = build_ctx(slug)
    if not ctx:
        log("  - %-44s 库中无大纲，跳过" % slug[:44])
        return None
    t0 = time.time()
    d, err = refine(ctx, log=log)
    if not d:
        log("  ✗ %-44s %s" % (slug[:44], err))
        return None
    DB_OUT.mkdir(parents=True, exist_ok=True)
    if not dry:
        (DB_OUT / ("%s.json" % slug)).write_text(
            json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    if write:
        html = render(d)
        (BOOKS / slug / "mindmap.html").write_text(html, encoding="utf-8")
    log("  ✓ %-44s 章=%3d 主干=%d 密度=%.0f%% 锚点缺=%d %.0fs"
        % (slug[:44], len(d["chapters"]), len(d["spine"]),
           d["evidence"]["density"] * 100, len(d["bad_anchor"]), time.time() - t0))
    return d


def skip_set():
    """docs/mindmap-skip.txt：不放行做导图的书（一行一个 slug，# 注释）。"""
    p = HERE / "docs" / "mindmap-skip.txt"
    if not p.exists():
        return set()
    out = set()
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.split("#")[0].strip()
        if ln:
            out.add(ln)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--write", action="store_true", help="写 mindmap.html")
    ap.add_argument("--dry-run", action="store_true", help="不落盘")
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--render-only", action="store_true",
                    help="不调 LLM，用 data/mindmap/<slug>.json 重新渲染页面")
    ap.add_argument("--workers", type=int, default=1, help="并发数（网络请求并行）")
    ap.add_argument("--digest", type=int, metavar="N",
                    help="只打印还没生成导图的 N 本书的紧凑摘要（不调 LLM）")
    ap.add_argument("--import-batch", help="导入批量 JSON 并渲染：{slug:{thesis,spine,chapters}}")
    ap.add_argument("--cut", type=int, default=42, help="摘要里每条要点的截断长度")
    a = ap.parse_args(argv)

    if a.import_batch:
        raw = json.loads(Path(a.import_batch).read_text(encoding="utf-8"))
        DB_OUT.mkdir(parents=True, exist_ok=True)
        for slug, item in raw.items():
            ctx = build_ctx(slug)
            if not ctx:
                print("  - %-44s 库中无大纲" % slug[:44])
                continue
            d = from_batch(slug, item, ctx)
            (DB_OUT / ("%s.json" % slug)).write_text(
                json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            if a.write:
                (BOOKS / slug / "mindmap.html").write_text(render(d), encoding="utf-8")
            print("  ✓ %-44s 章=%3d 主干=%d 密度=%.0f%% 锚点缺=%d" % (
                slug[:44], len(d["chapters"]), len(d["spine"]),
                d["evidence"]["density"] * 100, len(d["bad_anchor"])))
        return 0

    if a.import_batch is None and a.digest:
        pool = ([a.slug] if a.slug else
                sorted(p.name for p in BOOKS.iterdir()
                       if p.is_dir() and (p / "overview.html").exists()
                       and not (p / "mindmap.html").exists()))
        got = 0
        for s in pool:
            ctx = build_ctx(s)
            if not ctx:
                continue
            print("=" * 8, s, "=" * 8)
            print(_digest(ctx, cut=a.cut))
            got += 1
            if got >= a.digest:
                break
        print("\n（还有 %d 本无导图）" % len(pool))
        return 0

    if a.slug:
        slugs = [a.slug]
    else:
        slugs = sorted(p.name for p in BOOKS.iterdir()
                       if p.is_dir() and (p / "overview.html").exists())
        if a.skip_existing:
            slugs = [s for s in slugs if not (BOOKS / s / "mindmap.html").exists()]
        _skip = skip_set()
        if _skip:
            slugs = [s for s in slugs if s not in _skip]
        if a.limit:
            slugs = slugs[: a.limit]
    print("待提炼：%d 本" % len(slugs))
    ok = 0
    if a.workers > 1 and not a.render_only:
        import threading
        from concurrent.futures import ThreadPoolExecutor
        lock = threading.Lock()

        def _job(s):
            with lock:                      # 全局 sqlite 连接不能跨线程并发读
                ctx = build_ctx(s)
            if not ctx:
                return None
            d, err = refine(ctx, log=lambda *x: None)
            if not d:
                return ("✗ %s %s" % (s[:40], err))
            DB_OUT.mkdir(parents=True, exist_ok=True)
            (DB_OUT / ("%s.json" % s)).write_text(
                json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            if a.write:
                (BOOKS / s / "mindmap.html").write_text(render(d), encoding="utf-8")
            return ("✓ %-44s 章=%3d 主干=%d 密度=%.0f%% 锚点缺=%d" % (
                s[:44], len(d["chapters"]), len(d["spine"]),
                d["evidence"]["density"] * 100, len(d["bad_anchor"])))

        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            for i, r in enumerate(ex.map(_job, slugs), 1):
                print("[%d/%d] %s" % (i, len(slugs), r or "-"), flush=True)
                if r and r.startswith("✓"):
                    ok += 1
        print("完成 %d / %d" % (ok, len(slugs)))
        return 0

    for i, s in enumerate(slugs, 1):
        print("[%d/%d] %s" % (i, len(slugs), s))
        if a.render_only:
            p = DB_OUT / ("%s.json" % s)
            if not p.exists():
                print("  - 无 JSON，跳过")
                continue
            d = json.loads(p.read_text(encoding="utf-8"))
            (BOOKS / s / "mindmap.html").write_text(render(d), encoding="utf-8")
            ok += 1
            continue
        if run_one(s, a.write, a.dry_run):
            ok += 1
    print("完成 %d / %d" % (ok, len(slugs)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
