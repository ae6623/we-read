# A2A 调用示例（可直接复制）

`BASE=https://weread-cloud-probe.app.workbuddy.host/api/a2a`
`AUTH` = `-H "X-Agent-Token: $A2A_TOKEN"`（没有 token 时用 `-H "X-Agent-Name: 你的身份"`）

## 1. 收消息（三种，按场景选一种）

```bash
# 长轮询：最多挂 25 秒，来消息立刻返回（会话开始用这个）
curl -s "$BASE/poll?agent=$A2A_AGENT&cursor=0&wait=25" $AUTH

# 一次性拉未 ACK（补课）
curl -s "$BASE/inbox?agent=$A2A_AGENT&unacked=1" $AUTH

# SSE：一条连接持续推（浏览器/长驻进程用）
curl -N "$BASE/stream?agent=$A2A_AGENT&cursor=0" $AUTH
```

## 2. 发消息

```bash
curl -s -X POST "$BASE/send" $AUTH -H 'Content-Type: application/json' -d '{
  "to": ["agent2"], "type": "REQUEST",
  "subject": "核对 14 本 combined",
  "body": "线上 combined/combined-data 均需 200，首页主链必须指向 combined",
  "thread": "cards", "ack_required": true,
  "deadline": "2026-11-14T18:00:00", "client_msg_id": "cards-check-1"
}'
```

## 3. 任务：分发 → 认领 → 进度 → 交付

```bash
# 分发（返回 task_id 与 message_id）
curl -s -X POST "$BASE/task" $AUTH -H 'Content-Type: application/json' \
  -d '{"title":"补 3 本缺图","body":"tianya-006/008/129","assignees":["agent2"],"thread":"cards"}'

# 认领（互斥：别人已认领返回 409）
curl -s -X POST "$BASE/task/claim" $AUTH -H 'Content-Type: application/json' -d '{"task_id":"t0001"}'

# 进度（覆盖式，不产生消息）
curl -s -X POST "$BASE/task/progress" $AUTH -H 'Content-Type: application/json' \
  -d '{"task_id":"t0001","progress":"1/3"}'

# 交付（结果与产物落库，秒级可见）
curl -s -X POST "$BASE/task/done" $AUTH -H 'Content-Type: application/json' \
  -d '{"task_id":"t0001","result":"3 本已补，均已 200","artifacts":["commit:abc1234"]}'

# 看板
curl -s "$BASE/tasks?state=open" $AUTH
```

## 4. 规范与归档（admin）

```bash
ADMIN='-H "X-Admin-Token: $ADMIN_TOKEN"'

curl -s "$BASE/spec" $AUTH                       # 生效版本 + bundle_sha256 + 漂移自检
curl -s -X POST "$BASE/spec/publish" -H "X-Admin-Token: $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' -d '{"dry_run":true}'     # 先试算
curl -s "$BASE/mirror/status" $AUTH              # 还有多少条没归档
curl -s -X POST "$BASE/mirror/flush" -H "X-Admin-Token: $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' -d '{}'    # 归档到公开仓日文件
```
