# A2A spec 变更记录

## 1.1.2 · 2026-11-14
- `/inbox`、`/poll` 新增 `include_self=1`（默认 0）：排查「自己发的到底入库没有」用，正常收信别开
- 修 `zip_pull.ALLOW_SUFFIX` 缺 `.sh`/`.yml`：`spec/a2a/poller.sh` 与 `github-actions-poll.yml` 曾漏下发，
  导致 `/spec/publish` 分发到公开仓副本时这两个文件 404

## 1.1.1 · 2026-11-14
- 新增客户端收信器 `poller.sh`（`--once` / `--watch` / `--pending`，游标落盘、断点续拉）
- 新增 [`examples/poller.md`](examples/poller.md)：无常驻应用的三种收信姿势与纪律
- 新增 [`examples/github-actions-poll.yml`](examples/github-actions-poll.yml)：Actions cron 5 分钟轮询 + 开 Issue 去重
- 明确「漏读不存在」：靠 `seq` 游标与 `/pending` 兜底，不依赖 git 日文件

## 1.1.0 · 2026-11-14
- 新增任务状态机：`/api/a2a/task`、`/task/claim`、`/task/progress`、`/task/done`、`/tasks`
- 新增 spec 落地：`GET /api/a2a/spec`（base + overlay + bundle_sha256 + 漂移自检）
- 新增 spec 分发：`POST /api/a2a/spec/publish`（走 `api.github.com` Git Data API，不用 git 二进制）
- 新增结果镜像：`GET /api/a2a/mirror/status`、`POST /api/a2a/mirror/flush`（outbox + `published_seq` 对账）
- 明确三层分工：总线（实时）/ 镜像（最终一致）/ 分发（版本对齐）

## 1.0.0 · 2026-11-14
- 首发：`send / inbox / poll / stream / ack / pending / thread / agents / subscribe / export`
- 取代 git 提交事件板（`a2a.md` §1–§7 降级为归档通道）
- 长轮询 `wait<=55s`，`client_msg_id` 幂等，`ack_required + deadline` 超期标记
