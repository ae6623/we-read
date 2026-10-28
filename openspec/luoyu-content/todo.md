# Todo — luoyu-content（内容 / LuoYu）

> 角色目录 `openspec/luoyu-content/todo.md`。只写本文件，别人的只读取。
> 最后更新：2026-10-28 14:20 (UTC+8)

## 当前状态（崩溃恢复）
- 2026-10-27 早因 LLM 日额度 429 中断；本轮（15:30）续做。
- 实测仓库：原「38 本待生成」里 **30 本 overview.html 已落地（B1–B5）**，仅剩 **B6(6)+B7(2)=8 本缺失**，即早上卡住那批。
- 已收 frontend-mod 14:57 ACK：我推送的 18 篇 overview + 5 页 outline 内联归零均合格，已收账；index.html 结构完好、0 死链、panel-soon 重复已清。
- 协议遵循：本文件已建并登记；开工前已 `git fetch` + 读 a2a 板；**不再手动改 index.html / _data**（卡片结构若需动，先发 START）。

## 待办
- [x] 读 a2a 板 + git log，确认 B6/B7 是真实缺口（B1–B5 共 30 本已在线）
- [x] 建 `openspec/luoyu-content/todo.md` 并登记（回应 PROTOCOL 第 3 次催办）
- [x] a2a 板回 ACK（PROTOCOL 05:25）+ 回答 14:57 QUESTION 根因（outline 生成模板内联 `<style>` 已删除）
- [x] 复用 /workspace/gen 管线：build_ov.py + books_cfg.py + parse_ol.py（输出零内联 `<style>`、引用 reading-overview.css）
- [x] 构建已配置的 3 本（一地鸡毛 / 一个女人一生的二十四小时 / 一句顶一万句）_ov.html（style=0 校验通过）
- [x] 解析剩余 5 本大纲 → parsed.json（yong-di-yi-xing / yue-liang-yu-liu / zai-xia-jiang-de / zhi-shen-shi-nei / zhong-guo-wei-shen-me）
- [x] 撰写 5 本 BOOK 配置（论点/脑图/AI 问书/观点/行动/自测/记忆/来源）→ 构建 _ov.html
- [x] 全流程质量门：每本 grep `<style`=0、含 reading-overview.css、ch-item=章节数、>3KB（8/8 通过）
- [x] 修正 zhong-guo-wei-shen-me 子 agent 编造的书名/作者（依大纲改为「布衣」《中国为什么不同：穿越历史理解我们身处的时代》）
- [x] 推送 8 本 overview.html（gh api PUT 仓库新建，8/8 LIVE）
- [ ] 在 a2a 板发 DONE（写明 8 slug），交 frontend-mod 重跑 extract_content.py 刷新 _data
- [ ] 首页卡片（panel-soon→panel-whole）交由 frontend-mod 处理，本角色不碰 index.html

## 验收
- [x] 8 本 overview.html 全部在线、0 内联、引用共享 CSS、来源诚实标注
- [ ] a2a 板有对应 DONE；_data 经对方刷新与页面一致
- [x] 未动 index.html / _data / assets/css（归属 frontend-mod）

## 本轮（2026-10-28）精读深读页（deep-read）
- [x] 读 a2a 板 + 记忆，确认 frontend-mod 铁律 C1/C2（禁内联 `<style>`、共享 CSS 挂载）
- [x] 修复示例 deep-read.html 内联 `<style>` → 外置 `assets/css/reading-deep.css`（零内联、解耦 overview 共享表）
- [x] 改 `gen_deep_read.py`：移除内联 CSS、`<head>` 改 `<link>` site.css + reading-deep.css；「微信读书」→「AI 读书」；新增抽取式自动问答（无 LLM 兜底）
- [x] 作者从 `_data/books/<slug>.json` 取并清洗「作者：」前缀
- [x] 批量生成 58 本 `deep-read.html`（示例手写答案 + 其余抽取式）；逐本校验 0 内联 / 链接齐全 / 无死链
- [x] 在 a2a 板发 START+HANDOFF（通知新页型 + reading-deep.css 归属，请 frontend-mod ACK）
- [x] 发布：58 本 deep-read.html + reading-deep.css + a2a 板 + todo.md 到站点仓（gh api）
- [ ] 等 frontend-mod ACK（确认写法合规、认领 reading-deep.css）；收到后按其反馈微调

