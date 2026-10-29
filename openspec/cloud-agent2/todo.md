# cloud-agent2 · 待办（openspec）

维护人：`cloud-agent2`（= weread-cloud-agent-2 / WorkBuddy 独立账号 User2；部署源 `C:/Users/ROG/weread-cloud-new`，云端 `weread-daily-98024.app.workbuddy.host`）。
**只写本文件**，不碰其他角色的 todo。协议：[todo-protocol.md](../../skills/luoyu-reading/references/todo-protocol.md)（开工前登记、每完成一项 `[x]` 并单独 commit、卡住标 `⏸ 阻塞` 跳过）。

> 最后更新：2026-10-30 04:12（Asia/Shanghai）

## 当前状态

- 项目唯一源 = `ae6623/we-read-auto`；`weread-cloud` / `weread-cloud-new` 是同一项目部署到不同云端环境的目录副本，不是独立项目。
- agent-2 云端在线（HTTP 200），登录态已重导（11 cookie，`/api/check` ok=true），书架可读。
- 令牌：agent-2 自有，对 `ae6623/we-read` push=True。`ae6623/we-read-offline` 实测**不存在**（404 + `git ls-remote` Repository not found）——线上旧 config 指向它，publish 必失败；本轮保留本地 config 现值 `we-read.git`，publish 只新增《100个人生遗愿》产物、不覆盖任何已有文件。
- 工具链：openspec CLI **1.15.0 已全局安装**（`openspec --version` 通过）。
- 云端：部署成功（sandbox `df917fc4…`，域名 `weread-daily-98024` 不变，`verified:true`），重导 11 cookie 后 `/api/check` ok=true；`/api/compose/*` 上线；`cloud.enabled=false`（不自动跑阅读场次）。
- 本轮已提交 main：`26e6ccb`（todo）、`584762e`（第一本通读）、`82df3c7`（第二本 compose 产物）、`bc2653e7`（第一本精读页）。另有 agent-1 并发提交 `b7453a2`（首页卡片排序），非强制 PATCH 重试已扛住并发。

## 待办（本轮：部署 agent-2 云端 + 生产书架最新一本书）

### P0 · 部署
- [x] 读交接文档（最新接手必看 / HANDOFF v3）+ SKILL.md + coordination.md，确认角色=agent-2、可部署目录=`weread-cloud-new`（probe 属 agent-1，不碰）
- [x] 拉 A2A 最新 main（we-read `6bf64bf` / we-read-auto `9a9cbf9`），读 A2A-AGENT2.md 与 frontend-a2a 的 03:50 HANDOFF
- [x] 同步代码到 `weread-cloud-new`：从 `weread-cloud` 取 44 个文件（含 compose_book.py 27845B / 93KB web_app.py / 10-30 新版 overview_gen），从 we-read-auto origin/main 取 6 个新脚本；app.py 合并 probe 探针；vendor 离线包
- [x] config.json 只补缺键（read.only / compose / site.publish_mode=api / shared.local_only+snapshot_zip / cloud.enabled=false），保留 agent-2 自己的 token 与 repo_url
- [x] 本地校验同步后代码可 import（py_compile 关键文件）：44 文件全部编译通过
- [x] 部署 `weread-cloud-new` 到云端沙箱（WorkBuddy sites：python / installCmd / startCmd）：sandbox `df917fc4…`，`verified:true`
- [x] 部署后重导登录态（/api/auth/import）并验证 /api/check 与 /api/compose/status：11 cookie，check ok=true，compose/status 非 404

### P1 · 生产书
- [x] 确定书架最新两本 = 《100个人生遗愿》(3300199463) 与《买房让日本人幸福了吗？（译文坐标）》(3300042155)；第一本主仓无同名产物（纯新增），第二本主仓已有全套产物
- [x] 跑 compose：两本 outline/overview/publish 全绿（第一本 commit `584762e`；第二本 overview 命中「已有通读页不覆盖」、publish 提交 `82df3c7`）
- [x] 精读页：云端 `gen_mindmap.py` 缺失 + 无 GEMINI_API_KEY，compose 自带 mindmap 步骤不可用；改由本会话基于官方 AI 大纲四层结构自行结构化重算，复用站点 mmx-* 组件生成《100个人生遗愿》`mindmap.html`（34 章/206 要点/368 原句/密度 92%/34 条锚点逐字校验通过），commit `bc2653e7`，纯新增未覆盖任何已有产物。第二本主仓已有 `mindmap.html` + `notes/deep-read.html`，精读本就齐备
- [x] 在线验证：main 上三个 compose commit 已核；Pages `overview.html` / `outline.html` HTTP 200，`mindmap.html` 提交后 Actions 部署中（首次探测 404，待构建完复核）

### P2 · 收尾
- [x] A2A 日文件 `agent-communication/2026/10/2026-10-30.md` 追加本轮事件（只写公开最少元数据）
- [x] 汇总「搞得定/搞不定」结论给用户

## 阻塞与决策

- 决策：publish 目标用 `ae6623/we-read`（本地 config 现值，纯新增文件，非强制 PATCH refs + 422 重试保证并发安全）；`we-read-offline` 不存在，保留它只会让 publish 失败。不拿 agent-1 的 config 覆盖，不整目录扫描 diff。
- 已知限制：套装书（`CB_` 开头）AI 大纲接口返回空，做不了；本轮目标书是单本 epub，不受影响。
- 遗留（不阻塞、交索引维护方）：《100个人生遗愿》首页索引卡片的「精读」链接未补——按保守发布铁律索引由会话最全的本机维护，agent-2 未动 `index.html`。
- 遗留（交 agent-1）：云端线上旧 config 的 `shared.repo_url=ae6623/we-read-offline.git` 实测仓库不存在（404 + `git ls-remote` Repository not found）；本次沿用 agent-2 本地 config 现值 `we-read.git`。若要恢复 offline 绑定，请先创建该仓库。
- 遗留（交 agent-1）：云端 `gemini.enabled=false` 且无 `GEMINI_API_KEY`，`gen_mindmap.py` 在沙箱不可用；本轮精读由会话侧离线重算完成。
