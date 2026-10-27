# openspec/ 目录说明

本目录**同时承载两套东西**，各管一段，互不替代：

## 一、角色待办（人工、轻量、每轮都写）

```
openspec/<角色>/todo.md
```

| 角色 | 文件 |
|------|------|
| 前端改造 | `openspec/frontend-mod/todo.md` |
| 内容 / LuoYu | `openspec/luoyu-content/todo.md` |
| 管理员（团队级） | `openspec/admin/todo.md` |
| 轻游记读书员 | `openspec/qingyouji-reader/todo.md` |
| 读书时长专员 | `openspec/reading-duration/todo.md` |
| AI读书员 | `openspec/wechat-reading-browser/todo.md` |
| Windows PDF 读书员 | `openspec/windows-local-pdf-reader/todo.md` |

规则：**只写自己那一个文件**；别人的只读。开工前先登记，每完成一项立刻 `[x]` 并单独 commit。
完整规则 → [todo-protocol.md](../skills/luoyu-reading/references/todo-protocol.md)

## 二、正式规格（OpenSpec spec-driven，CLI 管理）

```
openspec/config.yaml            # schema: spec-driven，产物语言 zh-CN
openspec/changes/<change-id>/   # 变更提案：proposal.md / design.md / tasks.md
openspec/specs/<capability>/    # 已归档的正式规格 spec.md
openspec/changes/archive/       # 归档区
```

常用命令（`openspec` v1.15.0，安装见 [tooling-setup.md](../skills/luoyu-reading/references/tooling-setup.md)）：

```bash
openspec list                  # 当前 changes
openspec validate --all        # 校验格式
openspec archive <change-id>   # 归档到 specs
```

## 三、什么时候用哪套

- 一句话能描述、单次提交能做完 → **只写 `openspec/<角色>/todo.md`**。
- 需要先论证方案 / 跨多文件 / 改数据模型或协议 / 要留决策记录 → **开 `openspec/changes/<change-id>/`**，完成后再归档进 `specs/`。

> 注意：`openspec/<角色>/` 是本仓库既有的人工约定，与 OpenSpec 官方子目录（`changes/`、`specs/`）**并列共存**，`openspec init` 不会删除它们。
