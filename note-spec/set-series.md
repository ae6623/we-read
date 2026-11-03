# 合集拆书成系列 · 流程与卡片规则

> 读者：接手的实现者（本机 / 云端 / 任何 agent）。
> 目标：把微信读书里「一个套装 = 一本合集」的东西，拆成**单册页 + 系列页 + 首页书卡**三件套，
> 且新套装接进来时**不用手改 HTML**。
> 改规则先改这里，再改对应脚本；不要只改一处、留下一处私货。

版本：1.6.0（2026-11-03）　对应脚本：`tools/build_set_series.py`、`tools/sync_set_cards.py`

---

## 一、为什么要拆

微信读书对**套装合集**只给一份目录，不给 AI 大纲；但合集目录的一级标题恰好就是各分册书名。

于是：按分册名逐本搜 bookId → 单册都能拿到官方大纲（章 / 小节 / 要点 / 原句）→
单册页 + 系列页 + 首页书卡。**合集本身不建页**，只作拆册的入口与书目来源。

---

## 二、真源与产物

| 环节 | 真源 | 产物 |
|---|---|---|
| 套装登记 | `assets/data/series-sets.json`（`sets[]`：`slug / name / sub / desc / src_slug / src_title / total / with_outline / page`） | — |
| 合集 bookId | `assets/data/hero.json` 的 `ids.<src_slug>` | — |
| 分册清单 | 合集 `/book/chapterinfo` 的 level1 标题（过噪声） | 内存 |
| 单册匹配 | `/store/search`（书名归一化后 score ≥ 60） | bookId |
| 单册大纲 | `/web/book/outline` | `reading-notes/books/<slug>/outline.html` + `assets/data/outline/<slug>.json` + `book_outline` 表 |
| 系列页 | 上面两步的结果 | `reading-notes/series/<set>/index.html` |
| 首页书卡 | 系列页的分册清单 | `index.html` 里 `<section class="set-group" data-units="<set>">` |
| 封面 | 单册详情页的 `cover` 字段 | `assets/covers/<slug>.jpg` |

**单一真源原则**：卡片只从「系列页的分册清单」重建，不从旧卡片反推。
想改卡片内容，先改系列页（或重跑拆册），再跑同步。

---

## 三、流程（五步）

```bash
# 0. 看现有套装
python tools/build_set_series.py --list

# 1. 登记新套装：改 assets/data/series-sets.json 的 sets[]
#    { "slug": "x", "name": "显示名", "sub": "作者 · N 册",
#      "desc": "一句话", "src_slug": "合集slug", "src_title": "合集全名",
#      "total": 0, "with_outline": 0, "page": "reading-notes/series/x/index.html" }

# 2. 干跑：只列分册名与匹配结果，不写文件
python tools/build_set_series.py --set x --dry

# 3. 正式拆：抓大纲、写单册页、写系列页、回写 total/with_outline
python tools/build_set_series.py --set x

# 4. 补封面（见第五节）后，同步首页卡片
python tools/sync_set_cards.py --check     # 先看差异
python tools/sync_set_cards.py             # 写入 index.html

# 5. 本地验收
python3 -m http.server 8899 --bind 127.0.0.1
# 打开 http://127.0.0.1:8899/index.html#xiLie
```

拆册脚本可以 `--all` 全量重跑：已存在且含 `<details class="ch">` 的单册页会**复用**，不重抓。

---

## 四、卡片：能自动追加

**能。** `tools/sync_set_cards.py` 是幂等的，三种情况都覆盖：

| 情况 | 行为 |
|---|---|
| 组已存在、册数变了 | 整组 `.set-units-grid` 重建，组名与「N 册」一并对齐 |
| 组不存在（新套装） | 整组追加到 `.set-groups` 末尾，自动带上组头 |
| 只想补新册 | `--append-only`：保留已有卡，只追加清单里没有的 slug |

```bash
python tools/sync_set_cards.py --check                 # 只报差异，不写
python tools/sync_set_cards.py --set oracle-wwii       # 单组
python tools/sync_set_cards.py --append-only           # 全部套装，只补新册
```

**不要手写卡片。** 手写容易漏册、串封面、链接指错，而且下次同步就被覆盖。

### 卡片结构（生成结果，勿改格式）

```html
<section class="set-group" data-units="oracle-wwii">
  <div class="set-group-head">
    <span class="set-group-name">甲骨文·二战史</span>
    <span class="set-group-count">6 册</span>
  </div>
  <div class="set-units-grid">
    <article class="archive-card unit-card" data-slug="<slug>" data-search="<书名> <作者>">
      <div class="card-top"><time datetime="2026-11-03">11.03</time></div>
      <h3><a class="card-title-link" href="<链接>">《<书名>》</a></h3>
      <div class="card-foot"><span class="card-author"><作者></span><span class="card-meta"><章数|类型></span></div>
    </article>
    …
  </div>
</section>
```

- `data-slug` **必须**等于封面文件名 `assets/covers/<slug>.jpg` 的主干，否则封面永远加载不出来。
- `data-slug` 同时是「有整书笔记就先跳笔记」的判据，见下条。
- `data-search` 是站内搜索用的，书名 + 作者，末尾不要留空格。

### 单册卡去向（优先级不能反）

1. `reading-notes/books/<slug>/combined.html` —— 整书笔记
2. `reading-notes/books/<slug>/overview.html` —— 通读页
3. `reading-notes/books/<slug>/outline.html` —— AI 章节大纲
4. `https://weread.qq.com/book-detail?...` —— 原站（兜底，页面里要能看出来是原站）

