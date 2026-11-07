# EPUB 阅读器：Aa 入口归位、上传图书与异步补笔记（2026-11-07）

## 一、用户原话与需求拆解

> 继续，你掉线了，Aa面板不能放在右上角下载按钮的左边吗，不用悬浮。然后再增加一个上传epub图书的功能，服务端接收上传后保存在git（找个目录放一下），并且启动异步补笔记流程，自动跑书，匹配微信读书补书流程，左边书目增加一个「上传」和现在的全部书目区分，全部书目改为云端☁️，章节目录改为目录，相当于为上传节省出来了Tab空间，再在书架最右边增加图书搜索🔍，方便快速找书。

| 编号 | 需求 | 落点 |
| --- | --- | --- |
| U1 | Aa 入口放在右上角下载按钮左边，不要悬浮方块 | `reader.html` / `aa-panel.js` / `aa-panel.css` |
| U2 | 增加上传 EPUB 图书功能 | 书架「上传」Tab + 本机上传服务 |
| U3 | 服务端接收后保存在 git 仓库目录 | `reading-notes/epub/uploads/` + `uploads.json` |
| U4 | 启动异步补笔记流程、自动跑书 | 写 `book-registry.json` 入队 + 交接事件 |
| U5 | 对齐已有微信读书补书流程 | 复用 `reading-state-protocol.md` 的 queued 字段 |
| U6 | 左侧书目新增「上传」Tab，与全部书目区分 | 侧栏 `.tabs` 三 Tab |
| U7 | 「全部书目」改「云端☁️」 | Tab 文案 |
| U8 | 「章节目录」改「目录」 | Tab 文案 |
| U9 | 缩短 Tab 名为上传腾出空间 | 2 字 / 2 字 / 2 字，三等分不换行 |
| U10 | 书架最右边增加图书搜索🔍，快速找书 | Tab 行最右搜索钮 + 书架页右上角搜索框 |

## 二、架构约束（先把话说清楚）

1. **GitHub Pages 是纯静态托管，没有服务端进程**。浏览器里的 `fetch` 只能 GET 静态文件，不能写文件、不能 `git commit`、不能启动后台任务。想在前端塞一个 token 直接调 GitHub Contents API 也不可行：token 会出现在公开页面源码里，等同泄露凭据。
2. 因此 U2/U3/U4 的「服务端」只能是**本机（或用户自己的服务器）上跑的一个进程**。本次交付一个零外部依赖风格、与 `tools/tts-proxy/app.py` 同款的 Python 服务，放在 `tools/epub-upload-server/`。服务同时承担两件事：接收上传 + 静态托管 `reading-notes/epub/` 目录，这样上传与阅读**同源**，避开 CORS 与 HTTPS→HTTP 混合内容拦截。
3. **「异步补笔记、自动跑书」的真实边界**：读书 Agent 是另外一套多 Agent 系统（registry / roster / Cue 分发），本机服务无法、也不应该直接拉起别人的阅读进程。本项目已有的、可对接的异步入口是 `book-registry.json`：新书以 `queued` + `owner: null` + `claim.state: unclaimed` + `priority: user_requested` 入队，管理员按 `reading-state-protocol.md` 分发给阅读 Agent 认领跑书并产出笔记。远端 09:51 的提交 `f6e26481c`（`local-epub-tianchao-collapse-opium-war-research-revised`）就是用户上传本地 EPUB 后按同一字段入队的实例，本次严格复用，**不新造一套队列**。
4. 服务端默认只做**本地 git commit，不自动 push**：`main` 是多 Agent 串行写入的权威基线（`revision` 每次 +1），后台自动 push 会抢锁、制造冲突。需要自动同步时可显式设 `AUTO_PUSH=1`，服务会先 `pull --rebase` 再推。
5. 静态页仍带 `noindex`。`noindex` 只减少扩散，**不等于私有**；上传的整本 EPUB 一旦提交进公开仓库就是公开可下载，这点不因页面措辞改变。

## 三、解决方案

### U1 Aa 入口归位

- 删除 `aa-panel.js` 里创建的悬浮方块 `#rdFab`（含 `aa-panel.css` 对应样式与窄屏金色描边规则）。
- `aa-panel.js` 的 `buildFab()` 改为复用顶栏已有的 `#aaBtn`（位置本就在 `↓` 左边），`togglePanel()` 的 `.on` 高亮继续作用在它身上；听书设置按钮 `⚙` 与 `settings` 动作仍能打开面板。
- `#rdPanel` 由 `top:106px` 改为 `top:62px; right:8px`，紧贴顶栏下方右对齐展开，视觉上挂在 Aa/下载按钮下方；不再有第二个浮动 Aa。
- 保留 `🎧` 听书悬浮键：它是朗读控制，不属于 Aa 入口，且用户只要求去掉 Aa 的悬浮。

