# -*- coding: utf-8 -*-
"""auto.py — 通用「读前通读页」自动生产（overview_gen）。

把原本只支持 8 本内置策划书（books.py 手写配置）的 overview_gen，扩展成
可对任意书「给书名 → 匹配 → 一键生成」：

  1) 给出书名（控制台多行输入 / CLI） → 匹配已有书：
       优先 books.py 手写精修策划，其次 data/overview 已生成书
  2) 解析该书 data/overview/<slug>/outline.html（AI读书 AI 大纲，需先导出/上传）
  3) slug 在 books.py 里有手写精修配置 → 用精修版；否则按大纲自动派生内容层
  4) build → 质量门禁 → 写本地缓存 →（可选）发布到 we-read 站点仓库
  5) 「有则补偿，没有则生产新的」：已有 overview 的记 compensated，没有的记 created；
     缺 outline.html 的记 missing_outline 并给出应放置的精确路径

数据约定（相对仓库根 data/overview/）：
  data/overview/<slug>/outline.html   AI读书导出的 AI 大纲（必填输入）
  data/overview/<slug>/meta.json      {title, author, slug, created_at}（自动维护）
  data/overview/<slug>/overview.html  生成的本地缓存（发布副本在 we-read 仓库）

用法（库）：
  from overview_gen.auto import auto_generate
  results = auto_generate(["三体", "活着"], publish=True)

用法（CLI）：
  python -m overview_gen auto --names "三体\n活着" --publish
  python -m overview_gen books          # 列出 data/overview 下已有书
"""
import json
import os
import re
import zlib
import html as _html
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .parse_outline import parse_outline
from .build_overview import build, split_plain
from .quality_gate import check as gate_check
from . import books as books_mod
from .publish import publish_overview, load_cfg

OVERVIEW_ROOT = Path(os.environ.get("OVERVIEW_ROOT", "data/overview"))

TS_FMT = "%Y-%m-%d %H:%M"


def _now():
    return datetime.now(timezone(timedelta(hours=8))).strftime(TS_FMT)


def slugify(title):
    """把书名转成稳定的 URL-safe slug（确定性，跨进程一致）。

    优先 pypinyin（若已安装，得到美观的拼音 slug）；否则回退到
    「ASCII 安全前缀 + zlib.crc32 哈希」，保证唯一且稳定（绝不用 hash()，
    因为 Python 的 str hash 跨进程随机化，会导致 slug 漂移、线上 URL 失效）。
    """
    t = (title or "").strip()
    if not t:
        return "untitled"
    # 1) 尝试 pypinyin（美观拼音 slug）
    try:
        from pypinyin import lazy_pinyin  # type: ignore
        parts = lazy_pinyin(t)
        s = "-".join(parts)
        s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
        if s:
            return s[:64]
    except Exception:
        pass
    # 2) 回退：剥掉汉字后若还剩 ASCII，用它做前缀；否则用 book；再加确定性哈希
    safe = re.sub(r"[^a-z0-9]+", "-",
                  re.sub(r"[\u4e00-\u9fff]", "", t.lower())).strip("-")
    h = "%08x" % (zlib.crc32(t.encode("utf-8")) & 0xffffffff)
    base = safe if safe else "book"
    return (base + "-" + h)[:64]


def book_dir(slug):
    return OVERVIEW_ROOT / slug


def meta_path(slug):
    return book_dir(slug) / "meta.json"


def outline_path(slug):
    return book_dir(slug) / "outline.html"


def overview_cache_path(slug):
    return book_dir(slug) / "overview.html"


def fetch_outline_from_repo(slug, cfg=None):
    """从 we-read 站点仓拉 reading-notes/books/<slug>/outline.html 落到本地缓存。
    绝大多数书的大纲已随站点入仓，本地缺大纲时优先自动拉取，上传只是兜底。"""
    try:
        from .publish import load_cfg, _gh_api
        cfg = cfg or load_cfg()
        api = _gh_api()(cfg)
        data = api.read_file("reading-notes/books/%s/outline.html" % slug)
        if not data:
            return False
        p = outline_path(slug)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return True
    except Exception:
        return False


