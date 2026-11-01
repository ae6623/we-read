# add-ai-lead-merged-v3

## Why

2026-11-02 用户审阅《一生的读书计划》「通读·精读 合并版」第二版后提出 8 条修改意见（对应合并页 + 生成器 `merged_guide` 模块）：

1. 一句话主旨是「共 70 章、折成 10 段主干」这类结构描述，对人类没用；主旨应是回答「这本书讲什么」的内容句（AI 问答口径）。
2. 「全书骨架 · 章节导读 · 全书篇目（含 AI 大纲全文）」模块标题太长，改为 **AI领读**。
3. 模块内「全书篇目（AI 大纲顺序）」分组副标题多余，去掉。
4. 章 summary 后的「未读」徽标多余，去掉。
5. 用户判断「没有合并 AI 大纲进来」——因为合并版用的是 mmx 重渲染样式，而 AI 大纲页（outline.html）原生样式（绿标题 / 加粗要点 / 金色竖线原句）更好看。应直接内嵌 outline.html 原生目录与章节树，样式与大纲页完全一致。
6. 「迁移与行动」「复习与记忆复利」两个模块不需要，去掉。
7. 「全书思考 3 问」只出题不出答案（aiqa 库无数据时 `_quiz_answers_html` 返回空）。要求输出时直接带答案：aiqa 无数据则由 LLM 基于大纲撰写并随页面输出（数据回填，同 `add-ai-qa-manual-backfill` 先例）。
8. 「核心观点初判」列表项前缀「观点 1 / 观点 2 / …」（`.mmx-views li:before` 计数器）不需要。

## What Changes

### 生成器（we-read-auto / engine/overview_gen）

- `build_overview.py`
  - 新增 `_extract_outline_tree(outline_html)`：从 AI 大纲 HTML 抽取原生 `<div class="toc">` 目录 + 全部顶层 `<details class="ch">` 章节树（括号配对，非正则截断）。
  - `_m_merged_guide` 升级 v3：标题改「AI领读」；有 outline 原文时**直接内嵌原生 toc + 章节树**（样式与大纲页一致，天然无「未读」徽标、无分组副标题）；无 outline 原文时回退到 `_render_full_guide_inner` 结构化渲染（保留 v2 能力，不丢兜底）。
  - `build_modular` 新增 `outline_html=""` 参数；`_Ctx` 增加 `outline_tree` 字段。legacy `build()` 不动。
  - `quiz-ans` 标题文案「AI 补答（微信读书 Ai 问书）」→「AI 补答（AI 问书）」（站内不出现第三方平台名规范）。
- `auto.py`：`generate()` 命中 `MODULES_OVERRIDE` 时把 `outline.html` 原文传入 `build_modular(outline_html=…)`；其余书仍走 `build()` 零变化。
- `books.py`：新增 `MANUAL_QUIZ_ANSWERS`（按 slug 存 LLM 撰写的 3 问答案），作为 aiqa 库无数据时的回填数据源。
- `cli.py`：`_load_aiqa_data` 的 quiz 链路改为「SQLite/JSON 库 → `MANUAL_QUIZ_ANSWERS`（按 title 或 slug）」两级回退。

### 合并演示页（build_combined_yisheng.py → yi-sheng-combined.html 第三版）

- 「AI领读」模块内嵌 outline 原生树 + 内联 `reading-outline.css`（36 行，置于外壳样式之前避免覆盖）。
- 一句话主旨替换为内容主旨句（AI 问答口径，回答「这本书讲什么」，而非结构统计）。
- 模块顺序调整：去 `thesis`（已去）、去 `action`、去 `memo`；保留 quiz 并注入 `MANUAL_QUIZ_ANSWERS` 答案。
- 删除内联 CSS 中 `.mmx-views li:before` 的「观点 N」计数器规则。
- 全局 `微信读书→AI 读书`、`微信→AI` 替换保留。

## 影响 / 边界

- 仅 yi-sheng 走 `MODULES_OVERRIDE` → `merged_guide`；其它书仍走 legacy `build()`，零影响；回退只需删 `books.py` 的 `MODULES_OVERRIDE` 一行。
- 「AI 大纲页 outline.html」本身不动，站点仍是独立页。
- openspec 记录于本 change（we-read 仓 `openspec/changes/add-ai-lead-merged-v3/`）。
