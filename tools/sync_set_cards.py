#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""系列书卡同步：把「套装分册」写成首页系列 Tab 的书卡。

真源链（只认这两处，不认 index.html 里的旧卡片）：
    assets/data/series-sets.json            套装登记（slug / name / total / page）
    reading-notes/series/<set>/index.html   分册清单（标题 / 作者 / 章数 / 大纲链接）

产物：index.html 里 `<section class="set-group" data-units="<set>">` 的 `.set-units-grid`
      整块重建（幂等）；组不存在就追加到 `.set-groups` 末尾。

为什么要有这个脚本：卡片以前是手工/半手工拼进去的，新拆一个套装就得改 HTML，
很容易漏册、串封面、链接指错。现在只要系列页的分册清单是对的，跑一次就对齐。

用法：
  python tools/sync_set_cards.py --check          # 只报差异，不写文件
  python tools/sync_set_cards.py                  # 全部套装同步
  python tools/sync_set_cards.py --set oracle-wwii
  python tools/sync_set_cards.py --set oracle-wwii --append-only   # 只补新册，不动已有卡
"""
from __future__ import annotations

import argparse
import html as H
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"
SETS_JSON = ROOT / "assets" / "data" / "series-sets.json"
SERIES_DIR = ROOT / "reading-notes" / "series"
BOOKS = ROOT / "reading-notes" / "books"
COVERS = ROOT / "assets" / "covers"

# 与 note-spec 里统一的日期口径：卡片右上角只放「月.日」，不写年份
CARD_DATE = "2026-11-03"


# ── slug ────────────────────────────────────────────────────────────────
def pinyin_slug(title: str) -> str:
    """书名 → slug。规则与在建书目一致：汉字转全拼、数字原样保留、
    标点去掉、片段之间用 - 连，总长压到 64 字符以内。
    （pypinyin 的 errors="ignore" 会把「南京1937」的 1937 一起吃掉，
    所以先切段再分别处理。）"""
    try:
        from pypinyin import lazy_pinyin
    except ImportError:  # pragma: no cover
        raise SystemExit("需要 pypinyin：pip install pypinyin")
    tokens: list[str] = []
    for seg in re.findall(r"[\u4e00-\u9fff]+|[A-Za-z0-9]+", title):
        if re.match(r"[\u4e00-\u9fff]", seg):
            tokens.extend(lazy_pinyin(seg))
        else:
            tokens.append(seg.lower())
    s = "-".join(t for t in tokens if t)
    s = re.sub(r"[^a-z0-9\-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    if len(s) > 64:
        s = s[:64].rstrip("-")
    return s


def norm_title(s: str) -> str:
    s = H.unescape(s or "")
    s = re.sub(r"[《》「」“”\"'（）()\[\]【】]", "", s)
    s = re.sub(r"(经典版|升级版|增订版|精装版|纪念版|全\d+册|套装)", "", s)
    return re.sub(r"[\s·・,，。:：;；!！?？\-—–_/\\|｜]", "", s)


# ── 解析分册清单 ─────────────────────────────────────────────────────────
UNIT_RE = re.compile(r'<article class="book-entry"[^>]*>(.*?)</article>', re.S)


def parse_units(series_html: str) -> list[dict]:
    out = []
    for body in UNIT_RE.findall(series_html):
        m = re.search(r'<h3>\s*<a href="([^"]+)"[^>]*>(.*?)</a>', body, re.S)
        if not m:
            continue
        href, title = H.unescape(m.group(1)), re.sub(r"<[^>]+>", "", m.group(2))
        title = H.unescape(title).strip()

        # 分册页链接（相对 series/<set>/ 的两级）
        book = re.search(r"\.\./\.\./books/([^/\"]+)/", body)
        slug = book.group(1) if book else ""

        meta_txt = ""
        for p in re.findall(r"<p[^>]*>(.*?)</p>", body, re.S):
            t = H.unescape(re.sub(r"<[^>]+>", "", p)).strip()
            if t.startswith("作者"):
                meta_txt = t
                break
        author, chapter = "", ""
        # 作者名本身常带「·」（约翰·朱利叶斯·诺里奇），只有「空格·空格」
        # 才是作者与章数的分隔，不能按任意 · 切
        core = re.sub(r"^作者[:：]\s*", "", meta_txt).strip()
        mm = re.match(r"^(.*?)\s+[·・]\s+([\d,]+\s*章.*)$", core)
        if mm:
            author = mm.group(1).strip()
            chapter = mm.group(2).strip()
        elif core:
            author = core

        out.append({
            "title": title,
            "weread": href,
            "slug": slug or pinyin_slug(title),
            "author": author,
            "chapter": chapter,
        })
    return out


# ── 卡片 HTML ───────────────────────────────────────────────────────────
def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def resolve_href(u: dict) -> tuple[str, str]:
    """单册卡去向：整书笔记 > AI 章节大纲 > 微信读书原站。

    顺序不能反：先跳原站等于把读者扔出站外，回来还得自己找。
    返回 (href, 类型说明)。
    """
    slug = u["slug"]
    for name, kind in (("combined.html", "笔记"), ("overview.html", "通读"),
                       ("outline.html", "大纲")):
        p = BOOKS / slug / name
        if p.exists():
            return "reading-notes/books/%s/%s" % (slug, name), kind
    return u["weread"], "原站"


def card_html(u: dict) -> str:
    href, kind = resolve_href(u)
    label = {"笔记": "AI 笔记", "通读": "AI 通读", "大纲": "AI 大纲", "原站": "原站"}[kind]
    # 「0 章 / 0 条」是没抓到章的占位，宁可不显示也不要糊一个数字上去
    meta = u["chapter"] if u["chapter"] and not u["chapter"].startswith("0 章") else ""
    if not meta and kind != "原站":
        meta = label
    search = (u["title"] + ((" " + u["author"]) if u["author"] else "")).strip()
    foot = '<span class="card-author">%s</span>' % esc(u["author"])
    if meta:
        foot += '<span class="card-meta">%s</span>' % esc(meta)
    return (
        '          <article class="archive-card unit-card" data-slug="{slug}" data-search="{search}">\n'
        '          <div class="card-top"><time datetime="{date}">{md}</time></div>\n'
        '          <h3><a class="card-title-link" href="{href}">《{title}》</a></h3>\n'
        '          <div class="card-foot">{foot}</div>\n'
        '        </article>'
    ).format(
        slug=esc(u["slug"]), search=esc(search), href=esc(href),
        title=esc(u["title"]), foot=foot, date=CARD_DATE, md="11.03",
    )


def group_html(set_meta: dict, units: list[dict]) -> str:
    """按 index.html 里的既有缩进生成，保证重复执行不产生 diff。"""
    cards = "\n".join(card_html(u) for u in units)
    return (
        '<section class="set-group" data-units="{slug}">\n'
        '          <div class="set-group-head"><span class="set-group-name">{name}</span>'
        '<span class="set-group-count">{n} 册</span></div>\n'
        '          <div class="set-units-grid">\n{cards}\n          </div></section>'
    ).format(slug=esc(set_meta["slug"]), name=esc(set_meta["name"]),
             n=len(units), cards=cards)


# ── index.html 里的组定位（按 section 配平，不靠正则贪婪）────────────
def find_group_span(doc: str, set_slug: str) -> tuple[int, int] | None:
    idx = doc.find('data-units="%s"' % set_slug)
    if idx < 0:
        return None
    start = doc.rfind("<section", 0, idx)
    if start < 0:
        return None
    depth, i = 0, start
    pat = re.compile(r"</?section\b")
    while True:
        m = pat.search(doc, i)
        if not m:
            return None
        if doc[m.start():m.start() + 2] == "</":
            depth -= 1
            if depth == 0:
                return start, doc.index(">", m.start()) + 1
        else:
            depth += 1
        i = m.end()


def grid_span(group: str) -> tuple[int, int] | None:
    """组内 .set-units-grid 的开闭位置（含标签本身）。"""
    i = group.find('<div class="set-units-grid">')
    if i < 0:
        return None
    depth, j = 0, i
    pat = re.compile(r"</?div\b")
    while True:
        m = pat.search(group, j)
        if not m:
            return None
        if group.startswith("</", m.start()):
            depth -= 1
            if depth == 0:
                return i, group.index(">", m.start()) + 1
        else:
            depth += 1
        j = m.end()


# ── 主流程 ──────────────────────────────────────────────────────────────
def load_sets() -> list[dict]:
    d = json.loads(SETS_JSON.read_text(encoding="utf-8"))
    return d["sets"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", action="append", default=None, help="只处理指定套装 slug")
    ap.add_argument("--check", action="store_true", help="只报差异，不写文件")
    ap.add_argument("--append-only", action="store_true",
                    help="保留已有卡片，只追加清单里新增的分册")
    ap.add_argument("--skip-missing", action="store_true",
                    help="系列页不存在的套装直接跳过（默认报错退出）")
    a = ap.parse_args()

    doc = INDEX.read_text(encoding="utf-8")
    sets = load_sets()
    if a.set:
        want = set(a.set)
        sets = [s for s in sets if s["slug"] in want]
        missing = want - {s["slug"] for s in sets}
        if missing:
            raise SystemExit("series-sets.json 里没有：%s" % ", ".join(sorted(missing)))

    changed, report = 0, []
    for meta in sets:
        page = ROOT / meta["page"] if meta.get("page") else SERIES_DIR / meta["slug"] / "index.html"
        if not page.exists():
            msg = "系列页缺失：%s" % page.relative_to(ROOT)
            if a.skip_missing:
                report.append(("skip", meta["slug"], msg))
                continue
            raise SystemExit(msg)

        units = parse_units(page.read_text(encoding="utf-8"))
        if not units:
            report.append(("warn", meta["slug"], "系列页没有解析到 book-entry"))
            continue

        span = find_group_span(doc, meta["slug"])
        if span is None:
            # 新套装：整组追加到 .set-groups 末尾
            anchor = doc.find('<div class="set-groups">')
            end = doc.find('</div>', anchor)  # 不可靠，改用配平
            depth, i, end = 0, anchor, -1
            pat = re.compile(r"</?div\b")
            while True:
                m = pat.search(doc, i)
                if not m:
                    break
                if doc[m.start():m.start() + 4] == "</di":
                    depth -= 1
                    if depth == 0:
                        end = m.start()
                        break
                else:
                    depth += 1
                i = m.end()
            if end < 0:
                raise SystemExit("定位 .set-groups 失败")
            doc = doc[:end] + group_html(meta, units) + doc[end:]
            changed += 1
            report.append(("new", meta["slug"], "%d 册（整组新增）" % len(units)))
            continue

        start, end = span
        old_group = doc[start:end]
        gs = grid_span(old_group)
        if gs is None:
            report.append(("warn", meta["slug"], "组内没有 .set-units-grid"))
            continue

        new_cards = "\n".join(card_html(u) for u in units)
        if a.append_only:
            have = set(re.findall(r'data-slug="([^"]+)"', old_group))
            fresh = [u for u in units if u["slug"] not in have]
            if not fresh:
                report.append(("same", meta["slug"], "无新增"))
                continue
            new_cards = old_group[gs[0]:gs[1]].rstrip()
            new_cards = new_cards[:new_cards.rfind("</div>")]
            new_cards += "\n" + "\n".join(card_html(u) for u in fresh) + "\n          </div>"
            new_group = old_group[:gs[0]] + new_cards + old_group[gs[1]:]
            doc = doc[:start] + new_group + doc[end:]
            changed += 1
            report.append(("add", meta["slug"], "+%d 册" % len(fresh)))
            continue

        new_grid = '<div class="set-units-grid">\n%s\n          </div>' % new_cards
        new_group = old_group[:gs[0]] + new_grid + old_group[gs[1]:]
        # 组名/册数一并对齐
        new_group = re.sub(r'(<span class="set-group-name">)[^<]*(</span>)',
                           lambda m: m.group(1) + esc(meta["name"]) + m.group(2),
                           new_group, count=1)
        new_group = re.sub(r'(<span class="set-group-count">)[^<]*(</span>)',
                           lambda m: m.group(1) + "%d 册" % len(units) + m.group(2),
                           new_group, count=1)

        old_card_n = len(re.findall(r'class="archive-card unit-card"', old_group))
        if new_group == old_group:
            report.append(("same", meta["slug"], "%d 册" % len(units)))
            continue
        doc = doc[:start] + new_group + doc[end:]
        changed += 1
        report.append(("sync", meta["slug"],
                       "%d 册（原 %d 张卡）" % (len(units), old_card_n)))

    print("─" * 62)
    for kind, slug, msg in report:
        mark = {"new": "＋", "add": "＋", "sync": "✓", "same": "·",
                "skip": "-", "warn": "!"}.get(kind, "?")
        print("%s %-28s %s" % (mark, slug, msg))
    print("─" * 62)
    print("变更 %d 个组 / 共 %d 个套装" % (changed, len(sets)))

    # 缺封面的册：卡片会显示素封兜底，但最好补上
    lacks = []
    for meta in sets:
        page = ROOT / meta["page"] if meta.get("page") else SERIES_DIR / meta["slug"] / "index.html"
        if not page.exists():
            continue
        for u in parse_units(page.read_text(encoding="utf-8")):
            if not (COVERS / ("%s.jpg" % u["slug"])).exists():
                lacks.append((meta["slug"], u["slug"], u["title"]))
    if lacks:
        print("\n缺封面 %d 张（卡片会走素封兜底，建议补）：" % len(lacks))
        for s, slug, t in lacks[:12]:
            print("  %-22s %s" % (slug, t[:28]))

    if a.check or not changed:
        return 0
    INDEX.write_text(doc, encoding="utf-8")
    print("\n已写入 %s" % INDEX.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
