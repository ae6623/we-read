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
# 2026-10-28：gemini-3.5-flash 等主力模型免费额度按项目共享，跑几本就整批 429；
# lite 系列是独立额度。按此顺序轮询，前一个 429 就换下一个，避免整批中断。
# 顺序原则：先质量后数量。gemini-3-flash-preview 能出但额度极小（实测 5 次即尽）。
CANDIDATES = (
    "gemini-3.5-flash",          # 配额恢复时最好，通常是第一个 429 的
    "gemini-3-flash-preview",    # 完整 flash，额度小
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite",
    "gemma-4-26b-a4b-it",        # 兜底，质量差但几乎不限
)
BATCH = 80

# 已确认耗尽的模型（本进程内不再试，省掉 429 往返）
_DEAD = set()

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
            # 整章小节/要点/原句原样带下去：页面上的「不损失内容」靠它，
            # 不能只留 brief —— brief 是给模型看的压缩摘要，人读会嫌少。
            "secs": c["secs"],
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


def _model_chain():
    """可用模型顺序：--model 指定的优先，其余按 CANDIDATES 补；跳过已耗尽的。"""
    head = [MODEL] if MODEL else []
    return [m for m in (head + list(CANDIDATES)) if m not in _DEAD] or list(CANDIDATES)


def llm(prompt: str, max_tokens: int = 4096, retry: int = 1):
    """按模型链轮询。429/404/500 视为该模型不可用 → 立刻换下一个；
       只有「模型通了但 JSON 不合规」才在同一模型上重试。"""
    import gemini_client as gc
    errs = []
    for m in _model_chain():
        for k in range(retry + 1):
            try:
                r = gc.generate(prompt, system=SYSTEM, model=m, timeout=180,
                                max_tokens=max_tokens, temperature=0.35,
                                fallback=False)
            except Exception as e:            # 网络抖动
                r = {"ok": False, "error": "EXC " + str(e)[:120]}
            if r.get("ok"):
                d = _json_of(r["text"])
                if d is not None:
                    if m != MODEL:
                        pass                  # 静默降级，调用方看日志里的 model
                    return d, None
                err = "JSON 解析失败：" + (r.get("text") or "")[:120]
                errs.append("%s:%s" % (m, err))
                time.sleep(2)
                continue                       # 同模型重试
            e = str(r.get("error") or "")
            errs.append("%s:%s" % (m, e[:80].replace("\n", " ")))
            if any(c in e for c in ("429", "404", "500", "503", "quota", "exceeded")):
                _DEAD.add(m)                   # 这个模型这批别再试了
            break                              # 换下一个模型
        if all(x in _DEAD for x in CANDIDATES):
            break
    return None, " | ".join(errs[-4:])


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


def _chunks(s: str, per_line: int, max_lines: int = 2) -> list:
    """按字数切行。中文按 1 字 1 位算，够用且可预测。"""
    s = (s or "").strip()
    if not s:
        return [""]
    lines = [s[i:i + per_line] for i in range(0, len(s), per_line)]
    if len(lines) > max_lines:
        keep = lines[:max_lines]
        keep[-1] = keep[-1][:per_line - 1] + "…"
        return keep
    return lines


