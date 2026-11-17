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
    count / paths / cards[]
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
    sib      同阶段其余书在 cards 里的下标（最多 3 个）

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
OUT = os.path.join(ROOT, "channel", "cards.json")
COVER = "https://cdn.js-dev.cn/assets/covers/%s.jpg"

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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-color", action="store_true")
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
        # 先取本阶段其余书，不够 3 个再从同书单其他阶段顺位补
        for si, group in enumerate(stage_slugs):
            others = [x for s2 in range(len(stage_slugs)) if s2 != si for x in stage_slugs[s2]]
            for idx in group:
                same = [x for x in group if x != idx]
                fill = [x for x in others if x != idx]
                cards[idx]["sib"] = (same + fill)[:3]

    for i, c in enumerate(cards, 1):
        c["i"] = i
        c["pi"] = sum(1 for x in cards[:i] if x["p"] == c["p"])
        c["hue"] = fallback_hue(c["slug"])

    print("cards=%d  unique=%d" % (len(cards), len(seen)))

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
        "id": p["id"], "field": p["field"], "level": p["level"],
        "title": p["title"], "goal": p["goal"],
        "n": sum(1 for c in cards if c["p"] == p["id"]),
    } for p in paths]

    data = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "count": len(cards),
        "paths": paths_out,
        "cards": cards,
    }
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print("写出 %s  %.1f KB" % (a.out, os.path.getsize(a.out) / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
