> 执行规则：每完成一项立刻勾选 `[x]`；做不到写 `[!]` 并附原因。

## 1. 需求与拆解

- [x] 1.1 更新到最新 `main`，隔离干净工作树，不触碰其他任务未提交改动
- [x] 1.2 新增 `docs/allow-private-fulltext-archive-2026-11-07.md`，记录需求、根因、解决方案与验收口径
- [x] 1.3 新增 openspec change：`proposal.md` / `design.md` / `tasks.md` / `specs/private-fulltext-archive/spec.md`

## 2. 三处规则

- [x] 2.1 `skills/luoyu-reading/SKILL.md` 笔记质量段：引用限制改为按目标位置分流，新增私有归档全文豁免
- [x] 2.2 `skills/luoyu-reading/references/ai-ask-book.md` 交付前检查项：去掉「大段受版权保护文本」，注明短引限制仅适用公开页面
- [x] 2.3 `docs/local-reading-guide.md` 公开与私有边界：拆出私有存档允许段，保留公开发布与凭据安全项
- [x] 2.4 三处各自写全允许条件，不依赖交叉引用
- [x] 2.5 不动笔记核验范围、金句来源、AI 问书流程、registry / roster / 状态协议

## 3. 校验与提交

- [x] 3.1 `grep` 复核三处旧禁止句已消除，公开页面限制与安全项仍在
- [x] 3.2 只 `git add` 本次真实写入的文件，文本 LF，无绝对路径／机器名／凭据
- [x] 3.3 一次 commit，fast-forward 推送 `origin/main`
- [x] 3.4 同步到本机在用的工作副本，不混入该工作副本原有的未提交改动

## 4. 不在本次范围

- [ ] 4.1 既有笔记与发布物批量回改（不追溯）
- [ ] 4.2 任何对外转载／公开发布授权（白名单书籍除外，见第 5 节）

## 5. 白名单无条件服从（同日追加）

- [x] 5.1 需求 MD 追加白名单章节，更新解决方案与验收口径
- [x] 5.2 proposal / design / tasks / spec 同步追加白名单设计与 R8
- [x] 5.3 `skills/luoyu-reading/SKILL.md` 笔记质量段显眼位置写入白名单条款，明确覆盖公开页面与外链限制
- [x] 5.4 `skills/luoyu-reading/references/ai-ask-book.md` 交付检查段写入白名单条款，明确覆盖短引总量与交付前检查项
- [x] 5.5 `docs/local-reading-guide.md` 公开与私有边界节首位写入白名单条款，明确覆盖本节全部发布限制
- [x] 5.6 三处均写明「无条件服从、不再管硬性条件约束、优先级最高」，不叠新判据
- [x] 5.7 重新提交并推送 `origin/main`
- [x] 5.8 同步本机工作副本三处规则
