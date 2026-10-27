#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""AI 大纲「全文通读」入库 + 通读页渲染（默认折叠、点击展开）。

链路与 gen_aiqa_from_outline.py 一致（沙箱可直接跑：纯本地文件 + REST 单次提交）：

  扫描站点仓 outline.html（AI 大纲一手数据，含要点 + 第 4 层原句摘录）
    → 解析为 章 / 小节 / 要点 / 原句
    → 写本地 JSON + SQLite（book_outline 表）
    → 注入 overview.html 的「章节导读」区块（取消 pts[:4] / picked[:2] 截断）
    → 所有变更一次性提交发布（注意访问频率：只打 1 次提交）

用法：
  python3.11 gen_outline_full.py --dry-run                 # 只看会改多少，不落盘不发布
  python3.11 gen_outline_full.py --publish                 # 入库 + 注入 + 发布
  python3.11 gen_outline_full.py --slug <slug> --publish   # 单本
  python3.11 gen_outline_full.py --limit 3 --publish       # 先试 3 本
"""
from __future__ import annotations

import argparse
import html as H
import json
import os
import re
import sys
import time
from pathlib import Path

DEFAULT_SITE_REPO = "/workspace/we-read"
DEFAULT_OUT_DIR = Path(__file__).resolve().parent / "data" / "outline_full"
BOOKS_DIR = "reading-notes/books"

CH_ITEM_RE = re.compile(r'<details class="ch-item"[\s\S]*?</details>')
CH_T_RE = re.compile(r'<span class="ch-t">([\s\S]*?)</span>')


def esc(s) -> str:
    return H.escape((s or "").strip(), quote=False)


def _norm(s) -> str:
    """章节标题归一化，用于 overview / outline 对账。"""
    return re.sub(r"\s+", "", (s or "")).strip("《》 ").lower()


# ------------------------------------------------------------------ 发现
def discover(site_repo: str):
    """返回 [(slug, title)]：同时具备 outline.html（数据源）与 overview.html（注入目标）。"""
    base = os.path.join(site_repo, BOOKS_DIR)
    if not os.path.isdir(base):
        return []
    out = []
    for slug in sorted(os.listdir(base)):
        d = os.path.join(base, slug)
        if not os.path.isdir(d):
            continue
        if not (os.path.exists(os.path.join(d, "outline.html"))
                and os.path.exists(os.path.join(d, "overview.html"))):
            continue
        out.append((slug, _title_of(d, slug)))
    return out


def _title_of(d: str, slug: str) -> str:
    for f in ("overview.html", "outline.html"):
        p = os.path.join(d, f)
        if not os.path.exists(p):
            continue
        try:
            t = open(p, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        m = re.search(r"<h1>\s*《([^》]+)》", t)
        if m:
            return m.group(1).strip()
        m = re.search(r"<title>([^<]+)</title>", t)
        if m:
            v = re.split(r"[｜|]", m.group(1))[0].strip().strip("《》").strip()
            if v:
                return v
    return slug


# ------------------------------------------------------------------ 解析
def parse_full_outline(path: str):
    """解析站点 AI 大纲页：章(details.ch) → 小节(div.sec) → 要点(ul.point>li) → 原句(ul.quote>li)。"""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("! 需要 beautifulsoup4：pip3 install beautifulsoup4")
        return []
    try:
        soup = BeautifulSoup(open(path, encoding="utf-8", errors="ignore").read(), "html.parser")
    except Exception as e:
        print("  ! 读取失败 %s: %s" % (path, e))
        return []

    def _points(scope):
        pts = []
        for li in scope.select("ul.point > li"):
            b = li.find("b")
            quotes = [q.get_text(" ", strip=True) for q in li.select("ul.quote li")]
            quotes = [q for q in quotes if q]
            if b is not None:
                t = b.get_text(" ", strip=True)
            else:
                t = li.get_text(" ", strip=True)
                for q in quotes:          # 无 <b> 时原文混在一起，剥掉摘录
                    t = t.replace(q, " ")
            t = re.sub(r"\s+", " ", t).strip(" 　")
            if t:
                pts.append({"text": t, "quotes": quotes})
        return pts

    chs = []
    for i, d in enumerate(soup.select("details.ch"), 1):
        sm = d.find("summary")
        title = sm.get_text(" ", strip=True) if sm else ("第 %d 章" % i)
        secs = []
        sec_divs = d.select("div.sec")
        if sec_divs:
            for sd in sec_divs:
                hd = sd.find(["h4", "h5", "h3"])
                h = hd.get_text(" ", strip=True) if hd else ""
                pts = _points(sd)
                if pts:
                    secs.append({"h": h, "points": pts})
        if not secs:                       # 无 sec 分节的书：整章视为一个小节
            pts = _points(d)
            if pts:
                secs.append({"h": "", "points": pts})
        if secs:
            chs.append({"no": i, "title": title, "secs": secs})
    return chs


# ------------------------------------------------------------------ 渲染
def _quota(n_ch: int, budget: int = 500):
    """按章节数决定每章要点配额：章少的书给足，章多的书收紧（防单页爆炸）。"""
    if n_ch <= 20:
        per = 40
    elif n_ch <= 60:
        per = 20
    else:
        per = 8
    return per, budget


def build_ch_body(ch: dict, max_points: int = 40, first_open: int = 1):
    """章节展开后的正文：按小节分组折叠（第一个小节默认展开），要点渲染到 max_points。

    返回 (html, 实际渲染要点数)。max_points<=0 时只输出统计行 + 引导语。
    """
    secs = ch.get("secs") or []
    npts = sum(len(s["points"]) for s in secs)
    nq = sum(len(p.get("quotes") or []) for s in secs for p in s["points"])
    head = ('        <p class="ch-stat">共 %d 个小节 · %d 条要点 · %d 句原句摘录</p>'
            % (len(secs), npts, nq))
    if max_points <= 0:
        return (head + '\n        <p class="ch-more">'
                '（要点详见本书 AI 大纲页）</p>'), 0

    out = [head]
    used = 0
    for si, s in enumerate(secs, 1):
        pts = s["points"]
        if used >= max_points:
            out.append('        <p class="ch-more">（其余 %d 条要点见本书 AI 大纲页）</p>'
                       % (npts - used))
            break
        take = pts[: max_points - used]
        used += len(take)
        solo = (len(secs) == 1 and not s.get("h"))
        op = " open" if (si <= first_open or solo) else ""
        label = s.get("h") or "本章要点"
        out.append('        <details class="ch-sec"%s><summary><span class="sec-h">%s</span>'
                   '<span class="sec-count">%d 条</span></summary>' % (op, esc(label), len(pts)))
        out.append('          <ol class="ch-secs">')
        for p in take:
            qs = p.get("quotes") or []
            qhtml = ""
            if qs:
                qhtml = '<ul class="ch-quote">%s</ul>' % "".join(
                    "<li>「%s」</li>" % esc(x) for x in qs)
            out.append('            <li>%s%s</li>' % (esc(p["text"]), qhtml))
        out.append('          </ol>')
        out.append('        </details>')
    return "\n".join(out), used


def _ch_item_spans(html_text: str):
    """定位每个 <details class="ch-item"> 的完整区间（配对计数，兼容内部嵌套 details）。

    不能用正则非贪婪：章节正文里的小节本身也是 details，非贪婪会在小节闭合处截断。
    """
    spans, pos = [], 0
    while True:
        i = html_text.find('<details class="ch-item"', pos)
        if i < 0:
            break
        depth, j = 0, i
        while True:
            nd = html_text.find("<details", j)
            cd = html_text.find("</details>", j)
            if cd < 0:
                j = len(html_text)
                break
            if 0 <= nd < cd:
                depth += 1
                j = nd + 8
            else:
                depth -= 1
                j = cd + len("</details>")
                if depth == 0:
                    break
        spans.append((i, j))
        pos = j
    return spans


def inject(html_text: str, chapters: list, budget: int = 500):
    """逐章替换 <details class="ch-item"> 的 ch-body（幂等，按标题对账，失败按序号回退）。

    渲染受全书预算约束：章少的书每章给足，章多的书收紧，避免单页 DOM 爆炸。
    """
    by_title = {}
    for c in chapters:
        by_title.setdefault(_norm(c["title"]), c)
    n_ch = len(chapters)
    per, budget = _quota(n_ch, budget)

    out, pos, n, used = [], 0, 0, 0
    for i, (start, stop) in enumerate(_ch_item_spans(html_text)):
        block = html_text[start:stop]
        mt = CH_T_RE.search(block)
        ch = by_title.get(_norm(mt.group(1))) if mt else None
        if ch is None and i < len(chapters):
            ch = chapters[i]
        if ch is None:
            continue
        idx = block.find('<div class="ch-body">')
        end = block.rfind("</details>")
        if idx < 0 or end < idx:
            continue
        cap = min(per, budget - used)
        body, cnt = build_ch_body(ch, max(cap, 0))
        used += cnt
        new_block = (block[:idx] + '<div class="ch-body">\n' + body + "\n        "
                     + block[end:])
        out.append(html_text[pos:start])
        out.append(new_block)
        pos = stop
        n += 1
    out.append(html_text[pos:])
    return "".join(out), n


def inject_create(html_text: str, chapters: list, budget: int = 500):
    """#toc 平铺列表模板（一章一行、无章节导读区块）：在 #toc section 尾部插入逐章详读块。

    块用 <!-- ch-detail:begin/end --> 包住，便于幂等替换。
    """
    html_text = re.sub(r"\s*<!-- ch-detail:begin -->[\s\S]*?<!-- ch-detail:end -->",
                       "", html_text)
    i = html_text.find('id="toc"')
    if i < 0:
        return html_text, 0
    sec_end = html_text.find("</section>", i)
    if sec_end < 0:
        return html_text, 0

    per, budget = _quota(len(chapters), budget)
    parts = ['<!-- ch-detail:begin -->', '      <div class="toc-detail">',
             '        <h3>逐章详读 · AI 大纲全文</h3>',
             '        <p class="small">AI 大纲原始要点与书中原句摘录（第 4 层），点击章节展开。</p>']
    used = 0
    for c in chapters:
        cap = min(per, budget - used)
        body, cnt = build_ch_body(c, max(cap, 0))
        used += cnt
        parts.append('        <details class="ch-item"><summary>'
                     '<span class="ch-no">%d</span><span class="ch-t">%s</span>'
                     '<span class="caret">›</span></summary>' % (c["no"], esc(c["title"])))
        parts.append('          <div class="ch-body">')
        parts.append(body)
        parts.append("          </div></details>")
    parts += ["      </div>", "      <!-- ch-detail:end -->"]
    return html_text[:sec_end] + "\n".join(parts) + "\n    " + html_text[sec_end:], len(chapters)


# ------------------------------------------------------------------ 入库
def save_local(slug: str, title: str, chapters: list) -> int:
    """写本地 JSON + SQLite（book_outline 表）。返回要点条数。"""
    try:
        DEFAULT_OUT_DIR.mkdir(parents=True, exist_ok=True)
        (DEFAULT_OUT_DIR / ("%s.json" % slug)).write_text(
            json.dumps({"slug": slug, "book": title, "chapters": chapters},
                       ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as e:
        print("  ! 写 JSON 失败: %s" % e)
    n = 0
    try:
        import weread_store
        n = weread_store.save_book_outline(slug, title, chapters)
    except Exception as e:
        print("  ! 写 SQLite 失败: %s" % e)
    return n


# ------------------------------------------------------------------ 发布
def _gh_api_client():
    import subprocess
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from gh_api import GhApi
    url = subprocess.check_output(
        ["git", "-C", DEFAULT_SITE_REPO, "config", "--get", "remote.origin.url"],
        stderr=subprocess.DEVNULL).decode().strip()
    m = re.search(r"(gh[op]_[A-Za-z0-9]+)@github", url)
    if not m:
        raise RuntimeError("无法从 we-read 远端取出令牌")
    return GhApi("ae6623", "we-read", m.group(1), proxy="")


def batch_publish(files: dict, message: str, dry_run: bool):
    """多文件单次提交（GitHub REST，注意频率：全程只调一次）。"""
    if not files:
        print("发布：无变更")
        return
    if dry_run:
        print("发布：[dry-run] 将提交 %d 个文件" % len(files))
        return
    api = _gh_api_client()
    # 节流：publish_paths 每个文件要打一次 blob 接口，这里把速率压到约 3 req/s，
    # 避免触发 GitHub 限流（文件多时尤其重要）。
    _orig_blob = api.create_blob

    def _slow_blob(data, _o=_orig_blob):
        time.sleep(0.35)
        return _o(data)

    api.create_blob = _slow_blob
    t0 = time.time()
    ok, msg, det = api.publish_paths(files, message)
    print("发布：ok=%s msg=%s detail=%s 用时 %.0fs"
          % (ok, msg, str(det)[:120], time.time() - t0))


# ------------------------------------------------------------------ 主流程
CSS_PATCH = """
/* AI 大纲全文通读（章节导读·完整版）：章节折叠 → 小节折叠，点击展开 */
.ch-stat{margin:.2em 0 .5em;font-size:.76rem;color:var(--muted)}
.ch-sec{margin:6px 0;border-left:2px solid var(--line);padding-left:10px}
.ch-sec>summary{display:flex;gap:8px;align-items:baseline;cursor:pointer;list-style:none;font-size:.84rem;color:var(--green)}
.ch-sec>summary::-webkit-details-marker{display:none}
.sec-h{font-weight:600}
.sec-count{margin-left:auto;font-size:.74rem;color:var(--muted);flex:none}
.ch-quote{margin:.2em 0 .4em;padding-left:1em;list-style:none;border-left:2px dotted var(--line);font-size:.76rem;color:#8a8272}
.ch-quote li{margin:.15em 0}
.ch-more{font-size:.76rem;color:var(--muted);font-style:italic}
"""


def ensure_css(site_repo: str, files: dict):
    """把 .ch-sec/.ch-quote 等样式补到两套模板的 CSS（幂等）。"""
    for rel in ("assets/css/reading-overview.css", "assets/css/reading-note.css"):
        p = os.path.join(site_repo, rel)
        if not os.path.exists(p):
            continue
        s = open(p, encoding="utf-8").read()
        if "ch-sec>summary" in s:
            continue
        files[rel] = s.rstrip("\n") + "\n" + CSS_PATCH


def main(argv=None):
    ap = argparse.ArgumentParser(description="AI 大纲全文通读：入库 + 通读页渲染")
    ap.add_argument("--site-repo", default=DEFAULT_SITE_REPO)
    ap.add_argument("--slug", help="只处理指定 slug")
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 本（试跑）")
    ap.add_argument("--budget", type=int, default=500,
                    help="每本书渲染要点总预算（章多则按章节数自动收紧每章配额）")
    ap.add_argument("--create-section", action="store_true",
                    help="对无「章节导读」区块、但有 #toc 平铺列表的页面，新建「逐章详读」块")
    ap.add_argument("--publish", action="store_true", help="提交发布到站点仓")
    ap.add_argument("--dry-run", action="store_true", help="不落盘不发布")
    a = ap.parse_args(argv)

    books = discover(a.site_repo)
    if a.slug:
        books = [b for b in books if b[0] == a.slug]
    if a.limit:
        books = books[: a.limit]
    print("待处理：%d 本" % len(books))

    files, tot_ch, tot_pt = {}, 0, 0
    for slug, title in books:
        d = os.path.join(a.site_repo, BOOKS_DIR, slug)
        ol = os.path.join(d, "outline.html")
        ov = os.path.join(d, "overview.html")
        chapters = parse_full_outline(ol)
        if not chapters:
            print("  - %-46s 大纲解析为空，跳过" % slug[:46])
            continue
        html_text = open(ov, encoding="utf-8", errors="ignore").read()
        new_html, n = inject(html_text, chapters, a.budget)
        if not n and a.create_section:
            new_html, n = inject_create(html_text, chapters, a.budget)
            if n:
                print("  + %-46s 新建「逐章详读」区块 章=%d" % (slug[:46], n))
        if not n:
            print("  - %-46s 通读页无章节导读区块，跳过" % slug[:46])
            continue
        npts = save_local(slug, title, chapters) if not a.dry_run else \
            sum(len(s["points"]) for c in chapters for s in c["secs"])
        if not a.dry_run:
            open(ov, "w", encoding="utf-8").write(new_html)
        files["%s/%s/overview.html" % (BOOKS_DIR, slug)] = new_html
        tot_ch += n
        tot_pt += npts
        print("  ✓ %-46s 章=%2d 要点=%4d" % (slug[:46], n, npts))

    print("合计：注入章节 %d，入库要点 %d，变更文件 %d" % (tot_ch, tot_pt, len(files)))
    ensure_css(a.site_repo, files)
    batch_publish(files, "feat(overview): 章节导读接入 AI 大纲全文通读（入库 book_outline，章节/小节折叠，取消要点截断）",
                  a.dry_run or not a.publish)
    return 0


if __name__ == "__main__":
    sys.exit(main())
