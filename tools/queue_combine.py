#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""queue_combine.py — 旧模板书（只有 overview.html）批量转现行 combined 模板。

背景：2026-11-18 一批 79 本只发了 mindmap / outline / overview，没跑 combine，
书架留下 33 张旧模板卡。combine 硬依赖 mindmap.html（无 mindmap 直接跳过），
所以本工具把「能转的」排队跑完，转不了的单独列 blocked 交回生产侧。

流程（每本一本，串行排队）：
  1 从 GitHub tree 判定世代：有 combined.html=已转；无 combined 但有 mindmap=可转
  2 按需拉取 mindmap.html / outline.html / quiz.json / outline.json 到本地镜像目录
  3 调 overview_gen.combine_page.render_book 产出 combined.html + combined-data.html
  4 全部跑完后一次 publish_paths 提交（也可 --no-publish 只本地跑）

用法：
  python3 queue_combine.py --check                 # 只体检，打印队列
  python3 queue_combine.py --run --limit 5         # 先跑 5 本试水
  python3 queue_combine.py --run --publish         # 全量跑 + 发布
  python3 queue_combine.py --run --only a,b,c      # 指定 slug
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

API = "https://api.github.com"
OWNER, REPO = "ae6623", "we-read"
ENGINE = Path(os.environ.get("WEREAD_ENGINE") or "/root/wr-latest")
SITE = Path(os.environ.get("WEREAD_SITE") or "/root/we-read-site")
BOOKS = SITE / "reading-notes" / "books"
NEED = ("mindmap.html", "outline.html", "quiz.json", "outline.json")


def token() -> str:
    for p in ("/root/.wr-auth/token", "/root/.wr-auth/github_token"):
        f = Path(p)
        if f.is_file():
            t = f.read_text().strip()
            if t:
                return t
    t = os.environ.get("GITHUB_TOKEN", "").strip()
    if t:
        return t
    raise SystemExit("缺少 GitHub token：export GITHUB_TOKEN=...")


class GH:
    def __init__(self, tok):
        self.tok = tok

    def get(self, path: str, raw=False):
        import requests
        last = None
        for attempt in range(4):
            try:
                r = requests.get(
                    API + path,
                    headers={"Authorization": "Bearer " + self.tok,
                             "Accept": "application/vnd.github.raw" if raw else "application/vnd.github+json",
                             "User-Agent": "queue-combine",
                             "Connection": "close"},
                    timeout=120, stream=True)
                buf = bytearray()
                for chunk in r.iter_content(65536):
                    buf += chunk
                r.close()
                if r.status_code >= 400:
                    raise RuntimeError(f"HTTP {r.status_code}: {bytes(buf)[:200]}")
                return bytes(buf)
            except Exception as e:
                last = e
                time.sleep(2 + attempt * 2)
        raise last

    def tree(self):
        cache = Path("/tmp/gh-tree-cache.json")
        if cache.is_file() and time.time() - cache.stat().st_mtime < 3600:
            d = json.loads(cache.read_text())
        else:
            d = json.loads(self.get(f"/repos/{OWNER}/{REPO}/git/trees/main?recursive=1"))
            cache.write_text(json.dumps(d))
        return {t["path"]: t["sha"] for t in d.get("tree", []) if t.get("type") == "blob"}

    def blob(self, sha: str) -> bytes:
        c = Path("/tmp/gh-blob-cache") / sha
        if c.is_file():
            return c.read_bytes()
        d = json.loads(self.get(f"/repos/{OWNER}/{REPO}/git/blobs/{sha}"))
        data = base64.b64decode(d["content"])
        c.parent.mkdir(exist_ok=True)
        c.write_bytes(data)
        return data


def shelf_slugs(gh: GH) -> dict:
    """书架面板的卡：slug → 标题链接 href。"""
    idx = gh.get(f"/repos/{OWNER}/{REPO}/contents/index.html", raw=True).decode("utf-8", "ignore")
    i = idx.find('id="panel-whole"')
    j = idx.find('id="panel-soon"', i + 1)
    body = idx[i:j] if i > 0 and j > i else idx
    out = {}
    for card in re.findall(r"<article[^>]*archive-card.*?</article>", body, re.S):
        m = re.search(r'data-slug="([^"]+)"', card)
        a = re.search(r'class="card-title-link"[^>]*href="([^"]+)"', card)
        if m:
            out[m.group(1)] = a.group(1) if a else ""
    return out


