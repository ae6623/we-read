#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""系列流程唯一入口：拆书收尾、日常体检都走这里，不要再各写各的临时脚本。

为什么有它：
  以前「拆一本套装」要分好几步（生成系列页 → 改标题链接 → 跑 sync → 补封面），
  任何一步漏了，首页系列 Tab 就看不到，或者标题点了跳微信读书搜索页。
  这个脚本把「规范化 + 同步 + 体检」合成一条命令，幂等，可反复跑。

用法：
  python3 tools/series.py --audit              # 全量体检：所有套装是否已进首页/封面齐/标题本地化
  python3 tools/series.py --set <slug>         # 单套装：规范化系列页 + 同步卡片 + 体检
  python3 tools/series.py --all                # 所有套装：规范化 + 同步 + 体检
  python3 tools/series.py --set <slug> --check # 只体检，不写任何文件
  python3 tools/series.py --audit --strict     # 体检发现问题时退出码 1（供 CI/收尾断言）

它依次做三件事：
  1) 规范化系列页标题：每个 .book-entry 的标题 <a> 必须指本地页
     （combined > overview > outline），微信读书只作次级「原站 ↗」；
     顺手修掉历史上「主链接把 weread-jump 包进去」的畸形（幂等）。
  2) 调 tools/sync_set_cards.py 把分册写进 index.html 的系列面板（幂等）。
  3) 体检并打印 PASS/FAIL：组是否在首页、卡片数是否对齐、封面是否齐、标题是否本地化、
     本地页是否存在。

