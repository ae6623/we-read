# 微信读书 AI 数据入库：表结构、入口与盘点

> 最后更新：2026-10-28（82 本书盘点 + 兜底链路改造后）

## 1. 库文件

| 项 | 值 |
|---|---|
| 路径 | `data/we_read.db`（模块内 `weread_store.DB_PATH`） |
| 类型 | 单文件 SQLite，云端运行目录内 |
| 时区 | `CST`（UTC+8） |
| 写入方 | 本地脚本 / `weread_ai`；云端通过 `/api/ingest/*` 写入 |
| 读取方 | 通读页渲染（读库，库空时回退旧 JSON） |

模块 `weread_store.py` 收口读写；`data/ai_qa/*.json` 是**旧格式**（向后兼容回退用），
`data/overview/` 是网页端上传的 AI 大纲原稿（gitignore，仅本地）。

## 2. 表结构

### 2.1 `ai_qa` — AI 问书问答

```sql
CREATE TABLE ai_qa (
    book       TEXT NOT NULL,   -- 书名
    date       TEXT NOT NULL,   -- 日期 YYYY-MM-DD
    q          TEXT NOT NULL,   -- 问题
    a          TEXT,            -- 答案
    backfill   INTEGER NOT NULL DEFAULT 0,  -- 1=补录（非当日实时问书）
    asked_at   TEXT,
    at         TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (book, date, q)
);
```
按 `(book, date, q)` 幂等 upsert。`backfill` 区分「当日实时问书」与「事后补录」。

### 2.2 `quiz` — 读完自测 3 问的补答

```sql
CREATE TABLE quiz (
    book       TEXT NOT NULL,
    q          TEXT NOT NULL,
    a          TEXT,
    at         TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (book, q)
);
```
按 `(book, q)` 幂等 upsert，同一题只留最新答案。

### 2.3 `book_outline` — AI 大纲全文通读（已入库）

微信 AI 大纲 `outline.html` 内含章节要点与**原句摘录（第 4 层）**，是「全文通读」的一手数据。
已由 `gen_outline_full.py` 解析入库，通读页「章节导读」改从**完整数据**渲染（不再 `pts[:4]` / `picked[:2]` 截断）。

```sql
CREATE TABLE book_outline (
    slug      TEXT NOT NULL,    -- 站点 slug
    book      TEXT NOT NULL,    -- 书名
    ch_no     INTEGER NOT NULL, -- 章序（1 起）
    chapter   TEXT NOT NULL,    -- 章标题
    sec_no    INTEGER NOT NULL, -- 章内小节序号（0=无小节）
    sec       TEXT,             -- 小节标题（h4）
    point_no  INTEGER NOT NULL, -- 小节内要点序号
    point     TEXT,             -- 要点正文（<ul class="point"> 的 <b>）
    quote_no  INTEGER NOT NULL, -- 该要点下原句序号，0=无摘录
    quote     TEXT,             -- 原句摘录（第 4 层）
    updated_at TEXT NOT NULL,
    PRIMARY KEY (slug, ch_no, sec_no, point_no, quote_no)
);
CREATE INDEX idx_outline_book ON book_outline(book);
```

**渲染配额**（防单页 DOM 爆炸）：全书要点预算 500 条；每章配额按章节数动态定
（≤20 章 → 40 条/章，≤60 章 → 20 条，>60 章 → 8 条），超预算的章只留标题与「见 AI 大纲页」提示。
**库内始终是全量**，配额只作用于页面渲染。

## 3. 入库 / 读取入口

| 用途 | 入口 | 说明 |
|---|---|---|
| 写 AI 问书 | `weread_store.save_aiqa(book, items, date, backfill)` | 批量 upsert，返回条数 |
| 读 AI 问书 | `weread_store.load_aiqa(book, limit=6)` | 同问取最新，升序最多 limit |
| 写自测补答 | `weread_store.save_quiz(book, items)` / `weread_ai.save_quiz_items(title, qa_list)` | 后者会按 `ok` 过滤，**离线/兜底答案必须带 `ok=True`**，否则被静默丢弃 |
| 读自测补答 | `weread_store.load_quiz(book)` | 库空时回退 `weread_ai.load_quiz_items`（旧 JSON） |
| 写大纲全文 | `weread_store.save_book_outline(slug, book, chapters)` | 按 slug 先清后写，返回要点条数 |
| 读大纲全文 | `weread_store.load_book_outline(slug)` | 重建 `chapters` 结构（章→小节→要点→原句） |
| 统计 | `weread_store.counts()` | 每本书 qa / backfill / quiz 数，供 `/api/ingest/status` |
| 云端写入 | `web_app.py` 的 `/api/ingest/*`（令牌鉴权） | 本地不直连库文件 |
| 本机推送 | `cli.py` 的 `push-data` | 跑完自动推到云端 |
| 自测答案生成 | `gen_aiqa_from_outline.py` | 见 §4 |
| 大纲全文入库+渲染 | `gen_outline_full.py` | 见 §4.1 |


