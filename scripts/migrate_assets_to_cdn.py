#!/usr/bin/env python3
"""把站点素材迁到七牛 CDN，并改写仓库里的引用。

只改「引用方式」，不改文件名与目录结构——CDN 上的路径与本地一一对应，
所以出问题随时能改回来。

    # 1. 看看会动哪些文件、改多少处（不传不写）
    python scripts/migrate_assets_to_cdn.py --dry-run

    # 2. 上传 + 改写引用
    set QINIU_AK=... & set QINIU_SK=...
    python scripts/migrate_assets_to_cdn.py --apply

    # 3. 回滚引用（不动 CDN 上的文件）
    python scripts/migrate_assets_to_cdn.py --revert

默认处理 `assets/covers`、`assets/img` 下的图片音频，以及 `assets/fonts` 里的字体。
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
BUCKET = "we-read-assets"
CDN = "https://cdn.js-dev.cn"
MARK = "cdn.js-dev.cn"

# 只迁移「纯静态、不参与版本化逻辑」的媒体资源
MEDIA_DIRS = ["assets/covers", "assets/img", "assets/audio", "assets/video"]
MEDIA_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".mp3", ".m4a", ".wav", ".mp4", ".webm"}

# 需要改写引用的源码文件
SOURCE_EXT = {".html", ".js", ".css"}
SKIP_DIRS = {".git", "_site", "node_modules", ".a2a", ".workbuddy", ".codebuddy"}


def media_files() -> list[Path]:
    out: list[Path] = []
    for name in MEDIA_DIRS:
        base = ROOT / name
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in MEDIA_EXT:
                out.append(path.relative_to(ROOT))
    return sorted(out)


def source_files() -> list[Path]:
    out: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SOURCE_EXT:
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        out.append(path.relative_to(ROOT))
    return sorted(out)


def upload(files: list[Path]) -> bool:
    try:
        from qiniu import Auth, put_file_v2
    except ImportError:
        print("缺少依赖：pip install qiniu", file=sys.stderr)
        return False

    ak, sk = os.environ.get("QINIU_AK"), os.environ.get("QINIU_SK")
    if not (ak and sk):
        print("缺少 QINIU_AK / QINIU_SK", file=sys.stderr)
        return False

    auth = Auth(ak, sk)
    failed = []
    for index, rel in enumerate(files, 1):
        key = rel.as_posix()
        token = auth.upload_token(BUCKET, key, 3600)
        ret, info = put_file_v2(token, key, str(ROOT / rel))
        if info.status_code != 200:
            failed.append((key, getattr(info, "error", info.status_code)))
        if index % 50 == 0 or index == len(files):
            print(f"  上传 {index}/{len(files)}")
    if failed:
        for key, reason in failed[:10]:
            print(f"  ! {key}: {reason}")
        return False
    return True


# 只匹配会真正发请求的写法：
#   'assets/covers/' + slug        （字符串开头，后面紧跟引号结束）
#   '../../../assets/covers/x.jpg' （完整字面量路径）
# 注释里的 assets/covers/<slug>.jpg 这类占位不会命中。
REF_RE = re.compile(
    r"(?<![/\w])(?:\.{1,2}/)*assets/(covers|img|audio|video)/(?=[\"'`]|[\w.-]+\.(?:jpg|jpeg|png|webp|gif|svg|mp3|m4a|wav|mp4|webm))"
)


def rewrite(apply: bool) -> tuple[int, int]:
    changed_files = 0
    changed_refs = 0
    for rel in source_files():
        path = ROOT / rel
        text = path.read_text(encoding="utf-8", errors="surrogateescape")

        new_text, count = REF_RE.subn(lambda m: f"{CDN}/assets/{m.group(1)}/", text)
        if count == 0:
            continue
        changed_refs += count
        changed_files += 1
        if apply:
            path.write_text(new_text, encoding="utf-8", errors="surrogateescape", newline="")
    return changed_files, changed_refs


def revert() -> tuple[int, int]:
    """把 https://cdn.js-dev.cn/assets/... 改回相对路径 assets/..."""
    pattern = re.compile(re.escape(CDN) + r"/assets/(covers|img|audio|video)/")
    files = 0
    refs = 0
    for rel in source_files():
        path = ROOT / rel
        text = path.read_text(encoding="utf-8", errors="surrogateescape")
        new_text, count = pattern.subn(lambda m: f"assets/{m.group(1)}/", text)
        if count:
            files += 1
            refs += count
            path.write_text(new_text, encoding="utf-8", errors="surrogateescape", newline="")
    return files, refs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--revert", action="store_true")
    parser.add_argument("--skip-upload", action="store_true", help="只改引用，不上传")
    args = parser.parse_args()

    if args.revert:
        files, refs = revert()
        print(f"回滚：{files} 个文件 / {refs} 处引用")
        return 0

    files = media_files()
    total = sum((ROOT / rel).stat().st_size for rel in files)
    print(f"待迁移媒体：{len(files)} 个 / {total / 1024 / 1024:.1f} MB")

    if args.dry_run:
        # 统计会改动的源码文件与引用数，但不写盘
        hits_file = 0
        hits_ref = 0
        for rel in source_files():
            text = (ROOT / rel).read_text(encoding="utf-8", errors="surrogateescape")
            count = len(REF_RE.findall(text))
            if count:
                hits_file += 1
                hits_ref += count
        print(f"引用改写：{hits_file} 个源码文件 / {hits_ref} 处")
        sample = [m for rel in source_files() for m in REF_RE.findall(
            (ROOT / rel).read_text(encoding="utf-8", errors="surrogateescape"))][:3]
        print("样例：", sample)
        return 0

    if not (args.apply or args.skip_upload):
        print("需要 --apply 或 --dry-run", file=sys.stderr)
        return 1

    if not args.skip_upload:
        print("上传到七牛…")
        if not upload(files):
            print("上传失败，未改写任何引用", file=sys.stderr)
            return 1

    changed_files, changed_refs = rewrite(apply=True)
    print(f"已改写 {changed_files} 个文件 / {changed_refs} 处引用")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