def build_queue(gh: GH, only=None):
    tree = gh.tree()
    books = {}
    for p in tree:
        m = re.match(rf"{re.escape('reading-notes/books')}/([^/]+)/(.+)$", p)
        if m:
            books.setdefault(m.group(1), set()).add(m.group(2))
    shelf = shelf_slugs(gh)
    ready, blocked, done = [], [], []
    for slug in sorted(books):
        fs = books[slug]
        if only and slug not in only:
            continue
        if "combined.html" in fs:
            done.append(slug)
            continue
        if slug not in shelf:
            continue  # 不上架的残书不占队列
        rec = {"slug": slug, "title": "", "href": shelf[slug]}
        if "mindmap.html" in fs:
            ready.append(rec)
        else:
            blocked.append(rec)
    return ready, blocked, len(done), tree


def fetch_one(gh: GH, tree: dict, slug: str) -> dict:
    d = BOOKS / slug
    d.mkdir(parents=True, exist_ok=True)
    got = []
    for name in NEED:
        rel = f"reading-notes/books/{slug}/{name}"
        if rel not in tree:
            continue
        p = d / name
        p.write_bytes(gh.blob(tree[rel]))
        got.append((name, p.stat().st_size))
    return {"slug": slug, "files": got}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", default="")
    ap.add_argument("--json", default="/tmp/queue-combine.json")
    a = ap.parse_args()

    gh = GH(token())
    only = set(x for x in a.only.split(",") if x)
    ready, blocked, ndone, tree = build_queue(gh, only)
    print(f"已转 combined {ndone} 本 · 队列可转 {len(ready)} 本 · 无 mindmap 阻塞 {len(blocked)} 本")
    for r in ready[:40]:
        print("  ✓", r["slug"])
    for r in blocked:
        print("  ✗ 阻塞（无 mindmap）", r["slug"])
    if a.check or not a.run:
        json.dump({"ready": ready, "blocked": blocked}, open(a.json, "w"), ensure_ascii=False, indent=1)
        return 0

    if a.limit:
        ready = ready[:a.limit]

    # 1) 拉素材（并发 6）
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=6) as ex:
        fetched = list(ex.map(lambda r: fetch_one(gh, tree, r["slug"]), ready))
    print(f"[fetch] {len(fetched)} 本，{time.time()-t0:.1f}s")

    # 2) 排队 combine（串行，模块导入一次）
    env = dict(os.environ, COMBINE_BOOKS=str(BOOKS), PYTHONPATH=str(ENGINE))
    ok, skip, fail = [], [], []
    for i, r in enumerate(ready, 1):
        slug = r["slug"]
        p = subprocess.run([sys.executable, "-m", "overview_gen.combine_page", "--slug", slug],
                           cwd=str(ENGINE), env=env, capture_output=True, text=True)
        out = (p.stdout or "").strip().splitlines()
        line = out[-1] if out else ""
        if p.returncode == 0 and line.startswith("ok "):
            ok.append(slug)
        elif line.startswith("skip"):
            skip.append(slug)
        else:
            fail.append({"slug": slug, "err": (p.stderr or line)[-300:]})
        print(f"  [{i}/{len(ready)}] {line or 'ERR'}")

    # 3) 发布
    pub = None
    if a.publish and ok:
        sys.path.insert(0, str(ENGINE / "tools" / "engine" / "deploy"))
        from gh_api import GhApi
        api = GhApi(OWNER, REPO, gh.tok, proxy="")
        files = {}
        for slug in ok:
            for name in ("combined.html", "combined-data.html"):
                f = BOOKS / slug / name
                if f.is_file():
                    files[f"reading-notes/books/{slug}/{name}"] = f.read_text(encoding="utf-8")
        stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime())
        o, msg, detail = api.publish_paths(
            files, f"combine: 旧模板批量转 combined 模板 · {len(ok)} 本 · {stamp}",
            branch="main")
        pub = {"ok": o, "msg": msg, "detail": detail}
        print("[publish]", o, msg, detail.get("changed"))

    rep = {"ready": len(ready), "ok": ok, "skip": skip, "fail": fail,
           "blocked": blocked, "publish": pub}
    json.dump(rep, open(a.json, "w"), ensure_ascii=False, indent=1)
    print(f"[done] ok={len(ok)} skip={len(skip)} fail={len(fail)} → {a.json}")
    return 0 if not fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
