# TTS 代理（给没有 Web Speech 的浏览器下发发音）

## 为什么需要它

网页里的 `speechSynthesis` 用的是**操作系统/浏览器自带的语音包**，GitHub Pages
没法“下发”声音。手机浏览器、微信内置 webview（X5/TBS）经常**没有中文语音包，
或干脆不支持**，所以点了没声。

`edge-tts` 是微软 Edge 的神经语音，**免费、无需 API Key**，在服务器上把文本合成
mp3，前端用 `<audio>` 播放 —— 任何浏览器（含微信）都能出声，而且音质比系统 TTS 好。

## 当前状态（默认已接入）

线上 `reader.js` 已把默认地址写死在 `TTS_DEFAULT`，指向 WorkBuddy 托管的同一份服务，
**开箱即用，不需要你自己部署**。想换成自己的服务器时，只要在 `reader.js` 之前执行：

```js
window.RD_TTS_BASE = 'https://oauth.js-dev.cn/tts';   // 会覆盖默认值
```

> 托管实例随沙箱休眠可能冷启动（首次请求慢几秒）；要高可用/自定义域名，
> 按下面步骤部署到你自己的机器，再覆盖 `RD_TTS_BASE` 即可。

## 部署（在你的 Ubuntu 服务器上）

```bash
# 1) 拿代码（只这两个文件即可）
mkdir -p /opt/we-read-tts && cd /opt/we-read-tts
# 把 app.py / requirements.txt 放进来

# 2) 建虚拟环境并安装
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

# 3) 试跑
PORT=8765 TTS_CACHE=/var/cache/we-read-tts python3 app.py
curl -s -o /tmp/t.mp3 -w "%{http_code} %{content_type} %{size_download}\n" \
  "http://127.0.0.1:8765/tts?text=%E4%BD%A0%E5%A5%BD&voice=zh-CN-XiaoxiaoNeural"
# 期待：200 audio/mpeg 若干字节
```

### systemd 常驻

`/etc/systemd/system/we-read-tts.service`：

```ini
[Unit]
Description=we-read TTS proxy
After=network.target

[Service]
WorkingDirectory=/opt/we-read-tts
Environment=PORT=8765
Environment=TTS_CACHE=/var/cache/we-read-tts
ExecStart=/opt/we-read-tts/.venv/bin/python /opt/we-read-tts/app.py
Restart=always
User=ubuntu

[Install]
WantedBy=multi-user.target
```

```bash
sudo mkdir -p /var/cache/we-read-tts && sudo chown ubuntu /var/cache/we-read-tts
sudo systemctl daemon-reload && sudo systemctl enable --now we-read-tts
```

### nginx 反代（走 HTTPS，页面是 https，混用 http 会被浏览器拦）

`oauth.js-dev.cn.conf` 的 server 段里加：

```nginx
location /tts {
    proxy_pass http://127.0.0.1:8765/tts;
    proxy_set_header Host $host;
    proxy_read_timeout 120s;
}
```

```bash
sudo nginx -t && sudo systemctl reload nginx
# 验证（公网、https）：
curl -s -o /dev/null -w "%{http_code}\n" \
  "https://oauth.js-dev.cn/tts?text=%E4%BD%A0%E5%A5%BD"
```

## 前端启用（一行）

`assets/js/reader.js` 里的 `TTS_DEFAULT` 就是默认服务地址，`window.RD_TTS_BASE`
可覆盖它。所以：

- 换服务器：在 `reader.js` 之前执行 `window.RD_TTS_BASE = 'https://你的域名/tts';`
- 彻底关闭服务端朗读：`window.RD_TTS_BASE = ' '`（回到纯 Web Speech）

启用后：一级模块右上角的 ▶ 会用服务器音频朗读；代理不可用时自动回退到 Web Speech。

## 参数

| 变量 | 默认 | 说明 |
|---|---|---|
| `PORT` | 3000 | 监听端口（托管平台会注入） |
| `TTS_CACHE` | `./cache` | mp3 磁盘缓存目录（命中零成本） |
| `TTS_MAX_CHARS` | 1600 | 单次请求文本上限（前端按 ~360 字切块） |
| `TTS_DEFAULT_VOICE` | `zh-CN-XiaoxiaoNeural` | 默认音色 |

音色：`zh-CN-XiaoxiaoNeural`（女）/ `zh-CN-YunxiNeural`（男）/
`zh-TW-HsiaoChenNeural`（台湾腔女）/ `zh-TW-YunJheNeural`（台湾腔男）。
