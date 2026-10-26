#!/usr/bin/env python3
"""把 reading-notes/books/<slug>/ 的内容抽成统一结构化 JSON（_data/books/<slug>.json）。

设计原则：
- AI 大纲类：直接搬 outline.json（微信读书官方结构），不再解析 HTML。
- 文本类：overview.html / final.html / notes/*.html 的正文按 <section aria-labelledby>
  切成 {id, heading, html}，保真保留 HTML 片段（不强行转 markdown，避免丢信息）。
- 静态展示（nav/footer/样式/卡片）不入 JSON，由模板渲染，不手改页面。

用法：
  python3 scripts/extract_content.py --slug 1984 alaska-qingyouji
  python3 scripts/extract_content.py --all
"""
import re, json, sys, pathlib, argparse

REPO = pathlib.Path(__file__).resolve().parent.parent
BOOKS = REPO / "reading-notes/books"
OUT = REPO / "_data/books"

SCHEMA_VERSION = 1


def read(p):
    return pathlib.Path(p).read_text(encoding="utf-8", errors="ignore")


def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()


def first(pattern, text, default=""):
    m = re.search(pattern, text, re.S)
    return strip_tags(m.group(1)) if m else default


def find_sections(html):
    """按 <section> 平衡匹配切分，返回 [{id, heading, html}]。"""
    out = []
    pos = 0
    while True:
        m = re.search(r"<section\b[^>]*>", html[pos:])
        if not m:
            break
        start = pos + m.start()
        depth = 0
        i = start
        end = len(html)
        while i < len(html):
            m2 = re.search(r"</?section\b[^>]*>", html[i:])
            if not m2:
                break
            tag = m2.group(0)
            i += m2.start()
            depth += -1 if tag.startswith("</") else 1
            i += len(tag)
            if depth == 0:
                end = i
                break
        block = html[start:end]
        om = re.match(r"<section\b([^>]*)>", block)
        attrs = om.group(1) if om else ""
        sid = ""
        m3 = re.search(r'(?:id|aria-labelledby)="([^"]+)"', attrs)
        if m3:
            sid = m3.group(1)
        inner = block[om.end():] if om else block
        if inner.endswith("</section>"):
            inner = inner[: -len("</section>")]
        heading = ""
        hm = re.search(r"<h[1-3][^>]*>(.*?)</h[1-3]>", inner, re.S)
        if hm:
            heading = strip_tags(hm.group(1))
        out.append({"id": sid, "heading": heading, "html": inner.strip()})
        pos = end
    return out


def extract_page(path):
    """提取一个 HTML 页面的元信息 + header + sections。"""
    html = read(path)
    bm = re.search(r"<body[^>]*>(.*)</body>", html, re.S)
    body = bm.group(1) if bm else html

    # header：优先 <header ...>...</header>，否则 body 到第一个 <section> 之前
    hm = re.search(r"<header\b[^>]*>(.*?)</header>", body, re.S)
    if hm:
        header_html = hm.group(1).strip()
    else:
        sm = re.search(r"<section\b", body)
        header_html = body[: sm.start()].strip() if sm else body.strip()

    eyebrow = first(r'<p class="eyebrow">(.*?)</p>', header_html)
    h1 = first(r"<h1[^>]*>(.*?)</h1>", header_html)
    meta_line = first(r'<p class="meta">(.*?)</p>', header_html)

    # 去掉 nav/footer（静态展示，不入内容）
    body_no_nav = re.sub(r"<nav\b.*?</nav>", "", body, flags=re.S)
    body_no_nav = re.sub(r"<footer\b.*?</footer>", "", body_no_nav, flags=re.S)

    return {
        "file": pathlib.Path(path).name,
        "eyebrow": eyebrow,
        "title": h1,
        "meta_line": meta_line,
        "header_html": header_html,
        "sections": find_sections(body_no_nav),
    }


def extract_outline(book_dir):
    oj = book_dir / "outline.json"
    if not oj.exists():
        return None
    try:
        nodes = json.loads(read(oj))
    except Exception as e:
        return {"source": "outline.json", "error": str(e)}
    if not isinstance(nodes, list):
        nodes = []
    levels = {}
    for n in nodes:
        lv = str(n.get("level", ""))
        levels[lv] = levels.get(lv, 0) + 1
    arts = {}
    for name, fn in (("markdown", "outline.md"), ("epub", "outline.epub")):
        if (book_dir / fn).exists():
            arts[name] = fn
    # 只存大纲元信息；nodes 本体留在 outline.json，入库时单独导入 outline_nodes 表，
    # 避免在 _data 里重复 58 本 × ~800 条的节点（会让仓库膨胀到 20MB+）。
    return {
        "source": "outline.json",
        "node_count": len(nodes),
        "level_counts": levels,
        "artifacts": arts,
    }


def extract_book(slug):
    book_dir = BOOKS / slug
    if not book_dir.is_dir():
        return None

    texts = {}
    ov = book_dir / "overview.html"
    if ov.exists():
        texts["overview"] = extract_page(ov)
    fn = book_dir / "final.html"
    if fn.exists():
        texts["final"] = extract_page(fn)

    notes = []
    nd = book_dir / "notes"
    if nd.is_dir():
        for nf in sorted(nd.glob("*.html")):
            page = extract_page(nf)
            page["date"] = nf.stem
            notes.append(page)
    if notes:
        texts["notes"] = notes

    # 书目元数据：从 overview/final 的 title/meta 推
    base = texts.get("overview") or texts.get("final") or {}
    title = base.get("title") or slug
    meta_line = base.get("meta_line", "")
    # author 用「空格+·+空格」分隔首段（避免把名字里的间隔号如「乔治·奥威尔」切坏）
    _parts = re.split(r"\s+·\s+", meta_line) if meta_line else []
    author = _parts[0].strip() if _parts else ""

    data = {
        "schema_version": SCHEMA_VERSION,
        "slug": slug,
        "book": {
            "title": title,
            "author": author,
            "meta_line": meta_line,
            "series": "qingyouji" if "qingyouji" in slug else None,
        },
        "ai_outline": extract_outline(book_dir),
        "texts": texts,
    }
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", nargs="*", default=[])
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    if args.all:
        slugs = sorted(p.name for p in BOOKS.iterdir() if p.is_dir())
    elif args.slug:
        slugs = args.slug
    else:
        print("需要 --slug <slug...> 或 --all")
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    ok, skip = 0, []
    for slug in slugs:
        data = extract_book(slug)
        if data is None:
            skip.append(slug)
            continue
        dest = OUT / ("%s.json" % slug)
        dest.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        n_sec = sum(len(v.get("sections", [])) for k, v in data["texts"].items() if isinstance(v, dict))
        n_note = len(data["texts"].get("notes", []))
        ol = data["ai_outline"]["node_count"] if data["ai_outline"] else 0
        print("  %-46s outline=%d sections=%d notes=%d" % (slug, ol, n_sec, n_note))
        ok += 1
    print("\n写出 %d 本 -> %s" % (ok, OUT))
    if skip:
        print("跳过(无内容):", skip)
    return 0


if __name__ == "__main__":
    sys.exit(main())
