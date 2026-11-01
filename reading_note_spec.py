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
    "REFLECT_BANK",
    "REFLECT_NOTE",
    "reflect_questions_html",
    "pick_reflect_questions",
    "is_placeholder_title",
    "chapter_title",
    "TITLE_MAX_CHARS",
]

# ---------------------------------------------------------------- 反思题（全书思考）

#: 反思题区块的标题。旧名「读完自测 3 问」已废弃——不再有"读完/未读完"这个卡点，
#: 开读即产全套笔记，题面也不再是对当天进度的自测。
REFLECT_TITLE = "全书思考 3 问"

#: 题库（2026-11-01 用户定调）：24 道通用高维题，每本书按 slug 稳定随机抽 3 题，
#: 不再全站一模一样。口径红线：
#:   · 只出「指向全书主旨/论证/迁移」的题，**禁止**章节条目级、版面元信息级的问法
#:     （"大纲共列出多少条目""第一章最让你意外""合上本页能否讲清"这类）；
#:   · 虚构 / 非虚构都要能答；不依赖 AI 代答。
#: 素材来源：ReadingGroupGuides / book-club 通用题库 + 《如何阅读一本书》四问框架，
#: 由 agent 归纳改写为中文口径。改动题库 MUST 只改本文件，并在 we-read 仓库
#: note-spec/quiz-bank.json 同步一份快照（文档见 note-spec/README.md）。
REFLECT_BANK = [
    # -- 主旨与论证 --
    "本书真正要解决的「真问题」是什么？作者为什么认为它重要、又为什么难解？",
    "如果用一句话概括全书的核心主张，你会怎么讲？支撑它的最强证据与最薄弱的一环分别在哪里？",
    "作者给出的证据里，哪一条最让你信服？哪一条最勉强？为什么？",
    "全书的论证建立在哪些前提上？哪个前提一旦不成立，结论就站不住？",
    "作者在书中最想纠正的一种普遍误解是什么？你以前也这么误解过吗？",
    "如果把全书压缩成一条建议，你会怎么写？它成立的前提条件是什么？",
    # -- 结构与写法 --
    "全书是按什么结构组织的（问题→分析→方案？时间线？案例展开）？这种结构帮你看清了什么，又遮住了什么？",
    "哪一章最该保留、哪一章最可以删掉？说说你的取舍标准。",
    "作者的写作语气（克制、热血、怀疑、笃定）如何影响你对内容的信任度？",
    # -- 概念与洞见 --
    "书里最让你「原来如此」的一个概念或事实是什么？它推翻了你原来的哪个认知？",
    "哪个概念你当时读懂了、现在又讲不清了？试着用自己的话重新讲一遍。",
    "书中有没有一个你不同意的论断？你的反驳理由是什么，作者又会怎么回应你？",
    # -- 个人迁移 --
    "读罢全书，哪三个观念最值得带进你自己的决策或生活？它们会如何改变你的行为？",
    "书里的方法或结论，放到你所处的环境（行业、城市、人生阶段）里还成立吗？需要怎么改造？",
    "如果照着这本书做一件事，一周内能落地的最小行动是什么？",
    "这本书让你想重读自己的哪段经历？现在你会怎么解释它？",
    # -- 对话与延伸 --
    "如果能当面问作者一个问题，你会问什么？猜猜他会怎么答。",
    "这本书和同主题的另一本书（或你已读过的某本）观点哪里一致、哪里打架？",
    "作者如果今天更新这本书，哪一章最可能被推翻或改写？为什么？",
    "把这本书推荐给朋友时，你会怎么用一句话讲清它「好在哪、别指望什么」？",
    # -- 检验与评价 --
    "合上书不翻页，你能把全书脉络讲到一个外行听懂吗？试着写三句话。",
    "读完之后，你对书名的理解和翻开前有什么不同？",
    "这本书的结论有没有时效性？五年后哪些内容会过时、哪些大概率依然成立？",
    "如果只能留一句书中原文，你选哪句？它好在哪里？",
]

#: 兼容旧引用（produce_all 等）：默认仍给经典三问（= 题库前三题）。
REFLECT_QUESTIONS = REFLECT_BANK[:3]

#: 题面下方的说明。强调这是自省题，不是让 AI 代答。
REFLECT_NOTE = (
    "这是读后自省题：不依赖 AI 代答，指向全书主旨、论证结构与个人迁移，"
    "而非单章条目。"
)


def pick_reflect_questions(seed: str = "", n: int = 3) -> list:
    """按 seed（书 slug 或书名）从题库稳定随机抽 n 题。

    用 slug 做种子而不是每次真随机：同一本书重渲染抽到的题不变，
    台账 md5 才不会天天「已变化」；不同种子落到不同题组，全站不再千篇一律。
    """
    import hashlib
    import random
    h = int(hashlib.sha1((seed or "weread").encode("utf-8")).hexdigest(), 16)
    return random.Random(h).sample(REFLECT_BANK, min(n, len(REFLECT_BANK)))


def reflect_questions_html(seed: str = "") -> str:
    """把抽中的反思题渲染成 ``<li>…</li>`` 串（供直接拼进 ``<ol>``）。

    生成器拼 ``<ol>%s</ol>`` 时用这个，避免各自再写一遍循环。
    传 seed（slug/书名）即按书随机抽题；不传则用经典三问（向后兼容）。
    """
    import html as _html

    qs = pick_reflect_questions(seed) if seed else REFLECT_QUESTIONS
    return "".join("<li>%s</li>" % _html.escape(q, quote=False)
                   for q in qs)


# ---------------------------------------------------------------- 章节标题派生

#: 派生标题的最大长度。折叠态只有一行，过长会撑破布局。
TITLE_MAX_CHARS = 40

#: 纯序号章名：数字或中文数字 + 可选量词。**全串匹配**，不做包含判断——
#: 「第一节 童年的记忆」这种有真实内容的标题不能被误判。
_SEQ_ONLY_RE = re.compile(
    r"^\s*(?:第\s*)?[零〇一二两三四五六七八九十百千\d]+\s*[章回节篇部卷集]?\s*$"
)

#: 渲染器/生成器自身产生的文案，不能拿来当章名。
#: 前三项来自渲染器的空小节兜底；后三项来自 produce_all.chapter_blocks 批量造小节——
#: 那是全站统一的模板文案，不是本书真实的小节标题。若不排除，凡章名是「第二章」
#: 这类纯序号的书，每章都会被派生成同一个名字（2026-11-01 线上实测事故）。
_RENDER_FALLBACKS = frozenset({
    "本节要点", "本节要点：", "未命名", "未命名章节", "无标题", "-", "—", "…", "...",
    "读者划得最多的句子", "热门划线", "热门划线原句",
})

#: 统计型文案（「划线 12128 人」）同样不能当章名。
_COUNT_TEXT_RE = re.compile(r"^划线\s*[\d,，]+\s*人$")


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
    if _COUNT_TEXT_RE.match(t):
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
