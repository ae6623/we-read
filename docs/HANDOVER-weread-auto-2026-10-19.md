# weread-auto 交接文档（2026-10-19 00:35 · 换号/换模型接手用）

> 交接人：weread-auto 维护会话（WorkBuddy，2026-10-18 全天在线）
> 接手对象：任何继续维护 weread-auto（本机代码 + 云端阅读）的 Agent / 人
> 事实基准时间：2026-10-19 00:35（Asia/Shanghai），本文所有状态均为当时实测，非推测

---

## 0. 一句话现状

**云端能用，代码是好的，今天三场阅读全部成功。** 真正的遗留问题是「结束事件进 git 不及时」导致外部监听方误判为失败——已在 2026-10-18 深夜修完并部署。本机版停用，实际只有云端在跑。

---

## 1. 角色分工（别越界，这是硬规则）

| 角色 | 是谁 | 干什么 | 不干什么 |
|---|---|---|---|
| **微信读书主引擎** | `wechat-reading-browser`（浏览器 Agent） | 实时书架查看、**选书**、按 registry **认领**、跨 Agent **协调与冲突裁定** | — |
| **读书管理员 / 维护会话** | 本会话（weread-auto，WorkBuddy） | **只读汇报**：汇总 registry / roster / 交接记录，缺漏差异如实列报 | 不浏览书架、不选书、不派活、不裁定冲突、**不改他人条目**、不自主触发手动场次 |
| **代码阅读 Agent（云端）** | `weread-auto-cloud`（weread-daily-98024） | 按 roster 时段 + registry 协议跑场次，**只续读自己 held 的在读书** | 不自主挑新书、不抢认领、不调排班 |

权威规则在共享仓：`skills/luoyu-reading/SKILL.md`（含「主引擎与读书管理员」「weread-auto 侧的角色落位」）、`references/coordination.md`、`references/reading-state-protocol.md`。**先读 SKILL.md 再动手。**

关键代码开关：`weread_daily.py` 的 `follow_main_engine`（默认 `True`）——只读两类书：①用户显式指定（`book_title` / `reader_url`）②registry 里本人 held 的在读书；无书可续就**不开读**，如实报告「等主引擎认领/分配」。原三级自动选书兜底全部停用。

---

## 2. 资产清单（路径都是实测）

### 仓库
| 用途 | 路径 | 说明 |
|---|---|---|
| 共享仓（权威） | `C:\Users\ROG\we-read` | github `ae6623/we-read`，main 分支；registry / roster / skill / 交接记录都在这 |
| 代码仓（本机源） | `C:\Users\ROG\weread-auto` | HEAD `633ccf2`，工作区干净 |
| 新云端部署源 | `C:\Users\ROG\weread-cloud-new` | **本账号唯一可部署**的目录 |
| 旧云端部署源 | `C:\Users\ROG\weread-cloud` | 旧 WorkBuddy 账号，**本会话无法部署**（只能从旧账号会话重部署） |

三个目录的 `weread_daily.py` / `reading_state.py` / `web_app.py` / `cloud_scheduler.py` 已 md5 校验一致。

### 云端
- **新云端（在用）**：https://weread-daily-98024.app.workbuddy.host — 有登录态（9 cookie）、有 registry 写权限、实际出阅读成绩
- **旧云端（互备）**：https://weread-cloud-probe.app.workbuddy.host — 部署源已同步最新代码但**无法从本会话重部署**；无登录态，场次只会登录检查 abort，**不碰注册表，零风险**

### 本机
- Windows 计划任务 `WeReadDaily`：**State = Disabled**（停用）。触发器 06:00 / 18:00，上次运行 10-17 22:59，结果 0。要启用得先问用户。

> ⚠️ 凭据：`weread-cloud-new/config.json` 内含 github 令牌与云端配置，**不入库、不外传**。登录态文件 `weread-auto/weread-data/weread-auth.json`。本文档不记录任何令牌。

---

## 3. 排班真相（roster 与代码口径不一致，按代码）

| Agent | 代码/系统实际 | roster 记录 | 状态 |
|---|---|---|---|
| weread-auto-cloud | **06:00–06:59 / 19:00–19:59**（`cloud_scheduler.py` SLOTS） | 写的是 06:00-06:30 / **18:00-18:30** ❌ | 在用 |
| weread-auto（本机） | 计划任务触发器 06:00 / 18:00 | 06:00-06:30 / 18:00-18:30 | **停用** |
| wechat-reading-browser | — | 07:00-08:00 / 14:00-15:00 | 在用 |

