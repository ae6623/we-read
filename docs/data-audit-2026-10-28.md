# AI 笔记数据审计 · 二次提炼设计

> 2026-10-28 ｜ 审计方：本机 weread-auto ｜ 对照源：站点仓 `reading-notes/books`（82 本，HEAD `6d31360`）
> 关联文档：`docs/data-store.md`（云端 agent 写的表结构/入口说明）

## 0 结论摘要

1. **库没有全量入库，缺 4 本**，不是 5 本：`di-yi-xing-yuan-li` / `jin-rong-jia` / `tian-mu-hong-chen` / `xi-da-duo`。
   共 **351 章 / 2408 条要点 / 4445 句原句**。这 4 本通读页里 `ch-item` 与「章节导读」都在，注入器能正常跑，
   只是**从未被跑过**。缺口的要点数与原句数与 `data-store.md` 的差额（27590−25182=2408、52392−47947=4445）**逐位吻合**，
   说明除这 4 本外，其余 58 本是完整入库的。
2. **两个结构性缺陷**：「入库」被耦合在「渲染」上（`inject()` 返回 0 就不 `save_local`）；
   以及**两套 `weread_store.py` 写两个不同的 `we_read.db`**（站点仓 `data/we_read.db` vs 运行时 `data/we_read.db`），
   云端跑的 `gen_outline_full.py` 写的是前者，而 Web 应用读的是后者。
3. **`quiz` 缺 4 本**（60 个通读页有「读完自测」，56 个有 AI 补答）；**`ai_qa` 几乎全空**（站内仅 3 页 27 问）。
4. **精读笔记 22 篇 / 15 本没有表承接**——这是对方 schema 之外的真实遗漏。
5. **13 本的 `outline.html` 是散文式框架页**（无 `ul.point`），进不了 `book_outline`。
   这不是 bug：页面自述「未单独留存 AI 大纲原文」，属证据边界，不该伪造章节结构。

## 1 口径：谁是源、谁是库

| 角色 | 位置 | 状态 |
|---|---|---|
| **内容源** | `we-read/reading-notes/books/<slug>/{outline.html,overview.html,notes/}` | 唯一真源，82 本 |
| **结构化中间层** | `data/outline_full/<slug>.json`（`gen_outline_full.save_local` 写） | 62 本，可重算 |
| **库** | `data/we_read.db`，`weread_store.DB_PATH` | **六个可能的位置，见 §3.2** |

审计方法：不读云端库（无法直连），改为**从源侧全量解析重算**，再与 `data-store.md` 记录的入库量对账。
重算脚本：`audit_outline_db.py`（仓库根，幂等，只读或 `--write` 入库，不碰 overview、不发布）。

## 2 审计结果

### 2.1 `book_outline`

| 口径 | 书 | 章 | 要点 | 原句 |
|---|---|---|---|---|
| 源侧应有（62 本可结构化解析） | 62 | 3288 | 27590 | 52392 |
| 云端已入库（`data-store.md`） | 58 | 2918 | 25182 | 47947 |
| **缺口** | **4** | **370\*** | **2408** | **4445** |

\* 章数差额 370 与逐本加总 351 的 19 章差，来自「入库数用的是注入成功的 `ch-item` 块数」与「解析数用的是 `details.ch` 数」两种口径；
要点/原句两个口径一致，以 2408 / 4445 为准。

缺失明细：

| slug | 章 | 要点 | 原句 |
|---|---|---|---|
| `jin-rong-jia--jiao-fu--jin-rong-ban--mei-guo` | 200 | 1409 | 2708 |
| `di-yi-xing-yuan-li--pu-tong-ren-de-ren-sheng-ga` | 72 | 406 | 480 |
| `tian-mu-hong-chen--yao-yuan-de-jiu-shi-zhu--z` | 51 | 380 | 837 |
| `xi-da-duo--ming-jia-yi--shen-du-zhu-shi--ren` | 28 | 213 | 420 |

