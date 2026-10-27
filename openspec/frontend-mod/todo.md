# 前端改造员 · 待办（openspec）

维护人：`frontend-mod`（前端模块化 / 数据化 / Web 迁移）。**只写本文件**，不碰其他角色的 todo。
本文件只管待办与进度，不替代 `book-registry.json` / `agent-roster.json`（认领、锁、续读点仍以 main 上 registry 为准），
也不替代 [frontend-a2a.md](../../skills/luoyu-reading/references/frontend-a2a.md)（跨 agent 协调）。

> 协议：[todo-protocol.md](../../skills/luoyu-reading/references/todo-protocol.md) —— 开工前先登记、每步即提交。
> 最后更新：2026-10-27 18:48（本文件每次动作后立即更新并单独提交）

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
- [x] **本轮（2026-10-27 18:48 监听轮次）**：复核 `luoyu-content` 连发的 2 条 `UPDATE`，站点已从「米纸黄 hero」一路走到「绿底 hero + 二维码移页脚」：
  - ① `e1c6ce2`+`e7644b9`：hero 背景回退 `site.css` 深绿渐变，只改 `homepage-hero.css`（删掉对 `.hero` 背景/文字的覆盖），声明 `index.html` 零改动。
  - ② `4717f47`+`ad44047`+`579d361`：便签手写改「AI帮你读」、**二维码从 hero 右下移到 `.site-footer` 品牌块**（新增 `.footer-info`/`.footer-brand`/`.footer-brand-text`/`.footer-qr`），原 hero `figure` 删除。
  - **结论：结构/基线/约定 6 项全过；但二维码「能扫」这条不过（新缺陷，比原来更差）。**
  - ① 结构：`HTMLParser` 遍历 `index.html` → 未闭合 0、错配 0；`header` 1/1、`figure` 0/0（hero 的 figure 已随二维码一起移除，页脚改用裸 `<img>`）；`div` 开闭差 2 与改动前同为 −2（`<div` 正则会误吃 JS/注释内字面量，非真实缺口）。
  - ② 基线：`preread-card` **46** / `preread-soon` **36** / `reading-notes/books/` 链接 **166 唯一 0 死链** / 内联 `<style>` **0** / 重复 `id` **0**。
  - ③ 自检：`check_site_invariants.py` 仅 C1 存量 **29 页**（14:57 起第 5 轮零新增）；C2/C3/C4 全清，未跑 `--fix`。
  - ④ 布局：1280px footer 1080×115（QR 卡 72×72 落在 `x1080..1152`，距右边界 28px）；375px footer 375×151（`.footer-brand` 212×64 内含 64px QR）；两档 `scrollWidth == innerWidth`，零横向溢出，`.footer-info` 在 ≤680px 转纵向不挤。
  - ⑤ 样式死活：`.footer-info/.footer-brand/.footer-brand-text/.footer-qr` 在 `homepage-hero.css` 全部有定义（第 63/68/73/89 行）；`hero-qr` 全仓库仅剩第 61 行一条「已停用」注释，无悬挂规则；`--serif`/`--sans` 仍由 site.css `:root` 提供。
  - ⑥ **二维码扫描不过（唯一硬伤）**：`assets/img/hero-qr.png` 仍是 762B 无白边原图（116×116，**单独解码仍然失败**）；且尺寸不升反降 —— hero 时期渲染 84px，现在 `.footer-qr` 声明 72px 但 `box-sizing:border-box` + `padding:4px` + `1px border` → 实际绘出 **62px**，移动端更只剩 **54px**。实测截取页脚 QR 卡：桌面 72×73 **解出** `https://ae6623.github.io/we-read/`；**移动端 65×65 直接解码返回空**，要 4× 放大才能解出。即"手机上翻到自己站点的页脚，再用另一台手机扫"这条真实路径不可靠。
  - ⑦ 时钟：对方两条消息落款 `18:40`、`19:10`，我实际读到的时间分别约 `18:39`、`18:47`，**落款整体跑在未来**，已在 A2A 提醒按真实时间写，否则板子时序回溯会错位。


- [x] **本轮（2026-10-27 14:57 监听轮次）复核：两项均通过，无新增质量债。**
  - ① `aa5d14a`：5 页 `<style>` 归零，改为 `site.css` + `reading-outline.css`（与既有 58 页写法一致）。**逐页比对删除的 33 个选择器，在 `reading-outline.css` 全部有定义**（`:root`/`.page`/`.note-head`/`.eyebrow`/`.chip`/`.toc`/`details.ch`/`.sec`/`.point`/`.quote`/`.small` 等，missing=NONE），无样式裸奔。C1+C2 消项，C1 存量 34→29。
  - ② `6afd363`：`index.html` 结构完好 —— `.subtabs` 1 个、`panel-whole` 1 个、`panel-soon` 1 个、重复 id 0、内联 `<style>` 0、书中链接 151 条**唯一且 0 死链**。"panel-soon 重复"已清。
  - 不加 `.gcstat` 样式：该 class 是页脚 PV 占位，自带 `display:none`，62 页一致，非缺陷。
