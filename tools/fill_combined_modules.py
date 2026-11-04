"""补齐某本书 combined-data.html 的全部领读模块。

站点仓 reading-notes/books/<slug>/combined-data.html 是「全书领读」页的数据层，
按 data-key 分 10 个模块：
    svg / oneline / merged_guide / views / aiask /
    coreask / higher / verify / thennow / quiz

用法：
  # 仅补结构化 4 模块（svg/oneline/merged_guide/views，纯脚本、无 LLM）
  python3 tools/fill_combined_modules.py --slug <slug>
  # 端到端补齐：结构化 4 + 本 Agent 据大纲自动合成的 LLM 6 模块（aiask/coreask/higher/verify/thennow/quiz）
  python3 tools/fill_combined_modules.py --slug <slug> --auto-llm
  # 批量补齐「系列里仅有 AI 大纲」的书（自动锁定目标集，不碰已 9/10 的历史产出）
  python3 tools/fill_combined_modules.py --all --auto-llm
  # 仅看目标清单
  python3 tools/fill_combined_modules.py --all --dry
  # 兼容旧路径：手工 LLM JSON 注入
  python3 tools/fill_combined_modules.py --slug <slug> --llm drafts/<slug>-llm.json
"""
import argparse
import glob as _glob
import html as H
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOKS = ROOT / "reading-notes" / "books"
SYS = ROOT / "reading-notes" / "series"
sys.path.insert(0, str(ROOT / "tools"))
import rebuild_guide_from_outline as rbg  # parse_page / build_section / DEFAULT_STYLE

STRUCT_KEYS = ["svg", "oneline", "merged_guide", "views"]
LLM_KEYS = ["coreask", "higher", "verify", "thennow", "quiz"]
# 标准顺序：svg → oneline → merged_guide → views → aiask → 其余 LLM 模块
ORDER = ["svg", "oneline", "merged_guide", "views", "aiask",
         "coreask", "higher", "verify", "thennow", "quiz"]
STANDARD_ALL = ORDER

GROUP = 7  # 每多少章切一段主干（与 gen_mindmap.structural_batch 默认一致）
FALLBACK_TAG = "（Agent 兜底生成 · 基于大纲、未亲读）"


# ---------------------------------------------------------------- 解析
def chapters_of(slug: str) -> list:
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


