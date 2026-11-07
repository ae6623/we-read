# 任务清单

## 1. 需求与规范

- [x] `docs/epub-reader-upload-2026-11-07.md`：需求 U1–U10、架构约束、解决方案、文件清单、验收。
- [x] 在 `docs/allow-private-fulltext-archive-2026-11-07.md` 追加本次需求与方案指向。
- [x] `openspec/changes/epub-reader-upload-2026-11-07/`：`proposal.md` / `design.md` / `tasks.md` / `specs/epub-upload/spec.md`。

## 2. Aa 入口归位（U1）

- [x] `aa-panel.js`：`buildFab()` 复用 `#aaBtn`，不再创建 `#rdFab`；`closePanel()` 兼容 fab 为宿主元素。
- [x] `aa-panel.css`：删除 `#rdFab` 基础与窄屏规则；`#rdPanel` 上移到 `top:62px`。
- [x] 验证：DOM 中无 `#rdFab`，顶栏 `Aa` 点击开合面板，听书 ⚙ 仍能打开面板。

## 3. 上传服务（U2/U3/U4/U5）

- [x] `tools/epub-upload-server/app.py`：`ThreadingHTTPServer` + 原始二进制 POST、`/api/health`、`/api/uploads`、静态托管、CORS。
- [x] EPUB 校验：扩展名、ZIP、`mimetype` 首条 STORED、`container.xml`、15 MB 上限。
- [x] 落盘 `reading-notes/epub/uploads/` + 维护 `uploads.json`（幂等 `upload-*` ID）。
- [x] `book-registry.json` `queued` 入队、`revision +1`、当日交接事件追加。
- [x] 默认本地 commit 不 push；`AUTO_PUSH=1` 才 rebase+push；`PIPELINE_HOOK` 可选异步钩子。
- [x] `tools/epub-upload-server/README.md`：启动、接口、字段、边界、失败排查。

## 4. 前端 Tab、搜索与上传面板（U6–U10）

- [x] `reader.html`：Tab 改 `目录 / 云端☁️ / 上传 / 🔍`，窄屏不换行。
- [x] `reader.html`：上传面板（服务地址、文件选择/拖拽、上传、结果、离线提示）。
- [x] `reader.html`：`src=upload` 走 `uploads.json`；`🔍` 切到云端并聚焦筛选框。
- [x] `index.html`：右上角图书搜索框，即时过滤 + 命中计数 + `esc` 清空。
- [x] `reading-notes/epub/uploads.json` 初始空清单、`uploads/.gitkeep` 占位。

## 5. 验证与交付

- [x] JS 语法校验（`node --check` / `new Function`）。
- [x] 服务本地启动、health、上传一本合法 EPUB，核对落盘 / 清单 / registry / 交接事件。
- [x] 非法文件被拒且不产生副作用。
- [x] 无头浏览器冒烟：Tab 文案与数量、无 `#rdFab`、搜索过滤、面板展开、无脚本报错。
- [x] 清理临时文件，一次性合并提交并推送 `main`，确认工作树干净。
