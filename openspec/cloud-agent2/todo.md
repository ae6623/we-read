# cloud-agent2 · 待办（openspec）

维护人：`cloud-agent2`（= weread-cloud-agent-2 / WorkBuddy 独立账号 User2；部署源 `C:/Users/ROG/weread-cloud-new`，云端 `weread-daily-98024.app.workbuddy.host`）。
**只写本文件**，不碰其他角色的 todo。协议：[todo-protocol.md](../../skills/luoyu-reading/references/todo-protocol.md)（开工前登记、每完成一项 `[x]` 并单独 commit、卡住标 `⏸ 阻塞` 跳过）。

> 最后更新：2026-10-30 04:00（Asia/Shanghai）

## 当前状态

- 项目唯一源 = `ae6623/we-read-auto`；`weread-cloud` / `weread-cloud-new` 是同一项目部署到不同云端环境的目录副本，不是独立项目。
- agent-2 云端在线（HTTP 200），登录态已重导（11 cookie，`/api/check` ok=true），书架可读。
- 令牌：agent-2 自有，对 `ae6623/we-read` push=True。`ae6623/we-read-offline` 实测**不存在**（404 + `git ls-remote` Repository not found）——线上旧 config 指向它，publish 必失败；本轮保留本地 config 现值 `we-read.git`，publish 只新增《100个人生遗愿》产物、不覆盖任何已有文件。
- 工具链：openspec CLI 安装中；装不上按 [tooling-setup.md](../../skills/luoyu-reading/references/tooling-setup.md) 第 4 节降级，纯文本 todo 照用。

## 待办（本轮：部署 agent-2 云端 + 生产书架最新一本书）

### P0 · 部署
- [x] 读交接文档（最新接手必看 / HANDOFF v3）+ SKILL.md + coordination.md，确认角色=agent-2、可部署目录=`weread-cloud-new`（probe 属 agent-1，不碰）
- [x] 拉 A2A 最新 main（we-read `6bf64bf` / we-read-auto `9a9cbf9`），读 A2A-AGENT2.md 与 frontend-a2a 的 03:50 HANDOFF
- [x] 同步代码到 `weread-cloud-new`：从 `weread-cloud` 取 44 个文件（含 compose_book.py 27845B / 93KB web_app.py / 10-30 新版 overview_gen），从 we-read-auto origin/main 取 6 个新脚本；app.py 合并 probe 探针；vendor 离线包
- [x] config.json 只补缺键（read.only / compose / site.publish_mode=api / shared.local_only+snapshot_zip / cloud.enabled=false），保留 agent-2 自己的 token 与 repo_url
- [ ] 本地校验同步后代码可 import（py_compile 关键文件）
- [ ] 部署 `weread-cloud-new` 到云端沙箱（WorkBuddy sites：python / installCmd / startCmd）
- [ ] 部署后重导登录态（/api/auth/import）并验证 /api/check 与 /api/compose/status

### P1 · 生产书
- [ ] 确定书架最新一本 = 《100个人生遗愿》（bookId 3300199463，updateTime 1793302291），确认主仓 `reading-notes/books/` 无同名产物（纯新增）
- [ ] 跑 compose：outline -> overview -> publish，查 /api/compose/status 与 compose_output.log
- [ ] (可跳过) 若 publish 因目标仓库/权限受阻：标阻塞原因，保留 outline+overview 产物，跳过不卡点，汇总时说明
- [ ] 在线验证：GitHub commit 与 Pages 页面

### P2 · 收尾
- [ ] A2A 日文件 `agent-communication/2026/10/2026-10-30.md` 追加本轮事件（只写公开最少元数据）
- [ ] 汇总「搞得定/搞不定」结论给用户

## 阻塞与决策

- 决策：publish 目标用 `ae6623/we-read`（本地 config 现值，纯新增文件，非强制 PATCH refs + 422 重试保证并发安全）；`we-read-offline` 不存在，保留它只会让 publish 失败。不拿 agent-1 的 config 覆盖，不整目录扫描 diff。
- 已知限制：套装书（`CB_` 开头）AI 大纲接口返回空，做不了；本轮目标书是单本 epub，不受影响。