READER_TPL = """<!DOCTYPE html>
<html lang="zh-CN" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#15171a">
<title>《{title}》｜全书领读</title>
<script>
/* 防闪：渲染前先把上次保存的主题/字号/段距应用到 <html> */
(function(){{try{{var c=JSON.parse(localStorage.getItem('rd-cfg')||'{{}}'),d=document.documentElement;
d.dataset.theme=c.theme||'dark';
if(c.fs)d.style.setProperty('--fs',c.fs);
if(c.pm)d.style.setProperty('--pm',c.pm);}}catch(e){{}}}})();
</script>
<link rel="stylesheet" href="../../../assets/css/reading-overview.css"><link rel="stylesheet" href="../../../assets/css/mmx-guide.css"><link rel="stylesheet" href="../../../assets/css/reading-outline.css">
<link rel="stylesheet" href="../../../assets/css/reader.css?v=20261106c">
<link rel="stylesheet" href="../../../assets/css/share.css?v=20261104b">
<script src="../../../assets/js/vendor/qrcode.min.js" defer></script>
<script src="../../../assets/js/share.js?v=20261103b" defer></script>
</head>
<body data-slug="{slug}" data-title="{title}">
<div id="rdBar" aria-hidden="true"></div>
{outline_link}<header class="combined-head">
    <h1>《{title}》</h1>
  <div class="chips" id="rdChips"><span class="chip">通读 + 精读</span><span class="chip">AI 自主整理</span><span class="chip">AI 生产</span></div>
</header>
<nav class="nav" id="rdNav" aria-label="章节导航">
  <a class="navlink" href="#mod-svg">结构导图</a>
  <a class="navlink" href="#mod-oneline">核心主旨</a>
  <a class="navlink" href="#mod-merged_guide">AI领读</a>
  <a class="navlink" href="#mod-views">核心观点</a>
  <a class="navlink" href="#mod-aiask">AI 问书</a>
  <a class="navlink" href="#mod-coreask">核心追问</a>
  <a class="navlink" href="#mod-higher">更高维度</a>
  <a class="navlink" href="#mod-verify">阅读验证</a>
  <a class="navlink" href="#mod-thennow">往日今时</a>
  <a class="navlink" href="#mod-quiz">读完自测</a>
</nav>
<main id="rdBody" aria-busy="true">
  <div class="rd-skel" id="rdSkel" aria-hidden="true">
    <section class="rd-skel-card"><h3 class="sk-t">结构导图</h3><div class="sk-fig"></div></section>
    <section class="rd-skel-card"><h3 class="sk-t">核心主旨</h3><div class="sk-l w92"></div><div class="sk-l w68"></div></section>
    <section class="rd-skel-card"><h3 class="sk-t">AI领读</h3><div class="sk-sub"></div><div class="sk-node"></div><div class="sk-node"></div><div class="sk-node"></div></section>
    <section class="rd-skel-card"><h3 class="sk-t">核心观点</h3><div class="sk-l w88"></div><div class="sk-l w94"></div><div class="sk-l w62"></div></section>
    <section class="rd-skel-card"><h3 class="sk-t">AI 问书</h3><div class="sk-q"></div><div class="sk-a"></div><div class="sk-q"></div><div class="sk-a"></div></section>
    <section class="rd-skel-card"><h3 class="sk-t">核心追问</h3><div class="sk-l w86"></div><div class="sk-l w72"></div></section>
    <section class="rd-skel-card"><h3 class="sk-t">更高维度</h3><div class="sk-l w90"></div><div class="sk-l w78"></div></section>
    <section class="rd-skel-card"><h3 class="sk-t">阅读验证</h3><div class="sk-l w88"></div><div class="sk-l w64"></div></section>
    <section class="rd-skel-card"><h3 class="sk-t">往日今时</h3><div class="sk-l w92"></div><div class="sk-l w70"></div></section>
    <section class="rd-skel-card"><h3 class="sk-t">读完自测</h3><div class="sk-l w86"></div><div class="sk-l w76"></div><div class="sk-l w52"></div></section>
  </div>
</main>
<button id="rdFab" aria-label="阅读设置" title="阅读设置">Aa</button>
<div id="rdPanel" hidden>
  <div class="rd-row"><span>字号</span><span class="rd-btns"><button data-rd="fs-">A−</button><button data-rd="fs+">A＋</button></span></div>
  <div class="rd-row"><span>段距</span><span class="rd-btns"><button data-rd="pm-">紧</button><button data-rd="pm0">中</button><button data-rd="pm+">松</button></span></div>
  <div class="rd-row"><span>主题</span><span class="rd-btns"><button data-rd="th-cream">米白</button><button data-rd="th-light">纯白</button><button data-rd="th-green">护眼</button><button data-rd="th-dark">夜间</button></span></div>
</div>
<script>window.goatcounter={{no_onload:true}};</script>
<script data-goatcounter="https://ae6623.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
<script src="../../../assets/js/home-track.js?v=20261102h"></script>
<script src="../../../assets/js/reader.js?v=20261106b"></script>
</body>
</html>
"""


def gen_reader_page(slug: str) -> bool:
    """为缺 combined.html 的书生成 reader 页（reader.js 按 data-slug 同目录 fetch combined-data.html）。

    若同目录存在 outline.html，则在右上角操作区（分享按钮左侧）注入「AI 大纲」入口。
    """
    page = BOOKS / slug / "combined.html"
    if page.exists():
        return False
    meta = meta_of(slug)
    outline_link = ('<a class="ai-outline-link" href="outline.html" title="AI 大纲" '
                    'aria-label="AI 大纲">'
                    '<svg viewBox="0 0 24 24" aria-hidden="true" width="18" height="18" '
                    'fill="none" stroke="currentColor" stroke-width="1.8" '
                    'stroke-linecap="round" stroke-linejoin="round">'
                    '<path d="M8 6h12M8 12h12M8 18h12"/>'
                    '<circle cx="4" cy="6" r="1.1" fill="currentColor" stroke="none"/>'
                    '<circle cx="4" cy="12" r="1.1" fill="currentColor" stroke="none"/>'
                    '<circle cx="4" cy="18" r="1.1" fill="currentColor" stroke="none"/>'
                    '</svg></a>') \
        if (BOOKS / slug / "outline.html").exists() else ""
    page.write_text(
        READER_TPL.format(slug=slug, title=H.escape(meta["title"]), outline_link=outline_link),
        encoding="utf-8")
    return True


def inject_outline_link(slug: str) -> bool:
    """在 outline.html 头部导航行补「AI 问书 →」入口（指向 combined.html），打通模块可达性。"""
    p = BOOKS / slug / "outline.html"
    if not p.exists():
        return False
    t = p.read_text(encoding="utf-8")
    if "combined.html" in t:
        return False
    m = re.search(r'(<p>\s*<a href="\.\./\.\./\.\./index\.html">← 返回首页</a>.+?</p>)', t, re.S)
    if not m:
        return False
    new = m.group(1).replace("</p>", '　<a href="combined.html">AI 问书 →</a></p>')
    t = t[:m.start()] + new + t[m.end():]
    p.write_text(t, encoding="utf-8")
    return True




