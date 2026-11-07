#!/usr/bin/env python3
"""生成 GitHub Pages 发布目录 `_site/`：只拷贝真正对外的文件。

为什么需要这一步：仓库 674MB，但其中一部分从不出现在页面上——
  * `*.ttf` 约 60MB：全站 HTML/CSS/JS 零引用（字体是用 woff2 的）；
  * `*.pdf` 约 41MB：没有任何页面链接到它们；
  * `tools/ scripts/ _data/ openspec/ skills/ ...`：生成器与工作目录，非站点内容。
    （注意：根目录 `data/` 不能排除——`reader.js` 会 fetch `data/mm-graph/*.json`。）

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
    ".git", ".github", "tools", "scripts", "_data", "openspec",
    "templates", "overview_gen", "skills", "memory", "todo", "team-handoffs",
    "daily-output", "docs", "需求", "_site", ".bench",
}

# 站点上从未被引用的重文件。
# 注意：woff2 不在这里——字体优先走 CDN（cdn.js-dev.cn），
# 但 @font-face 的第二个 src 指向本地 assets/fonts/，作为 CDN 不可用时的兜底，
# 所以 6.6MB 的 woff2 仍然需要发布。
EXCLUDE_SUFFIXES = {".ttf", ".pdf", ".bak"}

# 生成用源数据，运行时零引用（grep 全站 JS/HTML 确认）
EXCLUDE_NAMES = {"outline.json", "outline.md"}

# 根目录 README 之外，所有 .md 都是源文件（只有 index.html 链了 README.md）
KEEP_MD = {"README.md"}

# 思维导图的生成素材（export_mindmap_material.py 的输出），只有 Python 脚本读，
# 前端 HTML/JS 零引用；发布产物里不该出现。
EXCLUDE_SUBTREES = {"data/mindmap-material", "data/mindmap"}

# 本地开发/协作留下的隐藏目录
EXCLUDE_HIDDEN = {".a2a", ".workbuddy", ".codebuddy", ".idea", ".vscode"}


def keep(path: Path) -> bool:
    if path.suffix.lower() in EXCLUDE_SUFFIXES:
        return False
    posix = path.as_posix()
    if any(posix == d or posix.startswith(d + "/") for d in EXCLUDE_SUBTREES):
        return False
    if path.name == "SHA256SUMS.txt":
        return False
    if path.name in EXCLUDE_NAMES:
        return False
    if path.suffix.lower() == ".md" and path.as_posix() not in KEEP_MD:
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
    shaved = 0
    for rel in kept:
        dest = OUT / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        path = ROOT / rel
        if path.suffix.lower() == ".html":
            text = path.read_text(encoding="utf-8", errors="replace")
            cut = text.find("</noscript>")
            if "epub-redirect" in text and 0 < cut:
                # 这些页已改成跳转 EPUB 阅读器，旧正文没有用了
                trimmed = text[: cut + len("</noscript>")] + "</head><body></body></html>\n"
                shaved += len(text) - len(trimmed)
                dest.write_text(trimmed, encoding="utf-8", newline="")
                continue
        shutil.copy2(path, dest)

    for required in ("index.html", "assets/css/site.css", "reading-notes/index.html"):
        if not (OUT / required).exists():
            print(f"missing required file: {required}", file=sys.stderr)
            return 1
    if shaved:
        print(f"trimmed {shaved / 1024 / 1024:.1f} MB of dead full-text behind epub redirects")
    print(f"written {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