## 4. 自测答案生成与兜底链路（`gen_aiqa_from_outline.py`）

```
--mode auto    gemini 优先 → 逐题降级
                 ├─ gemini 有数据          → 用 gemini
                 └─ gemini 异常/无数据     → agent LLM 答案(merge) → 离线模板
--mode gemini  只调 gemini，不兜底（验证真实产出）
--mode offline 直接用离线模板（沙箱无出网时）
```

- agent LLM 兜底答案文件：`answers_fallback.json`（`{slug: [{q, a}]}`），8 本手工书。
- 沙箱实测：`generativelanguage.googleapis.com` 不可达（status 000），故沙箱内 `auto` 会落到兜底。
- 入库落盘：`save_local()` 写 JSON + SQLite（**必须带 `ok=True`**）。

### 4.1 大纲全文通读链路（`gen_outline_full.py`）

```
站点 outline.html（AI 大纲一手数据：章 / 小节 / 要点 / 原句摘录）
  → parse_full_outline()  章=details.ch；小节=div.sec(h4)；要点=ul.point>li>b；原句=ul.quote>li
  → save_local()          写 data/outline_full/<slug>.json + SQLite book_outline（全量）
  → inject()              替换 overview.html「章节导读」的 ch-body：
                          章节折叠 → 小节折叠（第一个默认展开），取消 pts[:4] / picked[:2] 截断
  → batch_publish()       多文件单次提交（REST；create_blob 节流 0.35s/次，约 3 req/s）
```

- **幂等要点**：章节区间用 `details` 标签**配对计数**定位（`_ch_item_spans`），不能用非贪婪正则——
  章节正文里的小节本身也是 `details`，非贪婪会在第一个小节闭合处截断，二次运行会把页面撑大。
- 沙箱实测（2026-10-28）：56 本 / 2783 章 / 23930 条要点入库；单页最大 432KB，全站 overview 9.2MB。
- 跳过 6 本：4 本大纲页无 `details.ch` 结构（解析为空），2 本通读页无「章节导读」区块。
- `overview_gen/build_overview.py` 已同步去掉截断，本机重新生成不会回退到精简版。

## 5. 82 本书盘点（站点 `we-read/reading-notes/books`）

| 数据 | 数量 / 82 | 缺口 |
|---|---|---|
| `outline.json`（章节目录结构，level/text/chapterUid） | 62 | 20 本缺 |
| `outline.html`（**微信 AI 大纲**，含要点+原句摘录） | 75 | 7 本缺 |
| `overview.html`（读前通读页） | 71 | 11 本缺 |
| 精读笔记 | **15 本 / 22 篇** | — |
| `*.epub` | 67 | 见 §6 |

### 落库现状

| 表 | 行数 | 覆盖 | 状态 |
|---|---|---|---|
| `quiz` | 168 | 56 本 × 3 问（占 71 本 overview 的 56 本） | 部分 |
| `ai_qa` | **0** | 无 | **完全缺失**（`data/ai_qa/` 下只有 56 个 quiz.json，无问书数据） |
| `book_outline` | 表不存在 | 0 | **未入库**（任务：通读增强） |

### 查漏补缺清单

1. **`ai_qa` 为空** —— 需确认 AI 问书数据是否有来源可回填；当前 `data/ai_qa/` 无任何问书 JSON。
2. **`quiz` 缺 15 本** —— 71 本 overview 中 56 本有补答，剩 15 本无「读完自测 3 问」区块（属范围内无此题，非遗漏）。
3. **AI 大纲全文未入库** —— 75 本 outline.html 的一手通读数据（要点+摘录）无表承接，且渲染被截断。
4. **通读页渲染截断** —— `build_overview.py` 每章仅渲染 4 条要点（`pts[:4]`）+ 2 条摘录（`picked[:2]`），
   AI 产出的一手数据被丢弃（如一地鸡毛 539 条条目、951 个大纲节点）。

## 6. epub 现状（实测）

| 检查 | 结果 |
|---|---|
| 文件总数 | 67 |
| zip 结构（mimetype + .opf） | **67/67 合格** |
| OPF manifest 引用完整性 | **67/67 完整**（阅读器可打开） |
| 正文纯文字量 | 抽样 2.0–3.9 万字（非空壳） |
| `outline.html` 中 epub 链接落地率 | **67/67 可落地，0 个指向缺失** |
| 线上实测下载 | `alaska-qingyouji-ai-notes.epub` → HTTP 200，`application/epub+zip` |
| 唯一坏点 | `index.html` 中 `books/norway-night/collection.epub` → **404**（`norway-night` 整目录不存在，孤儿条目） |

## 7. 环境注意

- 沙箱到 **github.com（git 协议）不通**（port 443 超时），但 **api.github.com（REST）可达**。
  因此在沙箱内提交代码需用 `gh_api`（REST）而非 `git push`。
- 云端沙箱更新代码走 `zip_pull.py` 的 `local` 模式（`vendor/weread-auto.zip`）。
