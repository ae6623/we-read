## ADDED Requirements

### Requirement: 笔记页模板文本 MUST 有唯一真源

反思题区块标题、反思题题面、精读页章节名展示文本 MUST 由单一模块集中提供，任何生成器 MUST NOT 内联硬编码这些文本。

#### Scenario: 改题面只改一处
- **WHEN** 需要调整反思题题面
- **THEN** 只需修改 `reading_note_spec.REFLECT_QUESTIONS`
- **AND** `gen_mindmap.py`、`overview_gen/auto.py`、`overview_gen/build_overview.py` 的后续产物自动跟随
- **AND** 不需要修改任何一个生成器文件

#### Scenario: 模块不可用即失败，不静默降级
- **WHEN** `reading_note_spec` 无法导入
- **THEN** 生成器 MUST 以异常终止
- **AND** MUST NOT 退回到文件内联的默认模板

### Requirement: 精读页章节 MUST 展示可读标题

精读页每一章 MUST 展示非占位的可读标题；章名为空或仅为序号时 MUST 从该章首个子节点派生。

#### Scenario: 章名为纯序号
- **WHEN** 章节标题为 `一`、`第三章`、`第一部` 等纯序号
- **AND** 该章首个小节标题为「作者对艺术家的印象和舅舅的艺术家生涯」
- **THEN** `mmx-name` 展示「作者对艺术家的印象和舅舅的艺术家生涯」
- **AND** 不再展示裸序号 `一`

#### Scenario: 章名本身可读
- **WHEN** 章节标题为 `一 老大哥` 或 `第一节 童年的记忆` 或 `白银时代`
- **THEN** `mmx-name` 原样展示该标题
- **AND** 不被判定为占位、不发生替换

#### Scenario: 派生逐级下降
- **WHEN** 章名为占位，且首个小节标题也为空或为渲染 fallback「本节要点」
- **THEN** 依次尝试首个要点文本、锚点原句
- **AND** 全部缺失时展示 `第N章`（N 为章号），MUST NOT 展示空串

#### Scenario: 派生结果长度受限
- **WHEN** 派生出的标题超过 40 字
- **THEN** 截断为 40 字
- **AND** 折叠行布局不被撑破

### Requirement: 反思题 MUST 为全书视角的高维问

反思题题面 MUST 指向全书主旨、论证结构与个人迁移，MUST NOT 使用章节条目级或版面元信息级的问题。

#### Scenario: 默认题面
- **WHEN** 某本书没有专属出题、走默认题面
- **THEN** 题面为三问：全书真正要解决的「真问题」、一句话核心主张与最强/最弱证据、值得带走的三个观念
- **AND** 不出现「本书 AI 大纲共列出多少章节条目」「第一章最让你意外的要点」「合上本页，你能用自己的话讲清本书试图解决的问题吗」

#### Scenario: 区块标题统一
- **WHEN** 渲染任意通读页的反思题区块
- **THEN** 区块标题为「全书思考 3 问」
- **AND** 不出现「读完自测」

### Requirement: 存量回填 MUST 结构守恒且幂等

对已发布页面的章名回填 MUST 保证 HTML 结构不变，且重复执行结果一致。

#### Scenario: 结构守恒
- **WHEN** 回填某本 `mindmap.html`
- **THEN** `<details>` 开标签数与 `</details>` 闭标签数 MUST 相等（上传前后都成立）
- **AND** `<details class="mmx-cn">` 数量 MUST 不变
- **AND** 新文本长度 MUST NOT 短于原文本长度

#### Scenario: 校验不过就拒绝
- **WHEN** 任一校验项不通过
- **THEN** MUST 拒绝上传该文件
- **AND** 只记录跳过原因，继续处理其余书目

#### Scenario: 幂等
- **WHEN** 对同一文件连续回填两次
- **THEN** 第二次 MUST 不产生任何改动
- **AND** 已有真实章名 MUST 保持原样

### Requirement: 新书生产 MUST 剔除公众号

扫描书架补充产出时，公众号类内容 MUST NOT 进入四件套生产队列。

#### Scenario: 公众号被剔除
- **WHEN** 书架中存在公众号文章类条目
- **THEN** 该条目不出现在待产清单
- **AND** 不为其生成 AI 大纲 / 通读 / 精读 / AI 问答 任一产物

#### Scenario: 正常书籍照常产出
- **WHEN** 书架中存在未产出四件套的普通书籍
- **THEN** 该书籍进入待产清单
- **AND** 产出后四件套齐全
