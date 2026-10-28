## Why

站点在 10-27～10-28 两轮快速叠加后，页面类型与命名失控：同一批书同时存在「全书视角（overview）」「AI 大纲（outline）」「全书导图 / 精读（mindmap）」「精读深读（deep-read）」「日期笔记（notes/<date>）」五套入口，读者分不清先后；首页顶部 Tab 用「通读 / 精读 / 归档」但「通读」实际就是书架本身，筛选却按「在读 / 已完读 / 未开读」——而按站主 8.1 决定，后续不再安排亲读，「在读 / 已完读」这套状态口径已失效。

产品经理 2026-10-28 出 `[信息架构改版方案 v2]`（`docs/site-ia-redesign-2026-10-28.md`，状态：已拍板待执行），本变更即该方案的执行载体。

核心待解决问题：

1. **分类口径失效**：状态类（在读/已完读/未开读）不再有意义，需换成内容类型（通读/精读/归档/系列）。
2. **入口重复**：deep-read 58 页与精读页（mindmap）内容高度重叠（逐章原句重复），但逐章追问又是 deep-read 独有，读者要在两页间来回跳。
3. **首页不可用**：书架（通读面板）无搜索框、无内容类型筛选，78 张卡只能翻。
4. **文案历史包袱**：「读前通读」「全书导图」「精读深读」「网页版」「待整理」等旧词散布各页。

## What Changes

- **四种模式落地**：通读（overview.html，= 书架）/ 精读（mindmap.html）/ 归档（final.html、notes/）/ 系列（系列页）。取消一切状态类展示与筛选。
- **首页（第 1 批）**：顶部 Tab 改「书架 / 系列 / 精读 / 归档」；书架顶部加 sticky 搜索框 + 类型筛选（全部/通读/精读/归档）+ 结果计数；卡片精简成「书名链接（=全书入口）+ 1 个类型标签 + 一句提示 + 入口行（精读 / AI 大纲）」。
- **首页（第 2 批）**：首屏两段理念文字默认折叠（展开状态存 localStorage）；全站文案统一，废弃旧词。
- **deep-read 合并（第 3 批）**：58 页 deep-read 的「逐章追问」按章名匹配挂进对应精读页章节，「核心追问」进精读页尾部区块；完成后原 URL 保留轻量迁移页并清理站内引用。
- **单书页（第 4 批）**：overview.html 首屏加「从这里开始」导航块（这页解决什么 / 下一步去哪）。
- **内容与来源标注（8.2）**：LLM 生成内容在首屏说明 AI 来源；只有能逐字对应原文的才标「原文引句 / 金句」，其余标「AI 概括」。

## Impact

- Affected specs: `site-ia`（新建）
- Affected code:
  - 前端：`index.html`、`assets/css/homepage-reading.css`（+ 可能新增首页交互 JS）、`tools_link_mindmap_index.py`（卡片与筛选属性）
  - 内容：`gen_mindmap.py`（合并后模块/来源标注）、`gen_deep_read.py`（停用，不再产出新页）、`add_mindmap_modules.py`、`overview.html` 系列（IA-05 导航块）
  - 工具：新增 `merge_deepread_to_mindmap.py`（合并迁移 + 未匹配清单）、`rewrite_legacy_copy.py`（文案统一）
- 角色边界：
  - **frontend-mod**：首页结构 / Tab / 搜索 / 筛选 / 折叠 / 卡片模板 / CSS / JS（IA-01、IA-02、IA-03、IA-04 及 8.4、8.5 交互部分）
  - **luoyu-content（本提案起草人）**：deep-read 合并与下线、文案统一、来源标注、单书页导航块内容（IA-05、IA-06、第 3 批、8.2）
- 发布约束：沙箱 git 协议不通，提交一律走 GitHub REST（`gh_api.GhApi.publish_paths`）；本地仓落后于线上，改 `index.html` 前 MUST 先拉线上版为基准。
- Out of scope：
  - **EPUB 下载入口**：方案注明「暂不放」（此前因下载到假文件已隐藏 68 处），等真产物可用再恢复。
  - 系列页内容建设、书卡数据 `_data/books/*.json` 重建（`extract_content.py` 归 frontend-mod）。
  - 历史日期笔记的删除或改写（8.1 明确：不删除既有阅读事实）。
