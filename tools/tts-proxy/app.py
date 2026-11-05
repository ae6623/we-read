#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
极简 TTS 代理：把文本用 edge-tts（微软 Edge 神经语音，免费、无需 API Key）
合成 mp3 返回给浏览器。

用途：手机浏览器 / 微信 webview 往往没有 speechSynthesis 语音包，
网页端 Web Speech 发不出声。改由本站（或任意服务器）按需合成 mp3，
前端用 <audio> 播放，任何浏览器都能出声。

接口：
  GET  /tts?text=你好&voice=zh-CN-XiaoxiaoNeural&rate=%2B0%25
  POST /tts   {"text":"...","voice":"...","rate":"+0%"}
  GET  /health   -> ok

启动：
  pip install -r requirements.txt
  TTS_CACHE=/var/cache/we-read-tts PORT=8765 python3 app.py

说明：
  - 文本按前端切好的块请求（每块约 360 字），本服务也做长度上限保护。
  - 相同 (文本+音色+语速) 会命中磁盘缓存，重复朗读零成本。
  - 生产环境建议放在 nginx 后面走 HTTPS（前端页面是 https，混用 http 会被拦）。
"""
import asyncio
import hashlib
import os
import sys

from flask import Flask, Response, abort, request

try:
    import edge_tts
except ImportError:
    sys.exit("缺少依赖：请先 pip install -r requirements.txt")

app = Flask(__name__)

CACHE_DIR = os.environ.get("TTS_CACHE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache"))
os.makedirs(CACHE_DIR, exist_ok=True)
MAX_CHARS = int(os.environ.get("TTS_MAX_CHARS", "1600"))
DEFAULT_VOICE = os.environ.get("TTS_DEFAULT_VOICE", "zh-CN-XiaoxiaoNeural")

# 允许的音色（女声/男声/台湾腔）——与前端 Aa 面板的音色快捷项对应
VOICES = {
    "zh-CN-XiaoxiaoNeural", "zh-CN-XiaoyiNeural",          # 普通话女声
    "zh-CN-YunxiNeural", "zh-CN-YunjianNeural",            # 普通话男声
    "zh-TW-HsiaoChenNeural", "zh-TW-HsiaoYuNeural",        # 台湾腔女声
    "zh-TW-YunJheNeural",                                  # 台湾腔男声
}


def _cors(resp: Response) -> Response:
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


def _norm_rate(rate: str) -> str:
    """把 '+20%' / '-10%' / '1.2' 统一成 edge-tts 需要的 '+20%' 形式。"""
    r = (rate or "").strip()
    if not r:
        return "+0%"
    if r.endswith("%"):
        return r if r[0] in "+-" else "+" + r
    try:
        pct = int(round((float(r) - 1.0) * 100))
    except ValueError:
        return "+0%"
    pct = max(-90, min(100, pct))
    return ("+" if pct >= 0 else "") + str(pct) + "%"


def _synth(text: str, voice: str, rate: str) -> bytes:
    key = hashlib.sha1((voice + "|" + rate + "|" + text).encode("utf-8")).hexdigest()
    path = os.path.join(CACHE_DIR, key + ".mp3")
    if os.path.exists(path) and os.path.getsize(path) > 0:
        with open(path, "rb") as f:
            return f.read()

    async def run() -> bytes:
        comm = edge_tts.Communicate(text, voice=voice, rate=rate)
        buf = bytearray()
        async for chunk in comm.stream():
            if chunk.get("type") == "audio":
                buf.extend(chunk["data"])
        return bytes(buf)

    data = asyncio.run(run())
    if data:
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    return data


@app.route("/tts", methods=["GET", "POST", "OPTIONS"])
def tts():
    if request.method == "OPTIONS":
        return _cors(Response(status=204))

    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        text = (body.get("text") or "").strip()
        voice = (body.get("voice") or DEFAULT_VOICE).strip()
        rate = body.get("rate") or "+0%"
    else:
        text = (request.args.get("text") or "").strip()
        voice = (request.args.get("voice") or DEFAULT_VOICE).strip()
        rate = request.args.get("rate") or "+0%"

    if not text:
        abort(400, "empty text")
    if len(text) > MAX_CHARS:
        abort(413, "text too long (max %d)" % MAX_CHARS)
    if voice not in VOICES:
        voice = DEFAULT_VOICE
    rate = _norm_rate(rate)

    try:
        data = _synth(text, voice, rate)
    except Exception as e:  # noqa: BLE001
        return _cors(Response("tts error: %s" % e, status=502, mimetype="text/plain"))

    if not data:
        return _cors(Response("empty audio", status=502, mimetype="text/plain"))
    return _cors(Response(data, mimetype="audio/mpeg"))


@app.route("/health")
def health():
    return _cors(Response("ok", mimetype="text/plain"))


if __name__ == "__main__":
    # 平台（如应用托管）会注入 PORT；未注入时用 3000，与反代默认端口一致
    port = int(os.environ.get("PORT", "3000"))
    app.run(host="0.0.0.0", port=port, threaded=True)