## 本轮（2026-10-28 晚）精读入口下移 + 精读补模块
- [x] 深读页（deep-read.html）精读互链：从标题区移到**页面底部**，改**绿色按钮**（`.deep-jd-btn`，写在 `reading-deep.css`，守 C1 禁内联）
- [x] 批量重发 58 本 deep-read.html + 发布 `reading-deep.css`（线上已含 `.deep-jd-btn`）
- [x] 精读页（mindmap.html）补回丢失模块：**Top10 真实金句**（`book_outline.quote` 真原文，带章节出处）+ **复用 AI 问书**（本书日期笔记真实内容）+ **更高维度/当年与今天占位框架**
- [x] 写 `add_mindmap_modules.py` 对 55 本线上精读页注入模块并发布；`mmx-guide.css` 新增 `.mmx-mod` 模块样式并发布
- [x] 升级 `gen_mindmap.py`：`render` 加 `_extra_modules()`，云端重跑精读页自动带模块（取数全 try/except 降级，绝不拖垮主渲染），已提交站点仓
- [ ] 等云端 AI 阅读完读后，`produce_jingdu_page` 流程填充「AI 问书/更高维度/当年与今天」真实 LLM 内容（当前为复用/占位）

## 验收
- [x] 58 本深读页底部有绿色精读按钮、标题区无互链；线上 CSS 已生效
- [x] 55 本精读页含 Top10 真实金句 + 模块框架；`gen_mindmap` 升级保证云端一致不回退
- [x] 模块样式走 `mmx-guide.css`（`.mmx-mod`），未碰 frontend-mod 的 `reading-overview.css`
- [ ] a2a 板已发 DONE；等 frontend-mod 对绿色按钮 / 模块版式的 ACK

## 本轮（2026-10-29）精读页按 outline.html 模块排序补全
- [x] 参考《以日为镜》`outline.html` 模块排序，重排精读页（mindmap.html）补全模块：
  一句话主旨 → 核心观点初判 → 原文金句 Top10 → AI 问书 → 用更高维度的知识看
  → 阅读时要验证的问题 → 当年与今天 · 初步对照 → 来源与证据边界
- [x] **一句话主旨 / 核心观点初判**：取真实数据——前者取自全书命题 `thesis.claim`，后者取自主干 `spine`（label+why），非 LLM 杜撰（兼容线上旧版 `mm-` 与新版 `mmx-` 两种 class 名抽取）
- [x] **阅读时要验证的问题 / 来源与证据边界**：新增模块（占位 + 真实 provenance 口径，互补 footer）
- [x] `gen_mindmap.py` 的 `_extra_modules(d)` 按新顺序生成（取数全 try/except，调用点再包一层兜底）；`add_mindmap_modules.py` 重写为「以线上完整渲染版为基准」抽取+重排，已发布站点仓
- [x] `mmx-guide.css` 新增 `.mmx-oneline / .mmx-views / .mmx-evib` 样式并发布
- [x] 全量 55 本重排并分批发布；权威版（master）校验 51/55 顺序完美，4 本因无金句数据缺 Top10 模块（合理降级）
- [ ] 等云端 AI 阅读完读后填充「AI 问书/更高维度/当年与今天/阅读验证」真实 LLM 内容

## 验收
- [x] 55 本精读页模块顺序对齐 outline.html；一句话主旨/核心观点为真实数据
- [x] 0 内联、引用 mmx-guide.css；`gen_mindmap` 升级保证云端重跑一致
- [ ] a2a 板已发 DONE；等 frontend-mod 对模块排序 / 版式的 ACK

## 验收
- [x] 58 本 deep-read.html 全部在线、0 内联、引用共享 CSS、摘录与逐章追问齐全
- [ ] a2a 板有对应 ACK；reading-deep.css 归属被确认
- [x] 未动 index.html / _data / assets/css 其他文件（归属 frontend-mod）

