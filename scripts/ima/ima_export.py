#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把整站书卡（reading-notes/books/<slug>/combined-data.html）导出为结构化 Markdown，
供 IMA 知识库「we-read」入库，支持增量。

用法：
  python3 scripts/ima/ima_export.py --dry-run              # 只统计，不写盘
  python3 scripts/ima/ima_export.py --limit 20             # 只导前 20 本（按首页顺序）
  python3 scripts/ima/ima_export.py --only-cat 经济理财     # 只导某类目
  python3 scripts/ima/ima_export.py --local-only           # 只用本地已检出目录（离线）
  python3 scripts/ima/ima_export.py --force                # 忽略 hash，全部重写

产物：
  ima/cards/<类目>·<书名>.md    每本一个文件（≤ ~10KB，去掉样式的纯结构化文本）
  ima/manifest.json             增量台账：slug / hash / cat / status / ima_media_id / synced_at
  ima/pending.json              本次需要上传的清单（脚本不直连 IMA，由 Agent 按此上传）
  ima/00-总索引.md               全站书单总索引（按类目分组）
  ima/00-字段说明.md             给 IMA 检索用的结构说明

增量逻辑：
  hash 由「模板版本 + 各模块文本 sha1」决定。hash 未变 → skip；新书 / 内容变更 → pending。
  上传成功后把 media_id、synced_at、hash 写回 manifest（Agent 用 --mark 回写）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
BOOKS = ROOT / "reading-notes" / "books"
IMA_DIR = ROOT / "ima"
CARDS = IMA_DIR / "cards"
MANIFEST = IMA_DIR / "manifest.json"
PENDING = IMA_DIR / "pending.json"
SITE = "https://reader.js-dev.cn"
TEMPLATE_VER = "imacard-v6"          # 卡片渲染规则变更时 +1，触发全量重写
MAX_SECTION = 2600                   # 单模块正文上限（字符）
MAX_TOC = 80                         # 章节目录最多列多少章
MAX_SEC = 4                          # 每章最多展开多少小节
MAX_PTS = 3                          # 每小节最多列多少条要点

MOD_TITLES = [
    ("oneline", "一句话主旨"),
    ("views", "核心观点与结构脉络"),
    ("deepread", "精读判断"),
    ("top10", "原文金句"),
    ("coreask", "核心追问"),
    ("aiask", "AI 问书"),
    ("higher", "更高维度"),
    ("verify", "阅读时要验证"),
    ("thennow", "当年与今天"),
]

_BAD = re.compile(r'[\\/:*?"<>|\r\n\t]+')


def clean_name(s: str, limit: int = 90) -> str:
    s = unicodedata.normalize("NFKC", str(s or "")).strip()
    s = _BAD.sub("·", s)
    s = re.sub(r"·{2,}", "·", s).strip(" ·.")
    return s[:limit] or "未命名"


def norm(s: str) -> str:
    return re.sub(r"[\s\u3000《》「」·,，.。:：（）()\[\]【】\-—_]+", "", str(s or "")).lower()


# ---------------------------------------------------------------- 数据源

def load_index_cards() -> list[dict]:
    """从 index.html 解析书卡：slug / title / href / desc / date。"""
    h = (ROOT / "index.html").read_text("utf-8", errors="ignore")
    out, seen = [], set()
    for m in re.finditer(r'<article[^>]*data-slug="([^"]+)"[^>]*>(.*?)</article>', h, re.S):
        slug, body = m.group(1), m.group(2)
        if slug in seen:
            continue
        t = re.search(r'class="card-title-link"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', body, re.S)
        if not t:
            continue
        seen.add(slug)
        title = re.sub(r"<[^>]+>", "", t.group(2)).strip().strip("《》")
        d = re.search(r"<p>(.*?)</p>", body, re.S)
        out.append({
            "slug": slug,
            "title": title or slug,
            "href": t.group(1),
            "desc": re.sub(r"<[^>]+>", "", d.group(1)).strip() if d else "",
            "date": (re.search(r'datetime="([^"]+)"', body) or [None, ""])[1],
        })
    return out


def load_json(rel: str, default):
    p = ROOT / rel
    try:
        return json.loads(p.read_text("utf-8"))
    except Exception:
        return default


_SESS = None
_SESS_LOCK = __import__("threading").Lock()


def _session():
    global _SESS
    import requests
    from requests.adapters import HTTPAdapter
    with _SESS_LOCK:
        if _SESS is None:
            s = requests.Session()
            ad = HTTPAdapter(pool_connections=4, pool_maxsize=16, max_retries=1)
            s.mount("https://", ad)
            s.headers.update({"User-Agent": "wr-ima-export/1", "Accept-Encoding": "gzip, deflate"})
            _SESS = s
        return _SESS


