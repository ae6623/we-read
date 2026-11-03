#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给所有书籍详情页（reading-notes/books/*/combined.html）补上分享组件引用。

详情页是引擎批量产出的静态文件，重新生成后可能丢掉 share.css / share.js 的
<link> <script>。本脚本幂等，重跑只补缺失的引用：

    python3 tools/add_share_to_combined.py           # 打补丁
    python3 tools/add_share_to_combined.py --check   # 只检查，不写文件

组件行为：详情页右上角浮动分享图标（与 Aa 并排），点开是当前页二维码 +
微信/朋友圈/微博/QQ空间/复制链接。
"""
import argparse
import glob
import sys

CSS = '<link rel="stylesheet" href="../../../assets/css/share.css?v=20261103b">'
QR = '<script src="../../../assets/js/vendor/qrcode.min.js" defer></script>'
JS = '<script src="../../../assets/js/share.js?v=20261103b" defer></script>'
NEEDLE = 'assets/js/share.js'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只检查，不写入')
    ap.add_argument('--root', default='.', help='仓库根目录，默认当前目录')
    args = ap.parse_args()

    files = sorted(glob.glob(f'{args.root}/reading-notes/books/*/combined.html'))
    if not files:
        print('没找到 reading-notes/books/*/combined.html，确认在仓库根目录执行', file=sys.stderr)
        return 2

    missing, patched, nope = [], 0, []
    for f in files:
        s = open(f, encoding='utf-8').read()
        if NEEDLE in s:
            continue
        missing.append(f)
        if '</head>' not in s:
            nope.append(f)
            continue
        if not args.check:
            s = s.replace('</head>', f'{CSS}\n{QR}\n{JS}\n</head>', 1)
            open(f, 'w', encoding='utf-8').write(s)
            patched += 1

    print(f'详情页 {len(files)} 个，缺分享组件 {len(missing)} 个，'
          f'{"待补" if args.check else "已补"} {patched if not args.check else len(missing)} 个')
    if nope:
        print('缺少 </head> 跳过：' + ', '.join(nope[:5]))
    return 1 if (args.check and missing) else 0


if __name__ == '__main__':
    raise SystemExit(main())