- [x] **本轮（2026-10-27 监听轮次）**：`luoyu-content` 新推 18 篇 overview + 5 套 outline，`_data` 未收录其中 18 个 slug（C4）。跑 `extract_content.py` 刷新 `_data/books/*.json` 并提交（`708a30b`）；5 个新 outline 页的内联 `<style>`（C1）+ 缺 `reading-outline.css`（C2）不代改，已登记 P2 并在 A2A 板发 `QUESTION`（`QUESTION` 正文见 `frontend-a2a.md` 2026-10-27 13:50 条）。
- [ ] **等 `luoyu-content` 就 5 页 outline 选 A（改模板）/ B（授权我外置）**；等 `ACK` 后按选择执行。
  → 实操上已由对方自行外置（`aa5d14a`），A/B 问题作废；但**未发 `DONE`、未回 A/B**，流程账仍挂着。
- [ ] **根因未闭环**：5 页是"改成品"还是"改源"？仓库 `templates/` 只有 `book-collection` / `book-link-drawer` / `reading-note`，**无 outline 生成模板**，生成器在本仓库之外，我无法验证。判定口径：下批新 outline 若再带回内联 `<style>`，即证明只改成品没改源 → 直接升级 `CONFLICT`。
- [x] 建立 todo 前置制度：本文件 + `todo-protocol.md` + A2A 通告（`b870d10`→`72313f8`）
- [x] 安装工具链并写复现文档：`openspec` CLI（1.15.0，已装）+ `superpowers` 技能包（15 个，已装）→ `tooling-setup.md`
- [x] A2A 通告 `luoyu-content`：开工前先写 `openspec/luoyu-content/todo.md`，并要求其建该文件
- [x] **`luoyu-content` 已回 ACK（2026-10-27 15:40）→ PROTOCOL 闭环**：`openspec/luoyu-content/todo.md` 已建并入库（`6181431`），登记了本轮任务；承诺每轮开工前先登记、推送前跑 `a2a_frontend_check.py --alias luoyu-content --update`、崩溃恢复含 `git fetch` + 读板 + 对照 todo。**催办 3 次后闭环，本项消账。**
- [x] **`QUESTION` 根因答复已收（同一 ACK）**：其 outline 生成侧现只输出 `<link>` 不写内联；overview 走 `build_ov.py`，`<head>` 仅 `reading-overview.css` + `book-link-drawer.css`，零 `<style>`。并主动接受"下批再回潮直接 `CONFLICT`"的判定口径。**判定口径保持有效，下批新页仍是验伪点。**
- [x] **B6/B7 八本 `overview.html` 已收账（2026-10-27 17:22）**，三步全部完成：
  1. `extract_content.py --slug` 刷新 8 本 `_data/books/*.json`（`eca7107`）——`texts.overview` 各 9 段、`ai_outline` 只存元信息，C4 通过
  2. `index.html` 8 本从「即将上线」升格为「全书视角·AI 问书」三入口卡（`625cdf0`）——**全书视角 39→46 / 即将上线 43→36**，跨面板零重复、166 条卡片链接唯一且 0 死链、重复 id 0、内联 style 0
  3. `check_site_invariants.py`：C2/C3/C4 全过，C1 存量仍 29 页（本轮零新增）；顺带消 2 处存量 `subtle` 技术词
  → **修正上轮判断**：8 本里 7 本原本在 `panel-soon`（占位卡，仅大纲入口），只有《在峡江》在 `panel-whole`；上轮"每本都已有 panel-whole 卡"是 `grep` 把两类别混统计导致的误判，已在 A2A 板更正
- [x] **首页 hero 品牌头图改版已收账（`luoyu-content`，`a52bbe5`+`3eb3e9e`+DONE，17:55）**——品牌名「落雨阅读札记」、口号「通读交给 AI，精读留给自己」、米纸底、便签铅笔装饰、右下扫码卡。
  - 终检 7 项全过：全书视角 **46** / 即将上线 **36** / 卡片链接 **166 唯一 0 死链** / 内联 `<style>` **0** / 重复 `id` **0** / 新资源 HTTP 200 / **卡片区与基线 `425b8c8` 逐字节一致**
  - 结构：`header` 内 div 4 开 4 闭、figure 1 开 1 闭；Playwright 1366px + 375px 无溢出、无遮挡
  - **冻结已解除**，`index.html` 维护权收回（但 hero 区间 + `homepage-hero.css` + `hero-qr.png` 仍归对方，我出问题只发 QUESTION）
- [ ] **等对方修 `hero-qr.png` 的 quiet zone**（已发 QUESTION `b010e71`）：原图四边无白边，`cv2.QRCodeDetector` 直接解码返回空、detectable=False；补 ≥8px 白边后解出 `https://ae6623.github.io/we-read/`。页面靠卡片 7px padding ≈3.4 模块安静区（标准 4），部分手机会扫不出。已给出两条现成修复命令，**没替它改文件**
  → 收到 DONE 后只复跑：二维码解码 + 5 项基线
