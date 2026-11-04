#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 LLM 归纳出的「中心命题 → 议题分支 → 关键概念」渲染成真正的思维导图 SVG。

与旧版 build_spine 的区别：旧版是「第 X–Y 章 / 首章名→末章名」的目录切片，
本质是章节目录换了画法；这里只接受语义归纳结果（data/mindmap/<slug>.json），
节点是命题、议题、概念，连线体现中心→分支→叶子的层级与逻辑关系。

JSON 结构（由 LLM 归纳产出，见 tools/export_mindmap_material.py 的素材格式）：
{
  "title": "书名",
  "thesis": "全书一条命题，≤28字",
  "branches": [
    {"id":"A","label":"议题名，≤10字","rel":"因果|并列|递进|包含|对比",
     "points":["关键概念/判断，≤12字", ...2-3条],
     "note": "这条线在论证什么，≤34字（可选）"}
  ],
  "source": "llm"
}

布局：纵向三层树，宽度固定 364 → 手机 390 宽下 1:1 显示，字不用缩到 5px。
中心节点在上，左侧主干竖线串起各分支，分支内再挂关键词叶子。
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "mm-graph"

E = html.escape
W = 364
PAD = 14
BX = 46                       # 分支框左边界
BW = W - PAD - BX             # 分支框宽
CHIP_H = 22
COLORS = ("#8a9b6e", "#c58b5a", "#6f8fa8", "#a482a0", "#b0a06a", "#7d9a9b", "#b5837f")
RELS = {"因果", "并列", "递进", "包含", "对比"}


def _lines(text: str, per: int, max_lines: int = 2) -> list[str]:
    """按字数折行；超长截尾加省略号（SVG <text> 不会自动换行）"""
    s = (text or "").strip()
    if not s:
        return []
    out = [s[i:i + per] for i in range(0, len(s), per)]
    if len(out) > max_lines:
        out = out[:max_lines]
        out[-1] = out[-1][:-1] + "…"
    return out


def _chip_w(text: str) -> int:
    """叶子 chip 宽度：中文按 11px/字，ASCII 按 6px/字，两侧各留 8px"""
    w = sum(11 if ord(c) > 127 else 6 for c in text)
    return min(BW - 24, max(46, w + 16))


def load(slug: str) -> dict | None:
    p = DATA / (slug + ".json")
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    brs = [b for b in (d.get("branches") or []) if (b.get("label") or "").strip()]
    if not brs or not (d.get("thesis") or "").strip():
        return None
    d["branches"] = brs[:7]
    return d


def has_data(slug: str) -> bool:
    return load(slug) is not None


