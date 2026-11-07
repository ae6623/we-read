# a2a.md — A2A 的 git 协议（产物站 · 指针页）

> **本仓 `ae6623/we-read` 是笔记前台**（静态 Pages），不是服务端。
> A2A 的**协议正文、监听器、任务执行与部署**都在引擎仓 `ae6623/we-read-auto`：
> <https://github.com/ae6623/we-read-auto/blob/main/a2a.md> ·
> <https://github.com/ae6623/we-read-auto/blob/main/AGENTS.md#5-a2a-协作agent-之间怎么说话>
>
> 本页只回答一个问题：**「板子在哪、我该去哪查」**。规则以引擎仓 `a2a.md` 为准，本页不另立一套。

---

## 一句话：A2A 是 git 提交事件板

不是聊天、不是 API 推送、不是实时消息。一方在板文件末尾追加一个消息块并 **push 进 `main`**，
另一方监听 `main` 上的新提交、读写给自己的块、处理后在同一处追加 ACK / DONE 并 push。

**只有进入权威 `main` 的提交才算事件**；本地未 push 的 commit、分支、控制台输出、日志都不算。
**Git 记录 / 提交成功 / 监听命中都不等于消息已送达**，需要通知人的事仍要在 Cue 私聊直报。

## 本仓为什么会有 A2A 文件

前台仓不跑服务，但**全体 Agent 共用的事件日文件物理上放在这里**——这是 auto 仓 `AGENTS.md` §5 的既定约定
（「给人和 book-admin 看的走 agent-communication 日文件」）。所以：

| 谁 | 在哪 | 干什么 |
|---|---|---|
| `ae6623/we-read`（本仓） | 前台 / 静态 Pages | **承载事件板文件**，只放内容与页面；不跑监听、不跑调度、不做业务 |
| `ae6623/we-read-auto` | 服务端 / 唯一代码真相源 | `a2a.md` 协议正文、`comm_watch.py` 监听器、`A2A-*.md` 引擎内部交接、任务执行与部署 |

> 给云端 Agent 发请求、让它去查消息，**发到本仓当日日文件是对的**；不要发到 auto 仓根目录的 `A2A-*.md`
> （那是引擎内部两个 Agent 的交接日志）。

## 板子路径（都在本仓）

| 用途 | 路径 |
|---|---|
| **共用事件日文件**（用户指令 / REQUEST / ACK / DONE / 开跑 / 收尾） | `skills/luoyu-reading/references/agent-communication/YYYY/MM/YYYY-MM-DD.md` |
| 稳定入口索引（只读，**不追加事件**） | `skills/luoyu-reading/references/agent-communication.md` |
| 当月导航（只列链接） | `skills/luoyu-reading/references/agent-communication/YYYY/MM/index.md` |
| 前端专用 A2A 板 | `skills/luoyu-reading/references/frontend-a2a.md` |
| 前端板监听脚本 | `scripts/a2a_frontend_check.py`（`--alias` / `--update` / `--peek N` / `--watch S`） |
| 协议细则 | `skills/luoyu-reading/references/` 下的 `reading-state-protocol.md`（事件通道）、`coordination.md`（串行写入）、`cross-team-coordination.md`（团队/角色别名） |

日文件按 **Asia/Shanghai 当天日期**取；事件一律追加到对应日文件**文末**，只追加、不改写、不删除他人记录。
条目标题：`### [YYYY-MM-DD HH:MM] <团队别名/角色别名> / <run-id 或 task-id> → TO <别名|ALL>`。

## 最小读取流程（会话开工必做）

```bash
git pull --rebase origin main          # 只拉 main；这一步就是「接收事件」
tail -60 skills/luoyu-reading/references/agent-communication/$(date +%Y/%m)/$(date +%Y-%m-%d).md
```
找到 `→ TO <你的别名|ALL>` 且未 ACK 的块 → 按 BODY 执行 → 同一日文件文末追加 ACK / DONE（带 commit sha）
→ 只 `git add` 该文件 → commit → push。被并发拒绝就先拉最新再合并增量，**禁止强推**。

前端板另跑一次：`python scripts/a2a_frontend_check.py --alias <你的别名> --update --peek 5`
（`--peek` 必带——历史上游标短路漏读过两条消息）。

## 监听方式：不用 5 分钟定时任务

服务端**已有现成监听器**，代码在 `we-read-auto/comm_watch.py`，**不需要另写一套**。
云端用纯 HTTP 模式（本仓是公开仓，读 `raw.githubusercontent.com` 零凭据，不需要 git 二进制或本地克隆）：

```bash
python comm_watch.py --http --baseline --self <你的别名>      # 首次建基线
python comm_watch.py --http --once --self <你的别名>          # 会话开始查一次
python comm_watch.py --http --watch --interval 20 --days 2 --self <你的别名>   # 常驻，命中即打印全文并退出唤醒
```

`--self` 必填（否则会把自己的帖子当外部消息来回刷）；它按「新增消息块」判定事件，
写 `data/comm_inbox.md`。本机有本地克隆时可用默认 git 模式（`git ls-remote` → `git log prev..sha`），
事件判定更严。完整参数与边界见引擎仓 `a2a.md` §5。

严格说 Git 没有客户端被动推送，云端 `--http --watch` 仍是 20 秒短周期探测、raw CDN 有短缓存；
要真·事件驱动需 GitHub Actions `on: push` 或 Webhook 推到云端应用——**这两项属于服务端 / 平台配置，不在前台仓实现**，
且需云端应用已部署。**另外云端 Agent 是会话不是常驻进程**，靠「服务端应用替它盯 + 后台任务退出通知 / Cue 通知」唤醒；
平台不支持常驻时，退路是平台定时器每 1 分钟跑一次 `--http --once`。会话开始的 `--once` + 看板尾仍是必做兜底。

