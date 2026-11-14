# we-read 书卡 → IMA 知识库：方案与落地记录

> 目标：把整站 533 本书的「书卡」（结构化摘要）搬进 IMA 知识库 `we-read`，
> 可检索、可问答、可分主题对比，且站点更新后能一条命令增量同步。
> 执行时间：2026-11-14 凌晨｜知识库 ID：`ima_kb_Z69gwh6y`

---

## 一、结构设计

```
IMA 知识库：we-read
├── 00-字段说明.md                 ← 字段含义 + 提问范例（给 AI 检索时定锚）
├── 00-总索引.md                   ← 导航页：类目 + 计数 + 每类 4 本示例（刻意做小）
└── 📁 书卡/
    ├── 文学·1984.md
    ├── 经济理财·证券分析：投资者的圣经.md
    ├── 计算机·深入剖析 Apache Dubbo 核心技术与实战.md
    ├── 历史·王的归程——阿富汗战记(1839-1842).md
    └── …（共 512 张）
```

**命名规则：`<一级类目>·<书名>.md`**

选这个而不是多级文件夹，原因很实际：IMA 的 MCP 接口只暴露 `add_knowledge(folder_id)`，
**没有创建文件夹的接口**。用「类目前缀」换来三个好处：

1. 按文件名排序时天然按类目聚拢，视觉效果等于文件夹；
2. 检索命中时，文件名本身带类目，回答里能直接引用；
3. 移动端列表扁平，找书比点两层文件夹快。

> 想要真多级目录也能做：你在 IMA App 里建好「经济理财 / 文学 / …」子文件夹，
> 把 `folder_id` 填进 `ima/folders.json`（脚本已预留 `--folder-map` 解析位），
> 重跑上传即归位。MCP 不提供 create_folder，这一步只能手动建。

---

## 二、数据流

```
reading-notes/books/<slug>/combined-data.html    站点结构化卡片（最多 11 个模块）
        │
        │  scripts/ima/ima_export.py
        │   · 按 data-key 切模块：oneline / views / deepread / top10 /
        │     coreask / aiask / higher / verify / thennow / merged_guide
        │   · 去 <style>、去「本页由 AI 生成…」这类每张卡重复的元说明
        │   · 短行（≤14 字）识别为 ###小标题，长行合并为段落，列表原样保留
        │   · merged_guide 只取章节目录骨架（章名 + 小节数/要点数），
        │     不搬 70KB 的逐章原文 —— 书卡是索引，不是全文复制
        ▼
ima/cards/<类目>·<书名>.md        中位 5.2KB / 最大 10.3KB / 最小 1.5KB
        │
        │  scripts/ima/ima_upload.py
        │   · create_media → COS 预签名 PUT → add_knowledge(folder=书卡)
        │   · 失败重试 3 次（指数退避），并发 4
        ▼
IMA 知识库 we-read（写入即自动解析，parse_progress 100%）
```

---

## 三、每张书卡长什么样

```markdown
# 《1984》

![《1984》封面](https://cdn.js-dev.cn/assets/covers/1984.jpg)

> 极权不是让你说假话，而是接管「判定何为真」的权力。

| 项 | 值 |
|---|---|
| bookId | `3300012345` |
| 类目 | 文学 / 小说 |
| slug | `1984` |
| 卡片状态 | ok（9 个标准模块：oneline, views, …） |
| 最近更新 | 2026-11-13 |
| 站点原文 | …/1984/combined.html |

## 01 知识导图          ← Mermaid mindmap（Google 配色，矩形根节点，最多 12 章）
## 02 核心观点与结构脉络
## 03 精读判断
## 04 原文金句
## 05 核心追问
## 06 AI 问书
## 07 更高维度
## 08 阅读时要验证
## 09 当年与今天
## 10 章节目录          ← 四层：章 → 小节 → 要点 → 原句
```

**固定 10 节**（缺哪节＝这本书没有该模块，多为未读、大纲接口返空）。
数字前缀是为了让 IMA 的回答能引用「第 07 节」这种锚点。

### 3.1 顶部表格的字段口径

