#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把在线沙箱上传服务的数据同步回 we-read 仓库，完成「保存进 git」闭环。

用法（在仓库根目录或任意位置）：
    python tools/epub-upload-server/sync_to_git.py --from https://<沙箱域名> [--push] [--dry-run]
    python tools/epub-upload-server/sync_to_git.py            # 从 reading-notes/epub/upload-api.json 读地址

做的事：
  1. GET /api/sync 拿清单、队列、事件
  2. 下载每本 EPUB 到 reading-notes/epub/uploads/，校验 sha256
  3. 写 reading-notes/epub/uploads.json（相对路径，Pages 同源可读）
  4. 把 queued 条目合并进 book-registry.json（按 book_id 去重，revision +1）
  5. 把当日交接事件追加到 agent-communication（按 book_id 去重，不重复追加）
  6. git add + commit；仅 --push 时才 push（默认不抢 main 的并发写）

边界：只同步上传书与队列，不改 roster / 活动锁 / 亲读续读点 / completion / 完读计数；
入队不代表笔记已生成，由读书 Agent 按 reading-state-protocol.md 认领。
"""
import argparse
import datetime as _dt
import hashlib
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.environ.get("REPO_ROOT") or os.path.abspath(os.path.join(HERE, "..", ".."))
EPUB_DIR = os.path.join(REPO_ROOT, "reading-notes", "epub")
UPLOAD_DIR = os.path.join(EPUB_DIR, "uploads")
CATALOG = os.path.join(EPUB_DIR, "uploads.json")
API_CFG = os.path.join(EPUB_DIR, "upload-api.json")
REGISTRY = os.path.join(REPO_ROOT, "skills", "luoyu-reading", "references", "book-registry.json")
COMM_ROOT = os.path.join(REPO_ROOT, "skills", "luoyu-reading", "references", "agent-communication")
TZ = _dt.timezone(_dt.timedelta(hours=8))


def log(msg):
    print(msg, flush=True)


def get_json(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def read_json(path, fallback):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return fallback


def atomic_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def git(args, dry=False):
    if dry:
        log("  [dry-run] git " + " ".join(args))
        return True, ""
    p = subprocess.run(["git", "-C", REPO_ROOT] + args, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=120)
    return p.returncode == 0, (p.stderr or p.stdout or "").strip()[:300]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="base", default="", help="在线上传服务的 base URL")
    ap.add_argument("--push", action="store_true", help="同步后 push origin main（默认不推）")
    ap.add_argument("--dry-run", action="store_true", help="只打印将要做的事，不落盘不提交")
    a = ap.parse_args()

    base = a.base.strip().rstrip("/")
    if not base:
        base = str(read_json(API_CFG, {}).get("base", "")).strip().rstrip("/")
    if not base or not base.startswith(("http://", "https://")):
        log("未配置在线上传服务地址：请在 %s 写入 base，或用 --from 指定" % API_CFG)
        return 2

    log("拉取 %s/api/sync" % base)
    snap = get_json(base + "/api/sync")
    books = (snap.get("uploads") or {}).get("books", [])
    queue = snap.get("queue") or {"books": []}
    events = snap.get("events") or {}
    log("清单 %d 本 · 队列 %d 条 · 事件 %d 天" %
        (len(books), len(queue.get("books", [])), len(events)))

    if a.dry_run:
        for f in snap.get("files", []):
            log("  [dry-run] 下载 %s -> %s" % (f.get("url"), f.get("id")))
        return 0

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    changed = []
    for f in snap.get("files", []):
        bid, url = f.get("id"), f.get("url")
        if not bid or not url:
            continue
        dest = os.path.join(UPLOAD_DIR, bid + ".epub")
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                raw = r.read()
        except Exception as exc:
            log("  ! 下载失败 %s：%s" % (bid, exc))
            continue
        if f.get("sha256") and hashlib.sha256(raw).hexdigest() != f["sha256"]:
            log("  ! sha256 不符，跳过 %s" % bid)
            continue
        if os.path.exists(dest) and open(dest, "rb").read() == raw:
            continue
        with open(dest, "wb") as out:
            out.write(raw)
        changed.append("reading-notes/epub/uploads/%s.epub" % bid)
        log("  + %s (%d 字节)" % (bid, len(raw)))

    # 清单写成相对路径，Pages 同源可读
    cat_books = []
    for b in books:
        c = dict(b)
        c.pop("file_url", None)
        c["file"] = "uploads/%s.epub" % c.get("id", "")
        cat_books.append(c)
    cat_books.sort(key=lambda x: x.get("title", ""))
    atomic_json(CATALOG, {"generated": _dt.datetime.now(TZ).date().isoformat(),
                          "source": "upload", "count": len(cat_books), "books": cat_books})
    changed.append("reading-notes/epub/uploads.json")

    # 队列合并进 registry
    reg = read_json(REGISTRY, None)
    if not isinstance(reg, dict) or not isinstance(reg.get("books"), list):
        log("  ! book-registry.json 结构异常，跳过队列合并")
    else:
        have = set(b.get("book_id") for b in reg["books"])
        added = 0
        for item in queue.get("books", []):
            if item.get("book_id") in have:
                continue
            entry = dict(item)
            entry["upload_path"] = "reading-notes/epub/uploads/%s.epub" % item.get("book_id", "")
            reg["books"].append(entry)
            have.add(item.get("book_id"))
            added += 1
        if added:
            reg["revision"] = int(reg.get("revision", 0)) + 1
            reg["updated_at"] = _dt.datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00")
            atomic_json(REGISTRY, reg)
            changed.append("skills/luoyu-reading/references/book-registry.json")
            log("  + registry 新增 %d 条 queued，revision %s" % (added, reg["revision"]))

    # 交接事件按 book_id 去重追加
    for date, text in sorted(events.items()):
        if not text or not date.replace("-", "").isdigit():
            continue
        y, m, _ = date.split("-")
        d = os.path.join(COMM_ROOT, y, m)
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, date + ".md")
        old = ""
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                old = f.read()
        # 按整个事件块去重（标题含稳定 book_id，多次同步不重复追加）
        blocks, buf = [], []
        for line in text.splitlines():
            if line.startswith("### ") and buf:
                blocks.append("\n".join(buf)); buf = []
            buf.append(line)
        if buf:
            blocks.append("\n".join(buf))
        new_blocks = [b for b in blocks
                      if b.splitlines()[0].strip() and b.splitlines()[0].strip() not in old]
        if new_blocks:
            with open(p, "a", encoding="utf-8") as f:
                f.write("\n".join(new_blocks) + "\n")
            changed.append(os.path.relpath(p, REPO_ROOT).replace(os.sep, "/"))
            log("  + 交接事件 %s 追加 %d 块" % (date, len(new_blocks)))

    if not changed:
        log("没有需要同步的新内容")
        return 0
    ok, msg = git(["add", "--"] + sorted(set(changed)), a.dry_run)
    if not ok:
        log("git add 失败：%s" % msg)
        return 1
    ok, msg = git(["commit", "-m", "upload: 同步在线上传服务的 EPUB 与补书入队（%d 本）" % len(books)], a.dry_run)
    log("已本地 commit" if ok else "commit 未成功：%s" % msg)
    if a.push and ok:
        ok, msg = git(["pull", "--rebase", "origin", "main"], a.dry_run)
        if not ok:
            log("pull --rebase 失败，未 push：%s" % msg)
            return 1
        ok, msg = git(["push", "origin", "HEAD:main"], a.dry_run)
        log("已 push 到 main" if ok else "push 失败：%s" % msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