def load_meta(slug):
    p = meta_path(slug)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def save_meta(slug, title, author):
    d = book_dir(slug)
    d.mkdir(parents=True, exist_ok=True)
    meta = load_meta(slug) or {}
    meta.update({
        "slug": slug,
        "title": title,
        "author": author or meta.get("author") or "（待补，可在 meta.json 填写）",
        "created_at": meta.get("created_at") or _now(),
        "updated_at": _now(),
    })
    meta_path(slug).write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    return meta


def iter_data_books():
    """yield (slug, meta) —— data/overview 下每个带 meta.json 的书。"""
    if not OVERVIEW_ROOT.exists():
        return
    for d in sorted(OVERVIEW_ROOT.iterdir()):
        if d.is_dir():
            m = load_meta(d.name)
            if m:
                yield d.name, m


def _norm(t):
    return re.sub(r"\s+", "", (t or "").strip().lower())


def find_book(title):
    """匹配书名 → 已有书。返回 dict：
       {found, slug, title, author, source}，source ∈ {'books','data',None}
    books.py 手写精修策划优先；其次 data/overview 已生成书；否则按 slugify 算新书 slug。
    """
    t = (title or "").strip()
    if not t:
        return {"found": False, "slug": None, "title": t, "author": None, "source": None}
    n = _norm(t)
    # 1) books.py 手写精修策划（精确）
    for slug, cfg in books_mod.BOOKS.items():
        if _norm(cfg.get("title", "")) == n:
            return {"found": True, "slug": slug, "title": cfg.get("title", t),
                    "author": cfg.get("author"), "source": "books"}
    # 2) data/overview 已生成（精确）
    for slug, m in iter_data_books():
        if _norm(m.get("title", "")) == n:
            return {"found": True, "slug": slug, "title": m.get("title", t),
                    "author": m.get("author"), "source": "data"}
    # 3) 子串兜底（容错：用户少打/多打了前后缀）
    for slug, cfg in books_mod.BOOKS.items():
        if n and n in _norm(cfg.get("title", "")):
            return {"found": True, "slug": slug, "title": cfg.get("title", t),
                    "author": cfg.get("author"), "source": "books"}
    for slug, m in iter_data_books():
        if n and n in _norm(m.get("title", "")):
            return {"found": True, "slug": slug, "title": m.get("title", t),
                    "author": m.get("author"), "source": "data"}
    # 未找到：新书 slug 用 slugify（确定性）
    return {"found": False, "slug": slugify(t), "title": t,
            "author": None, "source": None}


