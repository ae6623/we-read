#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""AI 问书 / 自测：把「脚本调模型」换成「脚本出素材 + Agent 写内容 + 脚本回填」。

为什么要有这个脚本
------------------
`gen_quiz_answer.py` / `gen_mindmap.py` 都是脚本内直连 LLM（Gemini）。
沙箱到 Google 不可达、又没有国内模型 key 时，那条路整条断掉。

而云端 Agent 本身就是 LLM：它能读素材、也能写内容。所以正确分工是

    脚本：抓/解析大纲 → 出素材包（markdown + 待写清单）
    Agent：读素材，写 answers.json（含出处，不许编）
    脚本：校验 → 回填 combined-data.html 的 data-key="aiask" 段 → 打标

这样不依赖任何外部模型端点，也不依赖登录态。

用法
----
  python3 tools/ai_draft.py --list
  python3 tools/ai_draft.py --dump <slug>              # 出素材 → drafts/<slug>.md + .json
  python3 tools/ai_draft.py --dump <slug> --questions 3
  python3 tools/ai_draft.py --fill <slug> --answers drafts/<slug>.json [--write]
  python3 tools/ai_draft.py --fill <slug> --answers ... --create   # 无 combined-data 时新建

answers.json 结构
-----------------
  {
    "slug": "xxx",
    "title": "书名",
    "note": "AI 自主整理 · 非AI读书返回",
    "items": [
      {"q": "问题", "a": "答案 ≤160 字", "cite": "第N章 / 要点原文片段"}
    ]
  }
