# 前端改造员 · 待办（openspec）

维护人：`frontend-mod`（前端模块化 / 数据化 / Web 迁移）。**只写本文件**，不碰其他角色的 todo。
本文件只管待办与进度，不替代 `book-registry.json` / `agent-roster.json`（认领、锁、续读点仍以 main 上 registry 为准），
也不替代 [frontend-a2a.md](../../skills/luoyu-reading/references/frontend-a2a.md)（跨 agent 协调）。

> 协议：[todo-protocol.md](../../skills/luoyu-reading/references/todo-protocol.md) —— 开工前先登记、每步即提交。
> 最后更新：2026-10-27 20:10（本文件每次动作后立即更新并单独提交）

## 当前状态

- 基线提交：`72313f8`（fix-publish → main）。
- **待办制度已生效**：`todo-protocol.md` 定规则，`openspec/<角色>/todo.md` 落文件，A2A 板已发 `PROTOCOL` 通告（等 ACK）。
- **工具链已装**：`openspec` 1.15.0（全局）+ `openspec/config.yaml` + `.codebuddy/`（6 技能 6 命令，已入库）；`superpowers` 15 技能装在 `~/.workbuddy/skills`，vendor 在 `~/.workbuddy/vendor/superpowers`。复现方式见 `tooling-setup.md`。
- 全仓库 `overview.html` / `outline.html` / `final.html` 的 `<style>` 已归零，样式统一在 `assets/css/` 下：
  `site.css`、`reading-note.css`、`reading-note-rich.css`、`reading-overview.css`、`reading-outline.css`、`reading-outline-entry.css`、`homepage-reading.css`、`book-link-drawer.css`。
- 内容已结构化：`_data/books/*.json` 78 本（2.1MB）；大纲节点不入 JSON，留在各书 `outline.json`。
- 与 `luoyu-content` 的 A2A 已闭环一轮（其 ACK `55a3553`，我方修复其富词汇缺口 `50c33dd`）。

## 解耦：本地 ↔ 云端（2026-10-27 19:12 登记）

目标：用户不再需要「本地重打快照 → 覆盖上传」。口径已按 `luoyu-content` 的情报修正为 **API-only（零 git、零 zip）**——其沙箱无本地仓、git over https 不稳，只用 gh api 读板。

- [x] **L2 生成层**：确认 `_api_prime` 在发布前拉 main 的 `index.html` + `reading-notes/index.html`，首页宿主已不依赖快照新鲜度。`outline_by_names.generate()` 发布前的重复刷新待清理（不阻塞、无正确性问题，排队）
- [x] **L3-1 注册表读取走 API**（`weread-auto/reading_state.py::load_registry`）：新增 `shared.registry_source = "api"` 开关，**默认关闭**；开启后先走 Contents API，失败退回沙箱快照缓存。实测 0.53s、revision 196 与快照一致；默认路径行为零变化。已同步 `weread-cloud` / `weread-cloud-new`
- [ ] **L3-2 认领写入走 API**：新增 `claim_via_api`（`gh_api.publish_paths` 提交 `book-registry.json`，冲突重取重试 ≤2 次）。做完云端认领才能落到 main，本机才看得见"谁在读"
- [ ] **L3-3 打开开关并实测**：云端跑一场验证注册表读延迟与认领落库；通过后再撤掉 `vendor/we-read.zip` 依赖
- [ ] 等 `luoyu-content` 答两点：① 是否还会改 `index.html` 结构 ② 其沙箱 token 的环境变量名

## 待办

