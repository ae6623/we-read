# 前端改造员 · 待办（openspec）

维护人：`frontend-mod`（前端模块化 / 数据化 / Web 迁移）。**只写本文件**，不碰其他角色的 todo。
本文件只管待办与进度，不替代 `book-registry.json` / `agent-roster.json`（认领、锁、续读点仍以 main 上 registry 为准），
也不替代 [frontend-a2a.md](../../skills/luoyu-reading/references/frontend-a2a.md)（跨 agent 协调）。

> 协议：[todo-protocol.md](../../skills/luoyu-reading/references/todo-protocol.md) —— 开工前先登记、每步即提交。
> 最后更新：2026-10-27 05:20（本文件每次动作后立即更新并单独提交）

## 当前状态

- 基线提交：`b870d10`（fix-publish → main）。
- 全仓库 `overview.html` / `outline.html` / `final.html` 的 `<style>` 已归零，样式统一在 `assets/css/` 下：
  `site.css`、`reading-note.css`、`reading-note-rich.css`、`reading-overview.css`、`reading-outline.css`、`reading-outline-entry.css`、`homepage-reading.css`、`book-link-drawer.css`。
- 内容已结构化：`_data/books/*.json` 78 本（2.1MB）；大纲节点不入 JSON，留在各书 `outline.json`。
- 与 `luoyu-content` 的 A2A 已闭环一轮（其 ACK `55a3553`，我方修复其富词汇缺口 `50c33dd`）。

## 待办

### P0 · 进行中
- [ ] 建立 todo 前置制度：本文件 + `todo-protocol.md` + A2A 通告（本轮）
- [ ] 安装工具链并写复现文档：`openspec` CLI（1.15.0，已装）+ `superpowers` 技能包（15 个，已装）→ 产出 `tooling-setup.md`
- [ ] A2A 通告 `luoyu-content`：开工前先写 `openspec/luoyu-content/todo.md`，并要求其建该文件

### P1 · 等待用户拍板
- [ ] 13 个「大纲入口页」缺官方 `outline.json` → `_data` 里这些书 `ai_outline` 为空。需内容侧补抓，或前端降级展示
- [ ] Web 程序 Step 3：SQLite 建表（见 [content-model.md](../../skills/luoyu-reading/references/content-model.md)）+ Flask/FastAPI + Jinja2 复用现有 CSS，先跑通 1 本书（建议 1984）
- [ ] `_data/books.json` 单一数据源（书目/外链/系列/status），首页 71 张卡由数据渲染，替代手写 `index.html`

### P2 · 质量债
- [ ] 卡片生成器源头治理：`HTML` 技术词反复回潮，需定位 `luoyu-content` 的生成脚本并改为 `网页版`
- [ ] 38 本待生成 `overview` 的统一模板（共享 CSS + 统一词汇）落成模板文件，避免各写各的
- [ ] `index.html` 顶层 Tab 与通读子 Tab 的键盘焦点顺序复核（移动端 + 读屏）

### 已确认不做
- [x] 不把 `outline.json` 节点复制进 `_data`（会导致 23MB 重复；已回退为只存元信息）
- [x] 不改 `reading-outline-entry.css`（归属 `luoyu-content`；我只补 `<link>` 顺序）

## 规则

- 开工前：先在本文件写下本轮任务（断言式、可验收），再动手；动完一项立刻 `[x]` 并单独 commit。
- 只改自己认领的文件；跨角色文件先发 `START` 到 A2A 板，或用 `QUESTION` 协商。
- 提交前 `git fetch` + 跑 `python3 scripts/a2a_frontend_check.py --alias frontend-mod --update`。
- 公开文件不写凭据、私人路径、Agent UID。

## 已完成

- 2026-10-27：精读页 5 篇内联 CSS 外置（`reading-note(.rich).css`）。
- 2026-10-27：outline 58 篇 + 13 篇入口页外置（`reading-outline(.entry).css`）。
- 2026-10-27：通读「全书视角/即将上线」改独立分段控件 `.subtabs`（带计数/键盘/移动端）；71 处 `HTML`→`网页版`。
- 2026-10-27：overview 33 篇外置（`reading-overview.css` 超集，统一 `:root` 调色板）。
- 2026-10-27：内容结构化 78 本 `_data/books/*.json` + `extract_content.py` + `content-model.md`。
- 2026-10-27：A2A 机制（`frontend-a2a.md` + `a2a_frontend_check.py`）建立并完成一轮闭环。