`cite` 必须能在 outline.html 里找到（脚本会校验），防止编造。
"""
from __future__ import annotations

import argparse
import html as H
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOKS = ROOT / "reading-notes" / "books"
DRAFTS = ROOT / "drafts"
DEFAULT_NOTE = "AI 自主整理 · 非AI读书返回"


# ---------------------------------------------------------------- 大纲解析
def _strip(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()


def parse_outline(slug: str) -> list[dict]:
    """把 outline.html 解析成 [{no,title,secs:[{title,points:[{text,quotes[]}]}]}]"""
    p = BOOKS / slug / "outline.html"
    if not p.exists():
        return []
    txt = p.read_text(encoding="utf-8", errors="ignore")
    chs = []
    for i, m in enumerate(re.finditer(
            r'<details class="ch"[^>]*>\s*<summary>(.*?)</summary>([\s\S]*?)</details>', txt)):
        title = _strip(m.group(1))
        body = m.group(2)
        secs = []
        for sm in re.finditer(r'<div class="sec">([\s\S]*?)(?=<div class="sec">|$)', body):
            blk = sm.group(1)
            h4 = re.search(r"<h4[^>]*>(.*?)</h4>", blk)
            points = []
            for pm in re.finditer(
                    r'<li><b>(.*?)</b>\s*(?:<ul class="quote">([\s\S]*?)</ul>)?\s*</li>', blk):
                quotes = [_strip(q) for q in re.findall(r"<li>(.*?)</li>", pm.group(2) or "")]
                points.append({"text": _strip(pm.group(1)), "quotes": quotes})
            secs.append({"title": _strip(h4.group(1)) if h4 else "",
                         "points": points})
        chs.append({"no": i + 1, "title": title, "secs": secs})
    return chs


def parse_meta(slug: str) -> dict:
    p = BOOKS / slug / "outline.html"
    if not p.exists():
        return {}
    txt = p.read_text(encoding="utf-8", errors="ignore")
    title = re.search(r"<title>《(.+?)》", txt)
    meta = re.search(r'<p class="meta">([\s\S]*?)</p>', txt)
    author = ""
    if meta:
        m = re.search(r"作者：([^　<·]+)", _strip(meta.group(1)))
        author = m.group(1).strip() if m else ""
    return {"title": title.group(1) if title else slug,
            "author": author, "chapters": len(parse_outline(slug))}


def corpus_of(chs: list[dict], per_ch: int = 3, cut: int = 90) -> str:
    lines = []
    for c in chs:
        pts = [p["text"] for s in c["secs"] for p in s["points"]]
        lines.append("第%d章 %s｜%s" % (c["no"], c["title"],
                                       " / ".join(p[:cut] for p in pts[:per_ch])))
    return "\n".join(lines)


def quote_bank(chs: list[dict], limit: int = 12) -> list[str]:
    out = []
    for c in chs:
        for s in c["secs"]:
            for p in s["points"]:
                out.extend(p["quotes"])
    return out[:limit]


# ---------------------------------------------------------------- 素材包
Q_TEMPLATES = [
    "这本书最核心的判断是什么？它靠哪几条论证支撑？",
    "书里哪个观点最反直觉？作者是怎么论证的？",
    "读完这本，读者最该带走的一个可操作结论是什么？",
    "作者处理这个题材的方式有什么特别之处？",
    "哪一处论述最容易被误读？该怎样正确理解？",
]


def dump(slug: str, nq: int) -> int:
    chs = parse_outline(slug)
    if not chs:
        print("✗ %s 没有 outline.html，无法出素材" % slug)
        return 1
    meta = parse_meta(slug)
    quotes = quote_bank(chs)
    qs = Q_TEMPLATES[:nq]

    DRAFTS.mkdir(exist_ok=True)
    md = ["# %s · AI 问书素材" % meta["title"], "",
          "- slug：`%s`" % slug,
          "- 作者：%s" % (meta["author"] or "—"),
          "- 章数：%d，条目：%d" % (len(chs),
                                   sum(len(s["points"]) for c in chs for s in c["secs"])),
          "- 素材来源：`reading-notes/books/%s/outline.html`（AI 读书大纲，含原文摘录）" % slug,
          "", "## 待写问题", ""]
    md += ["%d. %s" % (i + 1, q) for i, q in enumerate(qs)]
    md += ["", "## 章节目录与要点", ""]
    for c in chs:
        md.append("### 第%d章 %s" % (c["no"], c["title"]))
        for s in c["secs"]:
            if s["title"]:
                md.append("- **%s**" % s["title"])
            for p in s["points"]:
                md.append("  - %s" % p["text"])
                for q in p["quotes"][:2]:
                    md.append("    > %s" % q[:120])
        md.append("")
    if quotes:
        md += ["## 可用原句（引用须命中这里）", ""] + ["> %s" % q for q in quotes]

    mp = DRAFTS / ("%s.md" % slug)
    mp.write_text("\n".join(md), encoding="utf-8")

    tpl = {"slug": slug, "title": meta["title"], "note": DEFAULT_NOTE,
           "items": [{"q": q, "a": "", "cite": ""} for q in qs]}
    jp = DRAFTS / ("%s.json" % slug)
    jp.write_text(json.dumps(tpl, ensure_ascii=False, indent=2), encoding="utf-8")

    print("✓ 素材：%s（%d 字）" % (mp, len("\n".join(md))))
    print("✓ 模板：%s（填 items[].a / cite 后跑 --fill）" % jp)
    return 0


# ---------------------------------------------------------------- 校验 + 回填
def validate(slug: str, data: dict) -> tuple[bool, list[str]]:
    errs = []
    chs = parse_outline(slug)
    hay = "\n".join([c["title"] for c in chs] +
                    [p["text"] for c in chs for s in c["secs"] for p in s["points"]] +
                    [q for c in chs for s in c["secs"] for p in s["points"] for q in p["quotes"]])
    items = data.get("items") or []
    if len(items) < 2:
        errs.append("items 少于 2 条")
    for i, it in enumerate(items, 1):
        if not (it.get("q") or "").strip():
            errs.append("第%d条缺 q" % i)
        a = (it.get("a") or "").strip()
        if len(a) < 20:
            errs.append("第%d条答案过短（<20 字）" % i)
        if len(a) > 220:
            errs.append("第%d条答案过长（>220 字，页面排版会断）" % i)
        cite = (it.get("cite") or "").strip()
        if not cite:
            errs.append("第%d条缺 cite（必须指向章节/要点原文）" % i)
        else:
            key = re.sub(r"^第\d+章\s*", "", cite)[:18]
            if key and key not in hay:
                errs.append("第%d条 cite 在大纲里找不到：%s" % (i, key))
    return (not errs), errs


def render_aiask(data: dict) -> str:
    note = data.get("note") or DEFAULT_NOTE
    items = "\n".join(
        '<div class="aiqa-item"><h3>%s</h3><p>%s</p></div>'
        % (H.escape(it["q"]), H.escape(it["a"])) for it in data["items"])
    return ('<h2 id="aiask">AI 问书</h2>'
            '<p class="mmx-mod-note">%s（基于本书 AI 大纲条目整理，非微信读书「AI 问书」原文）</p>'
            '<div class="mmx-ask">\n%s\n</div>' % (H.escape(note), items))


def fill(slug: str, answers: Path, write: bool, create: bool) -> int:
    data = json.loads(answers.read_text(encoding="utf-8"))
    ok, errs = validate(slug, data)
    if not ok:
        print("✗ 校验没过：")
        for e in errs:
            print("   -", e)
        return 2
    block = render_aiask(data)
    p = BOOKS / slug / "combined-data.html"
    if not p.exists():
        if not create:
            print("✗ %s 没有 combined-data.html（加 --create 新建）" % slug)
            return 1
        meta = parse_meta(slug)
        txt = ('<!--META %s-->\n<section data-key="aiask">%s</section>\n'
               % (json.dumps({"slug": slug, "title": meta.get("title", slug)},
                             ensure_ascii=False), block))
        mode = "新建"
    else:
        txt = p.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r'<section[^>]*data-key="aiask"[^>]*>[\s\S]*?</section>', txt)
        if m:
            txt = txt[:m.start()] + '<section data-key="aiask">%s</section>' % block + txt[m.end():]
            mode = "替换"
        else:
            txt = txt.rstrip() + '\n<section data-key="aiask">%s</section>\n' % block
            mode = "追加"
    if not write:
        print("✓ 校验通过（%d 条），%s模式预览，未写入。加 --write 落盘" % (len(data["items"]), mode))
        print(block[:400])
        return 0
    p.write_text(txt, encoding="utf-8")
    print("✓ 已%s %s（%d 条）" % (mode, p, len(data["items"])))
    return 0


# ---------------------------------------------------------------- 清单
SKELETON_SRC = "spain-qingyouji"   # 任意一本结构完整的 combined.html，当作骨架模板


def skeleton(slug: str, write: bool) -> int:
    """按标准骨架生成 combined.html（只换 slug / 书名），数据由 combined-data.html 提供。"""
    src = BOOKS / SKELETON_SRC / "combined.html"
    dst = BOOKS / slug / "combined.html"
    if not src.exists():
        print("✗ 骨架模板缺失：%s" % src)
        return 1
    if dst.exists():
        print("· %s 已存在 combined.html，跳过" % slug)
        return 0
    meta = parse_meta(slug)
    txt = src.read_text(encoding="utf-8", errors="ignore")
    txt = re.sub(r'data-slug="[^"]*"', 'data-slug="%s"' % slug, txt)
    txt = re.sub(r'data-title="[^"]*"', 'data-title="%s"' % H.escape(meta.get("title", slug)), txt)
    txt = re.sub(r"<title>[\s\S]*?</title>",
                 "<title>《%s》｜全书领读</title>" % H.escape(meta.get("title", slug)), txt, count=1)
    txt = re.sub(r'<h1>[\s\S]*?</h1>',
                 "<h1>《%s》</h1>" % H.escape(meta.get("title", slug)), txt, count=1)
    txt = txt.replace('<span class="chip">Gemini pro</span>',
                      '<span class="chip">AI 自主整理</span>')
    if not write:
        print("· 干跑：将生成 %s（%d 字节）" % (dst, len(txt)))
        return 0
    dst.write_text(txt, encoding="utf-8")
    print("✓ 已生成骨架 %s" % dst)
    return 0


def listing() -> int:
    d = [x for x in BOOKS.iterdir() if x.is_dir()]
    no_cd = [x.name for x in d if not (x / "combined-data.html").exists()]
    has_outline = [s for s in no_cd if (BOOKS / s / "outline.html").exists()]
    print("总书：%d｜有 combined-data：%d｜缺：%d（其中有大纲可出素材：%d）"
          % (len(d), len(d) - len(no_cd), len(no_cd), len(has_outline)))
    print("缺且有大纲（前 20）：")
    for s in sorted(has_outline)[:20]:
        print("  -", s)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dump")
    ap.add_argument("--questions", type=int, default=3)
    ap.add_argument("--fill")
    ap.add_argument("--answers")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--create", action="store_true")
    ap.add_argument("--skeleton", help="按标准骨架生成 combined.html")
    a = ap.parse_args(argv)

    if a.list:
        return listing()
    if a.skeleton:
        return skeleton(a.skeleton, a.write)
    if a.dump:
        return dump(a.dump, a.questions)
    if a.fill:
        if not a.answers:
            ap.error("--fill 需要 --answers")
        return fill(a.fill, Path(a.answers), a.write, a.create)
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
