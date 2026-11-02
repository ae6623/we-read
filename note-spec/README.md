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

### 阅读偏好（2026-11-02）：首页与书页共用一份 `rd-cfg`

`assets/js/home-theme.js`（首页）+ `assets/js/reader.js`（书页）读写同一个键：

```json
{"theme":"cream|light|green|dark", "fs":0.80, "pm":1, "cols":2}
```

- 首页样式真源 `assets/css/home-theme.css`：四主题变量 + 组件字号覆盖；
  书页是 `assets/css/reader.css`。两边变量名一致（`--paper/--card/--ink/--muted/--line/--green/--sage`）。
- `--fs` 控制 `html{font-size}`（整页 rem 一起缩放），`--pm` 控制卡片/分组间距。
- **默认值按页面性质分开**：首页米白（`.80`，紧凑 `pm=1`）、书页夜间（`.94`）。
- 初始化 `apply(false)` 只应用不落盘 —— 用户没主动选过，就不能被「默认」写成「偏好」，
  否则逛一次书页，首页会永久变黑。
- 首页多一个字段：`cols`（1 = 一排一 / 2 = 一排二，**默认 2**，不再按屏宽自动降级）；
  卡片收藏单独存 `rd-fav`（slug 数组），不进 `rd-cfg`。

### 书架信息流（2026-11-02）：瀑布流 + 15 张/页 + 默认两列 + 封面

- **默认一排二**（`html[data-cols="2"]`，按钮循环 二→三→一），卡片高度不一 → `assets/js/home-feed.js`
  按「当前最短列」绝对定位摆放；只写 `style` 不改结构，搜索/筛选那套 `card.hidden` 照旧有效。
- **首卡不再横幅铺满**：删掉 `data-span="full"` 首卡特判（原第一张大卡占满整行），所有卡统一按列数摆放；
  `isSpan()` 已移除，`home-feed.js` 里 `span` 恒为 `false`。
- **封面（一排一 / 一排二显示，一排三隐藏）**：`home-card.js` 的 `addCovers()` 给每张 `.archive-card`
  加 `.card-cover` —— 占位用 slug 哈希色相 + 书名去标点前两字做大字题字；同时试加载
  `assets/covers/<slug>.jpg`，加载失败（404）自动 `remove`、露出占位层。**库里目前没有真封面图**，
  日后把图丢进 `assets/covers/<slug>.jpg` 即自动生效，无需改代码。
  - 一排三：为防拥挤，**隐藏 `.card-cover` 与 `.card-author`**，只留书名 / 日期 / 章节数精简信息。
  - 一排二：`flex-direction:column`，封面置顶（5:3 渐变块）。
  - 一排一：`flex-direction:row`，封面置左（92px 竖版）。
- **首屏打散**：只把第一页 15 张打乱（`scatter()`，mulberry32 + 内存种子），第 16 张往后仍是时间序。
  种子在内存里 —— 同一次访问里重排多少次（切列数、改字号、resize）结果都不变，卡片不会乱跳。
- **「即将上线」「归档」两格不做瀑布**（`isFixedGrid()`）：前者只有标题 + 一句说明，
  跨列全是空白；后者卡里嵌「阅读入口」折叠块，窄列会把入口压成竖排字。两者固定两列。
- **一页 15 张**：未加载的卡只加 `data-pg="off"`（CSS 隐藏），不销毁 DOM；
  下滑到页脚前 240px 自动加载下一页，`--` 页脚是状态条（有 IntersectionObserver 时不给按钮，
  因为按钮出现的瞬间就开始加载，永远点不到）。
- **混排网格不参与**：系列页的网格里混着 `.series-preview` 导览块，绝对定位会把它们压叠，
  这类网格交回 CSS 网格、也不分页（`pure = 卡片数 === 子元素数`）。
- 「这个网格有哪些卡」每次现算，不快照 —— 上游 `homepage-reading.js` 会按时间重排、
  把书在网格之间搬家（`sortCardsNewest`）。
- **卡片三段式**：日期在右上角，书名单独一行，底部 `作者 …… 34 章 / 790 条 ⋯`。
  「章节数」原来是书名下面独占一行、靠左，白吃一行高度；`home-card.js` 的 `moveMeta()`
  把它搬进 `.card-foot` 右侧（`.card-meta`），只搬 `/^\d+ 章(\s*\/\s*\d+ 条)?$/` 这种纯元信息，
  描述型段落（归档卡、系列卡）留在原位，别把正文塞进底栏。
