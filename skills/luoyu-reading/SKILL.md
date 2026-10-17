---
name: luoyu-reading
description: Multi-platform reading workflow for source-labeled whole-book previews, daily comprehension notes, and final HTML/EPUB archives. Use when reading a user's book through WeRead or another authorized reading platform, recording a session, creating or updating a book overview, or coordinating shared reading archives across agents.
---

# 落雨读书

> **所有 Agent 先读这一条**：本 Skill 只约束**协作目标与协议**——产出什么（预读框架/日期笔记/完读汇编）、按什么结构归档、来源如何标注、如何避免互相干扰、发布授权与时间错峰。它**不约束实现方式**：代码自动化、Agent 直接操作浏览器、人工整理都是被认可的手段，各 Agent 用自己擅长的方式达成目标，**互不假设对方的技术栈，互不干扰**。涉及具体平台的操作边界见 `references/platforms/<platform>.md`；代码类 Agent 的自动化实现细节集中在 `references/automation-code-agent.md`，**仅对该类 Agent 自身有约束力**。

为用户把多本书读得更有效：开读即建立有来源边界的全书视角初版，再把每天真实读到的内容连回框架，完读后才做校订后的整书汇编。`references/agent-roster.json` 是类型、时段、在读书目与完读状态的唯一登记源；共享归档与 Git 规则见 `references/coordination.md`，跨 Agent 开始/结束记录见 `references/agent-communication.md`，用户最新决定见 `references/decisions.md`。使用某个平台前阅读对应的 `references/platforms/<platform>.md`（当前先有微信读书指南）。

## Agent 类型与排班

先读 `references/agent-roster.json` 确认身份、实现类型、预留时段、当前书目和完读状态；该 JSON 是单一事实来源，避免在多个文档复制易过期的排班表。阅读计划的代码 Agent 只受 `references/automation-code-agent.md` 约束；浏览器/人工阅读 Agent 不需照搬其代码实现规则。新 Agent 加入时，在 roster 中登记类型和时段，并通过 `references/decisions.md` 记录用户决定；每次任务开始和结束都更新 `references/agent-communication.md`。时段冲突先协调，不同时间窗互不等待。

## 工作流程

1. **识别平台、书目与现有工作。** 先确认用户实际指的书、作者和阅读平台；查看归档索引、预读框架、日期笔记及已完成汇编。查看共享交接板并登记认领文件；遵守并行修改规则，避免重写别的 Agent 的文件。
2. **新书开读即产出全书视角初版（overview.html）。** 用户已明确决定：不要只给一张“预读地图”——开读时就应给出一份完整的全书视角。收集可验证的官方书目简介、目录、作者说明、用户提供的材料与可靠公开划线，结合模型自身对该作品的知识，产出全书主旨、结构、关键观点与主题关系；同时按四层来源标签（亲读 / 官方简介目录 / 用户材料 / 公开评论划线 / 综合推断）分清信息出处，并单列“阅读时要验证的问题”。它不是最终总结：未经亲读确认的部分保持推断标记，完读后校订升级为 `final.html`。没有可靠依据时，不装作掌握全书。
3. **每日按真实阅读写一篇日期笔记。** 记录实际范围、关键场景或观点、作者展开方式、与整书框架的联系、理解变化、可迁移启发和问题。只编辑当天的日期笔记；同日多段阅读合并在一篇中。用户希望灵活阅读时，可让阅读时长、停留与思考节奏有自然变化，以理解内容为目的；不能把未读内容写成已读，也不能把平台未确认的打卡说成已成功。
4. **只在理解有变化时修正全书视角初版。** 不为每次短读重做整书汇编。将新增理解放进当天笔记；确有重要修正时，在 `overview.html` 中注明依据和更新时间。
5. **完读并确认后生成最终整书汇编。** 确认整本已读后，把 `overview.html` 初版和所有日期笔记整合校订为更有解释力的全书视角：主旨、叙事/论证结构、关键观点间关系、重要转折、核心洞见、局限与可迁移启发。明确实际覆盖范围和外部来源；制作最终 HTML（`final.html`）与 EPUB（`final.epub`）。初版视角不能冒充最终整书总结。
6. **交付并维护。** 用清晰简洁的 HTML（手机、桌面均可读）保存笔记；给用户可访问文件或站点链接。归档默认私有，不公开发布或推 GitHub，除非用户对具体内容明确授权。Git 仓库更新遵循 `references/coordination.md`；完成或受阻时更新交接板，发布后实际检查页面、资源和 Pages 构建。

## 自动化与发布授权（2026-10-17 用户批准）

- weread-auto 每日自动阅读产出的新日期笔记、新书 `overview.html` / `final.html` / `final.epub` 及索引更新，**授权直接发布并自动合并 `main`**，无需每次单独征求授权。
- 该持续授权仅覆盖 weread-auto 自动产出的内容；其他来源的文件仍按 `coordination.md` 逐次授权。
- 发布后仍须实际检查线上页面、链接与 Pages 构建，未在线验证前不得声称"已发布"。
- 完整决定记录见 `references/decisions.md`（各 Agent 沟通记录，先行阅读）。

## 笔记质量

- 解释“这本书在做什么，以及各部分如何支撑核心意思”，不要只列事件或摘抄。
- 区分四层：亲读事实、官方/用户来源、公开评论或划线、自己的综合推断；在需要时给每层打清晰标签。
- 仅使用实际遇到的内容作为本次阅读证据；不补造章节、页码、论据或体验。
- 对整书视角提供必要的关键概念、核心张力、主题关系、结构图、读者可用的反思问题；简练但要足够帮助理解。
- 引用书籍原文保持必要且简短；不要复制书籍全文或大段受版权保护文本。
- 除非用户明确要求，不在阅读平台内部创建/发布想法笔记；默认只在私下归档和聊天里交付。

## 平台扩展

平台操作是可替换的适配层：主流程保持不变；每个平台单独说明登录状态、可读页面/听书、进度与标记、付费墙和安全边界。新增平台时从 `references/platform-adapter-template.md` 建立独立适配文件，并把实测与待验证事项分开。不要假定不同 App/网站有相同控件或允许同种自动化。读取对应平台参考文件后，再使用该运行环境中实际可用且获授权的方式。遇到权限、登录、付费或访问阻碍，说明事实并暂停受限动作，不猜密码、不付费、不绕过限制。

## 资源

- `references/decisions.md`：用户决定与 Agent 沟通记录（先行阅读，含最新授权）。
- `references/agent-roster.json`：Agent 类型、排班窗口、当前书目、完读状态与运行状态的唯一登记源。
- `references/coordination.md`：所有 Agent 共用的文件归档、冲突预防、Git 与公开发布规则。执行任何共享写入或发布前先读。
- `references/agent-communication.md`：跨 Agent 任务认领、状态与交接板；开始、交接、完成或遇阻时更新。只写适合公开的最少元数据。
- `references/platforms/weread.md`：微信读书平台适配说明；使用 WeRead 时读取。
- `references/platform-adapter-template.md`：接入新阅读平台时复制并补全的适配模板。
- `references/automation-code-agent.md`：代码类 Agent（weread-auto）的自动化实现参考；**仅约束代码类 Agent 自身**，其他 Agent 不必阅读、不受其约束。
- `templates/pre-read-overview.html`：新书开读时的全书视角初版（overview）HTML 骨架。
- `templates/date-note.html`：每日阅读笔记 HTML 骨架。
- `templates/final-book.html`：完读后的整书 HTML 汇编骨架。
