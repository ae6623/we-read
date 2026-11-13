# -*- coding: utf-8 -*-
"""全站详情页模板健康度识别（可重复运行的脚本算法）。

判定依据不是文件大小，而是**新版统一模板的模块结构**：
  combined.html        —— 统一壳页（引用 reader-20261110.js）
  combined-data.html   —— 真正的内容片段，含若干 aria-labelledby 模块

新版标准模块（参考 jiao-yi-xin-li-fen-xi）：
  oneline / merged-guide-title / views / top10 / coreask /
  aiask / higher / verify / thennow          （9 个）
其中 top10（原文金句·持续积累）是渐进模块，缺它不算坏。

分级：
  ok       new>=8   已修好，留主页
  fixable  new=0 且 mindmap>=7  —— mindmap 已是新模块，只差统一壳页，脚本可修
  thin     new=7   有标准壳但缺 1-2 核心模块（内容充实，留主页 + 标记待补）
  dump     new<=3  壳对了但里面是老版思维导图 dump，一点用没有 → 归档 + 重产
  empty    无 combined-data 且 mindmap 也是老 dump/空壳/占位 → 归档

产出：
  assets/data/template-audit.json     前端搬卡/标记用
  /workspace/首页未修书识别清单-*.md   人读报告

用法：
  python3.11 tools/audit_templates.py              # 扫线上
  python3.11 tools/audit_templates.py --base https://reader.js-dev.cn
"""
import json, re, sys, time, pathlib, collections
import urllib.request, urllib.error, concurrent.futures

BASE = 'https://reader.js-dev.cn'
for i, a in enumerate(sys.argv):
    if a == '--base' and i + 1 < len(sys.argv):
        BASE = sys.argv[i + 1].rstrip('/')

ROOT = pathlib.Path(__file__).resolve().parents[1]
NEW = ['oneline', 'merged-guide-title', 'views', 'top10', 'coreask',
       'aiask', 'higher', 'verify', 'thennow']
NEWSET = set(NEW)
B = BASE + '/reading-notes/books/'


def fetch(url, timeout=30):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (template-audit)'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b''
    except Exception:
        return 'ERR', b''


def labs(text):
    return set(re.findall(r'aria-labelledby="([^"]+)"', text)) & NEWSET


def home_slugs():
    # 2026-11-13 坑：七牛对「根路径 + query」返回 404（读首页必须用 /index.html），
    # 之前带 ?cb= 时间戳导致脚本一启动就 RuntimeError。
    code, b = fetch(BASE + '/index.html')
    if code != 200:
        raise RuntimeError('首页拉取失败 HTTP %s' % code)
    h = b.decode('utf-8', 'ignore')
    cards = {}
    for card in re.findall(r'<article[^>]*archive-card.*?</article>', h, re.S):
        m = re.search(r'data-slug="([^"]+)"', card)
        if not m:
            continue
        slug = m.group(1)
        t = re.search(r'class="card-title-link"[^>]*>(.*?)</a>', card, re.S)
        href = re.search(r'class="card-title-link"[^>]*href="([^"]+)"', card)
        title = re.sub(r'<[^>]+>', '', t.group(1)).strip()[:80] if t else ''
        cards[slug] = {'title': title, 'href': href.group(1) if href else ''}
    return cards


def scan_one(slug, meta):
    r = {'title': meta['title'], 'href': meta['href']}
    c, b = fetch(B + slug + '/combined.html')
    r['shell'] = (c == 200 and b'reader-20261110.js' in b)
    c, b = fetch(B + slug + '/combined-data.html')
    r['data_code'] = c
    r['data_size'] = len(b)
    r['new'] = len(labs(b.decode('utf-8', 'ignore'))) if b else 0
    c, b = fetch(B + slug + '/mindmap.html')
    r['mm_size'] = len(b)
    r['mm_new'] = len(labs(b.decode('utf-8', 'ignore'))) if b else 0

    if r['new'] >= 8:
        status, action = 'ok', 'keep'
    elif r['new'] <= 3 and r['data_code'] == 200:
        status, action = 'dump', 'archive+rework'
    elif r['data_code'] != 200 and r['mm_new'] >= 7:
        status, action = 'fixable', 'fix'
    elif r['data_code'] != 200:
        status, action = 'empty', 'archive'
    else:
        status, action = 'thin', 'keep+mark'
    r['status'], r['action'] = status, action
    return slug, r