- **字号档位**：`FS = [.72 .74 .76 .78 .80 .83 .86 .90 .94 1.00 1.08]`，首页默认 **.76**（12.16px 基准）。
  默认值变过就升 `CFG_VER`，`boot()` 里把「存着旧默认（字号 .80 / 列数 2）」的配置迁到新默认，自己调过的不动。
- **首卡横幅**：一排二/三时第一张跨整行（`data-span="full"`，只在列宽 < 300px 且首卡带章节数时开）。
  纯文字卡的高度只随书名行数变（1 行 / 2 行，差 18px），两列很容易排成「表格」；
  开头压一张通栏卡，整面墙才有起点。只在**列宽 < 300px 且首卡带章节数**时生效 ——
  桌面（列宽 500）会变成一条空心横条，「即将上线」那种只有标题 + 一句话的卡跨列更是大片空白。
- **续页判定只有一个入口 `check()`**：IntersectionObserver 只报「进出视口」，
  快速滑到底时页脚被一口气滑过去就再也不回调 —— 以前 320ms 节流把那次回调丢掉，
  就永久停在「已显示 30 / 276」。现在被节流时挂 330ms 定时器补一次，另加 scroll 兜底，
  且「页脚已经滚到视口上方」也算到达。

### 埋点口径（GoatCounter events）

页脚「次访问 / 位访客」本来就走 `ae6623.goatcounter.com`，同一账号支持自定义事件
（`goatcounter.count({path, title, event:true})`）：不新增依赖、不进 PV，后台 Events 单列，
也能用 `https://ae6623.goatcounter.com/counter/<path>.json` 读回。

路径规范：`/ev/<类别>/<维度…>`

| 类别 | path | 触发 |
|---|---|---|
| 首屏 | `/ev/load/<pane>/p1/init` | 页面就绪，每网格一次 |
| 加载下一页 | `/ev/load/<pane>/p<n>/<auto\|click>` | 触发加载，n 从 2 起 |
| 曝光 | `/ev/expose/<pane>/p<n>/<A\|B\|C>` | 该页第一张卡进入视口，同页同位只报一次 |
| 打开 | `/ev/open/<slug>` | 点书名 |
| 收藏 | `/ev/fav/<on\|off>/<slug>` | 卡片菜单 |
| 分享 | `/ev/share/<slug>` | 卡片菜单 |

**A/B/C 位按页序切，不按像素**：

- **A 位**：第 1 页（首屏 15 张）
- **B 位**：第 2–3 页
- **C 位**：第 4 页及以后

站内没有广告位，位次只用来回答「读者到底滑到第几屏」。按页切比按像素稳——
字号可调（`--fs` .72~1.08），像素口径会随用户设置漂。

`pane` 取所在面板 id：`whole` / `soon` / `series` / `archive`；同面板多个网格加序号后缀（`whole-1`）。

限流：单次访问最多 60 条，同 path 只发一次；`count.js` 8 秒内没加载出来就丢弃队列
（离线、被拦截都不影响页面）。

### 详情页交互（2026-11-02）：Gemini pro 标签 + 结构导图弹层 + 上一篇/下一篇

- **「AI领读」→「Gemini pro」**：`reader.js` 的 `renderChips()` 第二枚 chip 固定文案由 `AI领读`
  改为 `Gemini pro`（第一枚仍是品类 `cat1`，第三枚 `AI 生产` 不变）。339 本 `combined.html` 里
  旧 `<span class="chip">AI领读</span>` 已全量替换为 `Gemini pro`。
- **结构导图全屏弹层**：点导航里的「结构导图」入口或点导图 svg 本身 → 克隆 `#mod-svg svg` 进
  `#rdSvgModal`（遮罩 + 舞台 + 右上角关闭钮 `✕`）。关闭方式三种：点关闭钮 / 点遮罩 / `Esc`。
  舞台 `overflow:auto` + svg `min-width:600px`，手机端可横向平移看大图。
- **上一篇 / 下一篇（SPA，不整页跳转）**：顺序走 `assets/data/book-order.json`（首页卡片序，最新在前）。
  上一篇 = 更新一篇（列表里后一个），下一篇 = 更早一篇（列表里前一个）。点按 `fetch` 目标书的
  `combined-data.html` 原地重渲染 + `history.pushState` 换 URL，前进/后退可用；渲染失败整页兜底跳转。
  翻页条 `#rdPn` 在 `#rdBody` 之后，左下「上一篇」、右下「下一篇」，书名带《》包裹。
