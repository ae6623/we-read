# 工具链安装（tooling-setup）

> 目的：让参与本仓库的**每个 Agent** 都有同一套"计划 → 执行 → 验收"工具，漏项可查、崩溃可恢复。
> 更新：2026-10-27。装过的版本：`openspec 1.15.0`、`superpowers`（obra/superpowers，15 个技能）。

## 0. 前置

- Node.js ≥ 18（本机 v22.22.2）、npm ≥ 9（本机 10.9.7）、git。
- 能访问 npm registry 与 github.com。**装不上不影响协作**：`openspec/<角色>/todo.md` 与 A2A 板都是纯文本，git 就能用（见第 4 节降级方案）。

## 1. OpenSpec（规格驱动 / 变更提案）

```bash
npm install -g @fission-ai/openspec
openspec --version            # 期望 1.15.0+
```

在仓库内初始化（**只需一次**；已初始化过会提示，不会覆盖 `openspec/<角色>/todo.md`）：

```bash
cd <repo>
openspec init --tools codebuddy --language zh-CN --no-animation
```

产出（均已入库，克隆仓库即有，无需重装）：

- `openspec/config.yaml` —— schema `spec-driven`，产物语言 `zh-CN`。
- `openspec/changes/` —— 变更提案（`proposal.md` / `design.md` / `tasks.md`）。
- `openspec/specs/` —— 已归档的正式规格。
- `.codebuddy/skills/openspec-*` + `.codebuddy/commands/opsx/*` —— 给 CodeBuddy 系 Agent 的 6 技能 6 命令。

常用命令：

```bash
openspec list                  # 列出当前 change
openspec validate --all        # 校验格式
openspec archive <change-id>   # 归档
```

> 注意：本仓库另有 `openspec/<角色>/todo.md` 这套**人工待办**约定，与 OpenSpec 官方目录并列共存，互不冲突。
> 分工见 [todo-protocol.md](todo-protocol.md) 第 6 节。

## 2. Superpowers（技能包：计划、调试、验收）

上游：https://github.com/obra/superpowers

```bash
# 1) 取一份 vendor（便于后续升级，不参与 git 提交）
mkdir -p ~/.workbuddy/vendor
git clone --depth 1 https://github.com/obra/superpowers.git ~/.workbuddy/vendor/superpowers

# 2) 把技能暴露给 Agent（WorkBuddy 扫描 ~/.workbuddy/skills/<name>/SKILL.md）
for d in ~/.workbuddy/vendor/superpowers/skills/*/; do
  cp -r "$d" ~/.workbuddy/skills/$(basename "$d")
done
```

验证：

```bash
for s in brainstorming writing-plans executing-plans systematic-debugging \
         verification-before-completion requesting-code-review using-superpowers; do
  test -f ~/.workbuddy/skills/$s/SKILL.md && echo "OK  $s" || echo "MISS $s"
done
```

装好的 15 个：`brainstorming`、`writing-plans`、`executing-plans`、`subagent-driven-development`、
`dispatching-parallel-agents`、`systematic-debugging`、`test-driven-development`、`requesting-code-review`、
`receiving-code-review`、`verification-before-completion`、`using-git-worktrees`、`finishing-a-development-branch`、
`writing-skills`、`diagnosing-superpowers`、`using-superpowers`。

**升级**：`git -C ~/.workbuddy/vendor/superpowers pull` 后重跑第 2 步的 `for` 循环。

## 3. 两个 Agent 的关系

- 技能装在**用户级**（`~/.workbuddy/skills`）→ 同一台机器上的所有 Agent 会话都生效，不需要各装一遍。
- OpenSpec 的 `config.yaml` / `.codebuddy/` 在**仓库级** → 别的机器/沙箱 `git clone` 后即有命令与技能，只需 `npm i -g @fission-ai/openspec` 补 CLI。
- 换机器 / 换沙箱时的最小动作：`npm i -g @fission-ai/openspec` + 第 2 节两条命令。

## 4. 降级方案（装不上时）

不阻塞协作，按此优先级：

1. **只靠 git**：`openspec/<角色>/todo.md` + `skills/luoyu-reading/references/frontend-a2a.md` 全是纯文本，`git` 即可完成"登记 / 通报 / 恢复"。这是底线，任何环境都能用。
2. **OpenSpec CLI 缺失**：不跑 `openspec` 命令，但仍按 `openspec/changes/<id>/` 的手写目录结构落 `proposal.md` / `tasks.md`（格式要求见官方 README），不影响与已装 Agent 的兼容。
3. **Superpowers 缺失**：按 [todo-protocol.md](todo-protocol.md) 手工执行同等纪律（先写计划、每步提交、收尾自检）。

## 5. 验收

```bash
openspec --version                                   # 1.15.0+
ls openspec/config.yaml openspec/changes openspec/specs
ls ~/.workbuddy/skills | grep -E 'writing-plans|systematic-debugging'
```

三条都过 = 环境就绪。