def fetch_remote(slug: str) -> str | None:
    url = f"{SITE}/reading-notes/books/{quote(slug)}/combined-data.html"
    try:
        r = _session().get(url, timeout=20)
        if r.status_code == 200 and len(r.content) > 2000:
            # 必须显式按 UTF-8 解码：CDN 不带 charset，requests 会猜成 ISO-8859-1 → 全是乱码
            return r.content.decode("utf-8", "ignore")
        return None
    except Exception:
        return None


# ---------------------------------------------------------------- HTML → 模块文本

def sections(html: str) -> dict[str, str]:
    """按 data-key 切 section，直接渲染成 Markdown（保留层级，不再压成一段）。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    out = {}
    for sec in soup.find_all("section"):
        k = sec.get("data-key")
        if not k:
            continue
        if k == "merged_guide":          # 章节树单独走 guide_tree
            continue
        for bad in sec.find_all(["style", "script"]):
            bad.decompose()
        if k == "oneline":
            # 一句话主旨是标题下的「> 摘要」，不是正文模块，保持纯文本；
            # 若也套两层列表，render() 取首行只会拿到「要点 1」，主旨会丢。
            md = as_markdown(strip_meta(sec.get_text("\n", strip=True)))
        else:
            md = render_section(sec)
            if not md:                   # 结构识别失败的老卡片，退回扁平文本
                md = as_markdown(strip_meta(sec.get_text("\n", strip=True)))
        if md:
            out[k] = md
    return out


def _li_rest(li, b) -> str:
    """li 里去掉粗体标签后的余下文本（保留「——」这类破折号）。"""
    from bs4 import BeautifulSoup
    s = BeautifulSoup(str(li), "html.parser")
    bb = s.find("b")
    if bb:
        bb.extract()
    return s.get_text(" ", strip=True)


def _blocks(el) -> list[tuple]:
    """把模块拆成块序列：('quote',原句,出处) / ('qa',问,答) / ('li_b',粗体,余文) / ('li',文本,'') / ('p',文本,'')。"""
    out = []
    for c in el.find_all(recursive=False):
        name, cls = c.name, " ".join(c.get("class") or [])
        if name in ("style", "script", "h1", "h2", "h3", "summary"):
            continue
        if name == "p" and ("mmx-mod-note" in cls or cls in ("small", "note")):
            continue
        if name in ("ul", "ol"):
            for li in c.find_all("li", recursive=False):
                bq = li.find("blockquote")
                if bq:
                    cite = li.find("cite")
                    out.append(("quote", bq.get_text(" ", strip=True),
                                cite.get_text(" ", strip=True) if cite else ""))
                    continue
                b = li.find("b")
                if b:
                    out.append(("li_b", b.get_text(" ", strip=True), _li_rest(li, b)))
                else:
                    out.append(("li", li.get_text(" ", strip=True), ""))
            continue
        if name == "div":
            if "mmx-qa" in cls:
                q, a = c.select_one(".mmx-q"), c.select_one(".mmx-a")
                if q:
                    out.append(("qa", q.get_text(" ", strip=True),
                                a.get_text(" ", strip=True) if a else ""))
                    continue
            out += _blocks(c)            # 包了一层的容器，递归展开
            continue
        t = c.get_text(" ", strip=True)
        if t:
            out.append(("p", t, ""))
    return out


_MARK = re.compile(r"【([^】]{2,12})】")
_SOFT = re.compile(r"\s+(?=(?:存疑|取舍|商榷|反驳|补充|延伸)\s*·\s)")


def _explode(t: str) -> list[tuple[str, str]]:
    """把一段长文按内嵌标记拆成 [(标签, 正文)]。

    站点里「更高维度」常用【书中主张】【外部证据】【综合分析】写三段式论证，
    「深读」用「存疑 ·」「取舍 ·」写判断，全塞在一个 <p> 里手机上就是一堵墙。
    有 ≥2 个标记才拆，正常段落原样返回。
    """
    marks = list(_MARK.finditer(t))
    if len(marks) >= 2:
        out = []
        pre = t[:marks[0].start()].strip()
        if pre:
            out.append(("", pre))
        for i, m in enumerate(marks):
            end = marks[i + 1].start() if i + 1 < len(marks) else len(t)
            body = t[m.end():end].strip()
            if body:
                out.append((m.group(1).strip(), body))
        return out or [("", t.strip())]
    segs = [s.strip() for s in _SOFT.split(t) if s.strip()]
    if len(segs) >= 2:
        return [("", s) for s in segs]
    return [("", t.strip())]


_SENT_END = re.compile(r"(?<=[。！？；;!?])")
_HEAD_LABEL = re.compile(r"^([^：:。！？；，]{2,18})[：:]\s*(.+)$", re.S)
_SOFT_LABEL = re.compile(r"^([\u4e00-\u9fa5]{2,6})\s*·\s*(.+)$", re.S)


def _emit(lines: list[str], parent: str, children: list[str]) -> None:
    """所有模块唯一的出口：一个加粗父节点 + 至少一条缩进子节点。

    用户要求「所有模块都应该是统一的样式」——02–09 节一律两层列表，
    与最后一节「章节目录」的缩进读法一致。不再允许裸段落、
    「- **主题**：说明」这种压成单行的写法，或没有子节点的平铺列表。
    """
    parent = re.sub(r"\s+", " ", (parent or "").strip())
    children = [re.sub(r"\s+", " ", str(c).strip()) for c in children if str(c).strip()]
    if not children:
        # 极少见（如回答为空的问答）：把内容降级成子节点，父节点退化为「要点」
        children = [parent] if parent else []
        parent = "要点"
    if not parent and not children:
        return
    lines.append(f"- **{parent or '要点'}**")
    for c in children:
        lines.append(f"  - {c}")


def _split_sentences(t: str) -> list[str]:
    """纯论述段按句拆成多条子节点；过短碎片并入前一条，避免出现半截话。"""
    segs = [s.strip() for s in _SENT_END.split(t) if s.strip()]
    out: list[str] = []
    for s in segs:
        if out and len(s) < 14:
            out[-1] += s
        else:
            out.append(s)
    return out or [t.strip()]


def _label_of(body: str) -> tuple[str, str]:
    """从一段文字里认出「小标题：正文」或「存疑 · 正文」，返回 (标签, 正文)。

    认不出就返回空标签，由调用方决定用序号父节点。
    """
    m = _HEAD_LABEL.match(body)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    m = _SOFT_LABEL.match(body)
    if m and m.group(1) in ("存疑", "取舍", "商榷", "反驳", "补充", "延伸", "一句话判断", "判断"):
        return m.group(1), m.group(2).strip()
    return "", body.strip()


def render_section(sec) -> str:
    """所有正文模块 → 统一的「加粗父节点 + 缩进子节点」两层列表（v6）。

    各 DOM 块如何映射到父子（结构完全一致，只有父节点名称来源不同）：

    | 块 | 父节点 | 子节点 |
    |---|---|---|
    | quote | 出处章名（连续同出处合并） | 逐条原句 |
    | qa | 问句 | 回答（按【标记】/存疑· 再拆多条） |
    | li_b | 粗体主题 | 余文按句拆 |
    | li | 要点 N | 原文按句拆 |
    | p（含【标记】/小标题） | 标记/小标题 | 正文按句拆 |
    | p（纯论述） | 首句或要点 N | 余句 |
    """
    lines: list[str] = []
    pending: tuple[str, list[str]] | None = None
    n_plain = 0

    def flush_quote():
        nonlocal pending
        if pending:
            _emit(lines, pending[0] or "原文金句", pending[1])
            pending = None

    def seq() -> str:
        nonlocal n_plain
        n_plain += 1
        return f"要点 {n_plain}"

    def plain(text: str) -> None:
        """无语义标签的块：尽量用「标签：正文」当父子，否则用序号父节点。"""
        lab, body = _label_of(text)
        if lab:
            _emit(lines, lab, _split_sentences(body))
        else:
            _emit(lines, seq(), _split_sentences(text))

    for kind, a, b in _blocks(sec):
        a = (a or "").strip()
        if not a or _is_meta(a):
            continue
        if kind != "quote":
            flush_quote()

        if kind == "quote":
            cite = (b or "").strip()
            if pending and pending[0] == cite:
                pending[1].append(a)
            else:
                flush_quote()
                pending = (cite, [a])
        elif kind == "qa":
            parts = _explode(b)
            kids = [(f"**{lab}** · " if lab else "") + body for lab, body in parts]
            kids = [k for k in kids if k.strip()]
            _emit(lines, a, kids)
        elif kind == "li_b":
            rest = re.sub(r"^[—－–\-:：\s]+", "", (b or "").strip())
            _emit(lines, a, _split_sentences(rest) if rest else [])
        elif kind == "li":
            plain(a)
        else:
            parts = _explode(a)
            if len(parts) > 1:
                for lab, body in parts:
                    if lab:
                        _emit(lines, lab, _split_sentences(body))
                    else:
                        plain(body)
                continue
            plain(a)
    flush_quote()
    return "\n".join(lines).strip()



def guide_tree(html: str) -> list[dict]:
    """把 AI领读的章节树完整读出来：章 → 小节(sec h4) → 要点(ul.point li b) → 原句。

    旧版只取「编号 + 章名 + 规模统计」，书卡里每章只有一行「共 N 个小节 ·
    M 条要点」，点进去是空的 —— 用户反馈「章节目录缺子节点」。现在把
    AI 大纲已有的三层结构原样搬进来，不再丢层级。
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    mg = soup.find("section", attrs={"data-key": "merged_guide"})
    if not mg:
        return []
    out = []
    for d in mg.select("details.mmx-cn"):
        s = d.find("summary")
        if not s:
            continue
        no_el, nm_el = s.select_one(".mmx-no"), s.select_one(".mmx-name")
        no = no_el.get_text(strip=True) if no_el else ""
        nm = nm_el.get_text(" ", strip=True) if nm_el else ""
        if not nm:
            nm = s.get_text(" ", strip=True).replace("›", "").strip()
        st = d.select_one(".mmx-stat")
        secs = []
        for sec in d.select("div.sec"):
            h4 = sec.find("h4")
            h = h4.get_text(" ", strip=True) if h4 else ""
            pts, q = [], ""
            for li in sec.select("ul.point > li"):
                b = li.find("b")
                t = (b.get_text(" ", strip=True) if b else li.get_text(" ", strip=True)).strip()
                if t:
                    pts.append(t)
            qn = sec.select_one("ul.quote.quote-node > li")
            if qn:
                q = qn.get_text(" ", strip=True)
            elif sec.select_one("ul.quote > li"):
                q = sec.select_one("ul.quote > li").get_text(" ", strip=True)
            if h or pts:
                secs.append({"h": h, "points": pts[:MAX_PTS], "quote": q})
        out.append({"no": no, "name": nm,
                    "stat": st.get_text(" ", strip=True) if st else "",
                    "secs": secs[:MAX_SEC]})
        if len(out) >= MAX_TOC:
            break
    return out


