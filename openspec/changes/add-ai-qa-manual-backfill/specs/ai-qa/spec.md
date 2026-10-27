## ADDED Requirements

### Requirement: AI 问书可脱离阅读场次独立触发

系统 SHALL 提供不依赖整场阅读流程的 AI 问书入口，对任意指定书目单独执行一轮问答并写入当日笔记。

#### Scenario: 控制台单本触发
- **WHEN** 用户向 `POST /api/ai_qa` 发送 `{"book": "文化苦旅", "n": 3}`
- **THEN** 系统启动隔离子进程执行 `weread_daily.py ai-qa --book 文化苦旅 --n 3`
- **AND** 不启动任何阅读场次、不翻页、不上报阅读时长
- **AND** 返回 `ai_qa_summary` 摘要与退出码

#### Scenario: 并发保护
- **WHEN** 上一轮 AI 问书尚未结束，用户再次发起请求
- **THEN** 系统返回 HTTP 409 与 `reason=run_busy`
- **AND** 不启动第二个浏览器实例

#### Scenario: 书目不存在
- **WHEN** 指定书目无法解析出阅读器 URL
- **THEN** 系统以退出码 2 结束
- **AND** 不生成任何笔记页或空区块

### Requirement: 历史笔记可按原日期回补且标注为事后补问

系统 SHALL 支持扫描缺少 AI 问书区块的历史笔记页并补齐，问答 MUST 按笔记原始日期落盘，且 MUST 在页面显式标注为事后补问。

#### Scenario: 按原日期落盘
- **WHEN** 回补 `2026-10-19` 的笔记页
- **THEN** 调用 `save_items(book, "2026-10-19", qa)`
- **AND** 不得使用运行当天日期，不得清除该日期已有条目

#### Scenario: 同书多篇共用一轮问答
- **WHEN** 一本书有多篇待补笔记
- **THEN** 系统只提问一轮（全书视角）
- **AND** 将同一组问答写入每一个待补日期

#### Scenario: 事后补问标注
- **WHEN** 渲染带 `backfill: true` 的问答条目
- **THEN** 该 section 显示「以上问答为事后补问（日期），依据全书内容生成，不代表当日阅读进度。」
- **AND** 不带该字段的正常条目渲染结果不变

#### Scenario: 幂等与断点续跑
- **WHEN** 回补中途中断后重跑
- **THEN** 已有 `<section class="aiqa">` 的页面默认跳过
- **AND** 单本失败只记录跳过原因，不中断其余书目

### Requirement: 提问生成 MUST 排除前置页噪声

系统的自动提问 MUST 不基于版权页、目录、引言等前置页面生成，同时 MUST NOT 误杀含相同词根的正文章节。

#### Scenario: 前置页被剔除
- **WHEN** 章节列表包含 `版权信息`、`引子`
- **THEN** 生成的问句不包含这些词，改由正文章节或通用问句生成

#### Scenario: 正文章节保留
- **WHEN** 章节列表包含 `版权制度的起源`
- **THEN** 该章节不被判定为前置页
- **AND** 可用于关键词抽取

### Requirement: 回补产物的发布 MUST 限定在完整会话持有方

改动历史笔记页的发布 MUST 由持有最全场次记录的客户端执行，云端发布 MUST 只追加当日笔记。

#### Scenario: 历史页发布
- **WHEN** 需要提交被回补的历史笔记页
- **THEN** 由本机执行 `git push origin fix-publish:main`
- **AND** 只提交本次真正改动的页面，不整目录扫描 diff

#### Scenario: 云端越界防护
- **WHEN** 云端完成回补产出
- **THEN** 云端只产出 JSON 与重建后的本地 HTML
- **AND** 不由云端推送历史页
