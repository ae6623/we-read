# 交接文档 v3 · weread-auto 微信读书自动阅读

> 生成：2026-10-19 01:25（Asia/Shanghai）
> 位置：`C:\Users\ROG\WorkBuddy\2026-10-17-00-26-07\`
> **本版取代 v1（`交接文档-weread-auto.md`）与 v2（`交接文档v2-weread-auto.md`）**，那两份保留作历史，顶部已标注"已被 v3 取代"。
> 本版 = v2 正文 + 强模型逐条核实后的勘误（见 §11）。
> **2026-10-19 01:20 用户裁定：低级模型账号（账号 B）的云阅读「各自管各自的」——本账号不再尝试部署或操作 `weread-cloud-new` / `weread-daily-98024`，该云端由其自行处置；本账号只负责本机 `weread-auto` 与共享仓。（原「账号归属阻塞」章节据此关闭，见 §8.1）**

---

## ⚠️ 开局必读：先看这个，再动手

### A. 铁律（违反会覆盖别人或搞坏云端）

1. **改 `we-read` 前必须 `git pull --rebase origin main`**。另一个 Agent（「微信读书」/`wechat-reading-browser`/Cue）在并行读写同一套注册表，10-19 00:00 后仍在活跃提交。直接改会冲突/覆盖。
2. **只改自己的条目**。`book-registry.json` / `agent-roster.json` / 交接记录里，别人的条目一律只读；交接只写 commits/路径，不复制书籍正文。
3. **不要手动 `cp` 单文件到云端部署源**。统一 `sync_to_cloud.py` 整体同步（**例外**：`cloud_scheduler.py` 不在同步列表，必须手工 cp）。
4. **不要替他人/历史补记**。11:40 场收尾缺口、roster 时段口径，都交主引擎裁定。
5. **不要动账号 B 的云端**（`weread-cloud-new` / `weread-daily-98024`，用户 2026-10-19 01:20 裁定「各自管各自的」）。只读探测可以，别部署、别改它目录里的文件、别在它上面试功能。本账号的活是本机 `weread-auto` + 共享仓。

### B. 身份与环境

- 本机 `AGENT_ID = weread-auto`，云端 `= weread-auto-cloud`，由 `reading_state.deployment(cfg)` 按配置自动判定；笔记/注册表归属据此区分，两部署互不覆盖。
- 本机与云端**日常只应一个主跑**。本机 `WeReadDaily` 已 Disabled，实际只有云端在跑。

### C. 凭证与登录态

- `we-read` 仓库 **PUBLIC**：读（clone/fetch/ls-remote）零凭证。
- 写（push）需 token，存于 `weread-cloud-new/config.json` 的 `shared.token`；优先级 `WEREAD_GH_TOKEN` > `shared.token` > `site.github_token`。**令牌随部署源目录留在机器上**，重部署不用重新授权 git。
- **微信读书登录态**：每次沙箱回收/重部署后需重新导入。当前云端登录态有效（10-19 00:57 `/api/check` ok，7 秒返回）。导入必须 **JSON body 直传**，multipart（`-F`）会被 400 拒：
  ```bash
  curl -X POST -H "Content-Type: application/json" \
    --data-binary @C:/Users/ROG/weread-auto/weread-data/weread-auth.json \
    https://weread-daily-98024.app.workbuddy.host/api/auth/import
  ```
- 本机导出登录态：`python weread_daily.py login`（生成 `weread-data/weread-auth.json`）。

### D. 已知坑（全量，含 v2 之后新增）

1. 后台 Chromium 走系统代理报 `ERR_PROXY_CONNECTION_FAILED` → `open_context` 已加 `--no-proxy-server`。
2. `schtasks.exe` / COM 快捷方式被本机沙箱黑名单拦截 → 本机计划任务用 PowerShell `Register-ScheduledTask`。
3. `weread.lock` 互斥 + `STOP` 停止文件；profile 被占用时 `open_context` 快速失败而非挂死。
4. `readinfo` 的 `bookInfo.finished` 对未读完的书也返回 1 → **完读只认 `progress >= 100`**。
5. 新版网页阅读器 canvas 渲染 → 方向键 / PageDown 可翻页，点击/滚轮无效。
6. 本地 bare 测试仓库 HEAD 默认 master → 需 `git symbolic-ref HEAD refs/heads/main`。
7. 中文书名 slug 经 `[^a-z0-9-]` 过滤会吃掉大写字母 → 测试用可区分标题。
8. **沙箱出口到 github.com 经常性抖动**（10-18 一天 4 轮：05:3x / 19:22 / …）。三层兜底：`ensure_repo` fetch 三重试 + HTTP/1.1（`90af4a4`）、补报队列、陈旧锁恢复。看到 `registry_close_error` 先看队列接住没。
9. **roster 时段口径**：云端实际 06:00/19:00，roster 写 18:00 是错的，且每次 `roster_sync` push 会覆盖回错值。**以代码为准**（§3）。
10. **云端是单线程 dev server**：git 操作会阻塞 HTTP（10-19 00:57 发布触发 504）。长任务（发布/检查）走子进程，HTTP 层可能超时但子进程继续。
11. **重部署/沙箱回收会丢微信读书登录态**（git 令牌不丢）。见 §8.1。
12. **探针限制**：`/api/read_file` 只读 BASE_DIR 根目录、**拒含 `/` 的名字**（子目录读不到，返回 `bad name`）、返回「头+尾」拼接且**中间截断 20000 字符**，别拿它做全文比对。
13. **部署账号归属**：`weread-cloud` 属账号 A、`weread-cloud-new` 属账号 B（低模型的号），当前账号对两者都无权部署（`SITES_ACCOUNT_MISMATCH`）。**用户已裁定各自管各自的**：不再尝试部署账号 B 的云端，只读探测可以，别动它（§8.1）。
14. **`/api/diag/net` 会挂**：内部 git fetch 可能超过 60 秒无响应，别用它做快速健康检查，用 `/api/status` + `/api/beats`。

### E. 记录纪律

- 交接记录按日期写到 `we-read/skills/luoyu-reading/references/agent-communication/YYYY/MM/YYYY-MM-DD.md`，**不要再往索引 `agent-communication.md` 追加运行记录**（它已是纯导航）。
- 写**实际**起止时间，不把计划时间写成运行时间。提交前查 `git status` / `git diff --check` / `git diff --stat`，只提交本次涉及文件。

---

## 0. 一句话背景

多 Agent 协作的微信读书自动阅读项目：

- **`weread-auto`**（`C:\Users\ROG\weread-auto`）——本机代码源，Playwright 开网页版微信读书自动翻页、生成每日精读笔记。
- **`we-read`**（`C:\Users\ROG\we-read`，`https://github.com/ae6623/we-read.git`）——共享规范 + 注册表 + 发布站点（`https://ae6623.github.io/we-read/`）。**另一个 Agent 在并行读写同一套注册表**。
- 本机与云端各跑一份，共享注册表串行认领；当前本机任务已停用，**只有云端在跑**。

