#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全量书卡总索引（逐本列出书名 + 站点网址）的生成与上传。

背景
----
ima_export.py 原本生成的 00-总索引.md 是「小而精」版：每类只列 4 本代表，
整页只有首页地址，没有每本书的网址。这里改成全量逐本带网址，并拆成
可独立运行的单元——刷索引不必重渲 523 张卡。

IMA 的硬限制（务必先读）
------------------------
MCP 只暴露 create_media / add_knowledge，没有 delete / update：
  - 同名再传 → DUPLICATE_NAME_STRATEGY_SAVE 会生成 `xxx_时间戳.md` 副本；
  - 用 REPLACE → 服务端清空旧条目另立，留下「当前内容已删除」空壳
    （2026-11-14 批量踩过，512 条里 328 条中招），已永久禁用。
因此更新已有索引只能：用户在 App 删除旧文件 → 再传同名的干净版。
本脚本默认落库名 `00-总索引·全量网址.md`（与旧精简版不重名，可直接落库），
清理旧副本的办法见 scripts/ima/README.md。

用法
  python3 scripts/ima/ima_index.py                        # 生成本地 ima/00-总索引.md
  python3 scripts/ima/ima_index.py --check               # 生成 + 抽样校验网址可达
  python3 scripts/ima/ima_index.py --upload              # 生成 + 上传到 IMA 根目录
  python3 scripts/ima/ima_index.py --upload --name 00-总索引.md   # 删旧文件后用原名重传
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[2]
IMA_DIR = ROOT / "ima"
MANIFEST = IMA_DIR / "manifest.json"
INDEX_FILE = IMA_DIR / "00-总索引.md"
SITE = "https://reader.js-dev.cn"
DEFAULT_UPLOAD_NAME = "00-总索引·全量网址.md"

# 常用类目优先，其余按字典序补在后面
ORDER = ["文学", "历史", "社会文化", "哲学宗教", "艺术", "人物传记", "精品小说",
         "政治军事", "经济理财", "计算机", "个人成长", "科学技术", "生活百科",
         "教育学习", "心理", "漫画", "男生小说", "其他"]


def book_rows(cards: dict) -> list[dict]:
    """manifest.cards -> 有效书卡列表。

    台账里有 532 条，其中约 9 条是去重合并掉的 / 归档无卡的（没有 file 字段），
    过滤掉正好是站点实际产出的 523 张卡，与 ima_export.py 的 ok 列表一致。
    """
    rows = []
    for slug, e in cards.items():
        if not e.get("file") or e.get("duplicate_of"):
            continue
        title = (e.get("title") or "").strip().strip("《》").strip()
        if not title:
            continue
        rows.append({
            "slug": slug,
            "title": title,
            "cat1": (e.get("cat1") or "其他").strip() or "其他",
            "url": f"{SITE}/reading-notes/books/{slug}/combined.html",
        })
    return rows


def build_index(cards: dict, today: str = "") -> str:
    """单一真相源：导出器与独立脚本都调这个函数，避免两份索引格式漂移。"""
    rows = book_rows(cards)
    cats: dict[str, list[dict]] = {}
    for r in rows:
        cats.setdefault(r["cat1"], []).append(r)

    order = [c for c in ORDER if c in cats]
    order += sorted(set(cats) - set(order))
    today = today or datetime.now().strftime("%Y-%m-%d")

    lines = [
        "# we-read 书卡总索引",
        "",
        f"> {len(rows)} 本｜{len(cats)} 个类目｜更新 {today}｜整站 {SITE}",
        "",
        "每本书在 IMA 里对应一张书卡，文件名 `<类目>·<书名>.md`。",
        "下面**逐本列出书名与站点详情页网址**（combined.html：含章节知识导图，可展开、可放大）。",
        "网址可直接复制到浏览器打开；每张书卡顶部「站点原文」字段指向同一地址。",
        "",
    ]
    for c in order:
        rs = sorted(cats[c], key=lambda x: x["title"])
        lines.append(f"## {c}（{len(rs)} 本）")
        lines.append("")
        for r in rs:
            lines.append(f"- 《{r['title']}》 — {r['url']}")
        lines.append("")
    lines += [f"合计 {len(rows)} 本。", ""]
    return "\n".join(lines)


def generate(today: str = "") -> tuple[str, list[dict]]:
    cards = json.loads(MANIFEST.read_text("utf-8"))["cards"]
    md = build_index(cards, today)
    INDEX_FILE.write_text(md, "utf-8")
    rows = book_rows(cards)
    return md, rows


def check_urls(rows: list[dict], n: int = 12) -> tuple[int, int, list]:
    """校验网址可达，避免索引里出现死链。n=0 表示全量（523 本）。"""
    import random
    import requests
    from concurrent.futures import ThreadPoolExecutor

    sample = rows if n == 0 else random.Random(20261114).sample(rows, min(n, len(rows)))
    s = requests.Session()

    def one(r):
        try:
            # 站点对 HEAD 可能不给 200，用 GET + stream 只取状态码，不下载正文
            resp = s.get(r["url"], timeout=15, allow_redirects=True, stream=True)
            code = resp.status_code
            resp.close()
            return r["slug"], code
        except Exception as ex:
            return r["slug"], str(ex)[:60]

    with ThreadPoolExecutor(max_workers=16) as ex:
        out = list(ex.map(one, sample))
    bad = [(slug, code) for slug, code in out if code != 200]
    # 全量时只打失败项，避免刷屏
    for slug, code in (bad if n == 0 else out):
        print(f"  {'✓' if code == 200 else '✗'} {code}  {slug}")
    return len(out) - len(bad), len(out), bad


def upload(name: str) -> str:
    """上传到 IMA 根目录。已有同名则拒绝（SAVE 会生成时间戳副本）。"""
    import ima_client as ima
    import ima_upload as up

    ima.init()
    kb = up.resolve_kb()
    have = up.folder_titles(kb, "")            # 根层；已修 folder_titles 对 "" 失效的问题
    if name in have:
        raise SystemExit(
            f"根目录已有「{name}」。IMA 没有更新接口，同名再传会生成 _时间戳 副本；\n"
            f"请先在 App 删除旧文件再跑，或换一个 --name。")
    r = up.upload_one(kb, "", INDEX_FILE, replace=False, file_name=name)
    return r["media_id"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="抽样校验网址可达（12 本）")
    ap.add_argument("--check-all", action="store_true", help="全量校验所有网址")
    ap.add_argument("--upload", action="store_true", help="上传到 IMA 根目录")
    ap.add_argument("--name", default=DEFAULT_UPLOAD_NAME, help="落库文件名")
    args = ap.parse_args()

    md, rows = generate()
    cats = len({r["cat1"] for r in rows})
    print(f"索引 → {INDEX_FILE}")
    print(f"  {len(rows)} 本｜{cats} 个类目｜{len(md.encode('utf-8')) / 1024:.1f} KB"
          f"｜网址行 {sum(1 for l in md.splitlines() if l.startswith('- 《'))} 条")

    if args.check or args.check_all:
        print("全量校验网址：" if args.check_all else "抽样校验网址：")
        ok, total, bad = check_urls(rows, 0 if args.check_all else 12)
        print(f"  可达 {ok}/{total}")
        if bad:
            print("  非 200 明细：")
            for slug, code in bad:
                print(f"    {code}  {slug}")
        if ok != total:
            return 1

    if args.upload:
        mid = upload(args.name)
        print(f"已上传 → {args.name}  media_id={mid[-16:]}")
        print("提示：IMA 解析是异步慢队列，稍等 media_state=2 后即可在库内搜到。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
