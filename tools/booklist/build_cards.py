#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""书卡工厂 · 把 booklist_paths.json 的真人书目导成频道页要的 cards.json。

为什么需要它
  频道页 channel/index.html 早期是 3 张手工样卡（室内设计主题，纯占位）。
  真实书目其实已经在 booklist_paths.json 里（9 条路径 / 85 本，含 slug、
  书名、一句话推荐、笔记 URL），书架快照还带着作者、分类、进度。
  这个脚本把两份数据联起来，顺带从 CDN 封面提主色，产出一份纯 JSON，
  频道页只负责渲染，不再硬编码任何一本书。

产出
  channel/cards.json          频道页 fetch 的数据源
    count / paths / cards[] / pool[] / lists[]
  lists[] 是频道页真正渲染的卡：一张卡 = 一条书单，卡内按三个阶段列出全部
    书目。之前一卡一本书，同一条书单的十本被拆开摊在画廊里，翻着像同一个
    主题反复出现，也看不出「第几步」。
  cards[] 保留一卡一本的形态，给 book.html（书卡详情）取 sib 关联书用。
  pool[] 是全库可访问书目（书单内 + 书架其余），只带渲染必需字段，
    cards[].sib 存的是 pool 下标，书卡详情的「关联阅读」从这里取书，
    这样一本书能挂十几本真正相关的书，而不是只有同阶段的 3 本。
  tools/booklist/notes_index.json  笔记页探测缓存（slug → combined/overview），
    避免每次重跑都打 400 多次网络。
  每张卡字段：
    i        全书序号（1 起）
    slug     书 slug，同时是封面文件名
    t        书名（已去掉副标题括号）
    tFull    原始书名
    a        作者（快照缺失时为空串）
    w        一句话推荐（来自书单，不是生成的）
    cover    封面绝对 URL
    href     笔记页相对地址（相对 /channel/）
    f/l/level 领域 / 难度
    cat      一级-二级分类
    p        所属书单 id / pi 书单内序号 / pt 书单标题 / pn 书单总数
    st       阶段序号 / stn 阶段总数 / stName 阶段名
    prog     阅读进度 0-100 / fin 是否读毕
    hue      封面主色相（0-360）
    sib      关联书在 pool 里的下标（最多 15 个，卡内横向轨道按此顺序铺）
    sibTag   与 sib 一一对应的关联理由：同作者 / 同一步 / 同书单 / 同题材 / 同领域

用法
  python3 tools/booklist/build_cards.py            # 生成
  python3 tools/booklist/build_cards.py --no-color # 跳过封面取色（离线/提速）
  python3 tools/booklist/build_cards.py --check    # 只校验输入，不写文件
