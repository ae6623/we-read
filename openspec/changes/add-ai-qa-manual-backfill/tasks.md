> 执行规则：每完成一项立刻勾选 `[x]` 并单独提交（commit message 带 `tasks: <编号>`）。
> 无法提交时，把勾选后的本文件全文回帖到 A2A 板，由本机代提交。
> 任何一项做不到就写 `[!]` 并附原因，**不要留空白**——空白等于漏掉。

## 1. 控制台入口（A）

- [x] 1.1 `weread_daily.py` 的 `main()` argparse 新增 `ai-qa` 子命令：`--book`（必填）、`--n`（默认 3，夹 1..8）、`--date`（默认今天）、`--all`、`--limit`、`--force`、`--headed`
- [x] 1.2 新增 `cmd_ai_qa(cfg, book, n, date, headless)`：复用 `cmd_check()` 的 context 构建（走 `open_context`，其已强制 `--no-proxy-server`）
- [x] 1.3 书目 URL 定位：`cfg["reader_url"]`（书名匹配时）→ 书架按书名点击定位 `book_url` → 失败退出码 2（`_resolve_reader_url`）
- [x] 1.4 `--book` 只改内存不落盘；书名与配置不同时清空 `reader_url`（照抄 `run` 子命令那段，防读串书）
- [x] 1.5 调 `weread_ai.run_session(page, title, chapters=<该书章节>, excerpts=[], log, max_questions=n, budget_sec=int(cfg.ai_qa.budget_sec))`
- [x] 1.6 `save_items(title, date, qa)` 后**只重建当日那一篇**笔记页（`_rebuild_note` → `publish_book`，按书粒度，不整站重写、不重建 overview/shelf 索引）
- [x] 1.7 stdout 打一行 `ai_qa_summary ok=<k>/<total> book=<书名> date=<YYYY-MM-DD> elapsed=<秒>`
- [x] 1.8 `web_app.py` 新增 `POST /api/ai_qa`：校验 book 非空、n 夹 1..8、`weread.lock` 拿不到返 409、走 `run_subprocess(["ai-qa", ...], timeout=900)`
- [x] 1.9 `web_app.py` 新增 `GET /api/ai_qa/books`：返回 `{"books":[{title, slug, status}]}`，源优先 `book-registry.json`，退化 `data/book_meta.json`，再退化扫描 notes
- [x] 1.10 `templates/index.html` 新增书名下拉 + 问数 + 「AI 问书补一轮」/「回补全部历史缺口」按钮，显示返回摘要或 `reason`（只改控制台模板）

## 2. 历史回补（A4）

- [x] 2.1 扫描 `reading-notes/books/*/notes/*.html`，按"页内有无 `<section class="aiqa"`"判定缺口，输出待补清单（`_scan_backfill_gaps`；预期 19 篇 / 13 本待本机回补运行后核对）
- [x] 2.2 `--all` 模式：按书聚合，一本书只跑一轮问答（全书视角，与日期无关）
- [x] 2.3 同一组问答写入该书**每一个待补日期**：`for d in dates: save_items(book, d, qa, backfill=True)`
- [x] 2.4 `save_items()` 条目新增 `backfill: true` 与 `asked_at`（真实提问时间），旧条目缺字段按 `false`（已加单测验证）
- [x] 2.5 `site_pub._render_site_ai()` 对 `backfill` 条目在 eyebrow 后加一行：`以上问答为事后补问（YYYY-MM-DD），依据全书内容生成，不代表当日阅读进度。`（已加单测验证）
- [x] 2.6 `--skip-existing` 默认开启（已有区块跳过），`--force` 可覆盖（`_note_has_aiqa` 判定）
- [x] 2.7 单本失败记 `ai_qa_backfill_skip`（含原因）后继续下一本，不中断整批（`try/except + continue`）
- [x] 2.8 分批执行（`--limit` 控制每批书数），每本结束重建对应页面

## 3. 关键词去噪（B）

- [x] 3.1 `weread_ai.py` 新增 `NOISE_HEADINGS`：版权信息、版权页、封面、书名页、扉页、目录、出版说明、出版信息、内容简介、作者简介、编辑推荐、上架、彩插、插图、前言、序言、序、引言、引子、楔子、后记、跋、致谢、附录、注释、参考文献、索引、书评、译后记、译者序
- [x] 3.2 新增 `_clean_chapters(chapters)`：去空白后**等于**噪声词，或以噪声词开头且总长 ≤ 噪声词长 + 2 才剔除（防止误杀「版权制度的起源」）
- [x] 3.3 `build_questions()` 先用 `_clean_chapters()` 再 `keywords()`；`keywords()` 对切出的片段也过一遍黑名单（双保险）
- [x] 3.4 `add()` 兜底：问句含黑名单词且仍有通用候选时丢弃该问句（`_q_has_noise` 末端过滤）
- [x] 3.5 `ask()` 保持零 diff（`has_more=0`、引源提前收尾、静默兜底三判据不动）

