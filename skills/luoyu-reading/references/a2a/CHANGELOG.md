# A2A spec 变更记录

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
