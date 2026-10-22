# 章节导航与「部分阅读」进度样式（硬规范）

用户 2026-10-19 决定：章节导读要「照这个样式来」——卡片分组、点章节下滑展开；**部分阅读的章展开后要能看到整章结构与读到哪一节，并且一眼认出来**。本文件是唯一权威实现，任何 Agent 产出笔记／全书视角都按此渲染，不自造变体。

## 1. 结构

```
.toc-part            一个部（或一级分组）一张卡
  .part-label        部名 + 章号区间
  details.ch-item    一章一行，默认折叠
    summary
      .ch-no         章号（第18章）
      .ch-t          章标题
      .badge[data-s] 状态徽标：read=整章 / reading=部分阅读 / unread=未读
      .caret         折叠箭头 ›
    .ch-body         展开体
      p              1–2 句导读（只写已读范围内能确认的）
      .ch-prog-cap   部分阅读才有：官方目录 共 N 节 · 已读 M 节，停在「X」
      ol.ch-secs.ch-prog  部分阅读才有：小节清单 + 已读高亮
      p.ch-prog-note 下次从哪接着读（可选）
      .ch-src        导读依据
```

零 JS，`<details>` 原生折叠；XHTML 友好，EPUB 兼容。

## 2. 部分阅读章的小节进度清单

**必做**：只要一章标了「部分阅读」，展开体就必须列出该章官方目录的**全部**小节，并标出读到哪一节。只写「读到某某节」而不给全章结构，等于让人无法判断还剩多少，不合格。

```html
<p class="ch-prog-cap"><span class="cap-k">官方目录</span><span>共 7 节 · 已读 2 节，停在「理论与比喻」</span></p>
<ol class="ch-secs ch-prog">
<li class="is-done"><span class="sec-t">引言</span><span class="sec-tag">已读</span></li>
<li class="is-done is-stop"><span class="sec-t">理论与比喻</span><span class="sec-tag">停在这里</span></li>
<li class="is-todo"><span class="sec-t">反全球化的出现</span></li>
<li class="is-todo"><span class="sec-t">未来场景1：重启全球化</span></li>
</ol>
```

三段语义，不许混用：

| class | 含义 | 视觉 |
| --- | --- | --- |
| `is-done` | 有证据确认读过 | 深绿底 `#244b40` + 米白字加粗，赭色圆点，右侧「已读」籤 |
| `is-done is-stop` | 确认停止在这里（最后一个读到的） | 同上 + 赭色 `#bf8247` 内描边 + 光晕，籤文案「停在这里」 |
| `is-todo` | 未读 | 灰字 `#a9a29a`，虚线圈点，不加籤、不写任何内容判断 |

规则：

- **已读判定只认证据**：日期笔记里写明实际阅读／略读的小节、或有内容访问依据的阅读器实测范围；不得凭进度百分比反推小节。后续允许跳读，读到第 N 节不证明前面各节已读，跳过的小节不得回填为已读。
- `停在这里` **有且只有一个**，必须是确认的最后一个小节；`ch-prog-cap` 的「已读 M 节」必须等于 `is-done` 的条数。
- 未读小节**只放标题**，不写概括、不写「大概讲的是」——标题本身来自官方目录，不是内容结论。
- 章标题／小节标题一律照抄官方目录，不改写、不补编号、不加分析性小标题。
- 多场跨日阅读同一章时，`read` 取并集，`停在这里` 取最近一次确认的停止处。

### 后续选择性覆盖（2026-10-19）

- 保留官方目录全部小节和现有 `read / reading / unread`；有略读、跳过或未读空缺的章使用 `reading`／「部分阅读」，不因浏览到章末改为整章。全未读章保持 `unread`；选择性读到书末也不等于全书完整读完。
- 复用日期笔记“实际覆盖”、`ch-prog-note` 与 `.ch-src`，按真实标题或已核实段落分别写明完整阅读、选择性略读、跳过和停止处；跳过必要时附短理由。只有略读实际接触的内容才可写导读，跳过与未读内容不写结论；不新增状态枚举或改色。
- 实际略读的小节可用 `is-done` 表示有接触证据，但必须在覆盖说明逐项标“选择性略读”，并将该节普通 `sec-tag` 写作「略读」；若兼为停止处，保留「停在这里」，在覆盖说明注明略读。计数仍等于高亮条数，包含略读时写“已读 M 节（含略读 K 节）”，不暗示完整阅读。
- 跳过的小节保持 `is-todo`、仅列官方标题、不高亮，跳过标记与必要理由放在既有实际覆盖／`ch-prog-note` 中，和“尚未读到”分开说明。唯一 `停在这里` 标记落在最后实际阅读或略读的小节，正文另记后续跳过范围及准确下一位置，不能把跳过伪装成已读停止处。
- **第一章不可跳过（2026-10-19 用户补充）**：任何书的第一章都必须有实际接触，不能整章留空或标「跳过」；长书择章起读时，第一章也须纳入。第一章低收益可以略读，按 `skim` 渲染成 `is-done` + 「略读」籤并计入「已读 M 节（含略读 K 节）」，但不写「跳过」，也不冒称整章完整读完；其后小节未读仍 `is-todo`。生成器侧：`secs` 首节所在章若 `read`/`skim` 均为空即为违规输出，须先补第一章实读再发布。
- 以上仅用于今后输出，不回写旧笔记、既有发布物或历史记录；不改变官方目录来源、计数与唯一停止标记要求。

