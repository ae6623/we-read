## Why

AI 问书（`weread_ai.py`）自 2026-10-25 已能完整跑通：浏览器内点开面板、提问、按 `/web/ai/proxy` 流式帧判收尾、落盘 `data/ai_qa/<书名>.json`、渲染进当日笔记页。2026-10-26 实测四本书各 3 问全部成功。

但它现在"有而不常用"，三个缺口：

1. **入口单一**：唯一调用点在 `weread_daily.py:2341`，绑在整场阅读的收尾流程里。控制台（`web_app.py`）没有任何 `ai_qa` 路由，想对某本书单独补一轮必须跑满整场阅读。
2. **历史欠账**：`reading-notes/books/*/notes/*.html` 共 22 篇笔记，含 `<section class="aiqa"` 的只有 3 篇，缺 19 篇、涉及 13 本书。
3. **提问质量**：`keywords()` 从章节名抽词时把前置页收进来。日志实证 2026-10-26：《文化苦旅》《透过地理看历史系列》都问到「版权信息」，《以日为镜》问到「引子」，白花额度。

## What Changes

- `weread_daily.py`：新增 `ai-qa` 子命令，参数 `--book / --n / --date / --all / --limit / --force / --headed`，退出码 0/2/3/4/5。
- `web_app.py`：新增 `POST /api/ai_qa`（走 `run_subprocess`，不在此进程内跑 Playwright）与 `GET /api/ai_qa/books`。
- `templates/index.html`：新增书名下拉 + 问数 + 「AI 问书补一轮」按钮。
- `weread_ai.py`：新增 `NOISE_HEADINGS` 与 `_clean_chapters()`，`build_questions()` 去噪；`save_items()` 条目新增 `backfill` / `asked_at` 字段。
- `site_pub.py`：`_render_site_ai()` 对 `backfill` 条目追加「事后补问」标注。
- 数据：回补 19 篇历史笔记页的 AI 问书区块。

## Impact

- Affected specs: `ai-qa`（新建）
- Affected code: `weread-auto/weread_ai.py`、`weread_daily.py`、`web_app.py`、`templates/index.html`、`site_pub.py`
- 数据结构：`data/ai_qa/*.json` 的 item 新增两个可选字段，旧条目无此字段时按 `backfill=false` 处理，向后兼容
- 发布权限：回补改的是历史页 HTML，**只能由本机发布**。云端保守发布策略只允许追加当天 `notes/<date>.html`，动历史页会缩水覆盖
- Out of scope：旧路径 `notes/2026/*.html`（5 篇，10-17 四篇 + 10-18 一篇）结构与新页不同，本轮不动