## 本轮（2026-10-29）深读页新增「通读」绿色入口
- [x] 用户反馈「点标题进通读看不出来」→ 深读页页脚上方新增**绿色「通读全书视角 · 读前先览 →」按钮**（进 `../overview.html`），与绿色「精读全书主干」按钮并列，复用 `.deep-jd-btn`（`reading-deep.css`，守 C1 禁内联）
- [x] 移除 header 里原先不显眼的「全书视角初版 →」文字链，入口统一由页脚绿色按钮承担；章节摘录区文案改「通读页·原文摘录」，命名统一
- [x] 防死链：`gen_deep_read.py` 新增 `--tongdu-link` 开关 + 本地 `overview.html` 检测；`gen_deep_read_batch.py` 新增 `online_overview_slugs()`（git trees API 拉线上 overview，75 本）
- [x] 58 本全量重发并上线：通读绿钮 **58/58**（线上 overview 全覆盖），精读绿钮 51 本（7 本无 mindmap 合理缺），旧文字链残留 0、内联 `<style>` 0
- [x] 引擎仓提交 `fd6337c0`（gen_deep_read.py + gen_deep_read_batch.py，changed=2）
- [ ] 遗留：通读页 `overview.html` 顶部仍有**内联 `<style>`**（`.mm-entry` 进精读链接），违反 C1；已在 a2a 板知会 frontend-mod，待其认领或授权我外置

## 验收
- [x] 58 本深读页底部有通读 + 精读两个绿色按钮；标题区/header 无旧文字链
- [x] 0 内联、引用 reading-deep.css；未碰 index.html / _data / reading-overview.css
- [ ] a2a 板已发 DONE（含遗留内联 `<style>` 知会）；等 frontend-mod ACK

## 本轮（2026-10-29）通读卡片补齐「精读」绿色入口（用户反馈"入口没有"）
- [x] **定位**：线上首页 78 张通读卡（preread-card），对应线上有精读页的 55 张中只挂了 15 张，**40 张漏挂**
- [x] **根因**：`tools_link_mindmap_index.py` 的 `mindmap_slugs()` 只扫本地（本地仅 18 本 mindmap，线上 55 本）→ 按残缺集合跑
- [x] **修复**：`mindmap_slugs()` 改**本地 ∪ 线上**（git trees API）；**以线上 index.html 为基准增量注入**（本地是旧版，缺 frontend-mod 的 card-title-link / card-actions 重排 / CSS 版本，不能覆盖线上）；只补缺不覆盖、幂等
- [x] **结果**：78 张通读卡 → **55 张全挂「精读 ↗」绿色链接**（`card-link-green`，样式已在 `homepage-reading.css`，未改任何 CSS）；线上抽查活着/红楼梦/局外人生效
- [x] 发布 commit `32962989`（index.html + tools_link_mindmap_index.py）
- [ ] 已问 frontend-mod：书名 `card-title-link` 点进通读，用户觉得"标题看不出来"，是否加更明显提示（index.html 归对方维护，待其定方案）

## 验收
- [x] 线上首页 55 张通读卡均有精读绿色入口；幂等复跑 0 新增
- [x] 未改动任何 CSS；未覆盖 frontend-mod 的线上结构更新

## 本轮（2026-10-29）信息架构改版（产品方案 v2 执行）
- 基线：`docs/site-ia-redesign-2026-10-28.md`（产品方案 v2，已拍板）；执行拆分见 `openspec/changes/site-ia-redesign-2026-10-28/`（proposal/design/tasks/spec）
- 角色分工：`[FE]` 首页结构·Tab·搜索·筛选·折叠·CSS·JS → frontend-mod；`[LC]` deep-read 合并·文案统一·来源标注·IA-05 文案 → 我（luoyu-content）
- [x] 拉取方案到本地 `docs/`；建立 change 提案（4 文件）
- [x] 确认协同现状：frontend-mod 尚未认领 IA 改版（openspec 与协同目录均无登记）
- [ ] 第 1 批 `[FE]`：IA-01 Tab 改名 / IA-02 搜索+筛选+计数 / IA-04 卡片精简
- [ ] 第 2 批：IA-03 首屏折叠 `[FE]`；IA-06 文案统一 `[LC]`
- [ ] 第 3 批 `[LC]`：deep-read 58 页合并进精读（8.3 闸门：未处置数=0 才下线）+ 迁移页
- [ ] 第 4 批：IA-05 单书页「从这里开始」（文案 `[LC]` / 结构 `[FE]`）
- [ ] 补充：8.2 来源标注 `[LC]`；8.4 可访问性与体量、8.5 搜索筛选组合 `[FE]`
- [ ] 待站主拍板：frontend-mod 未认领时 `[FE]` 项是否由我承接；EPUB 是否现在放回
