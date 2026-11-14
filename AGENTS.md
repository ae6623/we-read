# AGENTS.md — 本仓库协作规则（产物站）

这是**阅读笔记的静态站点仓库**：发布到 GitHub Pages，只有 HTML / CSS / JS / 内容，**没有任何采集或引擎代码**。
生成内容的程序在另一个仓库里，不要在这里找。

## 0. 准入门槛：先读，再动手

**开发这个读书项目的人、本机 agent、另一个账号的 agent，一律先通读本文，再动第一个文件。**
读完按顺序补完，缺哪一步都可能白干一轮：

| 顺序 | 读什么 | 为什么 |
|---|---|---|
| 1 | 本文全文 | 只拉 main、不放敏感内容、提交与发布纪律、可重复流程的固定入口 |
| 2 | **[本仓 `a2a.md`](a2a.md)** | **A2A 的 git 协议指针**：事件板在本仓哪个目录、怎么查消息、怎么写回帖 |
| 3 | 引擎仓 `ae6623/we-read-auto` 的 [`a2a.md`](https://github.com/ae6623/we-read-auto/blob/main/a2a.md) 与 [`AGENTS.md`](https://github.com/ae6623/we-read-auto/blob/main/AGENTS.md) | **A2A 协议正文与监听器在服务端**；三处目录分工、六条铁律、多 agent 并存、`comm_watch.py` |
| 4 | 共享开工须知（跨账号可共同编辑）<https://www.workbuddy.cn/space/d/VEW8rrC632XfmnVguxK7Ka> | 部署参数、事故复盘、人和 agent 都能改的共识面 |

> 架构别搞反：**本仓是笔记前台（静态 Pages），`we-read-auto` 是服务端**。A2A 的协议、监听、调度与部署都归服务端；
> 本仓只承载全体 Agent 共用的事件日文件，不跑服务、不实现监听。事件板路径与查法见 `a2a.md`。

提交前自检：只 `git add` 本次真正写入的文件 · 没有密钥/登录态/绝对路径 · 该跑的固定脚本跑过（如 `tools/series.py --set <slug> --check` 全通过）· 输出口径没写页数/时长/进度。

## 只拉 main

本仓库历史分支很多（100+），全量 clone 会很慢、也很占磁盘：

```bash
git clone --depth 1 --single-branch --branch main <本仓库地址>
```

已有克隆只 `git pull --rebase origin main`，不要 `git fetch --all`。

## 不要放进本仓库（公开可见）

- 任何密钥、token、Cookie、登录态文件
- 内部服务地址、部署参数、后台入口
- 个人身份信息、机器名、绝对路径
- 原始运行日志、调试截图、临时导出

需要这类内容时，放到私有仓库或本机，不要提交到这里。

## 开工与提交纪律（硬性，每次会话必守）

**开工第一步：更新最新代码（两个仓库都要）**

```bash
cd /tmp/we-read      && git pull --rebase origin main   # 产物站（SSH，可达）
cd /tmp/we-read-auto && git pull --rebase origin main   # 生成程序（远程用 SSH：git@github.com:ae6623/we-read-auto.git；HTTPS 缺凭据需先改 SSH）
```

只拉 `main`，不要 `git fetch --all`。确认主流程脚本（`tools/fill_combined_modules.py`、`tools/ai_draft.py`、`tools/series.py`）在位；缺失先从 auto 仓库同步逻辑。

**提交纪律：跑完且未出错，必须合并代码并提交**

- 一次"逻辑完整、未报错"的操作 = 一次 commit + push；不跨多轮堆积未提交改动，也不要整目录扫 diff（只 `git add` 本次真实写入的文件，文本统一 LF）。
- 提交后直接 `git push origin main` 触发 GitHub Pages 发布——**发布不需要另行拍板**，自动发布即可。
- 推送若遇 `github.com:443` 超时，改用 `tools/api_push_files.py`（Git Data API）绕过，不要当成缓存问题。

## 可重复流程（开工前必读）

**不要临时写脚本。** 所有可重复流程都有固定入口；尤其「拆书成系列」，收尾漏跑统一脚本，首页系列 Tab 就会看不到、标题会跳微信读书搜索页。

| 流程 | 说明文档 | 统一命令 |
|---|---|---|
| 拆书成系列 / 系列页维护 | `note-spec/set-series.md` | `python3 tools/series.py --set <slug>` |
| 全量系列体检 | 同上 | `python3 tools/series.py --audit` |
| AI 问书 / 自测内容 | 本文 §AI 内容生产 | `python3 tools/ai_draft.py --dump <slug>` → `--fill <slug> --answers <json>` |
| 新书书卡 → IMA 知识库同步 | `docs/IMA-INGEST.md` §4.2、引擎仓 `HANDOVER.md` §0.18 | `python3 scripts/ima/ima_sync.py --book <slug>` |
| 同步验收（站点有卡、md 不能缺） | 同上 | `python3 scripts/ima/ima_check.py --strict` |
| 书卡壳页 reader js 版本验收（防导图丢失） | `assets/data/reader-js.json`、§硬规则 4 | `python3 scripts/check_reader_js.py` |
| reader js 升级 / 全站壳页版本切换 | `scripts/upgrade_reader_js.py` | `python3 scripts/upgrade_reader_js.py --to reader-<日期>.js --push` |

**书卡产出的硬规则（每本新书必做）**

1. 云端 `compose` **不产 `combined-data.html`**（只发 mindmap / outline / overview /
   modules）。必须再跑 `POST /api/combine {"slugs":"<slug>"}` 产出 `combined.html` +
   `combined-data.html` 并发布到站点仓，线上返回 200 后才具备同步 IMA 的前提。
2. 上线后跑 `python3 scripts/ima/ima_sync.py --book <slug>`，再跑
   `python3 scripts/ima/ima_check.py --strict` 验收。漏同步由不带 `--book` 的
   `ima_sync.py` 全量增量扫描兜底自动补齐。
3. IMA 脚本只在 `scripts/ima/`，不要在 `tools/` 下另建副本；台账
   `ima/manifest.json` 必须入库（记录 `ima_media_id`，增量判定靠它）。
4. **新书上线后跑 `python3 scripts/check_reader_js.py`**：全站壳页必须引用
   `assets/data/reader-js.json` 的 `current`（当前含章节知识导图）。产出模板曾写死
   旧版 `reader-20261110.js`，导致新书回退、导图消失。守卫已挂进
   `.github/workflows/pages.yml` 部署前校验，版本不一致会**直接阻断发布**。
   升级 JS 只能换**新文件名**（CDN `max-age=31536000`，同名覆盖一年不生效），
   再按 `docs/IMA-INGEST.md` §4.2 的 SOP 跑 `upgrade_reader_js.py` 全量切换。

**拆书/系列任务的硬规则**

1. 新套装先在 `assets/data/series-sets.json` 登记（`slug / name / page / units`），再跑脚本。
2. 收尾跑 `python3 tools/series.py --set <slug>`：一次完成「标题本地化 + 同步首页系列卡 + 体检」。
3. 交付前跑 `python3 tools/series.py --set <slug> --check`，**必须「体检：全部通过」才算完成**；有 FAIL 不能说做完。
4. 系列页作者行写成 `作者：XXX　·　NN 章 / NN 条`，脚本才抓得到作者与章数。
5. **不要手改** `index.html` 里的系列卡片——那是脚本产物，下次同步会被覆盖。

### AI 内容生产（AI 问书 / 自测）

**不要假设有外部模型可用。** 云端沙箱到 Google 不通、也没有国内模型 key，`gen_quiz_answer.py` / `gen_mindmap.py` 那种「脚本直连 LLM」的路会整条断掉。

正确分工是**三段式**，Agent 自己就是那个 LLM：

```bash
python3 tools/ai_draft.py --dump <slug>          # 1. 脚本从 outline.html 出素材 → drafts/<slug>.md + .json
# 2. Agent 读素材，填 .json 里的 items[].a 与 cite（cite 必须命中大纲原文，脚本会校验，编造会被打回）
python3 tools/ai_draft.py --fill <slug> --answers drafts/<slug>.json --create --write
python3 tools/ai_draft.py --skeleton <slug> --write   # 只有 outline、没有 combined.html 时补骨架
```

硬规则：

1. 答案只许用 `outline.html` 里的条目与原句，**cite 指向具体章节/要点**，编造会被 `validate()` 拒绝。
2. 必须打标 `AI 自主整理 · 非AI读书返回`——不是微信读书「AI 问书」的原文，不能冒充。
3. 单条 ≤220 字（超了页面排版会断），每条至少 20 字。
4. **不需要登录态**：bookId 搜索、章节目录、`/web/book/outline` 全免登录（实测）。
5. 真要微信自家「AI 问书」原文时才需要登录态，且必须**在当前实例**扫码（`wr_skey` 单会话，扫在别处会顶掉）。

## 内容结构

| 路径 | 放什么 |
|---|---|
| `index.html` | 首页与归档索引 |
| `assets/css/site.css`、`assets/js/site.js` | 样式与前端脚本 |
| `notes/<YYYY>/` | 按年份存放的日期笔记 |
| `books/<slug>/` | 整书页（含章节页、精读页）与 EPUB |
| `templates/` | 日期笔记与整书汇编模板 |

## 改动约定

- 新建日期笔记：复制 `templates/` 里的模板再填，不要手搓结构
- 首页索引：**只替换** `<section class="archive-grid">` 内部的行，不要整页重写
- 书卡 / 封面 / 系列分组：走仓库里的同步脚本生成，不要手改生成的 JSON 索引
- 提交：只提交本次真正写入的文件，不要整目录扫 diff；文本统一 LF
- 写完自查：本地起静态服务看一眼，确认没有样式错位与死链

## 内容口径

- 笔记面向读者：讲清这本书在讲什么、作者怎么论证、哪里值得记，**不写页数、页码、翻页次数、阅读时长、进度**这类流水账
- 面向用户的阅读笔记默认公开；内部协调、原始场次与运行元数据保持私有

## 发布

推送到 `main` 即触发 GitHub Pages 自动发布；发布失败先看该次 Action 的日志，不要当成缓存问题。

---

## 数据保管：json 必须进 git，资料库每日备份

本仓库是**数据落盘处**（不是生成处）：导图归纳 `data/mm-graph/`、SVG 源 `data/mindmap/`、`data/mindmap-material/`（全书素材 / 证据来源，已补录）都已进 git 跟踪。

- **数据生成在引擎仓 `we-read-auto`**；那里的 `AGENTS.md` §6 是数据保管铁律的唯一规范（落库 + 进 git + 资料库备份），本仓只负责**接收并已跟踪的数据要及时 push**。
- 任何一批内容生成 / 修正完，必须 `git add` 本次真实写入的 json + `commit` + `push origin main`，触发 Pages 发布；**不要只留在本地不提交**。
- **资料库备份**由引擎仓统一编排：每日 `cloud_scheduler.start_backup_scheduler()` 定点跑 `backup.run_backup("all")`
  （SQLite 热备 → 进 git 提交推送 → 生成导出包 → 同步资料库台账），并在网页控制台「运维」面板提供
  「🗄 数据备份」卡片（查看 / 手动触发 / 下载导出包）。DB 快照**本地只保留最近 3 天、每天最多 1 份**，
  避免 117 MB 的库因同日多次备份占满磁盘。资料库台账（AGENTS 子页「数据备份快照」，节点 `hp2tQ3sSpbuqH6yo9bsEdw`）
  由 agent 覆盖更新（见引擎仓 §6.④）。
- **资料库**（`workbuddy.cn/space/d/VEW8rrC632XfmnVguxK7Ka`）是离云备份库；本仓 `AGENTS.md` 的改动也要同步到资料库（见引擎仓 §6.②）。
- **缺口（待定）**：`data/outline/`（54 MB，可由 outline.html 重算）仍被 `.gitignore` 排除、未进 git，是否纳入备份待统一决定。
