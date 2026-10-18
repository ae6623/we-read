# 代码类 Agent 自动化实现参考（仅约束代码类 Agent 自身）

> **适用范围声明**：本文件只描述 weread-auto（代码类 Agent，Playwright 自动化）的实现方式与实测结论。
> 其他 Agent——无论是直接操作浏览器还是人工整理——**不需要阅读、不受本文件约束**；
> 协作目标与协议以 `SKILL.md`、`coordination.md`、`decisions.md` 为准，实现方式各自独立。
> 代码位置：`C:\Users\ROG\weread-auto`（本地 git 仓库）。

## 登录态

- 必须**网页版扫码登录**：App/H5 登录态缺 `wr_rt` cookie，无法上报网页阅读时长。
- cookie 存 Playwright 持久化 profile；过期后重新扫码（日志会出现 `login_required` + 二维码截图）。

## 阅读时长与打卡验证（代码类 Agent 的优势能力）

- 网页版阅读计入打卡；当日阅读超 5 分钟为有效日。
- 时长由阅读器翻页时自己 POST `weread.qq.com/web/book/read`（带 `rt` 秒数，返回 `succ:1`）；
  脚本只做原生翻页，**不伪造任何上报请求**。
- 三重证据链（按可靠性）：① 网络监听统计 `succ:1` 次数（`read_ok`，最可靠）
  ② 会话日志 `session_end` 行 ③ readinfo 接口（**有明显延迟**，仅供参考；
  最权威核对是 App「我 → 阅读时长」）。`readdata/summary` 接口 401，放弃。
- 阅读进度：readinfo 的 `readingProgress`。**完读判定只认 progress ≥ 100**——
  `bookInfo.finished` 对未读完的书也可能返回 1，不可靠（曾误判，已修）。

## 新版网页阅读器实测结论

- **canvas 渲染**：`body.innerText` 只有几十字符；正文在隐藏 DOM 的
  `div.readerChapterContent`（当前页文本在 `[class*=renderTargetContainer]`）。
- **翻页手势**：方向键 / PageDown 有效；鼠标点击、滚轮无效（画布哈希实测判定）。
- 打开阅读器可能停在扉页并弹面板遮罩——先 Escape 关遮罩再翻页。
- 单次阅读 10 分钟（平台对单次过长的自动阅读有时长审核，不建议调大）。

## 选书与防识别

- 选书（2026-10-18 起 follow 主引擎，`weread_daily.py` 的 `follow_main_engine=True`）：
  只读两类书——用户显式指定（控制台 `book_title` / `reader_url`，视为用户指令）
  或注册表中本人 held 的在读书。新书选书与认领归微信读书主引擎；
  两类都没有时不开读、不自行从书架挑新书，如实报告并等主引擎认领/分配
  （原「跳过已读完 → 当前在读 → 下一本」的自动选书已停用）。
- 翻页节奏随机：间隔 15~45 秒随机、8% 概率长停顿、偶尔回翻一页。

## 稳定性工程

- profile 占用预检：Chromium 在 profile 被占用时**不快速失败而挂起**，必须先检查再启动；
  启动参数固定 `--no-proxy-server`（系统代理/WPAD 不稳定，曾报连接失败）。
- `weread.lock` 文件锁互斥（定时任务与网页端手动操作不撞车）+ `STOP` 文件停止。
- 发布幂等：无变更不提交（避免空提交）；首页索引“保留 + 替换”策略，
  **绝不重建整个卡片区**（会删掉其他 Agent/用户建的卡片）。
- 生成 HTML 统一走 `write_html` 出口清理行尾空白（满足 `git diff --check`）。

## 发布行为（用户已授权，见 decisions.md）

- 每日阅读结束即发布；日产内容自动合并 `main`，无需逐次授权。
- 归档结构：`reading-notes/books/<slug>/{overview.html, notes/YYYY-MM-DD.html, final.html, final.epub}`；
  早期旧路径的书不迁移。