| 字段 | 来源 | 用途 |
|---|---|---|
| `bookId` | 微信读书书籍 ID，来自云端 `/api/books`（标题归一 + 拼音兜底匹配） | 与微信读书原书对应；339/543 命中，其余显示 `—` |
| `类目` | `assets/data/book-cats.json` | 与站点权重同一套分类，检索时可按类目收敛 |
| `slug` | 站点目录名 | 拼站点链接、定位产物目录 |
| `卡片状态` | `assets/data/template-audit.json` | `ok/thin/fixable/dump/empty`，thin 以下说明内容不全 |

### 3.2 封面（标题下第一行）

`![《书名》封面](https://cdn.js-dev.cn/assets/covers/<slug>.jpg)`

- 图源就是站点首页/详情页用的那一份（同名同路径），不是另外生成的占位图；
- 域名必须用 **cdn.js-dev.cn**（`assets/js/reader.js` 里的 `coverSrc()` 同款），
  `reader.js-dev.cn/assets/covers/...` 虽然也能通、内容一致，但走的是站点主域，
  换成对象存储域名更稳；
- 索引表 `assets/data/covers.json`（`scripts/ima/build_covers.py` 生成，539/543 命中），
  导出时只读表、不逐本探测；
- **只能用 Markdown 图片语法**。实测 `<p align="center"><img ...></p>` 会让 IMA 的
  md 解析器直接卡在 `media_state=1`（内容永远为空），整条书卡等于没入库；
- IMA 会把图抓下来并对封面做 OCR，把识别到的书名/作者塞进 alt —— 属正常现象，
  不影响显示。

### 3.3 知识导图（01 节）

IMA 的 MCP 没有「生成导图」接口，所以导图由我们在导出阶段用
**站点已经编译好的篇章结构**本地生成，两种表达同时存在：

- `mermaid mindmap` 代码块：支持 Mermaid 的阅读器直接出图；
- 章节树（最后一节）承担同样的信息，纯文本、可检索。

样式约定（2026-11-14 定）：

- 根节点用矩形 `root["《书名》"]`，不用圆形 —— 圆形在小屏上像个气泡，边框还挤压文字；
- 配色取 Google 四色的浅色版：主蓝 `#4285F4` / 浅蓝 `#E8F0FE` / 浅绿 `#E6F4EA`，
  深蓝文字 `#174EA6`，连线灰 `#BDC1C6`；
- 必须把 `cScale0..11` 全部显式设色 —— 只设 `primaryColor` 时 mindmap 仍按分支
  索引取默认调色板，56 个分支会变成五颜六色的蜘蛛网；
- 章数超过 12 只画前 12 章，末尾挂「另 N 章见章节目录」，放射状布局放不下更多。

### 3.4 章节目录（最后一节）

四层缩进，递归取自 `merged_guide`（AI领读）的 DOM：

```
- **1 译者序**（3 小节 · 17 要点 · 11 原句）
  - 译者对《1984》的初识与翻译动机
    - 译者对《1984》的初识源于钱锺书先生的评论
    - 原句：钱锺书先生对奥威尔的评论：“他的政论、文评…久负当代盛名。”
```

旧版只写「共 N 个小节 · M 条要点」的统计，点进去是空的 —— 用户反馈
「章节目录缺子节点」就是指这个。现在每章最多展开 4 小节、每小节最多 3 条要点
+ 1 句代表原句，兼顾信息量与体积（中位 19KB）。

### 3.5 正文模块统一为父子两层（02–09 节，v6）

**唯一规则**：每个正文模块都只输出一种结构 —— `- **父节点**` 紧跟至少一条
`  - 子节点`。不允许再出现裸段落、`- **主题**：说明` 这种压成单行的写法，
或没有子节点的平铺列表。`render_section()` 的 `_emit()` 是所有模块唯一的出口，
读法与最后一节「章节目录」完全一致。

| DOM 块 | 父节点 | 子节点 |
|---|---|---|
| `blockquote + cite`（原文金句） | 出处章名（连续同出处合并） | 逐条原句 |
| `div.mmx-qa`（核心追问 / AI 问书） | 问句 | 回答；回答内按 `【标记】` / `存疑 ·` 再拆多条 |
| `li > b`（核心观点与结构脉络） | 粗体主题 | 余文按句拆 |
| `li`（阅读时要验证等纯文本） | `要点 N` 或识别出的「小标题：」 | 原文按句拆 |
| `p`（更高维度 / 当年与今天 / 精读判断） | `【书中主张】` / 段首小标题 / `要点 N` | 正文按句拆 |

