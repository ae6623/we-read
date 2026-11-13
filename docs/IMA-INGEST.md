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
        │  tools/ima_export.py
        │   · 按 data-key 切模块：oneline / views / deepread / top10 /
        │     coreask / aiask / higher / verify / thennow / merged_guide
        │   · 去 <style>、去「本页由 AI 生成…」这类每张卡重复的元说明
        │   · 短行（≤14 字）识别为 ###小标题，长行合并为段落，列表原样保留
        │   · merged_guide 只取章节目录骨架（章名 + 小节数/要点数），
        │     不搬 70KB 的逐章原文 —— 书卡是索引，不是全文复制
        ▼
ima/cards/<类目>·<书名>.md        中位 5.2KB / 最大 10.3KB / 最小 1.5KB
        │
        │  tools/ima_upload.py
        │   · create_media → COS 预签名 PUT → add_knowledge(folder=书卡)
        │   · 失败重试 3 次（指数退避），并发 4
        ▼
IMA 知识库 we-read（写入即自动解析，parse_progress 100%）
```

---

## 三、每张书卡长什么样

```markdown
---
slug: 1984
title: 1984
cat1: 文学
cat2: 小说
status: ok
modules: oneline,views,deepread,top10,coreask,aiask,higher,verify,thennow
updated: 2026-11-13
source: https://reader.js-dev.cn/reading-notes/books/1984/combined.html
---

# 《1984》

> 极权不是让你说假话，而是接管「判定何为真」的权力。

| 项 | 值 |
|---|---|
| 类目 | 文学 / 小说 |
| 卡片状态 | ok（9 个标准模块） |
| 站点原文 | …/1984/combined.html |

## 01 核心观点与结构脉络
### 译序与极权现实
——交代作品影响并展示大洋国监控、历史篡改与个体异化的统治日常。
…
## 02 精读判断
## 03 原文金句
## 04 核心追问
## 05 AI 问书
## 06 更高维度
## 07 阅读时要验证
## 08 当年与今天
## 09 章节目录
```

**固定 10 节**（缺哪节＝这本书没有该模块，多为未读、大纲接口返空）。
数字前缀是为了让 IMA 的回答能引用「第 07 节」这种锚点。

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

日常同步（站点出新书 / 重产某本之后）：

```bash
cd /root/we-read-site
python3 tools/ima_export.py            # 约 2 分钟，重算 hash，产出 pending.json
python3 tools/ima_upload.py            # 只传 pending，约 1.5 分钟/100 本
```

两条命令都幂等：重复跑不会产生重复知识（同名 `DUPLICATE_NAME_STRATEGY_REPLACE` 覆盖）。

单本重传：

```bash
python3 tools/ima_export.py --limit 1 --force        # 或直接改完 md 后
python3 tools/ima_upload.py --limit 1 --replace
```

分类同步 / 试水：

```bash
python3 tools/ima_export.py --only-cat 计算机
python3 tools/ima_upload.py --cat 计算机
python3 tools/ima_upload.py --dry-run --limit 10     # 只看要传什么
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
| `tools/ima_export.py` | HTML → 结构化 Markdown，出 `ima/cards/`、`manifest.json`、`pending.json`、两份索引 |
| `tools/ima_upload.py` | 按 pending 批量上传（create_media → PUT → add_knowledge），回写 media_id |
| `tools/ima_client.py` | 直连本机 IMA 连接器的最小 MCP 客户端（initialize / tools/call，兼容 SSE 响应） |

> `ima_client.py` 里的地址 `http://ima.agent-gateway.auth-proxy.local/mcp` 只在本机
> （带 IMA 连接器的工作环境）可达。换环境要么改成对应网关地址，要么改用 Agent 的 MCP 工具逐条调。

---

## 七、已知边界

1. **「其他」85 本**：`book-cats.json` 没匹配到类目（知乎神贴、行业报告、外文原版等）。
   要更准就补 `tools/build_cats.py` 的关键词规则后重跑两个脚本，只影响这 85 本的归类。
2. **thin / empty 的书**：卡片只有 5~7 节，缺 AI领读。不是脚本问题，是书没读过、
   大纲接口返空。等云端重产后再增量同步即可。
3. **IMA 解析是异步的**：上传后 `media_state=1`（解析中），几分钟内转 2。
   刚传完立刻提问可能检不到，等 1~2 分钟。
4. **章节目录只到「章名 + 规模」**，不含逐章要点。要逐章内容请直接看站点
   `combined.html` 的 AI领读模块 —— 书卡定位是检索层，不是全文层。
5. **编码坑（踩过）**：`cdn.js-dev.cn` 不返回 charset，`requests` 会按 ISO-8859-1 解码，
   中文全变 `ä¸å¥è¯`。必须 `r.content.decode('utf-8')`。第一轮 463 张卡因此全是乱码，
   已重生成重传 —— 以后加新数据源，先抽查一张卡的中文再批量跑。
6. **front matter 坑（踩过）**：IMA 把文件开头当 `introduction` 展示在检索结果里。
   写 YAML front matter 会让摘要位全是 `slug: xxx`。已改为「元信息放正文表格」，
   文件第一行就是 `# 《书名》`，第二行一句话主旨。
7. **索引要小**：`00-总索引.md` 最初列了全部 518 个书名（95KB），结果任何检索都把它顶到
   前几名。已改成「类目 + 计数 + 每类 4 本示例」，只做导航。

---

## 八、验证方式

```bash
# 1) 台账口径
python3 -c "import json;m=json.load(open('ima/manifest.json'))['cards'];print(len(m), sum(1 for v in m.values() if v.get('ima_media_id')))"

# 2) 知识库内实际条数
python3 - <<'EOF'
import sys,json; sys.path.insert(0,'tools'); import ima_client as ima
ima.init()
r=ima.call("get_knowledge_list",{"knowledge_base_id":"ima_kb_Z69gwh6y",
          "folder_id":"folder_7527070271816810","limit":5})
d=json.loads(ima.text_of(r)); print("书卡文件夹总数",d["total_size"])
for it in d["knowledge_list"]: print(it["title"], it["media_state"], it["parse_progress"])
EOF

# 3) 检索抽查
# 在 IMA 里问：「投资类书里，哪些给过可操作的估值方法？」
```
