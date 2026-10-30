# 笔记台账与补偿规范（notes-ledger）

> 2026-10-31 由 cloud-agent2 建立，用户定：**已产出的笔记要有库表存着，笔记下每个模块的产出情况也要存着**，下次一键生产能查漏补缺、能跳过；出问题时的**补偿 = 重新产出这份笔记**。
>
> 本文是这套台账的**唯一规范入口**。任何 agent（本机 / 云端 / 别的账号）都可以按本文在自己的部署里复现同一套表和流程，实现代码在 `ae6623/we-read-auto`（见文末「实现索引」）。

---

## 0. 权威边界（先看清，别拿台账当事实）

| 东西 | 位置 | 谁是权威 |
|---|---|---|
| 笔记正文（HTML/JSON/EPUB） | 站点仓库 `ae6623/we-read` 的 `reading-notes/books/<slug>/` | **权威** |
| 该书的归属 / 认领 / 完读 | `skills/luoyu-reading/references/book-registry.json` | **权威** |
| 跨 agent 交接与事件 | `references/agent-communication/YYYY/MM/YYYY-MM-DD.md` | **权威** |
| 笔记台账 `book_note` / `book_module` | 各自部署目录的 `weread-data/we_read.db` | **索引，不是事实** |

铁律：**台账与 main 冲突时，以 main 的实际文件为准**，台账只能用来「快速判断要不要动手」，不能用来声称「这本书做完了」。台账在各自环境里，别的 agent 读不到你的库，所以任何结论都要能被 main 里的文件复核。

---

## 1. 两张表

### 1.1 `book_note`（一本书一行）

| 字段 | 含义 |
|---|---|
| `slug` | 书目录名（`reading-notes/books/<slug>`），主键 |
| `book` / `author` / `book_id` | 书名 / 作者 / 微信读书 bookId |
| `status` | `empty` / `partial` / `ok` / `failed`（见 1.3） |
| `steps_ok` / `steps_all` | 步骤完成数 / 总数（固定 4） |
| `mods_ok` / `mods_all` | 精读子模块完成数 / 总数（固定 8） |
| `last_run_at` / `updated_at` | 最近生产时间 / 台账更新时间 |

### 1.2 `book_module`（每个产物 / 模块一行）

| 字段 | 含义 |
|---|---|
| `slug` + `module` | 联合主键 |
| `kind` | `step`（整书步骤）或 `sub`（精读页里的模块） |
| `parent` | 子模块填 `mindmap`，步骤行留空 |
| `status` | 见 1.3 |
| `path` / `size` / `md5` | 产物文件（相对书目录）、字节数、内容指纹 |
| `mode` | 生产通道：`llm` / `import` / `from-outline` / `backfill` / `page` |
| `detail` | JSON：`files`（各文件大小）、`items`、`chapters`、`skipped`、`submodules`、`inferred` |
| `run_at` / `updated_at` | 该模块产出时间 / 记录更新时间 |

### 1.3 状态语义（**这是补偿判定的全部依据**）

| status | 含义 | 一键生产时的行为 |
|---|---|---|
| `ok` | 本次真的产出了，且指纹已记 | 文件核对通过 → **跳过** |
| `skipped` | 已有产物，本次未重做 | 文件核对通过 → **跳过** |
| `stale` | 记着 ok，但**文件不见了 / 变小了 / md5 变了** | **重跑该步** |
| `failed` | 上次失败 | **重跑该步** |
| `missing` | 已知应有但没有（目前只用于精读 8 个子模块） | 不进 run，只进「缺模块」清单 |

`book_note.status` 的算法：4 个步骤都 `ok/skipped` 且 8 个模块都齐 → `ok`；步骤全但模块缺 → `partial`；有 `failed` → `failed`；什么都没 → `empty`。

### 1.4 模块命名（固定，不许自创）

- **步骤**：`outline` / `overview` / `mindmap` / `publish`
- **精读子模块**：`mindmap.oneline`、`mindmap.views`、`mindmap.top10`、`mindmap.aiask`、`mindmap.coreask`、`mindmap.higher`、`mindmap.verify`、`mindmap.thennow`

对应关系（文件 → 模块）：

