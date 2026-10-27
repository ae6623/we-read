#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""补全「无 AI 大纲原文」的 5 本书的章节导读。

这 5 本在仓库里没有 AI 大纲（`_data/books/*.json` 的 ai_outline 为 None），
无法像其余 58 本那样解析 details.ch / ul.point。改用手上真实存在的素材：

  A. ch-list 平铺模板（zhi-hu / yi-ri）：把「板块 h3 + 一章一行」转成折叠块，
     展开即该板块全部条目；不新增任何事实。
  B. 有 full-overview.md（unstable-life）：把 md「各章核心」按章名并入对应 ch-body，
     这是比 html 里更详细的一手整理内容。
  C. 单章短篇（serbia）：把页面「AI 问书」三小节并入该章 ch-body。
  D. 目录未核实（shi-shi）：仅转折叠，不编内容。

原则：只用页面/md 里已存在的信息，不生成虚构要点与原句。
"""
from __future__ import annotations

import argparse
import html as H
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_outline_full import _gh_api_client  # noqa: E402

SITE = "/workspace/we-read"
BOOKS = "reading-notes/books"

TOC_PART_RE = re.compile(r'<div class="toc-part">\s*<h3>([\s\S]*?)</h3>\s*<ul class="ch-list">([\s\S]*?)</ul>\s*</div>')
LI_RE = re.compile(r'<li><span class="ch-no">([\s\S]*?)</span><span class="ch-t">([\s\S]*?)</span>([\s\S]*?)</li>')


def esc(s):
    return H.escape(re.sub(r"\s+", " ", (s or "")).strip(), quote=False)


def _strip(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()


# ------------------------------------------------------------ A. ch-list → 折叠
def convert_chlist(html_text: str):
    """把「<div class=toc-part><h3>板块</h3><ul class=ch-list>...」转成折叠块（幂等）。"""
    n = [0]

    def repl(m):
        part = esc(_strip(m.group(1)))
        items = []
        for lm in LI_RE.finditer(m.group(2)):
            no = esc(_strip(lm.group(1)))
            t = esc(_strip(lm.group(2)))
            tail = _strip(lm.group(3)).strip("。").strip()   # 例：未读
            items.append((no, t, tail))
        if not items:
            return m.group(0)
        lis = []
        for no, t, tail in items:
            badge = ('<span class="badge" data-s="unread">%s</span>' % esc(tail)) if tail else ""
            lis.append('            <li><b>%s</b>：%s %s</li>' % (no, t, badge))
        n[0] += len(items)
        return (
            '<div class="toc-part">\n'
            '        <details class="ch-item"><summary><span class="ch-t">%s</span>'
            '<span class="sec-count">%d 条</span><span class="caret">›</span></summary>\n'
            '          <div class="ch-body">\n'
            '          <ol class="ch-secs">\n%s\n          </ol>\n'
            '          </div></details>\n'
            '      </div>' % (part, len(items), "\n".join(lis))
        )

    out = TOC_PART_RE.sub(repl, html_text)
    return out, n[0]


# ------------------------------------------------------------ B. md 并入 ch-body
def merge_md(html_text: str, md_path: str):
    """把 full-overview.md「各章核心」按章名并入对应 ch-item 的 ch-body（幂等）。"""
    md = open(md_path, encoding="utf-8").read()
    part = md.split("各章核心", 1)
    if len(part) < 2:
        return html_text, 0
    block = part[1].split("\n##", 1)[0]
    cores = {}
    for line in block.splitlines():
        m = re.match(r"\s*\d+\.\s*([^：:]{2,40})[：:](.+)", line)
        if m:
            cores[m.group(1).strip()] = m.group(2).strip()
    if not cores:
        return html_text, 0

    n = [0]
    _nz = lambda s: re.sub(r"\s+", "", s or "")

    def repl(m):
        whole = m.group(0)
        if "md-core" in whole:
            return whole
        title = _strip(m.group(1))
        hit = None
        for k, v in cores.items():
            a, b = _nz(k)[:5], _nz(title)[:5]
            if a and (a in _nz(title) or b in _nz(k)):
                hit = v
                break
        if not hit:
            return whole
        n[0] += 1
        extra = ('\n        <p class="md-core"><strong>整理要点（全貌 md）：</strong>%s</p>'
                 % esc(hit))
        k = whole.rfind("</div>")            # 追加到 ch-body 末尾，不抢导读的位置
        return whole[:k] + extra + "\n      " + whole[k:]

    out = re.sub(
        r'<details class="ch-item"[^>]*><summary><span class="ch-t">([\s\S]*?)</span>[\s\S]*?</summary>'
        r'\s*(<div class="ch-body">[\s\S]*?</div>)',
        repl, html_text)
    return out, n[0]


# ------------------------------------------------------------ C. 页面 section 并入
def merge_section(html_text: str, heading_kw: str, into_title_kw: str, label: str, max_items: int = 6):
    """把页面里某个 section 的 h3/li 条目并入指定章的 ch-body（幂等）。"""
    h2 = None
    for m in re.finditer(r'<h2[^>]*>([^<]+)</h2>', html_text):
        if heading_kw in m.group(1):
            h2 = m
            break
    if not h2:
        return html_text, 0
    sec_start = html_text.rfind("<section", 0, h2.start())
    sec_end = html_text.find("</section>", h2.end())
    if sec_start < 0 or sec_end < 0:
        return html_text, 0
    seg = html_text[sec_start:sec_end]

    items = []
    for m in re.finditer(r"<h3[^>]*>([\s\S]*?)</h3>\s*(?:<p[^>]*>)?([\s\S]{0,400}?)(?=<h3|</section|$)", seg):
        t = esc(_strip(m.group(1)))
        v = esc(_strip(re.sub(r"<[^>]+>", "", m.group(2))))[:220]
        if t and v:
            items.append((t, v))
        if len(items) >= max_items:
            break
    if not items:
        return html_text, 0

    lis = "\n".join('          <li><b>%s</b>：%s</li>' % (t, v) for t, v in items)
    block = ('        <details class="ch-sec"><summary><span class="sec-h">%s</span>'
             '<span class="sec-count">%d 条</span></summary>\n'
             '          <ol class="ch-secs">\n%s\n          </ol>\n'
             '        </details>' % (esc(label), len(items), lis))

    def repl(m):
        if 'data-src="%s"' % label in m.group(0) or label in m.group(0):
            return m.group(0)
        return m.group(0).replace("</div></details>", block + "\n      </div></details>", 1)

    pat = (r'<details class="ch-item"[^>]*><summary><span class="ch-t">[^<]*' + re.escape(into_title_kw) +
           r'[^<]*</span>[\s\S]*?</div></details>')
    new = re.sub(pat, repl, html_text, count=1)
    return (new, len(items)) if new != html_text else (html_text, 0)


# ------------------------------------------------------------ 主流程
def process(slug: str, dry: bool):
    d = os.path.join(SITE, BOOKS, slug)
    p = os.path.join(d, "overview.html")
    if not os.path.exists(p):
        return None, "无 overview.html"
    h0 = open(p, encoding="utf-8").read()
    h = h0
    notes = []

    if slug in ("zhi-hu-shen-tie--ren-shi-zhen-xiang",
                "yi-ri-wei-jing--jing-ji-xia-xing-qi-chuan-yue-z"):
        h, n = convert_chlist(h)
        notes.append("ch-list→折叠 %d 条" % n)

    if slug == "unstable-life-qingyouji":
        md = os.path.join(d, "full-overview.md")
        if os.path.exists(md):
            h, n = merge_md(h, md)
            notes.append("md 章核心并入 %d 章" % n)

    if slug == "serbia-qingyouji":
        h, n = merge_section(h, "AI 问书", "塞尔维亚", "AI 问书要点（页面整理）")
        notes.append("并入 AI 问书 %d 条" % n)

    if h == h0:
        return None, "无变更"

    if not dry:
        open(p, "w", encoding="utf-8").write(h)
    return ("%s/%s/overview.html" % (BOOKS, slug), h), "；".join(notes)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    targets = ["serbia-qingyouji", "shi-shi", "unstable-life-qingyouji",
               "zhi-hu-shen-tie--ren-shi-zhen-xiang",
               "yi-ri-wei-jing--jing-ji-xia-xing-qi-chuan-yue-z"]
    files = {}
    for s in targets:
        r, note = process(s, a.dry_run)
        if r is None:
            print("  - %-46s %s" % (s[:46], note))
            continue
        path, h = r
        files[path] = h
        print("  ✓ %-46s %.1fKB → %.1fKB  %s"
              % (s[:46], os.path.getsize(os.path.join(SITE, BOOKS, s, "overview.html")) / 1024,
                 len(h) / 1024, note))

    print("变更文件：%d" % len(files))
    if not files:
        return 0
    if not a.publish or a.dry_run:
        print("发布：[未开启 --publish 或 dry-run]")
        return 0

    api = _gh_api_client()
    orig = api.create_blob

    def slow(data, _o=orig):
        time.sleep(0.35)
        return _o(data)

    api.create_blob = slow
    ok, msg, det = api.publish_paths(
        files, "feat(overview): 补全无 AI 大纲的 5 本——ch-list 转折叠、md/页面素材并入章节块")
    print("发布：ok=%s msg=%s detail=%s" % (ok, msg, str(det)[:160]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
