#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验收守卫：全站壳页的 reader JS 版本必须与真相源一致，防止新书回退。

检查项：
  R1  ``assets/data/reader-js.json`` 的 current 合法，且 assets/js/ 下确有该文件
  R2  全站 543 本 combined.html 都引用 current（从 git tree 读，不受稀疏检出影响）
  R3  引擎仓产出模板常量（若同机可读）与 current 一致
  R4  CDN 上的 current JS 返回 200（可选，--online 才跑）

用法：
    python3 scripts/check_reader_js.py              # 本地（离线）检查
    python3 scripts/check_reader_js.py --online     # 追加 CDN 可达性检查

退出码 0 = 通过，1 = 有不一致。挂进产出 SOP / CI 后，任何版本回退都会被拦下。
"""
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS_RE = re.compile(rb'assets/js/(reader-\d+\.js)')
ENGINE_TPL = '/root/wr-latest/overview_gen/combine_page.py'


def git(*args, **kw):
    return subprocess.check_output(['git'] + list(args), cwd=ROOT, **kw)


def main():
    online = '--online' in sys.argv
    problems = []

    # R1 真相源
    cfg = ROOT / 'assets' / 'data' / 'reader-js.json'
    if not cfg.exists():
        print('✗ R1 缺真相源 assets/data/reader-js.json')
        return 1
    try:
        info = json.loads(cfg.read_text(encoding='utf-8'))
        current = info['current']
    except Exception as e:
        print('✗ R1 真相源解析失败: %s' % e)
        return 1
    if not re.match(r'^reader-\d+\.js$', current):
        print('✗ R1 current 格式非法: %r' % current)
        return 1
    jsfiles = set(os.listdir(ROOT / 'assets' / 'js'))
    if current not in jsfiles:
        problems.append('R1 assets/js/%s 不存在' % current)
    print('R1 真相源 current = %s  %s' %
          (current, '✓' if current in jsfiles else '✗'))

    # R2 全站壳页（从 HEAD tree 读，稀疏检出也覆盖 543 本）
    out = git('ls-tree', '-r', '-z', 'HEAD', '--', 'reading-notes/books')
    items = []
    for rec in out.split(b'\0'):
        if not rec:
            continue
        meta, path = rec.split(b'\t', 1)
        sha = meta.split()[2].decode()
        p = path.decode()
        if p.endswith('/combined.html'):
            items.append((sha, p))
    if not items:
        problems.append('R2 没找到任何 combined.html')
        return 1
    proc = subprocess.Popen(['git', 'cat-file', '--batch'],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, cwd=ROOT)
    stdout, _ = proc.communicate(b''.join(s.encode() + b'\n' for s, _ in items))
    pos = 0
    dist = {}
    bad = []
    for sha, path in items:
        nl = stdout.index(b'\n', pos)
        size = int(stdout[pos:nl].split()[2])
        pos = nl + 1
        data = stdout[pos:pos + size]
        pos += size + 1
        m = JS_RE.search(data)
        ver = m.group(1).decode() if m else '<无引用>'
        dist[ver] = dist.get(ver, 0) + 1
        if ver != current:
            bad.append((path, ver))
    print('R2 全站壳页 %d 本，引用分布:' % len(items))
    for k, v in sorted(dist.items(), key=lambda x: -x[1]):
        print('     %-28s %d 本 %s' % (k, v, '✓' if k == current else '✗'))
    if bad:
        problems.append('R2 有 %d 本引用不是 %s（示例 %s）' %
                        (len(bad), current, ', '.join(p.split('/')[-2] for p, _ in bad[:5])))

    # R3 引擎仓模板常量
    if os.path.exists(ENGINE_TPL):
        try:
            sys.path.insert(0, os.path.dirname(ENGINE_TPL))
            import combine_page as cp
            tpl_ver = getattr(cp, 'READER_JS', None)
            if tpl_ver != current:
                problems.append('R3 引擎仓模板 READER_JS=%r 与真相源 %r 不一致' %
                                (tpl_ver, current))
            else:
                print('R3 引擎仓产出模板 READER_JS = %s  ✓' % tpl_ver)
        except Exception as e:
            print('R3 引擎仓模板读取失败（跳过）: %s' % str(e)[:80])
    else:
        print('R3 引擎仓不在同机，跳过（CI 环境正常）')

    # R4 CDN 可达性
    if online:
        url = info.get('cdn_prefix', 'https://cdn.js-dev.cn/assets/js/') + current
        try:
            req = urllib.request.Request(url, method='HEAD')
            with urllib.request.urlopen(req, timeout=15) as r:
                ok = r.status == 200
                print('R4 CDN %s → HTTP %s %s' % (current, r.status, '✓' if ok else '✗'))
                if not ok:
                    problems.append('R4 CDN 返回 %s' % r.status)
        except Exception as e:
            problems.append('R4 CDN 不可达: %s' % str(e)[:80])

    if problems:
        print('\n✗ 验收未通过:')
        for p in problems:
            print('   - ' + p)
        return 1
    print('\n✓ 全部通过：全站 %d 本壳页均引用 %s' % (len(items), current))
    return 0


if __name__ == '__main__':
    sys.exit(main())
