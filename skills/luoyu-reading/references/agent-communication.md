# 阅读 Agent 协作与交接板

这里是跨 Agent 的持久交接记录，不是实时聊天。`agent-roster.json` 是类型、时间窗、当前书目、完读状态和运行状态的唯一登记源；本文件按次记录开始、结束与交接事件。先拉取最新 `main`，避免覆盖他人的更新。

## 使用规则

1. 每次计划运行开始前查看 roster 和最新通信记录，核对自己的登记时段与当天状态；仅在登记窗口内工作。若另一个 Agent 仍在同一本书上操作，先沟通，不并行翻页或改同一文件。
2. 开始时追加一条记录，写实际开始时间、登记时段和书目；结束、受阻、被打断或跳过回补时再追加对应记录，写实际结束时间和准确状态。不得把计划时间写成实际运行时间。
3. 结束后同步更新 roster 中自己的 `run_status`、`last_run_date`、`last_started_at`、`last_ended_at`、`current_book`、`book_completion` 与 `last_output`。不代其他 Agent 推断或修改其状态。回补只在当天主场未完成时接续。
4. 只编辑自己的记录；其他 Agent 的记录只读。交接时用 commit/PR/输出路径说明结果，不复制书籍内容。
5. 只记录协作所需的最少元数据。不要写密码、验证码、令牌、私人聊天内容、未获公开授权的读书笔记或长篇书籍摘录。
6. 这是公开仓库中的协作文件，只写适合公开的状态摘要；私密笔记留在用户私有归档中。
7. 需要实时讨论时，在已授权的 Agent 群组或对应 GitHub PR/Issue 中留言；本文件保留关键状态，不取代实时消息。
8. 更新本文件前后检查 `git status`、`git diff --check` 和 `git diff --stat`，只提交本任务涉及的文件。

## 记录格式

每次任务完成、受阻或跳过时追加一条记录并填实际起止时间；长任务可先登记“进行中”，结束时追加结果并沿用同一 run ID。使用 Asia/Shanghai 时间：

```text
### [YYYY-MM-DD HH:MM] <Agent 名称> / <run-id>
- Agent：<Agent 名称/标识>
- 类型：<code / browser_non_code / manual>
- 登记时段：<slot 名称与窗口；如 primary 07:00–08:00>
- 运行日期：<YYYY-MM-DD>
- 实际开始：<YYYY-MM-DD HH:MM 或“未启动”>
- 实际结束：<YYYY-MM-DD HH:MM 或“仍运行/被中断”>
- 书目：<书名或书目 slug；无则写“无”>
- 本次任务：<进行中 / 完成 / 受阻 / 被打断 / 跳过回补>
- 全书状态：<在读 / 已完读 / 未确认 / 不适用>
- 阅读范围：<仅章节/页面/平台明确的进度；无则写“未确认”>
- 认领文件：<路径列表>
- 输出：<日期笔记或 commit/PR 链接；未产生则写“无”>
- 交接给：<Agent 名称/标识或“用户”>
- 下一步：<一个明确动作或“无”>
- 备注：<只写公开且必要的事实>
```

## 当前工作

### [2026-10-17 18:22] 扩充跨平台阅读 Skill 协作规则
- Agent：微信读书
- 书目：无
- 状态：完成
- 认领文件：`skills/luoyu-reading/SKILL.md`、`references/coordination.md`、`references/agent-communication.md`、`references/platform-adapter-template.md`
- 分支/提交：`main`；`935bf0d`
- 交接给：其他阅读 Agent
- 下一步：使用共享 Skill 开始阅读任务
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

### [2026-10-17 09:57] 微信读书 / manual-2026-10-17-0957
- Agent：微信读书
- 类型：browser_non_code
- 登记时段：用户手动发起；本次发生时尚未登记固定窗口
- 运行日期：2026-10-17
- 实际开始：2026-10-17 09:57:26+08:00
- 实际结束：2026-10-17 10:10:30+08:00
- 书目：挪威极夜：独处时才能成为自己（轻游记）；世界这么大，我想到处躺
- 本次任务：完成约 10 分钟阅读；前一本读完，接着打开当前书的开篇
- 完读状态：挪威极夜已完读；世界这么大，我想到处躺在读
- 阅读范围：世界这么大，我想到处躺读至《印度折叠》第一章开篇；未记录精确进度
- 状态：完成
- 认领文件：当日私有阅读笔记
- 输出：私有归档；不在公开交接板放笔记正文或私有路径
- 交接给：同一 Agent 的下一阅读场次
- 下一步：后续从《世界这么大，我想到处躺》接读
- 备注：本次为用户手动发起，早于当前固定错峰安排。

### [2026-10-17 23:09] 微信读书 / browser-roster-2026-10-17
- Agent：微信读书（EeRJNYtYyV9U4CMrg8p74z）
- 类型：browser_non_code
- 登记时段：primary 07:00–08:00；recovery 14:00–15:00
- 运行日期：2026-10-17
- 实际开始：2026-10-17 23:09
- 实际结束：2026-10-17 23:35
- 书目：无；本次为排班和协作配置，不是阅读场次
- 本次任务：完成排班和协作规范调整
- 完读状态：当前在读书仍为《世界这么大，我想到处躺》；本次未进行阅读
- 阅读范围：本次未阅读
- 状态：已完成，等待 PR 合并
- 认领文件：`skills/luoyu-reading/SKILL.md`、`references/agent-roster.json`、`references/agent-communication.md`、`references/coordination.md`、`references/decisions.md`
- 输出：commit `501fc4a`；PR https://github.com/ae6623/we-read/pull/1；每日计划已调整为 07:00 与 14:00 触发
- 交接给：其他阅读 Agent
- 下一步：其他 Agent 查看 roster 并登记自己的类型、时段与状态；合并 PR 后按提示协作
- 备注：只记录公开的协作元数据，不包含读书笔记正文。

### [2026-10-17 23:29] weread-auto / roster-self-registration
- Agent：weread-auto（WorkBuddy 维护）
- 类型：code
- 登记时段：morning 06:00–06:30；evening 18:00–18:30（按现有 Skill 登记）
- 运行日期：待代码 Agent 自己更新
- 实际开始：未知，待代码 Agent 从自己的运行记录填入
- 实际结束：未知，待代码 Agent 从自己的运行记录填入
- 书目：未知，暂不猜测
- 本次任务：待协作
- 完读状态：未确认
- 阅读范围：未确认
- 认领文件：`references/agent-roster.json` 中自己的条目
- 输出：待代码 Agent 在共享 roster 中登记后补充
- 交接给：weread-auto 维护 Agent
- 下一步：请按自己的真实运行记录填写书目、完读状态、运行状态、最近开始/结束时间与输出索引；代码实现规则仍只由代码 Agent 自行维护
- 备注：浏览器 Agent 未访问代码 Agent 的本机记录，以上未知项保持空缺，不推断。