旁证：这 4 本同时也是「通读面板里只有 AI 大纲链接、没有全书视角卡」的 4 本，且是 `quiz` 缺答案的 4 本——
同一批书在多条链路上被跳过，指向同一个原因（这几本是后期补建目录，生成器没回头扫）。

### 2.2 `quiz`

- 有「读完自测 3 问」区块：**60 本**
- 有 `quiz-ans` AI 补答：**56 本**（= 168 行，与云端一致）
- **缺 4 本**：`di-yi-xing-yuan-li` / `jin-rong-jia` / `tian-mu-hong-chen` / `xi-da-duo` → 缺 12 条

好消息：**问答原文都在站内 HTML 里**，`quiz` 表可 100% 从站点回补，不需要重跑 AI。
结构：`<section class="card"><h2>读完自测 3 问</h2><ol><li>Q</li>…</ol><div class="quiz-ans"><div class="aiqa-item"><h3>Q截断</h3><p>A</p></div>`
注意 `aiqa-item` 的 `h3` 是**截断到约 40 字**的问题，回补要用「前缀匹配」而不是全等。

### 2.3 `ai_qa`

- 站内含 `<section class="aiqa">` 的笔记页：**3 页 / 27 问**（`tou-guo-di-li` `wen-hua-ku-lv` `yi-ri-wei-jing`，均 2026-10-26）
- 本机 `data/ai_qa/*.json`：只有 4 个文件，且都是自测 quiz 格式
- 云端表：0 行

结论：这是**唯一真正缺源**的一类，不能靠回补解决，只能重跑「AI 问书」（对方 task A4 尚未完成）。
可先做的：把已有 27 问回补进 `ai_qa`（带 `backfill=1`），别让已有数据继续躺在 HTML 里。

### 2.4 精读笔记

- **15 本 / 22 篇**，全部含 `aiqa-item` 样式与阅读度量块
- 对方 schema 里**没有表**承接 → 站内最"有人味"的一层内容在库里不存在

### 2.5 无法入库的 13 本

`alaska-qingyouji` `baikal-qingyouji` `camino-qingyouji` `da-zhuan-zhe` `elephant-qingyouji`
`er-yue-he-shuo-fan-fu` `king-return-dalrymple` `local-zhi-ye-gui-hua-niao-shu` `serbia-qingyouji`
`shi-shi` `unstable-life-qingyouji` `yi-ri-wei-jing` `zhi-hu-shen-tie`

共同特征：`outline.html` 里 `<section><h2>` + 散文 `<p>`，**零 `ul.point`**，页面自述「未单独留存 AI 大纲原文，
本页由全书视角笔记整理」。它们的小节标题是「先说明证据边界 / 已核实标题 / 全书主旨初判 / 思维导图 / 当年与今天 / 来源」——
**元框架，不是书的章节**。强行按章入库会污染 `book_outline` 的语义。

处置：**不入 `book_outline`**，改为在库里标 `kind='framework'`（见 §4.3），二次分析时按"框架页"单独处理。

## 3 三个结构性缺陷

### 3.1 入库被耦合在渲染上

`gen_outline_full.main()`：

```python
new_html, n = inject(html_text, chapters, a.budget)
if not n:
    print("通读页无章节导读区块，跳过")
    continue          # ← save_local 在下面，永远到不了
npts = save_local(slug, title, chapters)
```

「页面没有注入点」被当成「这本书没数据」。§2.1 的 4 本就是死在这条 `continue` 上（它们后来补了区块，但没人重跑）。
**入库与渲染必须解耦**：解析成功就入库，注入失败只影响页面、记 warn。

### 3.2 两个 `weread_store.py`，两个 `we_read.db`

| 模块 | 表 | DB |
|---|---|---|
| `we-read/weread_store.py`（对方） | `ai_qa` `quiz` **`book_outline`** | `we-read/data/we_read.db` |
| `weread-auto/weread_store.py`（我，运行时） | `ai_qa` `quiz`（**无 `book_outline`**） | `<运行时>/data/we_read.db` |