def _svg_spine(d: dict) -> str:
    """全书主干图：书名 → 5–7 条主干。规模恒定，长书也不会糊。

    行高按最长主干名自适应：主干名（15px）每行 17 字，最多两行，
    不再硬截 10 字（早期版本会把「读前：书信、缘起与读法导引」切成半句）。
    """
    sp = d["spine"]
    n = len(sp)
    LAB = 17                                  # 主干名单行字数（sw 内可容）
    WHY = 30                                  # 右侧说明单行字数
    lab_lines = [_chunks(s["label"], LAB) for s in sp]
    why_lines = [_chunks(s.get("why", ""), WHY) for s in sp]
    two = any(len(x) > 1 for x in lab_lines)
    three = any(len(x) > 2 for x in why_lines) or any(len(x) > 2 for x in lab_lines)
    row_h = 84 if three else (74 if two else 62)
    top = 30
    h = top * 2 + row_h * n + 36
    w = 1120
    cx0, cw = 28, 262
    sx, sw = 400, 292
    bx = 714
    cy = top + (row_h * n) / 2

    out = ['<svg class="mmx-svg" viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg"'
           ' role="img" aria-label="%s 全书精读">' % (w, h, E(d["title"])),
           '<rect x="0" y="0" width="%d" height="%d" fill="none"/>' % (w, h),
           '<style>'
           '.mmx-svg text{font-family:"Noto Serif SC",Georgia,serif}'
           '.mmx-svg .t1{font-size:15px;fill:#2f2a24;font-weight:600}'
           '.mmx-svg .t2{font-size:12px;fill:#5c5347}'
           '.mmx-svg .t3{font-size:10.5px;fill:#8a8272}'
           '.mmx-svg .rt{font-size:13px;fill:#f7f3ea;font-weight:600}'
           '.mmx-svg .ln{stroke:#cfc6b4;stroke-width:1.4;fill:none}'
           '</style>']

    # root：书名最多两行（每行 17 字），下面一行统计
    ti = _chunks(d["title"], 17)
    rh = 34 + 18 * len(ti)
    out.append('<rect x="%d" y="%d" width="%d" height="%d" rx="10" fill="#3d372e"/>'
               % (cx0, cy - rh / 2, cw, rh))
    for k, ln in enumerate(ti):
        out.append('<text class="rt" x="%d" y="%d">%s</text>'
                   % (cx0 + 16, cy - rh / 2 + 24 + k * 18, E(ln)))
    out.append('<text class="t3" x="%d" y="%d" style="fill:#c9c0ae">%d 章 · 主干 %d 条</text>'
               % (cx0 + 16, cy - rh / 2 + 24 + 18 * len(ti) + 2,
                  len(d["chapters"]), n))

    for i, s in enumerate(sp):
        y = top + i * row_h + row_h / 2
        ls = lab_lines[i]
        bh_i = 38 + 17 * len(ls)          # 框高跟着这行的文字行数走，不留空挡
        out.append('<path class="ln" d="M%d %d C%d %d,%d %d,%d %d"/>'
                   % (cx0 + cw, cy, cx0 + cw + 60, cy, sx - 60, y, sx, y))
        out.append('<rect x="%d" y="%d" width="%d" height="%d" rx="8" fill="#f4efe3"'
                   ' stroke="#d9d0bd"/>' % (sx, y - bh_i / 2, sw, bh_i))
        out.append('<rect x="%d" y="%d" width="5" height="%d" rx="2.5" fill="#8a9b6e"/>'
                   % (sx, y - bh_i / 2, bh_i))
        # 文字块整体垂直居中：label 若干行 + 章数一行
        block = 17 * len(ls) + 14
        y0 = y - block / 2 + 13
        for k, ln in enumerate(ls):
            txt = ("%s %s" % (s["id"], ln)) if k == 0 else ln
            out.append('<text class="t1" x="%d" y="%d">%s</text>'
                       % (sx + 16, y0 + k * 17, E(txt)))
        out.append('<text class="t3" x="%d" y="%d">%d 章</text>'
                   % (sx + 16, y0 + 17 * len(ls) + 3, len(s["chapters"])))
        ws = why_lines[i]
        wy = y - (15 * len(ws)) / 2 + 4
        for k, ln in enumerate(ws):
            out.append('<text class="t2" x="%d" y="%d">%s</text>'
                       % (bx, wy + k * 15, E(ln)))
        out.append('<path class="ln" d="M%d %d L%d %d"/>' % (sx + sw, y, bx - 14, y))
    out.append("</svg>")
    return "\n".join(out)