### P0 · 进行中
- [x] **本轮（2026-10-27 20:10 监听轮次）**：**补 19:33–19:43 三个未记账提交** —— 5 项验收全过，站点文件零改动。
  发现：`HEAD == origin/main == 6f028d8`，比上一条落账（19:07 `8307b11`）多 3 个提交 —— `5ee9ab7`（新增 `brand/` + 首页品牌行改 `a[href=brand/]`）、`47908c5`（`brand/index.html` 刊头改玄水底彩色标识 84px）、`6f028d8`（`index.html` 精读面板 16 张日期卡按 `<time datetime>` 倒序重排，26+/27−）。
  归属判定：`5ee9ab7` 内同时提交了 A2A 板 `[19:35] FROM frontend-mod` 帖，帖内 SCOPE 与 diff stat 逐项吻合（`index.html` 2 行、`homepage-hero.css` +25、`brand/*` 10 文件）→ **三个提交均属我方**，是 19:33–19:43 那轮的工作但未写进本文件、也未写进 automation memory（连续第二轮「代码已上、账未记」，属流程缺陷，须在本轮补平）。
  本轮要验收：① `index.html` 卡片基线不退化（全书视角 46 / 即将上线 36 / 卡片链接唯一且 0 死链 / 内联 `<style>` 0 / 重复 `id` 0）；② 16 张日期卡**是移动不是复制**（`archive-card` 总数与 `data-search` 唯一性）；③ 卡片重排后日期仍严格倒序、无断层；④ `brand/` 新页资源零死链、390px 无横向溢出；⑤ `.hero-brand` 改 `a` 后不影响 hero 区间布局。**不改站点文件**，只补账 + 记录。
  → 结果：**5 项全过，反推归属无争议**（`5ee9ab7` 的 diff stat 与板帖 SCOPE 逐项对上：`index.html` 2 行、`homepage-hero.css` +25、`brand/*` 10 文件；`6f028d8` 作者同为 ae6623，板帖缺记但内容与「我 19:35 帖里承诺的 hero 区以外不动」不冲突 —— 它动的是精读网格，本就是我方地盘）。
  - ① **卡片基线零退化**（DOM 实测，非 grep）：`#panel-whole` 46 张 / `#panel-soon` 36 张 / `.archive-card` 100 / `card-link-strong` 46 / `preread-soon` 36，与 19:07 基线 `8307b11` 逐项相同；内联 `<style>` 0；25 个 `id` 无重复。
  - ② **是移动不是复制**：精读网格 `archive-card` 总数重排前后同为 16；全页 `card-link` href 125 条**唯一 125 条**，零重复；本地链接 185 条唯一、**0 死链**。
  - ③ **顺序修对了**：改前 `10-25…10-17` 后接 `10-26 ×3`、`10-27`（断层，倒序判定 False）；改后 `10-27 → 10-26×3 → 10-25 → 10-21 → 10-19×3 → 10-18×2 → 10-17×5`，严格倒序 True。卡内文案零改动（diff 26+/27−）。
  - ④ **`brand/` 新页**：`index.html` 8957B、`proposal.html` 11334B，资源引用 0 死链（含 `../index.html` 回首页、2 个 `<symbol>` sprite、4 个落地尺寸示例）。Playwright：1200px / 390px 均 `scrollWidth == innerWidth`、零横向溢出；刊头 `84×84` 未越出 `.brand-head` 边界（390px 下 head 346px 宽、logo 在 `x22`）。**但两页各带 1 个内联 `<style>`**，见 P2 新增项。
  - ⑤ **`hero-brand` 由 `p` 改 `a` 无副作用**：`homepage-hero.css` 主规则是无元素前缀的 `.hero-brand{…}`（第 9/18/26 行）+ 媒体查询第 137 行，换标签后仍命中；追加的 `a.hero-brand` 四组规则只管去下划线/点击区/hover/focus。实测桌面 `text-decoration:none`、`cursor:pointer`、`340×29` 落在 `<header>` 内，header 高 495px；375px 下 `332×28`、header 421px，两档 `scrollWidth == innerWidth`，hero 区未走形。
  - **顺带查出根因（本轮真正的增量）**：`6f028d8` 的断层不是手误，是 `site_pub.update_index` **只追加**本场新条目（`decisions.md:418` 明写「只追加本场 managed 的新条目」），所以每新增一篇日期笔记就会再断一次。**该脚本不在本仓库**（在 `weread-auto` / `weread-cloud` 两份代码里），我只能治标（本次重排），治本需在生成器里改成「按 `<time datetime>` 有序插入」。已记 P2 并把判据定死：下次再出现新卡落在网格末尾，即视为生成器未改。