## 4. 验证

- [!] 4.1 不启动阅读场次，点控制台按钮 → 日志出现 `ai_qa_plan` → `ai_qa_done`（≥1 ok）→ `ai_qa_saved` —— 原因：沙箱无AI读书登录态/浏览器/AI 额度，无法真实触发；代码路径已接（`run_session` 内部即打 `ai_qa_plan`/`ai_qa_done`，`_cmd_ai_qa` 打 `ai_qa_saved`），待本机运行核对
- [!] 4.2 `data/ai_qa/<书名>.json` 中 `date == 今天` 的条数 == 询问数 —— 原因：同上，需真实运行
- [!] 4.3 该书当日 `notes/<今天>.html` 出现 `<section class="aiqa">`，问句与落盘一致 —— 原因：同上，需真实运行
- [!] 4.4 同一时刻连点两次，第二次返 409，不起第二个浏览器 —— 原因：需真实控制台 + `weread.lock` 并发验证
- [!] 4.5 书目写错 → 退出码 2，不产生空笔记页 —— 原因：代码已在 `reader_url` 解析失败处 `return 2` 且早于 `save_items`，逻辑已就位；退出码路径需真实运行最终确认
- [x] 4.6 `python -c "import weread_ai as w; print(w.build_questions('文化苦旅', ['版权信息','引子','道士塔','莫高窟','阳关雪'],[],None,None,4))"` 输出不含「版权信息」「引子」—— **已运行通过**
- [x] 4.7 `build_questions('X', ['版权信息','版权制度的起源','第一章 债务'],[],None,None,4)` 保留含「债务」的问句—— **已运行通过**
- [!] 4.8 `grep -rl '<section class="aiqa' reading-notes/books/*/notes/*.html | wc -l` == 22 —— 原因：当前仅 3 篇，需本机回补 19 篇后达 22
- [!] 4.9 每篇补上的区块都带「事后补问」标注，日期为真实补问日 —— 原因：渲染逻辑已单测通过（`_render_site_ai` 对 `backfill` 条目加标注），真实落盘待本机回补
- [!] 4.10 `git diff --stat` 只出现 `notes/*.html` 增加行，无删正文/进度/时长的 `-` 行 —— 原因：历史页发布按 D7 锁本机，沙箱不推送历史页；待本机 `git push origin fix-publish:main` 后核对
- [!] 4.11 中断后重跑幂等，已完成的书跳过 —— 原因：`--skip-existing` 已实现（`_note_has_aiqa` 判定），幂等行为待本机回补中断重跑验证

## 5. 同步、发布与收尾

- [!] 5.1 本机 `C:/Users/ROG/weread-auto` 与云端部署源 `C:/Users/ROG/weread-cloud` 两份代码都改 —— 原因：沙箱无法访问你本机两个 Windows 工作目录；代码已写入 `we-read-auto` 仓库（GitHub），需你本机各同步一份（或等云端自更新拉取）
- [x] 5.2 行尾统一 LF；提交前跑 `git diff --check` 与 `git diff --stat`（见本回合提交，行尾已 LF）
- [x] 5.3 只提交本次涉及文件（`weread_ai.py`/`weread_daily.py`/`web_app.py`/`site_pub.py`/`templates/index.html` + openspec 文档）
- [!] 5.4 历史页发布由本机执行（`git push origin fix-publish:main`），云端只产出不推历史页 —— 原因：按 D7 历史页发布锁定本机、沙箱无权也不应推送历史页；`cmd_ai_qa` 代码已就绪，发布动作由你本机执行
- [!] 5.5 全部完成后 `openspec validate add-ai-qa-manual-backfill` 通过，再 `openspec archive add-ai-qa-manual-backfill` —— 原因：`openspec validate` **已通过**（Change is valid）；`archive` 待真实回补跑完后再执行，避免把未运行验证的行为固化进 `specs/`
- [!] 5.6 在本 change 目录补 `archive-note.md`：实际补齐篇数、总耗时、遇到的问题与真实根因 —— 原因：草稿已建，真实回补篇数/耗时/根因待本机回补运行后补全（只写事实，不写"应该没问题"）
