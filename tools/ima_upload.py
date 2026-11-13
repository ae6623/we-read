#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 ima/cards/*.md 批量入库到 IMA 知识库「we-read」，支持增量与重跑。

依赖：tools/ima_client.py（直连本机 IMA 连接器的 MCP 端点）。

用法：
  python3 tools/ima_upload.py --dry-run                  # 只看要传什么
  python3 tools/ima_upload.py --limit 5                  # 先传 5 本试水
  python3 tools/ima_upload.py --cat 经济理财             # 只传某类目
  python3 tools/ima_upload.py                            # 传 pending.json 里的全部
  python3 tools/ima_upload.py --all-missing              # 不看 pending，传所有未入库的
  python3 tools/ima_upload.py --replace                  # 已入库的也重传（同名覆盖）

台账：ima/manifest.json 的 cards[slug].ima_media_id / synced_at / hash
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ima_client as ima  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
IMA_DIR = ROOT / "ima"
MANIFEST = IMA_DIR / "manifest.json"
KB_NAME = "we-read"
FOLDER_NAME = "书卡笔记v2"
MIME = {"md": "text/markdown"}


def load_manifest():
    return json.loads(MANIFEST.read_text("utf-8"))


def save_manifest(m):
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=1), "utf-8")


def resolve_kb() -> str:
    r = ima.call("get_knowledge_base_list", {"params": [{"limit": 50, "type": "KBT_MINE_KB"}]})
    d = json.loads(ima.text_of(r))
    for blk in d.get("results", []):
        for kb in blk.get("knowledge_base_list", []):
            if kb["basic_info"]["name"] == KB_NAME:
                return kb["id"]
    raise SystemExit(f"没找到知识库 {KB_NAME}")


def resolve_folder(kb_id: str) -> str:
    """在知识库根下找「书卡」文件夹；没有就返回空（传根目录）。"""
    r = ima.call("get_knowledge_list", {"knowledge_base_id": kb_id, "limit": 50})
    d = json.loads(ima.text_of(r))
    for it in d.get("knowledge_list", []):
        if it.get("media_type") == 99 and it.get("title") == FOLDER_NAME:
            return it["media_id"]
    print(f"⚠️ 根目录没有「{FOLDER_NAME}」文件夹，将传到根目录")
    return ""


def folder_titles(kb_id: str, folder_id: str) -> set:
    """拉文件夹里已存在的文件名，用于跳过重复上传（SAVE 会给副本加时间戳后缀）。"""
    out, cur, pages = set(), "", 0
    while folder_id and pages < 20:
        a = {"knowledge_base_id": kb_id, "folder_id": folder_id, "limit": 50}
        if cur:
            a["cursor"] = cur
        d = json.loads(ima.text_of(ima.call("get_knowledge_list", a)))
        for it in d.get("knowledge_list", []):
            if it.get("media_type") != 99:
                out.add(it["title"])
        pages += 1
        if d.get("is_end"):
            break
        cur = d.get("next_cursor") or ""
        if not cur:
            break
    return out


def upload_one(kb_id: str, folder_id: str, path: Path, replace: bool) -> dict:
    raw = path.read_bytes()
    name = path.name
    c = ima.call("create_media", {
        "knowledge_base_id": kb_id, "file_name": name, "file_size": len(raw),
        "file_ext": "md", "content_type": MIME["md"], "apply_upload_mode": 1,
    })
    m = json.loads(ima.text_of(c))
    mid = m["media_id"]
    up = m.get("upload_url") or {}
    if m.get("upload_mode") == 1:
        req = urllib.request.Request(up["presigned_url"], data=raw, method="PUT")
        for k, v in (up.get("auth_headers") or {}).items():
            req.add_header(k, str(v))
        with urllib.request.urlopen(req, timeout=120) as r:
            if r.status not in (200, 201):
                raise RuntimeError(f"PUT {r.status}")
    else:
        raise RuntimeError("需要 COS SDK 的 upload_mode=2，脚本未实现")
    a = ima.call("add_knowledge", {
        "knowledge_base_id": kb_id, "media_id": mid, "folder_id": folder_id,
        # 永远 SAVE：REPLACE 会让服务端把旧条目内容清空、新条目另立，
        # 列表里留下「当前内容已删除」的空壳（2026-11-14 踩过，512 条里 328 条中招）。
        # 需要覆盖时请先删掉旧条目再传，不要用 REPLACE。
        "duplicate_name_strategy": "DUPLICATE_NAME_STRATEGY_SAVE",
    })
    obj = json.loads(ima.text_of(a) or "{}")
    # 台账要记服务端最终确认的 id，否则指向已失效的 create_media id
    return {"media_id": obj.get("media_id") or mid, "bytes": len(raw)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--cat", default="")
    ap.add_argument("--replace", action="store_true",
                    help="忽略台账全量重传（策略仍是 SAVE，不覆盖同名旧条目）")
    ap.add_argument("--all-missing", action="store_true")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--skip-existing", action="store_true",
                    help="跳过文件夹里已存在的同名文件（避免 SAVE 生成 _时间戳 副本）")
    args = ap.parse_args()

    mf = load_manifest()
    cards = mf["cards"]

    if args.all_missing:
        todo = [s for s, e in cards.items() if not e.get("ima_media_id")]
    else:
        pend_path = IMA_DIR / "pending.json"
        if pend_path.exists():
            todo = [x["slug"] for x in json.loads(pend_path.read_text("utf-8"))["items"]]
        else:
            todo = list(cards)
    if args.cat:
        todo = [s for s in todo if cards.get(s, {}).get("cat1") == args.cat]
    if args.replace is False and not args.all_missing:
        todo = [s for s in todo if not cards.get(s, {}).get("ima_media_id") or args.replace]
    if args.limit:
        todo = todo[: args.limit]

    files = []
    for s in todo:
        f = cards.get(s, {}).get("file")
        if f and (ROOT / f).exists():
            files.append((s, ROOT / f))
    print(f"待上传 {len(files)} 本")
    if args.dry_run:
        for s, p in files[:10]:
            print(f"  {p.name}  {p.stat().st_size}B  [{cards[s].get('cat1')}]")
        return

    ima.init()
    kb = resolve_kb()
    folder = resolve_folder(kb)
    print(f"知识库 {kb}｜文件夹 {folder or '（根）'}")
    if args.skip_existing and folder:
        have = folder_titles(kb, folder)
        before = len(files)
        files = [(s, p) for s, p in files if p.name not in have]
        print(f"跳过已存在 {before - len(files)} 本，待传 {len(files)} 本")

    ok = fail = 0
    t0 = time.time()
    lock = __import__("threading").Lock()

    def job(item):
        nonlocal ok, fail
        s, p = item
        for attempt in (1, 2, 3):
            try:
                r = upload_one(kb, folder, p, args.replace)
                time.sleep(0.25)
                with lock:
                    e = cards.setdefault(s, {})
                    e["ima_media_id"] = r["media_id"]
                    e["synced_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
                    ok += 1
                    if ok % 10 == 0:
                        save_manifest(mf)
                        print(f"  ✓ {ok}/{len(files)}  {p.name[:40]}  ({time.time()-t0:.0f}s)")
                return
            except Exception as ex:
                if attempt == 3:
                    with lock:
                        fail += 1
                        print(f"  ✗ {p.name}: {str(ex)[:120]}")
                else:
                    time.sleep(2 * attempt)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        list(ex.map(job, files))

    save_manifest(mf)
    print(f"\n完成：成功 {ok}｜失败 {fail}｜耗时 {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