def toc_from_guide(html: str) -> list[str]:
    """扁平版（只给「一句话主旨」兜底用）。"""
    items = []
    for t in guide_tree(html):
        line = f"- {t['no']} {t['name']}".strip()
        items.append(line + (f"　（{t['stat']}）" if t["stat"] else ""))
    return items


def clip(text: str, limit: int = MAX_SECTION) -> str:
    text = re.sub(r"\n{3,}", "\n\n", (text or "").strip())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    pos = max(cut.rfind("。"), cut.rfind("\n"))
    if pos > limit * 0.6:
        cut = cut[: pos + 1]
    return cut.rstrip() + "\n\n…（原文更长，完整内容见站点）"


def clip_list(text: str, limit: int = MAX_SECTION) -> str:
    """正文模块专用裁剪：截断必须落在完整的子节点行上，避免父节点悬空。

    提示行用 `> ` 引用格式，不产生裸段落 —— 所有模块保持「父子两层」统一样式，
    超长模块也一样。只给 02–09 节用；一句话主旨是纯文本，仍走 clip()。
    """
    text = re.sub(r"\n{3,}", "\n\n", (text or "").strip())
    if len(text) <= limit:
        return text
    lines = text[:limit].split("\n")
    while lines and not lines[-1].startswith("  - "):
        lines.pop()
    if not lines:  # 极端情况：limit 内一个完整子节点都没有
        return text[:limit].rstrip() + "\n\n> …（原文更长，完整内容见站点）"
    return "\n".join(lines).rstrip() + "\n\n> …（原文更长，完整内容见站点）"


