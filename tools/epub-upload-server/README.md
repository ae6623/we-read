# EPUB 上传服务（本机 / 在线沙箱双模式）

给 `reading-notes/epub/` 阅读器补上「用户自己上传 EPUB」的能力。GitHub Pages 是纯静态托管，浏览器不能写文件、不能 commit、不能起后台任务，所以上传必须由一个真实 HTTP 服务接收。同一份 `app.py` 支持两种运行形态：

| 模式 | 判定 | 文件落在哪 | 入队写哪 | 谁能访问 |
| --- | --- | --- | --- | --- |
| 本机仓库 | 目录上溯能找到 `book-registry.json` | `reading-notes/epub/uploads/`（仓库） | `book-registry.json` + 交接事件，本地 commit | 只绑 127.0.0.1 |
| 在线沙箱 | 独立部署目录（无仓库结构）或 `MODE=sandbox` | `data/uploads/`（应用数据目录） | `data/queue.json` + `data/events/*.md` | 云端公网 URL |

前端 `reader.html` 启动时读 `reading-notes/epub/upload-api.json` 的 `base` 字段自动拿到线上地址；没有配置时回落到本机同源服务或仓库里的 `uploads.json`。用户也可以在「上传」Tab 手动填地址（存 localStorage，优先级最高）。

## 在线部署（由云端 Agent 执行）

本机 Agent 不直接部署。代码推到 `ae6623/we-read/main` 后，通过 A2A 板把部署请求发给 `workbuddy-cloud-luoyu`（见当日 `agent-communication/YYYY/MM/YYYY-MM-DD.md`）。云端按顺序：更新代码 → 检查在跑的任务并保存暂停 → 部署应用 → 回帖可访问的 base URL → 拉起中断的任务。

部署参数（WorkBuddy 应用托管 / sites）：

- 目录：`tools/epub-upload-server/`
- 语言：`python`，依赖：`requirements.txt`（纯标准库，无第三方包）
- 启动：`python app.py`；服务读平台注入的 `PORT` 并绑定 `0.0.0.0`
- 验证：`GET /api/health` 返回 `ok:true`、`mode:"sandbox"`
- 部署后把 URL 写入 `reading-notes/epub/upload-api.json` 的 `base` 并 push；前端自动生效

## 本机启动（可选）

在**仓库根目录**执行（Python 3.8+，标准库即可）：

```bash
python tools/epub-upload-server/app.py
# 打开 http://127.0.0.1:8788/reading-notes/epub/index.html
```

同源是关键：上传接口、清单、EPUB 二进制都从同一端口出，没有 CORS 与混合内容问题。

## 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 模式、服务 base、上传目录、队列 revision、webhook 状态 |
| GET | `/api/uploads` | 上传书目清单；每项 `file` / `file_url` 是**可直接跨域阅读的绝对 URL** |
| GET | `/api/queue` | 补书任务队列（registry 兼容 `queued` 条目） |
| GET | `/api/events?date=YYYY-MM-DD` | 当日交接事件文本 |
| GET | `/api/sync` | 清单 + 队列 + 事件 + 下载链接，供 `sync_to_git.py` 拉回仓库 |
| GET | `/uploads/<book_id>.epub` | EPUB 二进制，带 `Access-Control-Allow-Origin: *` |
| POST | `/api/upload?name=书名.epub` | **原始二进制** body；文件名也可放 `X-File-Name`（URL 编码） |

```bash
curl -X POST --data-binary @book.epub \
  -H "Content-Type: application/octet-stream" \
  "https://<沙箱域名>/api/upload?name=book.epub"
```

响应包含 `mode`、`file_url`、`queued`、`registry_revision`、`pipeline`，以及「已入队 queued，等待读书 Agent 认领补笔记；不代表笔记已生成」。

## 服务端做了什么

1. **校验**（任一不过直接 400，不落盘不入队）：`.epub` 后缀、ZIP 完整、`mimetype` 首条 STORED、`META-INF/container.xml`、≤ 15 MB。
2. **落盘**：读 OPF 取标题/作者，`upload-` + `sha256(规范化书名)[:12]` 作稳定 ID；先 `.part` 再原子替换。同名重复上传覆盖同一 ID，**不重复入队**。
3. **清单**：维护 `uploads.json`，字段与 `epubs.json` 对齐，另带 `sha256` / `uploaded_at` / `note_status`。
4. **入队补笔记**：按 `reading-state-protocol.md` 追加 `queued` / `unclaimed` / `user_requested` / `source_format: epub` 条目，并写交接事件，声明「不是阅读场次、不代表亲读或完读」。本机写进 `book-registry.json`（本地 commit）；沙箱写进 `data/queue.json` + `data/events/`。
5. **异步启动**：`PIPELINE_WEBHOOK` 配了就后台 POST 任务 JSON；`PIPELINE_HOOK` 配了就异步执行命令。都没配则只入队，由读书 Agent 轮询 `/api/queue` 认领。
6. **同步回 git**（沙箱 → 仓库）：`python tools/epub-upload-server/sync_to_git.py --from https://<沙箱域名> [--push]`，下载并校验 EPUB、写 `uploads.json`、合并队列进 `book-registry.json`、追加交接事件、本地 commit。默认不 push，避免抢 main 的并发写。

## 环境变量

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `MODE` | 自动 | `repo` / `sandbox` 强制指定 |
| `PORT` | `8788` | 监听端口（托管平台注入） |
| `HOST` | 沙箱 `0.0.0.0` / 本机 `127.0.0.1` | 监听地址 |
| `DATA_ROOT` | `./data` | 沙箱数据目录 |
| `REPO_ROOT` | 上溯两层 | 本机仓库根 |
| `PUBLIC_BASE` | 按请求 Host 推断 | 生成 `file_url` 时覆盖对外地址 |
| `MAX_BYTES` | `15728640` | 单本上限 15 MB |
| `AUTO_PUSH` | `0` | 本机模式下 `1` 才 rebase + push |
| `NO_GIT` | `0` | `1` 跳过 git |
| `PIPELINE_HOOK` / `PIPELINE_WEBHOOK` | 空 | 异步补笔记钩子 |

## 边界，别误读

- **入队 ≠ 笔记已生成**。服务不启动别人的读书 Agent，不宣称书已跑完、不宣称用户亲读或完读。
- **不改** `agent-roster.json`、活动锁、`resume_point`、`completion`、完读计数，也不改 `epubs.json` 的云端清单。
- 沙箱文件系统**不保证跨重新部署持久**；要长期保存必须跑 `sync_to_git.py` 同步回仓库。
- 上传的整本 EPUB 最终进的是**公开仓库**，页面 `noindex` 只减少扩散，**不等于私有**。
- 服务无鉴权，别在公共网络把无保护的本机端口暴露出去；沙箱模式只暴露上述公开只读/上传接口。

## 排查

| 现象 | 原因 / 处理 |
| --- | --- |
| 页面显示「未配置上传服务地址」 | `upload-api.json` 的 `base` 还是空；等云端部署回帖后填写，或在上传 Tab 手动填 |
| 页面显示「上传服务不可用」 | 沙箱休眠冷启动、域名写错或 CORS；先看 `/api/health` |
| 「超过 15 MB 上限」 | 与云端书架同一阈值；调大 `MAX_BYTES`，但太大的 epub 首屏会明显变慢 |
| 「mimetype 必须是 ZIP 第一个条目」 | 不是标准 EPUB 3 容器，用 Calibre / Sigil 重新导出 |
| 上传成功但书架看不到 | 前端拉的是 `/api/uploads`；确认清单接口返回 200 且 `file_url` 可下载 |
