# 阅读 Agent 协作与交接板

这里是跨 Agent 的持久交接记录，不是实时聊天。每个 Agent 开始或结束一项共享归档工作时，都按下方格式追加或更新自己的记录；先拉取最新 `main`，避免覆盖他人的更新。

## 使用规则

1. 开始工作前检查“进行中”记录与 GitHub 最新状态；认领具体书目、日期和文件路径。若同一文件已被其他 Agent 认领，先协调，不并行覆盖。
2. 只编辑自己的记录；其他 Agent 的记录只读。发起或接收交接时，用 GitHub commit / PR 链接或路径注明结果，避免把整段书籍内容复制进本文件。
3. 完成后将状态改为“已交接/完成”，记录提交号、输出路径和后续负责人；被阻塞时写清阻碍、需要谁做什么。
4. 只记录协作所需的最少元数据。不要写密码、验证码、令牌、私人聊天内容、未获公开授权的读书笔记或长篇书籍摘录。
5. 这是公开仓库中的协作文件，只写适合公开的状态摘要；私密笔记留在用户私有归档中。
6. 需要实时讨论时，在对应 GitHub PR/Issue 中留言；此文件保留关键结论、任务归属和交接，不取代实时消息。
7. 更新本文件前后检查 `git status`、`git diff --check` 和 `git diff --stat`，只提交本任务涉及的文件。

## 记录格式

复制此模板追加新工作；使用 Asia/Shanghai 时间：

```text
### [YYYY-MM-DD HH:MM] <任务短名>
- Agent：<Agent 名称/标识>
- 书目：<书名或书目 slug；无则写“无”>
- 状态：进行中 / 待协作 / 已交接 / 完成
- 认领文件：<路径列表>
- 分支/提交：<分支名与 commit；尚无则写“尚未提交”>
- 交接给：<Agent 名称/标识或“用户”>
- 下一步：<一个明确动作或“无”>
- 备注：<只写公开且必要的事实>
```

## 当前工作

### [2026-10-17 18:22] 扩充跨平台阅读 Skill 协作规则
- Agent：微信读书
- 书目：无
- 状态：进行中
- 认领文件：`skills/luoyu-reading/SKILL.md`、`references/coordination.md`、`references/agent-communication.md`、`references/platform-adapter-template.md`
- 分支/提交：`main`；尚未提交
- 交接给：其他阅读 Agent
- 下一步：完成本地校验并提交
- 备注：新增公开的协作交接板和平台适配模板，不包含任何读书笔记。

### [2026-10-17 21:50] 应用户要求更新 Skill：开读即出全书视角初版 + 自动发布授权
- Agent：weread-auto 维护 Agent（WorkBuddy）
- 书目：无
- 状态：已交接/完成
- 认领文件：`skills/luoyu-reading/SKILL.md`、`references/coordination.md`、`references/decisions.md`（新建）、`templates/pre-read-overview.html`、`templates/date-note.html`
- 分支/提交：`main`；单提交（rebase 合并）
- 交接给：其他阅读 Agent
- 下一步：各 Agent 按 `decisions.md` 四点执行；weread-auto 随后改造输出结构对齐新归档
- 备注：用户 2026-10-17 四点决定详见 `decisions.md`。本次与上方“扩充协作规则”任务并行修改同批文件：已保留对方全部增量（交接板机制、平台适配模板、流程第 1/6 步表述），仅按用户决定改写流程第 2/4/5 步、导语、模板与资源列表，未删除对方任何内容。若对“开读即出全书视角初版”有异议，请在 `decisions.md` 追加讨论。

### [2026-10-17 22:50] 晚场不再跳过 + 同日两场合并为“一天一篇”
- Agent：weread-auto 维护 Agent（WorkBuddy）
- 书目：无（规则变更，影响全部书目）
- 状态：已交接/完成
- 认领文件：`skills/luoyu-reading/SKILL.md`、`references/decisions.md`
- 分支/提交：`main`
- 交接给：其他阅读 Agent
- 下一步：各 Agent 同日多段阅读时，按天合并产出一篇日期笔记，不要在站点生成同日两篇
- 备注：用户决定“今天已有效阅读也别跳过，双读双保险”，晚场跳过逻辑已移除（06:00/18:00 两场都跑）；站点侧同日合并口径见 `decisions.md` 第 8 条（数值累加、章节摘录并集）。本次同时修正了《住小房子的女人》当日两场被拆成两版笔记的历史数据，已重新发布。
