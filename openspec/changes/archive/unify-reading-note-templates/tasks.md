> 执行规则：每完成一项立刻勾选 `[x]` 并单独提交（commit message 带 `tasks: <编号>`）。
> 任何一项做不到就写 `[!]` 并附原因，**不要留空白**——空白等于漏掉。

## 1. 单一真源模块（A）

- [x] 1.1 新增 `reading_note_spec.py`（仓库根）：`REFLECT_TITLE = "全书思考 3 问"`
- [x] 1.2 同文件 `REFLECT_QUESTIONS`：3 条高维通用问（真问题 / 核心主张 / 个人迁移），指向全书主旨与论证结构，**不含**「大纲共列出多少章节条目」「第一章最让你意外」「合上本页」这类章节条目级题面
- [x] 1.3 同文件 `REFLECT_NOTE`：说明这是读后自省题、不依赖 AI 代答
- [x] 1.4 同文件 `is_placeholder_title(t)`：全串匹配判定空串 / 纯序号（`一`、`第三章`、`第一部`、`12`）/ 渲染 fallback（`本节要点`）
- [x] 1.5 同文件 `chapter_title(c, full)`：优先级 章名 → 首小节名 → 首要点 → 锚点原句 → `第N章`；派生结果截断 40 字；派生链中跳过占位名
- [x] 1.6 模块只依赖标准库 `re`，无第三方依赖、无包内相对 import

## 2. 生产流程接入（B）——本次核心，杜绝再次打补丁

- [x] 2.1 `gen_mindmap.py`：`_chapter_html` 的 `mmx-name` 由 `E(c["title"])` 改为 `E(chapter_title(c, full))`
- [x] 2.2 `gen_mindmap.py`：顶部 `import reading_note_spec`（或 `from reading_note_spec import chapter_title`）
- [x] 2.3 `overview_gen/build_overview.py:321`：回退路径的 `<h2>读完自测 3 问</h2>` 改为引用 `REFLECT_TITLE`
- [x] 2.4 `overview_gen/build_overview.py:398`：`_quiz_block` 内的同标题改为引用 `REFLECT_TITLE`
- [x] 2.5 `overview_gen/build_overview.py`：`_quiz_answers_html` docstring 中的旧栏目名同步更新（不改逻辑）
- [x] 2.6 `overview_gen/auto.py:250-253`：默认 `quiz` 题面改为由 `REFLECT_QUESTIONS` 渲染，不再硬编码
- [x] 2.7 全仓 grep 确认站点仓源码内 `读完自测` 归零（文档/注释一并清，保留必要的"由旧名改来"说明除外）

## 3. 源码验证（C）

- [x] 3.1 `python -c "import reading_note_spec"` 通过（在仓库根执行）
- [x] 3.2 `py_compile` 三个改动文件通过
- [x] 3.3 单测 `chapter_title`：纯序号章 + 首小节名 → 返回小节名；带真名章 → 原样返回；空名无小节 → 返回 `第N章`
- [x] 3.4 单测 `is_placeholder_title`：`一`/`第三章`/`第一部`/`本节要点`/空 → True；`一 老大哥`/`第一节 童年的记忆`/`白银时代` → False
- [x] 3.5 用真实 `data/mindmap/*.json` 跑一遍 `chapter_title`，人工抽查派生结果可读、非乱码
- [x] 3.6 真实调用 `overview_gen.auto` 的默认题面构造，断言输出含高维 3 问、不含旧默认题

## 4. 存量回填（D）

- [x] 4.1 全库扫描 `reading-notes/books/*/mindmap.html`，按 `is_placeholder_title` 统计命中本书数与章数（严格判定，不用宽松正则）
- [x] 4.2 回填实现改为「锚点定位 + 原文等长位置替换」，**不做块切割再拼接**
- [x] 4.3 三道校验落地：`<details>` 开闭计数相等、`mmx-cn` 数不变、新文本长度不短于原文
- [x] 4.4 dry-run 输出每本将改的「旧 → 新」清单，人工确认派生结果正确
- [x] 4.5 正式上传：逐本带 sha 直传，单本失败只跳过并记录，不中断整批
- [x] 4.6 上传后复查：`<details>` 开闭平衡、`mmx-cn` 数不变、无占位章名残留
- [x] 4.7 若上传后结构异常，立即回滚到该文件上一个完好 commit（备好 `git log -- <path>` 取基线的方法）

## 5. 新书生产（E）

- [x] 5.1 扫描书架，列出「未产出四件套」的书
- [x] 5.2 **剔除公众号**（`type`/分类含公众号、或来源为公众号的条目一律不产）
- [x] 5.3 分批产出（AI 大纲 / 通读 / 精读 / AI 问答），每批结束提交 git
- [x] 5.4 抽验新产出：精读页章节名无纯序号、通读页为「全书思考 3 问」且题面为高维 3 问
- [x] 5.5 汇总本批书目、成功/失败数与 commit 号 —— 见 archive-note.md「实际数字」「关键 commit」

## 6. 归档

- [x] 6.1 `openspec validate --all` 通过（沙箱无 CLI 时，改为人工核对 front-matter 与 SHALL/WHEN/THEN 结构）
- [x] 6.2 变更完成后归档到 `openspec/specs/reading-note-templates/spec.md`，change 目录移入 `archive/`