- [ ] 监听下一批内容 `DONE`（对方 todo 剩 2 项：5 本 BOOK 配置 + 质量门，尚未推）
  → 固定动作不变：`extract_content.py --slug` → 卡片只补链/升格不加卡 → `check_site_invariants.py` + 死链复核
  → 注意：hero 冻结期间若收到内容 `DONE`，`_data` 可以刷（不在冻结范围），但 `index.html` 卡片要等解冻
- [ ] 监听任务复核：现有每小时 A2A 监听 automation 是否把「检查对方 todo 是否有新登记」纳入动作

### P1 · 等待用户拍板
- [ ] 13 个「大纲入口页」缺官方 `outline.json` → `_data` 里这些书 `ai_outline` 为空。需内容侧补抓，或前端降级展示
- [ ] Web 程序 Step 3：SQLite 建表（见 [content-model.md](../../skills/luoyu-reading/references/content-model.md)）+ Flask/FastAPI + Jinja2 复用现有 CSS，先跑通 1 本书（建议 1984）
- [ ] `_data/books.json` 单一数据源（书目/外链/系列/status），首页 71 张卡由数据渲染，替代手写 `index.html`

### P2 · 质量债
- [ ] **页脚二维码扫描可靠性（2026-10-27 18:48 实测，归属 `luoyu-content`）**：`hero-qr.png` 无 quiet zone + 页脚渲染尺寸偏小，双重叠加。① 原图 116×116 单独 `cv2` 解码失败；② `.footer-qr` 声明 72px，但 `*{box-sizing:border-box}` + `padding:4px` + `1px border` 吃掉 10px → 实际 **62px**（移动端 54px），比 hero 时期的 84px 更小；③ 截取移动端 QR 卡 65×65 **直接解码返回空**，4× 放大才成功。修法二选一或并用：给 PNG 补 ≥8px 白边（治本）、CSS 提到 `88px` 并把 padding 计入外框（治标）。**我不代改**（对方地盘），已发 QUESTION 附实测数字。
- [ ] **A2A 游标会「静默吃掉」消息（2026-10-27 18:39 实测）**：`e7644b9` 已含 `[18:40] FROM luoyu-content → TO frontend-mod / UPDATE`，但 `.a2a/frontend-a2a.seen` 游标已被推到 `e7644b9`，脚本走 `seen_hash == latest` 短路直接报「无新消息」→ 这条 UPDATE 从未进入任何一轮记录。**根因**：游标与「消息已处理」不绑定，中途任何一次 `--update`（含中断的会话）都会推过头。**临时纪律（立即生效）**：每轮除跑脚本外必须 `Get-Content frontend-a2a.md -Tail 60` 人工核对板尾，脚本输出不作唯一依据。**根治候选**：游标改存「最后一条已处置的板提交」而非「最新板提交」，或对 `to == 本别名` 且无对向回复的块二次扫描（需用户拍板，勿擅自重构）。
- [x] **新 outline 页内联 CSS 回潮（5 页，2026-10-27 批次）→ 已消项**：`di-yi-xing-yuan-li--pu-tong-ren-de-ren-sheng-ga`、`jin-rong-jia--jiao-fu--jin-rong-ban--mei-guo`、`tian-mu-hong-chen--yao-yuan-de-jiu-shi-zhu--z`、`xi-da-duo--ming-jia-yi--shen-du-zhu-shi--ren`、`zai-xia-jiang-de-zhuan-wan-chu--chen-xing-jia-r`。对方以 `aa5d14a` 自行外置（每页 -38 行内联、+1 行 `<link>`），我方复核 33 个选择器全覆盖，视觉等价。原判断"代加 `<link>` 会双写"成立，故当时不代改是对的。
- [ ] **剩余 29 页内联 CSS 存量**（`check_site_invariants.py` 的 C1 项）：日期笔记 `notes/*.html` 24 页 + `camino/history.html` + `spain-qingyouji` 2 篇 + 3 个系列索引 + `reading-notes/index.html`。普查结果：**23 种指纹**（date notes 各写各的，散乱最严重），不能一把梭合并，需按书族/模板分批外置。
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

- 2026-10-27 18:48：监听轮次 —— 连收 2 条 `UPDATE`（hero 回退绿底 `e1c6ce2`、二维码移入页脚 `ad44047`+`579d361`），**脚本继续漏报，靠人工看板尾捕获**。结构/基线/约定 6 项全过（46-36-166 唯一 0 死链、内联 0、重复 id 0、1280+375 零溢出、`.hero-qr` 无残留）。唯一硬伤：页脚二维码实际只绘 62px（移动 54px）+ 原图无白边，移动端实测解码失败，已记 P2 并发 QUESTION。另：推送时板文件追加冲突，已 `merge --abort` 后重置到 `origin/main` 重写自己的未推送提交，**未强推、未删对方任何一行**。

- 2026-10-27 14:57：监听轮次 —— A2A 无新消息（游标 `72313f8`→`ec9fca1`，仅我自己的提交）；`check_site_invariants.py` 仅剩 C1 存量 29 页（C2/C3/C4 全清）。复核对方 `6afd363`（首页恢复 30 张通读卡）与 `aa5d14a`（5 页 outline 内联外置）均通过，详见 P0。
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
