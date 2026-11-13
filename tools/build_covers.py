#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探测站点 CDN 上的书封面，生成 ima 封面索引。

封面由站点自己的 CDN 托管：https://cdn.js-dev.cn/assets/covers/<slug>.jpg（首页同源）
书卡顶部要放封面，但导出时不能为每本书都发一次 HEAD（512 次太慢），
所以先跑这个脚本把命中结果落成 assets/data/covers.json，导出器只读表。

用法：
  python3 tools/build_covers.py            # 只探未记录的
  python3 tools/build_covers.py --force    # 全量重探
"""
from __future__ import annotations

import argparse
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
CDN = "https://cdn.js-dev.cn/assets/covers"
OUT = ROOT / "assets" / "data" / "covers.json"

_SESS = None


def _session():
    global _SESS
    if _SESS is None:
        import requests
        from requests.adapters import HTTPAdapter
        s = requests.Session()
        s.mount("https://", HTTPAdapter(pool_connections=8, pool_maxsize=32, max_retries=1))
        s.headers.update({"User-Agent": "wr-cover/1"})
        _SESS = s
    return _SESS


def slugs() -> list[str]:
    h = (ROOT / "index.html").read_text("utf-8", errors="ignore")
    seen, out = set(), []
    for s in re.findall(r'data-slug="([^"]+)"', h):
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def probe(slug: str) -> tuple[str, str]:
    url = f"{CDN}/{quote(slug)}.jpg"
    try:
        r = _session().get(url, timeout=20, headers={"Range": "bytes=0-1024"})
        ct = r.headers.get("content-type", "")
        if r.status_code in (200, 206) and ct.startswith("image"):
            return slug, url
    except Exception:
        pass
    return slug, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--workers", type=int, default=10)
    args = ap.parse_args()

    try:
        old = json.loads(OUT.read_text("utf-8"))
        covers = old.get("covers", {})
    except Exception:
        old, covers = {}, {}

    todo = slugs()
    if not args.force:
        todo = [s for s in todo if s not in covers]

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for i, (slug, url) in enumerate(ex.map(probe, todo), 1):
            if url:
                covers[slug] = url
            else:
                covers.pop(slug, None)
            if i % 100 == 0:
                print(f"  …探测 {i}/{len(todo)}（{time.time()-t0:.0f}s）", flush=True)

    hit = sum(1 for v in covers.values() if v)
    OUT.write_text(json.dumps({
        "built_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "base": CDN,
        "stats": {"slugs": len(slugs()), "hit": hit},
        "covers": covers,
    }, ensure_ascii=False, indent=1), "utf-8")
    print(f"封面命中 {hit}/{len(slugs())} → {OUT}")


if __name__ == "__main__":
    main()
