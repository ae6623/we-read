# -*- coding: utf-8 -*-
"""build_overview.py — 读前通读（全书视角）页渲染引擎（we-read-auto / overview_gen）。

把「一本书的 AI 大纲章节结构（parsed.json）+ 人工/AI 撰写的 BOOK 配置」
渲染成 reading-notes/books/<slug>/overview.html。

设计要点：
  * build(cfg, chapters) 是纯函数，不碰文件 IO —— IO 交给 CLI / publish。
  * 输出零内联 <style>：只引用仓库共享样式表 reading-overview.css +
    book-link-drawer.css（frontend-mod 铁律）。
  * 所有 split_* 分卷函数集中在这里；books.py 直接 import 复用。
  * 带模块级状态的 split（zhi / why）在 build 前 reset，保证多次 build 不串状态。

用法（库）：
    from build_overview import build, reset_split_state
    html = build(cfg, chapters)          # chapters = parse_outline() 的返回值

用法（CLI）：见 cli.py
"""
import re
import html

# 共享样式表路径：overview.html 落在 reading-notes/books/<slug>/ 下，
# 相对路径 ../../../assets/css/ 正好是仓库根 assets/css/，与线上站点一致。
CSS_HEAD = '''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="《{title}》全书视角 · 读前通读（由 AI 大纲整理）">
<title>《{title}》｜全书视角（读前通读）</title>
<link rel="stylesheet" href="../../../assets/css/reading-overview.css">
<link rel="stylesheet" href="../../../assets/css/start-here.css">
<link rel="stylesheet" href="../../../assets/css/mmx-guide.css">
<link rel="stylesheet" href="../../../assets/css/book-link-drawer.css">
</head>
<body>
<main class="page">
'''


def esc(t):
    return html.escape(t, quote=False)


def trim(t, n=78):
    t = re.sub(r'\s+', ' ', t).strip()
    if len(t) <= n:
        return t
    cut = t[:n]
    for sep in ('。', '；', '，', '、'):
        i = cut.rfind(sep)
        if i > n * 0.55:
            return cut[:i + 1]
    return cut + '…'


# ---------------------------------------------------------------- 分卷 split
def split_plain(title, idx):
    return (str(idx + 1), title, '全书篇目（AI 大纲顺序）')


def split_copyright(title, idx):
    t = re.sub(r'^版权信息\s*·\s*', '', title)
    bits = [b.strip() for b in t.split('·')]
    no = bits[0] if len(bits) > 1 else str(idx + 1)
    name = bits[-1]
    return (no, name, '全篇（AI 大纲条目；源文件标题带「版权信息」前缀，已去除）')


def split_two_parts(title, idx):
    bits = [b.strip() for b in title.split('·')]
    part = bits[0]
    no = bits[1] if len(bits) > 2 else str(idx + 1)
    name = ' · '.join(bits[2:]) if len(bits) > 2 else bits[-1]
    return (no, name, part)


def split_numbered(title, idx):
    # 解析稿标题形如「1 自律是习惯，不是意志力」，前置「N 」为序号。
    t = title.strip()
    m = re.match(r'^(\d+)\s+(.*)$', t)
    if m:
        return (m.group(1), m.group(2), '全书 50 讲（AI 大纲顺序）')
    return (str(idx + 1), t, '全书 50 讲（AI 大纲顺序）')


def split_moon(title, idx):
    # 解析稿正文条目标题形如「月亮和六便士 · 第一章 · 查尔斯…」。
    bits = [b.strip() for b in title.split('·')]
    if bits[0] == '月亮和六便士' and len(bits) >= 3:
        return (bits[1], bits[2], '正文（月亮与六便士）')
    if bits[0] == '月亮和六便士' and len(bits) == 2:
        return (bits[1], '(本章无副标题)', '正文（月亮与六便士）')
    if title.strip() == '导读':
        return ('导读', '导读', '导读')
    return (str(idx + 1), title, '附录（作者 / 译者）')