def _chapter_html(c: dict, full: dict) -> str:
    """一章 = 折叠态一行（章号·章名·功能·要点数），展开是「小节 → 要点 → 原句」。

    样式完全自持（mmx- 前缀 + 页面内联 CSS），**不借用** reading-overview.css 里的
    .ch-item/.ch-body/.ch-sec/.ch-secs/.ch-quote —— 那套归通读页，两边共用一套选择器
    会互相牵制。要"看起来像"就照着写一份，不要去碰别人的组件。"""
    f = full.get(c["no"]) or {}
    secs = f.get("secs") or []
    n_pts = sum(len(s["points"]) for s in secs)
    n_q = sum(1 for s in secs for p in s["points"] for q in p["quotes"] if q)
    chips = "".join('<span class="mmx-chip">%s</span>' % E(x) for x in c["concepts"])
    stat = "共 %d 个小节 · %d 条要点 · %d 句原句摘录" % (len(secs), n_pts, n_q)
    out = ['<details class="mmx-cn">'
           '<summary><span class="mmx-no">%d</span>'
           '<span class="mmx-name">%s</span>'
           '<span class="mmx-role">%s</span>'
           '<span class="mmx-pnum">%d 条</span>'
           '<span class="mmx-caret">›</span></summary>'
           '<div class="mmx-body">'
           '<p class="mmx-stat">%s</p>'
           '<p class="mmx-gist">%s</p>%s'
           % (c["no"], E(c["title"]), E(c["role"]), n_pts, stat, E(c["gist"]), chips)]
    for i, s in enumerate(secs):
        out.append('<details class="mmx-sec"%s>'
                   '<summary><span class="mmx-sech">%s</span>'
                   '<span class="mmx-secc">%d 条</span></summary>'
                   '<ol class="mmx-pts">'
                   % (" open" if i == 0 else "", E(s["h"] or "本节要点"),
                      len(s["points"])))
        for p in s["points"]:
            qs = "".join('<li>「%s」</li>' % E(q) for q in p["quotes"] if q)
            out.append('<li><span class="mmx-pt">%s</span>%s</li>'
                       % (E(p["text"]),
                          ('<ul class="mmx-qt">%s</ul>' % qs) if qs else ""))
        out.append('</ol></details>')
    if not secs and c["anchor"]:
        out.append('<p class="mmx-qt mmx-qt1">「%s」</p>' % E(c["anchor"]))
    out.append('</div></details>')
    return "".join(out)


# ── 精读页模块统一开关（2026-10-29）：docs/mindmap-modules.json ──
# enabled=false 的模块在渲染时整体跳过；改配置即对所有书统一生效，无需改页面或逐个编辑。
MODULE_CFG_PATH = HERE / "docs" / "mindmap-modules.json"
MODULE_TEXT_PATH = HERE / "docs" / "mindmap-module-text.json"


def _module_text_cfg() -> dict:
    """模块文案模板：标题 / 说明 / 占位文案，全站共用（改一处即全站生效）。"""
    try:
        return json.loads(MODULE_TEXT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"defaults": {}, "show_pending": False}


_MT = _module_text_cfg()


def _mt(key: str, field: str, default=""):
    v = ((_MT.get("defaults") or {}).get(key) or {}).get(field)
    return default if v is None else v


def _module_enabled_map() -> dict:
    try:
        cfg = json.loads(MODULE_CFG_PATH.read_text(encoding="utf-8"))
        return {x["id"]: bool(x.get("enabled", True)) for x in cfg.get("modules", [])}
    except Exception:
        return {}


_ENABLED_MAP = _module_enabled_map()


def _section_id(html: str):
    m = re.search(r'<section[^>]*\saria-labelledby="([^"]+)"', html)
    return m.group(1) if m else None