`_split_sentences()` 按 `。！？；` 拆句，过短碎片（<14 字）并入前一条，
避免出现半截子节点；`_label_of()` 负责认出「小标题：」和「存疑 · / 取舍 ·」。

示例（注意 05 与 08 与 04 是同一套父子读法，08 不再是一行一条的平铺）：

```
## 02 核心观点与结构脉络

- **译序与极权现实**
  - 交代作品影响并展示大洋国监控、历史篡改与个体异化的统治日常。

## 04 原文金句

- **译者序**
  - 「钱锺书先生对奥威尔的评论……」

## 08 阅读时要验证

- **要点 1**
  - "新话"词典的设定应核对书中附录《新话的原则》原文，确认"削词=削思想"是书中明示机制。
- **译本差异**
  - 董乐山译本与各中译本对 Newspeak 术语译法不一，引用金句应注明译本。

## 09 当年与今天

- **要点 1**
  - 奥威尔写于1948年，当年能设想的监控是电屏幕+思想警察；
  - 他看不到算法与社交平台，但猜中了核心：当"过去可被随时改写"，个体就失去抵抗的锚。
```

**例外**：`oneline`（一句话主旨）是标题下的 `> 引用` 摘要，不是正文模块，
保持纯文本 —— 若也套两层列表，`render()` 取首行只会拿到「要点 1」，主旨会丢。
`svg` 段只在 `sections()` 里被解析，不进卡片正文。

版本演进：v5 按 DOM 语义分模块渲染，各模块样式不一致（02 压成单行、08 平铺、
09 还是整段裸文字），用户反馈「所有模块都应该是统一的样式」；v6 收敛为单一
`_emit()` 出口。`TEMPLATE_VER=imacard-v6`。

---

## 四、增量机制

`ima/manifest.json` 是唯一台账，每本书一条：

```json
"1984": {
  "title": "1984", "cat1": "文学", "cat2": "小说",
  "hash": "a1b2c3d4e5f6a7b8",          // sha1(TEMPLATE_VER + md 内容)
  "file": "ima/cards/文学·1984.md",
  "bytes": 13090, "modules": 9,
  "ima_media_id": "markdown_cls1_…",   // 上传成功才写
  "synced_at": "2026-11-14T02:40:11+08:00"
}
```

判定规则：

| 状态 | 条件 | 动作 |
|---|---|---|
| 新书 | manifest 里没有 | 写卡 + 入 pending |
| 内容变更 | hash 不同 | 重写卡 + 入 pending（覆盖同名） |
| 从未上传 | 有 hash 无 `ima_media_id` | 入 pending |
| 已同步 | hash 相同且有 `ima_media_id` | 跳过 |

### 4.1 日常同步：一条命令

```bash
cd /root/we-read-site
python3 scripts/ima/ima_sync.py            # 增量：导出 → 补传 → 刷索引
```

`ima_sync.py` 依次做三件事，任何一步失败即中止：

1. `ima_export.py`：按 `combined-data.html` 重算 hash，只把「新书 / 内容变了 /
   从没上传过」的写进 `pending.json`（约 2 分钟 / 全站）；
2. `ima_upload.py --replace --skip-existing --workers 2`：只传 pending，
   并跳过文件夹里已有同名文件（约 1.4s/本）；
3. 刷 `00-总索引.md` / `00-字段说明.md`（已存在则跳过，避免 REPLACE 空壳）。

### 4.2 新书产出 → 书卡同步（SOP）

**前置（最容易漏，2026-11-14 实测）**：云端 `compose` 只产
`mindmap / outline / overview / modules`，**不产 `combined-data.html`**，而 IMA 导出
完全依赖它 —— 11-14 新产的两本书线上 `combined-data.html` 都是 404。必须先跑合并页：

```bash
# compose 完成后单独跑合并页（只写引擎仓，不自动 publish）
curl -X POST -H "X-Agent-Name: workbuddy-cloud-luoyuJi" \
     -H "Content-Type: application/json" -d '{"slugs":"<slug>"}' \
     https://weread-cloud-probe.app.workbuddy.host/api/combine
# 进度：GET /api/combine/status
# 然后把 combined.html / combined-data.html 发布到站点仓，验收：
curl -s -o /dev/null -w "%{http_code}" \
     https://reader.js-dev.cn/reading-notes/books/<slug>/combined-data.html   # 必须 200
```

