# Archive Note — unify-reading-note-templates

> 本变更已全部落地并核验。核心目标不是"再修一次页面"，而是**把修复写进生成流程**：此后任何程序重跑都不会退回旧模板。

## 做了什么

### 1. 单一真源（新增 `reading_note_spec.py`，两仓各一份）

- `REFLECT_TITLE = "全书思考 3 问"`、`REFLECT_QUESTIONS`（高维三问）、`REFLECT_NOTE`、`reflect_questions_html()`
- `is_placeholder_title(t)`：全串匹配判定空串 / 纯序号（`一`、`第三章`、`第一部`、`12`）/ 渲染 fallback（`本节要点`）
- `chapter_title(c, full)`：优先级 **章名 → 首小节名 → 首要点 → 锚点原句 → `第N章`**，派生结果截断 40 字
- 只依赖标准库 `re`；**不做 try/except 静默降级**——导入失败就报错，否则等于又存一份内联模板

### 2. 生产流程接入（两仓）

| 文件 | 改动 |
|------|------|
| `gen_mindmap.py`（站点仓） | `_chapter_html` 的 `mmx-name` 由 `E(c["title"])` 改为 `E(chapter_title(c, full))` |
| `overview_gen/build_overview.py` | 反思题区块标题改引 `REFLECT_TITLE`（站点仓 2 处、引擎仓 1 处） |
| `overview_gen/auto.py` | 默认题面改由 `REFLECT_QUESTIONS` 渲染，替换「大纲共列出多少章节条目 / 第一章最让你意外 / 合上本页」那套 |
| `overview_gen/quality_gate.py`（引擎仓） | `BORROWED_SECTIONS` 旧栏目名「读完自测」→「全书思考」，否则改名后质量门漏检 |
| `weread_daily.py`（引擎仓） | 3 处旧栏目名文案清理 |
| `weread_api.py`（引擎仓） | 新增 `shelf()`（`/shelf/sync`）与 `is_mp_book()` |

**关键发现**：改动前线上生产代码（引擎仓 `overview_gen/auto.py:250-253`、`build_overview.py:269`）仍是旧模板——上一轮只改了 `we-read-auto` 的 artifact 副本，云端读的是 git 仓，等于只擦地板没关水龙头。本次两仓均已提交。

### 3. 存量回填（mindmap 章名）

- 全库扫描 150 本 `mindmap.html`，严格判定命中 **4 本 / 196 章**：`35-sui-hou--wo-wu-lu-ke-tui-`(81)、`bai-ye-xing`(13)、`bai-yin-shi-dai`(22)、`zhui-yi-shi-shui-nian-hua--quan-ji-`(80)
- 实现改为**锚点定位 + 原文等长位置替换**（不做块切割再拼接）
- 三道守恒校验：`<details>` 开闭计数相等、`mmx-cn` 数量不变、新文本不短于原文
- 4 本全部通过并上传

> **事故记录（已修复）**：初版回填脚本用「按 `<details>` 配对切块 → 逐块 append」，漏掉块间隙文本，`zhui-yi` 单本丢 6167 字符、标签失衡（428/429）。已 `revert` 至 `1dea65e4a5` 前的完好版本（新 commit `1dea65e4a5`），换实现后重做。这条写进 design D5，作为后续回填类脚本的强制校验项。

### 4. 书架新书生产

- 书架实际 **371 本**（`/shelf/sync`）；`/user/notebooks` 只有 36 本「有笔记的书」，不足以覆盖
- 剔除：**公众号 9 本**（`MP_WXS_` 前缀 / `mpbook` / `author=公众号`）、归档 106 本、垃圾条目 5 本（`tmp_`、`PDF文稿`、无中文的英文期刊）
- 新增 `shelf_books()` + `--shelf` + `--limit`，并把「线上已有」纳入判定（避免本地镜像落后导致重复跑）
- `gen_one` 加最小可产出保护：有效章节 < 2 直接跳过，不产空壳

## 验证情况

| 项 | 结果 |
|----|------|
| `reading_note_spec` 单测（占位判定 11 例 / 派生 7 例） | 通过 |
| 三生成器 `py_compile` | 通过 |
| 模拟仓 import 链（`overview_gen.build_overview` / `.auto` / `.quality_gate`） | 通过 |
| `build()` 端到端渲染 | 输出 `<h2>全书思考 3 问</h2>`，无「读完自测」 |
| `quality_gate` 栏目命中 | 含新名页面缺失栏目 = 0 |
| 回填守恒校验（4 本） | `<details>` 平衡、`mmx-cn` 数不变、长度只增 |
| 全库 overview 核验（335 本） | 「读完自测」= **0** |
| 全库 mindmap 核验（337 本） | `<details>` 失衡 = **0** |

## 实际数字

- 线上书籍目录：156 → **343**（新增约 187 本）
- 书房产出：231 本待产 → 除 **2 本因有效章节不足跳过**（`CB_EHw46...` 导入 PDF、`3300199304` 单章轻游记）外全部产出并发布
- 补漏洞：4 本历史旧版 overview（1 本 217 字节空壳 + 3 本无反思题段）已就地修补

## 关键 commit

| 仓 | commit | 内容 |
|----|--------|------|
| we-read-auto | `91d5413c73` | 模板收敛（4 文件） |
| we-read-auto | `779e4c9688` | `shelf()` / `is_mp_book()` / 文案 |
| we-read | `01748345ab` | `gen_mindmap` 派生 + openspec change |
| we-read | `99bda5b1f9` `d27407d608` `4a8cb01c78` `5491e652d6` | mindmap 章名回填（4 本） |
| we-read | `c70a1ddf7b` `bb8762556f` `1e39d9b456` | 首批新书发布 |
| we-read | `26857aa55b` `0a386f4ef3` `2b2a4750fa` | 新书批 1–3 |
| we-read | `b31491814b` `985227cf67` `23cc61372b` | 新书批 4–6 |
| we-read | `cdc7eb7185` `ad9d324a28` `9a33341c7f` `8628d05833` | 4 本 overview 补反思题 |

## 已知边界（非缺陷）

- **mindmap 显示「第N章」**：部分书（如《半生缘》《大明王朝1566》）的章节数据本身就是 `一/二/三`，且 `/book/chapterinfo` 只有 `level=1`、**没有子节点**，无法派生真实标题。此时「第N章」是诚实的兜底，好于裸序号，且不虚构标题。
- **quiz 缺失**：无热门划线的书（如《凯恩斯、拉斯基、哈耶克》《埃隆·马斯克传》）不产 quiz 页——按「无真实来源不渲染」原则诚实丢弃。
- **英文期刊/网站条目**（`downmagaz.net`、`Bloomberg Businessweek`）在本轮早期批次被产出过 4 个空壳页，后续已加 `is_junk_title` 过滤不再产；已产出的 4 个页面未删除（属书架真实条目，待人工决定是否清理）。
