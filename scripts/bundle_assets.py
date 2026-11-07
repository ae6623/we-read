#!/usr/bin/env python3
"""把首页的多个 CSS / JS 合并成单文件，减少请求数。

保守做法：
  * 只合并本地 assets 下的文件，外部 CDN 保持不动；
  * 严格按 <link>/<script> 出现顺序拼接，JS 语义不变；
  * 不压缩、不改写代码，只做拼接，出问题可以逐个回退；
  * 原文件保留，生成 bundle.css / bundle.js。

用法：
    python scripts/bundle_assets.py --dry-run
    python scripts/bundle_assets.py
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "index.html"

LINK_RE = re.compile(r'<link[^>]+rel="stylesheet"[^>]*href="(assets/[^"]+)"[^>]*>', re.I)
SCRIPT_RE = re.compile(r'<script[^>]+src="(assets/[^"]+)"[^>]*></script>', re.I)


def read_parts(paths: list[Path]) -> str:
    chunks = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        chunks.append(f"\n/* ==== {path.relative_to(ROOT).as_posix()} ==== */\n{text}\n")
    return "".join(chunks)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    html = PAGE.read_text(encoding="utf-8")

    css_paths = [ROOT / m.group(1) for m in LINK_RE.finditer(html)]
    js_paths = [ROOT / m.group(1) for m in SCRIPT_RE.finditer(html)]
    css_paths = [p for p in css_paths if p.exists()]
    js_paths = [p for p in js_paths if p.exists()]

    print(f"css: {len(css_paths)} files, {sum(p.stat().st_size for p in css_paths):,} bytes")
    for p in css_paths:
        print(f"  - {p.relative_to(ROOT).as_posix()}")
    print(f"js:  {len(js_paths)} files, {sum(p.stat().st_size for p in js_paths):,} bytes")
    for p in js_paths:
        print(f"  - {p.relative_to(ROOT).as_posix()}")

    if args.dry_run:
        return 0

    css_bundle = ROOT / "assets/css/bundle.css"
    js_bundle = ROOT / "assets/js/bundle.js"
    css_bundle.write_text(read_parts(css_paths), encoding="utf-8")
    js_bundle.write_text(read_parts(js_paths), encoding="utf-8")

    # 用单文件替换掉连续的一串 link / script，位置保持在原处。
    new_html = LINK_RE.sub("", html)
    new_html = new_html.replace(
        "</head>",
        '<link rel="stylesheet" href="assets/css/bundle.css?v=20261107b"></head>',
        1,
    )
    new_html = SCRIPT_RE.sub("", new_html)
    new_html = new_html.replace(
        "</body>",
        '<script src="assets/js/bundle.js?v=20261107b" defer></script>\n</body>',
        1,
    )
    PAGE.write_text(new_html, encoding="utf-8", newline="")

    print(
        f"\nbundled -> {css_bundle.relative_to(ROOT).as_posix()} "
        f"({css_bundle.stat().st_size:,}B), {js_bundle.relative_to(ROOT).as_posix()} "
        f"({js_bundle.stat().st_size:,}B)"
    )
    print(f"requests: {len(css_paths) + len(js_paths)} -> 2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
