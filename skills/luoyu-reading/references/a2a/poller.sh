#!/usr/bin/env bash
# A2A 收信器 · 给「没有常驻应用」的 Agent 用
#
# 为什么要它：A2A 总线是服务端在跑，收信这一侧得有人来取。
# 有服务器就常驻长轮询（本脚本 --watch），只有 GitHub 就挂 Actions cron 调 --once。
#
# 用法：
#   A2A_AGENT=workbuddy-cloud-luoyuJi A2A_TOKEN=wrk_xxx ./poller.sh --once     # 取一次，退出
#   A2A_AGENT=workbuddy-cloud-luoyuJi A2A_TOKEN=wrk_xxx ./poller.sh --watch    # 常驻，秒级
#   A2A_AGENT=workbuddy-cloud-luoyuJi ./poller.sh --pending                    # 只看没 ACK 的
#
# 产出：消息打印到 stdout（Markdown），原文追加到 $A2A_STATE/<agent>.inbox.jsonl
# 游标：$A2A_STATE/<agent>.cursor（整数，单调递增，断了重启自动续）
# 退出码：0 正常；2 参数/身份错误；3 网络错误（可重试）
set -uo pipefail

BASE="${A2A_BASE:-https://weread-cloud-probe.app.workbuddy.host/api/a2a}"
AGENT="${A2A_AGENT:-}"
STATE="${A2A_STATE:-$HOME/.a2a}"
WAIT="${A2A_WAIT:-25}"
TOKEN="${A2A_TOKEN:-}"
MODE="${1:---once}"

if [ -z "$AGENT" ]; then
  echo "需要 A2A_AGENT（例如 workbuddy-cloud-luoyuJi）" >&2
  exit 2
fi

mkdir -p "$STATE" || exit 2
CURSOR_FILE="$STATE/$AGENT.cursor"
INBOX="$STATE/$AGENT.inbox.jsonl"
[ -s "$CURSOR_FILE" ] || printf '0\n' > "$CURSOR_FILE"
touch "$INBOX"

auth=(-H "X-Agent-Name: $AGENT")
[ -n "$TOKEN" ] && auth+=(-H "X-Agent-Token: $TOKEN")

# 用 python3 解析，避免依赖 jq。
# 注意：必须用 -c 传代码，不能用 `python3 - <<PY`（heredoc 会占掉 stdin，把管道数据吞掉）。
PYCODE=$(cat <<'PY'
import json, sys
cursor_file, inbox = sys.argv[1], sys.argv[2]
raw = sys.stdin.read()
try:
    d = json.loads(raw)
except Exception as e:
    print("[a2a] 响应不是 JSON：%s（前 120 字：%r）" % (e, raw[:120]), file=sys.stderr)
    sys.exit(3)
if not d.get("ok", True):
    print("[a2a] 服务端拒绝：%s" % (d.get("message") or d.get("error")), file=sys.stderr)
    sys.exit(2)
msgs = d.get("messages") or []
if not msgs:
    print("[a2a] %s 无新消息（cursor=%s last_seq=%s）"
          % (d.get("agent", "-"), d.get("cursor", "-"), d.get("last_seq", "-")), file=sys.stderr)
    sys.exit(0)
cur = int((open(cursor_file).read().strip() or 0))
with open(inbox, "a", encoding="utf-8") as f:
    for m in msgs:
        print("### [%s] %s / %s → %s" % (m.get("ts", "")[:16].replace("T", " "),
              m.get("from", "-"), m.get("id", "-"), ",".join(m.get("to") or [])))
        if m.get("subject"):
            print("- 主题：%s" % m["subject"])
        print("- 类型：%s%s" % (m.get("type") or "-", "（需 ACK）" if m.get("ack_required") else ""))
        if m.get("deadline"):
            print("- 截止：%s" % m["deadline"])
        if m.get("thread"):
            print("- 话题：%s" % m["thread"])
        print("- 正文：%s" % (m.get("body") or "").strip())
        print()
        f.write(json.dumps(m, ensure_ascii=False) + "\n")
        cur = max(cur, int(m.get("seq") or 0))
open(cursor_file, "w").write("%d\n" % cur)
print("[a2a] 已收 %d 条，cursor → %d" % (len(msgs), cur), file=sys.stderr)
PY
)

_render() { python3 -c "$PYCODE" "$CURSOR_FILE" "$INBOX"; }

case "$MODE" in
  --pending)
    curl -sfS --max-time 30 "$BASE/pending?agent=$AGENT" "${auth[@]}" | _render
    ;;
  --once)
    curl -sfS --max-time $((WAIT + 20)) \
      "$BASE/poll?agent=$AGENT&cursor=$(cat "$CURSOR_FILE")&wait=$WAIT" "${auth[@]}" | _render
    ;;
  --watch)
    echo "[a2a] watch start agent=$AGENT base=$BASE cursor=$(cat "$CURSOR_FILE")" >&2
    while :; do
      curl -sfS --max-time $((WAIT + 20)) \
        "$BASE/poll?agent=$AGENT&cursor=$(cat "$CURSOR_FILE")&wait=$WAIT" "${auth[@]}" | _render
      [ "${PIPESTATUS[0]}" -eq 22 ] && exit 2   # 401/403：身份或 token 不对，重试没意义
      [ "${PIPESTATUS[0]}" -ne 0 ] && sleep 5   # 网络抖动退避
    done
    ;;
  *)
    echo "用法：poller.sh [--once|--watch|--pending]" >&2
    exit 2
    ;;
esac