---

## 1. 角色分工（2026-10-18 定稿，已写进 SKILL.md）

| 角色 | 是谁 | 干什么 | 不干什么 |
|---|---|---|---|
| 微信读书主引擎 | `wechat-reading-browser`（浏览器 Agent / Cue） | 实时书架查看、**选书**、按 registry **认领**、跨 Agent **协调与冲突裁定** | — |
| 读书管理员 / 维护会话 | 本会话（weread-auto 维护方） | **只读汇报**：汇总 registry / roster / 交接记录，缺漏差异如实列报交主引擎 | 不浏览书架、不选书、不派活、不裁定冲突、不改他人条目、不自主触发手动场次 |
| 代码阅读 Agent（云端） | `weread-auto-cloud` | 按 roster 时段 + registry 协议跑场次，**续读自己 held 的在读书** | 不挑新书、不抢认领、不调排班 |

代码开关：`weread_daily.py` 的 `follow_main_engine`（默认 `True`）——云端只读两类书：① 用户显式指定 ② registry 本人 held 的在读书；无书可续就**不开读**，报告「等主引擎认领/分配」。

---

## 2. 资产清单（实测）

| 用途 | 路径 | 说明 |
|---|---|---|
| 共享仓（权威） | `C:\Users\ROG\we-read` | `ae6623/we-read` main；registry / roster / skill / 交接记录 |
| 代码仓（本机源） | `C:\Users\ROG\weread-auto` | HEAD `3574fe9`，工作区干净 |
| 云端部署源（新账号） | `C:\Users\ROG\weread-cloud-new` | 应用 `wbapp_jbAdqRxuUUKVPHr1M4XbLH`，域名 `weread-daily-98024` |
| 旧云端部署源 | `C:\Users\ROG\weread-cloud` | 旧账号，本会话与本账号均无法部署 |
| 云端控制台（在用） | https://weread-daily-98024.app.workbuddy.host | 登录态有效、有 registry 写权限 |
| 旧云端（僵尸/互备） | https://weread-cloud-probe.app.workbuddy.host | **仍在线但登录态过期**，场次 abort，不碰注册表 |
| 本机计划任务 | `WeReadDaily` | **State=Disabled**，触发器 06:00/18:00，LastRun 10-17 22:59 |