退出码：0 全通过；1 有 FAIL（仅 --strict 时对 --audit 生效）。
"""
from __future__ import annotations

import argparse
import html as H
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sync_set_cards as S  # noqa: E402

ROOT = S.ROOT
INDEX = S.INDEX
SETS_JSON = S.SETS_JSON
SERIES_DIR = S.SERIES_DIR
BOOKS = S.BOOKS
COVERS = S.COVERS

ART_RE = re.compile(r'<article class="book-entry"[^>]*>.*?</article>', re.S)
H3_RE = re.compile(r"<h3>(.*?)</h3>", re.S)
BOOK_SLUG_RE = re.compile(r"\.\./\.\./books/([^/]+)/")
WEREAD_RE = re.compile(r"https://weread\.qq\.com[^\"'\s]*")


# ── 系列页：标题本地化 ──────────────────────────────────────────────────
def pick_local(slug: str) -> str | None:
    """单册本地页（相对 series/<set>/ 两级）；优先级 combined > overview > outline。"""
    for name in ("combined.html", "overview.html", "outline.html"):
        if (BOOKS / slug / name).exists():
            return "../../books/%s/%s" % (slug, name)
    return None


def normalize_page(page: Path) -> tuple[int, list[str]]:
    """把每个 book-entry 的 <h3> 重建成：标题→本地页 + 次级「原站 ↗」。

    重建式处理天然幂等，也能吃掉历史畸形（嵌套 weread-jump / 游离 </a>）。
    返回 (改动条数, 无本地页的 slug 列表)。
    """
    if not page.exists():
        return 0, []
    src = page.read_text(encoding="utf-8")
    changed = 0
    no_local: list[str] = []

    def repl(m: re.Match) -> str:
        nonlocal changed
        block = m.group(0)
        sm = BOOK_SLUG_RE.search(block)
        if not sm:
            return block
        slug = sm.group(1)
        local = pick_local(slug)
        wm = WEREAD_RE.search(block)
        weread = H.unescape(wm.group(0)) if wm else ""
        if local is None:
            no_local.append(slug)

        href = local or weread
        if not href:
            return block
        h3m = H3_RE.search(block)
        if not h3m:
            return block

        # 从现有 h3 里抽干净标题：先摘掉原站链接，再剥标签
        inner = re.sub(r'<a class="weread-jump"[^>]*>.*?</a>', "", h3m.group(1), flags=re.S)
        title = re.sub(r"<[^>]+>", "", inner).replace("原站 ↗", "").strip()
        title = H.unescape(title)

        # 把 data-weread-id 保留到「原站」链接上（标题本地化后主链接不再需要它）
        bid_m = re.search(r'data-weread-id="([^"]+)"', block)
        bid_attr = ' data-weread-id="%s"' % S.esc(bid_m.group(1)) if bid_m else ""

        jump = ""
        if local and weread:
            jump = ' <a class="weread-jump" href="%s" target="_blank" rel="noopener"%s>原站 ↗</a>' % (
                S.esc(weread), bid_attr)
        if local:
            new_h3 = '<h3><a href="%s">%s</a>%s</h3>' % (S.esc(href), S.esc(title), jump)
        else:
            # 无本地页：标题只能指原站，保留 data-weread-id 供 weread-link 兜底
            new_h3 = '<h3><a href="%s"%s>%s</a></h3>' % (S.esc(href), bid_attr, S.esc(title))
        new_block = block[: h3m.start()] + new_h3 + block[h3m.end():]
        if new_block != block:
            changed += 1
        return new_block

    new_src = ART_RE.sub(repl, src)
    if new_src != src:
        page.write_text(new_src, encoding="utf-8")
    return changed, no_local


# ── 同步（转调 sync_set_cards.py）────────────────────────────────────────
def run_sync(slug: str, check: bool) -> int:
    cmd = [sys.executable, str(HERE / "sync_set_cards.py"), "--set", slug]
    if check:
        cmd.append("--check")
    r = subprocess.run(cmd, capture_output=True, text=True)
    tail = (r.stdout or "").strip().splitlines()
    for line in tail[-3:]:
        print("    " + line)
    return r.returncode


# ── 体检 ────────────────────────────────────────────────────────────────
def audit_one(meta: dict, doc: str) -> list[tuple[str, str]]:
    """返回 [(级别, 说明)]，级别 PASS / WARN / FAIL。"""
    slug = meta["slug"]
    page = ROOT / meta["page"] if meta.get("page") else SERIES_DIR / slug / "index.html"
    out: list[tuple[str, str]] = []

    if not page.exists():
        return [("FAIL", "系列页缺失：%s" % page.relative_to(ROOT))]

    html_txt = page.read_text(encoding="utf-8")
    units = S.parse_units(html_txt)
    if not units:
        return [("FAIL", "系列页解析不到 book-entry")]

    # 1) 是否进首页系列面板 + 卡片数对齐
    span = S.find_group_span(doc, slug)
    if span is None:
        out.append(("FAIL", "未进首页系列 Tab（跑本脚本 --set %s 即可）" % slug))
    else:
        group = doc[span[0]:span[1]]
        n_card = len(re.findall(r'class="archive-card unit-card"', group))
        if n_card == len(units):
            out.append(("PASS", "首页系列卡 %d/%d" % (n_card, len(units))))
        else:
            out.append(("FAIL", "首页系列卡 %d 张，系列页 %d 册（不一致）" % (n_card, len(units))))

    # 2) 标题是否本地化（只针对「有本地页」的册；无本地页只能跳原站，不算错）
    bad_titles = []
    for block in ART_RE.findall(html_txt):
        sm = BOOK_SLUG_RE.search(block)
        if not sm or pick_local(sm.group(1)) is None:
            continue
        h3 = H3_RE.search(block)
        if not h3:
            continue
        ma = re.search(r'<a\s+href="([^"]+)"', h3.group(1))
        if ma and ma.group(1).startswith("https://weread.qq.com"):
            bad_titles.append(sm.group(1))
    if bad_titles:
        out.append(("FAIL", "有本地页却仍外链微信读书：%s" % ", ".join(bad_titles[:4])))
    else:
        out.append(("PASS", "标题已本地化"))

    # 3) 本地页存在性
    miss_local = [u["slug"] for u in units if S.resolve_href(u)[1] == "原站"]
    if miss_local:
        out.append(("WARN", "无本地页（只能跳原站）：" + ", ".join(miss_local)))
    else:
        out.append(("PASS", "单册本地页齐全"))

    # 4) 封面
    miss_cv = [u["slug"] for u in units if not (COVERS / ("%s.jpg" % u["slug"])).exists()]
    if miss_cv:
        out.append(("WARN", "缺封面 %d 张（走素封兜底）：%s" % (len(miss_cv), ", ".join(miss_cv[:4]))))
    else:
        out.append(("PASS", "封面齐全 %d 张" % len(units)))

    return out


# ── 主流程 ──────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description="系列流程唯一入口：规范化 + 同步 + 体检")
    ap.add_argument("--set", action="append", default=None, help="只处理指定套装 slug")
    ap.add_argument("--all", action="store_true", help="处理全部套装")
    ap.add_argument("--audit", action="store_true", help="只体检（默认全部套装）")
    ap.add_argument("--check", action="store_true", help="只体检，不写任何文件")
    ap.add_argument("--strict", action="store_true", help="有 FAIL 时退出码置 1")
    a = ap.parse_args()

    sets = S.load_sets()
    if a.set:
        want = set(a.set)
        sets = [s for s in sets if s["slug"] in want]
        missing = want - {s["slug"] for s in sets}
        if missing:
            raise SystemExit("series-sets.json 里没有：%s" % ", ".join(sorted(missing)))
    elif not (a.all or a.audit):
        ap.error("请指定 --set <slug> / --all / --audit 之一")

    doc = INDEX.read_text(encoding="utf-8")
    only_audit = a.check or a.audit
    fails = 0

    for meta in sets:
        slug = meta["slug"]
        page = ROOT / meta["page"] if meta.get("page") else SERIES_DIR / slug / "index.html"
        print("\n▶ %s  (%s)" % (meta.get("name", slug), slug))

        if not only_audit:
            n, no_local = normalize_page(page)
            if n:
                print("    · 规范化标题链接 %d 处" % n)
            rc = run_sync(slug, check=False)
            if rc != 0:
                print("    ! sync 失败（退出码 %d）" % rc)

        rows = audit_one(meta, doc)
        for level, msg in rows:
            mark = {"PASS": "✓", "WARN": "!", "FAIL": "✗"}[level]
            print("    %s %s" % (mark, msg))
            if level == "FAIL":
                fails += 1
        # 体检用最新 doc（同步后可能已变）
        doc = INDEX.read_text(encoding="utf-8")

    # 提示：index.html 里存在、但 series-sets.json 没登记的组（如手写的 qingyouji）
    known = {s["slug"] for s in S.load_sets()}
    in_html = set(re.findall(r'data-units="([^"]+)"', doc))
    untracked = sorted(in_html - known)
    if untracked:
        print("\n· 首页有组但未在 series-sets.json 登记（手写组，本脚本不动）：%s" % ", ".join(untracked))

    print("\n" + "─" * 56)
    if fails:
        print("体检：%d 项 FAIL" % fails)
        return 1 if a.strict else 0
    print("体检：全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
