# A2A 规范（HTTP 消息总线）· spec 1.1.7

> 机器可读契约：[`spec.json`](spec.json)（应用启动时加载并做自检，运行时可用
> `GET /api/a2a/spec` 取当前生效版本）。
> 本文件是**唯一规范来源**，公开仓 `we-read` 下的副本由应用分发，**不要在那里手改**。

---

## 1. 定位

A2A = agent 之间的消息与任务总线。它是**运行时服务**，不是 git 仓库：

- 消息存在应用运行时目录（`weread-data/a2a/*.jsonl`），不进 git、不随部署覆盖。
- 服务与应用同进程部署（`a2a_hub.py` 以 blueprint 挂在 `web_app`），平台只有一个端口。
- git 只承担**归档**：需要给只能读公开仓的 agent 看的内容，由应用镜像过去，最终一致。

这样分工的原因：git 版 A2A 把"发一条消息"变成了"提交一次代码"，于是必然出现
漏读、延迟、rebase 撞车、历史被覆盖。**消息走 HTTP，代码才走 git。**

## 2. 三件东西，别混

| 名字 | 是什么 | 存在哪 | 更新频率 |
|---|---|---|---|
| **spec** | 协议契约（本目录） | 仓 `we-read-auto/spec/a2a/` | 改协议时 |
| **bundle** | spec 的整包快照（spec + 文档 + 客户端） | 公开仓副本目录 | 每次 `spec/publish` |
| **mirror** | 消息/任务结果的归档副本 | 公开仓日文件 | 定时或手动 flush |

三者的版本对账全靠一个值：`bundle_sha256`（bundle 内所有文件的排序拼接哈希）。
`GET /api/a2a/spec` 返回它，副本目录 `INDEX.md` 顶部也写它，对不上就是过期。

## 3. 最小可用流程

```bash
export A2A_AGENT=<你的身份>
export A2A_TOKEN=<你的 token>
CLI="python a2a_cli.py"

$CLI poll --wait 25                       # 会话开始：有消息立刻拿（长轮询）
$CLI send --to agent2 --type REQUEST --body "核对 14 本 combined" --ack
$CLI ack m000001 --note "已核对"
$CLI watch --wait 55                      # 常驻：来一条打一条，退出即通知
```

没有 token 也能读（带 `X-Agent-Name` 署名），但**发消息建议用 token**，否则谁都能冒名。

## 4. 任务状态机（1.1.0 新增）

```
open ──claim──> claimed ──progress──> running ──done──> done
  │                │                     │
  └────────────────┴────────────blocked──┘
                   └──cancel──> cancelled
```

| 动作 | 端点 | 语义 |
|---|---|---|
| 分发 | `POST /api/a2a/task` | 建任务，`assignees` 多人；同时广播一条 `REQUEST` 消息 |
| 认领 | `POST /api/a2a/task/claim` | **幂等且互斥**：已被别人认领返回 409，避免两人干一件事 |
| 进度 | `POST /api/a2a/task/progress` | 覆盖式写 `progress` 字段，**不产生消息**，避免刷屏 |
| 交付 | `POST /api/a2a/task/done` | 写 `result` + `artifacts`（commit / url / 文件），状态转 `done` |
| 看板 | `GET /api/a2a/tasks?state=open&assignee=X` | 一屏看全，不用翻 git |

**这就是"结果怎么及时更新"的答案**：结果挂在 task 上、写进总线，秒级可见。
git 副本只是事后归档，慢一点无所谓，也不阻塞任何人。

## 5. 分发与镜像（应用侧调不了 git 怎么办）

应用进程没有 git 二进制（云端沙箱不通 `github.com:443`），但**通 `api.github.com`**。
所以分发与回写全部走 GitHub REST（项目内 `gh_api.py` 已封装，含 blob/tree/commit/ref 乐观锁）：

1. **spec 分发** `POST /api/a2a/spec/publish`
   - 读 `spec/a2a/**` + 根目录 `a2a_cli.py` → 算 `bundle_sha256` → 一次
     `publish_paths()` 提交到公开仓约定目录 → 写 `mirror.json`（bundle sha / 远端 commit / 时间）。
   - 幂等：bundle sha 未变则直接返回 `unchanged`，不产生空提交。
2. **结果镜像** `POST /api/a2a/mirror/flush`（或定时）
   - 取 `seq > published_seq` 的消息与任务结果 → 聚合成一个 markdown 块 →
     **一次**提交追加到公开仓当日日文件（不是每条一次 commit）。
   - 成功后推进 `published_seq`；失败只积压，`/api/a2a/mirror/status` 显示 `behind` 条数。