# ---------------------------------------------------------------- 结构化模块
def build_spine(chs: list, group: int = GROUP) -> list:
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
        # 控制在 2 行内（13 字/行）：首尾章名各留 8 字，节点里不再被切
        why = "「%s」→「%s」" % (first["title"][:10], last["title"][:10])
        spine.append({"id": sid, "label": label,
                      "why": why, "chapters": [c["no"] for c in g]})
    return spine


def render_oneline(chs: list, title: str) -> str:
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


def render_views(chs: list) -> str:
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


def _wrap_cjk(text: str, per: int = 12, max_lines: int = 2) -> list[str]:
    """按字数硬折行（SVG 的 <text> 不会自动换行，超宽就被节点边框切掉）"""
    text = text or ""
    lines = [text[i:i + per] for i in range(0, len(text), per)][:max_lines]
    if len(text) > per * max_lines:
        lines[-1] = lines[-1][:-1] + "…"
    return lines or [""]


def render_svg(chs: list, title: str) -> str:
    spine = build_spine(chs)
    if not spine:
        return ""
    n = len(spine)
    # 宽度按节点数走，不再一律 760：手机端 390 宽时 760 的 viewBox 会缩到 0.5，
    # 节点里的字小到看不清；480 起跳 + 每节点 180 是折中值。
    W = max(480, n * 180)
    HGT = 168
    gap = W / n
    parts = ['<svg class="mmx-svg" viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg"'
             ' preserveAspectRatio="xMinYMin meet" role="img" aria-label="%s 结构导图">'
             % (W, HGT, H.escape(title))]
    parts.append('<style>.mmx-svg text{font-family:"Noto Serif SC",Georgia,serif;fill:#3a342b}'
                '.mmx-svg .rt{font-size:13px;font-weight:600}'
                '.mmx-svg .rc{fill:#fbf7ee;stroke:#d8cdb4;stroke-width:1.4}'
                '.mmx-svg .ln{stroke:#cfc6b4;stroke-width:1.6;fill:none}'
                '.mmx-svg .sm{font-size:10px;fill:#8a8272}</style>')
    cy = HGT / 2
    bw, bh = 156, 86
    xs = [gap * (i + 0.5) for i in range(n)]
    for i, s in enumerate(spine):
        cx = xs[i]
        x0 = cx - bw / 2
        y0 = cy - bh / 2
        parts.append('<rect class="rc" x="%.1f" y="%.1f" width="%d" height="%d" rx="9"/>'
                     % (x0, y0, bw, bh))
        parts.append('<text class="rt" x="%.1f" y="%.1f" text-anchor="middle">%s</text>'
                     % (cx, cy - 14, H.escape(s["label"])))
        # 「首章」/「→末章」拆成两行，按箭头断句，不硬切字
        segs = s["why"].split("→")
        wlines = ([segs[0], "→" + segs[1]] if len(segs) == 2
                  else _wrap_cjk(s["why"], 13, 2))
        for li, line in enumerate(wlines):
            parts.append('<text class="sm" x="%.1f" y="%.1f" text-anchor="middle">%s</text>'
                         % (cx, cy + 6 + li * 15, H.escape(line)))
        if i < n - 1:
            parts.append('<path class="ln" d="M%.1f %.1f L%.1f %.1f"/>'
                         % (x0 + bw, cy, xs[i + 1] - bw / 2, cy))
    parts.append('</svg>')
    return ('<section class="mmx-svgwrap" data-key="svg">'
            '<h2 id="mod-svg" class="sr-only">结构导图</h2>'
            + "".join(parts) + '</section>')


def render_merged(chs: list) -> str:
    return rbg.build_section(rbg.DEFAULT_STYLE, chs)


# ---------------------------------------------------------------- LLM 模块（本 Agent 即 LLM）
def extract_material(chs: list):
    titles = [c.get("title", "") for c in chs]
    per = []
    for c in chs:
        pts, qs = [], []
        for s in c.get("secs", []):
            for p in s.get("points", []):
                if p.get("text"):
                    pts.append(p["text"])
                for q in (p.get("quotes") or []):
                    if q:
                        qs.append(q)
        per.append({"no": c.get("no"), "title": c.get("title", ""), "pts": pts, "quotes": qs})
    return titles, per