先跳原站等于把读者扔出站外，回来还得自己找。这条被明确提过，不要改。
`card-meta` 同步标注：`N 章 / M 条`（有大纲）或 `AI 笔记` / `原站`；`0 章 / 0 条` 一律不显示。

---

## 五、封面规则

| 项 | 规则 |
|---|---|
| 文件名 | `assets/covers/<slug>.jpg`，与卡片的 `data-slug` 一一对应 |
| 版式 | 竖版 30:43（`aspect-ratio:30/43`，容器 `object-fit:cover`） |
| 尺寸 | 抓微信读书 `t9_` 大图（约 428×616）；官方没有更大图时保留 `t6_`（250×360） |
| 体积 | 宽 >428 先压到 428；`JPEG quality 80, progressive, optimize` |
| 抓取 | 书籍详情页正则 `"cover":"https:\u002F\u002F…"`，把 `/s_` 换成 `/t9_` 试大图 |
| 缺图 | **必须**有兜底素封（见下），不要留白、不要拿别的书的封面临时顶 |

**兜底素封**：`tools/gen_fallback.py` 现成可用，深色渐变底 + 衬线书名居中 + 作者 + 站点小字：

```bash
python tools/gen_fallback.py <slug> "<书名>" "<作者>" [oracle|qingyou|tianya|default] [kicker首行小字]
# 已存在同名封面会跳过；确认要覆盖加 --force
```

输出 428×616（30:43），与真封面同尺寸同版式，混排看不出是生成的。

**禁止**：同一张图多本复用（历史上 24 本共用「韭菜的自我修养」封面，属于事故）。
`md5sum assets/covers/*.jpg | cut -d' ' -f1 | sort | uniq -d` 可以一键查重。

---

## 六、硬规则（违反过，被回退过）

1. **slug 规则**：汉字转全拼、数字保留（`南京1937` → `nan-jing-1937`）、标点转 `-`、
   总长 ≤ 64 字符。数字不能被 pypinyin 的 `errors="ignore"` 吃掉。
2. **噪声章节过滤**：封面 / 版权信息 / 总目录 / 目录 / 序言 / 前言 / 后记 / 译后记 /
   附录 / 出版说明 / 献词 / 题记 / 扉页 / 彩插 / 插图 / 地图 / 大事记 / 注释 / 参考文献 /
   索引 / 致谢 / 导读 / 中文版序 / 自序 / 推荐序 / 本书获誉 / 关于作者 —— 都不算分册。
3. **匹配阈值**：书名归一化（去书名号、括号、版本词、标点）后 `score ≥ 60` 才认；
   宁可少认（该册无大纲、卡片跳原站），不许认错（张冠李戴比缺页严重）。
4. **不编造**：分册名来自合集目录，章数/要点来自官方大纲。抓不到就标「无大纲」，
   不要用相似书的书目填空。
5. **作者解析**：系列页里写作 `作者：X　·　N 章 / M 条`，分隔符是**空格·空格**；
   作者名自带 `·`（约翰·朱利叶斯·诺里奇）不能当分隔符切。
6. **改前端资源必须升 `?v=`**：`index.html` 里 `home-theme.css?v=` / `home-page*.js?v=` 等，
   否则 Pages CDN 命中旧文件，改了等于没改。

---

## 七、验收清单

跑完必查，缺一条不算完成：

- [ ] `python tools/sync_set_cards.py --check` 输出 `变更 0 个组`
- [ ] 系列页册数 = 首页组头「N 册」= 组内 `article` 数
- [ ] 每张卡的 `data-slug` 都有对应 `assets/covers/<slug>.jpg`（脚本会列缺封面清单）
- [ ] 卡片链接按「笔记 > 通读 > 大纲 > 原站」命中，没有指错书
- [ ] 封面无重复：`md5sum assets/covers/*.jpg | cut -d' ' -f1 | sort | uniq -d` 为空
- [ ] 首页 `#xiLie` 在 1440 / 1024 / 390 三个宽度下：一排一/二/三都能切，封面都在
- [ ] 组很多时滚动，组头吸顶正常（`.set-group-head` 的 `position:sticky`）
- [ ] 空组（0 卡）被隐藏，不留一个只有标题的框

---

## 八、常见坑

| 现象 | 原因 | 处理 |
|---|---|---|
| 卡片全是一个样、只有书名 | 封面没抓到 / `has-img` 没挂上 | 查 `assets/covers/<slug>.jpg` 是否存在；`home-card.js` 靠 `naturalWidth>0` 挂 `has-img` |
| 整组只剩第一张卡 | 从书架搬卡时残留瀑布流的 `position:absolute` 与 `data-pg` | `homepage-reading.js` 搬卡时已清，别删那段 |
| 一排三只剩文字块 | `.card-cover{display:none}` 的窄卡规则扩到了宽屏 | 该规则必须在 `@media(max-width:680px)` 内 |
| 平板/PC 点「一排一」没反应 | 网格写死 `auto-fill 240px` | `.set-units-grid` 在 `min-width:681px` 下跟随 `html[data-cols]` |
| 组头不吸顶 | 祖辈有 `overflow:hidden/auto` | 吸顶元素的所有祖辈都不能截断溢出 |
| 推送超时 | 仓库大 + github.com:443 不稳 | `git config http.postBuffer 104857600`；重试；仍不行用 Git Data API 提交 |

---

## 九、和别的规范的关系

- 单册页内部结构（大纲 / 通读 / 精读 / 3 问 / 答案口径）→ 见 `note-spec/README.md`
- 详情页壳（`reader.js` / 分享 / 主题）→ 见 `note-spec/README.md` 第 16–19 批
- 本文件只管「套装 → 单册 → 系列页 → 首页卡」这一条链