_META_HEAD = re.compile(r"^(本页|下方|以下|按全书|按章节|按主干|跨章|逐章|取自|（来自|\(来自|全书篇目|共\s*\d+\s*章|本书共)")
_META_HINT = ("由模型", "由云端", "由 AI", "AI 阅读流程", "非读后感", "结构化重算",
              "结构重算", "占位", "摘自", "替代原先", "逐字取自", "未做人工解读", "按章序折成")


def _is_meta(t: str) -> bool:
    """块级判断：这行是「模块自带的说明文字」而不是正文。"""
    s = (t or "").strip()
    if not s or s.startswith(("-", "#", "**", "|", ">")):
        return False
    if len(s) <= 140 and (bool(_META_HEAD.match(s)) or any(h in s for h in _META_HINT)):
        return True
    # 「本页基于…模块二次整理」这类免责/来源说明常常很长，单独再放一次
    return len(s) <= 520 and bool(_META_HEAD.match(s))


def strip_meta(text: str) -> str:
    """去掉每个模块自带的说明性文字（每张卡都重复，检索时是噪声）。"""
    out = []
    for ln in (text or "").split("\n"):
        s = ln.strip()
        if not s:
            continue
        meta = len(s) <= 140 and (
            bool(_META_HEAD.match(s)) or any(h in s for h in _META_HINT)
        )
        if meta:
            continue
        out.append(s)
    return "\n".join(out)