def _pick(per: list, n: int):
    """均匀抽取 n 个章索引"""
    if not per:
        return []
    if len(per) <= n:
        return list(range(len(per)))
    step = len(per) / n
    return [int(i * step) for i in range(n)]


def gen_auto_llm(slug: str, chs: list, meta: dict) -> dict:
    """据本书真实大纲（章名/要点/划线）合成 LLM 模块。诚实标注「基于大纲、未亲读」。"""
    title = meta.get("title", slug)
    titles, per = extract_material(chs)
    n = len(chs)
    # ---- aiask：3 个代表章的问答 ----
    aiask = []
    for i in _pick(per, 3):
        ch = per[i]
        q = "《%s》这一章主要讲什么？" % ch["title"]
        a = "第%d章《%s》" % (ch["no"], ch["title"])
        if ch["pts"]:
            a += "，要点集中在：" + "；".join("「%s」" % t for t in ch["pts"][:3])
        if ch["quotes"]:
            a += "。原书有划线如：「%s」" % ch["quotes"][0][:90]
        aiask.append({"q": q, "a": a})
    # ---- coreask：跨章深读追问 ----
    coreask = []
    if n >= 2:
        coreask.append({
            "q": "全书以《%s》开篇、以《%s》收束，作者想用这条线索回应什么核心问题？"
                 % (titles[0], titles[-1]),
            "a": "从章序看，作者把议题从《%s》逐步推进到《%s》，构成一条主线；具体论证落在各章要点里（以下仅据大纲结构梳理，非读后感）。"
                 % (titles[0], titles[-1])
        })
    mids = _pick(per, 3)
    if len(mids) >= 2:
        a, b = titles[mids[0]], titles[mids[-1]]
        coreask.append({
            "q": "《%s》与《%s》这两部分是什么关系？" % (a, b),
            "a": "两者在全书结构中分别承担不同环节：前者铺陈背景，后者推进结论；衔接处的关键论据可在对应章的要点中核对。"
        })
    coreask.append({
        "q": "书中反复出现的张力（如《%s》与《%s》的对照）如何贯穿全书？" % (titles[0], titles[-1]),
        "a": "这条对照线在章序上首尾呼应，是作者组织材料的主轴之一；阅读时建议沿章追踪其演变。"
    })
    # ---- higher：更高维度 ----
    higher = [
        "把《%s》放回它所属的知识脉络里看：全书 %d 章沿着「%s → %s」的主轴展开，作者以结构化的方式把复杂议题拆成可循序进入的段落。"
        % (title, n, titles[0], titles[-1]),
        "读时应区分三类内容：书中明确主张、引用与个案、以及作者自己的综合判断；本页模块只据大纲结构还原脉络，未做外部证据核验。",
        "若想进一步深挖，可沿章末要点追到原书对应章节与参考文献，把「大纲的结构提要」补成「带一手证据的论证」。"
    ]
    # ---- verify：阅读时要验证 ----
    verify = []
    for i in _pick(per, 4):
        ch = per[i]
        if ch["pts"]:
            verify.append("读《%s》时，核对作者关于「%s」的论断：其依据是一手资料、转述还是类比？样本是否具代表性。"
                          % (ch["title"], ch["pts"][0][:40]))
        elif ch["quotes"]:
            verify.append("读《%s》时，确认划线句「%s」的上下文与出处是否如大纲所引。"
                          % (ch["title"], ch["quotes"][0][:40]))
    if not verify:
        verify.append("阅读时留意全书核心论断的证据强度：是来自数据、案例还是推断，分别标注。")
    # ---- thennow：当年与今天 ----
    thennow = []
    for i in _pick(per, 3):
        ch = per[i]
        thennow.append("《%s》讨论的议题，在今日的语境里可能已发生迁移——作者成书时所能掌握的事实与今天并不相同，服用时请区分「当时的结论」与「今天的可用证据」。"
                       % ch["title"])
    if not thennow:
        thennow.append("书中结论多受成书年代限制，今天重读应补上后来的事实与新研究。")
    # ---- quiz：读完自测（不给答案）----
    quiz = []
    for i in _pick(per, 5):
        ch = per[i]
        quiz.append({"q": "用一句话概括《%s》这一章想证明什么？" % ch["title"], "a": ""})
    if not quiz:
        quiz.append({"q": "用一句话概括全书主线。", "a": ""})
    return {"aiask": aiask, "coreask": coreask, "higher": higher,
            "verify": verify, "thennow": thennow, "quiz": quiz}


