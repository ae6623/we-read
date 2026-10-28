"""「全书导图」概念退役，统一改叫「精读」（2026-10-28 用户定调）。

用户原话：把全书导图当做精读就好了，以后没有按照日期的精读笔记了，
只有全书导图，全书导图的概念不需要了，它就是精读。

就地处理三类页面（全部幂等）：

1. index.html
   - 通读 tab preread-card：`全书导图 ↗` 链接 → 绿色 `精读 ↗`
     （card-link-strong 棕色 → card-link-green）
   - 精读 tab 日期笔记卡：删「本书全书导图」虚线胶囊（mm-note-link），
     书名 <h3> 改为链接直指 mindmap.html（book-jd-link）
   - homepage-reading.css 引用版本号 +1

2. books/*/mindmap.html（55 本）
   - title / h1 的「全书导图」→「精读」
   - meta description「全书主干导图」→「全书精读」
   - eyebrow「MIND MAP · AFTER THINKING」→「CLOSE READING · AFTER THINKING」

3. books/*/overview.html（55 本）
   - 顶部入口「→ 全书导图：主干重排 · …」→「→ 精读：主干重排 · …」

用法：
    python tools_mindmap_to_jingdu.py            # 预演
    python tools_mindmap_to_jingdu.py --write    # 落盘
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BOOKS = REPO / "reading-notes" / "books"
WRITE = "--write" in sys.argv

PILL = re.compile(
    r'<a class="mm-note-link" href="([^"]+)">本书全书导图 '
    r'<span aria-hidden="true">↗</span></a>\s*')
H3 = re.compile(r"<h3>(.*?)</h3>")


def patch_index(s: str):
    pill = name = green = 0
    # 1) 精读卡（archive-card）：删胶囊 + 书名变链接
    out, pos = [], 0
    for m in re.finditer(r'<article class="archive-card"', s):
        if m.start() < pos:
            continue
        end = s.find("</article>", m.start())
        if end < 0:
            continue
        block = s[m.start():end + len("</article>")]
        nb, done = block, False
        pm = PILL.search(nb)
        if pm:
            href = pm.group(1)
            nb = PILL.sub("", nb)
            h3 = H3.search(nb)
            if h3 and "mindmap.html" not in h3.group(1):
                nb = (nb[:h3.start()]
                      + '<h3><a class="book-jd-link" href="%s">%s</a></h3>' % (href, h3.group(1))
                      + nb[h3.end():])
                name += 1
                done = True
            pill += 1
        out.append(s[pos:m.start()])
        out.append(nb)
        pos = end + len("</article>")
    out.append(s[pos:])
    s = "".join(out)

    # 兜底：article 外结构变化导致的残留胶囊
    while True:
        pm = PILL.search(s)
        if not pm:
            break
        s = PILL.sub("", s, count=1)
        pill += 1

    # 2) 通读卡：文字改「精读」+ 绿色类
    s2 = s.replace('全书导图 <span aria-hidden="true">↗</span></a>',
                   '精读 <span aria-hidden="true">↗</span></a>')
    s = s2
    s, n = re.subn(r'(<a class="card-link) card-link-strong(" href="[^"]*mindmap\.html")',
                   r"\1 card-link-green\2", s)
    green = n

    # 3) CSS 版本号
    s = s.replace("homepage-reading.css?v=20261028d", "homepage-reading.css?v=20261028e")
    return s, {"pill": pill, "name": name, "green": green}


def patch_mindmap(s: str):
    n = 0
    for a, b in (("全书主干导图", "全书精读"),
                 ("全书导图", "精读"),
                 ("MIND MAP · AFTER THINKING", "CLOSE READING · AFTER THINKING")):
        if a in s:
            n += s.count(a)
            s = s.replace(a, b)
    return s, n


def patch_overview(s: str):
    n = s.count("→ 全书导图：")
    return s.replace("→ 全书导图：", "→ 精读："), n


def main():
    tot = {"mm": 0, "ov": 0}
    p = REPO / "index.html"
    s = p.read_text(encoding="utf-8")
    s2, st = patch_index(s)
    if s2 != s:
        print("index.html：胶囊删 %d、书名加链接 %d、通读卡绿色精读链接 %d"
              % (st["pill"], st["name"], st["green"]))
        if WRITE:
            p.write_text(s2, encoding="utf-8", newline="\n")

    for p in sorted(BOOKS.glob("*/mindmap.html")):
        s = p.read_text(encoding="utf-8")
        s2, n = patch_mindmap(s)
        if s2 != s:
            tot["mm"] += 1
            if WRITE:
                p.write_text(s2, encoding="utf-8", newline="\n")
    for p in sorted(BOOKS.glob("*/overview.html")):
        s = p.read_text(encoding="utf-8")
        s2, n = patch_overview(s)
        if s2 != s:
            tot["ov"] += 1
            if WRITE:
                p.write_text(s2, encoding="utf-8", newline="\n")

    print("[%s] mindmap 改名 %d 本；overview 入口改名 %d 本"
          % ("WRITE" if WRITE else "PREVIEW", tot["mm"], tot["ov"]))


if __name__ == "__main__":
    main()