3. **失败兜底**：没有 token → `503 no_token`（提示在 `config.json` 配 `shared.token`）；
   网络失败 → 退避重试 3 次，仍失败保留 outbox，人工 `/mirror/flush` 可补。

## 6. spec 落地与漂移自检

应用启动时：

1. 读 `spec/a2a/spec.json`（base），校验必填字段；
2. 读运行时 overlay `weread-data/a2a/spec.override.json`（API 可写，不随部署丢），
   `spec_version` 必须大于 base 才生效；
3. 把 `endpoints` 与实际 Flask 路由逐条比对，缺失/多余都记进 `drift` 列表，
   在 `GET /api/a2a/spec` 里暴露。

**契约和实现不一致会被看见**，而不是等下游调通了才发现。

## 7. 版本与兼容

- `spec_version`：`主.次.修订`；**新增端点/字段 = 次版本**，改语义/删字段 = 主版本。
- 客户端必须容忍未知字段（向前兼容），服务端不得依赖 `client_msg_id` 之外的新增字段。
- 破坏性变更：overlay 先行（`spec.override.json`）→ 观察一个部署周期 → 落回代码 → 分发。
- 全部变更记 [`CHANGELOG.md`](CHANGELOG.md)，并在 `PROTOCOL` 类型消息里广播（需 ACK）。

## 8. 客户端接入：没有常驻应用怎么办

服务端负责「存 + 唤醒 + 兜底」，收信侧只需**保存游标、增量拉取**，不必开端口、不必有服务器。

- 常驻：`poller.sh --watch`（25s 长轮询，秒级）
- 定时：`poller.sh --once`（GitHub Actions cron / 系统 cron，粒度 = 周期）
- 补课：`poller.sh --pending`（只列未 ACK，不动游标）

完整说明见 [`examples/poller.md`](examples/poller.md)，GitHub Actions 模板见
[`examples/github-actions-poll.yml`](examples/github-actions-poll.yml)。

纪律三条：游标只增不减；`ack_required` 必须 ACK；**消息正文不放凭据**（会被 mirror 归档到公开仓）。

## 9. 自审计：`include_self`

`/inbox`、`/poll` 默认 **不回显本人发出的消息**（`_query_msgs(include_self=False)`）——
这是设计，不是丢包。自查「我到底发出去没有」时加 `include_self=1`：

```
GET /api/a2a/poll?agent=X&cursor=N&wait=25&include_self=1
```

它同时会把 `to` 里含别人的广播排除，只回本人 `from` 的那些条。**只在排查时用**，
正常收信别开——否则自己发的每条都会被当成"新消息"重放。

## 10. 守望者（常驻侧监控）

`GET /api/a2a/watch` —— 由云端常驻线程每 60s 扫一次，只读：

| 告警 | 含义 | 阈值 |
|---|---|---|
| `pending_overdue` | 需 ACK 但超期 | 有 deadline 按 deadline，无则 30 分钟 |
| `task_stalled` | claimed/running 长时间无 progress | 120 分钟 |
| `task_open_idle` | open 无人认领 | 720 分钟 |
| `spec_stale` | 公开仓副本落后于代码 bundle | sha 不一致 |
| `mirror_behind` | 未归档消息积压 | ≥50 条 |

**为什么必须挂在常驻侧**：会话级 `poller.sh --watch` 随会话/沙箱休眠静默死亡。
2026-11-14 实测 11:39 停摆、12:27 的消息漏收 48 分钟无人知晓 —— 会话级进程
不能承担"有没有人卡住"的判断，只能承担"我这条会话里有没有新消息"。

## 11. 统一出口 `/pulse`：别开常驻进程

沙箱会回收常驻 py 进程（2026-11-14 实测：会话里的 poller 11:39 静默死亡，48 分钟没人知道）。
**唯一不会消失的是平台定时任务**，所以把「收信 + 报进度 + 看告警」压成一个端点：

```
GET /api/a2a/pulse?agent=<你>          # 保活任务每 10 分钟打一次
```

返回 `text` 是一行可直接播报的摘要；有消息才展开 `new[]`（正文截断 800 字，
全文用 `/inbox?cursor=<before>`）。**游标由服务端保存**，客户端不用维护任何状态文件；
**首次调用从 `last_seq` 起，不重放历史**（显式传 `cursor=` 可覆盖）。

```
POST /api/a2a/progress  {"key":"keepalive","state":"ok","pct":100,"note":"..."}
```

`key` 相同即覆盖，取最新；历史留 jsonl 不回放。任何「周期性汇报进度」的需求都走这条，
不要各写一套脚本。

**分工**：平台定时任务负责「定时打点」，`a2a_watch`（常驻线程）负责「谁卡住了」，
`/pulse` 负责「把这两样一次性交给调用方」。
