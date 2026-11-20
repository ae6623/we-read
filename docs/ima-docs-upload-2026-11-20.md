# IMA 架构/需求文档归档 · 2026-11-20

## 结论

把 auto 引擎仓（`wr-latest` = `ae6623/we-read-auto`）的**交接/架构文档**与**按日期的需求/方案文档**
整理进 IMA 知识库 `we-read` 的两个文件夹。同时给 `ARCHITECTURE.md` 补了 11 张 Mermaid 流程图。

| 文件夹 | folder_id | 条目数 | 内容 |
|---|---|---|---|
| 架构 | `folder_7529456948240818` | **31** | 交接文档 + 架构/规范/协议文档 |
| 需求 | `folder_7529457661272251` | **82** | 按日期的需求.md + 产出 + 专项复盘 |

合计 **113 份，0 失败，0 时间戳副本**。

## 架构文件夹（31）

- **交接/入口**：HANDOVER、AGENTS、ARCHITECTURE、README、流程、START-HERE、DEPLOY
- **协议**：a2a、A2A-AGENT2、A2A-WEREAD-AUTO2、docs/a2a/{README,OWNERS}
- **规范/复盘**：SESSION、cloud-rebirth-guide、code-commit-rule、data-store、
  deploy_tencent_cloud、epub-to-spark-notes、faq、mindmap-module-standard、
  pdf-fulltext-module-pipeline、pdf-fulltext-release-status、project-layout、
  spark-one-shot-pdf-notes、whitelist-audit
- **能力说明**：docs/capabilities/{01-阅读进度与打卡验证, 02-笔记归档策略,
  03-canvas阅读器正文提取, 04-EPUB自动合成, 05-工程实践, README}

落库名统一加 `架构·` 前缀（如 `架构·ARCHITECTURE.md`）。

## 需求文件夹（82）

- **`docs/requirements/<日期>/<需求短名>/` 全部 67 份**：31 份 `需求.md` + 36 份 `产出-*.md`。
  每个需求的「需求 + 解决方案 + openspec 拆解 + 验证 + 提交记录」都在同一份 `需求.md` 里
  （符合 `docs/requirements/README.md` 的 v2 归档规范），产出平铺在同文件夹。
- **docs 根目录带日期的专项文档 13 份**：如 `auth-login-state-2026-11-18`、`git-tls-retry-2026-11-17`、
  `backup-2026-11-10`、`cards-link-2026-11-14`、`dup-cards-2026-11-13` 等。

落库名 `需求·<日期>__<需求短名>__<原名>`（跨日期/跨需求不重名）；根目录专项为 `需求·<原名>`。
另含 `需求·归档规范README.md`（即 requirements 的归档规范）。

## ARCHITECTURE.md 补图（本次同步）

在本地提交 `f580414`（已推送）给架构文档补了 **11 张 Mermaid 流程图**：

1. §0.3 读写分离双链路（抢浏览器锁 409）
2. §1.3 五层架构总览
3. §1.5 全局前置门禁三闸
4. §5.1 备份 5 步流水线
5. §6.3 版本流全链路
6. §7.2 zip_pull 拉包 + 独立看护验活/回滚
7. §7.3 CDN 分发 5 步
8. §8 四层保活体系
9. §10.2 A2A 四态闭环
10. §10.4 任务状态机
11. §11.6 补书流水线完整流程

关键复杂图保留 ASCII 备用视图，避免无 Mermaid 渲染器时信息丢失。

## 上传机制与安全

- 脚本 `scripts/ima/ima_docs_upload.py`：复用 `ima_client`，`create_media → COS PUT → add_knowledge`，
  策略恒为 `SAVE`（不用 REPLACE，避免"当前内容已删除"空壳）。
- **无 create_folder 接口**：两个文件夹由用户在 IMA App 手动建好（16:13 架构 / 16:16 需求），
  脚本按 folder_id 直接投递。
- **绝不上传敏感文件**：`docs/credentials/` 下 4 份 token 文档在 `DENY_EXACT` 名单里，已排除。
  上传前对所有候选文档做了明文令牌正则扫描，命中的均为字段名/脱敏示例（如 `wr_skey`、`<hex>` 占位），无真实明文。
- **断点续传**：`ima/docs-upload-manifest.json` 记录 源相对路径 → {media_id, folder, name, cat}，
  重跑自动跳过已传；本次先试传 3 个验证落库位置，再全量 110 个。
- 落库名加分类前缀，验收确认 **0 个 `_时间戳` 副本**。

## 解析状态

IMA 解析是异步慢队列：刚传完大量条目时 `media_state=1`（解析中），随后台队列推进转 `2`。
验收时需求夹已有 36 份、架构夹 12 份完成解析，**无「解析完成但内容为空」条目**；
余下会继续自动完成。若某条长时间停在 1，可用 `ima_verify.py` 轮询确认。

## 回滚/重跑

- 上传记录：`ima/docs-upload-manifest.json`（113 条）。
- 日志：`ima/.bak/docs_upload_*.log`。
- 重跑：`python3 scripts/ima/ima_docs_upload.py`（已传自动跳过）；强制重传删对应 manifest 条目即可。
