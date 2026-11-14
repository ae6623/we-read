#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a2a_cli.py — 正式版 A2A 客户端（HTTP 消息总线，2026-11-14）

用法（先配两个环境变量，其余都能免参数）：
    export A2A_AGENT=workbuddy-cloud-luoyu
    export A2A_TOKEN=<你的 X-Agent-Token>        # 没有 token 时退化用 X-Agent-Name 署名

    python a2a_cli.py doc                          # 看协议与端点
    python a2a_cli.py send --to agent2 --type REQUEST --body "请核对 14 本 combined" --ack
    python a2a_cli.py send --to all --type PROTOCOL --body "以后走正式 A2A"
    python a2a_cli.py inbox --unacked              # 一次性拉未处理
    python a2a_cli.py poll --wait 25               # 长轮询一次（有消息立刻返回）
    python a2a_cli.py watch --interval 0            # 常驻：长轮询循环，来一条打一条
    python a2a_cli.py ack m000001 --note "已核对"
    python a2a_cli.py pending                       # 我欠别人的 ACK
    python a2a_cli.py agents                        # 花名册 + 各自未 ACK 数
    python a2a_cli.py thread cards
    python a2a_cli.py export --day 2026-11-14      # 导出旧日文件格式，供 git 归档

退出码：0 正常；2 参数错；3 服务端拒绝（401/400 等）；4 网络不通。
只依赖标准库。**别再为 A2A 写第二个监听器**——`watch` 就是监听器。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("A2A_BASE", "https://weread-cloud-probe.app.workbuddy.host").rstrip("/")
ROOT = BASE + "/api/a2a"


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    tok = os.environ.get("A2A_TOKEN") or os.environ.get("X_AGENT_TOKEN") or ""
    name = os.environ.get("A2A_AGENT") or os.environ.get("X_AGENT_NAME") or ""
    ver = ""
    try:
        import version_gate  # 本地有代码就自动带版本号，没有就算了
        ver = str(version_gate.AUTO_VERSION)
    except Exception:
        pass
    if tok:
        h["X-Agent-Token"] = tok
    if name:
        h["X-Agent-Name"] = name
    if ver:
        h["X-Auto-Version"] = ver
    return h


