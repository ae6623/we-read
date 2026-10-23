# 团队待办目录（todo）

用途：记录各位读书成员的 openspec 待办与完成情况，每人一个独立文件，互不覆盖。

## 结构

- `todo/admin/`：管理员的团队级待办（总计划、规则变更、窗口安排、群内 todo 汇总）。
- `todo/<成员>/`：各读书员自己的待办，按周拆分，文件名为 `YYYY-MM-DD-week.md`（周一日期）。
- 成员的 openspec 原文件仍放在 `openspec/<成员>/todo.md`；`todo/` 目录只放索引和每周进展，不替代 openspec。

## 规则

1. 每人只写自己的文件，不改别人的待办。
2. 待办只记事项与完成情况；认领、登记、锁、续读点、收尾仍以 main 上的 `book-registry.json` 和 `agent-roster.json` 为准。
3. 文件过长时，新开一个周文件，旧文件保留，不删改。
4. 公开文件不写 Agent UID、群 ID、账号、私人路径或凭据。
5. 每次更新走普通 PR，合并后回读 main，报 commit。

## 成员索引

| 成员 | 公开称呼 | 待办文件 |
|---|---|---|
| 管理员 | 管理员 | `openspec/admin/todo.md`（待建） |
| Windows 读书员 | 阅读员-Windows读书 | `openspec/windows-local-pdf-reader/todo.md` |
| AI读书员 | 阅读员-AI读书 | `openspec/wechat-reading-browser/todo.md` |
| 轻游记员 | 阅读员-轻游记 | `openspec/qingyouji-reader/todo.md` |
| 读书时长专员 | 读书时长专员 | `openspec/reading-duration/todo.md` |

以上“待建”项由各成员在 PR 里补齐。
