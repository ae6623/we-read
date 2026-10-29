#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 deep-read（精读深读）页的逐章追问 + 核心追问合并进精读页。

背景：第 3 批「deep-read 并入精读」被批量发布用旧快照覆盖，线上 0 页有
`details.mmx-ask`，而 58 个 deep-read 页仍是全文。本工具直接从这些页抽取，
按章节回灌到 `books/<slug>/mindmap.html` 的对应章条目里，并把跨书的
「核心追问」写进 `data/mindmap/<slug>.json` 的 `modules.coreask`。

匹配策略（三级，宁缺勿错）：
  1) 章数相同 → 按顺序一一对应（两页同源于同一份 outline，顺序一致）；
  2) 章数不同 → 名字归一化后精确匹配（去《》、标点、「第X章/节/卷」前缀、「1 ·」前缀）；
  3) 仍有剩余 → 在已匹配锚点切出的空档内，若两侧章数相同则按顺序补位；
  4) 还匹配不上的，丢弃并报告，不硬塞（塞错章比缺一条更糟）。

幂等：注入前先删掉该章里已有的 `details.mmx-ask`，再插入。

用法：
  python tools/merge_deep_ask.py              # 试运行，报匹配率与未匹配清单
  python tools/merge_deep_ask.py --write      # 落盘（含核心追问写 JSON + 重渲染模块区）
  python tools/merge_deep_ask.py --slug 1984  # 只处理一本
