#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把整站书卡（reading-notes/books/<slug>/combined-data.html）导出为结构化 Markdown，
供 IMA 知识库「we-read」入库，支持增量。

用法：
  python3 tools/ima_export.py --dry-run              # 只统计，不写盘
  python3 tools/ima_export.py --limit 20             # 只导前 20 本（按首页顺序）
  python3 tools/ima_export.py --only-cat 经济理财     # 只导某类目
  python3 tools/ima_export.py --local-only           # 只用本地已检出目录（离线）
  python3 tools/ima_export.py --force                # 忽略 hash，全部重写

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

ROOT = Path(__file__).resolve().parent.parent
BOOKS = ROOT / "reading-notes" / "books"
IMA_DIR = ROOT / "ima"
CARDS = IMA_DIR / "cards"
MANIFEST = IMA_DIR / "manifest.json"
PENDING = IMA_DIR / "pending.json"
SITE = "https://reader.js-dev.cn"
TEMPLATE_VER = "imacard-v1"          # 卡片渲染规则变更时 +1，触发全量重写
MAX_SECTION = 2600                   # 单模块正文上限（字符）
MAX_TOC = 80                         # 章节目录最多列多少条

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
            return r.text
        return None
    except Exception:
        return None


# ---------------------------------------------------------------- HTML → 模块文本

def sections(html: str) -> dict[str, str]:
    """按 data-key 切 section，返回 {key: 纯文本}（不依赖 bs4，正则+去标签）。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    out = {}
    for sec in soup.find_all("section"):
        k = sec.get("data-key")
        if not k:
            continue
        for bad in sec.find_all(["style", "script"]):
            bad.decompose()
        out[k] = sec.get_text("\n", strip=True)
    return out


def toc_from_guide(html: str) -> list[str]:
    """只取 AI领读的章节目录骨架：编号 + 章名 + 规模，不取正文。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    mg = soup.find("section", attrs={"data-key": "merged_guide"})
    if not mg:
        return []
    items = []
    for d in mg.select("details.mmx-cn"):
        s = d.find("summary")
        if not s:
            continue
        name = s.get_text(" ", strip=True).replace("›", "").strip()
        stat = d.select_one(".mmx-stat")
        st = stat.get_text(" ", strip=True) if stat else ""
        items.append(f"- {name}" + (f"　（{st}）" if st else ""))
        if len(items) >= MAX_TOC:
            break
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


_META_HEAD = re.compile(r"^(本页|下方|以下|按全书|按章节|按主干|跨章|逐章|取自|（来自|\(来自|全书篇目)")
_META_HINT = ("由模型", "由云端", "由 AI", "AI 阅读流程", "非读后感", "结构化重算",
              "结构重算", "占位", "摘自", "替代原先")


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

def render(card: dict, mods: dict[str, str], toc: list[str], cat: list[str],
           audit: dict, date_str: str) -> tuple[str, str]:
    title = card["title"]
    slug = card["slug"]
    url = f"{SITE}/reading-notes/books/{slug}/combined.html"
    present = [k for k, _ in MOD_TITLES if mods.get(k)]
    one = as_markdown(clip(strip_meta(mods.get("oneline", "").replace("一句话主旨", "", 1)), 400))
    one = re.sub(r"^#+\s*", "", one).replace("\n\n", " ").strip() or "（暂无一句话主旨）"
    head = [
        f"# 《{title}》",
        "",
        f"> {one}",
        "",
        "| 项 | 值 |",
        "|---|---|",
        f"| 类目 | {' / '.join(x for x in cat if x) or '未分类'} |",
        f"| 卡片状态 | {audit.get('status', '?')}（{len(present)} 个标准模块） |",
        f"| 最近更新 | {date_str or '—'} |",
        f"| 站点原文 | {url} |",
        "",
    ]
    body = []
    idx = 1
    for key, label in MOD_TITLES:
        if key == "oneline":
            continue
        txt = mods.get(key, "")
        if not txt:
            continue
        txt = re.sub(r"^%s\s*" % re.escape(label), "", txt).strip()
        txt = strip_meta(txt)
        if not txt:
            continue
        body += [f"## {idx:02d} {label}", "", clip(as_markdown(txt)), ""]
        idx += 1
    if toc:
        body += [f"## {idx:02d} 章节目录", "", "\n".join(toc), ""]
    fm = [
        "---",
        f"slug: {slug}",
        f"title: {title}",
        f"cat1: {cat[0] if cat else ''}",
        f"cat2: {cat[1] if len(cat) > 1 else ''}",
        f"status: {audit.get('status', '')}",
        f"modules: {','.join(present)}",
        f"updated: {date_str}",
        f"source: {url}",
        "---",
        "",
    ]
    md = "\n".join(fm + head + body).rstrip() + "\n"
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
    cats = load_json("assets/data/book-cats.json", {}).get("books", {})
    audit = load_json("assets/data/template-audit.json", {}).get("books", {})
    print(f"首页书卡 {len(index)} 本｜类目表 {len(cats)} 条｜审计 {len(audit)} 条")

    todo = index
    if args.only_cat:
        todo = [c for c in todo if (cats.get(c["slug"]) or ["其他"])[0] == args.only_cat]
    if args.local_only:
        todo = [c for c in todo if (BOOKS / c["slug"] / "combined-data.html").exists()]
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
            toc = toc_from_guide(html)
        except Exception as e:
            return {"slug": slug, "error": f"parse:{e}"}
        cat = cats.get(slug) or ["其他", "未分类"]
        md, h = render(card, mods, toc, cat, audit.get(slug, {}) or {}, card.get("date", ""))
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
    lines = ["# we-read 书卡总索引", "",
             f"> 共 {len(cards_mf)} 本｜更新 {datetime.now().strftime('%Y-%m-%d %H:%M')}｜"
             f"站点 {SITE}", "", "按类目分组；点书名进站点原文，书卡在同名 Markdown 里。", ""]
    for c1 in order + sorted(set(cat_index) - set(order)):
        rows = cat_index.get(c1)
        if not rows:
            continue
        lines += [f"## {c1}（{len(rows)}）", ""]
        for title, slug, fn in sorted(rows):
            lines.append(f"- 《{title}》 — `{slug}` — {SITE}/reading-notes/books/{slug}/combined.html")
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
