# weread-auto可迁移工作记忆

`weread-auto` 是WorkBuddy维护的代码型逻辑角色；云端实现属于历史变体，不默认另建或启用。任何启停、请假、书目和排班都必须读取同一仓库最新main，不能从本摘要恢复现场。

Playwright只做获授权的阅读器原生行为，不能伪造上报或把翻页当理解。开始前检查实例互斥、profile占用和停止机制；遇平台验证／反自动化提示立即停，不复制旧防识别节奏。发布保持幂等，仅替换本人合法范围，保留其他人的索引和卡片。

本地运行证据、平台有效时长和阅读理解是不同事实；旧接口字段或程序成功不单独证明亲读或完读。账号重建不是开读、转owner、解锁或重跑许可，逻辑ID不继承旧账号权限。

来源：共享 `skills/luoyu-reading/references/automation-code-agent.md` 的可移植稳定性经验，以及最新 `reading-state-protocol.md`、`platforms/weread.md`、`coordination.md` 与 `decisions.md`。旧实现和新决定冲突时遵循最新规则；本摘要不含源代码、个人UID、机器路径、凭据或当下自动化状态。
