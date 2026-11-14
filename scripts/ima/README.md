# scripts/ima — 书卡 → IMA 知识库同步脚本

> 唯一入口目录。站点每产出一本新书，`combined-data.html` 上线后必须跑这里的同步，
> IMA 知识库 `we-read` 里才会多出对应的书卡 md。
>
> 另一条链路别漏：书卡**壳页**的 reader js 版本由 `scripts/check_reader_js.py` 验收
> （真相源 `assets/data/reader-js.json`），决定线上书卡有没有「章节知识导图」。
> 完整新书 SOP 见 `docs/IMA-INGEST.md` §4.2：先跑壳页守卫，再跑本目录的 IMA 同步。

## 一条命令

```bash
python3 scripts/ima/ima_sync.py --book <slug>   # 新书产出后（SOP 第 2 步）
python3 scripts/ima/ima_sync.py                 # 日常兜底：全量增量扫描，补所有漏的
python3 scripts/ima/ima_sync.py --full          # 模板升级后全量重建
python3 scripts/ima/ima_check.py                # 验收：站点有书卡但 md 缺失就报错
```

## 脚本职责

| 脚本 | 作用 |
|---|---|
| `ima_client.py` | 最小 MCP 客户端，直连本机 IMA 连接器（initialize / tools/call，兼容 SSE 多行 JSON） |
| `ima_export.py` | `combined-data.html` → 结构化 Markdown；写 `ima/cards/`、`manifest.json`、`pending.json`、两份索引 |
| `ima_index.py` | 全量总索引（523 本逐本含站点网址）的生成 / 网址校验 / 上传；`ima_export.py` 也调它的 `build_index()` |
| `ima_upload.py` | 按 pending 批量上传（create_media → COS PUT → add_knowledge），回写 media_id |
| `ima_sync.py` | 导出 → 补传 → 刷索引，串成一条命令 |
| `ima_verify.py` | 轮询知识库 `media_state`，解析是异步慢队列，别刚传完就判失败 |
| `build_covers.py` | 探测站点封面，生成 `assets/data/covers.json` 索引 |
| `ima_check.py` | 验收守卫：站点书卡数 vs IMA md 数，缺哪本直接点名 |

## 模板升级试推（不污染台账）

模板大版本升级后，先推 2 本到**新建的空文件夹**让用户在 App 里确认渲染效果，确认后再全量重传。`--no-manifest` 保证试推不会把新文件夹的卡误记为已同步（台账仍指向旧文件夹里的卡）。
2026-11-14 已全量切到 `书卡笔记v3`（523 张 v6 卡），下次升级再新建 v4 试推：

```bash
python3 scripts/ima/ima_upload.py --folder 书卡笔记v4 \
    --books 1984,yi-sheng-de-du-shu-ji-hua --no-manifest --skip-existing
python3 scripts/ima/ima_verify.py --folder 书卡笔记v4 --wait 10
```

| 参数 | 作用 |
|---|---|
| `--folder <名称>` | 目标文件夹，默认 `书卡笔记v3`；`ima_verify.py` 同样支持 |
| `--books <slug,slug>` | 只推指定 slug，忽略 pending 与台账已入库状态 |
| `--no-manifest` | 不回写 `manifest.json`（试推专用） |

## 三条硬规则（都是踩过的坑）

1. **禁用 `DUPLICATE_NAME_STRATEGY_REPLACE`**：同名 REPLACE 会让服务端把旧条目内容清空、
   新条目另立，App 里显示「当前内容已删除」。上传固定 `SAVE`，覆盖前先在 App 删旧条目。
2. **上传前必须 `--skip-existing`**：SAVE 遇同名会生成 `_<时间戳>` 副本，列表里出现两条。
3. **台账记 `add_knowledge` 返回的 `media_id`**，不是 `create_media` 的，两者不是同一对象。

## 封面只能用 Markdown 图片语法

`![《书名》封面](https://cdn.js-dev.cn/assets/covers/<slug>.jpg)`

`<p align="center"><img ...></p>` 会让 IMA 的 md 解析器卡在 `media_state=1`，
整条书卡内容永远为空。

## 全量总索引（含每本网址）

`00-总索引.md` 从 2026-11-14 起改为**全量 523 本 + 逐本站点详情页网址**，
不再只列每类 4 本代表。生成逻辑在 `ima_index.py`，导出器每次同步都会刷新本地这份。

```bash
python3 scripts/ima/ima_index.py                  # 只生成本地 ima/00-总索引.md
python3 scripts/ima/ima_index.py --check-all     # 生成 + 全量校验 523 条 URL 可达
python3 scripts/ima/ima_index.py --upload        # 生成 + 上传到 IMA 根目录
```

落库名默认 `00-总索引·全量网址.md`（与旧精简版不重名，SAVE 不会加时间戳后缀）。

⚠️ **IMA 没有 delete / update 接口**，这份索引无法原地更新：
- 新书上线后本地索引自动带上新书，但 IMA 里那份不会变；
- 要让 IMA 同步，先在 App 删掉旧的 `00-总索引·全量网址.md` 再跑 `--upload`；
- 根目录里 `00-总索引.md`(512 本精简)、`00-总索引_261114094220.md`(523 本精简)、
  `00-字段说明_261114094222.md` 三份旧副本同样只能在 App 手工删除。全删干净后，
  可用 `--upload --name 00-总索引.md` 让根目录只留一份权威总索引。

完整方案、字段口径、新书产出 SOP 见 `docs/IMA-INGEST.md` §4.1 / §七.8。