沙箱里站点仓在 `data/we-read`（`shared.repo_dir`），所以：

```
/data/we-read/data/we_read.db   ← gen_outline_full.py 写的（有 book_outline）
/data/we_read.db                ← web_app.py 读的（没有 book_outline）
```

**两个不同的文件。** 页面能显示是因为通读页渲染读的是 HTML 本身/JSON，不是因为库通。
一旦要做「全书检索 / 跨书对照 / 二次分析」，这个分裂必须先合掉。

处置（本机先做，云端报给对方）：运行时 `weread_store.py` 补上 `book_outline`（**字段、主键与对方逐字一致**），
并加 `/api/ingest/outline` 让本机/站点侧把解析结果推给运行时库。谁写谁读的边界写进 `data-store.md`。

### 3.3 笔记无表

`note` 表缺失。22 篇不多，但它是「AI 大纲（机器）」与「人读后的判断（人）」之间唯一的桥，
跨书对照最值钱的一层就是它。建议加 `note(slug, date, title, html, bytes, ...)`。

## 4 补数方案

按「能不能自动、风险多大」排序，全部可回滚。

### 4.1 补 4 本的 `book_outline` + 注入（零风险，纯补）

```bash
cd C:/Users/ROG/we-read
python gen_outline_full.py --slug <slug>          # 不发布，只落盘
# 4 本跑完后本地 git 提交（不用 --publish，避免 REST 令牌与环境问题）
```
预期：62 本 / 3288 章 / 27590 要点 / 52392 原句全部入库，通读页 62/62 都有「逐章折叠」。

### 4.2 回补 `quiz`（从站内 HTML，零 LLM）

新脚本 `backfill_quiz_from_site.py`：解析 `overview.html` 的「读完自测」→ `ol>li` 取题，
`quiz-ans .aiqa-item` 取答案（`h3` 前缀匹配 `li`）→ `save_quiz(book, items)`。
预期 +4 本 / +12 条 → 180 条。附带产出「题目 vs 答案错配」清单（前缀匹配失败即告警）。

### 4.3 回补 `ai_qa` 已有 27 问（`backfill=1`）

解析 3 个笔记页的 `<section class="aiqa">` → `save_aiqa(book, items, date, backfill=True)`。
先把「已有但没入库」的擦干净，剩下的真空缺（其余 79 本）留给重跑 AI 问书。

### 4.4 `note` 表 + 22 篇入库

新表 + 解析笔记页（标题、日期、正文 HTML、字节数、是否含 aiqa/度量块）。只加表不动别人字段。

### 4.5 13 本框架页标记

`book_outline` 不写，另建轻表 `book_outline_meta(slug, kind, note)`，`kind ∈ {ai_outline, framework, missing}`，
让「查不到大纲」和「这本书本来就没有 AI 大纲」在 SQL 层可区分——现在的 `NOT EXISTS` 把两类混成一类。

## 5 二次分析设计

### 5.1 为什么现在能做

数据结构刚好够：`chapter → sec → point → quote` 四层，`point` 是 AI 的主张，`quote` 是**原书句子**。
52392 句原句 = 一个天然的「论点—证据」对偶库。这是做提炼的地基：所有二次产出都必须能**指回某一章某个要点某句原话**，
否则就是又一层 AI 复述。

### 5.2 四类产出（按价值排序）

**① 章节思维导图（用户点名）**
每本书一张：中心 = 全书命题，一级 = 主干（5–7 个），二级 = 章，三级 = 该章 2–3 个关键概念。
不是把目录换个画法——章的标签要写**该章在全书里的功能**（铺垫 / 立论 / 反证 / 案例 / 收束），
这是 LLM 才能给的东西，纯解析给不了。

**② 论点—证据对账**
对每章：N 条要点里，有多少条挂着原句（有据）、多少条是裸断言（无据）。
输出「全书证据密度」+「最缺证据的 5 章」。这个指标可以直接反馈给阅读流程：AI 大纲在哪几章偷懒了。

