# 猴面包的树·轻游记补产 80 本

- 数据源：微信读书 skill `/store/search`（作者维度 scope=10 翻页拉全）→ 书城在售 **115 本**
- 已产出：23 本（`_data/books` author=猴面包的树）+ 12 本有页面 = 35 本
- 本轮补产：**80 本**，10 批 × 8 本
- 官方 AI 大纲体检：79 本有逐章大纲（共 3323 条要点），1 本（`3300238669` 孟加拉国）官方暂无逐章大纲 → 降级

## 生产形态（与现有 24 本一致）

| 产物 | 说明 |
|---|---|
| `reading-notes/books/<slug>/outline.html` + `.json` | 官方 AI 大纲页（fetch_outline_api.render） |
| `.../combined-data.html` | 全书领读 10 模块：svg/oneline/merged_guide/views/aiask/coreask/higher/verify/thennow/quiz |
| `.../combined.html` | reader 页（reader.js 动态加载 10 模块） |
| `_data/books/<slug>.json` | 书架登记（title/author/series=qingyouji/meta_line） |
| `assets/data/hero.json` | slug→bookId 登记 |

## 流水线

1. `tools/fetch_outline_api.py`：`/book/chapterinfo` + `/web/book/outline` 拉官方 AI 大纲 → 缓存 `/tmp/outline_cache/<bookId>.json`
2. `drafts/<slug>-material.md`：大纲轻量摘要（供精写 Agent，避免读超大原文）
3. **派工精写**：子 Agent 基于摘要写 `drafts/<slug>-llm.json`（6 个内容模块），替代 `--auto-llm` 兜底
4. `tools/produce_qingyouji.py --llm ...`：一键产 outline + 10 模块 + reader + 登记（复用 fetch_outline_api / fill_combined_modules）

> 说明：`fill_combined_modules.gen_auto_llm` 是兜底机械合成（标注"Agent 兜底生成"），质量不对齐现有精写本；`--llm` 注入才是"本 Agent 即 LLM"的正统精写通道。

## 批次

| 批次 | 本数 | 任务卡 |
|---|---|---|
| 01 | 8 | [批次-01.md](./批次-01.md) |
| 02 | 8 | [批次-02.md](./批次-02.md) |
| 03 | 8 | [批次-03.md](./批次-03.md) |
| 04 | 8 | [批次-04.md](./批次-04.md) |
| 05 | 8 | [批次-05.md](./批次-05.md) |
| 06 | 8 | [批次-06.md](./批次-06.md) |
| 07 | 8 | [批次-07.md](./批次-07.md) |
| 08 | 8 | [批次-08.md](./批次-08.md) |
| 09 | 8 | [批次-09.md](./批次-09.md) |
| 10 | 8 | [批次-10.md](./批次-10.md) |

## 最终交付验收（2026-11-16 03:58 线上实测）

| # | 项 | 期望 | 实测 |
|---|---|---|---|
| 1 | 首页系列徽标 | 103 册 | **103 册** ✅ |
| 2 | 首页 intro | 含「轻游记 103 册排在最前」 | 命中 1 处，旧句「23 册」残留 0 ✅ |
| 3 | `assets/data/hero.json` | `ids`=405 / `nocover`=6 | 405 / 6 ✅ |
| 4 | 系列页卡片 | 103 | **103** ✅ |
| 5 | 抽样新书页 `combined.html` | 200 | 3/3 = 200 ✅ |
| 6 | **80 张封面（CDN）** | 200 且 >3KB | **80/80 = 200** ✅ |
| 7 | **80 张封面（站点域名）** | 200 + `image/jpeg` | 抽样 3/3 = 200，`image/jpeg` ✅ |
| 8 | 原有书封面回归 | 不坏 | `alaska-qingyouji` / `spain-qingyouji` = 200 ✅ |

封面规格：428×616 官方高清（`s_`→`t9_`），80 张合计 12.3MB，与原有 30 张同规格。
部署链路：`699e1517` 推 main → Pages + `Upload to CDN (qiniu)` → 03:57 封面转 200（约 3 分钟）。

**遗留（非本批）**：全站另有 1 本历史书缺封面 `ren-lei-jian-shi-san-bu-qu`（人类简史三部曲），`hero.json` 的 `ids` 有、`assets/covers` 无、且不在 `nocover` 里。建议后续 `python3 tools/check_covers.py --fix --manifest <该书单>` 单独补。

