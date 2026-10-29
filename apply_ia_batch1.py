#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""apply_ia_batch1.py —— 信息架构改版第 1 批（IA-01 / IA-02 / IA-04）

依据：docs/site-ia-redesign-2026-10-28.md（产品方案 v2，已拍板）
      openspec/changes/site-ia-redesign-2026-10-28/tasks.md 第 1 批

做四件事（幂等，可重复跑）：
  1) IA-01 顶部 Tab 改「书架 / 系列 / 精读 / 归档」：id 不动，只改可见文案与 aria-label
  2) IA-02 书架（原通读面板）顶部加 sticky 搜索框 + 类型筛选条 + 结果计数 + empty state
  3) IA-02 每张卡加 data-mode="whole jingdu archive"（按线上仓库树判定，本地仓不全）
  4) IA-04 卡片精简：card-top 只留 1 个类型标签，去掉「网页版」「AI 大纲」标签、
     EPUB 下载（按方案暂不放），入口行文案「读前通读 · AI 大纲」→「AI 大纲」
"""
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE / "index.html"
HAVE = json.loads(Path("/tmp/have.json").read_text()) if Path("/tmp/have.json").exists() else None


def online_have():
    """线上各书资源判定（本地仓不全，一律以线上为准）。"""
    if HAVE:
        return ({k: set(v) for k, v in HAVE.items()})
    out = subprocess.check_output(
        ["gh", "api", "repos/ae6623/we-read/git/trees/main?recursive=1",
         "--jq", "[.tree[].path]"], text=True, timeout=110)
    books = {}
    for p in json.loads(out):
        if p.startswith("reading-notes/books/"):
            parts = p.split("/")
            if len(parts) >= 3:
                books.setdefault(parts[2], set()).add("/".join(parts[3:]))
    return {
        "ov": {s for s, f in books.items() if "overview.html" in f},
        "mm": {s for s, f in books.items() if "mindmap.html" in f},
        "fin": {s for s, f in books.items() if "final.html" in f},
        "notes": {s for s, f in books.items() if any(x.startswith("notes/") for x in f)},
    }


def modes_for(slug, have):
    m = []
    if slug in have["ov"]:
        m.append("whole")
    if slug in have["mm"]:
        m.append("jingdu")
    if slug in have["fin"] or slug in have["notes"]:
        m.append("archive")
    return m


# ---------------------------------------------------------------- IA-01
OLD_TABS = ('        <button type="button" id="reading-tab-overview" data-panel="reading-panel-overview">通读</button>\n'
            '        <button type="button" id="reading-tab-close" data-panel="reading-panel-close">精读</button>\n'
            '        <button type="button" id="reading-tab-series" data-panel="reading-panel-series">系列</button>\n'
            '        <button type="button" id="reading-tab-archive" data-panel="reading-panel-archive">归档</button>')
NEW_TABS = ('        <button type="button" id="reading-tab-overview" data-panel="reading-panel-overview" aria-label="书架">书架</button>\n'
            '        <button type="button" id="reading-tab-series" data-panel="reading-panel-series" aria-label="系列">系列</button>\n'
            '        <button type="button" id="reading-tab-close" data-panel="reading-panel-close" aria-label="精读">精读</button>\n'
            '        <button type="button" id="reading-tab-archive" data-panel="reading-panel-archive" aria-label="归档">归档</button>')

# ---------------------------------------------------------------- IA-02
TOOLBAR = '''        <div class="toolbar shelf-toolbar" data-search-toolbar>
          <input id="shelf-search" type="search" placeholder="按书名或作者筛选…" autocomplete="off" data-card-search aria-label="搜索">
          <div class="filter-bar" data-filter-bar role="group" aria-label="按内容类型筛选">
            <button type="button" data-filter="all" aria-selected="true">全部</button>
            <button type="button" data-filter="whole" aria-selected="false">通读</button>
            <button type="button" data-filter="jingdu" aria-selected="false">精读</button>
            <button type="button" data-filter="archive" aria-selected="false">归档</button>
          </div>
          <p class="search-status" aria-live="polite" data-search-status></p>
        </div>
'''
EMPTY = ('        <p class="empty-state" data-empty-state hidden>没有找到匹配的书。'
         '<button type="button" class="link-button" data-clear-filters>清除筛选</button></p>\n')


def main():
    html = INDEX.read_text(encoding="utf-8")
    n0 = len(html)
    log = {}

    # ---------- IA-01 ----------
    if OLD_TABS in html:
        html = html.replace(OLD_TABS, NEW_TABS, 1)
        log["IA-01 Tab 改名+重排"] = "已改"
    elif NEW_TABS in html:
        log["IA-01 Tab"] = "已到位（幂等）"
    else:
        log["IA-01 Tab"] = "!! 未匹配到 Tab 区块"
    html = html.replace('id="reading-panel-overview" class="reading-panel" aria-label="通读"',
                        'id="reading-panel-overview" class="reading-panel" aria-label="书架"')

    # ---------- IA-02 工具栏 + empty state ----------
    if 'id="shelf-search"' not in html:
        anchor = '<section id="panel-whole"'
        if anchor in html:
            html = html.replace(anchor, TOOLBAR + anchor, 1)
            log["IA-02 书架搜索+筛选"] = "已插入"
        else:
            log["IA-02 书架搜索+筛选"] = "!! 找不到 panel-whole 锚点"
    else:
        log["IA-02 书架搜索+筛选"] = "已到位（幂等）"

    # empty state：必须落在书架面板区间内（JS 用 panel.querySelector 只查本面板内）
    # 锚点必须是整个 <section 开标签之前（否则会把开标签劈开，面板直接消失）
    ov_i = html.find('id="reading-panel-overview"')
    cl_i = html.find('<section id="reading-panel-close"')
    if cl_i < 0:
        k = html.find('id="reading-panel-close"')
        cl_i = html.rfind('<section', 0, k) if k > 0 else -1
    if ov_i > 0 and cl_i > ov_i:
        if 'data-empty-state' in html[ov_i:cl_i]:
            log["IA-02 empty state"] = "已存在（书架面板内）"
        else:
            # 必须落在 overview 面板「闭合 </section> 之前」——插到闭合之后就跑到面板外了
            end_ov = html.rfind('</section>', ov_i, cl_i)
            if end_ov > ov_i:
                html = html[:end_ov] + EMPTY + html[end_ov:]
                log["IA-02 empty state"] = "已插入书架面板"
            else:
                log["IA-02 empty state"] = "!! 找不到 overview 闭合标签"
    else:
        log["IA-02 empty state"] = "!! 找不到面板边界"

    # ---------- IA-02 data-mode ----------
    have = online_have()
    # 先建立 slug 映射：preread-card 注释 → slug
    card_slug = {}
    for cm in re.finditer(r'<!-- preread-card:([^\s]+) -->', html):
        end = html.find("</article>", cm.end())
        if end > 0:
            card_slug[cm.start()] = cm.group(1)

    def add_mode(m):
        """给 archive-card 开标签加 data-mode（whole=通读 / jingdu=精读 / archive=归档）。"""
        whole = m.group(0)  # 完整开标签，含已有属性
        if "data-mode" in whole:
            return whole
        end = html.find("</article>", m.end())
        block = html[m.start():end] if end > 0 else ""
        slug = None
        pre = html[:m.start()]
        pm = re.search(r'<!-- preread-card:([^\s]+) -->\s*$', pre)
        if pm:
            slug = pm.group(1)
        if not slug:
            lm = re.search(r'reading-notes/books/([^/"\']+)/', block)
            if lm:
                slug = lm.group(1)
        if not slug:
            return whole
        modes = modes_for(slug, have)
        if not modes:
            return whole
        return whole[:-1] + ' data-mode="%s">' % " ".join(modes)

    before = len(re.findall(r'<article[^>]*class="archive-card"', html))
    html = re.sub(r'<article[^>]*class="archive-card"[^>]*>', add_mode, html)
    after = len(re.findall(r'data-mode="', html))
    log["IA-02 data-mode"] = "卡片 %d 张，已标注 %d 张（其余无对应资源）" % (before, after)

    # ---------- IA-04 卡片精简 ----------
    steps = [
        ('<span class="type-tag">AI 大纲</span>', "", "去掉「AI 大纲」类型标签"),
        ('<span class="subtle">网页版</span>', "", "去掉「网页版」标签"),
        ('<span class="subtle">网页版 · EPUB</span>', "", "去掉「网页版 · EPUB」标签"),
        ('读前通读 · AI 大纲', "AI 大纲", "入口行文案改「AI 大纲」"),
    ]
    for old, new, desc in steps:
        c = html.count(old)
        if c:
            html = html.replace(old, new)
        log["IA-04 %s" % desc] = "%d 处" % c

    # 移除 EPUB 下载入口（方案：暂不放）
    epub = len(re.findall(r'<a class="download-link"[^>]*>.*?</a>', html, re.S))
    html = re.sub(r'\s*<a class="download-link"[^>]*>.*?</a>', '', html, flags=re.S)
    log["IA-04 移除 EPUB 下载"] = "%d 处" % epub

    # IA-04 收尾：可见文本与搜索词里的旧口径词（data-search 不可见，但会让人搜到已废弃的概念）
    extra = [
        ('，含 AI 问书', '', '卡片描述去「含 AI 问书」'),
        ('（待整理）', '', '书名去「（待整理）」'),
    ]
    for old, new, desc in extra:
        c = html.count(old)
        if c:
            html = html.replace(old, new)
        log["IA-04 %s" % desc] = "%d 处" % c

    def clean_ds(m):
        v = m.group(1).replace('AI 问书', ' ').replace('待整理', ' ')
        return 'data-search="%s"' % re.sub(r'\s+', ' ', v).strip()

    n_ds = len(re.findall(r'data-search="[^"]*(?:AI 问书|待整理)[^"]*"', html))
    html = re.sub(r'data-search="([^"]*)"', clean_ds, html)
    log["IA-04 data-search 清旧词"] = "%d 处" % n_ds

    INDEX.write_text(html, encoding="utf-8", newline="\n")
    print("=== 第 1 批应用结果 ===")
    for k, v in log.items():
        print("  %-34s %s" % (k, v))
    print("  文件长度 %d → %d（%+d）" % (n0, len(html), len(html) - n0))


if __name__ == "__main__":
    main()
