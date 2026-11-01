# -*- coding: utf-8 -*-
"""parse_outline.py — 解析微信读书 AI 大纲 HTML 为结构化 parsed.json。

输入：微信读书导出的 outline.html（含 <div class="toc"> … <details class="ch"> 结构）
输出：[{ "title": 章节标题, "secs": [{ "h4": 小节标题,
                                       "points": [要点…],
                                       "quotes": [原文摘录…] }] }]

这是确定性解析，不需要 LLM。详细程度完全取决于源大纲；
源大纲没有 quotes 字段时，quotes 就是空列表（渲染层会显示「未附原句摘录」）。

用法（库）：
    from parse_outline import parse_outline
    chapters = parse_outline(open("outline.html", encoding="utf-8").read())

用法（CLI）：
    python -m overview_gen.parse_outline outline.html -o parsed.json
"""
import re
import sys
import json
import html as _html


def parse_outline(html_text):
    body = html_text.split('<div class="toc">', 1)[-1]
    chapters = []
    parts = re.split(r'<details class="ch" id="ch\d+"><summary>', body)
    for p in parts[1:]:
        title = p.split('</summary>', 1)[0]
        title = _html.unescape(re.sub(r'<[^>]+>', '', title)).strip()
        content = p.split('</summary>', 1)[1]
        secs = []
        for sec in re.split(r'<div class="sec">', content)[1:]:
            m = re.match(r'\s*<h4>(.*?)</h4>', sec, re.S)
            if not m:
                continue
            h4 = _html.unescape(re.sub(r'<[^>]+>', '', m.group(1))).strip()
            pts, qts = [], []
            for blk in re.finditer(r'<li><b>(.*?)</b>(.*?)(?=</li>)', sec, re.S):
                txt = _html.unescape(re.sub(r'<[^>]+>', '', blk.group(1))).strip()
                pts.append(txt)
                for q in re.findall(r'<li>(.*?)</li>', blk.group(2), re.S):
                    qq = _html.unescape(re.sub(r'<[^>]+>', '', q)).strip()
                    if qq:
                        qts.append(qq)
            seen = set(); p2 = []
            for x in pts:
                if x and x not in seen:
                    seen.add(x); p2.append(x)
            seen = set(); q2 = []
            for x in qts:
                if x and x not in seen:
                    seen.add(x); q2.append(x)
            secs.append({'h4': h4, 'points': p2, 'quotes': q2})
        chapters.append({'title': title, 'secs': secs})
    return chapters


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="overview_gen.parse_outline",
                                 description="解析微信读书 AI 大纲 HTML 为 parsed.json")
    ap.add_argument("outline", help="源 outline.html 路径（或 '-' 读 stdin）")
    ap.add_argument("-o", "--output", default="", help="输出 parsed.json（默认打印到 stdout）")
    a = ap.parse_args(argv)
    if a.outline == '-':
        text = sys.stdin.read()
    else:
        text = open(a.outline, encoding="utf-8").read()
    chapters = parse_outline(text)
    data = json.dumps(chapters, ensure_ascii=False, indent=1)
    if a.output:
        with open(a.output, "w", encoding="utf-8") as f:
            f.write(data)
        print("%s -> %s 章节=%d" % (a.outline, a.output, len(chapters)))
        for c in chapters:
            npts = sum(len(s['points']) for s in c['secs'])
            nq = sum(len(s['quotes']) for s in c['secs'])
            print("  -", c['title'][:60], "| secs", len(c['secs']), "pts", npts, "q", nq)
    else:
        print(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
