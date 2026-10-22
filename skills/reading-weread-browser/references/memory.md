# 通用浏览器角色可迁移规则记忆

- 稳定ID `wechat-reading-browser`；浏览器实读角色与 `weread-auto` 代码自动化、轻游记专属角色职责不同。
- 官方微信读书 Skill 可辅助元数据查询，但不读正文/书内AI；正文与AI问答须在获授权阅读器现场确认。
- schedule-only 定时信号不是开始阅读；登记入 main、全队锁核验及管理员明确“已转达”后方可开始。错过不补。
- 共享阅读器全队串行；书目与活动状态以 registry、当天沟通记录及最新 main 为准。
- 来源：`skills/luoyu-reading/references/platforms/weread.md`、`reading-state-protocol.md`、`agent-roster.json`、`decisions.md`；轨迹 `agent-room/tracks/wechat-reading-browser.html` 仅说明职责，不是实时状态。