**以 19:00 为准，别信 roster 的 18:00。** 原因：roster 每次被云端 `roster_sync` push 覆盖回 18:00。改的时候必须同时改 roster 和代码，否则会被覆盖回去。

---

## 4. 共享状态快照（registry revision 17，`active_session: None`，状态干净）

| 书 | 状态 | 归属 | claim |
|---|---|---|---|
| 大转折：现代债务与可持续的增长 | in_progress | **weread-auto-cloud** | held |
| 住小房子的女人 | in_progress | weread-auto | held |
| 世界这么大，我想到处躺 | paused | wechat-reading-browser | held |
| 大转向：世界如何步入现代 | in_progress | wechat-reading-browser | held |
| 挪威极夜：独处时才能成为自己 | completed | — | released |

---

## 5. 2026-10-18 实际战绩（三场全成功，零中断）

| 场次 | run_id | 上报成功 | 失败 | 页/翻页 | 实际时长 | 今日平台时长 |
|---|---|---|---|---|---|---|
| 11:40 | cloud-114025 | 17 | 0 | — | 688s | 9.5 → 18.0（+8.5）|
| 14:49（用户指定测试场）| cloud-144944 | 26 | 0 | 翻页 20 | 1040s | 18.0 → 31.3（+13.3）|
| 19:00 | cloud-190031 | 34 | 0 | 12 页 | 1185s | 31.3 → **48.3**（+17.0）|

**取证方式**（别靠记忆，靠这两个）：
- `GET /api/status` → `last_session`：`run_id` / `read_ok` / `read_fail` / `pages_captured` / `elapsed_sec` / `today_min_before` / `today_min_after`
- `GET /api/read_file?name=run_output.log` → 场次进程日志，逐条事件（`session_start` / `read_report` / `note_saved` / `session_end` / `registry_closed` / `user_notice`）

---

## 6. 通知链路（重点，今天踩的坑都在这）

1. **主通道 = git**：场次开始（认领）和结束（收尾）各写一条交接板条目进共享仓，读书管理员/其他 Agent 监听 git 即可。
2. **控制台通知保留**：`record_notice` / toast / 结束简报，一条没动。
3. **补报队列（2026-10-18 新加）**：收尾写 git 失败 → 条目落盘 `data/pending_comm_events.json`（仓库外，重启不丢）→ 三种时机幂等重放：①场次启动前 ②app 启动 ③**调度器每 10 分钟独立线程**（`cloud_scheduler.py` `FLUSH_INTERVAL_SEC=600`，场次进行中跳过）。按 `run_id` 去重，交接板已有就跳过。

**为什么需要它**：今天三场的结束事件进 git 全不及时——11:40 没进、14:49 手动补、19:00 拖到 23:24 才重放。监听 git 的视角就是「一次都没成功」。**阅读成功 ≠ 通知送达，这两件事必须分开说。**

---

## 7. 已知问题与坑（按优先级，别重复踩）

**P1 沙箱出口到 github.com 经常性抖动**（今天 4 轮：05:3x、11:55、15:10、19:22），几乎全砸在收尾阶段。已有三层兜底：`ensure_repo` 的 HTTP/1.1 + 3 次 fetch 重试、补报队列、陈旧锁恢复。看到「registry_close_error」不用慌，看队列有没有接住。

**P2 roster 时段口径与代码不一致**（18:00 vs 19:00）。`roster_sync` 每次 push 会覆盖。改前想清楚，或者接受「代码为准」。

**P3 11:40 场（cloud-114025）结束事件从未进 git**——历史缺口，需主引擎裁定是否补记。我不代填他人/历史条目，这是角色红线。

**P4 云端是单线程 dev server**：git 操作会短暂阻塞 HTTP（今晚 23:22 出现过 504/超时，实为正在做 git 补报提交）。flush 已挪独立线程；但场次进程跑的时候控制台仍可能短暂无响应。

**P5 重新部署必丢微信读书登录态** → 必须重新导入：
```
curl -X POST -H "Content-Type: application/json" \
  --data-binary @C:/Users/ROG/weread-auto/weread-data/weread-auth.json \
  https://weread-daily-98024.app.workbuddy.host/api/auth/import
```
**必须用 JSON body 直传，multipart（-F）会被 400 拒。** git 令牌随目录保留，不用重授权。

**P6 探针限制**：`/api/read_file` 只能读 BASE_DIR **根目录文件**，不穿子目录（`data/pending_comm_events.json` 读不到，返回 `bad name`）；返回内容是「头 + 尾」拼接、**中间截断 20000 字符**，别拿它做全文比对。

