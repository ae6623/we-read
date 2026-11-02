# 产书规则 · 单一口径（所有读书实现者必读）

> 目的：不同的实现者（本机引擎、云端沙箱、任何 agent）产出的笔记页**结构、题面、
> 答案口径、发布方式完全一致**，出问题时有据可查。改规则先改这里 + 对应真源文件，
> 不许在生成器里内联私货。

## 一、一本书的产物模块（compose 步骤序）

| 步骤 | 产物 | 干什么 | 模板/规则真源 |
|---|---|---|---|
| `outline` | `reading-notes/books/<slug>/outline.html/.json/.md/.epub` | 微信读书 AI 大纲逐字导出，四层结构 | 官方数据，不改写 |
| `overview` | `…/overview.html` | 通读页：全书骨架 + 每章要点 + 热门划线 + **全书思考 3 问** | `reading_note_spec.py` + `overview_gen/` |
| `aiqa` | 注入 overview 的 quiz-card | 给思考 3 问写参考答案 | `gen_quiz.py` / `gen_aiqa_from_outline.py` |
| `mindmap` | `…/mindmap.html` | 精读页：章节树 + 要点 + 原句 + 8 个 AI 子模块 | `gen_mindmap.py` |
| `modules` | mindmap 内 `mmx-mod` 区块 | 补缺失 AI 模块（oneline/views/top10/aiask/coreask/higher/verify/thennow） | `gen_mindmap.py` |
| `publish` | GitHub 提交 | 只提交本次真正写入的文件 | compose `step_publish` |

## 二、全书思考 3 问 · 题库规则

- **题库位置**：真源在引擎仓 `reading_note_spec.REFLECT_BANK`（24 题）；
  本目录 `quiz-bank.json` 是同步快照，两者不一致时以 `reading_note_spec.py` 为准。
- **抽取规则**：按 `slug` 做随机种子稳定抽 3 题（`pick_reflect_questions(slug)`）。
  同一本书重渲染题面不变（台账 md5 才稳定）；不同书落到不同题组，全站不再千篇一律。
- **口径红线**：只出指向全书主旨 / 论证 / 迁移的题；**禁止**章节条目级、版面元信息级的
  问法（"大纲共列出多少条目""第一章最让你意外""合上本页能否讲清"这类，2026-11-01 废弃）。
- **区块标题**：`全书思考 3 问`（旧名「读完自测 3 问」已废弃）。

## 三、答案规则（aiqa）

三级降级，逐级标注来源，**不许空白也不许装亲读**：

1. **微信读书 Ai 问书**：官方按书生成的题 + 带书内引源的参考答案（最优）。
2. **LLM**（Gemini / OpenAI 兼容）：把章节要点 + 原句摘录喂给出题作答。
3. **离线自构**（云端常态）：基于 AI 大纲结构写「诚实答案」，**必须标注**
   「基于大纲、未亲读」；占位话术（待亲读后自答等）按规则剥离。

**笔记口径铁律**：给高认知不给流水账；**硬禁页数 / 页码 / 翻页次数 / 时长 / 进度百分比**
出现在任何笔记正文。

## 四、发布铁律（违反过、被回退过）

1. 只提交本次真正写入的文件，**绝不整目录扫 diff**（会用旧快照覆盖别人）。
2. 索引页只替换本书 `<!-- preread-card:<slug> -->` 段；卡片「精读」链接按
   `mindmap.html` 是否已产出给，不挂 404 链接。
3. **已有 mindmap.html 不覆盖**；确要重算先备份 `mindmap.prev.html`。
4. 文本统一 LF；`overview` 与书架索引以「会话最全」的一端为准，云端只动本书卡。
5. 屏蔽口径：`block_rule` 规则表（类目 / 公众号），被屏蔽书不产出、不上 C 端。

## 五、产物身份戳（produced-by）

每次 publish 给产物 HTML 顶部盖：
`<!-- produced-by: {"by","source","at","component","engine","built"} -->`
——谁触发的（cli / web / scheduler / queue）、哪个代码版本（`VERSION.json` 的
engine_commit）、什么时候。台账 `compose.json` 每书同记 `produced_by`，
`/api/notes/<slug>` 可查。出问题先看戳，再定性「代码没更新」还是「实现者差异」。

**修订台账（v1.4.0 起）**：每次 publish 成功向 SQLite 表 `note_revision`
追加一行（slug / book / produced_by / spec_version / files / at）。
同一本书可以反复重修，修过几次、每次谁产出，全部有据可查。
**「已产出」判定以修订台账 + 站点产物页为准，与「读没读完」（finished / progress）
完全解耦**——书读完不读完不影响笔记产出资格；选书策略只跳过「已产出笔记」的书。

## 六、版本与快照

- 云端部署源带 `VERSION.json`（`build_version.py` 生成）：engine_commit + site_commit +
  快照指纹。
- 站点快照 `vendor/we-read.zip` 由 `make_snapshot.py` 从 **we-read main 最新提交**打；
  快照过期（如本例：zip 早于 `--from-outline` 提交 1 小时）= 云端功能静默回退，
  部署前必须核对 `snapshot` 指纹晚于最新功能提交。

## 七、版本门槛（跑任务前强制比对）

- `note-spec/VERSION`（本目录）= **规则要求的最低版本**（x.y.z 语义化）。
  规则、题库、模板、发布口径有任何变更，随改动一起 bump，随代码进 main。