def derive_cfg(parsed, title, author, chip="AI大纲整理"):
    """从解析后的大纲自动派生内容层（无手写配置时）。

    正文只陈述大纲事实，不额外贴标签；质量低于人工精修页；
    建议读后人工润色或把精修版补进 books.py。
    """
    chapters = parsed or []
    n_ch = len(chapters)

    # 一句话主旨：取首章前两条要点拼成引导句
    lead_pts = []
    for c in chapters[:1]:
        for s in c.get("secs", []):
            lead_pts.extend(s.get("points", [])[:2])
    lead = lead_pts[0][:70] if lead_pts else "（大纲未提供可归纳的要点）"
    thesis = (
        "《%s》全书由 AI 大纲自动整理：共 %d 个章节条目。%s"
        ''
    ) % (title, n_ch, _html.escape(lead, quote=False))

    # 全书结构（mindmap）：章节标题 + 各章首层小节（忠实转写，按原样呈现）
    lines = ["%s · %s · 共 %d 章" % (title, author or "（作者待补）", n_ch)]
    for i, c in enumerate(chapters, 1):
        secs = " / ".join(s.get("h4", "") for s in c.get("secs", []) if s.get("h4"))[:48]
        lines.append("├─ 第%d章 《%s》" % (i, c.get("title", "")))
        if secs:
            lines.append("│   └─ %s" % secs)
    mindmap = _html.escape("\n".join(lines), quote=False)

    # AI 问书：转述前 3 章要点
    ai_parts = []
    for i, c in enumerate(chapters[:3], 1):
        pts = []
        for s in c.get("secs", []):
            pts.extend(s.get("points", [])[:2])
        if pts:
            summary = "；".join(p[:60] for p in pts[:3])
            ai_parts.append(
                '<p>第%d章《%s》：%s</p>'
                % (i, _html.escape(c.get("title", ""), quote=False),
                   _html.escape(summary, quote=False))
            )
    ai = "\n".join(ai_parts) or "<p>大纲未提供可转述的要点。</p>"

    # 核心观点初判：取前两章各一张「主张 + 存疑」卡
    views_parts = []
    for i, c in enumerate(chapters[:2], 1):
        views_parts.append(
            '<article class="card"><h3>《%s》的线索可归纳为核心议题</h3>'
            '<p><strong>主张来源：</strong>第%d章大纲条目（要点与原文摘录）。</p>'
            '<p><strong>判断：存疑。</strong>大纲仅给出条目级要点，是否构成全书核心主张'
            '需回原文核对；本页不作定论。</p></article>'
            % (_html.escape(c.get("title", ""), quote=False), i)
        )
    views = "\n".join(views_parts)

    action = (
        "<p><b>一、读前立靶：</b>先看本页「全书结构」，写出本书要解答的 1 个问题，"
        "把第一章要点当路标。</p>"
        "<p><b>二、读中对照：</b>每读完一章回到本页「原文摘录」做一句复述，"
        "避免被大纲带偏结论。</p>"
        "<p><b>三、验证存疑：</b>凡标「存疑」的观点，读原文时专门核对一次再决定是否采纳。</p>"
    )
    quiz = (
        "<li>本书 AI 大纲共列出多少章节条目？它们大致如何分组？</li>"
        "<li>第一章最让你意外的要点是什么？它和你原先的预期有何不同？</li>"
        "<li>合上本页，你能用自己的话讲清本书试图解决的问题吗？</li>"
    )
    memo = (
        "<p>《%s》是 AI 大纲自动整理页：先抓全书骨架（%d 章）与首章要点，再带着问题读原文。</p>"
        "<p>每周回看一次——哪些「存疑」已读原文验证、哪些仍待查证，让记忆复利。</p>"
    ) % (title, n_ch)

    total_pts = sum(len(s.get("points", [])) for c in chapters for s in c.get("secs", []))
    src = (
        "来源：本书 AI 大纲（共 %d 个章节条目、%d 条要点）；本页为<b>自动整理</b>，"
        "未逐页亲读正文，未改变任何章节的亲读状态。章节标题与要点忠实转写自大纲；"
        "「原文摘录」转录自大纲条目，个别标点/断句可能与纸书微差，引用前请回原文核对。"
        "凡标「存疑/推断」处均为整理者判断，非原书结论。"
        "<b>本页由程序依据 AI 大纲自动生成，质量低于人工精修页，建议读后人工润色或补写到 books.py。</b>"
    ) % (n_ch, total_pts)

    return {
        "title": title,
        "author": author or "（待补，可在 meta.json 填写）",
        "chip": chip,
        "split": split_plain,
        "thesis": thesis,
        "mindmap": mindmap,
        "ai": ai,
        "views": views,
        "action": action,
        "quiz": quiz,
        "memo": memo,
        "src": src,
        "head_note": "　·　本页由程序依据 AI 大纲自动生成，未经人工精修。",
    }