| 模块 | 产物文件 |
|---|---|
| `outline` | `outline.html` + `outline.json` + `outline.md` + `outline.epub` |
| `overview` | `overview.html` |
| `mindmap` | `mindmap.html` |
| `publish` | 无文件，记提交结果 |
| `mindmap.<k>` | 在 `mindmap.html` 里的 `<section class="mmx-mod" aria-labelledby="<k>">` |

---

## 2. 台账怎么被写进去

只有三个入口，别手工改库：

1. **生产时自动写**（常态）：`compose_book.run_book()` 每跑完一步就调 `record_step()`，写产物指纹 + 状态 + 通道；`mindmap` 步额外扫页面里的 8 个模块，缺的写 `missing`。
2. **扫描回填**（换环境 / 首次接入 / 库丢了）：扫站点仓库里已存在的文件，一次性登记（幂等，按 `slug+module` upsert）。
3. **核验**（定期 / 怀疑不一致时）：拿台账指纹和磁盘文件对一遍，把对不上的标 `stale`。

`publish` 的回填是**推定**：文件能在站点仓库树里看到 ≈ 已在 main 上，标 `ok` + `detail.inferred=true`。真要确认还是看 git 提交。

---

## 3. 三个操作（照着敲）

以下命令都在**部署目录**执行（本机 `C:/Users/ROG/weread-auto`、cloud-agent1 `C:/Users/ROG/weread-cloud`、cloud-agent2 `C:/Users/ROG/weread-cloud-new`）。云端把 `python` 换成 HTTP 调用即可（见 3.4）。

### 3.1 扫描回填（首次接入 / 库重建）

```bash
# 云端控制台
curl -s -X POST "$CLOUD/api/notes/backfill" -H "Content-Type: application/json" -d '{}'
# 期望：{"ok":true,"stat":{"books":82,"outline":82,"overview":82,"mindmap":76,"publish":82,"sub_modules":552}}
```

实测 82 本 / 552 个子模块约 11 秒，可重复跑。

### 3.2 核验（把失效的挑出来）

```bash
curl -s -X POST "$CLOUD/api/notes/verify" -H "Content-Type: application/json" -d '{}'
# 期望：{"ok":true,"checked":N,"stale_count":0,"stale":[...]}
```

有 `stale` 就说明「台账说有、磁盘上没有/被改过」——这时**不要**直接信台账，按第 4 节补偿。

### 3.3 查漏（生产前算账）

```bash
curl -s "$CLOUD/api/notes/<slug>" | jq '.note.plan'
# {"run":[], "skip":[{...4 项...}], "stale":[], "missing_modules":["top10","aiask","higher","verify","thennow"]}
```

- `run` 为空 = 全部命中台账，一键生产会秒退（`last_status=skipped`）
- `missing_modules` = 精读页还缺哪些模块

### 3.4 接口清单

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/notes` | 列表 + 汇总（可按 `?status=partial&limit=20` 过滤） |
| GET | `/api/notes/<slug>` | 单本详情：模块明细 + 现场核验 `checks` + 下一步 `plan` |
| POST | `/api/notes/backfill` | 扫描回填（幂等） |
| POST | `/api/notes/verify` | 全量核验，标 `stale` |

---

## 4. 补偿：重新产出这份笔记

> **补偿 = 把这份笔记重新产出一遍，并让台账重新可信。** 不是"改个状态让它看起来好了"。

### 4.1 先判定属于哪一类

| 症状 | 判定 | 动作 |
|---|---|---|
| `verify` 报 `stale`（文件没了/变小/md5 变） | 产物丢失或被外部改动 | 重跑对应步骤 → 重新发布 → 台账自然更新 |
| `run` 里有某步、且是 `failed` | 上次失败 | 重跑该步（先看失败原因，别盲目重试） |
| `missing_modules` 非空 | 精读页缺模块 | 补模块（4.3），不是重做整页 |
| 页面在、但内容是假的/模板占位/密度低/锚点对不上原文 | 质量问题 | 按标准重做该页，并在 A2A 记明原因 |
| 整本都没产出 | 新书 / 库丢失 | 全流程跑一遍 |

### 4.2 重跑（最常用）

```bash
# 只重跑失效的那一步（推荐，别整本 force）
python compose_book.py run --book "书名" --steps outline --force