- 实现者（引擎 / 云端沙箱 / 任何跑产书任务的 agent）自带 `reading_note_spec.SPEC_VERSION`；
  `compose_book.run_book` 开跑前调 `assert_spec_ready()`：
  **自带版本 < 仓库要求 → 拒绝执行**，报错里写明 remediation
  （本机 `git pull origin main`；云端重跑 `make_snapshot.py` 重打快照再部署）。
- 快照里没有 `note-spec/VERSION`（旧快照）视为尚未立门槛，放行——新快照起强制。
- bump 时机速查：改题库 / 改模板 / 改答案口径 / 改发布规则 / 新增模块 → minor+1；
  改错别字、纯注释 → 可不 bump。部署代码但不改规则 → 不用 bump（VERSION.json 记录部署指纹）。

## 八、overview 模块系统 + 合并页默认入口（overview_gen）

> 单一口径：本机引擎、云端沙箱、任何 agent 给读前通读页增删「模块」时口径一致、有据可查。
> 真源实现在 `we-read-auto` 的 `overview_gen/`（扁平布局）；详细模块清单见该仓
> `overview_gen/README.md` 的「模块系统」一节，本处只记口径与强制项。

### 增加模块 = 必须同步写模块说明（强制）

1. 在 `build_overview.py` 的 `MODULES` 注册表新增渲染函数（`_m_xxx`）时，**必须同时**在
   `overview_gen/README.md` 的「模块清单」补该模块的说明（职责 / 渲染内容 / 适用与覆盖情况），
   **并同步更新本文件**（本节）。不允许只在代码里加模块、不写文档。
2. 改规则先改这里（单一口径）+ `overview_gen/README.md`（真源项目说明），**不许在生成器里内联私货**。
3. 新需求一律「新增模块」，绝不在老模块 / 老 `build()` 上做大手术（低耦合高内聚）。
4. 模块的启用 / 停用只通过 `books.py` 的 `MODULES_OVERRIDE` 配置（一本一行），不碰共享渲染；
   回退只需删对应 `MODULES_OVERRIDE` 条目。

### 模块清单

| 模块名 | 职责 | 启用方式 |
|---|---|---|
| `thesis` | 一句话主旨 | 默认 |
| `chapter_guide` | 章节导读（带配额截断，超出显示「（其余 N 条要点见本书 AI 大纲页）」） | 老通读页 `overview.html` 默认 |
| `merged_guide` | **AI 领读**（新增）：全书骨架 + 章节导读全文 + AI 大纲融合为一棵自包含树；原句提升为节点并保留要点下嵌套原句，无配额截断、无跳转指引 | 合并页 `combined.html` 全站启用；也可按书 `MODULES_OVERRIDE` 覆盖 |
| `ai` | AI 问书 + 快答实录 | 默认 |
| `views` | 核心观点初判 | 默认 |
| `action` | 迁移与行动 | 默认（合并页不渲染） |
| `quiz` | 全书思考 N 问（带答案） | 默认 |
| `memo` | 复习与记忆复利 | 默认（合并页不渲染） |

### 合并页 = 站点默认入口（2026-11-02 起）

- 每本书新增 `reading-notes/books/<slug>/combined.html`：通读（overview）与精读（mindmap）
  模块去重合并成一页，顺序为 思维导图 → 一句话主旨 → **AI 领读** → 精读模块 → 全书思考 3 问。
- **老页 `overview.html` / `mindmap.html` / `outline.html` 一律保留**：继续生成、继续发布，
  卡片与入口抽屉里仍留有直达链接；切换的只是「点书名进哪页」（`_entry_page()` / `entry_page()`）。
- 回退方式：删掉 `combined.html`（或让生成器不产出）即自动回退老通读页，**不会出死链**。

### 合并页架构（2026-11-02 重构）：壳页 + 数据 + 共享资源

- **渲染逻辑唯一真源**：`assets/css/reader.css`（样式/主题）+ `assets/js/reader.js`
  （装配/导航/改名/清废话/设置面板/滚动高亮）。**改 UI 只动这两个文件，339 本书零重生成。**
- 每本书 `combined.html` 只是 ~2KB 壳页；内容在 `combined-data.html`
  （`<!--META {...}-->` + 若干 `<section data-key="…">`），reader.js fetch 后装配。
- 只有「内容生成逻辑变更」（AI领读融合树、问答答案等）或「新书入库」才需要跑
  `overview_gen/combine_page.py` 重生成 data；模块排序/标题/文案调整全部在前端做。
- 数据由 fetch 加载，页面需通过 http/https 访问；`--standalone` 可产离线单文件。

### 加载态口径（2026-11-02）：标题直出 + 内容形状骨架

数据 100~800KB，移动端慢网下有几秒空窗。加载态的分工：

| 层 | 内容 | 由谁产出 |
|---|---|---|
| 直出 | 书名、三个 chip、11 个导航标签、Aa 按钮、**11 张骨架卡的模块标题** | 壳页 HTML（`SHELL_TPL`） |
| 占位 | 各模块自己的内容形状（导图=大图块、领读=分组条、问书=问句+缩进答句、金句=列表） | `reader.css` `.rd-skel` |
| 动效 | 占位块扫光带 + 顶部 3px 生长式进度条 `#rdBar` | `reader.css` |
| 收尾 | 内容淡入 `.rd-in`，进度条淡出移除 | `reader.js` |

铁律：**骨架卡里的标题是真实模块名，只有内容是假的**——读者第一眼就知道这本书有哪几块，
不会因为一片空白以为页面挂了。深色主题下占位块与页面背景的灰阶差至少 2 档（≈+15 亮度）。
`prefers-reduced-motion` 下停扫光/淡入，只留静态色块；fetch 失败显示 `.rd-fail` + 重新加载。