_current_part = {"part": None}


def split_chen(title, idx):
    # 标题含「再版说明 / 序X / 第X记 / 原版跋 / 写给微信读书的读者朋友」等。
    t = title.strip()
    if t == '再版说明':
        return ('再版说明', '再版说明', '再版说明')
    if t.startswith('序'):
        p = t.split(' ', 1)
        return (p[0], p[1] if len(p) > 1 else t, '序言')
    if t.startswith('原版跋') or t.startswith('写给微信读书'):
        p = t.split(' ', 1)
        return (p[0], p[1] if len(p) > 1 else t, '附记')
    m = re.match(r'^第[一二三四五六七八九十]+记\s*(.*)$', t)
    if m:
        head = t.split(' ', 1)[0]
        return (head, m.group(1) or t, '正文 · 八记')
    return (str(idx + 1), t, '其他')


_current_part = {"part": None}


def split_zhi(title, idx):
    # 解析稿结构「上篇/下篇 + 第X章 + 第X节 + 结语」。
    # 篇标签本身作为该 part 的首条 ch-item（大纲中上/下篇条目自带内容摘要）。
    t = title.strip()
    if t.startswith('上篇') or t.startswith('下篇'):
        _current_part['part'] = t
        return ('', t, t)
    m = re.match(r'^(第[一二三四五六七八九十]+章)\s*(.*)$', t)
    if m:
        return (m.group(1), m.group(2).strip(), _current_part['part'] or '全书')
    m = re.match(r'^(第[一二三四五六七八九十]+节)\s*(.*)$', t)
    if m:
        return (m.group(1), m.group(2).strip(), _current_part['part'] or '全书')
    if t == '结语':
        return ('结语', '结语', _current_part['part'] or '全书')
    return (str(idx + 1), t, _current_part['part'] or '全书')


_ch_no = {"n": 0}


def split_why(title, idx):
    # 前 18 条只有「第X节」无显式章标题（末条「第七章 文明的未来」）。
    # 每次出现「第一节」即重置并 +1 章号，推断第 1—6 章；末条显式匹配第 7 章。
    t = title.strip()
    m = re.match(r'^第七章\s*(.*)$', t)
    if m:
        _ch_no['n'] = 7
        return ('第七章', m.group(1).strip() or '文明的未来', '第七章 文明的未来')
    m = re.match(r'^第([一二三四五六七八九十]+)节\s*(.*)$', t)
    if m:
        sec = m.group(1)
        if sec == '一':
            _ch_no['n'] += 1
        return (m.group(1) + '节', m.group(2).strip(), '第%d章' % _ch_no['n'])
    return (str(idx + 1), t, '全篇')


def reset_split_state():
    """重置带模块级状态的 split（zhi / why），避免多次 build 串状态。"""
    _current_part["part"] = None
    _ch_no["n"] = 0


