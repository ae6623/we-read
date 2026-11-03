# 套装拆册执行 · 人类简史三部曲（2026-11-03）

> 第一个走完「合集 → 按册拆开 → 逐册大纲 → 系列页 → 首页分组卡」全流程的套装。
> 后续套装照这份记录抄，命令与判据都在里面。

## 一、输入

| 项 | 值 |
|---|---|
| 合集书目 | 《人类简史三部曲（新版）》 |
| 合集 bookId | `44081364` |
| 分册数 | 3 |
| 分册判定 | 合集目录的 level1 标题 = 分册名（不是「第一章」那种） |

合集本身没有 AI 大纲：`/web/book/outline` 对合集只回一层「册名」，拿不到章级结构。
所以流程第一步是把合集拆成三个独立 bookId，再逐册按普通书处理。

## 二、产物

| 类型 | 路径 |
|---|---|
| 分册数据登记 | `assets/data/series-sets.json` → `sets[slug=ren-lei-jian-shi-san-bu-qu]` |
| 首页 hero 索引 | `assets/data/hero.json` → `ids` 追加 `ren-lei-jian-shi-san-bu-qu` |
| 三册大纲 | `reading-notes/books/<分册slug>/outline.html` |
| 系列汇总页 | `reading-notes/series/ren-lei-jian-shi-san-bu-qu/index.html` |
| 封面 | `assets/covers/<分册slug>.jpg`（428×616，30:43） |

三个分册 slug：

| 分册 | slug |
|---|---|
| 人类简史（新版）：从动物到上帝 | `ren-lei-jian-shi-xin-ban-cong-dong-wu-dao-shang-di` |
| 未来简史 | `wei-lai-jian-shi` |
| 今日简史：人类命运大议题 | `jin-ri-jian-shi-ren-lei-ming-yun-da-yi-ti` |

## 三、命令链路

```bash
# 1) 拉合集目录，按 level1 拆册（不开浏览器，走接口）
python tools/fetch_outline_api.py --book-id 44081364 --out data/outline/

# 2) 生成 series-sets 条目 + hero id
python tools/build_set_series.py --slug ren-lei-jian-shi-san-bu-qu

# 3) 逐册生成大纲（缺失时降级，保证页面不空）
python gen_outline_full.py --slug wei-lai-jian-shi
python tools/gen_fallback.py --slug wei-lai-jian-shi    # 接口失败时

# 4) 生成系列汇总页 + 同步首页分组卡
python tools/sync_set_cards.py --slug ren-lei-jian-shi-san-bu-qu
```

## 四、验收

| 检查 | 判据 |
|---|---|
| 分册数 | `series-sets.json` 里 `total == with_outline == 3` |
| 大纲质量 | 每册 `score ≥ 60`，噪声章节（版权页、致谢、索引）已过滤 |
| 封面 | 每张 428×616（30:43），文件 6–10 KB |
| 系列页 | 三册卡片按阅读顺序排列，链到各自 `outline.html` |
| 首页 | 系列 Tab 出现「人类简史三部曲 · 3 册」分组，吸顶标题正常 |

## 五、踩过的坑

1. **合集 id 当单册用**：直接对 `44081364` 跑 `gen_outline_full.py` 只会得到三行册名，
   必须先用 level1 标题拆册拿真实 bookId。
2. **hero.json 不是 bookId 列表**：`ids` 里放的是 slug（含套装 slug），塞 bookId 首页不认。
3. **封面尺寸**：250 宽的旧图在 3 列网格里发虚，统一升到 428 宽再压到 10 KB 内。
4. **首页不要手改**：书卡由 `sync_set_cards.py` 生成，手改会在下次同步时被覆盖。
