#!/usr/bin/env python3
"""首页瘦身：把重复的内联 SVG 收成 sprite，并压掉多余空白。

用法：
    python scripts/optimize_home.py            # 改写 index.html，原文件留 .bak
    python scripts/optimize_home.py --dry-run  # 只报告，不改写

为什么只做这一步：首页 743 KB 里有 201 KB（27%）是 1001 个内联 <svg>，
它们只对应十几种图案。抽成 <symbol> + <use> 后 HTML 变小、DOM 节点少约 1000 棵子树，
但不影响任何卡片内容与脚本（图标仍由浏览器渲染成同样的图形）。
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "index.html"

SVG_RE = re.compile(r"<svg\b([^>]*)>(.*?)</svg>", re.S)
# 生成过的 sprite 带这个 id；再跑一次时直接跳过，保证幂等。
SPRITE_MARKER = 'id="icon-sprite"'
SPRITE_START = '<svg xmlns="http://www.w3.org/2000/svg" id="icon-sprite" style="position:absolute;width:0;height:0;overflow:hidden" aria-hidden="true">'
WS_RE = re.compile(r">\s+<")
BLANK_RE = re.compile(r"\n\s*\n+")


def normalize(inner: str) -> str:
    """比较用的键：忽略缩进与换行，保留属性与路径。"""
    return re.sub(r"\s+", " ", inner).strip()


def optimize(html: str) -> tuple[str, dict]:
    if SPRITE_MARKER in html:
        # 已经优化过：只做空白压缩，绝不再碰 <use>/<symbol>。
        collapsed = BLANK_RE.sub("\n", WS_RE.sub("><", html))
        return collapsed, {
            "before": len(html),
            "after": len(collapsed),
            "svgs": 0,
            "symbols": 0,
        }

    symbols: dict[str, int] = {}
    order: list[str] = []
    replacements = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal replacements
        attrs, inner = match.group(1), match.group(2)
        if "<" not in inner:  # 空图标，原样保留
            return match.group(0)
        key = normalize(inner)
        if key not in symbols:
            symbols[key] = len(order) + 1
            order.append(key)
        symbol_id = f"ic-{symbols[key]}"
        replacements += 1
        return f"<svg{attrs}><use href=\"#{symbol_id}\"/></svg>"

    new_html = SVG_RE.sub(repl, html)

    if order:
        # 每个 symbol 的 viewBox 取自它第一次出现的原始 svg。
        viewboxes = {}
        for match in SVG_RE.finditer(html):
            key = normalize(match.group(2))
            if key in viewboxes:
                continue
            vb = re.search(r'viewBox="([^"]+)"', match.group(1))
            viewboxes[key] = vb.group(1) if vb else "0 0 24 24"
        sprite_defs = [
            f'<symbol id="ic-{index}" viewBox="{viewboxes[key]}">{key}</symbol>'
            for index, key in enumerate(order, start=1)
        ]
        sprite = (
            SPRITE_START
            + "".join(sprite_defs)
            + "</svg>"
        )
        new_html = new_html.replace("</body>", sprite + "\n</body>", 1)

    new_html = WS_RE.sub("><", new_html)
    new_html = BLANK_RE.sub("\n", new_html)

    stats = {
        "before": len(html),
        "after": len(new_html),
        "svgs": replacements,
        "symbols": len(order),
    }
    return new_html, stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--file", default=str(TARGET))
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"missing: {path}", file=sys.stderr)
        return 1

    original = path.read_text(encoding="utf-8")
    new_html, stats = optimize(original)
    saved = stats["before"] - stats["after"]
    print(
        f"{path.name}: {stats['before']:,} -> {stats['after']:,} bytes "
        f"({saved:,} saved, {saved / stats['before'] * 100:.1f}%) · "
        f"{stats['svgs']} svg -> {stats['symbols']} symbols"
    )

    if args.dry_run:
        return 0

    backup = path.with_suffix(path.suffix + ".bak")
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")
    path.write_text(new_html, encoding="utf-8")
    print(f"written {path.name} (backup: {backup.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