## 3. 数据来源

小节清单必须来自AI读书官方目录，不手抄、不凭记忆：

```bash
python toc_fetch.py            # 输出 data/toc.json、data/toc-flat.json
```

`data/toc-flat.json` 形如 `{"第18章 全球化的死与生": ["引言", "理论与比喻", …]}`。抓取需要有效登录态；`chapterInfos` 接口已下线，只能从阅读器目录面板取。

## 4. CSS（原样复制，不要改色）

```css
/* 官方目录小节清单：已读（深底）/ 停在这里（赭边）/ 未读（置灰）三段对比 */
.ch-secs{margin:.4em 0 .45em;padding:0;list-style:none;color:#5c574c;font-size:.78rem;line-height:1.65}
.ch-secs li{display:flex;gap:8px;align-items:baseline;padding:3px 9px;margin:.15em 0;border:1px solid transparent;border-radius:7px}
.ch-secs li::before{content:"";width:7px;height:7px;border-radius:50%;border:1.5px solid #cfc7b6;flex:none}
.ch-secs .sec-t{flex:1;min-width:0}
.ch-secs .sec-tag{flex:none;font-size:10.5px;font-weight:700;border-radius:5px;padding:0 6px;line-height:1.7}
.ch-secs li.is-done{background:#244b40;border-color:#244b40;color:#f6f1e8;font-weight:600}
.ch-secs li.is-done::before{background:#e8c48a;border-color:#e8c48a}
.ch-secs li.is-done .sec-tag{background:#e8c48a;color:#3a2c14}
.ch-secs li.is-stop{background:#2d5a4c;border-color:#bf8247;box-shadow:inset 0 0 0 1px #bf8247}
.ch-secs li.is-stop::before{background:#bf8247;border-color:#bf8247;box-shadow:0 0 0 3px rgba(191,130,71,.22)}
.ch-secs li.is-stop .sec-tag{background:#bf8247;color:#fffdf8}
.ch-secs li.is-todo{color:#a9a29a}
.ch-secs li.is-todo::before{border-style:dashed}
.ch-prog-cap{display:flex;align-items:baseline;gap:8px;margin:.55em 0 .2em;padding:3px 0 3px 9px;border-left:3px solid #bf8247;font-size:11.5px;font-weight:700;color:#8a5a24;line-height:1.6}
.ch-prog-cap .cap-k{flex:none;background:#f6e8d5;border:1px solid #e6cfae;border-radius:5px;padding:0 6px;font-size:10.5px;letter-spacing:.04em}
.ch-prog-note{color:#8a8f99;font-size:11.5px;margin:.1em 0 .3em}
.ch-secs:not(.ch-prog) li{padding:1px 9px;margin:.05em 0}
```

未读章的纯目录清单用同一套 `.ch-secs`，`li` 不带 class 即为置灰态，配 `.ch-cap` 一句「官方目录小节（先看结构，未读不出结论）：」。

## 5. 生成器接入

`notes_gen._render_chapter_guides` 的 `chapter_guides` 支持两种值：

```python
# 整章亲读
"第19章 全球化背景下的资产负债表危机": "整章导读……"

# 部分阅读：自动渲染小节进度清单
"第18章 全球化的死与生": {
    "guide": "只读到「引言」与「理论与比喻」……",
    "status": "reading",
    "secs": ["引言", "理论与比喻", "反全球化的出现", "未来场景1：重启全球化",
             "未来场景2：反全球化", "未来场景3：地区化与“大陆岛”", "结语"],
    "read": ["引言", "理论与比喻"],
    "read_upto": "理论与比喻",
    "note": "未读五节不写结论。",
}
```

`secs` 从 `data/toc-flat.json` 取，`read` 只写有证据（完整读过）的小节；**跳读时不要为了凑连续区间把前面各节填进 `read`**，未确认的一律不填。

略读用可选的 `skim` 传，渲染成 `is-done` + 籤「略读」，计数写「已读 M 节（含略读 K 节）」：

```python
"第21章 改变关税规则，应对中美贸易战": {
    "guide": "只读到「从商品关税转为货币关税」……",
    "status": "reading",
    "secs": ["引言", "从商品关税转为货币关税", "货币关税的机制",
             "把商品国竞争变为货币国竞争", "结语"],
    "read": ["从商品关税转为货币关税"],   # 不含「引言」：无单独阅读证据
    "skim": ["货币关税的机制"],
    "read_upto": "从商品关税转为货币关税",
    "note": "「引言」未单独确认阅读，按未读列示；跳过项的理由写这里。",
}
```

`skim` 与 `read` 互斥，同一小节只算一次；`is-done` 总数 = `已读 M 节`；跳过与未读的小节都留 `is-todo`，只列官方标题，理由写 `note`，不回填成已读。
