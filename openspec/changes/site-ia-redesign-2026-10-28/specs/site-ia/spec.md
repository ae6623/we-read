## ADDED Requirements

### Requirement: 四种模式是唯一分类口径

站点 SHALL 只以「通读 / 精读 / 归档 / 系列」四种模式组织内容，MUST NOT 再以「在读 / 已完读 / 未开读」等阅读状态做展示或筛选。

#### Scenario: 状态词下线
- **WHEN** 任何页面或卡片需要标注书籍进度
- **THEN** MUST NOT 出现「在读」「已完读」「未开读」「读前通读」「全书导图」「精读深读」「网页版」「待整理」
- **AND** 改用内容类型：全书视角（overview.html）、AI 大纲（outline.html）、精读（mindmap.html）、归档

#### Scenario: 归档不等同于读完
- **WHEN** 一本书进入「归档」
- **THEN** 表示已整理、可回看（可含 AI 问答、LLM 总结与历史日期笔记），MUST NOT 暗示亲读完成
- **AND** 各类内容分别标明来源与内容类型

### Requirement: 首页顶部 Tab 为「书架 / 系列 / 精读 / 归档」

顶部导航 SHALL 为四个面板，其中「书架」即通读（全部书），原「通读」Tab MUST 取消。

#### Scenario: Tab 改名不改 id
- **WHEN** 修改顶部 Tab 文案
- **THEN** 可见文案与 `aria-label` 改为「书架 / 系列 / 精读 / 归档」，元素 `id` MUST 保持不变
- **AND** 四个面板均可正常切换，页面上不再出现「通读」Tab

### Requirement: 书架 MUST 支持按内容类型筛选与搜索

书架 SHALL 在顶部提供 sticky 搜索框与类型筛选（全部 / 通读 / 精读 / 归档），并显示结果计数。

#### Scenario: 筛选判定依据
- **WHEN** 为卡片计算 `data-mode`
- **THEN** 存在 `overview.html` → `whole`；存在 `mindmap.html` → `jingdu`；存在 `final.html` 或 `notes/` → `archive`
- **AND** 一书可有多种模式（空格分隔），但「全部」视图只显示一张卡

#### Scenario: 搜索与筛选同时生效
- **WHEN** 用户输入搜索词并点选类型筛选
- **THEN** 两者 MUST 同时生效，结果计数反映筛选后的卡片数
- **AND** 搜索范围包含书名与折叠入口文字；空结果 MUST 提供「清除筛选」入口

### Requirement: 卡片模板精简为书名 + 一个类型标签 + 一句提示 + 入口行

书卡 SHALL 只保留：书名（= 全书入口链接）、1 个类型标签、一句提示、入口行（精读 / AI 大纲）。

#### Scenario: 入口行白名单
- **WHEN** 渲染卡片入口行
- **THEN** 只放「全书（书名链接）/ 精读 / AI 大纲」，其余一律不放
- **AND** 卡片上 MUST NOT 出现「AI 大纲」「网页版」「AI 问书」「待整理」标签
- **AND** EPUB 下载按「暂不放」执行（等真产物可用，站主另有指示除外）

### Requirement: deep-read 合并 MUST 满足内容保全闸门

58 页 deep-read 的逐章追问与核心追问 SHALL 迁入对应精读页；未匹配项 MUST NOT 静默丢弃。

#### Scenario: 逐章追问按章名匹配
- **WHEN** 迁移 deep-read 的《章名》追问
- **THEN** 按章名匹配挂到精读页对应章节（原句块之后），匹配不上的章跳过并**逐条记录**
- **AND** 迁移清单 MUST 记录「原页 / 原问题 / 处置结果 / 目标章节或锚点」

#### Scenario: 未处置项为零才允许下线
- **WHEN** 准备删除 deep-read 正文
- **THEN** 未匹配且未处置的条目数 MUST 为 0
- **AND** 处置只允许三种：迁移到对应章节、合并为跨章追问、人工确认重复后舍弃
- **AND** 完成迁移前后抽查后才可下线

#### Scenario: 原 URL 保留迁移页
- **WHEN** deep-read 正文下线
- **THEN** 原 URL MUST 保留轻量迁移页（说明内容已迁到哪本书的精读页并给出链接）
- **AND** 站内导航统一改指新精读页（GitHub Pages 无通用重定向）

### Requirement: LLM 内容 MUST 标明来源，引文 MUST 可核对

AI 生成内容与原文引句 SHALL 分别标注，MUST NOT 用引号包装模型概括伪装原文。

#### Scenario: AI 来源标注
- **WHEN** 展示逐章要点、章节追问、跨章总结等 LLM 内容
- **THEN** MUST 在首屏可见处说明其 AI 来源与依据
- **AND** MUST NOT 用「读后感」「亲读」「已完读」描述这些内容

#### Scenario: 引文分级
- **WHEN** 标记「原文引句 / 金句」
- **THEN** 该句 MUST 能逐字对应到可访问原文，并尽量给出章节或小节位置
- **AND** 模型概括、转述或无法核对的句子 MUST 标为「AI 概括」或不展示

### Requirement: 首屏与可访问性 MUST 达标

首屏 SHALL 无需滚动即可见书架卡片；页面在三档宽度 MUST 可用。

#### Scenario: 理念文字默认折叠
- **WHEN** 首次访问首页
- **THEN** 首屏两段理念文字默认折叠，展开状态记 `localStorage`
- **AND** sticky 搜索 MUST NOT 遮住标题或占用过多首屏空间

#### Scenario: 三档宽度与键盘可达
- **WHEN** 在 320px / 390px / 桌面宽度验收
- **THEN** 键盘可展开收起、焦点可见、筛选与搜索叠加正常、无 JS 时基本导航可用
- **AND** 在最大章节数页面实测首屏加载与展开首章响应（不得只测 gzip 总量）
