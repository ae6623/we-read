#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""切批：把待重做的书按难度配比切成小批，合并成一份可直接喂给 LLM 的素材卡。

为什么要它：
  逐本 Read + 逐本 Write 的固定开销（每次工具往返、每次重读上下文）比写作本身还贵。
  一次读 8 本素材卡、连着写 8 个 json，能把单本成本压掉一半以上。

配比（默认）：长 25% / 中长 40% / 中 22% / 短 13%
  —— 长书越早做越好，避免尾批集中啃 67 本 ≥2500 字的硬骨头。

用法：
  python3 tools/plan_batch.py                    # 默认 16 本，切 2 片
  python3 tools/plan_batch.py --size 16 --chunk 8
  python3 tools/plan_batch.py --dry              # 只看会挑哪些书

产出：
  需求/<需求目录>/批次-NN.md        每片一个文件（默认 8 本/片）
  需求/<需求目录>/批次分配.tsv      slug → 批次-片，避免重复挑
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from verify_mm_graph import check, tier  # noqa: E402

MM = ROOT / "data" / "mm-graph"
MAT = ROOT / "data" / "mindmap-material"
REQ = ROOT / "需求" / "20261105-导图全量重做-379本"
ASSIGN = REQ / "批次分配.tsv"

MIX = {"long": 0.20, "mid1": 0.45, "mid2": 0.22, "short": 0.13}
BAND = {"long": (8, 10), "mid1": (7, 9), "mid2": (6, 8), "short": (5, 6)}


def band_of(n: int) -> str:
    if n >= 2500:
        return "long"
    if n >= 1800:
        return "mid1"
    if n >= 1200:
        return "mid2"
    return "short"


def chapters(slug: str) -> list[str]:
    p = MAT / (slug + ".txt")
    if not p.exists():
        return []
    text = p.read_text(encoding="utf-8", errors="ignore")
    out, on = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            on = "章节与要点" in line
            continue
        if on and line.strip():
            out.append(line.strip())
    return out


def collect() -> list[dict]:
    items = []
    for p in sorted(MM.glob("*.json")):
        s = p.stem
        if not check(s, verbose=False):
            continue
        mp = MAT / (s + ".txt")
        n = len(mp.read_text(encoding="utf-8", errors="ignore")) if mp.exists() else 0
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        items.append({
            "slug": s,
            "title": d.get("title") or s,
            "chars": n,
            "band": band_of(n),
            "cur_br": len(d.get("branches") or []),
            "cur_pt": sum(len(b.get("points") or []) for b in d.get("branches") or []),
        })
    return items


def load_assigned() -> set[str]:
    if not ASSIGN.exists():
        return set()
    out = set()
    for line in ASSIGN.read_text(encoding="utf-8").splitlines()[1:]:
        if line.strip():
            out.add(line.split("\t")[0])
    return out


def pick(pool: list[dict], size: int) -> list[dict]:
    groups: dict[str, list[dict]] = {k: [] for k in MIX}
    for it in pool:
        groups[it["band"]].append(it)
    # 长书先按字数降序（最硬的先啃），其余按字数升序（快的先出量）
    for k in groups:
        groups[k].sort(key=lambda x: -x["chars"] if k == "long" else x["chars"])
    quota = {k: max(1, round(size * v)) for k, v in MIX.items()}
    while sum(quota.values()) > size:
        k = max(quota, key=lambda x: quota[x] - size * MIX[x])
        quota[k] -= 1
    out = []
    for k, q in quota.items():
        out.extend(groups[k][:q])
    if len(out) < size:
        rest = [x for k in MIX for x in groups[k] if x not in out]
        out.extend(rest[:size - len(out)])
    order = {"long": 0, "mid1": 1, "mid2": 2, "short": 3}
    out.sort(key=lambda x: (order[x["band"]], -x["chars"]))
    return out[:size]


def render(items: list[dict], batch: str, part: str) -> str:
    br_lo = sum(BAND[i["band"]][0] for i in items)
    br_hi = sum(BAND[i["band"]][1] for i in items)
    pt_lo, pt_hi = br_lo * 3, br_hi * 5
    L = [f"# 第 {batch} 批 · 第 {part} 片（{len(items)} 本）", "",
         f"- 目标分支：{br_lo}-{br_hi} 个；概念：{pt_lo}-{pt_hi} 个",
         "- 写法：每本一个 json，`evidence_ref` 只填章号（脚本会展开成原文），写完跑",
         f"  `python3 tools/expand_evidence.py --batch <逗号分隔>` → `python3 tools/verify_mm_graph.py --batch <同>`",
         "- 一遍过：分支数按下面档位凑够，概念 3-5 个/支、≤12 字，note ≤45 字，thesis ≤40 字带句号", ""]
    for i, it in enumerate(items, 1):
        lo, hi = BAND[it["band"]]
        sug = (lo + hi + 1) // 2
        L.append(f"## {i}. {it['slug']} ｜《{it['title']}》")
        L.append(f"素材 {it['chars']} 字 → **{lo}-{hi} 支（建议 {sug}）**，概念 {sug*3}-{sug*5} 个"
                 f"　现 {it['cur_br']} 支/{it['cur_pt']} 概念 ｜ 档位 {it['band']}")
        L.append("")
        chs = chapters(it["slug"])
        L.extend(chs)
        L.append("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=16)
    ap.add_argument("--chunk", type=int, default=8)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--no", type=int, default=0,
                    help="批次号；缺省沿用已有文件的最大号 +1")
    a = ap.parse_args()

    REQ.mkdir(parents=True, exist_ok=True)
    pool = [x for x in collect() if x["slug"] not in load_assigned()]
    if not pool:
        print("没有待办：全部已分配或已完成")
        return 0
    items = pick(pool, a.size)
    if a.dry:
        for it in items:
            print(f"{it['band']:5} {it['chars']:5} {it['slug']}  《{it['title']}》")
        print(f"\n共 {len(items)} 本，剩余池 {len(pool)}")
        return 0

    nums = [int(p.stem.split("-")[1]) for p in REQ.glob("批次-*.md")
            if p.stem.split("-")[1].isdigit()]
    batch = f"{(a.no or ((max(nums) + 1) if nums else 1)):02d}"
    parts = [items[i:i + a.chunk] for i in range(0, len(items), a.chunk)]

    lines = ["slug\t批次", ]
    for pi, part in enumerate(parts, 1):
        tag = f"{batch}-{pi}"
        f = REQ / f"批次-{tag}.md"
        f.write_text(render(part, batch, str(pi)), encoding="utf-8")
        print(f"写出 {f.relative_to(ROOT)}（{len(part)} 本）")
        lines += [f"{it['slug']}\t{tag}" for it in part]

    header = not ASSIGN.exists()
    with ASSIGN.open("a", encoding="utf-8") as fh:
        if header:
            fh.write(lines[0] + "\n")
        fh.write("\n".join(lines[1:]) + "\n")

    brs = [BAND[i["band"]] for i in items]
    print(f"第 {batch} 批共 {len(items)} 本，{len(parts)} 片；"
          f"档位 长{sum(1 for x in items if x['band']=='long')}/"
          f"中长{sum(1 for x in items if x['band']=='mid1')}/"
          f"中{sum(1 for x in items if x['band']=='mid2')}/"
          f"短{sum(1 for x in items if x['band']=='short')}；"
          f"平均素材 {int(statistics.mean(i['chars'] for i in items))} 字")
    return 0


if __name__ == "__main__":
    sys.exit(main())
