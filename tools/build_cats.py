#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重建 assets/data/book-cats.json（slug -> [一级类目, 二级类目]）

为什么要有这个脚本
------------------
首页权重（assets/data/weights.json）按类目决定「文化置顶 / 计算机沉底」，
前提是每本书都有可靠类目。旧的 book-cats.json 只有 301 条，而首页已有
539 本，缺口的书权重全落空，等于权重系统只对一半书生效。

数据来源（按优先级）
  1) 云端 /api/books —— weread 书架全量，自带 cat_l1 / cat_l2，按书名归一化匹配
  2) 关键词启发式 —— 覆盖云端没有的书（本地 PDF 导入、套装拆册、轻游记 23 册）
  3) 兜底「其他 / 未分类」

用法
  python3 tools/build_cats.py              # 拉云端并写文件
  python3 tools/build_cats.py --offline    # 只用 .cache/cloud-books.json
  python3 tools/build_cats.py --dry-run    # 只打印分布，不落盘
"""
import argparse
import json
import os
import re
import sys
import urllib.request
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "tools", ".cache", "cloud-books.json")
OUT = os.path.join(ROOT, "assets", "data", "book-cats.json")
CLOUD = "https://weread-cloud-probe.app.workbuddy.host/api/books"
AGENT = "workbuddy-cloud-luoyuJi"

# ── 关键词规则：顺序即优先级 ────────────────────────────────────────
# 先判计算机（技术书必须沉底，误判成文化会顶到首屏），再轻游记，
# 再经济理财（「货币战争」含「战争」，必须早于文化判），最后文化。
RULES = [
    ("计算机", "编程开发", [
        "java", "javascript", "typescript", "python", "golang", "rust", "c++", "kotlin",
        "spring", "netty", "kubernetes", "docker", "k8s", "elasticsearch", "rocketmq",
        "dubbo", "service-mesh", "redis", "mysql", "sql", "linux", "git", "vue", "react",
        "node", "apache", "tomcat", "nginx",
        "程序员", "编程", "代码", "算法", "并发", "分布式", "微服务", "架构", "数据库",
        "缓存", "中间件", "操作系统", "数据结构", "计算机网络", "机器学习", "深度学习",
        "人工智能", "神经网络", "前端", "后端", "运维", "重构", "高可用", "可伸缩",
    ]),
    ("文学", "游记", ["qingyouji", "轻游记"]),
    ("经济理财", "投资", [
        "投资", "理财", "金融", "货币", "股票", "基金", "财报", "估值", "期权",
        "保险", "银行", "商业", "创业", "交易", "期货", "债务", "通胀", "经济",
        "财富", "市场", "楼市", "房价", "资产", "华尔街", "大危机",
    ]),
    ("历史", "历史读物", [
        "史", "战争", "帝国", "革命", "文明", "王朝", "罗马", "希腊", "拜占庭", "明治",
        "冷战", "二战", "一战", "阿富汗", "中东", "近代", "民国", "古代", "历史",
    ]),
    ("文学", "文学", [
        "小说", "诗", "散文", "随笔", "文集", "全集", "选集", "译丛", "传记", "自传",
        "回忆录", "纪实", "文学", "故事", "诗词", "合集", "典藏", "阿勒泰",
    ]),
    ("社会文化", "社会", [
        "文化", "社会", "哲学", "宗教", "艺术", "美学", "法治", "法律", "政治", "人类",
        "自由", "思想", "伦理", "心理",
    ]),
]

CN = "《》「」·,，.。:：；;！!？?（）()[]【】\"'“”‘’—-…"


def norm(s):
    s = str(s or "").lower()
    return "".join(ch for ch in s if ch not in CN and not ch.isspace())


try:  # 拼音匹配是可选项：装了就多认一批「标题本身是拼音」的自传书
    from pypinyin import lazy_pinyin

    def py(s):
        return "".join(lazy_pinyin(str(s or "")))
except Exception:  # pragma: no cover
    def py(s):
        return ""


def fetch_books():
    req = urllib.request.Request(CLOUD, headers={"X-Agent-Name": AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read().decode("utf-8"))
    books = data.get("books") or []
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(books, f, ensure_ascii=False)
    return books


def load_books(offline):
    if offline:
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    try:
        return fetch_books()
    except Exception as e:  # 网络失败就退回缓存，别让权重系统断炊
        print("云端拉取失败(%s)，退回缓存" % e, file=sys.stderr)
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)


def index_cards():
    """从 index.html 抓 (slug, 书名)：卡片标题比 data-search 干净，后者带章节噪声。"""
    with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as f:
        h = f.read()
    out = {}
    for m in re.finditer(r'<article[^>]*data-slug="([^"]+)"[^>]*>(.*?)</article>', h, re.S):
        slug, body = m.group(1), m.group(2)
        t = re.search(r'class="card-title-link"[^>]*>(.*?)</a>', body, re.S)
        title = re.sub(r"<[^>]+>", "", t.group(1)).strip() if t else ""
        if slug not in out or (not out[slug] and title):
            out[slug] = title
    return out


def guess_from_text(slug, title):
    hay = norm(slug) + " " + norm(title)
    # 标题本身是拼音的书（本地导入的 PDF／套装拆册）只能靠 slug 的拼音串认，
    # 只对 >=4 字母的词做拼音匹配，避免「史→shi」「诗→shi」这类单字误伤。
    slug_py = norm(slug)
    for cat1, cat2, words in RULES:
        for w in words:
            nw = norm(w)
            if not nw:
                continue
            if nw in hay:
                return [cat1, cat2], w
            pw = py(w)
            if len(pw) >= 4 and pw in slug_py:
                return [cat1, cat2], w + "~py"
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cloud = load_books(args.offline)
    cards = index_cards()

    by_norm, by_title_list = {}, []
    for b in cloud:
        k = norm(b.get("title"))
        if not k:
            continue
        cat = [b.get("cat_l1") or "", b.get("cat_l2") or ""]
        # 云端自己也有一批「未分类」，别让它挡住后面的关键词兜底
        if not cat[0] or cat[0] in ("未分类", "其他"):
            continue
        by_norm.setdefault(k, cat)
        by_title_list.append((k, cat))

    books, titles = {}, {}
    stat = Counter()
    unresolved = []

    for slug, title in cards.items():
        k = norm(title)
        cat = by_norm.get(k) if k else None
        src = "cloud"
        if not cat and k:
            for ck, ccat in by_title_list:
                if len(ck) >= 3 and (ck in k or k in ck):
                    cat, src = ccat, "cloud~"
                    break
        if not cat:
            cat, word = guess_from_text(slug, title)
            src = "rule:" + str(word) if cat else "none"
        if cat and cat[0] and cat[0] not in ("未分类", "其他"):
            books[slug] = cat
            stat[cat[0]] += 1
            if k:
                titles[k] = cat
        else:
            books[slug] = ["其他", "未分类"]
            stat["其他"] += 1
            unresolved.append((slug, title))

    payload = {
        "built_at": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": "weread /api/books + 标题关键词启发式",
        "note": "books: slug -> [一级, 二级]; titles: 归一化书名 -> [一级, 二级]。"
                "由 tools/build_cats.py 生成，勿手改。",
        "stats": dict(stat.most_common()),
        "books": dict(sorted(books.items())),
        "titles": dict(sorted(titles.items())),
    }

    print("卡片 slug 总数:", len(cards))
    print("类目分布:", dict(stat.most_common()))
    print("未分类:", len(unresolved))
    for s, t in unresolved[:20]:
        print("   -", s, "|", t)

    if args.dry_run:
        return
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("写入", OUT, os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    main()
