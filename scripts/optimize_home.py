#!/usr/bin/env python3
"""首页瘦身：把重复的内联 SVG 收成 sprite，并压掉多余空白。

背景：首页 700+ KB 里有约 27% 是 1001 个内联 <svg>，它们只对应十几种图案。
抽成 <symbol> + <use> 后 HTML 变小、DOM 少约 1000 棵 SVG 子树，渲染结果不变。

这个脚本是**增量且幂等**的：
  * 已有 sprite 时，先读出现有 symbol，再扫描页面里新出现的内联 <svg>；
  * 已转成 <use> 的图标原样保留，id 不变；
  * 只有新图标才追加 symbol，因此任何人生成/编辑首页后再跑一次都能收敛。

用法：
    python scripts/optimize_home.py            # 改写 index.html，原文件留 .bak
    python scripts/optimize_home.py --dry-run  # 只报告，不改写
    python scripts/optimize_home.py --file path/to/page.html
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "index.html"

SVG_RE = re.compile(r"<svg\b([^>]*)>(.*?)</svg>", re.S)
SPRITE_RE = re.compile(
    r'<svg[^>]*id="icon-sprite"[^>]*>(.*?)</svg>', re.S
)
SYMBOL_RE = re.compile(r'<symbol id="(ic-\d+)" viewBox="([^"]*)">(.*?)</symbol>', re.S)
USE_ONLY_RE = re.compile(r'^\s*<use\s[^>]*/>\s*$')
WS_RE = re.compile(r">\s+<")
BLANK_RE = re.compile(r"\n\s*\n+")

SPRITE_TAG = (
    '<svg xmlns="http://www.w3.org/2000/svg" id="icon-sprite" '
    'style="position:absolute;width:0;height:0;overflow:hidden" aria-hidden="true">'
)


def normalize(inner: str) -> str:
    """比较用的键：忽略缩进与换行，保留属性与路径。"""
    return re.sub(r"\s+", " ", inner).strip()


def build_sprite(symbols: dict[str, tuple[str, str]]) -> str:
    parts = [
        f'<symbol id="{sid}" viewBox="{vb}">{body}</symbol>'
        for sid, (vb, body) in sorted(symbols.items(), key=lambda kv: int(kv[0].split("-")[1]))
    ]
    return SPRITE_TAG + "".join(parts) + "</svg>"


def optimize(html: str) -> tuple[str, dict]:
    stats = {"before": len(html), "added": 0, "reused": 0, "symbols": 0}

    # 1) 读出已有 sprite（增量重建的基础），并从页面里摘掉
    symbols: dict[str, tuple[str, str]] = {}
    body_by_key: dict[str, str] = {}
    sprite_match = SPRITE_RE.search(html)
    if sprite_match:
        for sid, viewbox, body in SYMBOL_RE.findall(sprite_match.group(1)):
            symbols[sid] = (viewbox, body)
            body_by_key[normalize(body)] = sid
        html = html[: sprite_match.start()] + html[sprite_match.end():]

    next_id = max((int(sid.split("-")[1]) for sid in symbols), default=0) + 1

    # 2) 扫描剩下的内联 <svg>：已经是 <use> 的跳过，其余收进 sprite
    def repl(match: re.Match[str]) -> str:
        nonlocal next_id
        attrs, inner = match.group(1), match.group(2)
        if USE_ONLY_RE.match(inner):
            return match.group(0)
        if "<" not in inner:
            return match.group(0)
        key = normalize(inner)
        sid = body_by_key.get(key)
        if sid is None:
            sid = f"ic-{next_id}"
            next_id += 1
            viewbox = re.search(r'viewBox="([^"]+)"', attrs)
            symbols[sid] = (viewbox.group(1) if viewbox else "0 0 24 24", key)
            body_by_key[key] = sid
            stats["added"] += 1
        else:
            stats["reused"] += 1
        return f'<svg{attrs}><use href="#{sid}"/></svg>'

    new_html = SVG_RE.sub(repl, html)

    # 3) 放回 sprite，并压空白
    if symbols:
        new_html = new_html.replace("</body>", build_sprite(symbols) + "\n</body>", 1)

    new_html = WS_RE.sub("><", new_html)
    new_html = BLANK_RE.sub("\n", new_html)

    stats["after"] = len(new_html)
    stats["symbols"] = len(symbols)
    return new_html, stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--file", default=str(TARGET))
    parser.add_argument("--no-backup", action="store_true", help="不写 .bak（CI 用，避免备份文件进入发布产物）")
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
        f"symbols={stats['symbols']} new={stats['added']} reused={stats['reused']}"
    )

    if args.dry_run or new_html == original:
        return 0

    backup = path.with_suffix(path.suffix + ".bak")
    if not args.no_backup and not backup.exists():
        backup.write_text(original, encoding="utf-8")
    path.write_text(new_html, encoding="utf-8", newline="")
    print(f"written {path.name}" + ("" if args.no_backup else f" (backup: {backup.name})"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
