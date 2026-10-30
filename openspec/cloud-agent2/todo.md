# cloud-agent2 · 待办（openspec）

维护人：`cloud-agent2`（= weread-cloud-agent-2 / WorkBuddy 独立账号 User2；部署源 `C:/Users/ROG/weread-cloud-new`，云端 `weread-daily-98024.app.workbuddy.host`）。
**只写本文件**，不碰其他角色的 todo。协议：[todo-protocol.md](../../skills/luoyu-reading/references/todo-protocol.md)（开工前登记、每完成一项 `[x]` 并单独 commit、卡住标 `⏸ 阻塞` 跳过）。

> 最后更新（旧）：2026-10-30 04:12（Asia/Shanghai）

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

## 轮次 · 2026-10-30 22:35 跟进 main 最新代码并重建沙箱

- [x] 拉 `ae6623/we-read-auto` origin/main `9285c9e`（较上轮 `9a9cbf9` 领先 11 提交），同步 45 个顶层 py + `overview_gen/` 10 文件 + `docs/` 12 文件到部署源
  - 新增：`gen_aiqa_from_outline.py`(20637) / `publish_deep_read.py` / `_regen_fake_coreask.py` / `gen_pending_manifest.py` / `overview_gen/mindmap_render.py`(15942，此前缺失的精读渲染器)
  - 升级：`gen_deep_read.py` 21794→24881（slug/书名双匹配，根治虚拟核心追问）、`gen_deep_read_batch.py`、`weread_daily.py` 150008→151000、`site_pub.py`、`weread_store.py` 6537→10780
- [x] 铁律校验：`web_app.py` 保持 93KB 版（main 上的 85398 未覆盖）；`compose_book.py`、`probe.py`、`config.json` 均未被覆盖
- [x] **坑（已修）**：main 的 `cloud_scheduler.py`(8219B) 只有 `start_scheduler`、**无 `start_compose_worker`**，直接部署会让 `app.py` ImportError 起不来 —— 已保留部署源版(11799B，含 worker)，`grep` 复核两个函数都在
- [x] 重打站点快照 `vendor/we-read.zip`：旧快照是 10-27，已落后三天；改用 `git archive origin/main` 导出干净副本（1093 文件/168MB）再打包，新指纹 `20261030-223336-69d0655f`（85MB），含主仓最新精读页与 `gen_mindmap.py`(34855)
- [x] 部署成功：sandbox `df917fc4…`、`verified:true`、域名不变；首页 HTTP 200 / 57KB；`/api/status`、`/api/compose/status`、`/api/books`、`/api/diag/gemini` 全 200
- [x] 登录态无需重导（部署后 `/api/check` 仍 ok=true，今日已读 20.8 分钟）；云端快照指纹已确认刷新为 `20261030-223336-69d0655f`
- [ ] ⏸ 遗留：云端 `GEMINI_API_KEY` 仍未配置（`/api/diag/gemini` key_configured=false），`gen_aiqa_from_outline` / `gen_mindmap` 的 LLM 通道不可用；按 `docs/mindmap-module-standard.md` 第 6 节应由云端模型亲自介入撰写真实内容

> 最后更新：2026-10-30 22:35（Asia/Shanghai）

## 轮次 · 2026-10-31 01:05 云端版本号 + 精读改离线导入通道并发布

用户口径（本轮的硬约束）：**只跑云端，本机不动；云端代码保持最新；云端留一个版本号跟最新提交对比。**

- [x] 版本标记落地
  - [x] `build_version.py` → `VERSION.json`（engine/site 提交 + 快照指纹 + 9 个运行时文件 md5 + built_at）
  - [x] `GET /api/version`：读 VERSION.json、重算运行时 md5 查漂移、带 token 实时比 `api.github.com` 的 main（匿名会 403/404）
  - [x] 修 sha 比较：本地 `[:8]` vs 上游 7 位导致永远 `stale` → 统一 `[:7]`
  - [x] 线上实测 `engine=54cace7 site=a5be4bd stale=false behind={engine:false,site:false} drift=[]`
- [x] 快照重建：`git archive origin/main` → `/c/tmp/we-read-snap`（1093 文件），`make_snapshot.py --repo … --out vendor/we-read.zip` → 指纹 `20261031-004335-2bda18ee`（83.4MB）
- [x] 引擎代码对齐：部署源顶层 py 与 `we-read-auto@54cace7` 逐文件比对，除 `cloud_scheduler.py`(11799B，含 `start_compose_worker`)、`web_app.py`(96KB) 外**全部一致**（其余差异只是 CRLF）；部署版路由是引擎版超集，没丢东西
- [x] 精读离线通道（云端到 Google 不通的解法，符合 mindmap 标准第 6 节）
  - [x] `data/import/100-ge-ren-sheng-yi-yuan.json`（14KB，thesis + 6 主干组 + 34 章 gist/role/anchor）
  - [x] `step_mindmap` 检测到该文件 → `gen_mindmap.py --import-batch <json> --write`（纯渲染、零 LLM）
  - [x] `gen_mindmap.py` 恢复 `render()`/`from_batch()`（站点仓库某次重构把它们整段删了，四个入口全 NameError）；补 `from_batch` 的 anchor 逐字校验
  - [x] `build_ctx` 补 `_outline_from_json` 回退（compose 只写 outline.json 不入库）
  - [x] `_chapter_html` 锚点块：原来只在「本章无小节」时才输出 → 改成有 anchor 就输出（34/34）
  - [x] `_page_stats` 改按 ctx 实算并 clamp 100（旧 JSON 的 with_quote 口径不一致，画出 179% 的溢出条）