def render(slug: str, title: str) -> str:
    d = load(slug)
    if not d:
        return ""
    thesis = d["thesis"].strip()
    brs = d["branches"]

    # ── 先算每块高度，再定 viewBox ────────────────────────────────
    t_lines = _lines(title, 16, 2)
    th_lines = _lines(thesis, 19, 2)
    root_h = 20 + 20 * len(t_lines) + 8 + 15 * len(th_lines) + 12

    blocks = []
    for b in brs:
        lab = b["label"].strip()
        rel = (b.get("rel") or "").strip()
        rel = rel if rel in RELS else ""
        note_lines = _lines(b.get("note") or "", 24, 1)
        pts = [str(x).strip()[:12] for x in (b.get("points") or []) if str(x).strip()][:3]
        # chip 排版：按累计宽度折行
        rows, row, used = [], [], 0
        for t in pts:
            cw = _chip_w(t)
            if row and used + 6 + cw > BW - 20:
                rows.append((row, used))
                row, used = [], 0
            row.append((t, cw))
            used += (6 if len(row) > 1 else 0) + cw
        if row:
            rows.append((row, used))
        h = 30 + (14 * len(note_lines) if note_lines else 0) + 8 + len(rows) * (CHIP_H + 6) + 10
        blocks.append({"label": lab, "rel": rel, "note": note_lines,
                       "rows": rows, "h": h})

    H = PAD + root_h + 16 + sum(b["h"] + 12 for b in blocks) + 12
    parts = ['<svg class="mmx-svg mmx-mind" viewBox="0 0 %d %d"'
             ' xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMinYMin meet"'
             ' role="img" aria-label="%s 思维导图">' % (W, H, E(title))]
    parts.append('<style>'
                 '.mmx-mind text{font-family:"Noto Serif SC",Georgia,serif}'
                 '.mmx-mind .m-root{fill:#2f4a3d}'
                 '.mmx-mind .m-br{fill:#fbf7ee;stroke:#d8cdb4;stroke-width:1.2}'
                 '.mmx-mind .m-chip{fill:#f1eadb;stroke:#ded2b9;stroke-width:1}'
                 '.mmx-mind .m-ln{stroke:#cfc6b4;stroke-width:1.5;fill:none}'
                 '.mmx-mind .m-t{font-size:14px;font-weight:700;fill:#f7f3ea}'
                 '.mmx-mind .m-th{font-size:10.5px;fill:#cfdcd0}'
                 '.mmx-mind .m-lb{font-size:12.5px;font-weight:700;fill:#2f2a24}'
                 '.mmx-mind .m-rel{font-size:9.5px;fill:#8a8272}'
                 '.mmx-mind .m-note{font-size:10.5px;fill:#6c6353}'
                 '.mmx-mind .m-cp{font-size:10.5px;fill:#4a4337}'
                 '.mmx-mind .m-id{font-size:10px;font-weight:700;fill:#fff}'
                 '</style>')

    # ── 中心：书名 + 全书命题 ─────────────────────────────────────
    parts.append('<rect class="m-root" x="%d" y="%d" width="%d" height="%d" rx="12"/>'
                 % (PAD, PAD, W - 2 * PAD, root_h))
    ty = PAD + 22
    for ln in t_lines:
        parts.append('<text class="m-t" x="%d" y="%d">%s</text>' % (PAD + 14, ty, E(ln)))
        ty += 20
    ty += 6
    for k, ln in enumerate(th_lines):
        parts.append('<text class="m-th" x="%d" y="%d">%s</text>'
                     % (PAD + 14, ty + k * 15, E(("命题 · " if k == 0 else "　　") + ln)))
    root_bottom = PAD + root_h

    # ── 主干竖线 ─────────────────────────────────────────────────
    spine_x = 28
    y = root_bottom + 16
    last_mid = y + blocks[-1]["h"] / 2
    parts.append('<path class="m-ln" d="M%d %d L%d %d"/>'
                 % (spine_x, root_bottom, spine_x, last_mid))

    for i, b in enumerate(blocks):
        color = COLORS[i % len(COLORS)]
        h = b["h"]
        mid = y + h / 2
        # 主干 → 分支
        parts.append('<path class="m-ln" d="M%d %d L%d %d"/>'
                     % (spine_x, mid, BX - 6, mid))
        parts.append('<circle cx="%d" cy="%d" r="3.5" fill="%s"/>'
                     % (spine_x, mid, color))
        parts.append('<rect class="m-br" x="%d" y="%d" width="%d" height="%d" rx="9"/>'
                     % (BX, y, BW, h))
        parts.append('<rect x="%d" y="%d" width="5" height="%d" rx="2.5" fill="%s"/>'
                     % (BX, y, h, color))
        # 编号 + 议题
        parts.append('<circle cx="%d" cy="%d" r="9" fill="%s"/>'
                     % (BX + 20, y + 19, color))
        parts.append('<text class="m-id" x="%d" y="%d" text-anchor="middle">%s</text>'
                     % (BX + 20, y + 22.5, E(chr(65 + i))))
        parts.append('<text class="m-lb" x="%d" y="%d">%s</text>'
                     % (BX + 36, y + 23, E(b["label"])))
        if b["rel"]:
            parts.append('<text class="m-rel" x="%d" y="%d" text-anchor="end">【%s】</text>'
                         % (BX + BW - 10, y + 23, E(b["rel"])))
        cy = y + 30
        for ln in b["note"]:
            cy += 14
            parts.append('<text class="m-note" x="%d" y="%d">%s</text>'
                         % (BX + 14, cy, E(ln)))
        cy += 14
        for row, used in b["rows"]:
            cx = BX + 14
            for t, cw in row:
                # 分支 → 叶子的短竖线
                parts.append('<path class="m-ln" d="M%d %d L%d %d"/>'
                             % (cx + 8, cy - 4, cx + 8, cy + 2))
                parts.append('<rect class="m-chip" x="%d" y="%d" width="%d" height="%d" rx="7"/>'
                             % (cx, cy + 2, cw, CHIP_H))
                parts.append('<text class="m-cp" x="%d" y="%d" text-anchor="middle">%s</text>'
                             % (cx + cw / 2, cy + 2 + 15, E(t)))
                cx += cw + 6
            cy += CHIP_H + 6
        y += h + 12

    parts.append('</svg>')
    note = ('本图由 AI 通读全书内容后归纳：中心＝全书命题，'
            '分支＝论证议题，叶子＝关键概念/判断；不是章节目录切片。')
    return ('<section class="mmx-svgwrap" data-key="svg">'
            '<h2 id="mod-svg" class="sr-only">结构导图</h2>'
            '<p class="mmx-mod-note">%s</p>' % E(note)
            + "".join(parts) + '</section>')
