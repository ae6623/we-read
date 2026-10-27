# Archive Note — add-ai-qa-manual-backfill

> 本文记录本变更的实际执行结果。代码实现与静态校验已在本回合完成；**真实回补运行（19 篇 / 13 本）需在本机微信读书登录态下执行**，相关真实数字待回补后补全。

## 做了什么（代码侧，已全部落地）

- `weread_ai.py`
  - 新增 `NOISE_HEADINGS`（3.1）与 `_clean_chapters()`（3.2）：前置/版式页**整名命中**才剔除，不误杀「版权制度的起源」。
  - `build_questions()` 先 `_clean_chapters()` 再 `keywords()`，`keywords()` 对切出片段二次过黑名单；`add()` 末端 `_q_has_noise` 兜底丢弃含黑名单词且无通用候选可替的问句（3.3 / 3.4）。
  - `ask()` **零 diff**（3.5）。
  - `save_items()` 新增 `backfill` / `asked_at` 字段（2.4），旧条目缺字段按 `false`。
- `weread_daily.py`
  - argparse 新增 `ai-qa` 子命令：`--book/--n/--date/--all/--limit/--force/--headed`（1.1）。
  - `cmd_ai_qa` / `_cmd_ai_qa`：复用 `open_context`（强制 `--no-proxy-server`），`--book` 只改内存、书名不符清空 `reader_url`（1.2 / 1.4）；`_resolve_reader_url` 按书名定位阅读器（1.3）；调 `weread_ai.run_session`（1.5）；`save_items` 后 `_rebuild_note`（1.6）；stdout 打 `ai_qa_summary`（1.7）。
  - `--all` 回补：`_scan_backfill_gaps` 扫描缺口 → 按书聚合、每书一轮 → 同组问答按原日期写入每篇（`backfill=True`）→ 单本失败记 `ai_qa_backfill_skip` 继续（2.1–2.8）。
- `web_app.py`：`POST /api/ai_qa`（锁占用返 409，子进程隔离，`timeout=900`）、`GET /api/ai_qa/books`（book-registry → book_meta → 扫描 notes，附 status）（1.8 / 1.9）。
- `site_pub.py`：`_render_site_ai()` 对 `backfill` 条目在 eyebrow 后加「事后补问」标注（2.5）+ CSS。
- `templates/index.html`：AI 问书卡片（书名下拉 + 问数 + 两按钮 + 状态回显）（1.10）。

## 验证情况

- `openspec validate add-ai-qa-manual-backfill` → **Change is valid** ✅
- `build_questions` 静态校验（4.6 / 4.7）→ **已运行通过**（文化苦旅去噪、债务问句保留）
- `save_items(backfill=True)` / `_render_site_ai(backfill)` 单测 → **通过**（backfill/asked_at 写入、标注渲染、正常条目无标注）
- 四个 Python 文件 `py_compile` → 通过

## 待本机回补运行后补全的真实数字（[!] 项）

- 实际补齐篇数 / 涉及书本数（预期 19 篇 / 13 本）
- 总耗时、AI 额度消耗
- 回补中遇到的真实问题及根因（如新书奇怪前置页漏词、单本失败原因）
- `grep -rl '<section class="aiqa"` 计数达 22 的确认
- `git diff --stat` 仅 `notes/*.html` 增行、无删正文/进度/时长的确认

## 发布说明（D7）

历史页发布锁定本机：`git push origin fix-publish:main`，只提交本次真正改动的页面。云端只产出 JSON 与重建后的本地 HTML，不由云端推送历史页。沙箱未执行历史页发布。
