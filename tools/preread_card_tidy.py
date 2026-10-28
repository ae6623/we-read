"""首页通读卡精简（2026-10-28 用户反馈）：

1. 卡片标题（书名 h3）包链接 → 全书视角页（原「全书视角 ↗」的 href），
   底部 action 行的「全书视角 ↗」删除——标题即入口，不再重复。
2. 「下载 EPUB ↓」隐藏（下载产物不可用），直接从 action 行移除节点。
3. 「精读 ↗」从 action 行末尾移到最前。

处理对象：index.html 全部 78 张 preread-card。幂等。
    python tools_preread_card_tidy.py            # 预演
    python tools_preread_card_tidy.py --write    # 落盘
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INDEX = REPO / "index.html"
WRITE = "--write" in sys.argv

CARD = re.compile(r"(<!-- preread-card:[^\s]+ -->\s*\n.*?</article>)", re.S)
VIEW = re.compile(r'\s*<a class="card-link card-link-strong" href="([^"]+)">'
                  r'全书视角 <span aria-hidden="true">↗</span></a>\n?')
EPUB = re.compile(r'\s*<a class="download-link" [^>]*>下载 EPUB ↓</a>\n?')
JD = re.compile(r'\s*<a class="card-link card-link-green" href="[^"]*mindmap\.html">'
                r'精读 <span aria-hidden="true">↗</span></a>\n?')
H3 = re.compile(r"<h3>([^<]*)</h3>")


def tidy_card(block: str, st: dict):
    # 1) h3 包链接（用「全书视角」链接的 href；已有链接则跳过）
    href = None
    m = VIEW.search(block)
    if m:
        href = m.group(1)
    h3 = H3.search(block)
    if href and h3 and "<a" not in h3.group(1):
        block = (block[:h3.start()]
                 + '<h3><a class="card-title-link" href="%s">%s</a></h3>'
                 % (href, h3.group(1))
                 + block[h3.end():])
        st["title"] += 1
    # 2) 删「全书视角 ↗」
    block, n = VIEW.subn("", block)
    st["view"] += n
    # 3) 删「下载 EPUB」
    block, n = EPUB.subn("", block)
    st["epub"] += n
    # 4) 精读移到最前：摘出来插到 card-actions 开头
    m = JD.search(block)
    if m:
        jd = m.group(0).strip()
        block = JD.sub("", block)
        anchor = '<div class="card-actions">\n'
        i = block.find(anchor)
        if i >= 0:
            j = i + len(anchor)
            block = block[:j] + "          " + jd + "\n" + block[j:]
            st["jd"] += 1
    return block


def main():
    s = INDEX.read_text(encoding="utf-8")
    st = {"title": 0, "view": 0, "epub": 0, "jd": 0}
    out, pos = [], 0
    for m in CARD.finditer(s):
        out.append(s[pos:m.start()])
        out.append(tidy_card(m.group(1), st))
        pos = m.end()
    out.append(s[pos:])
    s2 = "".join(out)
    print("标题加链 %d、删全书视角 %d、删EPUB %d、精读置前 %d" % (st["title"], st["view"], st["epub"], st["jd"]))
    if s2 != s:
        if WRITE:
            INDEX.write_text(s2, encoding="utf-8", newline="\n")
            print("已写入")
        else:
            print("预演，未落盘")
    else:
        print("无变化（幂等）")


if __name__ == "__main__":
    main()