三个目录的 7 个 py 文件（`notes_gen` / `site_pub` / `reading_state` / `roster_sync` / `weread_daily` / `web_app` / `cloud_scheduler`）已 md5 一致——但**云端跑的还是 23:27 部署的 `633ccf2`，我修的两处 bug（`3574fe9`）还没上线**，原因见 §8.1。

> 凭据：两个 `config.json` 内含 github token，**不入库不外传**。本文档不记录任何令牌。

---

## 3. 排班真相

| Agent | 实际（代码/系统） | roster 记录 | 状态 |
|---|---|---|---|
| weread-auto-cloud | **06:00–06:59 / 19:00–19:59**（`cloud_scheduler.py` SLOTS，WINDOW_MIN=60） | 06:00-06:30 / **18:00-18:30** ❌ | 在用 |
| weread-auto（本机） | 触发器 06:00 / 18:00 | 同左 | **停用** |
| wechat-reading-browser | — | 07:00-08:00 / 14:00-15:00 | 在用 |

**以代码 19:00 为准。** roster 每次被云端 `roster_sync` push 覆盖回 18:00，光改 roster 没用。

---

## 4. 当前状态快照（2026-10-19 01:20 实测）

- 共享仓远端 main 已到 `1e7411d`（另一 Agent 10-19 00:00 后仍在提交）；**接手先 `git pull --rebase`**，本地当时落后 2 条。
- registry **revision 19**，`active_session: None`，状态干净。
- 云端 held：**《大转折：现代债务与可持续的增长》in_progress**（progress ≈70%）。
- 其他：住小房子的女人（weread-auto held）、世界这么大我想到处躺（browser held/paused）、大转向（browser held in_progress）、挪威极夜（completed）、因为贱所以生活艰辛（local_pdf，user_requested）。
- 云端进程健康：心跳 5 秒一跳（`/api/beats`），登录态有效（`/api/check` ok），无场次在跑，**下一场今天 06:00**。
- **git 通道仍坏**：`/api/diag/net` 60 秒无响应。06:00 那场收尾大概率还是写不进 git，继续靠补报队列（§6）。

---

## 5. 战绩与三条判断口径（最重要的一节）

### 2026-10-18 三场硬数据（服务端可查，非文档转述）

| 场次 | run_id | read_ok | read_fail | 页/翻页 | 时长 | 今日平台时长 |
|---|---|---|---|---|---|---|
| 11:40 | cloud-114025 | 17 | 0 | — | 688s | 9.5 → 18.0（+8.5）|
| 14:49（用户指定测试场）| cloud-144944 | 26 | 0 | 翻页 20 | 1040s | 18.0 → 31.3（+13.3）|
| 19:00 | cloud-190031 | 34 | 0 | 12 页 | 1185s | 31.3 → **48.3**（+17.0）|

同日三场已合并成一篇日期笔记（19:20 note_saved，49 分钟口径）。

### ⚠️ 三件事必须分开看

1. **阅读成功**：3/3 全成（read_ok 见上表，read_fail 全 0，笔记已存）。
2. **通知/收尾送达 git**：0/3 实时成功——三场收尾写 git 全因沙箱→github 抖动失败。补报队列救回 2 条（`64cdb97`=144944、`719cbc7`=190031），**11:40 场（cloud-114025）收尾至今永久缺口**。
3. **闭环成功**（阅读+实时收尾）：0/3。

**主引擎说「云端一次都没成功」只对了第 2、3 条，第 1 条是误判**——它按 git 里有没有收尾条目判断。判断一场是否真成功必须读：

- `GET /api/status` → `last_session` 的 `read_ok` / `read_fail` / `pages_captured` / `elapsed_sec` / `today_min_before` / `today_min_after`
- `GET /api/read_file?name=run_output.log` → 场次子进程日志

**git 里暂时没有收尾条目 ≠ 阅读失败。**

---

## 6. 通知链路与补报队列（2026-10-18 补齐）

1. **主通道 = git**：场次开始（认领）/结束（收尾）各写一条交接板条目进共享仓，其他 Agent 监听 git。
2. **控制台通知保留**：`record_notice` / toast / 结束简报。
3. **补报队列**：收尾写 git 失败 → 落盘 `data/pending_comm_events.json`（仓库外，重启不丢）→ 幂等重放（按 run_id 去重），时机：① 场次启动前 ② app 启动 ③ **调度器每 10 分钟独立线程**（场次进行中跳过）。