def main():
    cards = home_slugs()
    print('首页卡片 slug 数:', len(cards), flush=True)
    out = {}
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        for i, (slug, r) in enumerate(ex.map(lambda kv: scan_one(*kv), cards.items()), 1):
            out[slug] = r
            if i % 100 == 0:
                print('  progress %d / %d  %ds' % (i, len(cards), int(time.time() - t0)), flush=True)

    by = collections.Counter(r['status'] for r in out.values())
    archive = sorted(s for s, r in out.items() if 'archive' in r['action'])
    rework = sorted(s for s, r in out.items() if 'rework' in r['action'] or r['status'] == 'dump')
    fix = sorted(s for s, r in out.items() if r['status'] == 'fixable')

    doc = {
        'version': time.strftime('%Y-%m-%dT%H:%M:%S+08:00'),
        'base': BASE,
        'standard_modules': NEW,
        'summary': dict(by),
        'total': len(out),
        'archiveSlugs': archive,
        'reworkSlugs': rework,
        'fixableSlugs': fix,
        'books': out,
    }
    dst = ROOT / 'assets/data/template-audit.json'
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding='utf-8')

    print('\n=== 分级汇总 ===')
    for k, v in sorted(by.items()):
        print('  %-9s %d 本' % (k, v))
    print('  归档 %d 本 / 重产 %d 本 / 可修 %d 本' % (len(archive), len(rework), len(fix)))
    print('\n产出:', dst)

    # 人读报告
    lines = ['# 首页未修书识别清单 %s' % time.strftime('%Y-%m-%d %H:%M'),
             '',
             '判定依据：`combined-data.html` 的新版模块命中数（非文件大小）。标准 9 模块：',
             '`oneline / merged-guide-title / views / top10 / coreask / aiask / higher / verify / thennow`。',
             '`top10`（原文金句·持续积累）为渐进模块，缺它不算坏。',
             '',
             '| 分级 | 本数 | 处置 |', '|---|---|---|']
    desc = {'ok': '已修好，留主页', 'thin': '缺 1-2 核心模块，内容充实，留主页+标记待补',
            'fixable': 'mindmap 已是新模块，脚本补统一壳页后留主页',
            'dump': '壳对了但里面是老版思维导图 dump → 归档 + 重产',
            'empty': '空壳/占位/老 dump → 归档'}
    for k, v in sorted(by.items()):
        lines.append('| %s | %d | %s |' % (k, v, desc.get(k, '')))
    lines += ['', '总计 **%d** 本，未修好 **%d** 本（thin+fixable+dump+empty）。' %
              (len(out), sum(v for k, v in by.items() if k != 'ok')), '']
    for st in ['dump', 'empty', 'fixable', 'thin']:
        rows = [(s, r) for s, r in out.items() if r['status'] == st]
        if not rows:
            continue
        lines += ['## %s（%d 本）' % (st, len(rows)), '',
                  '| 书名 | slug | new | combined-data | mindmap new |',
                  '|---|---|---|---|---|']
        for s, r in sorted(rows, key=lambda x: -x[1]['data_size']):
            lines.append('| %s | `%s` | %d | %dB | %d |' %
                         (r['title'][:34].replace('|', '/'), s, r['new'],
                          r['data_size'], r['mm_new']))
        lines.append('')
    rp = pathlib.Path('/workspace/首页未修书识别清单-%s.md' % time.strftime('%Y-%m-%d'))
    rp.write_text('\n'.join(lines), encoding='utf-8')
    print('报告:', rp)


if __name__ == '__main__':
    main()
