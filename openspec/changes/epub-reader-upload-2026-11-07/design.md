# 设计：Aa 入口归位、上传与异步补笔记

## 约束

GitHub Pages 只提供静态 GET，没有写文件、commit 或后台任务能力。任何「服务端接收上传并保存在 git」的实现 MUST 落在一个用户自己启动的进程上。前端把凭据写进公开页面等同泄露，MUST NOT 采用。

读书 Agent 是独立的多 Agent 系统，权威状态在 `main` 的 `book-registry.json`，按 `reading-state-protocol.md` 串行写入。本机服务 MUST NOT 拉起别人的阅读进程，也 MUST NOT 宣称笔记已产出。

## 决策 1：Aa 单一入口

`aa-panel.js` 的 `buildFab()` 不再 `document.body.appendChild` 一个 `position:fixed` 按钮。改为把模块级 `fab` 指向已有的 `#aaBtn`，`togglePanel()` / `closePanel()` 的 `.on` 高亮自然落在顶栏按钮上。面板 CSS 从 `top:106px`（为悬浮方块留位）改为 `top:62px`，贴合 56px 顶栏下沿。`#rdSpeakFab`（🎧）保留，它属于朗读控制，不是 Aa 入口。

代价：组件不再自带入口，宿主页面 MUST 提供 `#aaBtn`；文档写明。若宿主缺失，面板仍可由 `⚙` / `settings` 动作打开，不至于完全不可用。

## 决策 2：上传服务同源双职责

`tools/epub-upload-server/app.py` 用 Python 标准库 `http.server.ThreadingHTTPServer` 实现，零第三方依赖。上传采用 XHR 直接 POST **原始二进制**（文件名与可选标题放在请求头/查询参数），因此服务端不需要解析 multipart，也避开 Python 3.13 移除 `cgi` 的兼容问题；XHR 同时提供真实上传进度。服务提供：

- `/api/*` JSON 接口；
- `/` 起的静态文件服务，根指向仓库根，因而 `/reading-notes/epub/index.html`、`/reading-notes/epub/uploads/*.epub` 与 API 同源。

同源是关键：从 `http://127.0.0.1:8788/reading-notes/epub/index.html` 打开时，上传、清单读取、epub.js 的二进制 XHR 全部同源，不受 CORS 与 HTTPS→HTTP 混合内容拦截。线上 Pages 仍保留云端阅读能力，上传 Tab 允许配置服务地址并开启 CORS，但文档明确推荐同源打开。

上传校验在服务端做，不信任前端：扩展名、ZIP 完整性、EPUB `mimetype` 首条且未压缩、`META-INF/container.xml` 存在、≤ 15 MB。校验失败 MUST NOT 落盘、MUST NOT 入队。

## 决策 3：书目分清单

`epubs.json`（云端，203 本，生成脚本维护）与 `uploads.json`（上传，服务维护）MUST 完全分开。阅读器按 `?src=upload` 决定读哪个清单；`云端☁️` Tab 只读 `epubs.json`，`上传` Tab 只读 `uploads.json`。这样服务上传不会改写生成脚本的产物，也不会把本地书混进云端计数。

两个清单的 book 对象字段对齐（`id/title/author/pages/chars/chapters/bytes/file`），阅读器渲染与下载逻辑复用同一段代码。上传书额外带 `sha256`、`uploaded_at`、`source`、`note_status`。

## 决策 4：幂等 ID 与入队

`book_id = "upload-" + sha256(规范化书名)[:12]`，同名重复上传覆盖同一文件、不重复追加 registry 条目。入队字段严格对齐远端 09:51 提交 `f6e26481c` 的实例：`platform: local_pdf`、`priority: user_requested`、`status: queued`、`owner_agent_id: null`、`claim.state: unclaimed`、`resume_point.status: needs-confirmation`、`source_format: epub`。写 registry 前 MUST 重读磁盘最新版本，`revision += 1`、更新 `updated_at`。

交接事件按日文件 `### [YYYY-MM-DD HH:MM] 用户（本机上传服务代写） / upload-...` 追加，MUST 声明「不是阅读场次、不代表亲读或完读」，MUST NOT 改 roster、活动锁、completion 与完读计数。

`PIPELINE_HOOK` 是可选异步钩子（`Popen`，不等待）；默认不配置，仅入队。服务的响应 MUST 如实返回 `queued: true`，不写「已生成笔记」。

## 决策 5：git 写入策略

默认 `git add` + 本地 `commit`，不 push。理由：main 是多 Agent 串行权威基线，后台自动 push 会抢锁。`AUTO_PUSH=1` 时先 `pull --rebase` 再 `push`，失败保留本地提交并回报，不重试、不 force。git 操作失败 MUST NOT 回滚已落盘文件与已入队状态，只如实回报。

## 决策 6：Tab 与搜索

三个 Tab 文案压到 2 字以腾出空间，配合 `🔍` 固定宽度按钮（34px）与 11px 窄屏字号，保证 272px 侧栏不换行。搜索钮 MUST 把当前 Tab 切到 `云端☁️` 并聚焦筛选框，符合「快速找书」的语义；书架页右上角另加即时过滤框，输入即隐藏不匹配卡片并显示命中数。

## 风险

- 上传整本 EPUB 进公开仓库即公开可下载，页面 `noindex` 不等于私有。文档与页面提示 MUST 写明。
- 多 Agent 并发写 `book-registry.json` 时本机服务可能基于旧磁盘基线。缓解：写前重读文件、revision +1、事件注明「待 main 接受后生效」，不自动 push。
- `http.server` 单线程处理大文件上传会阻塞静态请求。使用 `ThreadingHTTPServer`，并设置合理超时。
