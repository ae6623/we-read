> 执行规则：每完成一项立刻勾选 `[x]`；做不到写 `[!]` 并附原因。

## 1. 生成器（we-read-auto / engine/overview_gen）

- [x] 1.1 `build_overview.py` 新增 `_extract_outline_tree(outline_html)`：括号配对抽取 toc div + 全部顶层 `details.ch`
- [x] 1.2 `_Ctx` 增加 `outline_tree` 字段；`build_modular` 新增 `outline_html=""` 参数并装配
- [x] 1.3 `_m_merged_guide` v3：标题「AI领读」；有原生树则内嵌，否则回退 `_render_full_guide_inner`
- [x] 1.4 `quiz-ans` 文案去平台名：「AI 补答（微信读书 Ai 问书）」→「AI 补答（AI 问书）」
- [x] 1.5 `auto.py` `generate()`：`build_modular` 路径传入 `outline_html`
- [x] 1.6 `books.py` 新增 `MANUAL_QUIZ_ANSWERS['yi-sheng-de-du-shu-ji-hua']`（LLM 撰写 3 问答案）
- [x] 1.7 `cli.py` `_load_aiqa_data`：quiz 空时回退 `MANUAL_QUIZ_ANSWERS`（title/slug 双键）
- [x] 1.8 回归：默认模块路径 `build_modular(默认)` 与 legacy `build()` 逐字节一致

## 2. 合并演示页（build_combined_yisheng.py → 第三版）

- [x] 2.1 内联 `reading-outline.css`（置于外壳样式前）+ 传入 `outline_html` 内嵌原生树
- [x] 2.2 一句话主旨替换为内容主旨句（AI 问答口径，非结构统计）
- [x] 2.3 模块调整：去 `action`、`memo`；quiz 注入 `MANUAL_QUIZ_ANSWERS` 答案
- [x] 2.4 删除内联 CSS `.mmx-views li:before`「观点 N」计数器规则
- [x] 2.5 全局 `微信读书→AI 读书`、`微信→AI` 替换保留并校验为 0

## 3. 校验

- [x] 3.1 AI领读：`details.ch`=70、无「未读」徽标、无「全书篇目（AI 大纲顺序）」、toc 锚点保留
- [x] 3.2 quiz：3 问均带答案（`quiz-ans` 块 3 条 `aiqa-item`）
- [x] 3.3 全页无「观点 N」计数器渲染、无 `action/memo/thesis` 模块
- [x] 3.4 部署补丁重建并通过 `git apply --check`
