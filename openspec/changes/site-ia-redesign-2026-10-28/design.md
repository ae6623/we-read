## Context

产品经理方案 v2（`docs/site-ia-redesign-2026-10-28.md`）已由站主拍板，本 change 是它的执行拆分。方案跨首页结构、58 页内容迁移、全站文案与标注，涉及两个角色（前端 `frontend-mod` / 内容 `luoyu-content`）。

当前站点现状（10-28 实测）：78 张通读卡、55 本有精读页（mindmap）、58 页 deep-read、线上 overview 75 本；本地仓落后于线上（git 协议在沙箱不通，本地 `index.html` 缺线上已落的 `card-title-link`、card-actions 重排与 CSS 版本升级）。

以下决策用于防止实现走偏，逐条附理由。

## Decisions

### D1：改 `index.html` 前 MUST 以线上版为基准

本地仓 git fetch 不通、内容落后。实测本地 `index.html`（102470B）与线上（95929B）卡片集合一致但结构不同——本地缺 frontend-mod 后来的改动。

若直接拿本地版提交，会把对方的 `card-title-link`、card-actions 重排、CSS 版本号整批回退。**必须先 `gh api` 拉线上版，在其上做增量改动**。

### D2：deep-read 合并的闸门按 8.3 从严，不做「计数后跳过」

方案 3.3 原写「未匹配数 ≤ 5% 且逐本记录」，但 8.3 追加要求更严：匹配失败 MUST 逐条记录「原页 / 原问题 / 处置结果 / 目标锚点」，未处置数必须为 0 才允许下线。

理由：逐章追问是 deep-read 唯一不与精读页重复的内容，一旦静默丢弃就找不回来（原页随后删除）。按 8.3 执行。

### D3：原 deep-read URL 保留迁移页，不做硬删除

GitHub Pages 不提供通用重定向，书签和站外链接仍会打到原 URL。方案 3.2 说「删除」，8.3 修正为「保留轻量迁移页」——以 8.3 为准：正文迁走，URL 留一个说明去向的轻页面。

### D4：文案统一只改口径词，不改既有事实

8.1 明确不删除或改写既有阅读事实与历史记录。因此 `rewrite_legacy_copy.py` 只替换口径类旧词（读前通读 / 全书导图 / 精读深读 / 网页版 / 待整理），日期笔记里的具体阅读记录、原句、问答内容一律不动。

### D5：角色边界——前端结构归 FE，内容迁移归 LC

`index.html` 结构 / Tab / 搜索 / 筛选 / 折叠 / CSS / JS 是 frontend-mod 认领范围（其 todo 规则明写「只改自己认领的文件」）。本提案起草人（luoyu-content）承接内容侧：deep-read 合并、文案统一、来源标注、IA-05 文案。

任务清单已逐条标 `[FE]` / `[LC]`。若 frontend-mod 未及时认领，需站主授权后 `[FE]` 项才可由 luoyu-content 承接（见 tasks 6.3）。

### D6：沙箱约束必须写进执行方式

- 提交：git 协议不通，一律走 GitHub REST（`gh_api.GhApi.publish_paths`），分批 ≤ 20 文件。
- LLM：沙箱无可用 LLM，`8.2` 的来源标注只能基于页面既有结构做模板化标注 + 对已落库原文（`book_outline.quote`）保留「原文引句」，不能现生成内容。
- 取数：本地 `data/mindmap/*.json` 为空、本地 mindmap 仅 18 本，凡判定「某书是否有某页」一律以线上仓库树（git trees API）为准。

### D7：EPUB 按「暂不放」执行

方案 ⚠ 段注明：EPUB 按钮上一轮刚因「下载到假文件」隐藏 68 处，本方案默认不放，等真产物可用再恢复。若要现在放回需站主一句话。
