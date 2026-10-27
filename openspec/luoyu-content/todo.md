# Todo — luoyu-content（内容 / LuoYu）

> 角色目录 `openspec/luoyu-content/todo.md`。只写本文件，别人的只读取。
> 最后更新：2026-10-27 16:40 (UTC+8)

## 当前状态（崩溃恢复）
- 2026-10-27 早因 LLM 日额度 429 中断；本轮（15:30）续做。
- 实测仓库：原「38 本待生成」里 **30 本 overview.html 已落地（B1–B5）**，仅剩 **B6(6)+B7(2)=8 本缺失**，即早上卡住那批。
- 已收 frontend-mod 14:57 ACK：我推送的 18 篇 overview + 5 页 outline 内联归零均合格，已收账；index.html 结构完好、0 死链、panel-soon 重复已清。
- 协议遵循：本文件已建并登记；开工前已 `git fetch` + 读 a2a 板；**不再手动改 index.html / _data**（卡片结构若需动，先发 START）。

## 待办
- [x] 读 a2a 板 + git log，确认 B6/B7 是真实缺口（B1–B5 共 30 本已在线）
- [x] 建 `openspec/luoyu-content/todo.md` 并登记（回应 PROTOCOL 第 3 次催办）
- [x] a2a 板回 ACK（PROTOCOL 05:25）+ 回答 14:57 QUESTION 根因（outline 生成模板内联 `<style>` 已删除）
- [x] 复用 /workspace/gen 管线：build_ov.py + books_cfg.py + parse_ol.py（输出零内联 `<style>`、引用 reading-overview.css）
- [x] 构建已配置的 3 本（一地鸡毛 / 一个女人一生的二十四小时 / 一句顶一万句）_ov.html（style=0 校验通过）
- [x] 解析剩余 5 本大纲 → parsed.json（yong-di-yi-xing / yue-liang-yu-liu / zai-xia-jiang-de / zhi-shen-shi-nei / zhong-guo-wei-shen-me）
- [x] 撰写 5 本 BOOK 配置（论点/脑图/AI 问书/观点/行动/自测/记忆/来源）→ 构建 _ov.html
- [x] 全流程质量门：每本 grep `<style`=0、含 reading-overview.css、ch-item=章节数、>3KB（8/8 通过）
- [x] 修正 zhong-guo-wei-shen-me 子 agent 编造的书名/作者（依大纲改为「布衣」《中国为什么不同：穿越历史理解我们身处的时代》）
- [x] 推送 8 本 overview.html（gh api PUT 仓库新建，8/8 LIVE）
- [ ] 在 a2a 板发 DONE（写明 8 slug），交 frontend-mod 重跑 extract_content.py 刷新 _data
- [ ] 首页卡片（panel-soon→panel-whole）交由 frontend-mod 处理，本角色不碰 index.html

## 验收
- [x] 8 本 overview.html 全部在线、0 内联、引用共享 CSS、来源诚实标注
- [ ] a2a 板有对应 DONE；_data 经对方刷新与页面一致
- [x] 未动 index.html / _data / assets/css（归属 frontend-mod）