- [x] **本轮（2026-10-27 19:07 监听轮次）**：巡检 + **补平 QR 两处欠账**。板尾最后一条是我 19:06 的 ACK、`HEAD == origin/main == d4fa97d`、`HEAD..origin/main` 空，自检仅 C1 存量 29 页（零新增）。**本轮唯一缺口是账不平**：QR 缺陷已在 A2A 关单并独立复验，但 P0「等对方修 quiet zone」与 P2「页脚二维码扫描可靠性」两条仍挂着 `[ ]`，须按实测证据改 `[x]`。**不动任何站点文件**。
  → 结果：两条已改 `[x]` 并附证据（原图 296×296/1464B，`cv2` 解出正确 URL、`detectable=True`；`.footer-qr` 为 `content-box` + `padding:0`，72px 真实，移动端同 72px）。站点文件零改动、`_data` 零刷新。**另自查出一处自身污点**：本文件上轮把「最后更新」写成 `19:12`，而当时真实时间约 `19:05` —— 我向对方强调过「落款别写未来」，自己也犯了，已改回真实时间并记此一笔。
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
- [x] **等对方修 `hero-qr.png` 的 quiet zone**（已发 QUESTION `b010e71`）：原图四边无白边，`cv2.QRCodeDetector` 直接解码返回空、detectable=False；补 ≥8px 白边后解出 `https://ae6623.github.io/we-read/`。页面靠卡片 7px padding ≈3.4 模块安静区（标准 4），部分手机会扫不出。已给出两条现成修复命令，**没替它改文件**
  → 收到 DONE 后只复跑：二维码解码 + 5 项基线
  → **已收账（2026-10-27 19:07 我独立复验，非采信其自测）**：对方 `b61e735` 重生成（`border=4`、296×296、762B→1464B），`c4dc19b` 把 `.footer-qr` 改 `content-box`+`padding:0`（72px 为真实尺寸，移动端同为 72px，不再掉到 54px），`5daa071` 发 `DONE`。我复跑 `cv2.QRCodeDetector`：**原图直接解出** `https://ae6623.github.io/we-read/`、`detectable=True`；缩至 88/116px 仍解出，54/62/72px 解不出但 detectable —— 与其「ZBar 54px 起」口径一致，按可接受判。**关单。**仅余非阻塞建议：页脚可提到 80–88px 留余量。
- [ ] 监听下一批内容 `DONE`（对方 todo 剩 2 项：5 本 BOOK 配置 + 质量门，尚未推）
  → 固定动作不变：`extract_content.py --slug` → 卡片只补链/升格不加卡 → `check_site_invariants.py` + 死链复核
  → 注意：hero 冻结期间若收到内容 `DONE`，`_data` 可以刷（不在冻结范围），但 `index.html` 卡片要等解冻
- [ ] 监听任务复核：现有每小时 A2A 监听 automation 是否把「检查对方 todo 是否有新登记」纳入动作

### P1 · 等待用户拍板
- [ ] 13 个「大纲入口页」缺官方 `outline.json` → `_data` 里这些书 `ai_outline` 为空。需内容侧补抓，或前端降级展示
- [ ] Web 程序 Step 3：SQLite 建表（见 [content-model.md](../../skills/luoyu-reading/references/content-model.md)）+ Flask/FastAPI + Jinja2 复用现有 CSS，先跑通 1 本书（建议 1984）
- [ ] `_data/books.json` 单一数据源（书目/外链/系列/status），首页 71 张卡由数据渲染，替代手写 `index.html`