站点新增一本书的标准动作，按顺序做，不要跳：

| 步骤 | 动作 | 验收 |
|---|---|---|
| 1 | 云端 compose（outline / overview / mindmap / modules / publish） | 站点仓出现 `compose: <slug> 整书产物` 提交 |
| 2 | `/api/combine` 产出合并页并发布 | 线上 `combined-data.html` 返回 200 |
| 3 | `python3 scripts/ima/ima_sync.py --book <slug>` | 输出「增量：待上传 1 张」并上传成功 |
| 4 | `python3 scripts/ima/ima_check.py --strict` | ✅ 全部对齐（站点有卡、md 与入库记录都在） |
| 5 | `python3 scripts/ima/ima_verify.py --wait 20` | `media_state=2`；解析是异步慢队列，约 8 条 / 75s |
| 6 | 若出现「内容已删除」/ 空摘要 | 说明同条目曾被 REPLACE 破坏，见 4.3，删旧条目重传 |

**每产出一本书，第 3–4 步必做**；`ima_check.py --strict` 可直接挂 CI，站点有卡而
台账无记录就失败。漏同步不用逐本补：跑 `python3 scripts/ima/ima_sync.py`（不带
`--book`）会全量增量扫描，自动把缺的补上。模板升级走 `--full`。

> 归档书例外：`progress=0` 的书微信读书大纲接口返空，不排产、没有 combined-data，
> 自然也不会生成 md。默认模式下 `ima_check.py` 把它们列为 ⚠️ 提示；但 SOP 第 4 步
> 用的 `--strict` 会把所有「站点有卡、台账无记录」一并判失败，**需要按线上
> `combined-data.html` 是否返回 200 区分**：200 的是漏同步（必须补），404 的才是归档书
> 例外。2026-11-14 实测 28 本未跟踪里，14 本为真漏同步（`ima_sync.py` 已补齐）、
> 14 本为归档书。本地 sparse 只检出部分书，这一步必须联网判定，别靠本地文件是否存在。

### 4.3 三条硬规则（都是踩过的坑）

1. **禁用 `DUPLICATE_NAME_STRATEGY_REPLACE`**。实测：同名 REPLACE 后服务端把旧
   条目内容清空、新条目另立一条，列表里留下 `media_state=1 / parse_progress=0 /
   content 空` 的空壳 —— 在 App 里打开就是「当前内容已删除」。2026-11-14 全量
   重传一次，512 条里 328 条中招。现在上传固定 SAVE，需要覆盖时先在 App 删旧条目。
2. **上传前必须 `--skip-existing`**。SAVE 遇到同名会新建副本并给文件名加
   `_<时间戳>` 后缀，列表里会出现「书名」和「书名_26111」两条。
3. **台账记 `add_knowledge` 返回的 id，不是 `create_media` 的**。两者在服务端
   不是同一个对象；记错会让 `/api/status` 的核对数字对不上，也无法反查条目。

### 4.4 其它常用组合

```bash
python3 scripts/ima/ima_export.py --only-cat 计算机     # 只重生成某类目
python3 scripts/ima/ima_upload.py --dry-run --limit 10  # 只看要传什么
python3 scripts/ima/ima_sync.py --full                  # 模板升级后全量重建
```

---

## 五、本次执行结果

| 项 | 数值 |
|---|---|
| 首页书卡 | 533 本 |
| 导出成功 | 518 本（15 本无 `combined-data`：空目录 / 归档书） |
| 去重合并 | 6 组（同书长短两个 slug，保留内容更全的） |
| 最终入库 | **512 张书卡** + 2 个索引文件 |
| 卡片体积 | 最小 1.5KB / 中位 5.2KB / 最大 10.3KB（去 front matter 与重复说明后） |
| 类目分布 | 经济理财 155 · 文学 90 · 其他 85 · 历史 73 · 计算机 27 · 精品小说 24 · 社会文化 21 · 个人成长 12 · 政治军事 12 · 其余 9 类共 20 |

