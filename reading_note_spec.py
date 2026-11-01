# -*- coding: utf-8 -*-
"""阅读笔记页模板的单一真源（single source of truth）。

为什么有这个文件
----------------
精读页章节名、通读页反思题、AI 出题默认题面原先硬编码在三个生成器里：

    gen_mindmap.py                  -> mmx-name 直出 c["title"]
    overview_gen/build_overview.py  -> <h2>读完自测 3 问</h2>（两处）
    overview_gen/auto.py            -> 默认题面「大纲共列出多少章节条目」那套

改一处漏两处，于是每轮都要再手工回填一遍已发布页面——打补丁。

本模块把这三种模板收敛到一处。**模板文本的改动 MUST 只改本文件**，
三个生成器一律从这里取，不再内联。

设计约束
--------
1. 只依赖标准库 re，不引第三方、不做包内相对 import——保证任何运行位置
   （云端 weread_daily、本机 gen_mindmap --render-only、沙箱 produce_all）
   都能直接 ``import reading_note_spec``。
2. 不提供 try/except 式静默降级。导入失败就让它报错：一旦降级成"文件内
   再存一份默认值"，就等于又回到两处真源，本文件也就失去意义了。
"""
from __future__ import annotations

import re

__all__ = [
    "REFLECT_TITLE",
    "REFLECT_QUESTIONS",
    "REFLECT_NOTE",
    "reflect_questions_html",
    "is_placeholder_title",
    "chapter_title",
    "TITLE_MAX_CHARS",
]

# ---------------------------------------------------------------- 反思题（全书思考）

#: 反思题区块的标题。旧名「读完自测 3 问」已废弃——不再有"读完/未读完"这个卡点，
#: 开读即产全套笔记，题面也不再是对当天进度的自测。
REFLECT_TITLE = "全书思考 3 问"

#: 高维通用三问。口径：指向全书主旨、论证结构、个人迁移。
#: 明确排除章节条目级 / 版面元信息级的问法（"大纲共列出多少条目""第一章最让你
#: 意外的是什么""合上本页能否讲清"这类），那种题读来无增益。
REFLECT_QUESTIONS = [
    "本书真正要解决的「真问题」是什么？作者为什么认为它重要、又为什么难解？",
    "如果用一句话概括全书的核心主张，你会怎么讲？支撑它的最强证据与最薄弱的一环分别在哪里？",
    "读罢全书，哪三个观念最值得带进你自己的决策或生活？它们会如何改变你的行为？",
]

#: 题面下方的说明。强调这是自省题，不是让 AI 代答。
REFLECT_NOTE = (
    "这是读后自省题：不依赖 AI 代答，指向全书主旨、论证结构与个人迁移，"
    "而非单章条目。"
)


def reflect_questions_html() -> str:
    """把 REFLECT_QUESTIONS 渲染成 ``<li>…</li>`` 串（供直接拼进 ``<ol>``）。

    生成器拼 ``<ol>%s</ol>`` 时用这个，避免各自再写一遍循环。
    """
    import html as _html

    return "".join("<li>%s</li>" % _html.escape(q, quote=False)
                   for q in REFLECT_QUESTIONS)


# ---------------------------------------------------------------- 章节标题派生

#: 派生标题的最大长度。折叠态只有一行，过长会撑破布局。
TITLE_MAX_CHARS = 40

#: 纯序号章名：数字或中文数字 + 可选量词。**全串匹配**，不做包含判断——
#: 「第一节 童年的记忆」这种有真实内容的标题不能被误判。
_SEQ_ONLY_RE = re.compile(
    r"^\s*(?:第\s*)?[零〇一二两三四五六七八九十百千\d]+\s*[章回节篇部卷集]?\s*$"
)

#: 渲染器自身产生的 fallback 文案，不能拿来当章名。
_RENDER_FALLBACKS = frozenset({
    "本节要点", "本节要点：", "未命名", "未命名章节", "无标题", "-", "—", "…", "...",
})


def _norm(v) -> str:
    return (v if isinstance(v, str) else ("" if v is None else str(v))).strip()


def is_placeholder_title(title) -> bool:
    """判断章名是否为占位（空 / 纯序号 / 渲染 fallback），是则说明需要派生。

    >>> is_placeholder_title("一"), is_placeholder_title("第三章")
    (True, True)
    >>> is_placeholder_title("一 老大哥"), is_placeholder_title('')
    (False, True)
    """
    t = _norm(title)
    if not t:
        return True
    if t in _RENDER_FALLBACKS:
        return True
    return bool(_SEQ_ONLY_RE.match(t))


def _secs_of(c: dict, full: dict) -> list:
    """取该章的小节列表：优先章节自带 secs，其次 full[no].secs。"""
    if isinstance(c, dict) and c.get("secs"):
        return c["secs"] or []
    if isinstance(full, dict):
        f = full.get(c.get("no")) if isinstance(c, dict) else None
        if isinstance(f, dict) and f.get("secs"):
            return f["secs"] or []
    return []


def _pt_text(p) -> str:
    if isinstance(p, dict):
        return _norm(p.get("text"))
    return _norm(p)


def chapter_title(c: dict, full: dict = None) -> str:
    """章的展示标题。占位名按「首小节名 → 首要点 → 锚点原句 → 第N章」派生。

    参数
    ----
    c    : 章节 dict，至少含 ``no`` / ``title``；可能自带 ``secs`` / ``anchor``
    full : 章号 -> 该章详情的映射（``{no: {"secs": [...]}}``），可为 None

    派生结果统一截断到 ``TITLE_MAX_CHARS``，并跳过派生链上的占位名
    （例如某章首小节标题本身为空、或被渲染成「本节要点」）。
    """
    full = full or {}
    raw = _norm(c.get("title")) if isinstance(c, dict) else _norm(c)
    if not is_placeholder_title(raw):
        return raw

    secs = _secs_of(c, full)

    # 1) 首个小节的标题
    for s in secs:
        h = _norm((s or {}).get("h")) if isinstance(s, dict) else ""
        if h and not is_placeholder_title(h):
            return h[:TITLE_MAX_CHARS]

    # 2) 首个要点的正文
    for s in secs:
        pts = (s or {}).get("points") if isinstance(s, dict) else None
        for p in (pts or []):
            t = _pt_text(p)
            if t and not is_placeholder_title(t):
                return t[:TITLE_MAX_CHARS]

    # 3) 本章锚点原句
    a = _norm(c.get("anchor")) if isinstance(c, dict) else ""
    if a and not is_placeholder_title(a):
        return a[:TITLE_MAX_CHARS]

    # 4) 兜底：至少给个可读标识，不能是裸序号或空
    no = c.get("no") if isinstance(c, dict) else None
    return ("第%s章" % no) if no else (_norm(raw) or "未命名章节")