def as_markdown(text: str) -> str:
    """短行（≤14 字、无句末标点）当小标题，其余按段落；列表行原样保留。"""
    lines = [l for l in (text or "").split("\n") if l.strip()]
    out, buf = [], []

    def flush():
        if buf:
            out.append(" ".join(buf).strip())
            buf.clear()

    for l in lines:
        s = l.strip()
        if re.match(r"^[-*·•]\s", s) or re.match(r"^\d+[.、]\s", s):
            flush()
            out.append(s)
        elif len(s) <= 14 and not re.search(r"[。！？；，、：:]$", s) and not s.endswith("。"):
            flush()
            out.append("### " + s)
        else:
            buf.append(s)
    flush()
    return "\n\n".join(out)


# ---------------------------------------------------------------- 渲染

def _mm(s, limit=26):
    """Mermaid mindmap 节点清洗：方/圆/花括号会被当语法，必须去掉。"""
    t = re.sub(r"[\[\]{}()（）<>\"'`#;|]", "", str(s or "")).strip()
    t = re.sub(r"\s+", " ", t)
    return t[:limit]


def _mindmap(title: str, tree: list[dict]) -> list[str]:
    """篇→章 两级 Mermaid mindmap，Google 配色。

    上一版踩的坑：只设 primaryColor 时，mindmap 仍会按分支索引从默认
    cScale 调色板取色 → 56 个分支五颜六色像蜘蛛网。现在把 cScale0-11
    全部压成「浅蓝/浅绿」两色交替，根节点用 Google 蓝深底白字；
    章数超过 12 时只画前 12 章（放射状布局放不下更多），其余在章节目录里。
    """
    blue, blue_t, green, ink = "#E8F0FE", "#D2E3FC", "#E6F4EA", "#174EA6"
    tv = [
        f"'primaryColor':'{blue}'", f"'primaryTextColor':'{ink}'",
        "'primaryBorderColor':'#4285F4'", "'lineColor':'#BDC1C6'",
        "'fontFamily':'Noto Sans SC,PingFang SC,Microsoft YaHei,sans-serif'",
        "'fontSize':'14px'",
    ]
    for i in range(12):
        tv.append(f"'cScale{i}':'{blue if i % 2 == 0 else green}'")
        tv.append(f"'cScaleLabel{i}':'{ink}'")
        tv.append(f"'cScaleInv{i}':'{blue_t if i % 2 == 0 else green}'")
    init = "%%{init: {'theme':'base','themeVariables':{" + ",".join(tv) + "}}}%%"

    shown = tree[:12]
    lines = ["```mermaid", init, "mindmap", f'  root["《{_mm(title, 18)}》"]']
    for t in shown:
        nm = _mm((t["no"] + " " + t["name"]).strip(), 24)
        if not nm:
            continue
        lines.append(f"    {nm}")
        if t["secs"]:
            h = _mm(t["secs"][0]["h"], 22)
            if h:
                lines.append(f"      {h}")
    if len(tree) > len(shown):
        lines.append(f"    【另 {len(tree) - len(shown)} 章见章节目录】")
    lines.append("```")
    return lines


def _toc_tree(tree: list[dict]) -> list[str]:
    """章 → 小节 → 要点 → 代表原句，四层缩进列表（IMA 会按层级解析）。"""
    out = []
    for t in tree:
        head = f"- **{t['no']} {t['name']}**".replace("** ", "**").strip()
        if head.endswith("- **"):
            head = f"- **{t['name']}**"
        if t["stat"]:
            head += f"　（{t['stat']}）"
        out.append(head)
        for sec in t["secs"]:
            if sec["h"]:
                out.append(f"  - {sec['h']}")
                pad = "    "
            else:
                pad = "  "
            for pt in sec["points"]:
                out.append(f"{pad}- {pt}")
            if sec["quote"]:
                q = sec["quote"]
                if len(q) > 90:
                    q = q[:90].rstrip() + "…"
                out.append(f"{pad}- 原句：{q}")
    return out