"""
from __future__ import annotations

import argparse
import html as _html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

BOOKS = HERE / "reading-notes" / "books"
DB_OUT = HERE / "data" / "mindmap"

ASK_OPEN = '<details class="mmx-ask"'
NO_PREFIX = re.compile(
    r"^(第[一二三四五六七八九十百零〇两0-9]+[章节卷册篇部回集]"
    r"|[0-9]{1,3}\s*[·.、\-—]\s*"
    r"|[·•]\s*)"
)
PUNCT = re.compile(r"[\s《》〈〉“”\"'·、，。！？：；（）()\[\]【】\-—…~～]+")


def norm(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s or "")
    s = _html.unescape(s)
    s = PUNCT.sub("", s)
    return s.strip()


def clean_ans(s: str) -> str:
    """深读页的答案里混着段落标签、偶发被截断的 <section> 残片，统一转成纯文本段落。"""
    s = re.sub(r"</p>\s*<p[^>]*>", "\n\n", s or "")
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = _html.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def core(s: str) -> str:
    """再剥一层章号前缀，用于「第一章 xxx」对「xxx」、以及「1 · xxx」对「xxx」的匹配。"""
    s = _html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()
    prev = None
    while prev != s:
        prev = s
        s = NO_PREFIX.sub("", s)          # 先在有分隔符的原文上剥
        s = PUNCT.sub("", s)              # 再去标点
        if re.match(r"^\d{1,3}[^\d]", s):  # 兜底：纯数字开头 + 还有内容
            s = re.sub(r"^\d{1,3}", "", s)
    return s.strip()


# ---------------------------------------------------------------- 解析
def parse_deep(text: str):
    """按 `<details class="ch-item">` 起点切块：有的页 ch-item 没闭合（巴布亚那页就是），
    不能依赖 `</details>`，改用「下一个 ch-item 或核心追问区」作为边界。"""
    starts = [m.start() for m in re.finditer(r'<details class="ch-item">', text)]
    if not starts:
        return []
    cut = len(text)
    for anchor in ('id="thematic"', 'id="best"'):
        i = text.find(anchor)
        if i > 0:
            cut = min(cut, i)
    bounds = starts + [cut]
    out = []
    for i in range(len(starts)):
        blk = text[bounds[i]:bounds[i + 1]]
        nm = re.search(r'<span class="ch-t">(.*?)</span>', blk)
        if not nm:
            continue
        qa = []
        for q in re.finditer(r'<div class="aiqa-item">(.*?)</div>', blk, re.S):
            body = q.group(1)
            qm = re.search(r"<h3[^>]*>(.*?)</h3>", body, re.S)
            if not qm:
                continue
            ans = clean_ans(re.sub(r"^.*?</h3>", "", body, flags=re.S))
            qa.append({"q": clean_ans(qm.group(1)), "a": ans})
        out.append({"name": nm.group(1).strip(), "qa": qa})
    return out


def parse_core(text: str):
    """跨书「核心追问」：thematic 区块内、不在 ch-item 里的 aiqa-item。"""
    i = text.find('id="thematic"')
    if i < 0:
        return []
    j = text.find("</section>", i)
    seg = text[i:j]
    out = []
    for q in re.finditer(r'<div class="aiqa-item">(.*?)</div>', seg, re.S):
        body = q.group(1)
        qm = re.search(r"<h3[^>]*>(.*?)</h3>", body, re.S)
        if not qm:
            continue
        ans = clean_ans(re.sub(r"^.*?</h3>", "", body, flags=re.S))
        out.append({"q": clean_ans(qm.group(1)), "a": ans})
    return out


def div_end(text: str, start: int) -> int:
    """从 `<div` 起始位置找配对的 `</div>` 结束位置（返回 `</div>` 之后的下标）。"""
    depth = 0
    for m in re.finditer(r"<div\b|</div>", text[start:]):
        if m.group(0) == "</div>":
            depth -= 1
            if depth == 0:
                return start + m.end()
        else:
            depth += 1
    return -1


def parse_mm(text: str):
    """返回精读页的章条目：name / 小节名 / body 起止（用于注入与匹配）。"""
    out = []
    for m in re.finditer(r'<details class="mmx-cn">', text):
        s = m.start()
        nm = re.search(r'<span class="mmx-name">(.*?)</span>', text[s:s + 900], re.S)
        b = text.find('<div class="mmx-body">', s)
        if not nm or b < 0:
            continue
        e = div_end(text, b)
        if e < 0:
            continue
        sechs = re.findall(r'<span class="mmx-sech">(.*?)</span>', text[b:e], re.S)
        out.append({"name": nm.group(1).strip(), "sechs": sechs,
                    "body_start": b, "body_end": e})
    return out


# ---------------------------------------------------------------- 匹配
def match(ds, ms):
    """返回 [(deep_idx, mm_idx)]，宁缺勿错。"""
    pairs = []
    used_m = set()
    if len(ds) == len(ms):
        return [(i, i) for i in range(len(ds))]

    # 2) 名字精确（归一化 + 去章号）
    for keyfn in (norm, core):
        idx_m = {}
        for j, mc in enumerate(ms):
            idx_m.setdefault(keyfn(mc["name"]), j)
        for i, d in enumerate(ds):
            if any(p[0] == i for p in pairs):
                continue
            j = idx_m.get(keyfn(d["name"]))
            if j is not None and j not in used_m:
                pairs.append((i, j))
                used_m.add(j)

    pairs.sort()
    # 2.5) 章名对不上时，用「该章第一个小节名」试一次（书名常见：章名只有编号，标题在小节里）
    key_sech = {}
    for j, mc in enumerate(ms):
        for sh in mc["sechs"][:3]:
            key_sech.setdefault(core(sh), j)
    for i, d in enumerate(ds):
        if any(p[0] == i for p in pairs):
            continue
        j = key_sech.get(core(d["name"]))
        if j is not None and j not in used_m:
            pairs.append((i, j))
            used_m.add(j)
    pairs.sort()

    # 3) 空档内按顺序补位
    anchors = [(-1, -1)] + pairs + [(len(ds), len(ms))]
    extra = []
    for (di0, mi0), (di1, mi1) in zip(anchors, anchors[1:]):
        dseg = list(range(di0 + 1, di1))
        mseg = [j for j in range(mi0 + 1, mi1) if j not in used_m]
        if dseg and len(dseg) == len(mseg):
            # 只在名字能对上「首字/包含」时才敢按序补，否则跳过
            ok = 0
            for a, b in zip(dseg, mseg):
                ca, cb = core(ds[a]["name"]), core(ms[b]["name"])
                if ca and cb and (ca in cb or cb in ca or ca[:4] == cb[:4]):
                    ok += 1
            if ok >= max(1, len(dseg) * 0.5):
                extra.extend(zip(dseg, mseg))
    pairs = sorted(pairs + extra)

    # 4) 兜底：归一化后高度相似（≥0.9）才算，避免把 A 章的追问塞进 B 章
    import difflib
    for i, d in enumerate(ds):
        if any(p[0] == i for p in pairs):
            continue
        best, best_r = None, 0.0
        ca = core(d["name"])
        for j, mc in enumerate(ms):
            if j in used_m:
                continue
            r = difflib.SequenceMatcher(None, ca, core(mc["name"])).ratio()
            if r > best_r:
                best, best_r = j, r
        if best is not None and best_r >= 0.9:
            pairs.append((i, best))
            used_m.add(best)
    pairs.sort()
    return pairs


# ---------------------------------------------------------------- 渲染
def ask_html(qa) -> str:
    if not qa:
        return ""
    # 单条且问题就是「《X》这一章围绕什么展开？」→ 折叠标题已表达，正文不再重复问句
    bodyless_q = (len(qa) == 1 and re.search(r"这一章围绕什么展开", qa[0]["q"] or ""))
    if bodyless_q:
        body = qa[0]["a"]
        label = "这一章围绕什么展开？"
    else:
        body = "".join('<p class="mmx-askq">%s</p>%s' % (x["q"], x["a"]) for x in qa)
        label = "这一章围绕什么展开？" if len(qa) == 1 else "这一章围绕什么展开？（%d 问）" % len(qa)
    return ('<details class="mmx-ask"><summary><span>%s</span>'
            '<span class="mmx-caret">\u203a</span></summary>'
            '<div class="mmx-askbody">%s</div></details>' % (label, body))


def strip_ask(seg: str) -> str:
    """删掉已有的 mmx-ask 块，保证幂等。"""
    out = seg
    while True:
        i = out.find(ASK_OPEN)
        if i < 0:
            return out
        e = out.find("</details>", i)
        if e < 0:
            return out
        out = out[:i] + out[e + len("</details>"):]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--slug", action="append", default=[])
    ap.add_argument("--source-git", action="store_true",
                    help="深读页已被改成迁移页时，从 git HEAD 读原文重新抽取（幂等重灌）")
    args = ap.parse_args()

    slugs = sorted({p.parent.parent.name for p in BOOKS.glob("*/notes/deep-read.html")})
    if args.slug:
        slugs = [s for s in slugs if s in set(args.slug)]

    stat = {"books": 0, "chapter_qa": 0, "mm_books": 0, "core": 0,
            "deep_ch": 0, "matched": 0, "pages": 0}
    misses = []
    core_todo = {}

    for slug in slugs:
        dp = BOOKS / slug / "notes" / "deep-read.html"
        mp = BOOKS / slug / "mindmap.html"
        if args.source_git:
            import subprocess
            rel = "reading-notes/books/%s/notes/deep-read.html" % slug
            r = subprocess.run(["git", "show", "HEAD:%s" % rel],
                               capture_output=True, text=True, encoding="utf-8")
            dtext = r.stdout if r.returncode == 0 else ""
        else:
            dtext = dp.read_text(encoding="utf-8", errors="ignore")
        ds = parse_deep(dtext)
        coreq = parse_core(dtext)
        stat["books"] += 1
        stat["deep_ch"] += len(ds)
        stat["chapter_qa"] += sum(len(d["qa"]) for d in ds)
        stat["core"] += len(coreq)
        if not mp.exists():
            misses.append((slug, "无精读页", len(ds)))
            continue
        stat["mm_books"] += 1
        mtext = mp.read_text(encoding="utf-8")
        # 先把整页里已有的逐章追问全清掉（有的旧注入落在章容器外，按章 strip 抓不到），
        # 再重新解析章位置——保证重复跑结果一致，不会残留第 25 条这种孤儿。
        if ASK_OPEN in mtext:
            mtext = re.sub(r'<details class="mmx-ask">.*?</details>', "", mtext, flags=re.S)
        ms = parse_mm(mtext)
        pairs = match(ds, ms)
        stat["matched"] += len(pairs)
        if len(pairs) < len(ds):
            misses.append((slug, "未匹配 %d 章" % (len(ds) - len(pairs)), len(ds)))

        # 注入（从后往前，避免下标位移）
        ins = []
        for di, mi in pairs:
            qa = ds[di]["qa"]
            if not qa:
                continue
            seg = mtext[ms[mi]["body_start"]:ms[mi]["body_end"]]
            if not seg.endswith("</div>"):
                continue
            inner = strip_ask(seg[: -len("</div>")])
            ins.append((ms[mi]["body_start"], ms[mi]["body_end"], inner, ask_html(qa)))
        if not ins:
            continue
        new = mtext
        for bs, be, inner, add in sorted(ins, key=lambda x: -x[0]):
            new = new[:bs] + inner + add + "</div>" + new[be:]
        if args.write and new != mtext:
            mp.write_text(new, encoding="utf-8", newline="\n")
            stat["pages"] += 1

        if coreq and args.write:
            core_todo[slug] = coreq

    if args.write and core_todo:
        for slug, qa in core_todo.items():
            jp = DB_OUT / ("%s.json" % slug)
            if not jp.exists():
                continue
            d = json.loads(jp.read_text(encoding="utf-8"))
            mods = d.setdefault("modules", {})
            mods["coreask"] = {"pairs": qa}
            jp.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n",
                          encoding="utf-8", newline="\n")

    print("深读页 %d 本 / 章块 %d / 逐章追问 %d 条 / 核心追问 %d 条"
          % (stat["books"], stat["deep_ch"], stat["chapter_qa"], stat["core"]))
    print("有精读页 %d 本 / 章级匹配 %d / %d  (%.1f%%)"
          % (stat["mm_books"], stat["matched"], stat["deep_ch"],
             100.0 * stat["matched"] / max(1, stat["deep_ch"])))
    if args.write:
        print("写入页面 %d 张 / 核心追问落 JSON %d 本" % (stat["pages"], len(core_todo)))
    if misses:
        print("未完全匹配：")
        for s, why, n in misses:
            print("  %-48s %s（深读章 %d）" % (s[:46], why, n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
