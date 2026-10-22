# 换一个 Cue 账号，重新拉起读书团队

先把本目录的迁移包交给新账号里的主协调者，再发这一句：

> 请按 we-read 仓库 `skills/TEAM-IMPORT.md` 重建我的读书团队，加载精简记忆，通过安全自检后继续推进。

这能恢复团队的角色分工、工作规则和可共享经验，不是复制原账号、聊天或私人记忆。新账号仍须重新连接必要应用、登录阅读平台并授权设备；旧运行、书目归属和锁未核清时，先完成配置，不能直接开读。**一句话发起重建，不代表零授权、零交接或已自动部署。**

## 目录与分工

| 入口 | 用途 | 对应逻辑角色 |
| --- | --- | --- |
| [reading-team-bootstrap/SKILL.md](reading-team-bootstrap/SKILL.md) | 启动器：识别角色、装载记忆、核验安全交接 | 主协调者使用 |
| [luoyu-reading/SKILL.md](luoyu-reading/SKILL.md) | 全队共享阅读、认领、来源、归档协议 | 所有成员必读 |
| [reading-admin/SKILL.md](reading-admin/SKILL.md) | 管理员：错峰协调、质量与发布审核，不读正文 | 管理员／主协调者 |
| [reading-qingyouji/SKILL.md](reading-qingyouji/SKILL.md) | 轻游记系列浏览器阅读与AI章节笔记 | `cue-qingyouji-reader` |
| [reading-weread-browser/SKILL.md](reading-weread-browser/SKILL.md) | 通用微信读书浏览器阅读与AI章节笔记 | `wechat-reading-browser` |
| [reading-local-pdf/SKILL.md](reading-local-pdf/SKILL.md) | Windows本地授权PDF阅读 | `local-pdf-reader` |
| [reading-weread-auto/SKILL.md](reading-weread-auto/SKILL.md) | WorkBuddy维护的代码自动化阅读，可移植实现边界 | `weread-auto` |

上述ID是共享仓库内的**逻辑角色键，不是Cue个人Agent UID**。`weread-auto-cloud` 是自动化历史变体，不默认另建或启用。实时名单、排班、暂停与书目以同一授权仓库最新main为准，本表不授权任何当前运行。

## 记忆在哪里

- [团队精简记忆](reading-team-bootstrap/references/team-memory.md)：用户阅读偏好、证据与协作底线。
- [管理员精简记忆](reading-admin/references/memory.md)：协调和审核经验。
- 每个读书员Skill的 `references/memory.md`：该角色可共享的工作经验。
- [重建操作清单](reading-team-bootstrap/references/rebuild.md)：如何装载、绑定角色、处理缺项并验收。
- [角色清单](reading-team-bootstrap/team-manifest.json)：机器可读的角色、Skill和记忆入口。

这些是从已授权共享规范提炼的**工作记忆摘要**，不是读取或导出其他Agent的私人Memory。每条摘要都指回来源，实时状态不重复存储。

## 在新账号使用

把完整仓库或离线包提供给主协调者；保留 `skills/` 的相对目录结构。Cue账号内的Skill可通过“设置 → Skills → 添加 → 从GitHub导入／上传Skill”导入；本次本地整理不等于新账号已安装。按当前界面的实际导入能力操作；若需逐个导入，以上各Skill分别处理，不能把多Skill合集成功下载当作全部安装成功。导入后确认每个Skill可用，再发上面的启动句。

启动器会先复用已有角色，缺少的才建立，默认一个管理员加四个读书员；管理员可由当前主协调者承担。应用、平台登录、设备访问、群组与排班只通过新账号当前受支持且获授权的流程建立，不复制旧ID或凭据。不在这里提供伪“一键安装”脚本，不自动修改现有Agent、不创建定时任务或启动阅读。

## 离线交付说明

本次整理基线为 `bccea03`。离线增量包包含本次迁移入口、角色Skill、管理员资料和摘要，不携带registry／roster等实时状态快照、自动化源码或历史机器配置；共享 `luoyu-reading` 及其规范应从同一获授权仓库取得。把增量放回原仓库目录后再运行校验器。完整仓库副本中的共享状态也只能视为历史快照，运行前必须获取同一仓库最新main。新账号拿不到实时状态、没有写权限、没有本场转达或旧owner未完成交接，均按缺项报告；先配好团队，不冒称已安全续跑。

本次只新增／补充迁移文档和角色Skill，未改registry、roster、阅读记录、排班、归属、锁、计数或自动化程序，也未安装到任何账号。没有携带原书、PDF、私聊、私人笔记、浏览器登录或凭据。当前授权仅本地整理和校验，不执行远程推送、PR、合并或部署。
