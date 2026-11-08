## 1. 前置：同步代码

- [x] 1.1 `git fetch origin main` 确认远端有新提交
- [x] 1.2 `git pull --rebase origin main` **失败**：本地历史分叉，几十个 `add/add` 冲突 → 已 `git rebase --abort` 回滚，工作副本恢复干净
- [x] 1.3 改用 `git clone --depth 1 --single-branch --branch main` 拉干净副本到 `D:/_wr_meta_20261108`，HEAD `1cb167c`

## 2. 排查与文档

- [x] 2.1 抓线上根站并核对响应头，确认是七牛 CDN 对象而非 Pages 直出
- [x] 2.2 确认线上 `<head>` 已有 title/description，但 `og:*` 与 `rel=icon` 均为 0
- [x] 2.3 确认品牌标准图为 `brand/logo-a.svg`（六爻方章），排除 `favicon.svg` 与 1200×260 横幅
- [x] 2.4 新增 `docs/share-card-meta-2026-11-08.md`
- [x] 2.5 本变更 proposal / tasks / spec delta 落盘

## 3. 实现

- [x] 3.1 生成 512×512 `assets/img/share-icon.png`（Pillow 按 logo-a 八笔矩形绘制）
- [x] 3.2 `index.html` 改 `<title>` 与 `description` 为用户指定文案
- [x] 3.3 `index.html` 补 og / twitter / itemprop / canonical / image_src / favicon
- [x] 3.4 幂等补丁同时应用到「线上部署版」与「main 源码版」两份 head

## 4. 上线与验证

- [x] 4.1 上传线上部署版 `index.html` 到七牛桶根 key（HTTP 200）
- [x] 4.2 上传 `assets/img/share-icon.png` 到七牛（HTTP 200）
- [x] 4.3 刷新 CDN：URL 刷新配额用尽（500/500）→ 目录刷新 → **预热 `prefetch_urls` 生效**
- [x] 4.4 `curl` 复核：`/` 与 `/index.html` 均返回 590741 字节、新 title、新 description、`og:title` 命中
- [x] 4.5 `share-icon.png` 返回 200、512×512 PNG
- [x] 4.6 合并提交并 push 到 `origin/main`（`6870286`，后续验收回填另起一条）

## 5. 微信侧（需用户操作）

- [ ] 5.1 **换 URL 破微信缓存**：分享 `https://reader.js-dev.cn/index.html?v=2`，不要重发旧链接
      ⚠️ 根路径 `https://reader.js-dev.cn/?v=2` 实测 404（七牛目录索引不认带查询串的根路径）
- [ ] 5.2 若仍不生效，等微信缓存过期；静态站无法用 JS-SDK 主动改写卡片
