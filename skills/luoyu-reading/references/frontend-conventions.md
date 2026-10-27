# 前端规范化约定（we-read 静态站）

> 目的：消除"每次改样式都要重写所有 HTML"和"多 agent 改同一批文件互相覆盖"的痛点。
> 适用范围：本仓库所有静态页面（index.html、reading-notes/、books/、notes/ 下的 *.html）。
> 生效时间：2026-10-27 起。所有 agent（含 LuoYu、AI读书 agent）提交前必须遵守。
>
> **Agent 间前端协作沟通走 [frontend-a2a.md](frontend-a2a.md)**：git 提交事件监听，含 START / DONE / SKIP 协议。改前端文件前先 `python3 scripts/a2a_frontend_check.py --alias <你> --update` 看有没有写给自己的协调消息。
>
> **开工前必须先登记待办**，见 [todo-protocol.md](todo-protocol.md)：写进 `openspec/<角色>/todo.md` 并提交，每完成一项立刻 `[x]` 并单独 commit（防崩溃丢进度）。工具链安装见 [tooling-setup.md](tooling-setup.md)。

## 1. 核心铁律：禁止页面内联 CSS

- **页面 `<head>` 里不得出现 `<style>` 块**。所有样式放 `assets/css/*.css`，页面用 `<link>` 引用。
- 新增/修改样式只改对应的 `.css` 文件，不要回到 HTML 里写 `<style>`。
- 改一处视觉（句号分行、卡片圆角、配色…）应只动 1 个 css 文件，全站即时生效，不再重生 HTML。

### 现有共享样式表（已外置，直接复用，勿重建）

| 文件 | 用途 | 引用方 |
|------|------|--------|
| `assets/css/site.css` | 站点基础（已被 outline 引用） | 全局基础 |
| `assets/css/homepage-reading.css` | 首页阅读区块 | `index.html` |
| `assets/css/book-link-drawer.css` | 书籍抽屉组件 | 各书页 |
| `assets/css/reading-note.css` | **精读模板A** + 轻游记 overview（章节导读式） | `final.html`、轻游记 `overview.html` |
| `assets/css/reading-note-rich.css` | **精读模板B**（baikal 的 hero/面包屑式） | baikal `final.html` |
| `assets/css/reading-outline.css` | **AI 大纲页**模板一（原始 58 本） | `outline.html` |
| `assets/css/reading-outline-entry.css` | **AI 大纲（读前通读入口页）**模板二（13 本新建入口页） | `outline.html` |

> 注：`reading-note.css` 与轻游记 `overview.html` 的内联 CSS 完全相同，已可共用，勿再内联。

## 2. 新增页面类型怎么办

1. 在 `assets/css/` 下建 `<type>.css`（若样式与某现有文件高度重合，直接复用现有文件）。
2. 页面 `<head>` 用 `<link rel="stylesheet" href="<相对路径>/assets/css/<type>.css">` 引用。
3. **绝不**把样式写进页面 `<style>`。

相对路径规则（按页面深度）：
- 书页 `reading-notes/books/<slug>/x.html` → `../../../assets/css/...`
- 首页/一级目录 → `assets/css/...`

## 3. 外链与导航：单一来源（进行中）

- 书的 weread / 豆瓣外链、跨页导航目前仍硬编码在各页，正在迁移到 `_data/books.json`（单一数据源）。
- **改动外链时**：先确认是否多页共用同一本书的链接；若已建 `_data/books.json`，改数据文件而非逐个改 HTML。
- 跨页导航（"阅读归档""系列"）保持相对路径一致，不要每页手敲不同深度。

## 4. 首页卡片：数据驱动（计划）

- 首页 `index.html` 的 archive-grid 卡片（全书视角 / 即将上线）将改为由 `_data/books.json` + 卡片模板渲染，按 `status` 字段自动分流。
- **未迁移前**：新增卡片仍手写在 `index.html`，但不得把样式内联进卡片 HTML；样式走 `homepage-reading.css`。

## 5. 多 agent 合并协议（重要）

本仓库有多个 agent 同时提交，务必遵守：

1. **提交前先 `git pull --rebase origin main`**（或先 fetch 再 merge），基于最新 main 再改。
2. **禁止 `git push --force` 到 main**；冲突时就地解决，不要覆盖对方。
3. 若两人改到同一文件：保留共享 `<link>` 引用，**不要把对方外置的 CSS 又内联回 HTML**。
4. 页面 `<head>`（样式/链接）与 `<body>`（内容/卡片）改动区域通常不同，3-way 合并大多能自动通过；若冲突，优先保留"外置样式 + 自己新增的内容"。
5. 大批量页面改动（如全站样式）优先抽成共享 css 一次性提交，减少与他人碰撞面。

## 6. 验收

- 全仓库 `<style>` 块数量应趋于 0（仅历史未迁移页面暂存，按第 2 条逐步外置）。
- 任意页面改视觉后，只需 `git diff` 出 1 个 `.css` 文件即视为达标。

## 7. 卡片文案规范（防技术词回潮）

- 首页 / 书页卡片里的 `<span class="subtle">` **禁止出现 `HTML` 等实现层技术词**（读者看不懂，且每次重生成都会回潮）。
- 统一用语义化文案，例如：`网页版`、`网页版 · 可下载 EPUB`、`全书视角 · 网页版`。
- 若卡片由生成器产出（weread-auto 的 `site_pub.py` 等），**改生成器源模板**，不要只在已渲染的 `index.html` 上批量替换——否则下次生成又会写回 `HTML`。
- 验收：`grep -rn 'subtle">HTML' .` 必须为空。
