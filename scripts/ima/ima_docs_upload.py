#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把引擎仓(wr-latest)的交接/架构文档、需求/方案文档批量上传到 IMA 知识库。

两个目标文件夹（用户在 App 手动建好，MCP 无 create_folder 接口）：
  - 架构 folder_7529456948240818  ← HANDOVER/AGENTS/ARCHITECTURE + 架构规范 + capabilities + a2a 协议
  - 需求 folder_7529457661272251  ← docs/requirements/** (需求.md + 产出-*) + docs 根目录带日期专项文档

落库名规则：加分类前缀保证唯一（IMA SAVE 同名会生成 _时间戳 副本）：
  - 架构: 架构/<原名>.md，如 架构·ARCHITECTURE.md
  - 需求: 需求/<日期>__<需求短名>__<原名>.md，保证跨日期/跨需求不重名

断点续传：ima/docs-upload-manifest.json 记录 源相对路径 -> {media_id, folder, name}；
重跑时已记录的跳过（除非 --force）。

用法:
  python3 scripts/ima/ima_docs_upload.py            # 上传全部（跳过已传）
  python3 scripts/ima/ima_docs_upload.py --dry-run  # 只列清单不传
  python3 scripts/ima/ima_docs_upload.py --limit N  # 只传前 N 个（分批试跑）
  python3 scripts/ima/ima_docs_upload.py --cat arch|req  # 只传某一类
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ima_client as ima  # noqa: E402

ENGINE = Path(os.environ.get("WR_ENGINE", "/root/wr-latest"))
SITE = HERE.parents[1]  # /root/we-read-site
MANIFEST = SITE / "ima" / "docs-upload-manifest.json"

KB = "ima_kb_Z69gwh6y"
FOLDER_ARCH = "folder_7529456948240818"
FOLDER_REQ = "folder_7529457661272251"
MIME_MD = "text/markdown"

# 敏感文件/目录：绝不上传
DENY_EXACT = {
    "docs/credentials/a2a-agents-token.md",
    "docs/credentials/a2a-luoyuJi-token.md",
    "docs/credentials/a2a-qcoder-luoyu-token.md",
    "docs/credentials/admin-token.md",
}


def build_arch() -> list[tuple[Path, str]]:
    out = []
    for f in ["HANDOVER.md", "AGENTS.md", "ARCHITECTURE.md", "README.md", "流程.md",
              "START-HERE.md", "DEPLOY.md", "a2a.md", "A2A-AGENT2.md", "A2A-WEREAD-AUTO2.md"]:
        p = ENGINE / f
        if p.is_file():
            out.append((p, f"架构·{f}"))
    docs = ENGINE / "docs"
    for p in sorted(docs.glob("*.md")):
        if "-20" not in p.name and str(p.relative_to(ENGINE)) not in DENY_EXACT:
            out.append((p, f"架构·{p.name}"))
    for sub, prefix in [("capabilities", "架构·能力"), ("a2a", "架构·A2A")]:
        for p in sorted((docs / sub).glob("*.md")):
            out.append((p, f"{prefix}-{p.name}"))
    return out


def build_req() -> list[tuple[Path, str]]:
    out = []
    reqroot = ENGINE / "docs" / "requirements"
    for p in sorted(reqroot.rglob("*.md")):
        if p.name == "README.md":
            name = "需求·归档规范README.md"
        elif p.parent == reqroot:
            # requirements 根目录的汇总/规范类文档，用干净落库名（不带日期/短名）
            name = f"需求·{p.name}"
        else:
            rel = p.relative_to(reqroot)
            parts = rel.parts  # (日期, 需求短名, 文件)
            date = parts[0]
            short = parts[1] if len(parts) >= 2 else "misc"
            fname = parts[-1]
            name = f"需求·{date}__{short}__{fname}"
        out.append((p, name))
    docs = ENGINE / "docs"
    for p in sorted(docs.glob("*.md")):
        if "-20" in p.name:
            out.append((p, f"需求·{p.name}"))
    return out


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text("utf-8"))
    return {"items": {}}


def save_manifest(m: dict) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=1), "utf-8")


def upload_one(path: Path, kb: str, folder: str, name: str) -> str:
    raw = path.read_bytes()
    c = ima.call("create_media", {
        "knowledge_base_id": kb, "file_name": name, "file_size": len(raw),
        "file_ext": "md", "content_type": MIME_MD, "apply_upload_mode": 1,
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
        raise RuntimeError("需要 upload_mode=2 COS SDK，脚本未实现")
    a = ima.call("add_knowledge", {
        "knowledge_base_id": kb, "media_id": mid, "folder_id": folder,
        "duplicate_name_strategy": "DUPLICATE_NAME_STRATEGY_SAVE",
    })
    obj = json.loads(ima.text_of(a) or "{}")
    return obj.get("media_id") or mid


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--cat", choices=["arch", "req"], default="")
    args = ap.parse_args()

    jobs = []
    if args.cat in ("", "arch"):
        jobs += [("arch", FOLDER_ARCH, p, n) for p, n in build_arch()]
    if args.cat in ("", "req"):
        jobs += [("req", FOLDER_REQ, p, n) for p, n in build_req()]

    mf = load_manifest()
    done = mf["items"]
    todo = [(c, f, p, n) for c, f, p, n in jobs if str(p.relative_to(ENGINE)) not in done]
    if args.limit:
        todo = todo[: args.limit]

    print(f"总任务 {len(jobs)}｜已完成 {len(jobs)-len(todo)}｜本次待传 {len(todo)}")
    if args.dry_run:
        for c, f, p, n in todo[:20]:
            print(f"  [{c}] {n}  <- {p.relative_to(ENGINE)}")
        print(f"  ... 另 {max(0,len(todo)-20)} 个")
        return

    if not todo:
        print("没有待上传，结束")
        return

    ima.init()
    ok = fail = 0
    t0 = time.time()
    for i, (cat, folder, path, name) in enumerate(todo, 1):
        key = str(path.relative_to(ENGINE))
        for attempt in (1, 2, 3):
            try:
                mid = upload_one(path, KB, folder, name)
                done[key] = {"media_id": mid, "folder": folder, "name": name, "cat": cat,
                             "synced_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
                save_manifest(mf)
                ok += 1
                print(f"  ✓ {ok}/{len(todo)} [{cat}] {name[:50]}  ({time.time()-t0:.0f}s)", flush=True)
                break
            except Exception as e:
                if attempt == 3:
                    fail += 1
                    print(f"  ✗ [{cat}] {name[:50]}  ERROR={e}", flush=True)
                else:
                    time.sleep(1.5 * attempt)
    print(f"\n完成：成功 {ok}｜失败 {fail}｜耗时 {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
