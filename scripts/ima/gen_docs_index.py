#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成「文档坐标汇总.md」——需求/设计/架构文档的单一真相源索引。

为什么需要它
------------
归档规范（we-read-auto/docs/requirements/README.md）只规定了文档「放哪里」，
但没有一张总表能一眼看到：现在一共有哪些需求/设计文档、各自坐标在哪、
哪些已同步到 IMA。结果是每次新产出文档后，各 Agent 不知道该往哪登记，
也不知道 IMA 还差哪些没传。

本脚本读站点仓的 IMA 上传 manifest（ima/docs-upload-manifest.json），
扫描引擎仓的实际文档，生成一张带「IMA 同步状态」列的汇总表：

  - ✅已同步：manifest 里有该文档、且 media_id 有效
  - ⬜未同步：本地有文档但 manifest 没有 → 提醒该补传 IMA

用法
----
  python3 scripts/ima/gen_docs_index.py            # 生成（写引擎仓 docs/requirements/文档坐标汇总.md）
  python3 scripts/ima/gen_docs_index.py --stdout   # 只打印，不写文件

新文档产出流程（写进归档规范）：
  1. 按 v2 规范把 需求.md / 产出-*.md 放进 docs/requirements/<日期>/<短名>/
  2. 跑本脚本刷新汇总表（新文档会以 ⬜未同步 出现）
  3. 跑 ima_docs_upload.py 补传（已传自动跳过）
  4. 再跑一次本脚本，未同步项变 ✅已同步；一起提交
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

ENGINE = Path(os.environ.get("WR_ENGINE", "/root/wr-latest"))
SITE = HERE.parents[1]  # /root/we-read-site
MANIFEST = SITE / "ima" / "docs-upload-manifest.json"
OUT = ENGINE / "docs" / "requirements" / "文档坐标汇总.md"

FOLDER_ARCH = "folder_7529456948240818"
FOLDER_REQ = "folder_7529457661272251"
FOLDER_NAME = {FOLDER_ARCH: "架构", FOLDER_REQ: "需求"}


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text("utf-8")).get("items", {})
    return {}


def synced(key: str) -> bool:
    """manifest 里有该 key 且 media_id 有效即为已同步。"""
    v = MANIFEST_ITEMS.get(key)
    return bool(v and v.get("media_id"))


def doc_type(fname: str) -> str:
    if fname == "需求.md":
        return "需求/方案"
    if fname.startswith("产出-"):
        return "产出/设计"
    if fname == "README.md":
        return "规范"
    return "文档"


def collect() -> list[dict]:
    """返回 [{cat, date, unit, type, key, rel, ima_name, synced, synced_at}]。"""
    rows = []
    # ── 架构类（与 ima_docs_upload.py build_arch 同口径）──
    arch_top = ["HANDOVER.md", "AGENTS.md", "ARCHITECTURE.md", "README.md", "流程.md",
                "START-HERE.md", "DEPLOY.md", "DEPLOY-CDN.md", "a2a.md", "A2A-AGENT2.md", "A2A-WEREAD-AUTO2.md"]
    arch_files = []
    for f in arch_top:
        p = ENGINE / f
        if p.is_file():
            arch_files.append(p)
    for p in sorted((ENGINE / "docs").glob("*.md")):
        if "-20" not in p.name:
            arch_files.append(p)
    for sub in ("capabilities", "a2a"):
        arch_files += sorted((ENGINE / "docs" / sub).glob("*.md"))
    for p in arch_files:
        key = str(p.relative_to(ENGINE))
        v = MANIFEST_ITEMS.get(key, {})
        rows.append(dict(cat="架构", date="—", unit="架构/规范",
                         type=doc_type(p.name), key=key, rel=key,
                         ima_name=v.get("name", ""), synced=synced(key),
                         synced_at=v.get("synced_at", "")))

    # ── 需求类（与 build_req 同口径）──
    reqroot = ENGINE / "docs" / "requirements"
    for p in sorted(reqroot.rglob("*.md")):
        rel = p.relative_to(ENGINE)
        key = str(rel)
        parts = p.relative_to(reqroot).parts
        if p.parent == reqroot:
            # requirements 根目录：规范 / 汇总表，无日期与短名
            if p.name == "README.md":
                date, unit = "—", "归档规范"
            else:
                date, unit = "—", "汇总/规范"
        else:
            date = parts[0] if parts else "—"
            unit = parts[1] if len(parts) >= 2 else "misc"
        v = MANIFEST_ITEMS.get(key, {})
        rows.append(dict(cat="需求", date=date, unit=unit,
                         type=doc_type(p.name), key=key, rel=key,
                         ima_name=v.get("name", ""), synced=synced(key),
                         synced_at=v.get("synced_at", "")))
    # docs 根目录带日期专项文档（v2 口径）
    for p in sorted((ENGINE / "docs").glob("*.md")):
        if "-20" in p.name:
            key = str(p.relative_to(ENGINE))
            v = MANIFEST_ITEMS.get(key, {})
            rows.append(dict(cat="需求", date="专项", unit="docs根目录",
                             type="专项复盘", key=key, rel=key,
                             ima_name=v.get("name", ""), synced=synced(key),
                             synced_at=v.get("synced_at", "")))
    return rows