def generate(title, author=None, publish=False, dry_run=False, force=False):
    """生产单本 overview，返回结果 dict（含 status / action / gate / error）。"""
    fb = find_book(title)
    slug = fb["slug"]
    author = author or fb.get("author")
    existed_before = overview_cache_path(slug).exists()
    op = outline_path(slug)
    res = {
        "title": title, "slug": slug, "matched": fb["found"],
        "source": fb["source"], "author": author,
        "action": None, "status": None, "bytes": 0,
        "gate": [], "published": False, "url": None,
        "outline_path": str(op), "error": None,
    }
    if not op.exists():
        # 先尝试从 we-read 站点仓自动拉（多数书的大纲已随站点入仓），失败才要求上传
        if fetch_outline_from_repo(slug):
            res["action"] = "fetched_outline"
        else:
            res["status"] = "missing_outline"
            res["error"] = ("缺少 AI 大纲且站点仓库里也没有该书的大纲：请把AI读书 AI 大纲"
                            "导出后放到 %s，或在控制台用「上传大纲」按钮上传，然后重新点「自动生产」。") % str(op)
            return res
    try:
        chapters = parse_outline(op.read_text(encoding="utf-8"))
    except Exception as e:
        res["status"] = "parse_error"
        res["error"] = "解析大纲失败: %s" % str(e)[:200]
        return res
    if not chapters:
        res["status"] = "empty_outline"
        res["error"] = ("大纲解析为空（outline.html 可能不是AI读书 AI 大纲格式，"
                       "需含 <div class=\"toc\"> … <details class=\"ch\"> 结构）。")
        return res
    # 内容层：books.py 手写精修优先，否则自动派生
    if slug in books_mod.BOOKS:
        cfg = books_mod.BOOKS[slug]
    else:
        # 占位符（含「待补」）统一视为「未填」，保证同一输入产出恒定，
        # 否则首次运行 author=None 与后续读 meta 默认值会产出不同文案、触发多余重发。
        author_for_cfg = author if (author and "待补" not in author) else None
        cfg = derive_cfg(chapters, fb["title"] or title, author_for_cfg)
    try:
        from .cli import _load_aiqa_data
        aiqa_html, quiz_answers = _load_aiqa_data(slug)
        html = build(cfg, chapters, aiqa_html=aiqa_html, quiz_answers=quiz_answers)
    except Exception as e:
        res["status"] = "build_error"
        res["error"] = "渲染失败: %s" % str(e)[:200]
        return res
    # 质量门禁（写到本地缓存后检查）
    cache = overview_cache_path(slug)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(html, encoding="utf-8")
    gate = gate_check(str(cache))
    res["bytes"] = len(html.encode("utf-8"))
    res["gate"] = [{"rule": r, "status": s, "note": n} for (_, r, s, n) in gate]
    if any(g["status"] == "FAIL" for g in res["gate"]):
        fails = [g for g in res["gate"] if g["status"] == "FAIL"]
        res["status"] = "gate_fail"
        res["error"] = "质量门禁未通过: " + "; ".join(
            "%s=%s" % (g["rule"], g["note"]) for g in fails)
        return res
    # 维护 meta
    save_meta(slug, fb["title"] or title, author)
    # 发布
    if publish:
        try:
            cfg_repo = load_cfg()
            ok, msg, detail = publish_overview(slug, html, cfg_repo, dry_run=dry_run)
            res["published"] = bool(ok) and not dry_run
            res["url"] = (detail.get("url")
                          if isinstance(detail, dict) else None)
            if not ok:
                res["status"] = "publish_fail"
                res["error"] = "发布失败: %s" % str(msg)[:200]
                return res
        except Exception as e:
            res["status"] = "publish_error"
            res["error"] = "发布异常: %s" % str(e)[:200]
            return res
    res["action"] = "compensated" if (existed_before and not force) else "created"
    res["status"] = "ok"
    return res


def auto_generate(names, publish=False, dry_run=False):
    """批量生产。names 可为换行/逗号分隔字符串或列表，返回结果列表。"""
    if isinstance(names, str):
        items = re.split(r"[\n,，;；]+", names)
    else:
        items = list(names)
    items = [x.strip() for x in items if x and x.strip()]
    return [generate(t, publish=publish, dry_run=dry_run) for t in items]