"""
import argparse
import colorsys
import concurrent.futures as cf
import io
import json
import os
import re
import ssl
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PATHS = os.path.join(HERE, "booklist_paths.json")
SHELF = os.environ.get("WR_SHELF_SNAPSHOT") or os.path.join(HERE, "shelf_snapshot.json")
INDEX = os.path.join(HERE, "notes_index.json")
OUT = os.path.join(ROOT, "channel", "cards.json")
COVER = "https://cdn.js-dev.cn/assets/covers/%s.jpg"
SITE = "https://reader.js-dev.cn/reading-notes/books/"

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0 (bookcard-factory)"}


def clean_title(t):
    t = (t or "").strip()
    for sep in ("（", "(", "【", "——", "："):
        i = t.find(sep)
        if i >= 4:
            t = t[:i]
            break
    return t.strip(" ：:·") or (t or "")


def norm_author(a):
    a = (a or "").strip()
    if a.lower() in ("unknown", "n/a", "none", "-"):
        return ""
    a = re.sub(r"\s{2,}", " ", a)
    # 多作者压缩：卡面只有一行，留前两位 + 等，避免撑爆被省略号切得难看
    parts = [x for x in re.split(r"\s+(?=\[)", a) if x]
    if len(parts) > 2:
        a = " ".join(parts[:2]) + " 等"
    return a


def hue_from_bytes(raw):
    """封面主色相。丢掉近白/近黑/低饱和像素，取色相圆均值。"""
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        im = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        return None
    im.thumbnail((64, 84))
    xs, ys = [], []
    for r, g, b in im.getdata():
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if s < 0.16 or v < 0.12 or v > 0.96:
            continue
        ang = h * 2 * 3.141592653589793
        xs.append(__import__("math").cos(ang) * s)
        ys.append(__import__("math").sin(ang) * s)
    if len(xs) < 24:
        return None
    import math
    hx, hy = sum(xs) / len(xs), sum(ys) / len(ys)
    if abs(hx) < 1e-9 and abs(hy) < 1e-9:
        return None
    return int(round((math.atan2(hy, hx) % (2 * math.pi)) / (2 * math.pi) * 360)) % 360


def fallback_hue(slug):
    v = 0
    for ch in slug:
        v = (v * 131 + ord(ch)) & 0xFFFFFFFF
    return v % 360


def fetch_hue(slug):
    import urllib.request
    url = COVER % slug
    r = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(r, timeout=20, context=CTX) as resp:
            raw = resp.read()
    except Exception as e:
        return slug, None, str(e)
    return slug, hue_from_bytes(raw), None


def probe_note(slug):
    """探一本书的笔记页是 combined 还是 overview。返回 (slug, tpl|None)。"""
    import urllib.request
    for tpl in ("combined", "overview"):
        r = urllib.request.Request(SITE + slug + "/" + tpl + ".html",
                                   headers=UA, method="HEAD")
        try:
            with urllib.request.urlopen(r, timeout=12, context=CTX) as resp:
                if resp.status == 200:
                    return slug, tpl
        except Exception:
            continue
    return slug, None


def load_note_index(slugs, force=False):
    """读笔记页缓存，只补探测没探过的书。缓存就是为了别每次都打 400 次网络。"""
    tpl = {}
    if os.path.exists(INDEX) and not force:
        try:
            tpl = json.load(open(INDEX, encoding="utf-8")).get("tpl", {})
        except Exception:
            tpl = {}
    todo = [s for s in slugs if s not in tpl]
    if todo:
        print("探测笔记页 %d 本（缓存命中 %d）..." % (len(todo), len(slugs) - len(todo)))
        t0 = time.time()
        with cf.ThreadPoolExecutor(max_workers=12) as ex:
            for slug, t in ex.map(probe_note, todo):
                tpl[slug] = t or ""
        with open(INDEX, "w", encoding="utf-8") as f:
            json.dump({"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "tpl": tpl},
                      f, ensure_ascii=False, separators=(",", ":"))
        print("  探测完成 %.1fs，可用 %d / %d" % (
            time.time() - t0, sum(1 for s in todo if tpl.get(s)),
            len(todo)))
    return tpl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-color", action="store_true")
    ap.add_argument("--no-probe", action="store_true", help="只用已有缓存，不探测新书")
    ap.add_argument("--refresh-index", action="store_true", help="强制重探全部笔记页")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    paths = json.load(open(PATHS, encoding="utf-8"))
    shelf = {}
    if os.path.exists(SHELF):
        for b in json.load(open(SHELF, encoding="utf-8")).get("books", []):
            shelf[b.get("slug")] = b
    print("paths=%d  shelf=%d" % (len(paths), len(shelf)))

    cards = []
    seen = {}
    path_stages = {}
    for p in paths:
        pn = sum(len(s["items"]) for s in p["stages"])
        stage_slugs = []
        for si, st in enumerate(p["stages"], 1):
            stage_slugs.append([])
            for it in st["items"]:
                slug = it["s"]
                if slug in seen:
                    stage_slugs[-1].append(seen[slug])
                    continue
                meta = shelf.get(slug, {})
                cat = meta.get("category") or ""
                if "未分类" in cat:
                    cat = ""
                cards.append({
                    "slug": slug,
                    "t": clean_title(it.get("t")),
                    "tFull": it.get("t", ""),
                    "a": norm_author(meta.get("author")),
                    "w": it.get("w", ""),
                    "cover": COVER % slug,
                    "href": "../" + it.get("u", "reading-notes/books/%s/overview.html" % slug),
                    "f": p["field"],
                    "l": p["level"],
                    "level": p["levelKey"],
                    "cat": cat,
                    "p": p["id"],
                    "pt": p["title"],
                    "pn": pn,
                    "st": si,
                    "stn": len(p["stages"]),
                    "stName": st.get("name", ""),
                    "prog": int(meta.get("progress") or 0),
                    "fin": bool(meta.get("finished")),
                    "hue": None,
                    "sib": [],
                })
                seen[slug] = len(cards) - 1
                stage_slugs[-1].append(len(cards) - 1)
        path_stages[p["id"]] = [{
            "name": st.get("name", ""),
            "aim": st.get("aim", ""),
            "tip": st.get("tip", ""),
            "slugs": [cards[i]["slug"] for i in group],
        } for st, group in zip(p["stages"], stage_slugs)]

    for i, c in enumerate(cards, 1):
        c["i"] = i
        c["pi"] = sum(1 for x in cards[:i] if x["p"] == c["p"])
        c["hue"] = fallback_hue(c["slug"])

    # ---- 关联池：全库可访问书目 ----------------------------------------
    # 只靠书单内 85 本，每条单最多凑 10 本、冷门类只有 2-3 本，做不出「十几本」。
    # 所以把书架 405 本也拉进来，只要笔记页能打开、有分类，就能参与关联。
    if a.no_probe:
        try:
            note_tpl = json.load(open(INDEX, encoding="utf-8")).get("tpl", {})
        except Exception:
            note_tpl = {}
    else:
        note_tpl = load_note_index(sorted(shelf.keys()), a.refresh_index)

    # 书单的 field 用的是「金融 / 世界史」这种细分叫法，书架 cat_l1 是「经济理财 /
    # 历史」。不映射的话，那些没有书架分类的书（20 本）就永远匹配不到同类，
    # 关联只能凑出三五本。
    FIELD_L1 = {
        "金融": "经济理财", "投资": "经济理财", "经济周期": "经济理财",
        "中国史": "历史", "世界史": "历史",
        "中国文学": "文学", "世界文明": "历史",
    }

    pool = []
    pool_ix = {}
    for slug, meta in shelf.items():
        tpl = note_tpl.get(slug)
        if not tpl:
            continue
        cat = (meta.get("category") or "").replace("未分类", "").strip()
        c1, _, c2 = cat.partition("-")
        pool.append({
            "slug": slug,
            "t": clean_title(meta.get("title")),
            "tFull": meta.get("title") or "",
            "a": norm_author(meta.get("author")),
            "cat": cat, "c1": c1, "c2": c2,
            "cover": COVER % slug,
            "href": "../reading-notes/books/%s/%s.html" % (slug, tpl),
            "inPath": False, "p": "", "st": 0,
        })
        pool_ix[slug] = len(pool) - 1

    # 书单里的书必须都在池里（笔记页探测失败也要兜住，书单的 u 字段是人工验过的）
    for c in cards:
        if c["slug"] in pool_ix:
            p = pool[pool_ix[c["slug"]]]
            p["inPath"], p["p"], p["st"] = True, c["p"], c["st"]
            if not p["c1"]:
                p["c1"] = FIELD_L1.get(c["f"], c["f"])
            continue
        c1, _, c2 = (c["cat"] or "").partition("-")
        pool.append({
            "slug": c["slug"], "t": c["t"], "tFull": c["tFull"], "a": c["a"],
            "cat": c["cat"], "c1": c1 or FIELD_L1.get(c["f"], c["f"]), "c2": c2,
            "cover": c["cover"], "href": c["href"],
            "inPath": True, "p": c["p"], "st": c["st"],
        })
        pool_ix[c["slug"]] = len(pool) - 1

    # ---- 关联度：同作者 > 同一步 > 同题材（跨单）> 同领域（跨单）> 同单补位 ----
    # 关键点：同一条书单的书不重复铺一遍。整条单点「领读」就能看全，
    # 卡内轨道要展示的是「这本书还接得上哪些书」，所以跨单题材分要高于同单分，
    # 同单只留少量补位，否则 14 本全是同单，看上去还是随机塞的。
    name_re = re.compile(r"[\u4e00-\u9fa5\u00b7]{2,}")

    def author_set(name):
        s = set(name_re.findall(name or ""))
        s.discard("等")
        return s

    au = [author_set(p["a"]) for p in pool]
    # 每张卡挂几本关联书：15 正好把详情页的 5 列铺满 3 行，不留半行尾巴
    SIB_N = 15
    QUOTA = {"同一步": 4, "同书单": 3}

    for i, c in enumerate(cards):
        ci = pool_ix.get(c["slug"], -1)
        cau = au[ci] if ci >= 0 else set()
        cc1 = pool[ci]["c1"] if ci >= 0 else ""
        scored = []
        for j, o in enumerate(pool):
            if j == ci:
                continue
            sc, tag = 0.0, ""
            if cau and au[j] and (cau & au[j]):
                sc, tag = 6.0, "同作者"
            if o["p"] and o["p"] == c["p"]:
                if o["st"] == c["st"]:
                    sc += 4.5
                    tag = tag or "同一步"
                else:
                    sc += 1.2
                    tag = tag or "同书单"
            if c["cat"] and o["cat"] == c["cat"]:
                sc += 3.6
                # 同单但不同阶段 + 同题材时，标「同题材」更有信息量
                if tag in ("", "同书单", "同领域"):
                    tag = "同题材"
            elif cc1 and o["c1"] == cc1:
                sc += 2.0
                tag = tag or "同领域"
            sc -= j * 0.0006
            if sc > 0.5:
                scored.append((sc, j, tag))
        scored.sort(key=lambda x: (-x[0], x[1]))

        picked, cnt = [], {}
        for sc, j, tag in scored:
            if tag in QUOTA and cnt.get(tag, 0) >= QUOTA[tag]:
                continue
            cnt[tag] = cnt.get(tag, 0) + 1
            picked.append((j, tag))
            if len(picked) >= SIB_N:
                break
        c["sib"] = [j for j, _ in picked]
        c["sibTag"] = [t for _, t in picked]

    print("cards=%d  pool=%d（书单内 %d）" % (
        len(cards), len(pool), sum(1 for p in pool if p["inPath"])))
    avg = sum(len(c["sib"]) for c in cards) / max(1, len(cards))
    print("每卡关联书 平均 %.1f 本，最少 %d 本" % (
        avg, min(len(c["sib"]) for c in cards)))

    # ---- 画廊排序：让相邻的卡互有关联，而不是按书单顺序拼接 ----
    # 原来是「书单 A 的 9 本 + 书单 B 的 10 本」依次摊开，翻的时候主题乱跳，
    # 看着就像随机堆的。改成贪心链：每步从还没用到的卡里挑与当前卡关联最强的
    # 一本接上去，链断了（没有关联）自然落到最早未用的一本重新起链，
    # 整条画廊就成了一条主题流，相邻两卡必定说得上有什么关系。
    for c in cards:
        # 20 本没有书架分类，但有书单领域，用它兜底，别让这些书在链上被孤立
        c["_c1"] = (c["cat"] or "").partition("-")[0] or c["f"]
        c["_au"] = author_set(c["a"])

    def rel_score(a, b):
        s = 0.0
        if a["p"] and a["p"] == b["p"]:
            s += 4.5 if a["st"] == b["st"] else 1.2
        if a["cat"] and a["cat"] == b["cat"]:
            s += 3.6
        elif a["_c1"] and a["_c1"] == b["_c1"]:
            s += 2.0
        if a["_au"] and b["_au"] and (a["_au"] & b["_au"]):
            s += 6.0
        return s

    order, used = [0], {0}
    while len(order) < len(cards):
        cur = cards[order[-1]]
        best, bs = -1, -1e9
        for j, o in enumerate(cards):
            if j in used:
                continue
            s = rel_score(cur, o)
            if s > bs:
                bs, best = s, j
        order.append(best)
        used.add(best)

    cards = [cards[j] for j in order]
    joined = sum(1 for k in range(1, len(cards))
                 if rel_score(cards[k - 1], cards[k]) > 0)
    for i, c in enumerate(cards, 1):
        c["i"] = i
        c.pop("_c1", None)
        c.pop("_au", None)

    print("画廊相邻卡有关联 %d / %d 对（%.0f%%）" % (
        joined, len(cards) - 1, joined * 100.0 / max(1, len(cards) - 1)))

    if a.check:
        bad = [c for c in cards if not c["t"] or not c["w"] or not c["cover"]]
        print("缺字段:", len(bad))
        for c in bad[:5]:
            print("  ", c["slug"])
        return 0

    if not a.no_color:
        uniq = sorted(seen.keys())
        print("从 CDN 取封面主色 %d 张 ..." % len(uniq))
        t0 = time.time()
        ok = fail = 0
        with cf.ThreadPoolExecutor(max_workers=8) as ex:
            for slug, hue, err in ex.map(fetch_hue, uniq):
                if hue is not None:
                    cards[seen[slug]]["hue"] = hue
                    ok += 1
                else:
                    fail += 1
        print("取色 ok=%d fail=%d  用时 %.1fs" % (ok, fail, time.time() - t0))

    paths_out = [{
        "id": p["id"], "field": p["field"], "level": p["level"], "levelKey": p["levelKey"],
        "title": p["title"], "goal": p["goal"],
        "n": sum(1 for c in cards if c["p"] == p["id"]),
        "stages": path_stages.get(p["id"], []),
    } for p in paths]

    # ---- 书单卡：频道页的主卡单位 --------------------------------------
    # 之前一卡一本书，同一条书单的 10 本被拆开摊在画廊里，翻着像同一个主题
    # 反复出现，而且看不出「第几步」。改成一卡 = 一条书单，卡内按阶段列出
    # 全部书目，卡与卡之间才是书单之间的衔接，步骤关系就落在卡里了。
    by_slug = {c["slug"]: c for c in cards}
    # 书单排序：钱 → 判断力 → 社会 → 商业 → 历史 → 文学，一条从具体到宏观
    # 再到审美的路。原来是按写完的先后拼的，中国史夹在投资和周期中间，翻过去断档。
    LIST_ORDER = [
        "finance-base", "stock-value", "cycle-crisis", "macro-policy",
        "corp-finance", "market-game", "money-personal",
        "thinking-basics", "society-observe", "business-management",
        "china-history", "world-history-modern", "world-us-history",
        "world-civilization",
        "literature-cn", "literature-documentary", "literature-essay",
    ]

    def split_title(t):
        for sep in ("·", "："):
            i = t.find(sep)
            if i > 0:
                return t[:i].strip(), t[i + 1:].strip()
        return t, ""

    paths_sorted = sorted(
        paths,
        key=lambda p: LIST_ORDER.index(p["id"]) if p["id"] in LIST_ORDER
        else len(LIST_ORDER))

    lists_out = []
    for p in paths_sorted:
        sts = []
        for si, st in enumerate(p["stages"], 1):
            books = []
            for it in st["items"]:
                c = by_slug.get(it["s"])
                if not c:
                    continue
                books.append({k: c[k] for k in
                              ("slug", "t", "a", "cover", "w", "prog", "fin", "hue")})
            if books:
                sts.append({"i": si, "name": st.get("name", ""),
                            "aim": st.get("aim", ""), "tip": st.get("tip", ""),
                            "books": books})
        if not sts:
            continue
        allb = [b for s in sts for b in s["books"]]
        main, sub = split_title(p["title"])
        lists_out.append({
            "id": p["id"], "field": p["field"], "level": p["level"],
            "title": p["title"], "main": main, "sub": sub, "goal": p["goal"],
            "n": len(allb), "nsteps": len(sts),
            "read": sum(1 for b in allb if b["prog"] > 0),
            "hue": allb[0]["hue"],
            "stages": sts,
        })
    print("书单卡 %d 张，共 %d 本" % (
        len(lists_out), sum(l["n"] for l in lists_out)))

    # pool 只输出前端渲染要用的字段，c1/c2/st/tFull 是算法中间量，不进 JSON
    pool_out = [{"s": p["slug"], "t": p["t"], "a": p["a"], "c": p["cat"],
                 "cv": p["cover"], "h": p["href"], "in": p["inPath"]}
                for p in pool]

    data = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "count": len(cards),
        "paths": paths_out,
        "pool": pool_out,
        "cards": cards,
        "lists": lists_out,
    }
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print("写出 %s  %.1f KB" % (a.out, os.path.getsize(a.out) / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