# ---------------------------------------------------------------- 渲染
def build(cfg, chapters, aiqa_html="", quiz_answers=None):
    """渲染一本 overview.html 文本。

    cfg      : BOOK 配置 dict（slug/title/author/chip/split/thesis/mindmap/ai/
                                views/action/quiz/memo，可选 head_note）
    chapters : parse_outline() 返回的章节列表
    aiqa_html: 可选，data/ai_qa 快答实录渲染块（无数据传空串则整个区块不出现）
    quiz_answers: 可选，「读完自测 3 问」的 AI 补答列表 [{q,a}]（无补答则不渲染任何提示）
    """
    reset_split_state()
    out = [CSS_HEAD.format(title=cfg['title'])]
    out.append('''<header class="note-head">
  <p class="eyebrow">全书视角</p>
  <h1>《%s》</h1>
  <p class="meta">作者：%s　·　来源：AI 大纲整理　·　共 %d 章</p>
  <div class="chips"><span class="chip">全书视角</span><span class="chip">AI 大纲</span><span class="chip">%s</span></div>
  <p class="small">本页由本书 AI 大纲（章节要点与原文摘录）整理，供全书视角与后续精读对照，<b>不等同于已亲读</b>。%s</p>
</header>
''' % (cfg['title'], cfg['author'], len(chapters), cfg['chip'], cfg.get('head_note', '')))

    # IA-05「从这里开始」导航块（首屏可见；链接按数据可用性，由 auto.py 填 cfg['start_here']）
    out.append(cfg.get('start_here') or '')

    out.append('<section class="card"><h2>一句话主旨</h2>\n<p>%s</p></section>\n' % cfg['thesis'])
    # 「全书结构与主题关系」章节串联块已合并进章节导读（2026-10-28）：
    # 同一批章在三处出现（结构分组/章节导读/AI 大纲），满屏大纲感。
    # 结构分组块删除，cfg['mindmap'] 保留但不再渲染；AI 大纲页继续作为完整版。

    out.append('<section aria-labelledby="chapter-guide-title"><h2 id="chapter-guide-title">章节导读</h2>\n')

    parts = []
    for idx, c in enumerate(chapters):
        no, t, part = cfg['split'](c['title'], idx)
        if not parts or parts[-1][0] != part:
            parts.append([part, []])
        parts[-1][1].append((no, t, c))

    # 章节正文配额：章少的书给足，章多的书收紧，避免单页 DOM 爆炸
    # （与 gen_outline_full.py 的 _quota/budget 保持一致）
    per_ch = 40 if len(chapters) <= 20 else (20 if len(chapters) <= 60 else 8)
    budget, used_total = 500, 0

    for part, items in parts:
        out.append('  <div class="toc-part"><span class="part-label">%s</span>\n' % esc(part))
        for no, t, c in items:
            secs = c.get('secs') or []
            npts = sum(len(s.get('points') or []) for s in secs)
            nq = sum(len(s.get('quotes') or []) for s in secs)
            out.append('''    <details class="mmx-cn"><summary>
        <span class="mmx-no">%s</span><span class="mmx-name">%s</span>
        <span class="badge" data-s="unread">未读</span><span class="mmx-caret">›</span>
      </summary>
      <div class="mmx-body">
''' % (no, esc(t)))
            out.append('        <p class="mmx-stat">共 %d 个小节 · %d 条要点 · %d 句原句摘录</p>\n'
                       % (len(secs), npts, nq))
            cap = min(per_ch, budget - used_total)
            if not secs:
                out.append('        <p class="mmx-empty">本章大纲未提供分层要点。</p>\n')
            elif cap <= 0:
                out.append('        <p class="mmx-more">（要点详见本书 AI 大纲页）</p>\n')
            else:
                shown = 0
                for si, s in enumerate(secs, 1):
                    pts = s.get('points') or []
                    if shown >= cap:
                        out.append('        <p class="mmx-more">（其余 %d 条要点见本书 AI 大纲页）</p>\n'
                                   % (npts - shown))
                        break
                    take = pts[: cap - shown]
                    shown += len(take)
                    qs = [q for q in (s.get('quotes') or []) if 10 <= len(q) <= 200]
                    op = ' open' if (si == 1 or (len(secs) == 1 and not s.get('h'))) else ''
                    out.append('        <details class="mmx-sec"%s><summary>'
                               '<span class="mmx-sech">%s</span><span class="mmx-secc">%d 条</span>'
                               '</summary>\n' % (op, esc(s.get('h') or '本章要点'), len(pts)))
                    out.append('          <ol class="mmx-pts">%s</ol>\n'
                               % ''.join('<li>%s</li>' % esc(trim(p)) for p in take))
                    if qs:
                        out.append('          <ul class="mmx-qt">%s</ul>\n'
                                   % ''.join('「%s」' % esc(trim(q, 92)) for q in qs[:6]))
                    out.append('        </details>\n')
                used_total += shown
            out.append('      </div></details>\n')
        out.append('  </div>\n')
    out.append('</section>\n\n')

    out.append('''<section class="card" aria-labelledby="ai-ask-title"><h2 id="ai-ask-title">AI 问书</h2>
%s
</section>

''' % cfg['ai'])
    if aiqa_html:
        out.append('<section class="aiqa-ov" aria-labelledby="aiqa-real-title">'
                   '<h2 id="aiqa-real-title">AI 问书 · 快答实录</h2>\n'
                   '<p class="small">以下问答来自 AI 读书「AI 问书」对本书的真实提问（全书视角）。</p>\n'
                   '%s</section>\n\n' % aiqa_html)

    out.append('<section class="views"><h2>核心观点初判</h2>\n%s</section>\n\n' % _pretty_views(cfg['views']))
    out.append('<section class="card"><h2>迁移与行动</h2>\n%s</section>\n\n' % cfg['action'])
    out.append('<section class="card quiz-card"><h2>读完自测 3 问</h2>\n<ol>\n%s\n</ol>%s</section>\n\n'
               % (cfg['quiz'], _quiz_answers_html(cfg.get('quiz'), quiz_answers or [])))
    out.append('<section class="card"><h2>复习与记忆复利</h2>\n%s</section>\n\n' % cfg['memo'])
    out.append('<footer class="site-footer"><a href="../../../index.html">← 返回首页</a>　<a href="../../index.html">阅读归档索引</a></footer>\n</main>\n</body>\n</html>\n')
    return ''.join(out)


