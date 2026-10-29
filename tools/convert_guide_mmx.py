#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""convert_guide_mmx.py — 通读页章节区收敛为 mmx- 组件（就地转换，幂等）。

背景（2026-10-28 用户定调）：通读页里章节内容出现三处 ——
  ①「全书结构与主题关系」（mm-group 章节串联块）
  ②「章节导读」（ch-item 折叠树，展开即 小节→要点→原句）
  ③ AI 大纲页（outline.html，同一数据的完整版）
满屏都是大纲感。合并为一处：② 保留并换用与「全书导图」页共享的 mmx- 组件
（assets/css/mmx-guide.css），① 删除（信息 ② 全覆盖，分部信息在 part-label 里），
③ 维持独立页面链接。

转换内容：
  1. <head> 引入 mmx-guide.css（幂等：已有即跳过）
  2. 删除「全书结构与主题关系」整个 section（配平 <section> 计数，防误删）
  3. 「章节导读」内 ch-item/ch-no/ch-t/ch-body/ch-stat/ch-sec/sec-h/sec-count/
     ch-secs/ch-quote/ch-empty/ch-more → mmx-cn/mmx-no/mmx-name/mmx-body/
     mmx-stat/mmx-sec/mmx-sech/mmx-secc/mmx-pts/mmx-qt/mmx-empty/mmx-more
     （badge「未读/亲读」是通读页自有徽标，保留不动）
  4. h2 后插入「展开全部要点 / 全部收起」工具行，页尾插一段内联 JS

用法：
    python tools/convert_guide_mmx.py            # 预览
    python tools/convert_guide_mmx.py --write    # 落盘
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOKS = ROOT / "reading-notes" / "books"

CSS_LINK = '<link rel="stylesheet" href="../../../assets/css/mmx-guide.css">'
GUIDE_OPEN = re.compile(r'<section[^>]*aria-labelledby="chapter-guide-title"[^>]*>')
STRUCT_H2 = "<section><h2>全书结构与主题关系</h2>"
TOOLS = ('<div class="mmx-tools">'
         '<button class="mmx-btn" data-mmx="open">展开全部要点</button>'
         '<button class="mmx-btn" data-mmx="close">全部收起</button>'
         '<span class="mmx-tip">章折叠态只占一行，点章名展开全部小节、要点与原句；'
         '更完整的分层见本书 AI 大纲页</span></div>')
JS = """<script>
(function(){
  var btns=document.querySelectorAll("[data-mmx]");
  for(var i=0;i<btns.length;i++){(function(b){
    b.addEventListener("click",function(){
      var open=b.getAttribute("data-mmx")==="open";
      document.querySelectorAll("details.mmx-cn").forEach(function(d){d.open=open;});
      document.querySelectorAll("details.mmx-sec").forEach(function(d){d.open=open;});
    });
  })(btns[i]);}
})();
</script>
"""

# 章节导读 section 内的类名替换（有序、全字匹配）
RENAME = [
    ('class="ch-item"', 'class="mmx-cn"'),
    ('class="ch-no"', 'class="mmx-no"'),
    ('class="ch-t"', 'class="mmx-name"'),
    ('class="caret"', 'class="mmx-caret"'),
    ('class="ch-body"', 'class="mmx-body"'),
    ('class="ch-stat"', 'class="mmx-stat"'),
    ('class="ch-sec"', 'class="mmx-sec"'),
    ('class="sec-h"', 'class="mmx-sech"'),
    ('class="sec-count"', 'class="mmx-secc"'),
    ('class="ch-secs"', 'class="mmx-pts"'),
    ('class="ch-quote"', 'class="mmx-qt"'),
    ('class="ch-empty"', 'class="mmx-empty"'),
    ('class="ch-more"', 'class="mmx-more"'),
]


def _section_span(s: str, start: int) -> tuple[int, int]:
    """从 start（应指向某个 <section）起做 <section>/</section> 配平，
    返回 (start, end)，end 指向闭合 </section> 之后。"""
    i, depth = start, 0
    while i < len(s):
        mo = re.compile(r"<section\b|</section>").search(s, i)
        if not mo:
            raise ValueError("section 未闭合")
        if mo.group(0) == "</section>":
            depth -= 1
            if depth == 0:
                return start, mo.end()
        else:
            depth += 1
        i = mo.end()
    raise ValueError("section 未闭合")


def convert(html: str, name: str) -> tuple[str, list[str]]:
    log = []
    if "mmx-guide.css" in html:
        return html, ["已转换过，跳过"]

    # 0) 先确认有「章节导读」再动刀。结构块的信息靠章节导读全覆盖，
    #    没有章节导读就删结构块 = 净丢内容（long-cang / 马克·吐温短篇属此类）。
    if not GUIDE_OPEN.search(html):
        return html, ["无章节导读，整体跳过（未改动）"]

    # 1) 删「全书结构与主题关系」
    p = html.find(STRUCT_H2)
    if p >= 0:
        a, b = _section_span(html, p)
        inner = html[a:b]
        log.append("删结构块 %d 字节（含 %d 个 mm-group）"
                   % (b - a, inner.count('class="mm-group')))
        html = html[:a] + html[b:]
    else:
        log.append("无结构块")

    # 2) 章节导读：类名替换 + 工具行
    m = GUIDE_OPEN.search(html)
    if not m:
        return html, log + ["无章节导读，中止"]
    a, b = _section_span(html, m.start())
    block = html[a:b]
    n = 0
    for old, new in RENAME:
        n += block.count(old)
        block = block.replace(old, new)
    log.append("章节导读类名替换 %d 处" % n)
    block = re.sub(r'(<h2 id="chapter-guide-title">[^<]*</h2>\n?)',
                   r"\1" + TOOLS + "\n", block, count=1)
    html = html[:a] + block + html[b:]

    # 3) head 引入共享组件样式 + 页尾 JS
    html = html.replace(
        '<link rel="stylesheet" href="../../../assets/css/reading-overview.css">',
        '<link rel="stylesheet" href="../../../assets/css/reading-overview.css">\n'
        + CSS_LINK, 1)
    if "</main>" in html:
        html = html.replace("</main>", JS + "</main>", 1)
    return html, log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--slug")
    a = ap.parse_args()
    pool = ([BOOKS / a.slug / "overview.html"] if a.slug else
            sorted(BOOKS.glob("*/overview.html")))
    done = skip = 0
    for ov in pool:
        if not ov.exists():
            continue
        s = ov.read_text(encoding="utf-8")
        out, log = convert(s, ov.parent.name)
        if log == ["已转换过，跳过"]:
            skip += 1
            continue
        done += 1
        print("%-46s %s" % (ov.parent.name[:46], "；".join(log)))
        if a.write:
            ov.write_text(out, encoding="utf-8", newline="\n")
    print("转换 %d，跳过 %d%s" % (done, skip, "（预览，未落盘）" if not a.write else ""))


if __name__ == "__main__":
    main()
