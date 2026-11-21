#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""书架健康守卫 —— 每张首页书卡必须有封面、有页面、且是现行模板。

为什么需要它
  2026-11-18 事故：weread-auto 大纲批一次上了 79 本，只发 mindmap / outline /
  overview，没跑 `POST /api/combine` 也没下封面。书架于是出现两批坏卡：
    · 62 张无封面（退化成渐变素封）
    · 33 本仍是旧模板 overview.html，不是现行 combined.html
  两个症状都是「产物少了最后几步」，但旧守卫只看 hero.json 登记表，全绿放行。

判定口径（与 tools/booklist/booklist_factory.py 一致）
  combined.html 存在          → new     现行「全书领读」模板
  只有 overview.html          → legacy  旧「全书视角·读前通读」模板
  只有 mindmap.html           → stub    连外壳都没有，卡片不该上架

用法
  python3 tools/check_shelf.py               # 体检 + 写 assets/data/shelf-health.json
  python3 tools/check_shelf.py --strict      # legacy 也算失败（老模板清零后的门禁）
  python3 tools/check_shelf.py --root /path  # 指定仓库根

退出码
  0  封面齐、目标页都在（legacy 只报告）
  1  有卡缺封面或目标页不存在；--strict 下 legacy 也计 1
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path

BOOKS = "reading-notes/books"


def cover_ok(p: Path) -> bool:
    if not p.is_file() or p.stat().st_size < 3000:
        return False
    with p.open("rb") as f:
        return f.read(2) == b"\xff\xd8"


def shelf_cards(root: Path) -> list[dict]:
    idx = root / "index.html"
    if not idx.is_file():
        raise SystemExit("index.html 不存在，无法体检")
    h = idx.read_text(encoding="utf-8", errors="ignore")
    # 只体检「书架」面板：panel-whole（全书视角）→ panel-soon（即将上线）之间。
    i = h.find('id="panel-whole"')
    j = h.find('id="panel-soon"', i + 1)
    body = h[i:j] if i > 0 and j > i else h
    out = []
    for card in re.findall(r'<article[^>]*archive-card.*?</article>', body, re.S):
        m = re.search(r'data-slug="([^"]+)"', card)
        if not m:
            continue
        a = re.search(r'class="card-title-link"[^>]*href="([^"]+)"', card)
        t = re.search(r'class="card-title-link"[^>]*>(.*?)</a>', card, re.S)
        out.append({
            "slug": m.group(1),
            "href": a.group(1) if a else "",
            "title": re.sub(r"<[^>]+>", "", t.group(1)).strip("《》") if t else "",
        })
    return out


def generation(bdir: Path) -> str:
    if (bdir / "combined.html").is_file():
        return "new"
    if (bdir / "overview.html").is_file():
        return "legacy"
    if (bdir / "mindmap.html").is_file():
        return "stub"
    return "missing"


def nocover_set(root: Path) -> set[str]:
    """hero.json 里正式登记「确实没有封面」的书。

    check_covers 早就认这份名单（本地自建书、微读书库里查不到的条目），
    check_shelf 却没读 —— 同一本书一个门禁绿、一个门禁红，白名单形同虚设。
    """
    try:
        data = json.loads((root / "assets" / "data" / "hero.json").read_text(encoding="utf-8"))
        return set(data.get("nocover") or [])
    except Exception:  # noqa: BLE001
        return set()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", help="仓库根目录（默认脚本上一级）")
    ap.add_argument("--strict", action="store_true", help="legacy 旧模板也算失败")
    ap.add_argument("--json", default="assets/data/shelf-health.json")
    a = ap.parse_args()

    root = Path(a.root).resolve() if a.root else Path(__file__).resolve().parent.parent
    covers = root / "assets" / "covers"
    exempt = nocover_set(root)
    cards = shelf_cards(root)
    no_cover, broken, legacy, stub = [], [], [], []
    for c in cards:
        slug = c["slug"]
        if slug not in exempt and not cover_ok(covers / f"{slug}.jpg"):
            no_cover.append(c)
        href = c["href"]
        if href.startswith(BOOKS + "/"):
            parts = href.split("/")
            bdir = root / BOOKS / parts[2]
            gen = generation(bdir)
            if not (root / href).is_file():
                broken.append({**c, "reason": "目标页不存在"})
            elif gen == "legacy":
                legacy.append({**c, "gen": gen})
            elif gen == "stub":
                stub.append({**c, "gen": gen})
            elif gen == "missing":
                broken.append({**c, "reason": "目录里没有任何页面"})

    print(f"书架卡 = {len(cards)} 张 · 缺封面 {len(no_cover)} · 死目标 {len(broken)} "
          f"· 旧模板 {len(legacy)} · 仅导图 {len(stub)}", flush=True)
    for c in no_cover[:8]:
        print(f"  [缺封面] assets/covers/{c['slug']}.jpg  {c['title'][:24]}")
    for c in broken[:8]:
        print(f"  [死目标] {c['href']}  {c['title'][:24]} ({c['reason']})")
    for c in legacy[:8]:
        print(f"  [旧模板] {c['slug']}  {c['title'][:24]}  → 需要跑 POST /api/combine")

    out = {
        "generated_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(timespec="seconds"),
        "total": len(cards),
        "missing_cover": [c["slug"] for c in no_cover],
        "broken": [{"slug": c["slug"], "href": c["href"], "reason": c["reason"]} for c in broken],
        "legacy_template": [{"slug": c["slug"], "title": c["title"], "href": c["href"]} for c in legacy],
        "stub_only": [c["slug"] for c in stub],
    }
    dest = root / a.json
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"报告 → {a.json}")

    fail = bool(no_cover or broken) or (a.strict and bool(legacy))
    if fail:
        print("  → 先把缺失封面补齐（tools/check_covers.py --fix），"
              "旧模板书跑 POST /api/combine 再上架")
        return 1
    if legacy:
        print(f"  [提示] 仍有 {len(legacy)} 本旧模板书，跑 combine 后会自动转绿（--strict 会拦）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