## 铁律

1. 只有 `main` 上的新提交是事件，核对用 `git log origin/main`，不靠索引文件或 roster 推断。
2. Git 记录 ≠ 送达；失败 / 受阻 / 结果不确定必须在 Cue 私聊直报，无发送能力标「待通知」。
3. 只追加、不覆盖他人记录；共享写入前后 `git status` / `git diff --check`。
4. 没读完正文不要推进已读游标；定长轮询必带 `--peek`。
5. 只写适合公开的最少元数据：不写凭据、登录态、内部服务地址、绝对路径、私有日志、书籍全文。
6. **三段式回复，禁止沉默执行**（2026-11-07 13:07 `A2A-PROTOCOL-20261107-1307-three-stage-ack` 确立，细则见当日事件板；权威协议以 `we-read-auto/a2a.md` 为准，本条是既有 REQUEST→ACK 闭环的落地细化，不另立一套）：读到 `→ TO <你|ALL>` 的 REQUEST / PING / 指令后，**在下一个动作之前先回一条 `A2A-ACK` 收条**（`已收到 / 待办清单 / 状态 received|queued|blocked`），哪怕一步没做、哪怕注定做不了也要回；长任务可补 `A2A-PROGRESS`；做完再回 `A2A-DONE`（`结果 / 做了什么+证据 / 还有什么诉求 / 未解决项`）。**ACK 是收条不是完工报告**：禁止只回 DONE 不回 ACK、禁止用收条冒充完工、禁止等全部做完才第一次发声。

> 为什么加第 6 条：原协议把 ACK 写成完成回执，Agent 会憋到做完才回，导致 2026-11-07 11:38→13:07 一个半小时零回帖。收条与完工分开，链路才不会看起来「卡死」。

## 条目类型枚举（TYPE）：说「是什么」，不写「不是什么」

自 2026-11-07 13:17 `A2A-PROTOCOL-20261107-1317-type-enum-and-followup` 起，条目正文**第一行必须是 `- TYPE: <枚举值>`**。
禁止再写「不是阅读场次 / 不是新任务 / 不进未 ACK 清单 / 不代表亲读或完读」这类否定式套话——
语义由枚举隐含：只有 `SESSION_OPEN` / `SESSION_CLOSE` 与阅读场次相关，只有 `tracked=true` 进未 ACK 清单。
**历史条目不回改**，没有 `TYPE` 的旧条目按 id 前缀回退推断。

| 枚举 | 含义 | group | needAck | tracked |
|---|---|---|---|---|
| `USER_INSTRUCTION` | 用户本人下达的指令 | todo | 是 | 是 |
| `REQUEST` | 要求对方执行某件事 | todo | 是 | 是 |
| `PING` | 链路探测 | todo | 是 | 否 |
| `PROTOCOL` | 规则 / 口径 / 格式变更，TO ALL | todo | 是 | 否 |
| `PROTOCOL_NOTE` | 对既有纪律的细化 / 重申 | todo | 否 | 否 |
| `FOLLOWUP` | 「还在搞吗」超时催办 | todo | 是 | 否 |
| `ACK_RECEIPT` | 已收到 + 待办 + 状态（收条） | reply | 否 | 否 |
| `PROGRESS` | 长任务中途进度 | reply | 否 | 否 |
| `DONE` | 结果 + 做了什么 + 诉求 + 未解决项 | reply | 否 | 否 |
| `PONG` | PING 的回环确认 | reply | 否 | 否 |
| `FAILURE` | 失败 / 阻塞直报 | reply | 否 | 否 |
| `DEPLOY` | 应用上线 / 重启 / 地址变更 | other | 否 | 否 |
| `SESSION_OPEN` | 真实 AI 阅读场次开始 | other | 否 | 否 |
| `SESSION_CLOSE` | 真实 AI 阅读场次收尾 | other | 否 | 否 |
| `STATE_CHANGE` | registry / roster / 活动锁变更 | other | 否 | 否 |
| `UNCLASSIFIED` | 兜底，出现即补枚举 | other | 否 | 否 |

`needAck` = 对方是否该回收条；`tracked` = 是否进未 ACK 清单；`group` = 看板分组（要干什么 / 回复了什么 / 其他）。
**有新事件就加枚举**：先在表中加一行（并同步 `we-read-auto/a2a.md` 权威协议与控制台 `console.html` 的 `TYPES`），再用该枚举发帖；`UNCLASSIFIED` 不允许长期凑合。

## 超时与激活：别让对方静默

看板对每条 `tracked=true` 任务必须显示：**谁 → 谁**、**要干什么**、**发出时间**、**谁回了收到**、**收到后已过去多久还没完工**、**是否 DONE**。

| 情形 | 提示 | 标红 |
|---|---|---|
| 无收条 > 10 分钟 | 该催了 | > 30 分钟 |
| 已收条未 DONE > 30 分钟 | 还在搞吗 | > 60 分钟 |

催办用 `FOLLOWUP` 枚举，正文写「任务 id / 已等待多久 / 请回 ACK 收条或 PROGRESS 或 DONE」；
**同一任务每 30 分钟最多一条**，看板给出可复制话术，由本机主 Agent 或每小时播报任务追加并 push，不自动无限刷屏。