def _call(path: str, params: dict | None = None, body: dict | None = None,
          timeout: float = 70.0, raw: bool = False):
    url = ROOT + path
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
    data = None
    method = "GET"
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        method = "POST"
    req = urllib.request.Request(url, data=data, headers=_headers(), method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            txt = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        txt = e.read().decode("utf-8", "replace")
        print("[HTTP %s] %s" % (e.code, txt[:400]), file=sys.stderr)
        sys.exit(3)
    except Exception as e:
        print("[网络不通] %s（%s）" % (url, type(e).__name__), file=sys.stderr)
        sys.exit(4)
    if raw:
        return txt
    try:
        return json.loads(txt)
    except Exception:
        return {"raw": txt}


def _print_msg(m: dict) -> None:
    mark = "★" if m.get("ack_required") and not m.get("acked") else " "
    head = "%s [%s] %s → %s  %s" % (mark, m.get("id"), m.get("from"),
                                    ",".join(m.get("to") or []), m.get("type"))
    print("=" * 78)
    print(head)
    if m.get("subject"):
        print("  主题：%s" % m["subject"])
    extras = []
    for k in ("task", "baseline", "thread", "reply_to", "deadline"):
        if m.get(k):
            extras.append("%s=%s" % (k, m[k]))
    if m.get("acked_by"):
        extras.append("ACK=%s" % ",".join(m["acked_by"]))
    if m.get("overdue"):
        extras.append("已超期")
    if extras:
        print("  " + " / ".join(extras))
    print("  时间：%s" % m.get("ts"))
    print("-" * 78)
    print(str(m.get("body") or ""))


def main() -> int:
    ap = argparse.ArgumentParser(description="正式版 A2A 客户端（HTTP 消息总线）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doc")

    p = sub.add_parser("send")
    p.add_argument("--to", required=True, help="收件人，多个用逗号；全体写 all")
    p.add_argument("--type", default="NOTE")
    p.add_argument("--body", required=True)
    p.add_argument("--subject", default="")
    p.add_argument("--task", default="")
    p.add_argument("--baseline", default="")
    p.add_argument("--thread", default="")
    p.add_argument("--reply-to", dest="reply_to", default="")
    p.add_argument("--ack", action="store_true", help="要求对方 ACK")
    p.add_argument("--deadline", default="")
    p.add_argument("--priority", type=int, default=0)
    p.add_argument("--client-msg-id", dest="cid", default="")

    p = sub.add_parser("inbox")
    p.add_argument("--agent", default="")
    p.add_argument("--since", type=int, default=0)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--unacked", action="store_true")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("poll")
    p.add_argument("--agent", default="")
    p.add_argument("--cursor", type=int, default=0)
    p.add_argument("--wait", type=int, default=25)
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("watch")
    p.add_argument("--agent", default="")
    p.add_argument("--cursor", type=int, default=0)
    p.add_argument("--wait", type=int, default=55)
    p.add_argument("--interval", type=float, default=0)

    p = sub.add_parser("ack")
    p.add_argument("ids", nargs="+")
    p.add_argument("--note", default="")

    p = sub.add_parser("pending")
    p.add_argument("--agent", default="")

    sub.add_parser("agents")

    p = sub.add_parser("thread")
    p.add_argument("tid")

    p = sub.add_parser("export")
    p.add_argument("--day", default="")

    a = ap.parse_args()

    if a.cmd == "doc":
        d = _call("")
        print(json.dumps(d, ensure_ascii=False, indent=2))
        return 0

    if a.cmd == "send":
        body = {
            "to": a.to, "type": a.type, "body": a.body, "subject": a.subject,
            "task": a.task, "baseline": a.baseline, "thread": a.thread,
            "reply_to": a.reply_to, "ack_required": a.ack,
            "deadline": a.deadline, "priority": a.priority,
            "client_msg_id": a.cid,
        }
        print(json.dumps(_call("/send", body=body), ensure_ascii=False))
        return 0

    if a.cmd == "inbox":
        d = _call("/inbox", {"agent": a.agent, "since": a.since,
                             "limit": a.limit, "unacked": "1" if a.unacked else ""})
        if a.json:
            print(json.dumps(d, ensure_ascii=False, indent=2))
            return 0
        print("agent=%s  count=%d  last_seq=%s" % (d.get("agent"), d.get("count"), d.get("last_seq")))
        for m in d.get("messages") or []:
            _print_msg(m)
        return 0

    if a.cmd == "poll":
        d = _call("/poll", {"agent": a.agent, "cursor": a.cursor, "wait": a.wait},
                  timeout=a.wait + 20)
        if a.json:
            print(json.dumps(d, ensure_ascii=False, indent=2))
            return 0
        if not d.get("woke"):
            print("（%.0fs 内无新消息，cursor=%s）" % (a.wait, d.get("cursor")))
            return 0
        print("★★ 有新消息 %d 条，cursor=%s" % (d.get("count"), d.get("cursor")))
        for m in d.get("messages") or []:
            _print_msg(m)
        return 0

    if a.cmd == "watch":
        cur = a.cursor
        print("常驻监听中（长轮询 %ss，Ctrl-C 停）cursor=%d" % (a.wait, cur), flush=True)
        seen = set()
        while True:
            d = _call("/poll", {"agent": a.agent, "cursor": cur, "wait": a.wait},
                      timeout=a.wait + 20)
            if d.get("woke"):
                for m in d.get("messages") or []:
                    if m.get("id") in seen:
                        continue
                    seen.add(m.get("id"))
                    _print_msg(m)
                cur = max(cur, int(d.get("cursor") or cur))
                print("→ cursor 推进到 %d" % cur, flush=True)
            if a.interval:
                time.sleep(a.interval)
        return 0

    if a.cmd == "ack":
        print(json.dumps(_call("/ack", body={"ids": a.ids, "note": a.note}),
                         ensure_ascii=False))
        return 0

    if a.cmd == "pending":
        d = _call("/pending", {"agent": a.agent})
        print("待我 ACK：%d 条（超期 %s）" % (d.get("count"), d.get("overdue")))
        for m in d.get("messages") or []:
            _print_msg(m)
        return 0

    if a.cmd == "agents":
        d = _call("/agents")
        print("%-30s %-10s %-8s %s" % ("身份", "来源", "待ACK", "最近seq"))
        for x in d.get("agents") or []:
            print("%-30s %-10s %-8s %s" % (x.get("name"), x.get("source"),
                                           x.get("pending_ack"), x.get("last_seen_seq")))
        return 0

    if a.cmd == "thread":
        d = _call("/thread", {"thread": a.tid})
        print("thread=%s  %d 条" % (a.tid, d.get("count")))
        for m in d.get("messages") or []:
            _print_msg(m)
        return 0

    if a.cmd == "export":
        txt = _call("/export", {"day": a.day}, raw=True)
        sys.stdout.write(txt if isinstance(txt, str) else str(txt))
        return 0

    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已停止", file=sys.stderr)
        sys.exit(0)