def render(card: dict, mods: dict[str, str], tree: list[dict], cat: list[str],
           audit: dict, date_str: str, bookid: str = "", cover: str = "") -> tuple[str, str]:
    title = card["title"]
    slug = card["slug"]
    url = f"{SITE}/reading-notes/books/{slug}/combined.html"
    present = [k for k, _ in MOD_TITLES if mods.get(k)]
    one = re.sub(r"[*`#>]", "", mods.get("oneline", "").replace("一句话主旨", "", 1)).strip()
    one = re.sub(r"\s+", " ", one.split("\n")[0].lstrip("- ").strip()) if one else ""
    one = clip(one, 240)
    if not one:
        # 108 本书的 oneline 本身就是「共 N 章、逐字取自大纲」的结构统计，
        # 过滤掉后没有主旨 → 用结构脉络的分组名兜底，比空着有信息量。
        vs = [m.group(1).strip() for m in
              (re.match(r"^-\s+\*\*(.+?)\*\*", x.strip()) for x in mods.get("views", "").split("\n"))
              if m and len(m.group(1).strip()) <= 20]
        if vs:
            one = "全书主线：" + "、".join(vs[:3])
        elif tree:
            one = f"全书 {len(tree)} 章：" + "、".join(t["name"] for t in tree[:3])
        else:
            one = "站点未生成一句话主旨，见下方结构脉络"
    head = [
        f"# 《{title}》",
        "",
        *( [f"![《{title}》封面]({cover})", ""] if cover else [] ),
        f"> {one}",
        "",
        "| 项 | 值 |",
        "|---|---|",
        f"| bookId | {('`' + bookid + '`') if bookid else '—'} |",
        f"| 类目 | {' / '.join(x for x in cat if x) or '未分类'} |",
        f"| slug | `{slug}` |",
        f"| 卡片状态 | {audit.get('status', '?')}（{len(present)} 个标准模块：{', '.join(present)}） |",
        f"| 最近更新 | {date_str or '—'} |",
        f"| 站点原文 | {url} |",
        "",
    ]
    body = []
    idx = 1

    # 01 知识导图：IMA 没有生成导图的接口，这里用站点已编译的篇章结构本地生成，
    # 既能在支持 Mermaid 的阅读器里出图，也能被检索命中「章名-小节名」。
    if tree:
        n_sec = sum(len(t["secs"]) for t in tree)
        body += [f"## {idx:02d} 知识导图", ""]
        body += _mindmap(title, tree)
        body += ["", f"> {len(tree)} 章 · {n_sec} 个小节。导图取「篇→章」两级；"
                     "逐章的小节/要点/原句在最后一节「章节目录」里。", ""]
        idx += 1

    for key, label in MOD_TITLES:
        if key == "oneline":
            continue
        txt = mods.get(key, "")
        if not txt:
            continue
        txt = re.sub(r"^%s\s*" % re.escape(label), "", txt).strip()
        if not txt:
            continue
        body += [f"## {idx:02d} {label}", "", clip_list(txt), ""]
        idx += 1

    if tree:
        body += [f"## {idx:02d} 章节目录", "",
                 "> 层级：章 → 小节 → 要点 → 原句摘录。点站点原文可看每小节完整 AI 大纲。", ""]
        body += _toc_tree(tree)
        body += [""]

    # 不写 YAML front matter：IMA 会把文件开头当 introduction 展示，
    # front matter 会占满摘要位。元信息改放正文表格，检索同样能读到。
    md = "\n".join(head + body).rstrip() + "\n"
    return md, hashlib.sha1((TEMPLATE_VER + md).encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only-cat", default="")
    ap.add_argument("--local-only", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--mark", default="", help="JSON: {\"slug\": \"media_id\"} 回写上传结果")
    ap.add_argument("--only-slug", default="", help="只处理指定 slug（新书产出后单本同步）")
    args = ap.parse_args()

    IMA_DIR.mkdir(exist_ok=True)
    manifest = load_json("ima/manifest.json", {"version": TEMPLATE_VER, "cards": {}})
    cards_mf = manifest.setdefault("cards", {})

    if args.mark:
        patched = json.loads(Path(args.mark).read_text("utf-8"))
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        for slug, mid in patched.items():
            e = cards_mf.setdefault(slug, {})
            e["ima_media_id"] = mid
            e["synced_at"] = now
        MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), "utf-8")
        print(f"已回写 {len(patched)} 条上传结果 -> {MANIFEST}")
        return

    index = load_index_cards()
    _catf = load_json("assets/data/book-cats.json", {})
    covers = load_json("assets/data/covers.json", {}).get("covers", {})
    cats = _catf.get("books", {})
    bookids = _catf.get("ids", {})
    audit = load_json("assets/data/template-audit.json", {}).get("books", {})
    print(f"首页书卡 {len(index)} 本｜类目表 {len(cats)} 条｜bookId {len(bookids)} 条｜审计 {len(audit)} 条")

    todo = index
    if args.only_cat:
        todo = [c for c in todo if (cats.get(c["slug"]) or ["其他"])[0] == args.only_cat]
    if args.local_only:
        todo = [c for c in todo if (BOOKS / c["slug"] / "combined-data.html").exists()]
    if args.only_slug:
        todo = [c for c in todo if c["slug"] == args.only_slug]
    if args.limit:
        todo = todo[: args.limit]
    print(f"本次待处理 {len(todo)} 本")

    def work(card):
        slug = card["slug"]
        local = BOOKS / slug / "combined-data.html"
        if local.exists():
            html = local.read_text("utf-8", errors="ignore")
            src = "local"
        elif args.local_only:
            return None
        else:
            html = fetch_remote(slug)
            src = "remote"
        if not html:
            return {"slug": slug, "error": "no-data"}
        try:
            mods = sections(html)
            tree = guide_tree(html)
        except Exception as e:
            return {"slug": slug, "error": f"parse:{e}"}
        cat = cats.get(slug) or ["其他", "未分类"]
        md, h = render(card, mods, tree, cat, audit.get(slug, {}) or {},
                       card.get("date", ""), bookids.get(slug, ""), covers.get(slug, ""))
        return {"slug": slug, "md": md, "hash": h, "cat": cat, "src": src,
                "mods": len([k for k, _ in MOD_TITLES if mods.get(k)]), "size": len(md)}

    t0 = time.time()
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for i, r in enumerate(ex.map(work, todo), 1):
            if r:
                results.append(r)
            if i % 25 == 0:
                print(f"  …处理 {i}/{len(todo)}（{time.time()-t0:.0f}s）", flush=True)

    ok = [r for r in results if r.get("md")]
    bad = [r for r in results if r.get("error")]
    new, changed, same = [], [], []
    for r in ok:
        old = cards_mf.get(r["slug"], {}).get("hash")
        if args.force or not old:
            new.append(r)
        elif old != r["hash"]:
            changed.append(r)
        else:
            same.append(r)

    print(f"\n解析成功 {len(ok)}｜失败 {len(bad)}｜新增 {len(new)}｜变更 {len(changed)}｜未变 {len(same)}")
    if bad:
        print("失败样本:", bad[:5])
    if ok:
        sizes = sorted(r["size"] for r in ok)
        print("卡片体积 min/中位/max: %d / %d / %d 字节" % (sizes[0], sizes[len(sizes) // 2], sizes[-1]))

    if args.dry_run:
        for r in ok[:3]:
            print("\n" + "=" * 30, r["slug"])
            print(r["md"][:1200])
        return

    # 写盘
    CARDS.mkdir(exist_ok=True)
    # 去重：站点里同一本书可能有两个 slug（长/短目录），保留内容更全的一份，
    # 否则两条会写同一个文件名、并在 IMA 里变成两条同名知识。
    best: dict[tuple, dict] = {}
    for r in ok:
        m = re.search(r"^# 《(.+?)》", r["md"], re.M)
        r["_title"] = m.group(1) if m else r["slug"]
        key = ((r["cat"][0] if r["cat"] else "其他"), norm(r["_title"]))
        cur = best.get(key)
        if cur is None or r["size"] > cur["size"]:
            if cur is not None:
                cur["_dup"] = True
            best[key] = r
        else:
            r["_dup"] = True
    dups = [r for r in ok if r.get("_dup")]
    for d in dups:
        key = ((d["cat"][0] if d["cat"] else "其他"), norm(d["_title"]))
        keeper = best.get(key)
        cards_mf.setdefault(d["slug"], {}).update(
            {"duplicate_of": keeper["slug"] if keeper else "", "file": ""})
    ok = [r for r in ok if not r.get("_dup")]
    if dups:
        print(f"去重合并 {len(dups)} 本（同一书两个 slug）: " +
              ", ".join(d["slug"] for d in dups[:4]) + (" …" if len(dups) > 4 else ""))

    cat_index: dict[str, list] = {}
    for r in ok:
        cat = r["cat"]
        c1 = cat[0] if cat else "其他"
        m = re.search(r"^# 《(.+?)》", r["md"], re.M)
        title = clean_name(r["_title"], 80)
        path = CARDS / f"{clean_name(c1,12)}·{title}.md"
        path.write_text(r["md"], "utf-8")
        e = cards_mf.setdefault(r["slug"], {})
        e.update({"title": r["_title"], "cat1": c1,
                  "cat2": cat[1] if len(cat) > 1 else "", "hash": r["hash"],
                  "file": str(path.relative_to(ROOT)), "bytes": r["size"],
                  "modules": r["mods"], "exported_at": datetime.now().astimezone().isoformat(timespec="seconds")})
        e.pop("duplicate_of", None)
        cat_index.setdefault(c1, []).append((r["_title"], r["slug"], path.name))

    # 索引与说明
    order = ["文学", "历史", "社会文化", "哲学宗教", "艺术", "人物传记", "精品小说",
             "政治军事", "经济理财", "计算机", "其他"]
    # 索引刻意做小而精：列出类目与计数、每类 4 本代表，避免全量书名把检索结果挤满。
    n_cards = sum(len(v) for v in cat_index.values())
    lines = ["# we-read 书卡总索引", "",
             f"> {n_cards} 本｜{len(cat_index)} 个类目｜更新 {datetime.now().strftime('%Y-%m-%d')}｜"
             f"整站 {SITE}", "",
             "每本书一张书卡，文件名 `<类目>·<书名>.md`。本页只做导航，不承担检索。", ""]
    for c1 in order + sorted(set(cat_index) - set(order)):
        rows = cat_index.get(c1)
        if not rows:
            continue
        lines.append(f"## {c1}（{len(rows)} 本）")
        lines.append("")
        for title, slug, fn in sorted(rows)[:4]:
            lines.append(f"- 《{title}》")
        if len(rows) > 4:
            lines.append(f"- …其余 {len(rows) - 4} 本见「书卡」文件夹（文件名以「{c1}·」开头）")
        lines.append("")
    (IMA_DIR / "00-总索引.md").write_text("\n".join(lines), "utf-8")

    (IMA_DIR / "00-字段说明.md").write_text("""# we-read 书卡 · 字段与读法说明

本知识库每本书一张「书卡」，由站点 reading-notes/books/<slug>/combined-data.html 抽取，
不是读后感，也不含全书正文。用于按主题检索、横向对比与问答。

## 字段

| 字段 | 含义 |
|---|---|
| slug | 书在站点里的唯一目录名（英文/拼音），可用来拼站点 URL |
| title | 书名（中文） |
| cat1 / cat2 | 一级 / 二级类目，来自微信读书书架 |
| status | 卡片完整度：ok（9 模块齐）/ thin（缺 1~2）/ fixable / empty / dump |
| modules | 本书实际有的模块 |
| source | 站点详情页（combined.html） |

## 固定章节

01 一句话主旨 · 02 核心观点与结构脉络 · 03 精读判断 · 04 原文金句 ·
05 核心追问 · 06 AI 问书 · 07 更高维度 · 08 阅读时要验证 · 09 当年与今天 · 10 章节目录

缺哪个章节说明这本书没有该模块（多为未读、大纲接口返空）。

## 提问建议

- 「投资类书里，哪些对『估值』给过可操作的方法？」→ 按 cat1=经济理财 过滤后比对 02/03 节
- 「《1984》和《美丽新世界》对极权的判断差在哪？」→ 两卡 07 更高维度 节
- 「哪些书的 08 验证节提到译本问题？」→ 全库检索「译本」
""", "utf-8")

    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), "utf-8")
    pend = [{"slug": r["slug"], "file": cards_mf[r["slug"]]["file"],
             "title": cards_mf[r["slug"]]["title"], "cat1": r["cat"][0],
             "hash": r["hash"], "bytes": r["size"]}
            for r in (new + changed + [x for x in same
                                        if not cards_mf.get(x["slug"], {}).get("ima_media_id")])
            if cards_mf.get(r["slug"], {}).get("file") and not cards_mf.get(r["slug"], {}).get("duplicate_of")]
    PENDING.write_text(json.dumps({"generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                                   "count": len(pend), "items": pend}, ensure_ascii=False, indent=1), "utf-8")
    print(f"写出 {len(ok)} 张卡 → {CARDS}")
    print(f"待上传 {len(pend)} 条（新/变更 + 从未入库）→ {PENDING}")
    print(f"索引 → {IMA_DIR/'00-总索引.md'}")


if __name__ == "__main__":
    sys.exit(main())
