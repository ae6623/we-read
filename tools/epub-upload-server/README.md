# EPUB 上传服务

给 `reading-notes/epub/` 阅读器补上「用户自己上传 EPUB」的能力。GitHub Pages 是纯静态托管，浏览器不能写文件、不能 commit、不能起后台任务，所以这一步必须由一个你显式启动的本机进程完成。

## 启动

在**仓库根目录**执行（Python 3.8+，标准库即可，无需 pip install）：

```bash
python tools/epub-upload-server/app.py
```

然后打开同源书架：

```
http://127.0.0.1:8788/reading-notes/epub/index.html
```

同源是关键：上传接口、清单 `uploads.json`、EPUB 二进制都从同一个端口出，没有 CORS 和 HTTPS→HTTP 混合内容问题。直接开线上 Pages 也能读云端☁️书目，但上传 Tab 会提示服务离线。

## 用页面上传

阅读器左侧点 `上传` Tab → 确认服务地址（默认 `http://127.0.0.1:8788`）→ 点虚线框选择或直接拖入 `.epub`（可多选）→ 看进度与结果日志。上传完刷新 `云端☁️` 旁边的 `上传` 列表，点书名即可阅读：

```
reader.html?book=upload-xxxxxxxxxxxx&src=upload
```

`云端☁️`（`epubs.json`，203 本）和 `上传`（`uploads.json`）是两份独立清单，互不改写。

## 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 服务状态、仓库根、上传目录、registry revision |
| GET | `/api/uploads` | 返回 `uploads.json` |
| POST | `/api/upload?name=书名.epub` | **原始二进制** body，文件名也可放 `X-File-Name` 请求头（URL 编码） |
| GET | `/reading-notes/epub/...` | 静态托管，根指向仓库根 |

curl 示例：

```bash
curl -X POST --data-binary @book.epub \
  -H "Content-Type: application/octet-stream" \
  "http://127.0.0.1:8788/api/upload?name=book.epub"
```

响应示例：

```json
{
  "ok": true,
  "book_id": "upload-1a2b3c4d5e6f",
  "title": "书名",
  "file": "uploads/upload-1a2b3c4d5e6f.epub",
  "queued": true,
  "duplicate": false,
  "registry_revision": 295,
  "event": "skills/luoyu-reading/references/agent-communication/2026/11/2026-11-07.md",
  "git": ["已本地 commit"],
  "note": "已入队 queued，等待读书 Agent 认领补笔记；不代表笔记已生成"
}
```

## 服务端做了什么

1. **校验**（任一不过直接 400，不落盘、不入队）：`.epub` 后缀、ZIP 完整、`mimetype` 为首条且 STORED、内容 `application/epub+zip`、`META-INF/container.xml` 存在、≤ 15 MB。
2. **落盘**：读 OPF 取标题/作者，按规范化书名算 `upload-` + `sha256[:12]` 作稳定 ID；写 `reading-notes/epub/uploads/<id>.epub`（先 `.part` 再原子替换）。同名重复上传覆盖同一 ID，**不重复入队**。
3. **清单**：更新 `reading-notes/epub/uploads.json`，字段与 `epubs.json` 对齐，另带 `sha256`、`uploaded_at`、`source_name`、`note_status`。
4. **异步补笔记入队**（对齐 `reading-state-protocol.md` 与远端 09:51 的 `f6e26481c` 实例）：重读最新的 `book-registry.json`，追加一条 `platform: local_pdf` / `priority: user_requested` / `status: queued` / `owner_agent_id: null` / `claim.state: unclaimed` / `source_format: epub` 的书目，`revision + 1`、`updated_at` 更新；再往当日 `agent-communication/YYYY/MM/YYYY-MM-DD.md` 追加交接事件，声明「不是阅读场次、不代表亲读或完读」。
5. **git**：默认只 `git add` + 本地 `commit`，**不 push**。`main` 是多 Agent 串行权威基线，后台自动 push 会抢锁。`AUTO_PUSH=1` 才 `pull --rebase origin main` 再 `push`，不用 force。
6. **可选异步钩子**：`PIPELINE_HOOK` 配了命令就以 `Popen` 异步触发（不等待、不阻塞响应），支持 `{book_id}` `{title}` `{file}` 占位符。没配就只入队，由管理员按既有协议分发。

## 环境变量

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `PORT` | `8788` | 监听端口 |
| `HOST` | `127.0.0.1` | 只绑本机；改 `0.0.0.0` 会暴露到局域网，别在公共网络这么干 |
| `REPO_ROOT` | 本文件上溯两层 | 仓库根 |
| `MAX_BYTES` | `15728640` | 单本上限 15 MB |
| `AUTO_PUSH` | `0` | `1` 才 rebase + push |
| `NO_GIT` | `0` | `1` 完全跳过 git，只落盘 + 入队（测试用） |
| `PIPELINE_HOOK` | 空 | 可选异步补笔记命令 |

## 边界，别误读

- **入队 ≠ 笔记已生成**。服务不启动别人的读书 Agent，不宣称书已跑完、不宣称用户亲读或完读。认领、跑书、产出笔记由多 Agent 系统按共享状态协议完成。
- **不改** `agent-roster.json`、活动锁、`resume_point`、`completion`、完读计数，也不改 `epubs.json` 的 203 本云端清单。
- 上传的整本 EPUB 进的是**公开仓库**，一旦提交即公开可下载。页面 `noindex` 只减少扩散，**不等于私有**。
- 服务只监听 127.0.0.1，且拦截 `/.git/`、`/.workbuddy/`、`/.env` 路径；无鉴权，**不要**在没有额外保护的情况下绑到公网地址。

## 排查

| 现象 | 原因 / 处理 |
| --- | --- |
| 页面显示「服务离线」 | 服务没启动，或地址填错（端口、协议）。在仓库根执行启动命令。 |
| 上传报「超过 15 MB 上限」 | 与云端书架同一阈值；调大 `MAX_BYTES`，但太大的 epub 首屏会明显变慢。 |
| 上传报「mimetype 必须是 ZIP 第一个条目」 | 文件不是标准 EPUB 3 容器，用 Calibre / Sigil 重新导出。 |
| 「本地 commit 未成功」 | 仓库未配置 `user.name` / `user.email`，或有未解决冲突。文件与入队状态**已落盘**，不会因 git 失败回滚；手工提交即可。 |
| `AUTO_PUSH=1` 但没推送 | 多半是工作树脏导致 `pull --rebase` 失败，响应 `git` 字段会写明，服务不会强推。 |
| 线上 Pages 也能看到云端书，但读不了刚上传的 | 线上是静态站，读不到本机服务的文件；从 `http://127.0.0.1:8788/reading-notes/epub/index.html` 打开即可。 |