---

## 7. 发布链路（2026-10-19 发现断了两处，已修未部署）

**故障现象**：10-18 的笔记发不出站点，`site.enabled=false` 只是一层；真正断的是：

1. **`site_pub.git_publish` 裸 `git push` 无凭证**——`ensure_repo` 克隆后会把 remote 还原成干净 URL，所以 push 必 403。
2. **`git pull --rebase` 单发 120s 超时就把整次发布打回**（10-19 00:57 实测：pull 超时 → 发布失败）。

**已修（commit `3574fe9`，已同步到 `weread-cloud-new`，未部署）**：
- `_push_with_token`：推前把令牌一次性注入 remote URL、推后还原，不落 `.git/config`（本地 bare 仓实测通过）。
- `_sync_remote`：`fetch(180s) + rebase`，3 次重试，替代裸 pull。
- `_publish_token`：`shared.token` 优先，退回 `site.github_token`。
- **新增 `/api/notes/<path:name>` 下载路由**：此前笔记只在沙箱 `data/notes/`，`read_file` 拒子目录、索引页只发 `index.html`，**没有任何通道把笔记取出来**（孤本，沙箱回收即丢）。现在索引页里的相对链接在云端可直接点开/下载（限 notes 目录内，防路径穿越）。
- 本地 `weread-cloud-new/config.json` 的 `site.enabled` 已预设为 `true`，**部署后即自动生效**；线上开关我已改回 `false`（旧代码开着只会让 06:00 收尾多挂 120 秒再 403）。

---

## 8. 操作手册

### 8.1 部署（账号归属：用户已裁定各自管各自的，本节仅留事实）

```bash
# 本账号侧的完整发布链（代码已就绪，3574fe9 已同步进 weread-cloud-new）：
# 1) 改 C:\Users\ROG\weread-auto → git commit
# 2) 同步 7 文件到 weread-cloud-new
python sync_to_cloud.py
# 3) cloud_scheduler.py 不在同步列表 —— 手工 cp
cp cloud_scheduler.py /c/Users/ROG/weread-cloud-new/
# 4) 部署参数（仅账号 B 会话可执行）
#   appName=weread云端阅读 / directory=C:/Users/ROG/weread-cloud-new /
#   domainPrefix=weread-daily / language=python /
#   installCmd="pip install -r requirements.txt && python -m playwright install chromium" /
#   startCmd="python app.py"
# 5) 部署后必须重导登录态（见 §C）
```

**账号归属事实（2026-10-19 实测确认）**：
- `weread-cloud`（旧目录/旧应用 `weread-cloud-probe`）属于**账号 A**；`weread-cloud-new`（应用 `wbapp_jbAdqRxuUUKVPHr1M4XbLH`/`weread-daily-98024`）属于**账号 B**（低模型那个号）。
- 平台规则：**已发布应用与部署目录绑定在发布账号下**，换账号部署同目录直接 `SITES_ACCOUNT_MISMATCH` 拒绝，换域名前缀/换参数重试同样被拒。
- **用户 2026-10-19 01:20 裁定：各自管各自的。** 本账号不再尝试部署或改动账号 B 的云端（含其目录 `C:\Users\ROG\weread-cloud-new`——本账号改过的唯一一处 `config.json` 的 `site.enabled` 已恢复为 `false`）。`3574fe9` 已同步进该目录，账号 B 何时部署、是否部署由它自行决定；不部署则发布链路与笔记下载维持旧状。
- 10-18《大转折》笔记仍是孤本（只在账号 B 沙箱 `data/notes/`）。原抢救路径（本账号部署带下载路由的新代码）已随裁定关闭；该笔记能否保留取决于账号 B 对自己沙箱/部署的处置，**本账号不再主动抢救**。

### 8.2 日常查证

- `GET /api/status` — 状态与上一场数据
- `GET /api/read_file?name=run_output.log` — 场次日志（只读根目录、截断 20000 字符）
- `GET /api/notes/index` + 点笔记链接 — 看/下载笔记（需 `3574fe9` 已部署）
- `POST /api/check` — 只读体检登录态（约 7 秒）
- `POST /api/run`（无 body）— 手动触发一场；409 = 已有场次在跑，别重复触发
- 时长由 `config.json` 的 `read_minutes_min/max`（7–15 分钟 + 秒级抖动）随机决定，**不要指定时长**

---

## 9. 待办

