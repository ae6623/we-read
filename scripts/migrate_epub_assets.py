#!/usr/bin/env python3
"""把大文件从 we-read 搬到独立的 we-read-assets 仓库（同源 GitHub Pages）。

为什么能同源：两个项目站点都在 `ae6623.github.io` 下，属于同一个 origin，
`reader.html` 直接 fetch 绝对路径即可，不需要 CORS 配置。

为什么要拆：we-read 的 Pages 产物约 565MB，其中 EPUB 212MB、PDF 41MB、字体 60MB；
拆出去后主站只剩网页与图片，部署时间大幅下降。字体在站点里零引用，可只留在 assets 仓。

四步走（默认只报告，不删不改）：

    python scripts/migrate_epub_assets.py            # 1. 报告体积
    python scripts/migrate_epub_assets.py --prepare  # 2. 复制到 ../we-read-assets 并 git init
    python scripts/migrate_epub_assets.py --verify   # 3. 逐个 HEAD 线上 URL，确认已发布
    python scripts/migrate_epub_assets.py --apply    # 4. 从 we-read 删除（git rm），完成迁移

`--apply` 会先跑一次 verify，任何一个 URL 不是 200 就整体中止，避免删了没人接。
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT.parent / "we-read-assets"
ASSETS_ORIGIN = "https://ae6623.github.io/we-read-assets/"

PATTERNS = [
    "reading-notes/epub/books/**/*.epub",
    "books/**/*.pdf",
    "books/**/*.epub",
    "assets/fonts/*.ttf",
]

README = """# we-read-assets

`ae6623/we-read` 的静态大文件（EPUB / PDF / 字体）。独立成仓的原因：主站 Pages 产物过大，
部署要十几分钟；这些文件极少变动，且两个站点同在 `ae6623.github.io` 下，**同源**，
主站可直接 fetch，无需 CORS。

路径保持与主站相同，例如：

    reading-notes/epub/books/local-tianya-pdf-1.epub
    ->

    https://ae6623.github.io/we-read-assets/reading-notes/epub/books/local-tianya-pdf-1.epub

主站 `reading-notes/epub/reader.html` 通过 `ASSET_BASE` 拼接；本地联调用
`?assets=http://127.0.0.1:8771/` 覆盖。
"""


def collect() -> list[Path]:
    files: set[Path] = set()
    for pattern in PATTERNS:
        for path in ROOT.glob(pattern):
            if path.is_file():
                files.add(path.relative_to(ROOT))
    return sorted(files)


def human(total: int) -> str:
    return f"{total / 1024 / 1024:.1f} MB"


def prepare(files: list[Path]) -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    (ASSETS / "README.md").write_text(README, encoding="utf-8", newline="")
    for rel in files:
        dest = ASSETS / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            shutil.copy2(ROOT / rel, dest)
    if not (ASSETS / ".git").exists():
        subprocess.run(["git", "init", "-q"], cwd=ASSETS, check=True)
        subprocess.run(["git", "checkout", "-q", "-b", "main"], cwd=ASSETS, check=False)
    subprocess.run(["git", "add", "-A"], cwd=ASSETS, check=True)
    subprocess.run(
        ["git", "-c", "user.name=dsh-agent", "-c", "user.email=agent@local",
         "commit", "-q", "-m", "assets: 迁移 we-read 的 EPUB/PDF/字体（保持原路径）"],
        cwd=ASSETS, check=False,
    )
    print(f"prepared {ASSETS} ({len(files)} files)")


def verify(files: list[Path]) -> bool:
    bad = []
    for rel in files:
        url = ASSETS_ORIGIN + urllib.parse.quote(rel.as_posix())
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status != 200:
                    bad.append((rel, resp.status))
        except Exception as error:  # noqa: BLE001 - 只关心是否可用
            bad.append((rel, str(error)[:40]))
    if bad:
        print(f"verify failed: {len(bad)}/{len(files)}")
        for rel, reason in bad[:10]:
            print(f"  ! {rel} -> {reason}")
        return False
    print(f"verify ok: {len(files)} URLs all 200")
    return True


def apply_removal(files: list[Path]) -> None:
    for rel in files:
        subprocess.run(["git", "rm", "-q", "--cached", "--ignore-unmatch", str(rel)], cwd=ROOT, check=False)
        path = ROOT / rel
        if path.exists():
            path.unlink()
    subprocess.run(
        ["git", "-c", "user.name=dsh-agent", "-c", "user.email=agent@local",
         "commit", "-q", "-m", "assets: EPUB/PDF/字体迁至 we-read-assets（同源 Pages）"],
        cwd=ROOT, check=False,
    )
    print(f"removed {len(files)} files from we-read")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true", help="复制到 ../we-read-assets 并提交")
    parser.add_argument("--verify", action="store_true", help="HEAD 线上 URL 验证")
    parser.add_argument("--apply", action="store_true", help="从 we-read 删除（先自动 verify）")
    args = parser.parse_args()

    files = collect()
    total = sum((ROOT / rel).stat().st_size for rel in files)
    print(f"candidates: {len(files)} files / {human(total)}")
    by_ext: dict[str, int] = {}
    for rel in files:
        by_ext[rel.suffix] = by_ext.get(rel.suffix, 0) + (ROOT / rel).stat().st_size
    for ext, size in sorted(by_ext.items(), key=lambda kv: -kv[1]):
        print(f"  {ext:6} {human(size)}")

    if args.prepare:
        prepare(files)
    if args.verify and not verify(files):
        return 1
    if args.apply:
        if not verify(files):
            print("abort: 线上还没就绪，不删除任何文件", file=sys.stderr)
            return 1
        apply_removal(files)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
