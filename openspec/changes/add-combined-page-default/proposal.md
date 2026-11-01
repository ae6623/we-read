# 合并页（通读 + 精读）成为站点默认读书页

## Why

《一生的读书计划》上验证完成的合并渲染方式（AI领读 = 章节目录 + 骨架 + AI 大纲融合树，
外加精读模块与全书思考 3 问）被确认优于现有的 overview（通读）/ mindmap（精读）分页：
读者点开卡片要在一页里拿到「这本书讲什么 + 全书面貌 + 精读判断」，分着看要来回跳。

线上 344 本书仍停在旧分页，卡片默认进 overview.html。需要把这套渲染做成**默认模板**，
并让所有书补齐，卡片点击进入新页面。

## What Changes

- 新增 `overview_gen/combine_page.py`：只读现成的 mindmap.html（精读）与 outline.html（AI 大纲），
  产出 `combined.html`。不修改任何既有页面文件。
- `produce_all.gen_one()` 在写完 outline/overview/mindmap/quiz 之后追加一步产出 combined.html，
  失败只告警、不影响其它页面（try/except 包住）。
- `link_index.py` 新增 `entry_page(slug)`：卡片标题链接优先 combined.html，缺失回退 overview.html。

## 模块装配（配置驱动，改顺序只改 ORDER_HEAD / ORDER_TAIL）

svg（结构导图，置顶）→ oneline（一句话主旨）→ merged_guide（AI领读）→
精读其余模块（保持各书自然顺序）→ quiz（读完自测，通读侧）。

## 降级策略（绝不硬产空壳）

| outline.html 形态 | AI领读渲染 |
|---|---|
| 完整 AI 大纲（details.ch + .sec/.point/.quote） | 融合树：目录 + 骨架 + 要点 + 原句（含「原句 · 本小节汇总」节点） |
| 简版章级目录（div.ch，无要点/原句） | 全书篇目列表 + 说明「大纲补全后自动升级」 |
| 全书视角笔记整理版（toc + section） | 原样收进 AI领读 |
| 缺 outline / 缺 mindmap | 不产 AI领读 / 不产页面（卡片回退 overview.html） |

全书思考 3 问：**无答案不出该模块**（不留只问不答的留白）。

## Impact

- 新增产出：每本书 combined.html（339 本实测 ok，0 失败，合计约 31 MB）。
- 老页面 overview.html / mindmap.html / outline.html 全部保留，不删除、不覆盖。
- 卡片默认入口改为 combined.html（回退机制保证不死链）。

## Decision（2026-11-02 定稿）

- **老页全保留**：`overview.html`（通读）、`mindmap.html`（精读）、`outline.html`（AI 大纲）
  继续生成、继续发布、继续留在入口抽屉与卡片里。合并页是**新增页**，不是替换页。
- **入口切换**：卡片书名链接、入口抽屉首项、日期笔记顶部「全书视角」一律优先进
  `combined.html`（`site_pub._entry_page()` / `link_index.entry_page()`）；
  该书没有合并页时自动回退 `overview.html`，**不会出死链**。
- **回退方式**：需要回退时不必改代码——删掉 `combined.html`（或让 `produce_all` 不产）即可，
  所有入口自动回到老通读页。要彻底下线再改 `MODULES_OVERRIDE` / `ORDER_*`。
- **发布口径**：本次提交含 339 个 `combined.html`（约 32 MB）+ `index.html` 入口切换
  + `note-spec/README.md` 口径章节。