### U2/U3 上传通道

- 服务：`tools/epub-upload-server/app.py`
  - `GET  /api/health`：服务状态、仓库根、上传目录、registry 版本。
  - `GET  /api/uploads`：返回 `uploads.json` 清单。
  - `POST /api/upload`：前端用 XHR 直接 POST **原始二进制**（`application/octet-stream`，文件名/标题放请求头与查询参数），服务端零 multipart 解析；校验扩展名 `.epub`、ZIP 完整性、`mimetype` 首条且不压缩、`container.xml` 存在、体积 ≤ 15 MB（与云端书架同一阈值）；按规范化书名生成稳定 `book_id = upload-` + `sha256[:12]`，同名重复上传覆盖同一 ID，不重复入队。
  - 落盘 `reading-notes/epub/uploads/<book_id>.epub`，生成/更新 `reading-notes/epub/uploads.json`（字段与 `epubs.json` 对齐，额外带 `uploaded_at`、`sha256`、`source: "upload"`、`note_status`）。
  - 本地 `git add` + `git commit`（默认不开 push）。
  - `GET  /`、`/reading-notes/epub/...`：静态托管仓库根，同源打开书架。
- 前端「上传」Tab：服务地址输入（默认 `http://127.0.0.1:8788`，存 localStorage）、文件多选、拖拽、上传进度、结果列表、失败原因、一键打开阅读器；服务未启动时明确给出启动命令，不静默失败。
- 阅读器支持 `?src=upload&book=<id>`：从 `uploads.json` 取 `meta.file`，其余渲染逻辑与云端书完全一致。

### U4/U5 异步补笔记

服务端每次成功上传做三件事（顺序固定，失败不假装成功）：

1. 重读磁盘上最新的 `book-registry.json`，`revision += 1`，追加一条 `queued` 书目：`platform: "local_pdf"`、`priority: "user_requested"`、`owner_agent_id: null`、`claim.state: "unclaimed"`、`status: "queued"`、`source_format: "epub"`、`upload_path`（仓库相对路径）、`note_status: "pending"`；已有同 `book_id` 不重复追加。更新 `updated_at`。
2. 追加交接事件到 `skills/luoyu-reading/references/agent-communication/YYYY/MM/YYYY-MM-DD.md`，类型标为「用户上传本地 EPUB → 入队补笔记」，写明文件名、稳定 ID、时间、入队状态，**声明不是阅读场次、不代表亲读或完读**；按现有日文件格式 `### [时间] 用户（本机上传服务代写） / upload-...`。
3. 可选 `PIPELINE_HOOK` 环境变量：配置一条本地命令时以 `Popen` 异步触发（不等待、不阻塞响应）；默认不配置，仅入队，由管理员按既有协议分发。

响应返回 `{ok, book_id, queued: true, registry_revision, event}`，前端显示「已入队，等待读书 Agent 认领补笔记」。**不宣称笔记已经生成、不宣称 Agent 已开始跑书。**

### U6–U10 左侧 Tab 与搜索

- 侧栏 `.tabs` 由 2 个变 3 个 + 1 个搜索钮：`目录` / `云端☁️` / `上传` / `🔍`。三个 Tab 等分，搜索钮固定 34px 不参与等分；窄屏字号 11px、`padding:10px 2px`，保证不换行。
- Tab 切换复用现有 `renderList()`：`toc` 渲染章节、`shelf` 渲染 `epubs.json`（云端）、`upload` 渲染 `uploads.json` 并额外渲染上传控件。筛选框覆盖三个 Tab；`upload` Tab 下 placeholder 改为「筛选已上传书名」。
- `🔍` 钮：切换/聚焦筛选框，并把当前 Tab 强制切到 `云端☁️`（书架）以便「快速找书」；搜索框为空时再次点击收起。
- 书架页 `reading-notes/epub/index.html` 右上角增加即时过滤搜索框，输入即隐藏不匹配卡片，显示命中计数；`esc` 清空。这样从书架入口进也能快速找书。
- 「上传」Tab 与云端书目在数据层彻底分开：云端只读 `epubs.json`，上传只读 `uploads.json`，互不污染，也不改 `epubs.json` 的 203 本清单。

## 四、文件清单