def _extra_modules(d: dict) -> str:
    """精读页模块：结构统一、文案取自 JSON。

    三层数据源（改文案不需要动任何 html）：
      1) docs/mindmap-module-text.json  —— 全站共用的标题 / 说明 / 占位文案模板；
      2) data/mindmap/<slug>.json 的 modules 字段 —— 本书专属内容（有就用）；
      3) 结构化重算 —— thesis.claim（主旨）、spine（观点）、book_outline.quote（金句）、
         本书日期笔记（AI 问书）。这三块本来就是数据，不手写。
    任何一层缺失都不报错，降级到下一层；show_pending=false 时没有真实内容的模块整块不渲染。
    """
    mods = d.get("modules") or {}
    out = []

    def sec(key, body):
        title = _mt(key, "title", key)
        note = _mt(key, "note")
        s = ['<section class="mmx-mod" aria-labelledby="%s">' % key,
             '<h2 id="%s">%s</h2>' % (key, E(title))]
        if note:
            s.append('<p class="mmx-mod-note">%s</p>' % E(note))
        s.append(body)
        s.append('</section>')
        return "".join(s)

    def pending(key):
        txt = _mt(key, "pending")
        if not txt or not _MT.get("show_pending", False):
            return None
        return '<div class="mmx-pending">%s</div>' % txt

    def paras(key, key_name="paras"):
        """通用：{"paras": [...]} → <p> 段；{"items": [...]} → <ul>。"""
        m = mods.get(key) or {}
        ps = [x for x in (m.get(key_name) or []) if x]
        if ps:
            return "".join('<p>%s</p>' % E(x) for x in ps)
        items = [x for x in (m.get("items") or []) if x]
        if items:
            return '<ul class="mmx-views">%s</ul>' % "".join(
                '<li>%s</li>' % E(x) for x in items)
        return pending(key)

    # 0) 一句话主旨：本书覆盖 > thesis.claim
    claim = (mods.get("oneline") or "").strip() if isinstance(mods.get("oneline"), str) else ""
    claim = claim or ((d.get("thesis") or {}).get("claim") or "").strip()
    if claim:
        out.append(sec("oneline", '<p class="mmx-oneline">%s</p>' % E(claim)))

    # 1) 核心观点初判：本书覆盖 > spine(label + why)
    items = [x for x in ((mods.get("views") or {}).get("items") or []) if x]
    if not items:
        for s in (d.get("spine") or []):
            label = (s.get("label") or "").strip()
            if not label:
                continue
            why = (s.get("why") or "").strip()
            items.append("<b>%s</b>%s" % (E(label), ("——%s" % E(why)) if why else ""))
    if items:
        out.append(sec("views", '<ul class="mmx-views">%s</ul>' % "".join(
            "<li>%s</li>" % x for x in items)))

    # 2) 原文金句 Top10：本书覆盖 > book_outline.quote（真实原文）
    q = [x for x in ((mods.get("top10") or {}).get("items") or []) if x]
    if not q:
        try:
            import sqlite3
            con = sqlite3.connect(str(HERE / "data" / "we_read.db"))
            seen = set()
            for ch, qt in con.execute(
                    "SELECT chapter, quote FROM book_outline "
                    "WHERE slug=? AND quote IS NOT NULL AND quote!='' "
                    "ORDER BY ch_no, sec_no, point_no, quote_no", (d["slug"],)):
                qt = (qt or "").strip()
                if len(qt) < 15 or qt in seen:
                    continue
                seen.add(qt)
                q.append({"quote": qt, "from": ch or "本书正文"})
                if len(q):
                    if len(q) >= 10:
                        break
            con.close()
        except Exception:
            q = []
    if q:
        lis = []
        for x in q:
            if isinstance(x, dict):
                lis.append('<li><blockquote>「%s」</blockquote><cite>%s</cite></li>'
                           % (E(x.get("quote") or ""), E(x.get("from") or "本书正文")))
            else:
                lis.append('<li><blockquote>「%s」</blockquote></li>' % E(x))
        out.append(sec("top10", '<ol class="mmx-qlist">%s</ol>' % "".join(lis)))

    # 3) AI 问书：本书覆盖 > 本书日期笔记里已有的真实问答 > 占位
    ai = mods.get("aiask") or {}
    pairs = [x for x in (ai.get("pairs") or []) if x]
    if pairs:
        body = "".join(
            '<div class="mmx-qa"><p class="mmx-q">%s</p><p class="mmx-a">%s</p></div>'
            % (E(x.get("q") or ""), E(x.get("a") or "")) for x in pairs)
    else:
        body = ""
        try:
            notes = BOOKS / d["slug"] / "notes"
            if notes.exists():
                for f in sorted(notes.glob("*.html")):
                    html = f.read_text(encoding="utf-8")
                    m = re.search(r"<h2>\s*AI\s*问书\s*</h2>(.*?)(?=<h2>|</section>|</main>|$)",
                                  html, re.S)
                    if m and m.group(1).strip():
                        body = '<div class="mmx-ask">%s</div>' % m.group(1).strip()
                        break
        except Exception:
            body = ""
        if not body:
            body = pending("aiask")
    if body:
        out.append(sec("aiask", body))

    # 4-6) 三个纵深模块：本书 JSON 有内容就渲染，没有就按 show_pending 决定是否留占位
    for key in ("higher", "verify", "thennow"):
        body = paras(key)
        if body:
            out.append(sec(key, body))

    # 7) 来源与证据边界：lede + 固定条目（全站模板），本书可追加 items
    ev_items = list(_mt("evib", "items", []) or []) + list((mods.get("evib") or {}).get("items") or [])
    if ev_items:
        out.append(sec("evib", '<div class="mmx-evib"><p>%s</p><ul>%s</ul></div>'
                       % (_mt("evib", "lede"),
                          "".join("<li>%s</li>" % x for x in ev_items))))

    # 统一开关：enabled=false 的整块跳过（docs/mindmap-modules.json）
    if _ENABLED_MAP:
        out = [s for s in out if _ENABLED_MAP.get(_section_id(s), True)]
    return "\n".join(out)


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
        html = render(d, ctx)
        (BOOKS / slug / "mindmap.html").write_text(html, encoding="utf-8", newline="\n")
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
    ap.add_argument("--model", help="首选模型（失败自动按 CANDIDATES 降级）")
    ap.add_argument("--budget", type=int, default=0,
                    help="秒；跑够就停，留给下次调用（Bash 单条命令有上限）")
    a = ap.parse_args(argv)
    if a.model:
        globals()["MODEL"] = a.model

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
                (BOOKS / slug / "mindmap.html").write_text(
                    render(d, ctx), encoding="utf-8", newline="\n")
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
        if a.all and not a.render_only:
            # 小书先出：单次命令有超时上限，先让短书成批落地
            _sz = {}
            for s in slugs:
                try:
                    _sz[s] = len(S.load_book_outline(s))
                except Exception:
                    _sz[s] = 9999
            slugs.sort(key=lambda s: (_sz.get(s, 9999), s))
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
                (BOOKS / s / "mindmap.html").write_text(render(d, ctx), encoding="utf-8", newline="\n")
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

    _t_start = time.time()
    _left = []
    for i, s in enumerate(slugs, 1):
        if a.budget and (time.time() - _t_start) > a.budget:
            _left = slugs[i - 1:]
            print("⏸ 预算用尽（%ds），本批完成 %d 本，剩 %d 本待下批"
                  % (a.budget, ok, len(_left)))
            break
        print("[%d/%d] %s" % (i, len(slugs), s))
        if a.render_only:
            p = DB_OUT / ("%s.json" % s)
            if not p.exists():
                print("  - 无 JSON，跳过")
                continue
            d = json.loads(p.read_text(encoding="utf-8"))
            (BOOKS / s / "mindmap.html").write_text(render(d, build_ctx(s)),
                                                   encoding="utf-8", newline="\n")
            ok += 1
            continue
        if run_one(s, a.write, a.dry_run):
            ok += 1
    print("完成 %d / %d" % (ok, len(slugs)))
    if _left:
        print("剩余待跑：%d 本（重跑同一命令继续）" % len(_left))
    return 0


if __name__ == "__main__":
    sys.exit(main())
