#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全站重刷「结构导图」SVG —— 只换 data-key="svg" 这一段，其它模块一字不动。

用途：render_svg 改版（节点文字折行、viewBox 收窄）后，把已上线的书同步过来。

用法：
  python tools/refresh_svg.py --dry
  python tools/refresh_svg.py            # 全站有 outline 的书
  python tools/refresh_svg.py --slug a,b
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import fill_combined_modules as F  # noqa: E402

SEC = re.compile(r'<section class="mmx-svgwrap" data-key="svg">.*?</section>', re.S)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", default="")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    books = F.BOOKS
    slugs = ([x.strip() for x in a.slug.split(",") if x.strip()] if a.slug
             else sorted(d.name for d in books.iterdir() if d.is_dir()))
    ok = skip = 0
    for slug in slugs:
        page = books / slug / "combined-data.html"
        if not page.exists():
            continue
        chs = F.chapters_of(slug)
        if not chs:
            skip += 1
            continue
        new = F.render_svg(chs, F.meta_of(slug)["title"])
        if not new:
            skip += 1
            continue
        s = page.read_text(encoding="utf-8", errors="ignore")
        if not SEC.search(s):
            skip += 1
            continue
        if SEC.search(s).group(0) == new:
            continue
        if a.dry:
            ok += 1
            continue
        page.write_text(SEC.sub(lambda m: new, s, count=1), encoding="utf-8")
        ok += 1
    print("重刷 %d 本，跳过 %d 本" % (ok, skip))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
