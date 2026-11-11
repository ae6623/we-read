#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""书单工厂 · 扫描书架 → 归纳书单 → 校验 → 继续生产。

一条可重跑的流水线，解决「书单只能手工加、加完不知道链接死没死」的问题。
全部只读线上公开页面 + 本地备份的书架快照，不碰云端应用、不需要登录态。

子命令
  scan      扫描书架，产出 shelf_index.json（每本书的真实笔记 URL / 模板世代 / 封面 / 分类）
  check     校验 booklist_paths.json：3 阶段、每阶段≥1 本、每本 u 字段可访问、封面存在
  propose   按分类统计「哪些领域书够开新路径」，产出候选主题与书目池 topic_pool.json
  sync      把 shelf_index.json 里解析出的真实 URL 回填到 booklist_paths.json 的 u 字段

约定
  - 最新模板 = combined.html（动态「全书领读」，11 模块，reader-20261110.js 注入）
  - 旧模板   = overview.html（静态「全书视角·读前通读」）
  - 优先级：combined.html 200 > overview.html 200 > 不可用
  - 封面     = https://cdn.js-dev.cn/assets/covers/<slug>.jpg

用法
  python3 booklist_factory.py scan
  python3 booklist_factory.py check
  python3 booklist_factory.py propose
  python3 booklist_factory.py sync
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import html
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
HOME_URL = "https://reader.js-dev.cn/"
SITE = "https://reader.js-dev.cn/reading-notes/books/"
COVER = "https://cdn.js-dev.cn/assets/covers/%s.jpg"
# 书架快照：/api/shelf 导出的书目元数据（仅书名/作者/分类/产物标记，无登录态）。
# 默认取同目录 shelf_snapshot.json；可用 WR_SHELF_SNAPSHOT 指向别处。
SHELF_SNAPSHOT = os.environ.get("WR_SHELF_SNAPSHOT") or os.path.join(HERE, "shelf_snapshot.json")

INDEX = os.path.join(HERE, "shelf_index.json")
PATHS = os.path.join(HERE, "booklist_paths.json")
POOL = os.path.join(HERE, "topic_pool.json")

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0 (booklist-factory)"}


def req(url, method="GET"):
    try:
        r = urllib.request.Request(url, headers=UA, method=method)
        with urllib.request.urlopen(r, timeout=20, context=CTX) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def head(url):
    try:
        r = urllib.request.Request(url, headers=UA, method="HEAD")
        with urllib.request.urlopen(r, timeout=15, context=CTX) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def parse_home_cards(text):
    """从首页 HTML 抽书卡：slug / 书名 / 真实主链接 / 章节数 / 日期。"""
    out = {}
    for m in re.finditer(
        r'<article class="([^"]*card[^"]*)"([^>]*)>(.*?)</article>', text, re.S
    ):
        attrs, body = m.group(2), m.group(3)
        sm = re.search(r'data-slug="([^"]+)"', attrs)
        if not sm:
            continue
        slug = sm.group(1)
        tm = re.search(r'card-title-link"[^>]*href="([^"]+)"', body)
        nm = re.search(r'card-title-link"[^>]*>(.*?)</a>', body, re.S)
        cm = re.search(r"<p>([^<]*)</p>", body)
        dm = re.search(r'time datetime="([^"]+)"', body)
        title = re.sub(r"<[^>]+>", "", nm.group(1)).strip() if nm else ""
        title = html.unescape(re.sub(r"^《|》$", "", title))
        out[slug] = {
            "slug": slug,
            "title": title,
            "url": tm.group(1) if tm else None,
            "chapters": cm.group(1).strip() if cm else "",
            "date": dm.group(1) if dm else "",
        }
    return out


def load_shelf():
    if not os.path.exists(SHELF_SNAPSHOT):
        return {}
    d = json.load(open(SHELF_SNAPSHOT, encoding="utf-8"))
    return {
        b["slug"]: {
            "title": b.get("title", ""),
            "author": b.get("author", ""),
            "cat_l1": b.get("cat_l1") or "未分类",
            "cat_l2": b.get("cat_l2") or "",
            "category": b.get("category", ""),
            "finished": bool(b.get("finished")),
            "progress": b.get("progress"),
            "has": b.get("has") or {},
        }
        for b in d.get("books", [])
    }


def probe_one(slug):
    """探测一本书：最新模板优先、旧模板回退、封面是否有。"""
    c = head(SITE + slug + "/combined.html")
    if c == 200:
        url, tpl = "reading-notes/books/%s/combined.html" % slug, "combined"
    else:
        o = head(SITE + slug + "/overview.html")
        if o == 200:
            url, tpl = "reading-notes/books/%s/overview.html" % slug, "overview"
        else:
            url, tpl = None, None
    cv = head(COVER % slug) == 200
    return slug, url, tpl, cv


