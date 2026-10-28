#!/usr/bin/env python3
# add_mindmap_modules.py —— 给精读页（mindmap.html）按 outline.html 模块排序补全/重排模块：
#   一句话主旨 · 核心观点初判 · 原文金句 Top10 · AI 问书 · 用更高维度的知识看
#   · 阅读时要验证的问题 · 当年与今天 · 初步对照 · 来源与证据边界
# 设计：纯本地拼装，不调 LLM；从已渲染 mindmap 抽取真实 thesis.claim / spine 派生前两个模块，
# 金句读引擎仓 DB（book_outline.quote），AI 问书复用日期笔记；其余 LLM 模块先占位。
# 注入到 <footer class="site-footer"> 之前，并确保引用 mmx-guide.css。幂等可重跑。
import re, sqlite3, subprocess
from pathlib import Path

SITE = Path('/workspace/we-read')
ENG_DB = Path('/workspace/we-read-auto/data/we_read.db')
BOOKS = SITE / 'reading-notes' / 'books'
MMX_LINK = '<link rel="stylesheet" href="../../../assets/css/mmx-guide.css">'


def esc(s: str) -> str:
    return (s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def online_mindmap_slugs():
    out = subprocess.check_output(
        ["gh", "api", "repos/ae6623/we-read/git/trees/main?recursive=1",
         "--jq", ".tree[].path | select(endswith(\"/mindmap.html\"))"],
        text=True, timeout=90)
    return {p.split("/")[2] for p in out.split() if p.startswith("reading-notes/books/")}


def clean(html: str) -> str:
    return re.sub(r'<[^>]+>', '', html or '').strip()


def extract_claim(html: str) -> str:
    # 兼容新旧渲染：mm-claim（旧线上版）与 mmx-claim（新版 gen_mindmap）
    m = re.search(r'<p class="mmx?-claim">(.*?)</p>', html, re.S)
    return clean(m.group(1)) if m else ""


def extract_views(html: str) -> list:
    views = []
    for blk in re.findall(r'<details class="mmx?-spine".*?</details>', html, re.S):
        lm = re.search(r'class="mmx?-label">(.*?)</span>', blk, re.S)
        wm = re.search(r'class="mmx?-why">(.*?)</p>', blk, re.S)
        label = clean(lm.group(1)) if lm else ""
        why = clean(wm.group(1)) if wm else ""
        if label:
            views.append((label, why))
    return views


def get_quotes(slug, n=10):
    db = sqlite3.connect(str(ENG_DB))
    c = db.cursor()
    seen, res = set(), []
    for ch, q in c.execute(
            "SELECT chapter, quote FROM book_outline "
            "WHERE slug=? AND quote IS NOT NULL AND quote!='' "
            "ORDER BY ch_no, sec_no, point_no, quote_no", (slug,)):
        q = (q or "").strip()
        if len(q) < 15 or q in seen:
            continue
        seen.add(q)
        res.append((ch or "本书正文", q))
        if len(res) >= n:
            break
    return res


def extract_ai_ask(slug):
    notes = BOOKS / slug / 'notes'
    if not notes.exists():
        return None
    for f in sorted(notes.glob('*.html')):
        html = f.read_text(encoding='utf-8')
        m = re.search(r'<h2>\s*AI\s*问书\s*</h2>(.*?)(?=<h2>|</section>|</main>|$)',
                      html, re.S)
        if m and m.group(1).strip():
            return m.group(1).strip()
    return None


def build_mod(slug, claim, views):
    parts = []
    # 0) 一句话主旨
    if claim:
        parts.append(
            '<section class="mmx-mod" aria-labelledby="oneline">'
            '<h2 id="oneline">一句话主旨</h2>'
            '<p class="mmx-oneline">%s</p>'
            '<p class="mmx-mod-note">本页「精读」由 AI 大纲条目结构化重算，'
            '主旨句取自全书命题，非读后感。</p></section>' % esc(claim))
    # 1) 核心观点初判
    if views:
        items = []
        for label, why in views:
            txt = "<b>%s</b>" % esc(label)
            if why:
                txt += "——%s" % esc(why)
            items.append("<li>%s</li>" % txt)
        parts.append(
            '<section class="mmx-mod" aria-labelledby="views">'
            '<h2 id="views">核心观点初判</h2>'
            '<p class="mmx-mod-note">按全书主干分组，归纳各段在论证中的位置'
            '（取自 spine，结构重算，非读后感）。</p>'
            '<ul class="mmx-views">%s</ul></section>' % "".join(items))
    # 2) Top10 原文金句
    quotes = get_quotes(slug)
    if quotes:
        items = "".join(
            '<li><blockquote>「%s」</blockquote><cite>%s</cite></li>'
            % (esc(q), esc(ch)) for ch, q in quotes)
        parts.append(
            '<section class="mmx-mod" aria-labelledby="top10">'
            '<h2 id="top10">原文金句 · 持续积累</h2>'
            '<p class="mmx-mod-note">以下原句取自本书 AI 大纲落库的原文摘录'
            '（book_outline.quote），按大纲顺序节选，非 AI 生成；更多见逐章深读页。</p>'
            '<ol class="mmx-qlist">%s</ol></section>' % items)
    # 3) AI 问书
    ask = extract_ai_ask(slug)
    if ask:
        parts.append(
            '<section class="mmx-mod" aria-labelledby="aiask">'
            '<h2 id="aiask">AI 问书</h2>'
            '<p class="mmx-mod-note">下方内容复用自本书日期笔记中的 AI 问书'
            '（按实读范围生成）；全书级整理将在云端 AI 阅读流程完成后补充。</p>'
            '<div class="mmx-ask">%s</div></section>' % ask)
    else:
        parts.append(
            '<section class="mmx-mod" aria-labelledby="aiask">'
            '<h2 id="aiask">AI 问书</h2>'
            '<div class="mmx-pending">本书 <b>AI 问书</b> 由 AI 读书平台的书籍 AI 生成，'
            '将在云端 AI 阅读流程完读后自动补充到此页。</div></section>')
    # 4) 用更高维度的知识看
    parts.append(
        '<section class="mmx-mod" aria-labelledby="higher">'
        '<h2 id="higher">用更高维度的知识看这本书</h2>'
        '<div class="mmx-pending">此模块由云端 AI 阅读流程在完读后生成：把本书放回知识史与'
        '理论框架中重读，区分书中主张、外部证据与综合分析。当前待补。</div></section>')
    # 5) 阅读时要验证的问题
    parts.append(
        '<section class="mmx-mod" aria-labelledby="verify">'
        '<h2 id="verify">阅读时要验证的问题</h2>'
        '<div class="mmx-pending">此模块由云端 AI 阅读流程在完读后生成：列出读时需核对的'
        '原句、数字与论点（如关键数据出处、个案代表性、类比限度）。当前待补。</div></section>')
    # 6) 当年与今天 · 初步对照
    parts.append(
        '<section class="mmx-mod" aria-labelledby="thennow">'
        '<h2 id="thennow">当年与今天 · 初步对照</h2>'
        '<div class="mmx-pending">此模块由云端 AI 阅读流程在完读后生成：区分作者当年所能'
        '知晓与后来才显现的事实，给出今日可迁移的启发。当前待补。</div></section>')
    # 7) 来源与证据边界
    parts.append(
        '<section class="mmx-mod" aria-labelledby="evib">'
        '<h2 id="evib">来源与证据边界</h2>'
        '<div class="mmx-evib">'
        '<p>本页「精读」由 <b>AI 大模型</b> 对本书 AI 大纲条目做结构化重算'
        '（主干、分组、证据密度），<b>非读后感</b>。</p>'
        '<ul>'
        '<li><b>原文金句</b>：逐字取自全书 AI 大纲落库的原文摘录（book_outline.quote）；</li>'
        '<li><b>AI 问书</b>：复用自本书日期笔记中已有的真实 AI 问答；</li>'
        '<li><b>更高维度 / 阅读验证 / 当年与今天</b>：由云端 AI 阅读流程完读后生成，当前为占位；</li>'
        '<li>归纳与解读均为模型生成，<b>仅供参考</b>，读后请以原书为准。</li>'
        '</ul></div></section>')
    return "\n".join(parts)


def fetch_html(slug):
    """取基准 HTML：优先本地「完整渲染版」（含 .mmx-claim），否则拉线上完整渲染版。
    线上 55 本均为 gen_mindmap 完整渲染（含命题卡与主干 spine），可稳定抽取真实 claim/spine。"""
    fpath = BOOKS / slug / 'mindmap.html'
    if fpath.exists():
        local = fpath.read_text(encoding='utf-8', errors='ignore')
        if 'mmx-claim' in local or 'mm-claim' in local:
            return local, fpath
    path = "reading-notes/books/%s/mindmap.html" % slug
    try:
        online = subprocess.check_output(
            ["gh", "api", "repos/ae6623/we-read/contents/" + path,
             "--header", "Accept: application/vnd.github.raw"],
            text=True, timeout=90)
        if online.strip():
            return online, fpath
    except Exception:
        pass
    if fpath.exists():
        return fpath.read_text(encoding='utf-8', errors='ignore'), fpath
    return None, fpath


def process(slug):
    html, fpath = fetch_html(slug)
    if not html:
        return None, "拉取失败: 无可用 HTML"
    if '<footer class="site-footer">' not in html:
        return None, "无 footer 锚点，跳过"
    claim = extract_claim(html)
    views = extract_views(html)
    mod = build_mod(slug, claim, views)
    # 移除旧模块，按新顺序重排
    pre, sep, post = html.partition('<footer class="site-footer">')
    pre = re.sub(r'\s*<section class="mmx-mod".*?</section>', '', pre, flags=re.S)
    if 'mmx-guide.css' not in pre:
        pre = pre.replace('reading-overview.css">', 'reading-overview.css">\n' + MMX_LINK, 1)
    html = pre.rstrip() + '\n\n' + mod + '\n\n  <footer class="site-footer">' + post
    fpath.parent.mkdir(parents=True, exist_ok=True)
    fpath.write_text(html, encoding='utf-8', newline='\n')
    n = (1 if claim else 0) + (1 if views else 0) + (1 if get_quotes(slug) else 0)
    return fpath, "已重排 %d 模块（含一句话主旨/核心观点）" % (n + 4)


def main():
    slugs = online_mindmap_slugs()
    print("线上精读(mindmap) %d 本" % len(slugs))
    ok = fail = 0
    for s in sorted(slugs):
        fp, msg = process(s)
        if fp and '失败' not in msg:
            ok += 1
        else:
            fail += 1
            print("  ✗", s, msg)
    print("完成：重排 %d · 失败 %d" % (ok, fail))


if __name__ == "__main__":
    main()
