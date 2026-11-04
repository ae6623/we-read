#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scan_fonts.py — 生成 assets/fonts/fonts.json，供详情页 Aa 面板的「字体」下拉读取。

以后新增字体只要两步（不用改 reader.js / reader.css，也不用重生成任何一本书）：

  1. 把 .ttf / .otf / .woff2 丢进 assets/fonts/
  2. 在仓库根目录跑：python3 assets/fonts/scan_fonts.py --subset
     然后提交 fonts.json 和新生成的 .woff2

--subset 会把大 TTF 转成「常用汉字子集 + woff2」，体积约降到 1/10；
不加该参数时只刷新 fonts.json，不改动任何字体文件。
依赖（仅 --subset 需要）：pip install fonttools brotli

清单里只列 woff2（存在时优先）；原始 TTF 保留在仓库作源文件，但不进下拉，
避免有人误点 18MB 的文件。字体只在用户主动选中时才下载，缺字自动回退系统字体。
"""
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXTS = ('.woff2', '.woff', '.ttf', '.otf')
SRC_EXTS = ('.ttf', '.otf')

# 显示名覆盖：子集化后字体内部 name 表通常只剩英文族名，这里给回中文名。
# 新增字体时按需补一行即可，不补就用字体内部名 / 文件名。
ALIASES = {
    'CE-03-W04': '仓耳今楷 03 W04',
    'CE-05-W05': '仓耳今楷 05 W05',
    'CE-W03': '仓耳今楷 03 W03',
    'yyb': 'yyb Sans',
}


def build_charset():
    """GB2312 全量（6763 汉字）+ ASCII + 中文标点/全角符号 + 常见特殊符号。

    覆盖现代汉语 99.9% 用字；生僻字由 CSS fallback 接住，不会显示豆腐块。
    """
    cs = set(chr(c) for c in range(0x20, 0x7f))
    for b1 in range(0xA1, 0xF8):
        for b2 in range(0xA1, 0xFF):
            try:
                cs.add(bytes([b1, b2]).decode('gb2312'))
            except UnicodeDecodeError:
                pass
    for lo, hi in ((0x3000, 0x3040), (0xFF00, 0xFFF0), (0x2000, 0x2070)):
        for cp in range(lo, hi):
            cs.add(chr(cp))
    for c in '·—…‰℃№★☆○●◎◇◆□■△▲※→←↑↓↔™®©§¶†‡±×÷≈≠≤≥∞′″':
        cs.add(c)
    return set(ord(c) for c in cs)


def family_name(stem, path):
    """优先用 ALIASES，其次字体内部 name 表，最后用文件名。"""
    if stem in ALIASES:
        return ALIASES[stem]
    try:
        from fontTools.ttLib import TTFont
        f = TTFont(path, lazy=True)
        best = ''
        for r in f['name'].names:
            if r.nameID in (4, 1) and r.platformID == 3:
                try:
                    v = r.toUnicode().strip()
                except Exception:
                    continue
                if r.nameID == 4 and v:
                    best = v
                    break
                if not best:
                    best = v
        f.close()
        if best:
            return best
    except Exception:
        pass
    return os.path.splitext(os.path.basename(path))[0]


def subset_one(src, dst, unicodes):
    import time
    from fontTools import subset
    from fontTools.ttLib import TTFont

    t = time.time()
    opt = subset.Options()
    opt.flavor = 'woff2'
    opt.layout_features = []       # 丢 GSUB 竖排等特性，中文横排用不到
    opt.name_IDs = ['*']
    opt.notdef_glyph = True
    opt.recommended_glyphs = True
    f = TTFont(src)
    ss = subset.Subsetter(options=opt)
    ss.populate(unicodes=unicodes)
    ss.subset(f)
    f.flavor = 'woff2'
    f.save(dst)
    f.close()
    return time.time() - t


def human(n):
    return '%.2f MB' % (n / 1048576.0) if n >= 1048576 else '%.0f KB' % (n / 1024.0)


def main():
    do_subset = '--subset' in sys.argv
    force = '--force' in sys.argv

    files = sorted(f for f in os.listdir(HERE) if f.lower().endswith(EXTS))
    bystem = {}
    for f in files:
        stem, ext = os.path.splitext(f)
        bystem.setdefault(stem, []).append((f, ext.lower()))

    if do_subset:
        try:
            import fontTools  # noqa: F401
            import brotli     # noqa: F401
        except ImportError:
            print('缺少依赖，请先执行： pip install fonttools brotli', file=sys.stderr)
            return 1
        cs = build_charset()
        print('子集字符集：%d 个码位' % len(cs))
        for stem, variants in bystem.items():
            src = next((f for f, e in variants if e in SRC_EXTS), None)
            dst = stem + '.woff2'
            if not src or (os.path.exists(os.path.join(HERE, dst)) and not force):
                continue
            sp, dp = os.path.join(HERE, src), os.path.join(HERE, dst)
            dt = subset_one(sp, dp, cs)
            a, b = os.path.getsize(sp), os.path.getsize(dp)
            print('  %-14s %s -> %s (%.1f%%, %.1fs)' %
                  (stem, human(a), human(b), b * 100.0 / a, dt))
        files = sorted(f for f in os.listdir(HERE) if f.lower().endswith(EXTS))
        bystem = {}
        for f in files:
            stem, ext = os.path.splitext(f)
            bystem.setdefault(stem, []).append((f, ext.lower()))

    entries = []
    for stem, variants in sorted(bystem.items()):
        exts = {e for _, e in variants}
        if '.woff2' in exts:
            pick = next(f for f, e in variants if e == '.woff2')
        else:
            pick = next((f for f, e in variants if e in SRC_EXTS or e == '.woff'), None)
        if not pick:
            continue
        src = next((f for f, e in variants if e in SRC_EXTS), pick)
        e = {
            'file': pick,
            'name': family_name(stem, os.path.join(HERE, src)),
            'bytes': os.path.getsize(os.path.join(HERE, pick)),
        }
        if src != pick:
            e['source'] = src
            e['sourceBytes'] = os.path.getsize(os.path.join(HERE, src))
        entries.append(e)

    data = {
        'generated': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
        'note': ('由 assets/fonts/scan_fonts.py 生成。只列 woff2（有则优先），原始 TTF 保留作源文件；'
                 '字体按需加载、font-display:swap，缺字自动回退系统字体。新增字体后重跑本脚本即可，'
                 '不用改 reader.js / reader.css，也不用重生成任何一本书。'),
        'fonts': entries,
    }
    out = os.path.join(HERE, 'fonts.json')
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write('\n')

    print('已写入 %s，共 %d 个字体：' % (out, len(entries)))
    for e in entries:
        extra = ('（源 %s）' % human(e['sourceBytes'])) if 'sourceBytes' in e else ''
        print('  %-22s %-24s %s%s' % (e['file'], e['name'], human(e['bytes']), extra))
    return 0


if __name__ == '__main__':
    sys.exit(main())
