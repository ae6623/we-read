#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""极简 MCP HTTP 客户端：直连本机 IMA 连接器（http://ima.agent-gateway.auth-proxy.local/mcp）。

用途：批量上传书卡时避免逐条走 Agent 工具调用。
说明：该地址只在带 IMA 连接器的工作环境里可达；换机器请改用 Agent 的 MCP 工具。
"""
from __future__ import annotations

import json
import urllib.request

URL = "http://ima.agent-gateway.auth-proxy.local/mcp"
_MID = 0
_SESSION = None


def _post(payload, timeout=90, allow_empty=False):
    global _SESSION
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(URL, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    if _SESSION:
        req.add_header("Mcp-Session-Id", _SESSION)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        sid = r.headers.get("Mcp-Session-Id")
        if sid:
            _SESSION = sid
        raw = r.read().decode("utf-8", "ignore")
    if allow_empty and not raw.strip():
        return {}
    # 兼容 SSE 与纯 JSON 两种响应
    out = None
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith(":") or line.startswith("id:") or line.startswith("event:"):
            continue
        if line.startswith("data:"):
            line = line[5:].strip()
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict) and obj.get("id") == payload.get("id"):
            out = obj
    if out is None:
        raise RuntimeError("MCP 无响应: " + raw[:300])
    if "error" in out:
        raise RuntimeError("MCP error: " + json.dumps(out["error"], ensure_ascii=False)[:400])
    return out["result"]


def init():
    global _MID
    _MID += 1
    r = _post({"jsonrpc": "2.0", "id": _MID, "method": "initialize",
               "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                          "clientInfo": {"name": "wr-ima", "version": "1"}}})
    _post({"jsonrpc": "2.0", "method": "notifications/initialized"}, allow_empty=True)
    return r


def call(tool: str, args: dict, timeout=90):
    global _MID
    _MID += 1
    return _post({"jsonrpc": "2.0", "id": _MID, "method": "tools/call",
                  "params": {"name": tool, "arguments": args}}, timeout=timeout)


def text_of(result: dict) -> str:
    parts = []
    for c in (result or {}).get("content") or []:
        if c.get("type") == "text":
            parts.append(c.get("text", ""))
    return "\n".join(parts)


if __name__ == "__main__":
    print(json.dumps(init(), ensure_ascii=False)[:300])
    r = call("get_knowledge_base_list", {"params": [{"limit": 10, "type": "KBT_MINE_KB"}]})
    print(text_of(r)[:500])
