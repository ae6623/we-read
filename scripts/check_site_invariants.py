#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""站点不变量自检（push 前跑一次，防回归）

用法：
    python3 scripts/check_site_invariants.py          # 检查，违反则退出码 1
    python3 scripts/check_site_invariants.py --fix    # 仅自动修复"缺共享CSS链接"

检查项（对应 skills/luoyu-reading/references/frontend-conventions.md）：
  C1 页面不得内联 <style>（reading-notes/ *.html、index.html）
  C2 overview / final / outline 三类页必须挂到 assets/css 下的共享样式表
  C3 首页卡片 subtle 不得出现技术词 HTML
  C4 _data/books/*.json 必须合法 JSON，且与 reading-notes 目录不脱节
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS_DIR = "assets/css/"
# 按页面类型允许挂的共享样式表（任一命中即算通过）
ALLOW = {
    "overview": ("reading-overview.css", "reading-note.css", "reading-note-rich.css"),
    "final": ("reading-note.css", "reading-note-rich.css"),
    "outline": ("reading-outline.css", "reading-outline-entry.css", "reading-overview.css"),
}
# 缺链接时默认补哪份（轻游记族用 note，其余 overview 用 overview）
NOTE_FAMILY = {"alaska-qingyouji", "baikal-qingyouji", "camino-qingyouji",
               "elephant-qingyouji", "serbia-qingyouji", "unstable-life-qingyouji"}

problems = []
fixed = []


def pages(kind):
    if kind == "overview":
        return sorted(ROOT.glob("reading-notes/books/*/overview.html"))
    if kind == "final":
        return sorted(ROOT.glob("reading-notes/books/*/final.html"))
    return sorted(ROOT.glob("reading-notes/books/*/outline.html"))


def rel_link(from_file, css):
    depth = len(from_file.relative_to(ROOT).parts) - 1
    return "../" * depth + CSS_DIR + css


def check_inline_style():
    targets = list(ROOT.glob("reading-notes/**/*.html")) + [ROOT / "index.html"]
    for f in targets:
        t = f.read_text(encoding="utf-8", errors="ignore")
        if "<style>" in t:
            problems.append(f"[C1] 内联 <style>: {f.relative_to(ROOT)}")


def check_css_link(kind, do_fix):
    for f in pages(kind):
        t = f.read_text(encoding="utf-8", errors="ignore")
        if not any(c in t for c in ALLOW[kind]):
            slug = f.parent.name
            if do_fix:
                css = "reading-note.css" if slug in NOTE_FAMILY else {
                    "overview": "reading-overview.css",
                    "final": "reading-note.css",
                    "outline": "reading-outline.css",
                }[kind]
                link = '<link rel="stylesheet" href="%s"/>' % rel_link(f, css)
                # 插到 </title> 之后；无 head 则塞到 <body 之前
                if "</title>" in t:
                    t = t.replace("</title>", "</title>" + link, 1)
                else:
                    t = re.sub(r"(<body[^>]*>)", link + r"\1", t, count=1)
                f.write_text(t, encoding="utf-8")
                fixed.append(f"[C2] 补 {css}: {f.relative_to(ROOT)}")
            else:
                problems.append(f"[C2] {kind} 页缺共享样式表链接: {f.relative_to(ROOT)}")


def check_tech_words():
    idx = ROOT / "index.html"
    if not idx.exists():
        return
    t = idx.read_text(encoding="utf-8", errors="ignore")
    n = len(re.findall(r'subtle">\s*(HTML|CSS|JSON|EPUB)\s*<', t))
    if n:
        problems.append(f"[C3] index.html 卡片 subtle 含技术词 {n} 处（应为“网页版”等语义化文案）")


def check_data():
    data_dir = ROOT / "_data/books"
    if not data_dir.exists():
        problems.append("[C4] 缺少 _data/books/")
        return
    for f in sorted(data_dir.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            problems.append(f"[C4] JSON 非法 {f.name}: {e}")
            continue
        slug = d.get("slug") or f.stem
        book = ROOT / "reading-notes/books" / slug
        if not book.is_dir():
            problems.append(f"[C4] JSON 指向不存在的书目录: {slug}")
            continue
        if (book / "overview.html").exists() and not d.get("texts", {}).get("overview"):
            problems.append(f"[C4] {slug} 有 overview.html 但 JSON 未收录（跑 extract_content.py --slug {slug}）")


def git_dirty():
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain"],
                             capture_output=True, text=True).stdout
    except Exception:
        return []
    return [l for l in out.splitlines() if "outline.built" not in l]


def main():
    do_fix = "--fix" in sys.argv
    check_inline_style()
    for k in ("overview", "final", "outline"):
        check_css_link(k, do_fix)
    check_tech_words()
    check_data()

    for line in fixed:
        print("FIXED ", line)
    if problems:
        print("\n发现 %d 个问题：" % len(problems))
        for p in problems:
            print("  ", p)
        print("\n提示：--fix 可自动补共享 CSS 链接；其余需人工处理。")
        return 1
    print("全部通过（C1 内联样式 / C2 共享CSS / C3 技术词 / C4 数据一致性）")
    dirty = git_dirty()
    if dirty:
        print("提示：工作树有 %d 处未提交改动，提交前确认是否都在 TODO 里。" % len(dirty))
    return 0


if __name__ == "__main__":
    sys.exit(main())
