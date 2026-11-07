# EPUB 阅读器入口与上传补书（epub-upload）规范

## 意图

阅读器 MUST 只有一个 Aa 入口，且位于顶栏下载按钮左侧；用户自上传的 EPUB MUST 能与预置云端书目分开管理，并通过既有共享状态协议异步进入补笔记队列。实现 MUST NOT 假装静态 Pages 有服务端，MUST NOT 假装入队等于笔记已生成。

## 要求

### R1 Aa 单一入口 MUST 非悬浮

Aa 配置面板 MUST 以顶栏 `#aaBtn` 为唯一入口；该按钮 MUST 位于下载按钮 `#dl` 左侧。页面 MUST NOT 再创建 `position:fixed` 的悬浮 Aa 方块 `#rdFab`。

面板展开时 MUST 锚定在顶栏下方右侧，不得脱离顶栏独立漂浮于正文中。`togglePanel()` 与 `closePanel()` 的高亮状态 MUST 作用在 `#aaBtn` 上。听书控制悬浮键 MUST NOT 被一并删除。

### R2 上传 MUST 由显式启动的服务端接收

浏览器页面 MUST NOT 内置任何写仓库凭据或 token。上传 MUST 发往用户显式启动的本机服务；服务未启动时，页面 MUST 显示离线状态与启动命令，MUST NOT 静默失败或显示假成功。

服务 MUST 同源托管 `reading-notes/epub/`，使上传、清单读取与 EPUB 二进制加载避开 CORS 与混合内容拦截。

### R3 服务端 MUST 校验后再落盘

服务端 MUST 校验：文件名为 `.epub`、ZIP 结构完整、`mimetype` 为首个条目且不压缩、`META-INF/container.xml` 存在、体积不超过 15 MB。任一校验失败 MUST 返回明确错误，且 MUST NOT 写文件、MUST NOT 改清单、MUST NOT 入队。

合法文件 MUST 落盘 `reading-notes/epub/uploads/<book_id>.epub`，并维护 `reading-notes/epub/uploads.json`。`book_id` MUST 由规范化书名稳定推导，同名重复上传 MUST 覆盖同一 ID 且 MUST NOT 重复入队。

### R4 云端与上传书目 MUST 分清单

`epubs.json` MUST 只由生成脚本维护，服务 MUST NOT 改写它。`uploads.json` MUST 只由上传服务维护。阅读器 `云端☁️` Tab MUST 只读 `epubs.json`，`上传` Tab MUST 只读 `uploads.json`。两份清单的 book 字段 MUST 对齐，使渲染与下载逻辑复用。

阅读器 MUST 支持 `?src=upload&book=<id>`，从 `uploads.json` 取 `meta.file`，其余渲染行为与云端书一致。

### R5 入队 MUST 复用既有共享状态协议

每次成功上传（新 `book_id`）MUST 以如下字段追加一条 `book-registry.json` 书目：`platform: local_pdf`、`priority: user_requested`、`status: queued`、`owner_agent_id: null`、`claim.state: unclaimed`、`resume_point.status: needs-confirmation`、`source_format: epub`。写前 MUST 重读磁盘最新版本，`revision` MUST 加 1，`updated_at` MUST 更新。

MUST 追加当日交接事件，MUST 声明「不是阅读场次、不代表亲读或完读」。MUST NOT 改 `agent-roster.json`、活动锁、`completion` 或完读计数。

响应 MUST 如实返回 `queued: true`；MUST NOT 宣称笔记已生成、书已跑完或 Agent 已开始阅读。可选的 `PIPELINE_HOOK` MUST 以异步非阻塞方式触发，未配置时只入队。

### R6 git 写入 MUST 不抢 main

服务端默认 MUST 只做本地 `git add` + `commit`，MUST NOT 自动 push。仅显式设置 `AUTO_PUSH=1` 时允许先 `pull --rebase` 再 `push`，MUST NOT 使用 force。git 操作失败 MUST 如实回报且 MUST NOT 回滚已落盘文件与已入队状态。

### R7 左侧 Tab 与搜索 MUST 满足布局约束

侧栏 Tab MUST 依次为 `目录`、`云端☁️`、`上传`，并在最右有 `🔍` 图书搜索按钮。三 Tab MUST 等分且窄屏不换行；搜索按钮 MUST 固定宽度、不参与等分。

`🔍` 被点击时 MUST 把当前 Tab 切到 `云端☁️` 并聚焦筛选框，以便快速找书。筛选框 MUST 同时覆盖章节、云端与上传三个 Tab。书架页右上角 MUST 有即时过滤搜索框，输入即隐藏不匹配卡片并显示命中计数，`Esc` MUST 清空。

### R8 公开性边界 MUST 如实说明

文档与页面 MUST 写明：上传的整本 EPUB 一旦进入公开仓库即公开可下载，`noindex` 只减少扩散、不等于私有。MUST NOT 用「私有」「仅本人可见」描述公开 Pages 上的文件。

### R9 不改动项

MUST NOT 改 `epubs.json` 的 203 本云端清单、`books/*.epub`、Aa 面板内部功能项、侧栏点击遮罩收起逻辑、用户亲读 `resume_point` / `completion` / 完读计数、其他 Agent 的 roster 与活动锁、三处白名单规则文本。
