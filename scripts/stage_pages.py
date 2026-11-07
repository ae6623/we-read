#!/usr/bin/env python3
"""生成 GitHub Pages 发布目录 `_site/`：只拷贝真正对外的文件。

为什么需要这一步：仓库 674MB，但其中一部分从不出现在页面上——
  * `*.ttf` 约 60MB：全站 HTML/CSS/JS 零引用（字体是用 woff2 的）；
  * `*.pdf` 约 41MB：没有任何页面链接到它们；
  * `tools/ scripts/ _data/ data/ openspec/ skills/ ...`：生成器与工作目录，非站点内容。

只减不改：链接结构、相对路径、文件名全部保持原样，因此页面无需改动。
跑完可 `python -m http.server 8000 -d _site` 本地验证。

用法：
    python scripts/stage_pages.py            # 生成 _site/
    python scripts/stage_pages.py --report   # 只统计会排除多少，不拷贝
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_site"

# 只用于生成/协作的目录，页面里没有指向它们的链接（已用 grep 全站确认）
EXCLUDE_DIRS = {
    ".git", ".github", "tools", "scripts", "_data", "data", "openspec",
    "templates", "overview_gen", "skills", "memory", "todo", "team-handoffs",
    "daily-output", "docs", "需求", "_site", ".bench",
}

# 站点上从未被引用的重文件
EXCLUDE_SUFFIXES = {".ttf", ".pdf", ".bak"}

# 本地开发/协作留下的隐藏目录
EXCLUDE_HIDDEN = {".a2a", ".workbuddy", ".codebuddy", ".idea", ".vscode"}


def keep(path: Path) -> bool:
    if path.suffix.lower() in EXCLUDE_SUFFIXES:
        return False
    if path.parts:
        first = path.parts[0]
        if first in EXCLUDE_DIRS or first in EXCLUDE_HIDDEN:
            return False
    return True


def walk(root: Path):
    for path in root.rglob("*"):
        if path.is_file():
            yield path.relative_to(root)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    files = list(walk(ROOT))
    kept = [p for p in files if keep(p)]
    dropped = [p for p in files if not keep(p)]

    total = sum((ROOT / p).stat().st_size for p in files)
    keep_bytes = sum((ROOT / p).stat().st_size for p in kept)
    drop_bytes = total - keep_bytes
    print(
        f"site: {len(files):,} files / {total / 1024 / 1024:.1f} MB -> "
        f"{len(kept):,} files / {keep_bytes / 1024 / 1024:.1f} MB "
        f"(drop {drop_bytes / 1024 / 1024:.1f} MB, "
        f"{(drop_bytes / total * 100 if total else 0):.0f}%)"
    )

    if args.report:
        return 0

    if OUT.exists():
        shutil.rmtree(OUT)
    for rel in kept:
        dest = OUT / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dest)

    for required in ("index.html", "assets/css/site.css", "reading-notes/index.html"):
        if not (OUT / required).exists():
            print(f"missing required file: {required}", file=sys.stderr)
            return 1
    print(f"written {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
