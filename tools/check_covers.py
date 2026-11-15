#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全站封面守卫 —— 与 check_reader_js.py 并列的第二道提交前闸门。

真相源：`assets/data/hero.json` 的 `ids`（slug→bookId，代表已登记上架的书）
规则：每本已登记且不在 `nocover` 白名单里的书，必须存在
      `assets/covers/<slug>.jpg`，且是有效 JPEG（>3KB、\xff\xd8 开头）。

背景：2026-11-15 补产 80 本时，manifest 里 80/80 都有微信读书官方 `cover` URL，
      但生产脚本从未下载/推送封面，线上 80 张卡全部退回渐变占位（WE READ 素封）。
      上一轮 PROCESS-FIX 写的「形态基线」列了 script src / link href / 10 data-key /
      导航 / chips / 标注，**唯独漏了封面文件** —— 故补本守卫，把封面纳入硬闸门。

用法：
  python3 tools/check_covers.py                          # 全站检查；缺封面 → 退出码 1
  python3 tools/check_covers.py --files /tmp/list.txt   # 只检查清单里出现的 slug
  python3 tools/check_covers.py --fix --manifest /tmp/qingyouji_manifest.json
        # 对缺失封面按 manifest 的 cover URL 补下载（s_ → t9_ 高清，428×616）
  python3 tools/check_covers.py --root /path/to/we-read # 指定仓库根

**推 main 前必跑本脚本；退出码非 0 时禁止 `push_snapshot.py --main`。**
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

# 历史遗留：本次 80 本之外、早于本次补产就缺封面的书。不是本次事故范围，
# 但保留在此让全站守卫可绿；根治时应补图或正式加入 hero.json 的 nocover。
KNOWN_EXEMPT = {"ren-lei-jian-shi-san-bu-qu"}

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "Chrome/126 Safari/537.36",
    "Referer": "https://weread.qq.com/",
}


def root_of(a) -> Path:
    return Path(a.root).resolve() if a.root else Path(__file__).resolve().parent.parent


def registered(root: Path, files: str | None) -> list[str]:
    """返回需要检查封面的 slug 列表。"""
    hero = json.loads((root / "assets" / "data" / "hero.json").read_text(encoding="utf-8"))
    ids = hero.get("ids", {})
    nocover = set(hero.get("nocover", []))
    slugs = set(ids) if isinstance(ids, dict) else set(ids)
    if files:
        wanted = set()
        for line in Path(files).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            # 支持 reading-notes/books/<slug>/... 与 _data/books/<slug>.json
            m = re.search(r"(?:books/|_data/books/)([^/\.]+)", line)
            if m:
                wanted.add(m.group(1))
        slugs &= wanted
    return sorted(s for s in slugs - nocover - KNOWN_EXEMPT)


def cover_ok(p: Path) -> bool:
    if not p.is_file() or p.stat().st_size < 3000:
        return False
    with p.open("rb") as f:
        return f.read(2) == b"\xff\xd8"


def fetch_cover(slug: str, url: str, covers: Path) -> str:
    dest = covers / f"{slug}.jpg"
    if cover_ok(dest):
        return "exists"
    big = url.replace("/s_", "/t9_")

    def get(u: str) -> bytes:
        req = urllib.request.Request(u, headers=UA)
        return urllib.request.urlopen(req, timeout=25).read()

    try:
        try:
            data = get(big)
            if len(data) < 3000:
                raise ValueError("t9 too small")
        except Exception:
            data = get(url)
        if not data.startswith(b"\xff\xd8") or len(data) < 3000:
            raise ValueError(f"invalid jpeg {len(data)}B")
        covers.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return f"ok:{len(data)}"
    except Exception as e:
        return f"ERR:{type(e).__name__}:{str(e)[:60]}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", help="只检查该清单里出现的 slug")
    ap.add_argument("--fix", action="store_true", help="按 manifest 的 cover URL 补下载缺失封面")
    ap.add_argument("--manifest", help="补下载用的书单（含 cover 字段）")
    ap.add_argument("--root", help="仓库根目录（默认脚本上级）")
    a = ap.parse_args()

    root = root_of(a)
    covers = root / "assets" / "covers"
    slugs = registered(root, a.files)
    print(f"扫描范围 = {len(slugs)} 本已登记书（root={root}）", flush=True)

    missing = [s for s in slugs if not cover_ok(covers / f"{s}.jpg")]
    print(f"缺封面 = {len(missing)}")
    for s in missing[:8]:
        print(f"  [缺] assets/covers/{s}.jpg")

    if a.fix and missing:
        if not a.manifest:
            print("[FATAL] --fix 需要 --manifest 提供 cover URL")
            return 2
        m = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
        rows = m["books"] if isinstance(m, dict) else m
        url_of = {r["slug"]: r.get("cover") for r in rows if isinstance(r, dict) and r.get("slug")}
        done, fail = [], []
        for i, s in enumerate(missing, 1):
            u = url_of.get(s)
            r = fetch_cover(s, u, covers) if u else "ERR:no-cover-in-manifest"
            (done if r.startswith(("ok", "exists")) else fail).append((s, r))
            time.sleep(0.45)
            if i % 20 == 0:
                print(f"  [{i}/{len(missing)}] ok={len(done)} fail={len(fail)}", flush=True)
        print(f"补下载：成功 {len(done)} / 失败 {len(fail)}")
        for s, w in fail[:8]:
            print(f"  [FAIL] {s} -> {w}")
        missing = [s for s in slugs if not cover_ok(covers / f"{s}.jpg")]

    if missing:
        print(f"  → 推 main 前必须修好：python3 tools/check_covers.py --fix --manifest <书单>")
        return 1
    print("[OK] 封面全绿（每本已登记书均有有效 JPEG 封面）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