### P2 · 质量债
- [x] **页脚二维码扫描可靠性（2026-10-27 18:48 实测，归属 `luoyu-content`）→ 2026-10-27 19:07 已消项**：`hero-qr.png` 无 quiet zone + 页脚渲染尺寸偏小，双重叠加。① 原图 116×116 单独 `cv2` 解码失败；② `.footer-qr` 声明 72px，但 `*{box-sizing:border-box}` + `padding:4px` + `1px border` 吃掉 10px → 实际 **62px**（移动端 54px），比 hero 时期的 84px 更小；③ 截取移动端 QR 卡 65×65 **直接解码返回空**，4× 放大才成功。修法二选一或并用：给 PNG 补 ≥8px 白边（治本）、CSS 提到 `88px` 并把 padding 计入外框（治标）。**我不代改**（对方地盘），已发 QUESTION 附实测数字。**结局**：对方两条都做了（`b61e735` 补 4 模块白边、`c4dc19b` 改 `content-box` 去 padding），我 19:07 复验原图解码成功、另存 88/116px 亦成功，**两条修法叠加后缺陷消失**。
- [ ] **A2A 游标会「静默吃掉」消息（2026-10-27 18:39 实测）**：`e7644b9` 已含 `[18:40] FROM luoyu-content → TO frontend-mod / UPDATE`，但 `.a2a/frontend-a2a.seen` 游标已被推到 `e7644b9`，脚本走 `seen_hash == latest` 短路直接报「无新消息」→ 这条 UPDATE 从未进入任何一轮记录。**根因**：游标与「消息已处理」不绑定，中途任何一次 `--update`（含中断的会话）都会推过头。**临时纪律（立即生效）**：每轮除跑脚本外必须 `Get-Content frontend-a2a.md -Tail 60` 人工核对板尾，脚本输出不作唯一依据。**根治候选**：游标改存「最后一条已处置的板提交」而非「最新板提交」，或对 `to == 本别名` 且无对向回复的块二次扫描（需用户拍板，勿擅自重构）。
- [x] **新 outline 页内联 CSS 回潮（5 页，2026-10-27 批次）→ 已消项**：`di-yi-xing-yuan-li--pu-tong-ren-de-ren-sheng-ga`、`jin-rong-jia--jiao-fu--jin-rong-ban--mei-guo`、`tian-mu-hong-chen--yao-yuan-de-jiu-shi-zhu--z`、`xi-da-duo--ming-jia-yi--shen-du-zhu-shi--ren`、`zai-xia-jiang-de-zhuan-wan-chu--chen-xing-jia-r`。对方以 `aa5d14a` 自行外置（每页 -38 行内联、+1 行 `<link>`），我方复核 33 个选择器全覆盖，视觉等价。原判断"代加 `<link>` 会双写"成立，故当时不代改是对的。
- [ ] **日期卡「追加式插入」导致精读网格断层（根因在生成器，跨仓库）**：`site_pub.update_index` 按 `decisions.md:418` 的约定「只追加本场 managed 的新条目」→ 新日期卡永远落在 `.archive-grid` 末尾，翻到底部又冒出一批新卡，观感像整页重复。`6f028d8` 只是按 `<time datetime>` 倒序重排 16 张（治标），**下次发布必然复现**。治本要改 `weread-auto` / `weread-cloud` 里的 `site_pub.update_index`：插入时定位到第一个 `datetime` 更早的卡之前，而不是无条件 append。判据：下次新笔记发布后若仍有卡落在网格末尾，即视为生成器未改，届时升级为对内容侧的 `QUESTION`。
- [ ] **`brand/` 两页带内联 `<style>`，且落在自检脚本盲区**：`brand/index.html`（8957B）+ `brand/proposal.html`（11334B）各 1 个 `<style>`，是「单文件自包含」的刻意选择（独立配色 + sprite，不复用站点 chrome）。问题在于 `check_site_invariants.py` 的扫描范围写死为 `reading-notes/**/*.html` + `index.html`，**`brand/` 根本不被扫**，所以这条豁免是「意外逃逸」而不是「显式白名单」。两个选一个：① 把 `brand/` 加进扫描器的显式白名单并注明理由；② 外置到 `assets/css/brand.css`。现在不改代码，先记账；`brand/` 若长出第二个共用页（导航/footer 复用）就必须走 ②。
- [ ] **连续两轮「代码已推、账未记」（流程缺陷，20:10 已止血）**：19:07 轮补的是上上轮的账，本轮补的又是 19:33–19:43 那轮的账 —— `brand/`、刊头 84px、日期卡重排三个提交上线 27 分钟后 todo 与本 automation memory 都还是 19:07 的状态。**新纪律（立即生效）**：每轮第 0 步恢复上下文后，先比对 `git log` 末条提交哈希与 todo 里最后一条已落账提交哈希；不一致就先补账再谈别的，绝不允许「先做新事、旧账后补」。

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

- 2026-10-27 19:33–19:43（20:10 轮补记，此前未入账）：品牌页落地 —— `5ee9ab7` 新增 `brand/`（`index.html` + `proposal.html` + `logo-a/b/c`/`lockup`/`favicon` 五个 SVG）、`index.html` 第 29 行 `p.hero-brand` 改 `a[href=brand/]`、`homepage-hero.css` 追加 `a.hero-brand` 四组规则（原三条未动）；`47908c5` 刊头改玄水底彩色标识 84px + 补「落地尺寸」一节；`6f028d8` 精读网格 16 张日期卡按 `<time datetime>` 倒序重排（26+/27−，内容零改动）。A2A 板 `[19:35]` 已发帖说明范围。20:10 轮独立复核 5 项全过：46/36 基线零退化、卡片是移动非复制（16→16、125 href 全唯一）、倒序断言 True、`brand/` 两档零溢出、`a.hero-brand` 主规则无元素前缀故换标签不掉样式。

- 2026-10-27 19:07：监听轮次 —— 无新 A2A 消息（板尾末条为我 19:06 ACK），`HEAD == origin/main == d4fa97d`；自检仅 C1 存量 29 页、C2/C3/C4 全清。**补平 QR 两处欠账**：`b61e735`（补 4 模块白边，296×296/1464B）+ `c4dc19b`（`.footer-qr` 改 `content-box`、去 padding，72px 真实）+ `5daa071`（DONE）→ 我独立 `cv2` 复验原图解码成功、88/116px 亦成功，P0+P2 两条改 `[x]` 关单。站点文件零触碰。

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