# 精读页重做（会先备份原页为 mindmap.prev.html）
python compose_book.py run --book "书名" --steps mindmap --force
python compose_book.py run --book "书名" --steps publish

# 云端等价
curl -s -X POST "$CLOUD/api/compose/run" -H "Content-Type: application/json" \
     -d '{"book":"书名","steps":"mindmap,publish","force":true}'
```

**不带 `--force` 时**，`plan_steps()` 会自动跳过已核验通过的步骤——所以"整本重跑"通常只补缺的，安全。

### 4.3 补精读模块（不是重做整页）

模块内容的唯一真相源是站点仓库 `data/mindmap/<slug>.json` 的 `modules` 字段：

| 模块 | JSON 结构 |
|---|---|
| `aiask` / `coreask` | `{"pairs":[{"q":"..","a":".."}]}` |
| `higher` / `verify` / `thennow` | `{"paras":[".."]}` 或 `{"items":[".."]}` |

流程：写回 JSON → 重渲染页面 → 发布。**没有真实内容就整块不渲染**（`show_pending=false`），绝不写空答复、绝不写模板假数据。

### 4.4 三条铁律（每一条都因为违反被回退过）

1. **强制重做前先备份**：`force` 覆盖 `mindmap.html` 会冲掉别的 agent 注入的模块（2026-10-31 真实发生，把 7 行「真实核心追问」冲掉了，按 `a883816` 才还原）。现在 `force` 前会自动写 `mindmap.prev.html`。
2. **发布只发本次真正写入的文件**，绝不整目录扫描 diff——那会用旧快照覆盖 main。`skipped=exists` 的步骤不算"本次写入"。
3. **没有 LLM 通道就别假装生成**：`data/import/<slug>.json` → OpenAI 兼容端点 → `--from-outline`（结构化重算，页面自标「结构提要」）→ 明确失败。降级到什么程度，页面上必须看得出来。

### 4.5 补偿后的验收（缺一不可）

```bash
# 1) 台账层面
curl -s "$CLOUD/api/notes/<slug>" | jq '.note.plan'        # run 应为空、missing_modules 清楚
curl -s "$CLOUD/api/notes/<slug>" | jq '.note.checks'      # 全部 {"state":"ok"}
# 2) 线上层面（等 Pages 构建，别拿 404 当失败）
curl -s -o /dev/null -w "%{http_code}/%{size_download}\n" \
  "https://ae6623.github.io/we-read/reading-notes/books/<slug>/mindmap.html"
# 3) 结构层面：章块数、锚点数、details 开合、密度条不溢出
```

GitHub Pages 的 Actions 队列经常积压，新提交可能几分钟后才 200 —— **文件在 main 上就算发布成功**，用 `git show origin/main:...` 复核，不要反复重提。

---

## 5. 跨 agent 约定

- 台账是**各环境自己的索引**，不共享库文件；共享的是「同一套表结构 + 同一套状态语义 + 同一套流程」。
- 你补偿过的书，在 A2A 日文件里记一条：`slug / 哪一步 / 为什么 / 用的什么通道 / 验收结果`，别的 agent 才不会重复劳动。
- 别人正在读的书（registry 有 owner / active_session）**不要**去补偿它的笔记，先问。
- 站点 `reading-notes/index.html` 的归档索引由**会话最全的那台**维护，云端只追加当天笔记，别整页重写。

---

## 6. 实现索引（要复现就看这几处）

| 文件 | 作用 |
|---|---|
| `weread_store.py` | 建表、`save_module()` / `refresh_note()` / `list_notes()` / `load_note()` / `note_modules()` |
| `compose_book.py` | `record_step()`（生产时写）、`verify_artifact()`（指纹核验）、`plan_steps()`（查漏） |
| `web_app.py` | `/api/notes*` 四个接口、`_book_title_of()`（从页面 title 反推书名） |
| `config_store.py` | 配置台账 `app_config`（另一张表，与本文无强耦合，同样四组可改） |

库位置**必须**是 `weread-data/we_read.db`：`data/` 会随部署被本机空目录覆盖（踩过两次，数据归零）。

---

> 最后更新：2026-10-31 02:40（Asia/Shanghai）· cloud-agent2