| 文件 | 变更 |
| --- | --- |
| `reading-notes/epub/aa-panel.js` | 移除悬浮 `#rdFab`，复用 `#aaBtn` |
| `reading-notes/epub/aa-panel.css` | 删 `#rdFab` 规则，`#rdPanel` 上移到顶栏下方 |
| `reading-notes/epub/reader.html` | 三 Tab + 搜索钮 + 上传面板 + `src=upload` 书目源 |
| `reading-notes/epub/index.html` | 右上角图书搜索框 |
| `reading-notes/epub/uploads.json` | 新增，上传书目清单（初始 `books: []`） |
| `reading-notes/epub/uploads/.gitkeep` | 上传目录占位 |
| `tools/epub-upload-server/app.py` | 新增，上传 + 静态托管 + 入队服务 |
| `tools/epub-upload-server/README.md` | 启动、接口、边界说明 |
| `docs/epub-reader-upload-2026-11-07.md` | 本文档 |
| `openspec/changes/epub-reader-upload-2026-11-07/*` | 本次 change 规范 |

## 五、使用方式

```bash
# 1) 启动本机服务（仓库根目录执行）
python tools/epub-upload-server/app.py
# 默认 http://127.0.0.1:8788，可用 PORT / REPO_ROOT / AUTO_PUSH / PIPELINE_HOOK 覆盖

# 2) 从服务同源打开书架（推荐，上传与阅读都可用）
#    http://127.0.0.1:8788/reading-notes/epub/index.html

# 3) 或仍用线上 Pages 看云端书目；在「上传」Tab 填服务地址后上传
#    https://ae6623.github.io/we-read/reading-notes/epub/reader.html?book=...
```

线上 Pages 只提供云端☁️书目与阅读；**上传、入队、补笔记只在启动了本机服务时可用**，页面会直接显示服务离线与启动命令。

## 六、验收

1. 页面右上角不再出现悬浮 Aa 方块；顶栏 `Aa` 唯一入口，点开面板贴顶栏右侧展开。
2. 左侧 Tab 依次为 `目录 / 云端☁️ / 上传 / 🔍`，窄屏不换行；章节、云端 203 本、上传书目互不串数据。
3. 🔍 在书架与阅读器都能即时过滤书名，命中计数正确，`esc` 清空。
4. 服务启动后上传一本合法 EPUB：`uploads/<id>.epub` 落盘、`uploads.json` 更新、`book-registry.json` 出现一条 `queued` 且 `revision +1`、当日交接文件出现入队事件、页面显示「已入队」。
5. 非法文件（非 .epub / 坏 ZIP / 超 15 MB）被拒且不写任何文件、不入队。
6. 上传的书能在阅读器里按章节打开，`src=upload` 走 `uploads.json`。
7. 全部改动一次性合并提交到 `main`，工作树干净。

## 七、不改动

`epubs.json` 的 203 本云端清单与 `books/*.epub`、Aa 面板内部功能项（字体/字号/行距/主题/双栏/方向/区域点击/方向键/听书）、侧栏点击遮罩收起逻辑、用户亲读 `resume_point` / `completion` / 完读计数、其他 Agent 的 roster 与活动锁、三处白名单规则文本。

## 八、迭代（2026-11-07 11:35）：在线沙箱上传 API + Aa 微调

用户反馈四项，已落地：

1. Aa 面板「按键」分组（↑↓←→ 四个可改下拉）隐藏；默认值与 `onKey` 逻辑保留，方向键行为不变。「硬件按键」分组保留。
2. 面板打开时点阅读区（尤其左侧露出的正文）先收起 Aa 面板，本次不翻页；iframe 内点击不冒泡到父文档，故在 `handleTap` 里处理，长按在面板打开时也不触发。
3. 音量键翻页补齐事件源：`keydown`/`keyup`、`e.key`/`e.code`、`keyCode 24/25/174/175`、阅读器壳自定义 `volumeup`/`volumedown`、MediaSession 蓝牙媒体键；220ms 去重节流，避免 keydown + keyup 双翻。普通 Chrome / 微信浏览器默认不把硬件音量键交给网页，需在浏览器设置里开启「音量键翻页」或换支持该能力的阅读器 App。
4. 上传服务改双模式：本机仓库模式（原逻辑不变）+ 在线沙箱模式（`data/uploads/`、`data/queue.json`、`data/events/`、`/api/sync`、可选 `PIPELINE_WEBHOOK` 异步回调）。前端从 `reading-notes/epub/upload-api.json` 读线上 base，上传清单优先 `/api/uploads`，其中 `file` 为跨域可读的绝对 URL；`sync_to_git.py` 把沙箱数据同步回仓库，完成「保存进 git」。

部署边界：本机 Agent **不直接部署**云端应用，改由 A2A 板把「更新代码 → 检查在跑的任务并保存暂停 → 部署应用 → 回帖 base URL → 恢复中断任务」发给 `workbuddy-cloud-luoyu`。沙箱磁盘不保证跨重新部署持久，长期保存靠 `sync_to_git.py` 同步回仓库。

验证：服务端隔离环境双模式 **49/49** 通过；Aa 行为无头浏览器 **15/15** 通过。
