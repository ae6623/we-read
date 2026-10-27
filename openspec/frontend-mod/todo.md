# 前端改造员 · 待办（openspec）

维护人：`frontend-mod`（前端模块化 / 数据化 / Web 迁移）。**只写本文件**，不碰其他角色的 todo。
本文件只管待办与进度，不替代 `book-registry.json` / `agent-roster.json`（认领、锁、续读点仍以 main 上 registry 为准），
也不替代 [frontend-a2a.md](../../skills/luoyu-reading/references/frontend-a2a.md)（跨 agent 协调）。

> 协议：[todo-protocol.md](../../skills/luoyu-reading/references/todo-protocol.md) —— 开工前先登记、每步即提交。
> 最后更新：2026-10-27 14:57（本文件每次动作后立即更新并单独提交）

## 当前状态

- 基线提交：`72313f8`（fix-publish → main）。
- **待办制度已生效**：`todo-protocol.md` 定规则，`openspec/<角色>/todo.md` 落文件，A2A 板已发 `PROTOCOL` 通告（等 ACK）。
- **工具链已装**：`openspec` 1.15.0（全局）+ `openspec/config.yaml` + `.codebuddy/`（6 技能 6 命令，已入库）；`superpowers` 15 技能装在 `~/.workbuddy/skills`，vendor 在 `~/.workbuddy/vendor/superpowers`。复现方式见 `tooling-setup.md`。
- 全仓库 `overview.html` / `outline.html` / `final.html` 的 `<style>` 已归零，样式统一在 `assets/css/` 下：
  `site.css`、`reading-note.css`、`reading-note-rich.css`、`reading-overview.css`、`reading-outline.css`、`reading-outline-entry.css`、`homepage-reading.css`、`book-link-drawer.css`。
- 内容已结构化：`_data/books/*.json` 78 本（2.1MB）；大纲节点不入 JSON，留在各书 `outline.json`。
- 与 `luoyu-content` 的 A2A 已闭环一轮（其 ACK `55a3553`，我方修复其富词汇缺口 `50c33dd`）。

## 待办

### P0 · 进行中
- [ ] **本轮（2026-10-27 14:57 监听轮次）**：复核对方新推的 2 个提交并决定 P2 条目去留 —— ①`aa5d14a`「5 页新大纲内联样式外置」（即我 13:50 QUESTION 的对象，但未回 A/B、未发 DONE）；②`6afd363`「恢复被云端批量大纲覆盖的 30 张通读卡」（动了 `index.html`，我认领 SCOPE）。验收口径：5 页内联 `<style>` 归零且 **删除的 33 个选择器在 `reading-outline.css` 全部有定义**（不许出现样式裸奔）；`index.html` 保持 `.subtabs` + `panel-whole`/`panel-soon` 单实例、无重复 id、无死链、卡片无重复。复核完据此打勾 P2 并回 A2A。
- [x] **本轮（2026-10-27 监听轮次）**：`luoyu-content` 新推 18 篇 overview + 5 套 outline，`_data` 未收录其中 18 个 slug（C4）。跑 `extract_content.py` 刷新 `_data/books/*.json` 并提交（`708a30b`）；5 个新 outline 页的内联 `<style>`（C1）+ 缺 `reading-outline.css`（C2）不代改，已登记 P2 并在 A2A 板发 `QUESTION`（`QUESTION` 正文见 `frontend-a2a.md` 2026-10-27 13:50 条）。
- [ ] **等 `luoyu-content` 就 5 页 outline 选 A（改模板）/ B（授权我外置）**；等 `ACK` 后按选择执行。
- [x] 建立 todo 前置制度：本文件 + `todo-protocol.md` + A2A 通告（`b870d10`→`72313f8`）
- [x] 安装工具链并写复现文档：`openspec` CLI（1.15.0，已装）+ `superpowers` 技能包（15 个，已装）→ `tooling-setup.md`
- [x] A2A 通告 `luoyu-content`：开工前先写 `openspec/luoyu-content/todo.md`，并要求其建该文件
- [ ] **等 `luoyu-content` 回 ACK**（确认其已建自己的 todo.md、已装工具链）；超一轮无回应则用监听脚本复查并在板上再提醒
- [ ] 监听任务复核：现有每小时 A2A 监听 automation 是否把「检查对方 todo 是否有新登记」纳入动作