**③ 跨章张力图谱**
同一概念在 A 章与 B 章的处理不一致（作者自我修正、前后矛盾、伏笔回收）→ `tensions[]`。
这是"读通一本书"和"读了一堆章节"的分界线。

**④ 跨书对照**
同主题书的命题并置（如「制度决定论」在《枪炮》《崩溃》《饥荒》里的不同边界）。
需要 embedding，放最后做，且只对已完读的书。

### 5.3 提示词契约（结构化 JSON，禁止自由发挥）

```json
{
  "slug": "wei-cheng",
  "title": "围城",
  "thesis": {"claim": "全书一条命题", "boundary": "这个判断在什么范围内成立", "ch_ref": [1, 8]},
  "spine": [{"id": "A", "label": "主干名（≤8字）", "chapters": [1,2,3], "why": "为什么这几章构成一条主干"}],
  "chapters": [{
    "no": 1, "title": "章标题",
    "gist": "一句话说清这章在论证什么（≤40字）",
    "role": "铺垫|立论|反证|案例|收束",
    "concepts": ["概念A", "概念B"],
    "anchor": "本章最有代表性的一句原话（必须逐字来自 quote 字段）"
  }],
  "tensions": [{"a": "第3章", "b": "第9章", "about": "同一概念", "note": "两处处理如何不同"}],
  "evidence": {"points": 0, "with_quote": 0, "density": 0.0}
}
```

硬约束（写进提示词，也写进校验器）：
- `anchor` 必须能在该书的 `quote` 集合里**字符串包含匹配**，否则丢弃该章（防编造引文）；
- `chapters` 必须覆盖全部章，缺章即失败重试；
- 禁词沿用站点规范：不出现平台中文名（一律写 `AI`）、不提页码/时长/翻页次数。

### 5.4 长篇怎么办

章数分布：≤20 章 27 本 / 21–60 章 20 本 / 61–150 章 10 本 / >150 章 5 本（最长 296 章）。

- ≤60 章：一次调用（每章给「标题 + 前 3 条要点 + 1 句原句」压缩上下文）
- \>60 章：两段式——先按 8–12 章一批做「段摘要」，再合并成全书主干；
  章级 `gist` 由批内结果拼接，主干由合并层给。网络小说类（296 章）必须走这条路，否则上下文爆。

### 5.5 渲染

**不用 mermaid CDN**（国内加载不稳、多一个运行时依赖）。方案：Python 直接生成**内联 SVG 横向树**
（圆角卡片 + 贝塞尔连线 + 按主轴分色），配 `<details>` 折叠列表做移动端/无障碍降级。
产出落 `books/<slug>/mindmap.html`，通读页顶部加一行入口。

可视化只在「主干 → 章」两层展开；概念层默认折叠，避免 296 章的书变成一张糊。

### 5.6 成本

62 本 × 1–3 次调用（Gemini flash），单本输入约 6–15k tokens。全量跑一遍约 100 次调用。
先跑 3 本样张（短/中/长各一）给用户过目，通过后再批量。

## 6 执行顺序与验收

| # | 动作 | 验收 |
|---|---|---|
| 1 | 补 4 本 `book_outline` + 注入 | 库 62 本 / 3288 章 / 27590 要点；通读页 62 本有逐章折叠、0 截断 |
| 2 | `backfill_quiz_from_site.py` | `quiz` 180 行 / 60 本，0 错配告警 |
| 3 | `backfill_aiqa_from_site.py` | `ai_qa` 27 行 / 3 本，`backfill=1` |
| 4 | `note` 表 + 22 篇 | `note` 22 行 / 15 本 |
| 5 | 运行时补 `book_outline` + `/api/ingest/outline` | 本机推 62 本到云端，云端 `counts()` 与本地一致 |
| 6 | `gen_mindmap.py` 样张三本 | 每本一张 SVG + JSON，`anchor` 校验 100% 命中原句 |
| 7 | 全量 62 本 | 站点 `mindmap.html` 62 页，0 死链 |
| 8 | A2A | 缺口、两库分裂、schema 增补写进通信记录 |

