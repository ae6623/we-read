# 待办协议（todo-protocol）

> 目的：**防崩溃丢进度、防两个 Agent 漏项或重复做**。
> 适用范围：本仓库所有 Agent（`frontend-mod`、`luoyu-content`、`admin`、`qingyouji-reader`、`reading-duration`、`wechat-reading-browser`、`windows-local-pdf-reader`）。
> 生效：2026-10-27 起。与 [frontend-a2a.md](frontend-a2a.md)（跨 Agent 协调）、[frontend-conventions.md](frontend-conventions.md)（前端实现）、[coordination.md](../coordination.md)（Git 协调）并用，互不替代。

## 1. 一句话规则

**开工前先把自己的待办写进 `openspec/<角色>/todo.md` 并提交；每完成一项立刻打勾并提交。**

不写 todo 就动手 = 违反协议。崩溃后没人知道你想干什么、干到哪了。

## 2. 文件归属

| 角色 | 待办文件 |
|------|----------|
| 前端改造 | `openspec/frontend-mod/todo.md` |
| 内容/LuoYu | `openspec/luoyu-content/todo.md` |
| 管理员（团队级） | `openspec/admin/todo.md` |
| 其余角色 | `openspec/<角色>/todo.md`（沿用既有目录名） |

- **只写自己那一个文件**。别人的 todo 只读，不改。团队级事项归 `admin`。
- 不新建平级的 `TODO.md` 于仓库根 —— 根目录会被所有 Agent 抢写，必冲突。

## 3. 开工前三步（强制）

1. **读**：`cat openspec/<角色>/todo.md`，确认上一轮有没有未完成项。
2. **写**：在本轮动手前，把本轮要做的事写进「待办」区，每条必须满足：
   - 动词开头、可验收（写出"改哪个文件/产出什么"），不写"优化一下""看看"；
   - 标注依赖或阻塞（等谁、等什么结论）。
3. **提交**：只提交这一个文件，`git push`，让对方在 main 上看得到你要做什么。

```bash
git add openspec/<角色>/todo.md
git commit -m "todo(<角色>): 登记本轮任务：<一句话>"
git push origin fix-publish:main   # 各角色按自己的推送分支
```

## 4. 执行中（每步即落盘）

- **完成一项 → 立刻改 `[x]` → 单独 commit**。不要攒到最后一次性提交，崩溃时攒的全会丢。
- 中途改变计划：先改 todo（新增/删去/标注放弃原因）再动手，别让 todo 与事实脱节。
- 卡住超过一个动作没进展：在该项后加 `⏸ 阻塞：<原因>`，并发 A2A `QUESTION` 给对方，不要静默放弃。
- 提交粒度参考：一次 commit 对应 todo 里的一条，commit message 带上该条的关键词，便于 `git log` 反查。

## 5. 崩溃 / 新会话恢复（关键）

新会话第一件事，按顺序：

1. `git fetch origin && git log --oneline -10 origin/main` —— 看最近发生了什么。
2. `cat openspec/<角色>/todo.md` —— 找 `[ ]` 与 `⏸ 阻塞` 的项。
3. `python3 scripts/a2a_frontend_check.py --alias <角色> --update` —— 看有没有写给自己或 `ALL` 的消息。
4. 对照 `git log` 与你 todo 的勾选，判断"最后一条 `[x]` 之后做了什么"：有 commit 但 todo 没打勾 → 先补勾；有 todo 没 commit → 先确认工作树是否有未提交改动（`git status` / `git stash list`），**不要直接重做**。
5. 从中断处继续，并把恢复判断写进 todo 的「当前状态」。

## 6. 与 OpenSpec（spec-driven）的分工

仓库同时有两套东西，别混：

| 用途 | 位置 | 何时用 |
|------|------|--------|
| **日常待办 / 进度** | `openspec/<角色>/todo.md` | 每一轮都写，轻量，人工可读 |
| **正式变更提案** | `openspec/changes/<change-id>/`（`proposal.md` / `design.md` / `tasks.md`） | 跨多文件、改数据模型、改协议、需要留决策记录时 |
| **已定稿规格** | `openspec/specs/<capability>/spec.md` | 变更归档后沉淀的"系统当前应有的行为" |
| **配置** | `openspec/config.yaml` | 产物语言 `zh-CN`、schema |

判断口径：**能一句话描述、单次提交能做完 → 只写 todo.md；需要先论证方案或分多轮 → 开 change。**

CLI（已装 v1.15.0，见 [tooling-setup.md](tooling-setup.md)）：

```bash
openspec list                 # 列当前 changes
openspec validate --all       # 校验 spec/change 格式
openspec archive <change-id>  # 归档已完成的 change 到 specs
```

## 7. 验收（自检清单）

- [ ] 本轮动手前，`openspec/<角色>/todo.md` 已有对应条目并已推送。
- [ ] 本轮每个完成项都已 `[x]`，且各有一条 commit。
- [ ] `git status` 干净，没有"改了但没提交、也没记在 todo 里"的孤儿改动。
- [ ] 撞到别人文件时，A2A 板上已有 `START` / `QUESTION` / `CONFLICT` 记录。
