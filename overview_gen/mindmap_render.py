# -*- coding: utf-8 -*-
"""mindmap_render.py — 「全书结构与主题关系」区块渲染（读前通读页）。

输入三种来源，输出同一套结构化 HTML（章节折叠树 / 分组要点卡）：

  1. outline.json（最准）：扁平目录条目，level 1=章、2=小节、3=要点、4=原句
  2. 纯文本树（旧 auto 生成）：`├─ 第N章 《…》` + `│   └─ a / b`
  3. 纯文本分组（手写归纳）：`一、xxx` / `《篇名》· 4 节` + `  · 要点…`

为什么不直接 <pre>：纯文本树没有层级颜色、8–51 章挤成一坨、长小节被
48 字截断。结构化后每章一张折叠卡，章号有色块、小节是胶囊，宽屏可读。
"""
from __future__ import annotations

import html
import re

# ---------------------------------------------------------------- 基础工具
CN_DIGITS = {'零': 0, '〇': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4,
             '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
CN_UNITS = {'十': 10, '百': 100, '千': 1000}


WX_RE = re.compile(r'微信读书|微信')


def esc(t: str) -> str:
    # 站内文案规范：不出现第三方平台名（原书章节名里带「微信读书」的，统一写作 AI 读书）
    t = WX_RE.sub(lambda m: 'AI 读书' if m.group(0) == '微信读书' else 'AI', t or '')
    return html.escape(t, quote=False)


def cn2int(s: str) -> int | None:
    """中文数字 → 整数（支持 十一 / 二十三 / 一百零五 / 12）。"""
    s = (s or '').strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    total, cur = 0, 0
    for ch in s:
        if ch in CN_DIGITS:
            cur = CN_DIGITS[ch]
        elif ch in CN_UNITS:
            total += (cur or 1) * CN_UNITS[ch]
            cur = 0
        else:
            return None
    return total + cur


CH_NO_RE = re.compile(r'^第\s*([零〇一二两三四五六七八九十百千\d]+)\s*[章回节篇講讲]\s*$')
NOISE = {'版权信息', '封面', '书名页', '目录', '扉页', '版权页'}


def split_chapter(display: str, idx: int) -> tuple[str, str]:
    """'版权信息 · 第一章 · 罗家明在苏联的投资失败' → ('1', '罗家明在苏联的投资失败')。"""
    raw = (display or '').strip()
    # 只剥完整包裹的书名号：《红楼梦》校注本 → 红楼梦》校注本（strip 会把「红楼梦」前面的《吃掉一半）
    if raw.startswith('《') and raw.endswith('》'):
        raw = raw[1:-1].strip()
    no, name = None, []
    # 「八 · 西洋赶驴子的人」这类用中文序数当章号
    m0 = re.match(r'^([一二三四五六七八九十]{1,3})[\s·・]+(.+)$', raw)
    if m0 and cn2int(m0.group(1)):
        no = cn2int(m0.group(1))
        raw = m0.group(2).strip()
    segs = [s.strip() for s in re.split(r'\s*[·・]\s*', raw) if s.strip()]
    for s in segs:
        m = CH_NO_RE.match(s)
        if m and no is None:
            no = cn2int(m.group(1))
            continue
        if s in NOISE:
            continue
        name.append(s)
    if no is None:
        m = re.match(r'^第\s*([零〇一二两三四五六七八九十百千\d]+)\s*[章回节篇講讲]', raw)
        if m:
            no = cn2int(m.group(1))
    title = ' · '.join(name) or raw
    if len(title) > 60:
        title = title[:58] + '…'
    return str(no if no else idx), title


# ---------------------------------------------------------------- 解析：JSON
def from_outline_json(items: list, title: str = '', author: str = '') -> dict:
    """outline.json 扁平条目 → 章节结构。"""
    chapters, cur_ch, cur_sec = [], None, None
    for it in items:
        lv = it.get('level') or 1
        txt = (it.get('display') if lv == 1 else it.get('text')) or it.get('text') or ''
        txt = txt.strip()
        if not txt:
            continue
        if lv == 1:
            no, name = split_chapter(txt, len(chapters) + 1)
            cur_ch = {'no': no, 'name': name, 'raw': txt, 'subs': [],
                      'pts': 0, 'quotes': 0}
            chapters.append(cur_ch)
            cur_sec = None
        elif lv == 2 and cur_ch is not None:
            cur_sec = {'name': txt, 'pts': 0}
            cur_ch['subs'].append(cur_sec)
        elif lv >= 3 and cur_ch is not None:
            cur_ch['pts'] += 1
            if lv >= 4:
                cur_ch['quotes'] += 1
            if cur_sec is not None and lv == 3:
                cur_sec['pts'] += 1
    return {
        'kind': 'tree', 'title': title, 'by': author,
        'groups': [{'label': '', 'chapters': chapters}],
        'n_pts': sum(c['pts'] for c in chapters),
        'n_quotes': sum(c['quotes'] for c in chapters),
    }


# ---------------------------------------------------------------- 解析：文本树
TREE_CH = re.compile(r'^[├└]\s*─?\s*(第\s*[零〇一二两三四五六七八九十百千\d]+\s*[章回节篇].*)$')
TREE_SUB = re.compile(r'^[│\s]*[├└]\s*─?\s*(.+)$')


def parse_tree(text: str) -> dict:
    """字符树：顶格的 ├/└ 视为一层节点（不一定是「第N章」），缩进/带 │ 的视为子项。"""
    title, chapters = '', []
    for raw in text.replace('\r', '').split('\n'):
        line = raw.rstrip()
        body = line.strip()
        if not body:
            continue
        indent = len(line) - len(line.lstrip(' \u3000\t'))
        head = body[0]
        if head not in '├└│' and not chapters and indent == 0:
            title = body
            continue
        if head in '├└' and indent == 0:
            txt = body.lstrip('├└─ ').strip()
            if CH_NO_RE.match(txt.split(' ')[0]) or re.match(r'^第\s*[零〇一二两三四五六七八九十百千\d]+\s*[章回节篇]', txt):
                no, name = split_chapter(txt, len(chapters) + 1)
            else:
                no, name = str(len(chapters) + 1), txt
            name = re.sub(r'^[一二三四五六七八九十]+\s*[·・]\s*', '', name)  # 「八 · x」→「x」
            if len(name) > 60:
                name = name[:58] + '…'
            chapters.append({'no': no, 'name': name, 'raw': txt, 'subs': [], 'pts': 0, 'quotes': 0})
            continue
        if head in '├└│' and chapters:
            txt = body.lstrip('│├└─ ').strip()
            for one in re.split(r'\s*/\s*', txt):
                one = one.strip()
                if one:
                    chapters[-1]['subs'].append({'name': one, 'pts': 0})
    return {'kind': 'tree', 'title': title, 'by': '',
            'groups': [{'label': '', 'chapters': chapters}], 'n_pts': 0, 'n_quotes': 0}


# ---------------------------------------------------------------- 解析：文本分组
GROUP_RE = re.compile(
    r'^(?:[一二三四五六七八九十]+、|第[一二三四五六七八九十]+[部篇章卷]|《.+?》|译者序|序言|前言|后记|附录|尾声|结语)')
NOTE_RE = re.compile(r'^(注[:：]|说明[:：]|——)')


def parse_flat(text: str) -> dict:
    """自由格式：顶格=分组标题，缩进/带 ├└ 的行=要点（缩进 ≥2 为二级）。

    兼容三类真实写法：
      * 手写分组（一、xxx + "  · 要点 → 要点"）
      * 符号大纲（├─ / └─ 顶格，偶有嵌套）
      * 散文式三五句（无符号、无分组，整体视作要点）
    """
    title, note, blocks = '', '', []
    cur = None
    pending = False
    for raw in text.replace('\r', '').split('\n'):
        line = raw.rstrip()
        s = line.strip()
        if not s:
            pending = False
            continue
        indent = len(line) - len(line.lstrip(' \u3000\t'))
        bullet = s[0] in '├└│·•▪-—'
        body = s.lstrip('├└│·•▪-—─━ ').strip()
        if not body:
            continue
        if not blocks and not title and not bullet and indent == 0 \
                and len(body) <= 40 and not body.endswith(('。', '！')):
            title = body
            continue
        if indent == 0 and not bullet and NOTE_RE.match(s):
            note = s
            continue
        if bullet or indent > 0:
            if cur is None:
                cur = {'label': '', 'points': []}
                blocks.append(cur)
            lvl = 2 if indent >= 3 else 1
            if pending and cur['points']:
                prev = cur['points'][-1][1]
                sep = '' if prev.endswith(('，', '。', '、', '（', '「')) else ' '
                cur['points'][-1] = (cur['points'][-1][0], prev + sep + body)
            else:
                cur['points'].append((lvl, body))
            pending = body.endswith(('→', '、', '，', '；', '·', '/'))
            continue
        cur = {'label': s, 'points': []}
        blocks.append(cur)
    # 只有标题、没有要点 → 整体降级成一组平铺要点
    if blocks and all(not b['points'] for b in blocks):
        pts = [(1, b['label']) for b in blocks]
        blocks = [{'label': '', 'points': pts}]
    if not blocks and title:
        blocks = [{'label': '', 'points': [(1, title)]}]
        title = ''
    return {'kind': 'flat', 'title': title, 'by': '', 'groups': blocks,
            'n_pts': sum(len(g['points']) for g in blocks), 'n_quotes': 0, 'note': note}


def parse_text(text: str) -> dict:
    t = html.unescape(text or '')
    if re.search(r'^[├└]─', t, re.M):
        st = parse_tree(t)
        if st['groups'][0]['chapters']:
            return st
    return parse_flat(t)


# ---------------------------------------------------------------- 渲染
COLORS = (('mm-c1', '#2f6b52', '#eaf2ec'),
          ('mm-c2', '#5f7440', '#eff2e4'),
          ('mm-c3', '#a4693c', '#f8efe3'),
          ('mm-c4', '#466a85', '#eaf0f5'),
          ('mm-c5', '#7a5a7f', '#f4edf5'))

ICON_OPEN = '<svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true"><path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>'


def _meta(st: dict) -> str:
    bits = []
    if st['kind'] == 'tree':
        n_ch = len(st['groups'][0]['chapters'])
        n_sub = sum(len(c['subs']) for c in st['groups'][0]['chapters'])
        bits.append('<b>%d</b> 章' % n_ch)
        if n_sub:
            bits.append('<b>%d</b> 小节' % n_sub)
    if st.get('n_pts'):
        bits.append('<b>%d</b> 条要点' % st['n_pts'])
    if st.get('n_quotes'):
        bits.append('<b>%d</b> 句原句' % st['n_quotes'])
    return ' · '.join(bits)


def _head(st: dict) -> str:
    # 章节树：书名页头已有，这里只报骨架口径，避免与 h1 重复（且部分页 h1 书名被截断）
    t = '全书骨架' if st['kind'] == 'tree' else (esc(st['title']) if st['title'] else '')
    by = esc(st['by']) if st.get('by') else ''
    show_by = bool(by) and by not in t  # 书名行里已带作者时不再重复
    head = '<p class="mm-t">%s%s</p>' % (t, ('<small>%s</small>' % by) if show_by else '')
    meta = _meta(st)
    tools = ''
    if st['kind'] == 'tree':  # 分组要点本来就是全展开的，不需要批量开关
        tools = ('<p class="mm-tools"><button type="button" class="mm-btn" data-mm="open">全部展开</button>'
                 '<button type="button" class="mm-btn" data-mm="close">全部收起</button></p>')
    return ('<div class="mm-top">%s<p class="mm-meta">%s</p></div>%s' % (head, meta, tools))


def _chapter(c: dict, idx: int) -> str:
    cls, fg, bg = COLORS[idx % len(COLORS)]
    name = esc(c['name'])
    subs = c.get('subs') or []
    kinds = []
    if subs:
        kinds.append('%d 小节' % len(subs))
    if c.get('pts'):
        kinds.append('%d 要点' % c['pts'])
    cnt = ' · '.join(kinds)
    body = []
    if subs:
        CAP = 30  # 单章小节过多（网文常见 60+）只列前 30，其余指向大纲页
        li = []
        for s in subs[:CAP]:
            dup = ' mm-dup' if s['name'].strip() == c['name'].strip() else ''
            li.append('<li class="mm-sub%s">%s</li>' % (dup, esc(s['name'])))
        if len(subs) > CAP:
            li.append('<li class="mm-sub mm-more">另 %d 个小节见 AI 大纲页</li>'
                      % (len(subs) - CAP))
        body.append('<ul class="mm-subs">%s</ul>' % ''.join(li))
    if c.get('quotes'):
        body.append('<p class="mm-q"><a href="#quotes">本章含 %d 句原文摘录</a></p>'
                    % c['quotes'])
    if not subs and not c.get('quotes'):
        return _chapter_flat(c, idx)  # 无小节可展开：直接出静态行，别给一个点开是空的箭头
    if not body:
        body.append('<p class="mm-q">本章大纲未提供分层小节。</p>')
    # summary 本身保持 list-item（iOS/Safari 对 display:flex 的 summary 会丢失点击热区），
    # 行内布局交给内层 span.mm-row
    return ('<li class="mm-ch %s"><details><summary><span class="mm-line">'
            '<span class="mm-no">%s</span><span class="mm-name">%s</span>'
            '%s<i class="mm-arw">%s</i></span></summary>'
            '<div class="mm-body">%s</div></details></li>'
            % (cls, esc(c['no']), name,
               ('<span class="mm-cnt">%s</span>' % cnt) if cnt else '',
               ICON_OPEN, ''.join(body)))


def _chapter_flat(c: dict, idx: int) -> str:
    """章数过多 / 无小节可展开：只给章名 + 计数，不做折叠。"""
    cls, fg, bg = COLORS[idx % len(COLORS)]
    n_sub = len(c.get('subs') or [])
    if n_sub:
        cnt = '%d 小节' % n_sub
    elif c.get('pts'):
        cnt = '%d 要点' % c['pts']
    else:
        cnt = ''
    return ('<li class="mm-ch mm-row %s"><span class="mm-no">%s</span>'
            '<span class="mm-name">%s</span>%s</li>'
            % (cls, esc(c['no']), esc(c['name']),
               ('<span class="mm-cnt">%s</span>' % cnt) if cnt else ''))


def _point(p) -> str:
    if isinstance(p, (tuple, list)):
        lvl, txt = p[0], p[1]
    else:
        lvl, txt = 1, p
    cls = ' mm-l2' if lvl and lvl >= 2 else ''
    return '<li class="mm-pt%s">%s</li>' % (cls, esc(txt))


def render(st: dict) -> str:
    out = ['<div class="mm" data-k="%s">' % st['kind'], _head(st)]
    ci = 0
    for gi, g in enumerate(st['groups']):
        cls, fg, bg = COLORS[gi % len(COLORS)]
        if st['kind'] == 'tree':
            chapters = g['chapters']
            # 只有体量真的撑不住（网文动辄上千小节）才降级成静态骨架行；
            # 「点不动」比「页面略大」更劝退，300 章以内一律给可折叠
            n_sub = sum(len(c.get('subs') or []) for c in chapters)
            compact = len(chapters) > 400 or n_sub > 1800
            out.append('<ol class="mm-chs">')
            for c in chapters:
                out.append(_chapter_flat(c, ci) if compact else _chapter(c, ci))
                ci += 1
            out.append('</ol>')
            if compact:
                out.append('<p class="mm-note">章目过多（%d 章 / %d 小节），此处只列骨架；'
                           '逐章小节见本书 AI 大纲页。</p>' % (len(chapters), n_sub))
        else:
            out.append('<section class="mm-group %s">' % cls)
            if g.get('label'):
                out.append('<p class="mm-gl">%s</p>' % esc(g['label']))
            if g.get('points'):
                out.append('<ul class="mm-pts">%s</ul>'
                           % ''.join(_point(p) for p in g['points']))
            out.append('</section>')
    if st.get('note'):
        out.append('<p class="mm-note">%s</p>' % esc(st['note']))
    out.append('</div>')
    return '\n'.join(out)


def render_mindmap(text_or_struct) -> str:
    st = text_or_struct if isinstance(text_or_struct, dict) else parse_text(text_or_struct)
    if not st['groups'] or (st['kind'] == 'tree' and not st['groups'][0]['chapters']):
        return '<p class="mm-empty">%s</p>' % esc(str(text_or_struct)[:400])
    return render(st)
