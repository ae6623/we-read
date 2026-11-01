# design — add-ai-lead-merged-v3

## 核心决策：AI领读内嵌原生大纲树，而非继续重渲染

v2 的 `merged_guide` 走 `parse_outline → _render_full_guide_inner` 重渲染（mmx-cn/mmx-sec 折叠树）。用户反馈大纲页原生样式更好看，且重渲染引入过「未读」徽标、分组副标题等大纲页没有的元素。

outline.html 原生结构自包含且稳定：

```html
<div class="toc"><b>章节目录</b><ul>…锚点列表…</ul></div>
<details class="ch" id="chN"><summary>章名</summary>
  <div class="sec"><h4>小节</h4>
    <ul class="point"><li><b>要点</b><ul class="quote"><li>原句</li></ul></li></ul>
  </div>…
</details>
```

其样式全部集中在 `reading-outline.css`（36 行，含 `.toc/.ch/.sec/.point/.quote` 全套 + `:root` 变量）。因此 v3 选择**搬运而非重绘**：

- `_extract_outline_tree()` 用括号配对抽 toc div 与全部顶层 `details.ch`（沿用合并页脚本已验证的配对算法，避免 `</details>` 嵌套歧义）。
- 内嵌片段原样保留 `id="chN"`，toc 锚点跳转在合并页内继续可用。
- `reading-outline.css` 内联进合并页并置于外壳样式**之前**：其 `body/.page` 页面级规则会被合并页外壳样式（在后）覆盖，树样式无冲突、完整保留。

## 回退链设计

```
_m_merged_guide:
  c.outline_tree 非空 → 内嵌原生树（v3，首选）
  否则               → _render_full_guide_inner（v2 兜底，结构化重渲染）

quiz 答案:
  weread_store.load_quiz（SQLite/JSON 库）
  → 空 则 books.MANUAL_QUIZ_ANSWERS[title] or [slug]（LLM 回填，本 change）
  → 仍空 则不输出答案块（现状）
```

`MANUAL_QUIZ_ANSWERS` 按 slug 为键（yi-sheng 不在 `BOOKS`，`_load_aiqa_data` 只能拿到 slug），条目 `q` 字段必须与 `reflect_questions_html` 产出的 3 问原文一致，`_quiz_answers_html` 靠问题文本配对。

## 兼容性

- legacy `build()` 签名与输出零改动；`outline_html` 仅 `build_modular` 接收，`auto.generate()` 中以 `build_fn is build_modular` 区分传参。
- `_extract_outline_tree` 抽不到内容时返回 `""`，自然走 v2 兜底，不抛错。
- 合并页脚本为演示层，不影响站点生成链路。
