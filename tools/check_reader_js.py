#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全站 reader JS 版本守卫 —— 本地闸门，与云端 `Verify reader JS version across all book shells` 同规则、同真源。

真相源：`assets/data/reader-js.json` 的 `cdn_prefix` + `current`。
规则：所有 `reading-notes/books/*/combined.html` 里 reader 的 `<script src>` 必须**严格等于**该 URL；
      禁止相对路径、禁止 `?v=`、禁止历史版本文件、禁止缺失。

背景：2026-11-15 补产 80 本时生成器硬编码 `reader.js?v=20261106b`，
      本地无守卫 → 旧模板进 main → GitHub Actions 连续 3 次发布被守卫拦截。

用法：
  python3 tools/check_reader_js.py                          # 全站检查；有不一致 → 退出码 1
  python3 tools/check_reader_js.py --fix                   # 把不一致的壳页引用切到真源 URL（换 key，不覆盖同名 JS）
  python3 tools/check_reader_js.py --files /tmp/list.txt [--fix]   # 只处理清单里的 combined.html
  python3 tools/check_reader_js.py --root /path/to/we-read         # 指定仓库根（默认脚本上级）

**推 main 前必跑本脚本；退出码非 0 时禁止 `push_snapshot.py --main`。**
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

# 只匹配含 reader 的 script src；其它 js（share / home-track / qrcode / count）不受影响
SCRIPT_RE = re.compile(
    r'(<script\b[^>]*\bsrc=")([^"]*reader[^"]*\.js[^"]*)("[^>]*>)', re.I)


def expected(root: Path) -> str:
    p = root / "assets" / "data" / "reader-js.json"
    if not p.exists():
        raise SystemExit(f"[FATAL] 缺版本真相源: {p}")
    d = json.loads(p.read_text(encoding="utf-8"))
    cur, prefix = d.get("current"), d.get("cdn_prefix")
    if not cur or not prefix:
        raise SystemExit(f"[FATAL] reader-js.json 缺 current/cdn_prefix: {p}")
    return prefix.rstrip("/") + "/" + cur


def targets(root: Path, files: str | None) -> list[Path]:
    if files:
        out = []
        for line in Path(files).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line.endswith("combined.html"):
                continue
            p = Path(line)
            out.append(p if p.is_absolute() else root / p)
        return out
    return sorted((root / "reading-notes" / "books").glob("*/combined.html"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true", help="把不一致的引用切到真源 URL")
    ap.add_argument("--files", help="只处理该清单里的 combined.html（每行一个路径）")
    ap.add_argument("--root", help="仓库根目录（默认脚本上级）")
    a = ap.parse_args()

    root = Path(a.root).resolve() if a.root else Path(__file__).resolve().parent.parent
    exp = expected(root)
    paths = targets(root, a.files)
    print(f"真相源 current = {exp}")
    print(f"扫描范围       = {len(paths)} 本 combined.html（root={root}）", flush=True)

    bad: list[tuple[Path, str]] = []
    missing: list[Path] = []
    fixed: list[Path] = []
    for p in paths:
        if not p.exists():
            continue
        t = p.read_text(encoding="utf-8", errors="ignore")
        m = SCRIPT_RE.search(t)
        if not m:
            missing.append(p)
            continue
        if m.group(2) != exp:
            bad.append((p, m.group(2)))
            if a.fix:
                t2 = SCRIPT_RE.sub(lambda mm: mm.group(1) + exp + mm.group(3), t, count=1)
                p.write_text(t2, encoding="utf-8", newline="\n")
                fixed.append(p)

    print(f"不一致 = {len(bad)} | 无 reader 引用 = {len(missing)} | 已修 = {len(fixed)}")
    for p, ref in bad[:5]:
        print(f"  [不一致] {p.relative_to(root)} -> {ref}")
    for p in missing[:5]:
        print(f"  [缺引用] {p.relative_to(root)}")
    if bad and not a.fix:
        print("  → 推 main 前必须修好：python3 tools/check_reader_js.py --fix")
    if a.fix:
        print(f"  → 已按真源换 key 修复 {len(fixed)} 本（仅改壳页引用，不覆盖 CDN 上的 JS 文件）")

    # 修复模式下重新校验一遍，确保真的全绿
    if a.fix:
        left = []
        for p in paths:
            if not p.exists():
                continue
            m = SCRIPT_RE.search(p.read_text(encoding="utf-8", errors="ignore"))
            if not m or m.group(2) != exp:
                left.append(p)
        if left:
            print(f"[FAIL] 修复后仍有 {len(left)} 本不一致，如 {left[0]}")
            return 1
        print("[OK] 修复后全绿")
        return 0
    return 1 if (bad or missing) else 0


if __name__ == "__main__":
    sys.exit(main())
