#!/usr/bin/env python3
"""把所有静态资源引用改到 CDN（cdn.js-dev.cn），保留本地原文件。

范围：
  * HTML 里的 <link href>、<script src>、<img src> 指向 assets/** 的引用
  * JS 里的运行时 fetch/字符串拼接指向 assets/data、assets/js 的地方

不动：
  * EPUB / PDF（阅读器依赖 GitHub Pages 同源 fetch）
  * HTML 页面之间的相对链接（页面本身仍在 GitHub Pages）
  * @font-face 的本地兜底 src（刻意保留，CDN 失效时回落）

    python scripts/cdn_all_assets.py --dry-run
    python scripts/cdn_all_assets.py --apply
    python scripts/cdn_all_assets.py --revert
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CDN = "https://cdn.js-dev.cn"
SKIP_DIRS = {".git", "_site", "node_modules", ".a2a", ".workbuddy", ".codebuddy"}

# HTML 属性里的 assets 路径：允许任意层 ../ 或 ./
HTML_ATTR_RE = re.compile(
    r'(?P<attr>\b(?:href|src))="(?P<prefix>(?:\.\.?/)*)assets/(?P<rest>(?:css|js|data|img)/[^"]+)"'
)
# 已经改过的（幂等）
HTML_DONE_RE = re.compile(r'\b(?:href|src)="' + re.escape(CDN) + r'/assets/')

# JS 里的运行时路径：fetch('assets/...'), fetch('../../../assets/...'), base+'assets/...'
JS_STR_RE = re.compile(
    r"(?P<q>['\"])(?P<prefix>(?:\.\.?/)*)assets/(?P<rest>(?:data|js)/[^'\"]+)(?P=q)"
)


def html_files() -> list[Path]:
    out = []
    for path in ROOT.rglob("*.html"):
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        out.append(path.relative_to(ROOT))
    return out


def js_files() -> list[Path]:
    out = []
    for path in ROOT.rglob("*.js"):
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        # aa-panel.js 里的 FONT_FALLBACK 需要保留本地路径，单独处理
        out.append(path.relative_to(ROOT))
    return out


def rewrite_html(text: str) -> tuple[str, int]:
    def repl(m: re.Match[str]) -> str:
        return f'{m.group("attr")}="{CDN}/assets/{m.group("rest")}"'

    return HTML_ATTR_RE.subn(repl, text)


def rewrite_js(text: str) -> tuple[str, int]:
    def repl(m: re.Match[str]) -> str:
        return f'{m.group("q")}{CDN}/assets/{m.group("rest")}{m.group("q")}'

    return JS_STR_RE.subn(repl, text)


def revert_all() -> tuple[int, int]:
    files = 0
    refs = 0
    for rel in html_files():
        path = ROOT / rel
        text = path.read_text(encoding="utf-8", errors="surrogateescape")
        new, n = re.subn(
            r'\b(?P<attr>href|src)="' + re.escape(CDN) + r'/assets/(?P<rest>(?:css|js|data|img)/[^"]+)"',
            lambda m: f'assets/{m.group("rest")}',
            text,
        )
        if n:
            files += 1
            refs += n
            path.write_text(new, encoding="utf-8", errors="surrogateescape", newline="")
    for rel in js_files():
        path = ROOT / rel
        text = path.read_text(encoding="utf-8", errors="surrogateescape")
        new, n = re.subn(
            r"(['\"])" + re.escape(CDN) + r"/assets/((?:data|js)/[^'\"]+)\1",
            lambda m: f'{m.group(1)}assets/{m.group(2)}{m.group(1)}',
            text,
        )
        if n:
            files += 1
            refs += n
            path.write_text(new, encoding="utf-8", errors="surrogateescape", newline="")
    return files, refs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--revert", action="store_true")
    args = parser.parse_args()

    if args.revert:
        files, refs = revert_all()
        print(f"回滚：{files} 个文件 / {refs} 处引用")
        return 0

    html_targets = html_files()
    js_targets = js_files()

    h_files = h_refs = 0
    j_files = j_refs = 0
    for rel in html_targets:
        path = ROOT / rel
        text = path.read_text(encoding="utf-8", errors="surrogateescape")
        new, n = rewrite_html(text)
        if n:
            h_files += 1
            h_refs += n
            if args.apply:
                path.write_text(new, encoding="utf-8", errors="surrogateescape", newline="")

    for rel in js_targets:
        path = ROOT / rel
        text = path.read_text(encoding="utf-8", errors="surrogateescape")
        new, n = rewrite_js(text)
        if n:
            j_files += 1
            j_refs += n
            if args.apply:
                path.write_text(new, encoding="utf-8", errors="surrogateescape", newline="")

    print(f"HTML：{h_files} 个文件 / {h_refs} 处引用")
    print(f"JS  ：{j_files} 个文件 / {j_refs} 处引用")
    if not args.apply:
        print("（dry-run，未写盘）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
