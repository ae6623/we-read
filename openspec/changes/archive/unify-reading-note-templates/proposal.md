## Why

阅读笔记的「模板文本」——精读页章节名、通读页反思题标题与题面、AI 出题默认题面——目前**散落在三个文件里，且没有任何单一真源**：

| 模板 | 所在位置 | 现状 |
|------|----------|------|
| 精读章节名 | `gen_mindmap.py` `_chapter_html` | 直接输出 `c["title"]`，无兜底 |
| 反思题标题 | `overview_gen/build_overview.py:321`、`:398` | 硬编码「读完自测 3 问」 |
| 反思题题面 | `overview_gen/auto.py:250-253` | 硬编码「大纲共列出多少章节条目」那套 |

由此产生两个已发生的后果：

**一、修了内容，没修生产，下次一跑就回退。** 2026-10-30 至 11-01 已对**已发布的 148 篇 `overview.html`** 做过两轮手工回填（「读完自测 3 问」→「全书思考 3 问」、31 篇坏默认题换成高维 3 问）。但云端真正运行的生产代码在站点仓根目录，本轮实测仍是旧版：

- `overview_gen/auto.py:250-253` —— 仍是「本书 AI 大纲共列出多少章节条目？/第一章最让你意外…/合上本页…」这套章节条目级题面
- `overview_gen/build_overview.py:321`、`:398` —— 仍渲染 `<h2>读完自测 3 问</h2>`
- `gen_mindmap.py` —— 无任何章名派生逻辑

上一轮改的是 `we-read-auto` 的 artifact 副本，**云端不读那份**。等于只擦了地板没关水龙头：下一次 `weread_daily.py` 跑一遍，新页与重跑页会全部回到旧模板。

**二、精读页章节只有序号，没有标题。** 线上实测存在章名为纯序号的书：

- `bai-yin-shi-dai`（白银时代）22 章只显示「一/二/三…」
- `zhui-yi-shi-shui-nian-hua--quan-ji-`（追忆似水年华全集）9 章只显示「第一部/第二章…」

而这些章下面的**首个小节其实有真实标题**（如「作者对艺术家的印象和舅舅的艺术家生涯」）。根因是 outline 解析阶段把章名退化成了序号，渲染器又没有兜底，于是页面上只剩编号。

## What Changes

- **新增 `reading_note_spec.py`（仓库根）**，作为笔记页模板的**单一真源**：
  - `REFLECT_TITLE`（反思题区块标题）
  - `REFLECT_QUESTIONS`（高维通用 3 问）
  - `REFLECT_NOTE`（题面说明）
  - `is_placeholder_title()` / `chapter_title()`（章名兜底派生）
- **`gen_mindmap.py`**：`_chapter_html` 改用 `chapter_title(c, full)` 渲染 `mmx-name`，不再直出 `c["title"]`
- **`overview_gen/build_overview.py`**：`:321`、`:398` 两处 quiz 区块标题改为引用 `REFLECT_TITLE`
- **`overview_gen/auto.py`**：`:250-253` 默认题面改为由 `REFLECT_QUESTIONS` 生成
- **存量回填**：全库 `mindmap.html` 中判定为占位章的 `mmx-name`，按同一 `chapter_title` 规则就地补标题（幂等，只增不改）
- **新书生产**：按「扫描书架 → 过滤已产出 → 产出四件套」执行一轮，**剔除公众号**

## Impact

- Affected specs: `reading-note-templates`（新建）
- Affected code: `reading_note_spec.py`（新增）、`gen_mindmap.py`、`overview_gen/build_overview.py`、`overview_gen/auto.py`
- 数据结构：**无变化**，仅渲染文本；`data/mindmap/*.json`、`data/outline/*` 均不改 schema
- 向后兼容：已发布页不重跑则原样保留；重跑/回填后章名与题面统一
- 发布口径：模板改动落在站点仓源码，云端下一次生成即生效；存量回填一次性执行，走 `contents` API 带 sha 直传，保留正文
- Out of scope：
  - `reading-notes/books/*/notes/*.html` 单篇笔记页的 AI 追问区块模板（不在本次收敛范围）
  - 公众号文章（本就不产出四件套，仅在扫描阶段显式剔除）
