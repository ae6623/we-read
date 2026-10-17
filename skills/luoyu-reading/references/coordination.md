# 共用归档与 Git 协调规则

本指南给所有协作阅读的 Agent 使用。先检查本文件与仓库最新状态，再编辑。

## 归档结构

优先沿用现有归档；当前约定的目标结构：

```text
reading-notes/
├── index.html
├── 规范.md                  # 历史版人读规则；本 Skill 为当前操作版
└── books/<book-slug>/
    ├── overview.html         # 预读版全书视角
    ├── notes/YYYY-MM-DD.html
    ├── final.html            # 完读后整书汇编
    └── final.epub            # 完读后 EPUB
```

旧文件名（如 `书名-YYYY-MM-DD-总结.html`）可继续使用；不要为了统一而移走、覆写或删除现有公开文件。新旧路径并存时同步更新 `index.html` 中的链接。

## 并发工作规则

1. 修改前检查当前任务中的文件和 GitHub 最新 `main`，确认这本书/日期的拥有者与其他 Agent 正在处理的文件。
2. 同一个文件同一时间只允许一个 Agent 写入。认领文件后只改认领范围；碰到并行改动先暂停并协调。
3. 不用旧的本地快照重建整个站点。发布前比较线上、当前 `main`、本地差异，保留线上较新的内容与其他 Agent 已提交的增量。
4. 每个工作分支只含单项变更，建议 `notes/<book-slug>/<date>-<agent>` 或 `site/<date>-<change>`。先 `git fetch origin`，再从最新基线切分支。
5. 提交前运行 `git diff --check`、检查 `git status` 和 `git diff --stat`。确认无误后推分支并通过 PR 或已批准的合并流程；禁止强推、覆盖式上传、无审查地把分支整体并入 `main`。
6. Pages 只发布经授权的已核对版本。推送会让文件公开时，必须确认这次批准覆盖了具体文件；过去对一批内容的批准不自动覆盖未来新笔记。
7. 合并或发布后核对部署结果，再检查主页、各页面、下载链接、时间标签与手机宽度排版。未在线验证前不能说“已发布”。

## 文件命名与笔记范围

- 日期笔记：`<book-slug>/notes/YYYY-MM-DD.html`，一天多次阅读合并到同一文件并标注各段。
- 预读框架：`<book-slug>/overview.html`。它是基于公开材料和用户材料形成的“预读地图”，不是逐章亲读总结。
- 完读汇编：只有整本实际读完并校订后才更新 `<book-slug>/final.html` 和 `.epub`。
- 每次短读只新增/更新当天笔记；不要每天重做全书汇编。
- 标签建议：`亲读`、`官方简介/目录`、`用户材料`、`公开评论/划线`、`综合推断`。不得混写来源。

## GitHub 身份验证

- 优先走已批准的 GitHub CLI/OAuth 或 Git Credential Manager 浏览器授权；GitHub 官方支持 HTTPS Git 凭据助手。
- 一次性设置的常见方式：`gh auth login --hostname github.com --git-protocol https --web`，完成浏览器授权后执行 `gh auth setup-git`。检查 `gh auth status`；后续对已授权仓库进行 `git push` 通常复用凭据，不应每次重新输入令牌。
- 如果授权状态丢失、过期、缺少仓库权限或组织重新要求批准，按真实提示处理；不要声称一次性授权永久有效。
- 不要求用户把 PAT、密码、验证码贴进聊天。禁止把凭据写在 remote URL、脚本、仓库文件、提交信息或 shell 日志中；不要用明文长期保存令牌。
- 该电脑由多个 Agent 共用。GitHub 凭据属于账户敏感凭据，只能由拥有授权的用户/Agent 的既定凭据助手使用；不可复制给其他系统或绕过账号权限。Agent 可以共享仓库规范，不意味着每个 Agent 都获得额外 GitHub 权限。

## 发布边界

公开站点可能被任何人访问。公开笔记、预读框架或 EPUB 只限用户明确批准的那批内容；新增内容默认只留在私有归档。即使拥有 `git push` 权限，也不得把未获授权的文件发布到 Pages。
