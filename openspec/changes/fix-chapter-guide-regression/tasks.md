> 执行规则：每完成一项立刻勾选 `[x]`；做不到写 `[!]` 并附原因。

## 1. 生产流程（核心：把修复写进流程，不是补页面）

- [x] 1.1 `produce_all.py` 新增 `chapter_blocks(chs, bms)`：章→小节→要点→原句 唯一装配口，通读/精读共用
- [x] 1.2 `chapter_blocks` 某章无划线时留空，不造小节、不编要点
- [x] 1.3 `chapter_blocks` 不输出 `role`/`gist`/`anchor`（无 LLM 不编章功能与本章概括）
- [x] 1.4 `render_overview` 用「章节导读」模块替换 `<ol>` 平铺 30 章标题，调用 `GM._chapter_html`
- [x] 1.5 `render_overview` 的 `head()` 引入 `assets/css/mmx-guide.css`，不再内联第二套章节样式
- [x] 1.6 `render_mindmap` 用 `chapter_blocks` 填 `secs`/`quotes`/`pts`/`with_q`
- [x] 1.7 `render_mindmap` 的 `GM.render(d)` 改为 `GM.render(d, ctx)`（否则 `full` 恒空）
- [x] 1.8 `render_mindmap` 清掉 `structural_batch` 默认的 `role`/`gist`/`anchor`
- [x] 1.9 `gen_mindmap._chapter_html`：`role`/`gist` 为空整段不输出（站点仓 + 引擎副本同步）

## 2. 单一真源（章名派生）

- [x] 2.1 `reading_note_spec._RENDER_FALLBACKS` 增加 `读者划得最多的句子` / `热门划线` / `热门划线原句`
- [x] 2.2 新增 `_COUNT_TEXT_RE`，排除「划线 12128 人」这类统计文案被当作章名
- [x] 2.3 单测：`chapter_title({"no":2,"title":"第二章"}, 模板小节)` → `第2章`；有真小节名时仍取真名

## 3. 存量回填

- [x] 3.1 新增 `rebuild_overview.py`（按线上 size<20KB 筛简版，只写 overview.html）
- [x] 3.2 新增 `rebuild_mindmap.py`（按线上 size<20KB 筛空壳，只写 mindmap.html）
- [x] 3.3 通读页重建 218 本并发布（commit `c45ba0b07a`）
- [x] 3.4 精读页重建 59 本并发布（commit `980a58b182`）
- [x] 3.5 全库核验：335 本中 330 本含「章节导读」；`<details>` 开闭失衡 0
- [!] 3.6 5 本仍无章节导读：`baikal-qingyouji`/`elephant-qingyouji`/`serbia-qingyouji`/`local-zhi-ye-gui-hua-niao-shu`/`shi-shi` —— 缺 `data/mindmap/<slug>.json` 的 bookId 映射，需按书名反查

## 4. 首页入口

- [x] 4.1 新增 `link_index.py`：增量插卡，已有 slug 跳过，幂等
- [x] 4.2 通读卡补齐（`<!-- preread-card:<slug> -->` 块，98 → 318 张）
- [x] 4.3 精读卡补齐（archive-card，94 → 315 个可点入口）
- [x] 4.4 发布 index.html（commit `d88caa227e`），结构校验 div/article/section 全平衡

## 5. 取证与回归

- [x] 5.1 线上抽查 `er-shou-shi-jian` / `zhou-qi`：overview 均含章节导读且 details 平衡
- [x] 5.2 线上抽查 `zhou-qi` 精读页：22 章 11 章有划线小节，其余如实为空
- [x] 5.3 首页抽查「二手时间」「大明王朝1566」：各 4 处命中（卡片 + 搜索词）
- [x] 5.4 安全阀拦截记录：7 本线上比本地充实（老完整版），保留线上不覆盖

## 6. 待办（不在本次范围）

- [ ] 6.1 首页减重：509KB → 按需渲染
- [ ] 6.2 新链接入 AI 大纲（LLM）以获得真实小节/要点，而非只有划线原文
- [ ] 6.3 `produce_all.py` 等 5 个脚本入仓 `we-read-auto`，结束「沙箱脚本无版本管理」状态
