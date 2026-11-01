## 背景

同一站点存在**两条笔记生产链**：

| | 老链 | 新链（`produce_all.py`） |
|---|---|---|
| 通读页 | `overview_gen.build_overview.build()` —— 14 个模块，含「章节导读」折叠树 | `render_overview()` 手写 5 段模板，无章节导读 |
| 精读页 | `gen_mindmap.refine()` + LLM | `gen_mindmap.structural_batch()`（无 LLM 结构型） |
| 章节数据 | `book_outline` 表（章→节→要点→原句） | `/book/chapterinfo` + `/book/bestbookmarks` |
| 首页 | 手工/一次性生成卡片 | 完全不碰 |

上一轮的修复改在老链上，实际批量跑的是新链。这是「越修越丢」的机制性原因。

## 决策

### D1 章节数据只装配一次：`chapter_blocks()`

通读页与精读页此前各写一套章节循环，导致一边改了另一边不动。改为单一函数输出统一结构：

```python
{"no", "title", "role"(""), "gist"(""), "concepts": [],
 "anchor"(""), "quotes": [...], "secs": [{"h", "points": [{"text", "quotes"}]}],
 "pts", "with_q"}
```

`role`/`gist`/`anchor` 全部留空——当前数据源里没有「章的功能」「本章一句话」这类判断，编出来就是假内容。渲染器对空值不输出（见 D3）。

### D2 渲染复用站点同一份 `_chapter_html`

`produce_all` 不自己拼章节 HTML，直接调 `GM._chapter_html(c, full)`。样式来自 `assets/css/mmx-guide.css`（该文件全部 `mmx-` 前缀，无全局选择器，可安全引入到任何页面）。

这样「通读页的章节导读」与「精读页的章节树」在 DOM 与样式上完全同构，改一处两页同时生效。

### D3 空值不渲染，而不是渲染空壳

`_chapter_html` 原来无条件输出 `<span class="mmx-role">%s</span>` 与 `<p class="mmx-gist">%s</p>`。字段为空时页面上就是一排空 span 和空段落——看起来像内容，实际是噪音。改为空则整段不输出。

### D4 章名派生必须排除模板文案

`chapter_title()` 的派生链是「首小节名 → 首要点 → 锚点原句 → 第N章」。`chapter_blocks` 造出来的小节名是全站统一模板（「读者划得最多的句子」），被当作章名后：

```
2  读者划得最多的句子        ← 第 2 章
3  读者划得最多的句子        ← 第 3 章
```

因此在 `_RENDER_FALLBACKS` 中排除这三类模板文案，并新增 `_COUNT_TEXT_RE` 排除「划线 12128 人」。排除后落到第 4 级兜底「第N章」——信息量低但不撒谎。

### D5 存量回填只按「页面形态」筛，不按时间

不能靠 mtime 判断哪些页要重建（镜像里 327 个目录混杂了历史产物）。用线上 tree 的 `size` 作为判据：

- `overview.html < 20KB` → 简版，重建
- `mindmap.html < 20KB` → 空壳，重建

重建脚本只写单个文件，不碰 `outline.html` / `quiz.html`，避免把已有的完整精读页覆盖成结构型简版。

### D6 挂卡幂等，不整墙重写

`gen_jingdu_panel.py` 的做法是「扫本地 → 整块替换 grid」，本地镜像不全时会把线上卡片冲掉。`link_index.py` 改为增量：只对 `<!-- preread-card:<slug> -->` 或 mindmap 链接缺失的书插入卡片，已有的跳过，跑第二遍 diff 为空。

## 权衡

- **首页体积**：318 + 315 张卡让 index.html 从 172KB 涨到 509KB。完整性优先，后续若要减重应改为 JSON 按需渲染。
- **章节内容深度**：新链没有 AI 大纲，章节展开只有「划线原文」，不及老链的「小节 → 要点 → 原句」。这是数据源差异，不是渲染问题；已在页面文案上标注「原文逐字取自本书热门划线，一条未改」，不冒充 AI 归纳。
