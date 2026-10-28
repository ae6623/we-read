#!/bin/sh
# 一键重建：回滚通读页 → 清证据等级标签 → 升级「全书结构」区块
set -e
cd /workspace/we-read
git checkout -- reading-notes/books/*/overview.html
python3 - <<'PY'
import re, glob
TAGS = ['建议复习', '可衡量', '待亲读后自答']
n = 0
for f in glob.glob('reading-notes/books/*/overview.html'):
    t = open(f, encoding='utf-8').read(); o = t
    for tag in TAGS:
        t, k = re.subn(r'[ \t]*<span class="tag">\s*' + tag + r'\s*</span>[ \t]*', '', t); n += k
    t, k = re.subn(r'<p class="notice">标记最值得复现的\s*1[–\-]3\s*个条目与建议复习时点；[^<]*?</p>\s*', '', t); n += k
    if t != o:
        open(f, 'w', encoding='utf-8').write(t)
print('清标签', n)
PY
python3.11 tools/upgrade_mindmap.py --write "$@"