- [x] 排障（4 个都修了）
  - [x] 残留 `weread.lock` 的 pid 在容器重建后被复用 → `os.kill(pid,0)` 通过 → 锁永远等 25 分钟；`run_book` 直接 return 且不留痕。加 `/api/diag/locks`（GET 详情 / POST clear）+ `last_status=blocked`
  - [x] 单跑 `mindmap` 跳过 `ensure_repo_ready` → 旧快照 → 0.2s「库中无大纲」退出 0 记 ok；改成无条件先 ensure
  - [x] `need_browser` 把 mindmap 也算进去（`gen_mindmap.py` 无任何 playwright 调用）→ 改成只看 `outline`
  - [x] 单跑 `publish` 时 `steps_done=[]` → 「没有可发布文件」；回退成「最近一次成功产物步骤」
  - [x] `step_mindmap` 成败改看 returncode（原来只看文件存在，崩了也 ok），日志带 `import_batch/size/tail`
- [x] 云端产出并发布：《100个人生遗愿》`章=34 主干=6 密度=92% 锚点缺=0`，123,596B，commit `2ff4cec`（只提交这一个文件）
- [x] 线上复核：Pages 200 / 123,596 字节；34 章块 / 34 锚点 / 153 个 details 全闭合 / 密度条 `width:92%`
- [x] 部署后重导登录态：`POST /api/auth/import` → 11 cookie，`ok=true`
- [x] A2A 日文件 `agent-communication/2026/10/2026-10-31.md` + 月索引
- [x] 本轮 `make_snapshot.py` 默认 `--out` 写死成 agent-1 目录（`weread-cloud/vendor/we-read.zip` 被覆盖成新快照）→ 已在 A2A 声明，建议改默认值
- [ ] ⏸ `backfill_modules.py`（higher/verify/thennow/aiask/coreask）已同步进部署源，但**没接进 compose 步骤**；《文化苦旅》等仍有模板假 core-ask
- [ ] ⏸ 云端仍无 `GEMINI_API_KEY`、到 Google 不通 → 一切 LLM 步骤走离线导入通道（需要会话侧先写 `<slug>.json`）
- [ ] ⏸ 《100个人生遗愿》不在 `reading-notes/index.html` 归档索引里（站首页有卡片）；索引归会话最全的本机维护，agent-2 不碰
- [ ] ⏸ `ae6623/we-read-offline` 仓库仍不存在（线上旧 config 指向它）

## 轮次 · 2026-10-31 01:22 官方 API key 接入 + 跑书安全性加固

用户给了微信读书官方 skill 的 `wrk-` key（**不需要登录态**，用户明说云端和本机都要）。

- [x] key 落位三处：本机 `~/.weread-auto-api-key`、部署源 `weread-cloud-new/weread-api-key.txt`（随部署上传）、顺手给 `weread-cloud/` 也放一份；`.gitignore` 已加两行
- [x] 新增 `GET /api/diag/weread`：报 key 来源（env / home / deploy_file）、书名作者评分、章节数、热门划线总数
  - 云端实测：`key_configured=true`（deploy_file）、40 章、381 条热门划线、最热 1404 人
- [x] **修封装 bug**：`best_bookmarks` 网关默认只回 20 条，必须显式传 `maxIdx`（400 → 381 条一次取完）；已提交引擎 main `341fe963`
- [x] **修限流**：连续请求网关回 **HTTP 499**（不是 JSON 错误码），逐章循环必中，静默 45s 才恢复。`call()` 加 1.2s 全局节流 + 499 指数退避重试（6/12/24s），已提交 `609be02f`。实测 40 章逐章拉取 0 失败，35 章有划线、366 条
- [x] 产出 `data/import/100-ge-ren-sheng-yi-yuan.bookmarks.json`（40 章 / 366 条官方原文 + 划线人数），留作锚点校验与后续升级的原料
- [x] **跑书安全加固**：`step_mindmap` 在没有 `<slug>.json` 且 **Gemini TLS 不可达**时快速失败（`_gemini_reachable()` 做 TLS 握手探测，不是只 connect——本机 TCP 通但 TLS 被掐，只看 connect 会误判）。负向实测《买房让日本人幸福了吗》→ 50 秒内 `ok=false` 并说明「没有 data/import/xxx.json，且云端到 Gemini 不通」，不再空转 25 分钟、不动已有页面
- [x] 幂等验证：《100个人生遗愿》重跑精读 0.1s → 123,596B / 34 章 / 锚点缺 0，与线上完全一致；再跑 publish → **「无变更」**，没产生空提交
- [x] 部署后回归：`/api/version` `stale=false`、`drift=[]`、engine `c2e7a4e`（代码提交是 `609be02`，`c2e7a4e` 只是 agent-1 新加的 `A2A-WEREAD-AUTO2.md` 文档）；登录态重导 11 cookie

> 最后更新：2026-10-31 01:22（Asia/Shanghai）


> 最后更新：2026-10-31 01:05（Asia/Shanghai）