未入库的 15 本：`-shu-zi-you-min-quan-qiu-chuang-ye-`、`-wen-gao`、`chan-yu-mo-tuo-che-wei-xiu-yi-shu`、
`da-zhuan-xiang-…`、`downmagaz-net` 等 —— 线上确实没有 `combined-data.html`，
属于 `empty` / `dump` 档，等内容源补齐后重跑脚本会自动补进去。

---

## 六、脚本清单

| 文件 | 作用 |
|---|---|
| `scripts/ima/ima_export.py` | HTML → 结构化 Markdown，出 `ima/cards/`、`manifest.json`、`pending.json`、两份索引 |
| `scripts/ima/ima_upload.py` | 按 pending 批量上传（create_media → PUT → add_knowledge），回写 media_id |
| `scripts/ima/ima_client.py` | 直连本机 IMA 连接器的最小 MCP 客户端（initialize / tools/call，兼容 SSE 响应） |

> `ima_client.py` 里的地址 `http://ima.agent-gateway.auth-proxy.local/mcp` 只在本机
> （带 IMA 连接器的工作环境）可达。换环境要么改成对应网关地址，要么改用 Agent 的 MCP 工具逐条调。

---

## 七、已知边界

1. **「其他」85 本**：`book-cats.json` 没匹配到类目（知乎神贴、行业报告、外文原版等）。
   要更准就补 `tools/build_cats.py` 的关键词规则后重跑两个脚本，只影响这 85 本的归类。
2. **thin / empty 的书**：卡片只有 5~7 节，缺 AI领读。不是脚本问题，是书没读过、
   大纲接口返空。等云端重产后再增量同步即可。
3. **IMA 解析是异步的**：上传后 `media_state=1`（解析中），512 本全量解析约 20~40 分钟
   才轮到一批。刚传完立刻提问可能检不到，等一会儿再问；`parse_progress=100` 才可检索。
4. **章节目录只到「章名 + 规模」**，不含逐章要点。要逐章内容请直接看站点
   `combined.html` 的 AI领读模块 —— 书卡定位是检索层，不是全文层。
5. **编码坑（踩过）**：`cdn.js-dev.cn` 不返回 charset，`requests` 会按 ISO-8859-1 解码，
   中文全变 `ä¸å¥è¯`。必须 `r.content.decode('utf-8')`。第一轮 463 张卡因此全是乱码，
   已重生成重传 —— 以后加新数据源，先抽查一张卡的中文再批量跑。
6. **front matter 坑（踩过）**：IMA 把文件开头当 `introduction` 展示在检索结果里。
   写 YAML front matter 会让摘要位全是 `slug: xxx`。已改为「元信息放正文表格」，
   文件第一行就是 `# 《书名》`，第二行一句话主旨。
7. **108 本没有主旨句**：站点 `oneline` 模块对这批书只写了「共 N 章、按章序折成 M 段、
   逐字取自大纲」，过滤元说明后就空了。兜底顺序：结构脉络分组名 → 章节目录前三章名 →
   提示语。现在摘要位是「全书 12 章：第1章 人类的新议题、第2章 人类世…」。
8. **索引要小**：`00-总索引.md` 最初列了全部 518 个书名（95KB），结果任何检索都把它顶到
   前几名。已改成「类目 + 计数 + 每类 4 本示例」，只做导航。

---

## 八、验证方式

```bash
# 1) 台账口径
python3 -c "import json;m=json.load(open('ima/manifest.json'))['cards'];print(len(m), sum(1 for v in m.values() if v.get('ima_media_id')))"

# 2) 知识库内实际条数
python3 - <<'EOF'
import sys,json; sys.path.insert(0,'scripts/ima'); import ima_client as ima
ima.init()
r=ima.call("get_knowledge_list",{"knowledge_base_id":"ima_kb_Z69gwh6y",
          "folder_id":"folder_7527070271816810","limit":5})
d=json.loads(ima.text_of(r)); print("书卡文件夹总数",d["total_size"])
for it in d["knowledge_list"]: print(it["title"], it["media_state"], it["parse_progress"])
EOF

# 3) 检索抽查
# 在 IMA 里问：「投资类书里，哪些给过可操作的估值方法？」
```
