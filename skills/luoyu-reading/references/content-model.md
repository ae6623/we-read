# 内容模型与迁移方案（content-model）

> 目标：把散落在静态 HTML 里的内容抽成**结构化数据**，为"web 程序 + 数据库读取"铺路；
> 同时明确哪些内容属于「AI 大纲」、哪些是「文本」、哪些是「静态展示（不用改 HTML）」。
> 配套提取脚本：`scripts/extract_content.py`；产出目录：`_data/books/<slug>.json`。
> 与 [frontend-conventions.md](frontend-conventions.md)（禁内联 CSS、共享样式表）互补：
> 前者管**表现层**，本文管**数据层**。

## 一、三类内容（先分类，再迁移）

| 类别 | 载体 | 性质 | 迁移方式 |
|------|------|------|----------|
| **AI 大纲** `ai_outline` | `outline.json`（AI读书官方结构：扁平 `{level:1–4, text, uiIdx, range, chapterUid}`）+ `outline.md` / `.epub` / `.html` | **已是结构化数据**（level1=章、2=节、3=要点、4=原句摘录） | 直接入库为 `outline_nodes` 表；HTML 是它的渲染产物，可弃 |
| **文本** `text` | `overview.html`（全书视角）、`final.html`（精读/AI阅读汇编）、`notes/YYYY-MM-DD.html`（日期笔记） | 正文是规整的 `<section aria-labelledby><h2>…` 结构，元信息在 `<header>` | 抽成 `{header, sections:[{id,heading,html}]}`，保真存 HTML 片段 |
| **静态展示** `static` | `nav` / `footer` / `assets/css/*` / 首页卡片与索引 / `books/*/index.html` | 纯展示、无内容语义 | **模板渲染，不手改页面**；改样式只动共享 CSS，改卡片只动数据源（见下） |

> 「不用改 HTML 的」= 第三类。当前它由共享 CSS（已外置）+ 模板承担；迁移后由 web 程序的
> 布局模板（Jinja2 等）统一渲染，页面里不再有手写内容。

## 二、每书 JSON schema（`_data/books/<slug>.json`）

```jsonc
{
  "schema_version": 1,
  "slug": "1984",
  "book": { "title": "1984", "author": "[英] 乔治·奥威尔", "meta_line": "...", "series": null },
  "ai_outline": {
    "source": "outline.json",
    "node_count": 1001,
    "level_counts": { "1": 25, "2": 88, "3": 192, "4": 696 },
    "artifacts": { "markdown": "outline.md", "epub": "outline.epub" }
  },
  "texts": {
    "overview": {
      "file": "overview.html", "eyebrow": "...", "title": "1984", "meta_line": "...",
      "header_html": "<div class=\"card\">…</div>",
      "sections": [ { "id": "chapter-guide-title", "heading": "章节导读 · 初版", "html": "…" } ]
    },
    "final": null,
    "notes": [ { "date": "2026-10-22", "file": "2026-10-22.html", "title": "…", "sections": [ … ] } ]
  }
}
```

设计取舍：
- **正文存 HTML 片段而非 markdown**：`tag / card / details / blockquote` 等语义都要保真，转 markdown 会丢结构；web 程序直接注入片段即可，无损。
- **`nav` / `footer` 不入 JSON**：它们是静态展示层，由模板渲染。
- **outline 不再解析 HTML**：`outline.json` 就是真相，避免二次解析出错。
- **outline 节点不内联进 `_data` JSON**：nodes 本体留在 `outline.json`，入库时单独导入 `outline_nodes` 表；
  否则 58 本 × ~800 条重复一遍会让 `_data` 从 2.1MB 膨胀到 23MB（实测），纯属冗余。

## 三、数据库表设计（迁移目标）

```sql
-- 书目
CREATE TABLE books (
  slug TEXT PRIMARY KEY, title TEXT, author TEXT, series TEXT,
  status TEXT,              -- preview | reading | done
  meta_line TEXT, word_count INTEGER,
  weread_url TEXT, douban_url TEXT,
  created_at TEXT, updated_at TEXT
);

-- AI 大纲节点（来自 outline.json）
CREATE TABLE outline_nodes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT REFERENCES books(slug),
  level INTEGER, text TEXT, ui_idx TEXT, range TEXT,
  chapter_uid INTEGER, chapter_title TEXT, sort_order INTEGER
);

-- 文本分节（overview / final）
CREATE TABLE sections (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT REFERENCES books(slug),
  doc_type TEXT,            -- overview | final
  section_id TEXT, heading TEXT, html TEXT,
  header_html TEXT, sort_order INTEGER
);

-- 日期笔记
CREATE TABLE notes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT REFERENCES books(slug),
  note_date TEXT, title TEXT, html TEXT, sections_json TEXT,
  created_at TEXT
);

-- 附件（epub / md）
CREATE TABLE assets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT REFERENCES books(slug), kind TEXT, path TEXT
);
```

索引建议：`outline_nodes(slug, sort_order)`、`sections(slug, doc_type, sort_order)`、`notes(slug, note_date)`、全文检索（SQLite FTS5 / Postgres tsvector）建在 `sections.html`、`outline_nodes.text`、`notes.html` 上——这是"从数据库读取"最直接的收益（站内可搜索）。

## 四、迁移三步（渐进，不破坏现有线上）

**Step 1 · 抽数据（现在）**
```bash
python3 scripts/extract_content.py --all      # → _data/books/*.json
```
不改任何 HTML，纯新增。JSON 是**快照/种子**，线上仍是静态站。

**Step 2 · 校验无损**
用 JSON 重新渲染一份「影子 HTML」，与现 HTML 做文本与结构比对（section 数、heading、正文长度、关键语句）。
全绿才进入下一步；有差异按 `slug/doc_type` 修脚本或标例外。

**Step 3 · 入库 + 上程序**
1) `_data/books/*.json` 批量导入 SQLite（后续可换 Postgres）；
2) 起 web 程序（Flask/FastAPI + Jinja2），模板复用 `assets/css/*`（已外置，直接可用）；
3) 路由映射：`/book/<slug>/overview`、`/book/<slug>/outline`、`/book/<slug>/final`、`/book/<slug>/notes/<date>`；
4) 首页/索引由 `books` 表 + 共享卡片模板渲染，**不再手写卡片 HTML**；
5) GitHub Pages 静态站：迁移期双跑，稳定后改为"从 DB 导出的静态快照"或直接下线。

## 五、维护规则（防退化）

1. **单一真相**：迁移前 HTML 是真相、JSON 是快照 → 内容 agent 改完 HTML 后**必须重跑** `extract_content.py`；
   迁移后 DB 是真相、HTML 是渲染产物。
2. **禁止在 HTML 里手写重复内容**：卡片、导航、索引一律由数据 + 模板生成。
3. **样式改动只动 `assets/css/*`**（见 frontend-conventions.md）。
4. **新增一本书** = 新增 `reading-notes/books/<slug>/`（overview/outline/final/notes）+ 跑一次提取；
   首页卡片由 `_data` 自动生成，不手改 `index.html`。
5. 与内容 agent 协作：`_data/*` 与 `scripts/extract_content.py` 由 **frontend-mod** 认领；
   内容 agent 负责 `<slug>` 目录下的 HTML 与 `outline.json`。改前走 [frontend-a2a.md](frontend-a2a.md)。