1. **（已按用户裁定关闭）部署 `3574fe9`**——用户 2026-10-19 01:20 裁定「各自管各自的」，本账号不再部署账号 B 的云端。代码已就绪并同步在 `weread-cloud-new`，账号 B 自行决定；**本账号侧无需动作**。
2. **交主引擎裁定**：roster 云端 evening 口径统一 19:00（或确认「以代码为准」写进 `decisions.md`）。
3. **交主引擎裁定**：11:40 场（`2026-10-18-cloud-114025`）结束事件是否补记——**不代填他人/历史条目**。
4. **交主引擎裁定/知会**：旧云端 `weread-cloud-probe` 仍在线且按点打卡失败（登录态过期），本账号无法 unpublish，只能等它自己烂着或由账号 A 处理。
5. 验证补报队列分钟级送达：下次 06:00 场次结束后，确认结束事件数分钟内进 git（`3574fe9` 部署前这条大概率仍不达标）。
6. （可选）把 `gho_` 全仓 classic PAT 换成 fine-grained 只读 we-read。
7. （可选）修 `test_reading_state.py` 的 fixture 失配（未改 HEAD 上也挂，预置问题）。

---

## 10. 代码变更史（`94a21a8` 之后，全部已提交）

| commit | 内容 |
|---|---|
| `ea47e24` | derive_status 认 `web_auth_import_ok/fail` 事件 |
| `fc15d2b` | 阅读子进程独立会话 + 启动补报孤儿场次 |
| `24ef3fc` | `_local_run_active` 排除本进程自持的锁（修僵尸 active_session 卡死） |
| `ee1b241` | 每场时长区间随机 7-15 分钟 + 0-50 秒抖动 |
| `90af4a4` | `ensure_repo` fetch 三重试 + HTTP/1.1（修 GnuTLS -110） |
| `b2256a4` | preflight 的 `intended_title` 改 registry 权威优先 |
| `3d87a43` | 同步目标切到 `weread-cloud-new` + 留档计划任务备份 |
| `f5ef006` | follow 主引擎：停用自动选书 |
| `7dd5705` | git 通知补报队列 |
| `7751a22` | 修回归：follow 守卫误拦 held 书续读 |
| `f07f0fc` | 修盲区：close 基础条目提到 mutate 外，fetch 失败也能入队 |
| `633ccf2` | 调度器每 10 分钟独立线程补报 |
| **`3574fe9`** | **修发布链路（push 令牌注入 + fetch 重试）+ 新增笔记下载路由（未部署）** |

---

## 11. v2 → v3 勘误（强模型逐条核实后的修正）

v2 的事实准确率很高，以下为**补正与新增**：

1. **v2 说「部署生产前先确认（未经允许不得私自部署）」，但没写账号归属这个硬阻塞**。现已确认：当前账号对两个云端部署源都无权发布（§8.1）。~~这是接手第一件事~~ → **2026-10-19 01:20 用户裁定各自管各自的，本账号不再部署任何云端，此条关闭**；事实仍记录在 §8.1 以备复用。
2. **v2 未记录「笔记孤本且无下载通道」**。10-18《大转折》笔记只在沙箱 `data/notes/`，`read_file` 拒子目录、索引页只发 `index.html`，站点发布又关着——等于 10-18 全天阅读成果没有任何出口。已修代码（§7），**未部署**。
3. **v2 未记录「发布链路本身是断的」**：`site.enabled=false` 只是表层，`git_publish` 无令牌必 403、裸 pull 120s 超时必失败。已修代码（§7）。
4. **v2 的 P5「重部署必丢登录态」需修正为「沙箱回收/重部署可能丢」**：实测 10-18 23:27 那次部署后，`data/notes/`、`weread.log`、`run_output.log` 均存活（/workspace 是就地更新），登录态也在 23:28 重新导入过。**但不要因此赌它一定不丢**——部署后第一件事仍是验证 `/api/check`。
5. **v2 说本地 `probe_beat.json` `beats_total: 1` 像探针没跳**——那是本地测试残留；远端 `/api/beats` 5 秒一跳，正常。
6. **v2 待办第 1、2 项维持「交主引擎裁定」**，本版不代填。
7. **v2 §5 的 registry revision 17 已过时**，现为 19；且另一 Agent 在 10-19 00:00 后仍在提交，接手必须先 pull。

---

*接手第一步：`git pull --rebase` 拉最新 we-read main → 读 SKILL.md → 读 `agent-communication/2026/10/2026-10-19.md` → 只读探测 `GET /api/status` + `GET /api/beats` 确认账号 B 云端活着（**不要动它**，用户已裁定各自管各自的）→ 本账号的活：本机 `weread-auto`（计划任务仍 Disabled，是否恢复主跑待用户定）+ 共享仓。*