def render_llm(key: str, data) -> str:
    if key == "aiask":
        items = data if isinstance(data, list) else []
        body = '<div class="mmx-ask">%s</div>' % "".join(
            '<div class="aiqa-item"><h3>%s</h3><p>%s</p></div>'
            % (H.escape(it.get("q", "")), H.escape(it.get("a", ""))) for it in items)
        return _mmx(key, "微信读书 · AI 问书（自主整理）",
                    "非微信读书「AI 问书」原文；由本 Agent 据本书 AI 大纲与热门划线自主整理、未亲读原书。", body)
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
            '<div class="aiqa-item"><h3>%s</h3><p class="quiz-blank">（合上书本自测，不在此给答案）</p></div>'
            % H.escape(it.get("q", "")) for it in items)
        return ('<section class="card quiz-card" data-key="quiz">'
                '<h2 id="quiz">读完自测</h2>'
                '<p class="mmx-mod-note">基于本书 AI 大纲与热门划线原文的自测追问，不编答案。%s</p>%s</section>'
                % (FALLBACK_TAG, body))
    # higher / verify / thennow：段落或列表
    paras = data if isinstance(data, list) else []
    if paras and all(isinstance(x, str) for x in paras):
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


def series_targets() -> list:
    """系列页引用、且需要补齐领读落地页的书 = 任务③目标集。
    判定：有 outline.html，且（无 combined-data.html）或（有 data 但缺 combined.html reader 页）。
    严格排除已含 reader 页的历史产出（「历史已产出的不用动」）。"""
    slugs = set()
    for sp in _glob.glob(str(SYS / "*" / "index.html")):
        txt = open(sp, encoding="utf-8").read()
        for s in re.findall(r'\.\./\.\./books/([a-z0-9\-]+)/', txt):
            slugs.add(s)
    targets = []
    for s in sorted(slugs):
        d = BOOKS / s
        if not (d / "outline.html").exists():
            continue
        if not (d / "combined-data.html").exists():
            targets.append(s)
            continue
        if not (d / "combined.html").exists():
            targets.append(s)          # 已补数据但缺 reader 页（本次主目标）
    return targets


def assemble(slug: str, struct: bool, llm_data: dict | None, auto_llm: bool = False) -> int:
    page = BOOKS / slug / "combined-data.html"
    if not page.exists():
        # 自动创建骨架（含 META），供后续填充
        meta = meta_of(slug)
        page.write_text("<!--META %s-->\n" % json.dumps(
            {"slug": slug, "title": meta.get("title", slug)}, ensure_ascii=False), encoding="utf-8")
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

    if auto_llm:
        llm_data = gen_auto_llm(slug, chs, meta)

    if llm_data:
        for k in LLM_KEYS + ["aiask"]:
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
    ap.add_argument("--all", action="store_true", help="批量补齐系列里仅有 AI 大纲的书")
    ap.add_argument("--llm", help="Agent 兜底的 LLM 模块 JSON（coreask/higher/verify/thennow/quiz）")
    ap.add_argument("--auto-llm", action="store_true", help="用大纲自动合成 LLM 模块（本 Agent 即 LLM）")
    ap.add_argument("--only", help="只补这些模块（逗号分隔，如 quiz），用大纲自动合成，不动其它模块")
    ap.add_argument("--dry", action="store_true", help="只打印目标，不执行")
    a = ap.parse_args()

    if a.all:
        targets = series_targets()
    elif a.slug:
        targets = [a.slug]
    else:
        ap.print_help()
        return 1

    if a.dry:
        print("目标 %d 本（系列里仅有 AI 大纲）：" % len(targets))
        for t in targets:
            print("  ", t)
        return 0

    only = {x.strip() for x in (a.only or "").split(",") if x.strip()}
    auto = bool(a.all or a.auto_llm or only)
    if a.llm:
        llm_data = json.loads(Path(a.llm).read_text(encoding="utf-8"))
        struct = False  # 手动 --llm 只注入 LLM 模块
    elif only:
        llm_data = None            # 逐本现算，见下
        struct = False
    else:
        llm_data = None
        struct = True
    ok = 0
    for slug in targets:
        ld = llm_data
        if only:
            chs = chapters_of(slug)
            full = gen_auto_llm(slug, chs, meta_of(slug)) if chs else {}
            ld = {k: v for k, v in full.items() if k in only}
        rc = assemble(slug, struct=struct, llm_data=ld, auto_llm=False)
        if rc == 0:
            gen_reader_page(slug)
            inject_outline_link(slug)
        ok += (0 if rc == 0 else 1)
    print("完成：成功 %d / %d（已补 combined.html + outline 入口）" % (len(targets) - ok, len(targets)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
