## Why

2026-11-01 用户实测：「精读的章节导读模块都消失了，不仅没有标题，而且一、二、三也没了；《大明王朝1566》通读和精读都没有产出卡片」。

三个抱怨，对应三处**生产流程断层**，都不是单页 bug：

| 现象 | 根因 | 影响面 |
|------|------|--------|
| 章节导读整块消失 | `produce_all.render_overview` 是手写极简模板：一句话 / 简介 / `<ol>` 平铺 30 章标题 / 热门划线 / 三问，**从来没有「章节导读」模块** | 线上 335 本通读页里 240 本被它覆盖成 4–8KB 简版 |
| 精读章节点开是空的 | `render_mindmap` 给 `structural_batch` 的 chapters 里 `secs`/`quotes` 恒为空数组，且 `GM.render(d)` **漏传 ctx**，`_chapter_html` 拿不到章节详情 | 87 本 mindmap.html「共 0 个小节 · 0 条要点 · 0 句原句摘录」 |
| 书有页面但首页没卡片 | `produce_all` 只往 `reading-notes/books/<slug>/` 写文件，**从不动 index.html**；首页两张卡片墙各有自己的生成器（`preread-card` 注释块 / `gen_jingdu_panel.py`），新书一个都没挂 | 首页 98 张通读卡 vs 站内 335 本；94 张精读卡 vs 337 本 |

为什么会「打补丁打不完」：上一轮改的是 `overview_gen/build_overview.py`（有完整章节导读的那条线）、`gen_mindmap.py`（站点仓）、以及线上已发布页面，**但批量生产实际跑的是 `produce_all.py` 里的另一套模板**。改的和跑的不是同一份，于是每次重跑都把页面刷回简版。

## What Changes

- **`produce_all.py` 新增 `chapter_blocks(chs, bms)`**：章节数据唯一装配口，输出「章 → 小节 → 要点 → 原句」。通读页与精读页都吃这一份，不再各算一遍。
  - 小节名固定为「读者划得最多的句子」（数据事实上就是按热门划线分组，不冒充 AI 归纳）
  - 要点文本写「划线 N 人」，原句放引文位，一行原文只出现一次
  - 某章无划线就留空，不造小节、不编要点
  - 不写 `role`/`gist`（无 LLM 不编「章功能」「本章一句话」）
- **`produce_all.render_overview`**：`<ol>` 平铺改为「章节导读」模块，直接调用站点同一份 `GM._chapter_html` 渲染折叠章节树；head 引入 `assets/css/mmx-guide.css`（与精读页共用的章节组件样式，不再页面内联第二套）。
- **`produce_all.render_mindmap`**：chapters 改用 `chapter_blocks` 的真实 `secs`/`quotes`/`pts`/`with_q`；`GM.render(d)` → `GM.render(d, ctx)`（关键修复，否则 `full` 恒空）；清掉结构化批次默认的 `role`/`gist`/`anchor` 重复文案。
- **`gen_mindmap._chapter_html`**（合入站点仓与引擎副本）：`role`/`gist` 为空时整段不输出，避免页面留一排空 span 冒充内容。
- **`reading_note_spec.py`**：`_RENDER_FALLBACKS` 增加 `读者划得最多的句子` / `热门划线` / `热门划线原句`；新增 `_COUNT_TEXT_RE` 排除「划线 12128 人」。否则凡章名是「第二章」这类纯序号的书，每章都会被派生成同一句模板文案（本轮线上实测事故）。
- **新增 `rebuild_overview.py` / `rebuild_mindmap.py`**：存量回填工具，按线上页面大小筛出简版/空壳，只重建对应单页，不碰其他文件。
- **新增 `link_index.py`**：把已产出的书增量挂到首页两张卡片墙，已有 slug 跳过，幂等。
- **`publish_all.py`**：新增 `--only` / `--no-json` / `--msg`，支持只发布指定页面并自定义提交信息。

## 存量回填结果

- 通读页：218 本重建并发布（commit `c45ba0b07a`），335 本中 330 本已有「章节导读」，剩 5 本缺 bookId/章节数据
- 精读页：59 本重建并发布（commit `980a58b182`）
- 首页：补 220 张通读卡 + 221 张精读卡（commit `d88caa227e`），98→318 张 / 94→315 个可点入口

## 已知边界

- 《大明王朝1566》这类书平台目录只有「第一章/第二章」，无真实章名可派生，页面显示「第2章」兜底。要真标题必须接 AI 大纲（LLM），当前数据源（`/book/chapterinfo` + `/book/bestbookmarks`）不具备。
- 5 本仍无章节导读（`baikal-qingyouji` / `elephant-qingyouji` / `serbia-qingyouji` / `local-zhi-ye-gui-hua-niao-shu` / `shi-shi`），缺 `data/mindmap/<slug>.json` 里的 bookId 映射。
- 首页 172KB → 509KB，卡片一次性补齐的代价；后续若要减重，应改为从 JSON 按需渲染而非继续堆静态卡。

## 第二轮（同日）：空壳精读页 + 末位挂卡

第一轮修的是「有数据但没渲染」，这一轮处理「数据本身没被取到」：

| 现象 | 根因 |
|------|------|
| 35 本精读页点开「共 0 个小节 · 0 条要点 · 0 句原句摘录」 | 其中 19 本是轻游记，平台目录只有 封面/版权信息/正文，清洗后剩 1 章，被「≥2 章」判据整本跳过；页面停在老空壳 |
| 5 本 0 要点 | 这些书在微信读书上没有任何公开热门划线（`bestbookmarks` 返回空），硬产就只能是一排 0 |
| 首页仍差 20 / 23 张卡 | 上一轮只对「本地已有页面」的书挂卡，游记和仅精读页的书没覆盖 |

对应改动见 `tasks.md` 第 7 节。核心是把「渲染口径」和「产出判据」一起改：

- 空章 → 静态一行（不显示 0 条），全书无划线 → 页面顶部说明
- 产出判据 → 「≥1 章 且 热门划线 ≥1」，单篇书放行；无划线书仍不自动产（避免空壳）
- 单章书的「正文」→ 书名
