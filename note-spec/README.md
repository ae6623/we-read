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

## 六、版本与快照

- 云端部署源带 `VERSION.json`（`build_version.py` 生成）：engine_commit + site_commit +
  快照指纹。
- 站点快照 `vendor/we-read.zip` 由 `make_snapshot.py` 从 **we-read main 最新提交**打；
  快照过期（如本例：zip 早于 `--from-outline` 提交 1 小时）= 云端功能静默回退，
  部署前必须核对 `snapshot` 指纹晚于最新功能提交。
