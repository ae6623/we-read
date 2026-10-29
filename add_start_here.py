#!/usr/bin/env python3
"""IA-05 单书页「从这里开始」：给存量 overview.html 插入首屏导航块（2026-10-29）。

- 链接按本书数据可用性生成（存在才挂，防死链）：mindmap.html → 精读；outline.html → AI 大纲
- 插入位置：note-head 之后（首屏可见）；同时给 head 加 start-here.css 引用
- 幂等：已含 .start-here 的页面跳过
用法：python3 add_start_here.py [--write]
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BOOKS = HERE / "reading-notes" / "books"
CSS_LINK = '<link rel="stylesheet" href="../../../assets/css/start-here.css">'


def block(has_mindmap: bool, has_outline: bool, n_note: int = 0,
          book_dir: Path | None = None) -> str:
    what = "全书结构与每一章讲什么——先看命题与一句话主旨，再按章节展开全书脉络"
    links = []
    if has_mindmap:
        links.append('<a href="mindmap.html">下一步：精读 · 全书主干 →</a>')
    if has_outline:
        links.append('<a href="outline.html">AI 大纲 · 逐章逐条 →</a>')
    # 无精读页的书（deep-read 保留为独立页）才挂深读链接；其余统一指向精读页
    if ((not has_mindmap) and book_dir is not None
            and (book_dir / "notes" / "deep-read.html").exists()):
        links.append('<a href="notes/deep-read.html">逐章深读（含 AI 追问） →</a>')
    link_html = "".join('<span>%s</span>' % a for a in links)
    return (
        '<nav class="start-here" aria-label="从这里开始">\n'
        '      <p class="sh-title">从这里开始</p>\n'
        '      <p>这一页解决：%s。</p>\n'
        '      <p class="sh-links">%s</p>\n'
        '    </nav>\n' % (what, link_html)
    )


def process(f: Path):
    html = f.read_text(encoding="utf-8")
    if "start-here" in html:
        return None
    book_dir = f.parent
    has_mm = (book_dir / "mindmap.html").exists()
    has_ol = (book_dir / "outline.html").exists()
    n_note = len(list((book_dir / "notes").glob("2026-*.html"))) if (book_dir / "notes").exists() else 0
    if not (has_mm or has_ol or n_note):
        return "no-links"

    # head 加 CSS（优先挂 reading-overview.css link 后；轻游记等简版挂任意 stylesheet link 后）
    if "start-here.css" not in html:
        m = re.search(r'<link rel="stylesheet" href="[^"]*reading-overview\.css">', html) \
            or re.search(r'<link rel="stylesheet" href="[^"]*">', html) \
            or re.search(r'<link [^>]*rel="stylesheet"[^>]*>', html)
        if not m:
            return "no-css-anchor"
        html = html[:m.end()] + "\n" + CSS_LINK + html[m.end():]

    # </header> 后插块（note-head 版式）；无 header 的简版用首个 meta 段落兜底
    m = re.search(r"</header>\n?", html)
    if m:
        pos = m.end()
    else:
        m2 = re.search(r'<p class="meta">.*?</p>\n?', html, re.S)
        if not m2:
            return "no-anchor"
        pos = m2.end()
    html = html[:pos] + "  " + block(has_mm, has_ol, n_note, book_dir) + html[pos:]
    f.write_text(html, encoding="utf-8", newline="\n")
    tags = "".join(c for c, y in (("精", has_mm), ("纲", has_ol), ("深", n_note)) if y)
    return tags


def main():
    write = "--write" in sys.argv
    files = sorted(BOOKS.glob("*/overview.html"))
    done, skip, other = 0, 0, {}
    for f in files:
        r = process(f)
        if r is None:
            skip += 1
        elif r in ("no-links", "no-anchor", "no-css-anchor", "no-header"):
            other.setdefault(r, []).append(f.parent.name)
            if write:
                print("!!", f.parent.name, r)
        else:
            done += 1
    print("共 %d 本 overview；%s 插入 %d 本，已存在跳过 %d 本，失败 %d 本" %
          (len(files), "已" if write else "[DRY-RUN 会]", done, skip, len(other)))
    for k, v in other.items():
        print("  %s: %s" % (k, v[:6]))


if __name__ == "__main__":
    main()