### P1 · 等待用户拍板
- [ ] 13 个「大纲入口页」缺官方 `outline.json` → `_data` 里这些书 `ai_outline` 为空。需内容侧补抓，或前端降级展示
- [ ] Web 程序 Step 3：SQLite 建表（见 [content-model.md](../../skills/luoyu-reading/references/content-model.md)）+ Flask/FastAPI + Jinja2 复用现有 CSS，先跑通 1 本书（建议 1984）
- [ ] `_data/books.json` 单一数据源（书目/外链/系列/status），首页 71 张卡由数据渲染，替代手写 `index.html`

### P2 · 质量债
- [ ] **新 outline 页内联 CSS 回潮（5 页，2026-10-27 批次）**：`di-yi-xing-yuan-li--pu-tong-ren-de-ren-sheng-ga`、`jin-rong-jia--jiao-fu--jin-rong-ban--mei-guo`、`tian-mu-hong-chen--yao-yuan-de-jiu-shi-zhu--z`、`xi-da-duo--ming-jia-yi--shen-du-zhu-shi--ren`、`zai-xia-jiang-de-zhuan-wan-chu--chen-xing-jia-r` 的 `outline.html`。症状：只 `<link site.css>`、自带整段 `<style>`、未引 `reading-outline.css`（同时触发 C1+C2）。已发 `QUESTION` 等 `luoyu-content` 从生成模板改源，**不代改**（代加 `<link>` 会与其内联规则双写）。
- [ ] **剩余 29 页内联 CSS 存量**（`check_site_invariants.py` 的 C1 项）：日期笔记 `notes/*.html` 24 页 + `camino/history.html` + 3 个系列索引 + `reading-notes/index.html`。普查结果：**23 种指纹**（date notes 各写各的，散乱最严重），不能一把梭合并，需按书族/模板分批外置
- [ ] 卡片生成器源头治理：`HTML` 技术词反复回潮，需定位 `luoyu-content` 的生成脚本并改为 `网页版`（当前首页 0 处，靠脚本 C3 兜底）
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

- 2026-10-27 13:50：快进合并 `luoyu-content` 19 个提交（`6f59ccc..6538ba1`，零冲突）；18 篇新 overview **0 内联 0 技术词**；按 18 个 slug 重跑 `extract_content.py`，`_data` 与页面同步（C4 清零，commit `708a30b`）。
- 2026-10-27 13:50：发现 5 个新 `outline.html` 内联 CSS 回潮（C1+C2），不代改，记入 P2 并发 `QUESTION` 要求改生成模板或授权外置；同时二次催 `openspec/luoyu-content/todo.md`（仍不存在）。
- 2026-10-27：合并 `luoyu-content` 新推的 12 本 overview（全书视角 33→45 本），merge 零冲突；其页面**0 内联、0 技术词**，已守约定。
- 2026-10-27：修 `camino-qingyouji/overview.html` 样式表链接丢失（正文 `card/tag/ch-item/mindmap` 裸奔）→ 补 `reading-note.css`。
- 2026-10-27：`index.html` 内联样式（2537B，办公室入口/hero/阅读说明/系列卡）外置到 `homepage-reading.css`，首页 `<style>` 归零。
- 2026-10-27：新增 `scripts/check_site_invariants.py`（C1 内联样式 / C2 共享CSS链接 / C3 技术词 / C4 数据一致性），push 前一条命令自检，暴露 30 页存量内联。
- 2026-10-27：`2026-10-27` 待办制度落地：`openspec/frontend-mod/todo.md` + `todo-protocol.md` + `openspec/README.md`；A2A `PROTOCOL` 通告已发。
- 2026-10-27：`openspec` 1.15.0 安装并 init（`config.yaml`/`changes`/`specs`/`.codebuddy`）；`superpowers` 15 技能安装；`tooling-setup.md` 复现文档。
- 2026-10-27：精读页 5 篇内联 CSS 外置（`reading-note(.rich).css`）。
- 2026-10-27：outline 58 篇 + 13 篇入口页外置（`reading-outline(.entry).css`）。
- 2026-10-27：通读「全书视角/即将上线」改独立分段控件 `.subtabs`（带计数/键盘/移动端）；71 处 `HTML`→`网页版`。
- 2026-10-27：overview 33 篇外置（`reading-overview.css` 超集，统一 `:root` 调色板）。
- 2026-10-27：内容结构化 78 本 `_data/books/*.json` + `extract_content.py` + `content-model.md`。
- 2026-10-27：A2A 机制（`frontend-a2a.md` + `a2a_frontend_check.py`）建立并完成一轮闭环。
