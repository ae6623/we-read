# -*- coding: utf-8 -*-
"""
normalize_oldcards.py — 揪出并修复首页「另一套模板」卡片

背景（2026-11-12 排查）
-----------------------
线上首页混着两代 archive-card：

  标准卡（有封面）：
    <article class="archive-card" ... data-slug="<slug>" data-mode="whole jingdu archive">
      <h3><a class="card-title-link" href=".../overview.html|combined.html">《书名》</a></h3>
      <p>18 章 / 2645 条</p>
      <div class="card-actions" hidden>...</div>
      <div class="card-foot">...</div>

  旧模板卡（无封面、深绿 WE READ 占位）—— 由 we-read-auto/site_pub.py 的
  sync_preread_cards()（写于 2026-10-26，未随规范升级）产出：
    <article class="archive-card" data-ts="..." data-search="...">   ← 没有 data-slug
      <h3>纯文本书名</h3>                                              ← 没有 card-title-link
      <p>10 章 / 304 条　·　读前通读材料，尚未亲读。</p>             ← 重复/规则文案
      <div class="card-actions"> 直接展开 + EPUB 下载 </div>          ← 没有 hidden / card-foot

  为什么没封面：assets/js/home-card.js 的 addCovers() 读 card.dataset.slug，
  拼 /assets/covers/<slug>.jpg；旧卡 slug 为空 → 不生成 <img> → 只剩文字兜底
  占位（深绿底 + 书名 + WE READ）。所以「没封面」不是图片坏了，是模板缺字段。

判定规则（三条命中任一即为旧模板卡）
-----------------------------------
  1. archive-card 且 缺 data-slug
  2. 标题是 <h3>纯文本</h3>（没有 card-title-link / book-jd-link）
  3. 正文含「读前通读材料，尚未亲读」或「共 N 章 / N 条　·　N 章 / N 条」重复文案

排除（本来就不该有封面、不能动）
--------------------------------
  - archive-card-soon（即将上线占位卡，data-search 里带「即将上线」）
  - archive-note（阅读方法说明卡）
  - 没有任何 reading-notes/books/<slug>/ 链接的卡（本地书目 / 汇编说明等）

修复策略（只改模板层，不动书、不动链接、不动日期、不动排序）
------------------------------------------------------------
  从卡片自身的 reading-notes/books/<slug>/ 链接提取 slug，然后：
    - 补 data-slug="<slug>"、data-mode="whole jingdu archive"
    - <h3> → <h3><a class="card-title-link" href="<主页面>">《书名》</a></h3>
      主页面优先 combined.html，其次 overview.html，再次 outline.html
    - 去重复文案：保留「N 章 / M 条」，删「共…·…」「读前通读材料，尚未亲读」
    - card-actions 加 hidden，正文里若已有 card-title-link 主链则不再重复
    - 补标准 card-foot（作者 + 更多菜单），作者从 card-search 兜底取
  幂等：已带 data-slug 的卡一律跳过；重跑零变化。

用法
----
  python3.11 normalize_oldcards.py detect  --file index.html          # 只检测，输出清单
  python3.11 normalize_oldcards.py fix     --file index.html          # 原地修复（自动 .bak）
  python3.11 normalize_oldcards.py fix     --file a.html --out b.html  # 写到新文件
  python3.11 normalize_oldcards.py check   --file index.html          # 门禁：有问题返回退出码 1
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

CARD_RE = re.compile(
    r'(?P<indent>[ \t]*)(?P<mark><!-- preread-card:(?P<tag>[^\s]+) -->\s*)?'
    r'(?P<open><article class="(?P<cls>[^"]*archive-card[^"]*)"(?P<attrs>[^>]*)>)'
    r'(?P<body>.*?)'
    r'(?P<close></article>)(?P<endmark>\s*<!-- /preread-card -->)?',
    re.S,
)

BOOK_HREF_RE = re.compile(r'reading-notes/books/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)')
H3_RE = re.compile(r'(<h3[^>]*>)(.*?)(</h3>)', re.S)
P_RE = re.compile(r'<p[^>]*>(.*?)</p>', re.S)
TIME_RE = re.compile(r'<time[^>]*datetime="([^"]+)"[^>]*>(.*?)</time>', re.S)
TAG_RE = re.compile(r'<span class="type-tag[^"]*">([^<]+)</span>')
AUTHOR_RE = re.compile(r'card-author">([^<]*)<')
ACTIONS_RE = re.compile(r'(<div class="card-actions)([^>]*>)', re.S)

CARD_FOOT = (
    '<div class="card-foot"><span class="card-author"></span>'
    '<button class="card-more" type="button" aria-label="更多操作" '
    'aria-haspopup="true" aria-expanded="false">'
    '<svg viewBox="0 0 24 24" aria-hidden="true"><use href="#ic-9"/></svg></button>'
    '<div class="card-menu" hidden>'
    '<button type="button" data-act="fav">'
    '<svg viewBox="0 0 24 24" aria-hidden="true"><use href="#ic-10"/></svg>'
    '<span>收藏</span></button>'
    '<button type="button" data-act="share">'
    '<svg viewBox="0 0 24 24" aria-hidden="true"><use href="#ic-11"/></svg>'
    '<span>分享</span></button></div></div>'
)


def strip_tags(x: str) -> str:
    return html.unescape(re.sub(r'<[^>]+>', '', x)).strip()


def is_excluded(cls: str, body: str) -> bool:
    if 'archive-card-soon' in cls or 'archive-note' in cls:
        return True
    if '即将上线' in body or '资料收集中' in body:
        return True
    return False


def classify(cls: str, attrs: str, body: str) -> dict:
    """判断一张 archive-card 是否是旧模板卡，并抽取修复所需字段。"""
    if 'archive-card' not in cls:
        return {'old': False}
    if is_excluded(cls, body):
        return {'old': False, 'excluded': True}
    has_slug = 'data-slug=' in attrs
    h3 = H3_RE.search(body)
    h3_inner = h3.group(2) if h3 else ''
    has_title_link = bool(re.search(r'card-title-link|book-jd-link', h3_inner))
    p = P_RE.search(body)
    p_text = strip_tags(p.group(1)) if p else ''
    dup_text = bool(re.search(r'共\s*\d+\s*章.*?·.*?\d+\s*章|读前通读材料|尚未亲读', p_text))

    # 旧模板判定：缺 slug 或 标题纯文本 或 重复/规则文案
    old = (not has_slug) or (not has_title_link) or dup_text
    if not old:
        return {'old': False}

    slugs = BOOK_HREF_RE.findall(body)
    if not slugs:
        # 没有真实书链接 → 说明卡/占位，不动
        return {'old': False, 'excluded': True, 'reason': 'no-book-href'}

    slug = slugs[0][0]
    # 选主链接：combined > overview > outline > 其它
    files = [f for s, f in slugs if s == slug]
    def rank(f):
        for i, k in enumerate(['combined.html', 'overview.html', 'outline.html', 'mindmap.html']):
            if f == k:
                return i
        return 99
    files.sort(key=rank)
    main_file = files[0] if files else 'overview.html'

    title = strip_tags(h3_inner) if h3 else slug.replace('-', ' ')
    # 标题规范：套《》，但别叠两层
    if not (title.startswith('《') and title.endswith('》')):
        disp = '《%s》' % title.strip('《》 ')
    else:
        disp = title

    # 段落文案：只保留干净的「N 章 / M 条」或「N 章」
    m = re.search(r'(\d+\s*章(?:\s*/\s*\d+\s*条)?)', p_text)
    meta = m.group(1) if m else ''

    tm = TIME_RE.search(body)
    date = tm.group(1) if tm else ''
    tags = TAG_RE.findall(body)
    am = AUTHOR_RE.search(body)
    author = am.group(1).strip() if am else ''

    reasons = (
        ('no-slug' if not has_slug else '')
        + ('|plain-h3' if not has_title_link else '')
        + ('|dup-text' if dup_text else '')
    ).strip('|')
    # 只有「文案重复」而结构已标准（有 slug + 有标题链接）→ 只清 <p>，最小改动
    full_upgrade = (not has_slug) or (not has_title_link)
    return {
        'old': True,
        'full_upgrade': full_upgrade,
        'slug': slug,
        'main_href': 'reading-notes/books/%s/%s' % (slug, main_file),
        'disp': disp,
        'title': title,
        'meta': meta,
        'date': date,
        'tags': tags,
        'author': author,
        'reasons': reasons,
    }


def render(m: dict, info: dict, orig_body: str) -> str:
    """用标准模板重排卡片正文，尽量保留原有可用信息。"""
    # 保留原始 card-actions 里的链接（精读/大纲/下载），但加 hidden
    acts = re.search(r'<div class="card-actions"[^>]*>(.*?)</div>', orig_body, re.S)
    acts_inner = acts.group(1).strip() if acts else ''
    # 主链已在标题里，actions 里若指向同一主页可保留（不影响）
    body = []
    top = []
    # type-tag：沿用原有「全书视角 / 读前通读」标签，但升级为「全书视角」更统一？
    # 保守：保留用户能看到的类型标识，避免信息丢失
    for t in info['tags']:
        gold = ' type-tag-gold' if t in ('全书视角', '读前通读') else ''
        top.append('<span class="type-tag%s">%s</span>' % (gold, html.escape(t)))
    if info['date']:
        d = info['date']
        md = d[5:7] + '.' + d[8:10] if len(d) >= 10 else d
        top.append('<time datetime="%s">%s</time>' % (html.escape(d), html.escape(md)))
    body.append('<div class="card-top">%s</div>' % ''.join(top))
    body.append('<h3><a class="card-title-link" href="%s">%s</a></h3>' % (
        html.escape(info['main_href']), html.escape(info['disp'])))
    if info['meta']:
        body.append('<p>%s</p>' % html.escape(info['meta']))
    if acts_inner:
        body.append('<div class="card-actions" hidden>%s</div>' % acts_inner)
    foot = CARD_FOOT
    if info['author']:
        foot = foot.replace('<span class="card-author"></span>',
                            '<span class="card-author">%s</span>' % html.escape(info['author']))
    body.append(foot)
    return '\n        '.join(body)


def process(text: str, mode: str) -> tuple[str, list]:
    found = []
    out = []
    pos = 0
    for m in CARD_RE.finditer(text):
        info = classify(m.group('cls'), m.group('attrs'), m.group('body'))
        if not info.get('old'):
            continue
        found.append({
            'slug': info['slug'], 'title': info['title'],
            'reasons': info['reasons'], 'date': info['date'],
            'main': info['main_href'], 'meta': info['meta'],
        })
    if mode == 'detect':
        return text, found

    # fix：逐个替换（用 re.sub + 回调，保证只动命中的卡）
    def repl(m):
        info = classify(m.group('cls'), m.group('attrs'), m.group('body'))
        if not info.get('old'):
            return m.group(0)
        body = m.group('body')
        if not info['full_upgrade']:
            # 结构已标准，只清理 <p> 里的重复/规则文案，其余逐字节保留
            def clean_p(pm):
                if not re.search(r'共\s*\d+\s*章.*?·|读前通读材料|尚未亲读', strip_tags(pm.group(1))):
                    return pm.group(0)
                meta = info['meta']
                return ('<p>%s</p>' % html.escape(meta)) if meta else ''
            new_body = P_RE.sub(clean_p, body, count=1)
            return m.group(0).replace(body, new_body, 1)

        attrs = m.group('attrs')
        if 'data-slug=' not in attrs:
            attrs = attrs.rstrip() + ' data-slug="%s" data-mode="whole jingdu archive"' % html.escape(info['slug'])
        new_body = '\n        ' + render(m, info, body) + '\n      '
        open_tag = '<article class="%s"%s>' % (m.group('cls'), attrs)
        head = (m.group('indent') + (m.group('mark') or ''))
        tail = (m.group('endmark') or '')
        return head + open_tag + new_body + m.group('close') + tail

    return CARD_RE.sub(repl, text), found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['detect', 'fix', 'check'])
    ap.add_argument('--file', required=True)
    ap.add_argument('--out')
    ap.add_argument('--json')
    a = ap.parse_args()
    src = Path(a.file)
    text = src.read_text(encoding='utf-8', errors='replace')

    if a.cmd == 'detect':
        _, found = process(text, 'detect')
    else:
        new, found = process(text, a.cmd)
        if a.cmd == 'fix':
            out = Path(a.out) if a.out else src
            if out == src:
                src.with_suffix(src.suffix + '.bak').write_text(text, encoding='utf-8')
            out.write_text(new, encoding='utf-8')
            print('已写出:', out, '| 修复', len(found), '张旧卡')
        text = new

    print('旧模板卡总数:', len(found))
    import collections
    print('命中原因:', dict(collections.Counter(f['reasons'] for f in found)))
    print('有干净章数文案:', sum(1 for f in found if f['meta']), '/', len(found))
    if a.json:
        Path(a.json).write_text(json.dumps(found, ensure_ascii=False, indent=1), encoding='utf-8')
        print('清单:', a.json)
    if a.cmd != 'fix':
        for f in found[:20]:
            print('  %-46s %-12s %s' % (f['slug'][:46], f['date'], f['reasons']))
        if len(found) > 20:
            print('  ... 其余', len(found) - 20, '张见 --json')

    if a.cmd == 'check':
        # 门禁：修复后重新扫一遍，仍有问题卡就报错
        _, remain = process(text, 'detect')
        print('修复后残留旧卡:', len(remain))
        return 1 if remain else 0
    return 0


if __name__ == '__main__':
    sys.exit(main())
