---
name: luoyu-reading
description: Multi-platform reading workflow for source-labeled whole-book previews, daily comprehension notes, and final HTML/EPUB archives. Use when reading a user's book through WeRead or another authorized reading platform, recording a session, creating or updating a book overview, or coordinating shared reading archives across agents.
---

# 落雨读书

为用户把多本书读得更有效：先搭建有来源边界的全书预读框架，再把每天真实读到的内容连回框架，完读后才做校订后的整书汇编。把 `references/coordination.md` 作为所有 Agent 共用的归档与 Git 规则；开始、交接或结束共享工作时更新 `references/agent-communication.md`。使用某个平台前阅读对应的 `references/platforms/<platform>.md`（当前先有微信读书指南）。

## 工作流程

1. **识别平台、书目与现有工作。** 先确认用户实际指的书、作者和阅读平台；查看归档索引、预读框架、日期笔记及已完成汇编。查看共享交接板并登记认领文件；遵守并行修改规则，避免重写别的 Agent 的文件。
2. **新书先做预读框架。** 收集可验证的官方书目简介、目录、作者说明、用户提供的材料与可靠公开划线。产出带来源的全书主题/结构框架和待验证问题；标清二手材料、推断和未亲读部分。没有可靠目录或内容时，不装作掌握全书。
3. **每日按真实阅读写一篇日期笔记。** 记录实际范围、关键场景或观点、作者展开方式、与整书框架的联系、理解变化、可迁移启发和问题。只编辑当天的日期笔记；同日多段阅读合并在一篇中。用户希望灵活阅读时，可让阅读时长、停留与思考节奏有自然变化，以理解内容为目的；不能把未读内容写成已读，也不能把平台未确认的打卡说成已成功。
4. **只在理解有变化时修正预读框架。** 不为每次短读重做整书汇编。将新增理解放进当天笔记；确有重要修正时，在预读框架中注明依据和更新时间。
5. **完读后才生成最终整书汇编。** 确认整本已读后，把预读框架和所有日期笔记整合为更有解释力的全书视角：主旨、叙事/论证结构、关键观点间关系、重要转折、核心洞见、局限与可迁移启发。明确实际覆盖范围和外部来源；制作最终 HTML 与 EPUB。预读框架不能冒充最终整书总结。
6. **交付并维护。** 用清晰简洁的 HTML（手机、桌面均可读）保存笔记；给用户可访问文件或站点链接。归档默认私有，不公开发布或推 GitHub，除非用户对具体内容明确授权。Git 仓库更新遵循 `references/coordination.md`；完成或受阻时更新交接板，发布后实际检查页面、资源和 Pages 构建。

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

- `references/coordination.md`：所有 Agent 共用的文件归档、冲突预防、Git 与公开发布规则。执行任何共享写入或发布前先读。
- `references/agent-communication.md`：跨 Agent 任务认领、状态与交接板；开始、交接、完成或遇阻时更新。只写适合公开的最少元数据。
- `references/platforms/weread.md`：微信读书平台适配说明；使用 WeRead 时读取。
- `references/platform-adapter-template.md`：接入新阅读平台时复制并补全的适配模板。
- `templates/pre-read-overview.html`：新书预读框架 HTML 骨架。
- `templates/date-note.html`：每日阅读笔记 HTML 骨架。
- `templates/final-book.html`：完读后的整书 HTML 汇编骨架。