第 1–4 步不改任何站点文案、不动别人的生成器，只补数据与加表；第 5 步起才动运行时，需对方确认 schema 增量。

---

## 7 执行记录（2026-10-28 05:00–06:30）

### 7.1 已完成

| # | 动作 | 结果 |
|---|---|---|
| 1 | 补 4 本 `book_outline` + 注入 | 62 本 / 3288 章 / 27590 要点 / 52392 原句；通读页 62/62 有「逐章折叠」，0 处 `ch-pending` |
| 2 | 回补 `quiz` | 168 → **180** 行 / 60 本；4 本缺答案的用 `gen_quiz_answer.py` 按库内大纲补齐（12 条） |
| 3 | 回补 `ai_qa` | 9 行 / 3 本（站内仅 3 页有区块），`backfill=1` |
| 4 | `note` 表 + 22 篇 | `note` 22 行 / 15 本 |
| 5 | 全书导图 | **18 本**已上线（见 §7.3） |

库文件：`we-read/data/we_read.db`（26MB，已 gitignore）。

### 7.2 一个必须记下来的坑

`gen_aiqa_from_outline.py --mode gemini` 给黑塞《悉达多》生成的答案是**阅读方法论**——
上下文取错了，答的不是这本书。已回滚该页，改走 `gen_quiz_answer.py`（从 `book_outline` 取真实章节）。
**结论：任何给"这本书"生成内容的链路，上下文必须来自库里的该书数据，不能来自页面字符串拼接。**

### 7.3 导图进度与两种产出方式

已上线 18 本：围城、1984、金融家、遥远的救世主、爱鸡尾酒与生化危机、低欲望社会、媚色无双、
法治的细节、一个女人一生的二十四小时、长安的荔枝、日本泡沫后的三十年、一地鸡毛、
动物农场、活着、快乐的死、认知觉醒、局外人、文化苦旅。

三条产出路径，页面结构完全一致（同一 `render()`），差别只在 `data/mindmap/<slug>.json` 的来源：

| 路径 | 命令 | 适用 |
|---|---|---|
| Gemini 两段式 | `gen_mindmap.py --slug X --write` | 有配额时批量；长书自动按 80 章分批 |
| 人工提炼 | 写 JSON → `gen_mindmap.py --import-batch f.json --write` | 配额不可用时；质量最高 |
| 仅重渲染 | `gen_mindmap.py --slug X --render-only` | 改版式，不重算 |

**锚点不接受编造**：`--import-batch` 时 anchor 一律由脚本从该章首句原句取；
Gemini 路径的 anchor 要过「字符串包含」校验，不命中就丢弃并计入 `bad_anchor`。
十八本实测 bad_anchor = 0。

### 7.4 明确排除的三本

| slug | 章 | 原因 |
|---|---|---|
| `ba-bu-ya-xin-ji-nei-ya--sheng-zhe-chi-xia-shi-z` | 1 | 单章，做「全书主干」没有意义 |
| `fang-si-qi-de-chu-lian-le-yuan--jing-bian-ban-` | 2 | 同上 |
| `bai-ye-xing` | 13 | 13 个条目标题全是「1 · …」，AI 大纲只覆盖第一章，做成全书导图会误导 |

### 7.5 剩余 41 本

Gemini 免费配额耗尽（429，各模型共用同一项目配额），重置约在北京时间 15:00。
恢复后一条命令补齐：

```bash
cd C:/Users/ROG/we-read
python gen_mindmap.py --all --write --skip-existing
python tools_link_mindmap.py --write
git add -A reading-notes/books && git commit -m "feat(mindmap): 补齐其余书目" && git push origin fix-publish:main
```

长书（296/295/294/271 章四本网络小说 + 红楼梦 122 章）单本 3–4 次调用，全量约 100 次。