def cmd_scan(args):
    code, home = req(HOME_URL)
    if code != 200:
        print("首页抓取失败:", code)
        return 1
    cards = parse_home_cards(home)
    shelf = load_shelf()
    slugs = sorted(set(cards) | set(shelf))
    print("首页书卡 %d 本 / 书架快照 %d 本 / 合并去重 %d 本" % (len(cards), len(shelf), len(slugs)))

    with cf.ThreadPoolExecutor(max_workers=24) as ex:
        probed = dict(
            (s, (u, t, c)) for s, u, t, c in ex.map(probe_one, slugs)
        )

    books = []
    for s in slugs:
        c = cards.get(s, {})
        sh = shelf.get(s, {})
        u, tpl, cv = probed.get(s, (None, None, False))
        books.append({
            "slug": s,
            "title": sh.get("title") or c.get("title") or "",
            "author": sh.get("author", ""),
            "cat_l1": sh.get("cat_l1", "未分类"),
            "cat_l2": sh.get("cat_l2", ""),
            "url": u,
            "tpl": tpl,
            "cover": cv,
            "in_home": s in cards,
            "home_url": c.get("url"),
            "date": c.get("date", ""),
        })

    idx = {
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": [HOME_URL, SHELF_SNAPSHOT],
        "rule": "combined.html 优先，overview.html 回退",
        "total": len(books),
        "usable": sum(1 for b in books if b["url"]),
        "books": books,
    }
    with open(INDEX, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=1)

    import collections
    print("可用笔记页 %d / %d" % (idx["usable"], idx["total"]))
    print("模板世代:", dict(collections.Counter(b["tpl"] or "无" for b in books)))
    print("封面齐备:", sum(1 for b in books if b["cover"]))
    print("→ 已写", INDEX)
    return 0


def load_paths():
    return json.load(open(PATHS, encoding="utf-8"))


def cmd_check(args):
    paths = load_paths()
    idx = json.load(open(INDEX, encoding="utf-8")) if os.path.exists(INDEX) else {"books": []}
    by_slug = {b["slug"]: b for b in idx["books"]}
    problems = []
    nbooks = 0
    for p in paths:
        stages = p.get("stages", [])
        if len(stages) != 3:
            problems.append("%s: 阶段数 %d（应为 3）" % (p["id"], len(stages)))
        for i, st in enumerate(stages, 1):
            if not st.get("items"):
                problems.append("%s: 第 %d 阶段无书" % (p["id"], i))
        total = sum(len(st.get("items", [])) for st in stages)
        nbooks += total
        if not (8 <= total <= 12):
            problems.append("%s: 共 %d 本（建议 8–12）" % (p["id"], total))
        for st in stages:
            for it in st["items"]:
                s, u = it["s"], it.get("u")
                ref = by_slug.get(s, {})
                if not u:
                    problems.append("%s: %s 缺 u 字段（会回退旧 overview）" % (p["id"], s))
                elif ref.get("url") and u != ref["url"]:
                    problems.append("%s: %s 的 u 与扫描不符 (%s != %s)" % (p["id"], s, u, ref["url"]))
                if idx["books"] and not ref.get("cover"):
                    problems.append("%s: %s 无封面" % (p["id"], s))
    print("路径 %d 条 / 书目 %d 本 / 问题 %d 条" % (len(paths), nbooks, len(problems)))
    for x in problems[:60]:
        print("  !", x)
    if len(problems) > 60:
        print("  ... 另有 %d 条" % (len(problems) - 60))
    return 1 if problems else 0


def cmd_propose(args):
    """按分类归纳：哪些领域书够多、可以开新路径，给出已验链接的候选书目池。"""
    idx = json.load(open(INDEX, encoding="utf-8"))
    paths = load_paths()
    used = {it["s"] for p in paths for st in p["stages"] for it in st["items"]}
    covered = {p["field"] for p in paths}

    import collections
    groups = collections.defaultdict(list)
    for b in idx["books"]:
        if b["url"] and b["cover"]:
            groups[b["cat_l1"]].append(b)

    topics = []
    for cat, bs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        fresh = [b for b in bs if b["slug"] not in used]
        topics.append({
            "cat": cat,
            "usable": len(bs),
            "unused": len(fresh),
            "covered_by_paths": cat in covered,
            "can_open_path": len(fresh) >= 9,
            "candidates": [
                {"s": b["slug"], "t": b["title"], "u": b["url"], "tpl": b["tpl"], "cat_l2": b["cat_l2"]}
                for b in fresh
            ],
        })
    out = {
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "note": "按 cat_l1 归纳；can_open_path=true 表示该领域还有 ≥9 本未用且链接/封面齐备，可开一条 3 阶段路径。语义（title/goal/stages/why）由 agent 编排后写入 booklist_paths.json。",
        "existing_paths": [{"id": p["id"], "field": p["field"], "level": p["level"]} for p in paths],
        "topics": topics,
    }
    with open(POOL, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("领域 %d 个；可开新路径的领域：" % len(topics))
    for t in topics:
        flag = "可开" if t["can_open_path"] else "  -"
        print("  %s %-8s 可用 %3d / 未用 %3d  已覆盖=%s" % (
            flag, t["cat"], t["usable"], t["unused"], t["covered_by_paths"]))
    print("→ 已写", POOL)
    return 0


def cmd_sync(args):
    """把扫描出的真实 URL 回填到每条路径的 u 字段（幂等，只补不改语义）。"""
    idx = json.load(open(INDEX, encoding="utf-8"))
    by_slug = {b["slug"]: b for b in idx["books"]}
    paths = load_paths()
    changed = 0
    for p in paths:
        for st in p["stages"]:
            for it in st["items"]:
                u = by_slug.get(it["s"], {}).get("url")
                if u and it.get("u") != u:
                    it["u"] = u
                    changed += 1
    with open(PATHS, "w", encoding="utf-8") as f:
        json.dump(paths, f, ensure_ascii=False, indent=1)
    print("回填 %d 条 u 字段 → %s" % (changed, PATHS))
    return 0


def main():
    ap = argparse.ArgumentParser(description="书单工厂：扫描书架 → 归纳书单 → 校验 → 继续生产")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in [("scan", cmd_scan), ("check", cmd_check),
                     ("propose", cmd_propose), ("sync", cmd_sync)]:
        sub.add_parser(name).set_defaults(fn=fn)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