def render(rows: list[dict]) -> str:
    total = len(rows)
    done = sum(1 for r in rows if r["synced"])
    todo = total - done
    L = []
    L.append("# 文档坐标汇总（单一真相源 · 自动生成）")
    L.append("")
    L.append("> 本表由 `scripts/ima/gen_docs_index.py` 自动生成，**请勿手工编辑表格正文**。")
    L.append("> 归档位置与命名规范见 [README.md](README.md)（v2）；IMA 同步状态取自站点仓")
    L.append("> `ima/docs-upload-manifest.json`。新需求/设计文档产出后按文末流程刷新本表。")
    L.append("")
    L.append(f"**统计**：共 **{total}** 份（架构 {sum(1 for r in rows if r['cat']=='架构')} / "
             f"需求 {sum(1 for r in rows if r['cat']=='需求')}）· "
             f"✅已同步 IMA **{done}** · ⬜未同步 **{todo}**")
    L.append("")
    L.append("## 坐标表")
    L.append("")
    L.append("| # | 类别 | 日期 | 需求/条目 | 文档类型 | 仓库坐标（相对 we-read-auto/） | IMA同步 | IMA落库名 |")
    L.append("|---:|---|---|---|---|---|---|---|")
    # 架构在前，需求按日期倒序
    ordered = sorted(rows, key=lambda r: (r["cat"] != "架构", r["date"] == "—", r["date"], r["unit"], r["type"]), reverse=False)
    arch = [r for r in ordered if r["cat"] == "架构"]
    req = sorted([r for r in rows if r["cat"] == "需求"],
                 key=lambda r: (r["date"] == "专项" or r["date"] == "—", r["date"], r["unit"]), reverse=True)
    for i, r in enumerate(arch + req, 1):
        mark = "✅已同步" if r["synced"] else "⬜未同步"
        name = r["ima_name"] or "—"
        L.append(f"| {i} | {r['cat']} | {r['date']} | {r['unit']} | {r['type']} | "
                 f"`{r['rel']}` | {mark} | {name} |")
    L.append("")
    L.append("## 新文档产出后怎么更新（每次都要做）")
    L.append("")
    L.append("1. 按 v2 规范落地文档：`docs/requirements/<YYYY-MM-DD>/<需求短名>/` 下的 `需求.md` / `产出-*.md`；"
             "架构/规范类放引擎仓约定位置。")
    L.append("2. 刷新本表：`python3 scripts/ima/gen_docs_index.py` —— 新文档会以 **⬜未同步** 出现在表尾。")
    L.append("3. 同步到 IMA：`python3 scripts/ima/ima_docs_upload.py`（已传自动跳过，只传未同步的新文档）。")
    L.append("4. 再刷新一次本表：新文档状态变 **✅已同步**；把本表连同新文档一起 `git add` 提交。")
    L.append("")
    L.append("> 只在「确认已落库 IMA」后才标 ✅；状态由 manifest 自动判定，不要手改。")
    L.append("")
    L.append(f"<!-- 生成时间 {datetime.now().astimezone().isoformat(timespec='seconds')} · "
             f"共 {total} 条 / 已同步 {done} -->")
    return "\n".join(L)


def main() -> None:
    global MANIFEST_ITEMS
    MANIFEST_ITEMS = load_manifest()
    ap = argparse.ArgumentParser()
    ap.add_argument("--stdout", action="store_true", help="只打印，不写文件")
    args = ap.parse_args()
    rows = collect()
    text = render(rows)
    if args.stdout:
        print(text)
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(text, "utf-8")
        print(f"已写入 {OUT}（{len(rows)} 条，已同步 {sum(1 for r in rows if r['synced'])}）")


if __name__ == "__main__":
    main()