# ---------------------------------------------------------------- 视图增强
def _pretty_views(views_html):
    """核心观点初判：把 article 内整段 <p> 拆成逐句成行（加粗标签独立成行），
    与 AI 大纲要点条列样式对齐；无法解析时原样返回。"""
    arts = re.findall(r'<article class="card">(.*?)</article>', views_html, re.S)
    if not arts:
        return views_html
    rebuilt = []
    for a in arts:
        m = re.match(r'\s*<h3>(.*?)</h3>\s*<p>(.*)</p>\s*$', a, re.S)
        if not m:
            rebuilt.append('<article class="card v-item">%s</article>' % a)
            continue
        title, body = m.group(1), m.group(2)
        segs = [s.strip() for s in re.split(r'(?=<strong>)', body) if s.strip()]
        lines = ''.join('<p class="v-line">%s</p>' % s for s in segs)
        rebuilt.append('<article class="card v-item"><h3>%s</h3>%s</article>'
                       % (title, lines))
    return '\n'.join(rebuilt)


def _quiz_answers_html(quiz_cfg, answers):
    """读完自测 3 问的 AI 补答区块：按题面模糊配对；无补答时返回空（不渲染任何提示）。"""
    qs = re.findall(r'<li>(.*?)</li>', quiz_cfg or '', re.S)
    if not qs:
        return ''
    def _norm(s):
        return re.sub(r'[\s，。？?！!、「」·：:；;（）()《》]', '', s or '')
    used, pairs = set(), []
    for q in qs:
        nq = _norm(q)
        hit = None
        for idx, it in enumerate(answers):
            if idx in used:
                continue
            na = _norm(it.get('q'))
            if na and (na in nq or nq in na or na[:16] == nq[:16]):
                hit = idx
                break
        if hit is not None:
            used.add(hit)
            pairs.append((q, answers[hit].get('a') or ''))
        else:
            pairs.append((q, None))
    if all(a is None for _, a in pairs):
        return ''
    blocks = ['<div class="quiz-ans"><h3>AI 补答（微信读书 Ai 问书）</h3>']
    for q, a in pairs:
        if a:
            blocks.append('<div class="aiqa-item"><h3>%s</h3><p>%s</p></div>'
                          % (esc(q), esc(a).replace('\n', '<br>')))
    blocks.append('</div>')
    return ''.join(blocks)