**P7 测试现状**：`test_dual_merge.py` PASS；`test_reading_state.py` 有一条「甲书」fixture 断言失败——**在未改动的 HEAD 上同样挂**（预置失配，与任何改动无关）；`test_notify.py` 需 playwright，本机缺依赖跑不了。

---

## 8. 日常操作手册

### 改代码 → 部署
1. 改 `C:\Users\ROG\weread-auto` 下的源码 → `git commit`
2. `python sync_to_cloud.py` → 同步 7 个文件到 `weread-cloud-new`
   （`notes_gen.py` / `site_pub.py` / `reading_state.py` / `roster_sync.py` / `weread_daily.py` / `web_app.py` / `templates/index.html`）
3. **云端专属文件不在同步列表**：`cloud_scheduler.py` 要手工 `cp` 到 `weread-cloud-new` 和 `weread-cloud`
4. 部署（WorkBuddy 站点部署）：
   `appName=weread云端阅读` / `directory=C:/Users/ROG/weread-cloud-new` / `domainPrefix=weread-daily` / `language=python` / `installCmd="pip install -r requirements.txt && python -m playwright install chromium"` / `startCmd="python app.py"`
5. 部署完**必须重导登录态**（P5）

### 日常查证
- 状态：`GET /api/status`
- 场次日志：`GET /api/read_file?name=run_output.log`
- 手动触发一场：`POST /api/run`（无 body）；返回 409 说明已有场次在跑，别重复触发
- 云端随机时长由 `config.json` 的 `read_minutes_min/max`（7–15 分钟 + 秒级抖动）决定，**不要试图指定时长**

### 写交接记录（格式已改，别写错地方）
- **按日期写到** `skills/luoyu-reading/references/agent-communication/YYYY/MM/YYYY-MM-DD.md`（2026-10-18 起已按年/月/日拆分归档）
- **不要再往索引** `agent-communication.md` 追加运行记录（它现在是纯导航）
- 条目标题：`### [YYYY-MM-DD HH:MM] <Agent> / <run-id>`
- 新日期文件要在当月 `index.md` 加链接；跨日结束写结束当天、沿用同一 run_id
- 只写本人事件，不覆盖他人记录；push 被拒先 `git pull --rebase`，**禁止强推**

---

## 9. 红线（违反会破坏协作，不是建议）

1. **不自主选书、认领、派活、调排班** —— 全部 follow 主引擎结论。
2. **不改其他 Agent 的 registry / roster / 交接条目**，只改自己条目。
3. **完读只认进度 ≥ 100%**；不确定写 `needs-confirmation`，不把百分比猜成页码。
4. **不把令牌、登录态、私人聊天写进任何入库文档**；跨书综合与私有原始记录不入 git / Pages。
5. **部署前先确认**（用户有明确规则：未经允许不得私自部署到生产）。
6. **只触发和验证时不得顺手改代码**；要改就说清楚改了什么、为什么。

---

## 10. 待办清单（交给主引擎 / 接手者裁定）

1. **roster 时段口径对齐**：把 `weread-auto-cloud` evening 统一成 19:00-20:00，或确认「以代码为准」并写进 decisions.md。
2. **11:40 场（cloud-114025）结束事件**是否补记 —— 交主引擎裁定，我不代填。
3. **旧云端 weread-cloud-probe 重部署**：需从旧 WorkBuddy 账号会话操作，本会话做不了。当前零风险（无登录态）。
4. **验证补报队列分钟级送达**：明天 06:00 场次结束后，确认结束事件在数分钟内进 git（不再拖数小时）。
5. （可选）修 `test_reading_state.py` 的 fixture 失配。

---

## 11. 今天的代码变更（全部已提交 + 已部署）

| commit | 内容 |
|---|---|
| `f5ef006` | follow 主引擎：停用自动选书，无 explicit 书且无 held 书时不开读 |
| `7dd5705` | git 通知补报队列（落盘 + 幂等重放），控制台通知保留 |
| `7751a22` | **修回归**：follow 守卫缺 `target_href is None` 条件，误拦 held 书续读（14:44 场次 open_reader_failed）|
| `f07f0fc` | **修盲区**：close 基础条目提到 mutate 外构造，fetch 阶段失败（mutate 未执行）也能入队 |
| `633ccf2` | 调度器每 10 分钟独立线程补报，结束事件不再迟到数小时 |

共享仓侧：角色落位写进 SKILL.md（`e763537`）、双云端适配登记（`f169a82`）、云端战绩核查（`5ef02ac`）。

---

*接手第一步：拉最新 `we-read` main → 读 SKILL.md → 读 `agent-communication/2026/10/2026-10-18.md` → `GET /api/status` 看云端活着没 → 再决定动不动手。*
