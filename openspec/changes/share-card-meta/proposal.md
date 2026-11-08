# Change: 补齐站点分享元数据（标题 / 描述 / 图标）

## Why

用户在微信里发送 `reader.js-dev.cn` 链接，卡片只显示一行域名，没有站名、描述和图标。
抓线上页面发现：`<title>` 与 `meta description` **本来就有**，但 `og:*` 命中 0、
`rel="icon"` 命中 0，`canonical` / `image_src` / `apple-touch-icon` 全无。
静态站没有公众号 JS-SDK 签名能力，卡片内容完全依赖爬虫读 `<head>`；缺缩略图和结构化
标签时微信容易退化成纯域名链接卡片。叠加微信对已分享链接的缓存，旧链接短期不会变。

## What Changes

- `index.html` `<head>`：
  - `<title>` 改为 `落雨·阅读札记`（去掉 `｜we-read`）
  - `meta[name=description]` 改为 `通过阅读，感知你我本心，快来一起读书吧。`
  - 新增 `og:type/site_name/title/description/url/image/image:width/image:height`
  - 新增 `twitter:card/title/description/image`
  - 新增 `itemprop=name/description/image`
  - 新增 `canonical`、`image_src`、`rel=icon`（SVG + PNG）、`apple-touch-icon`
- 新增 `assets/img/share-icon.png`：512×512，按 `brand/logo-a.svg`（水天需 · 六爻方章）
  的八笔矩形与配色绘制
- 新增 `docs/share-card-meta-2026-11-08.md` 与本变更

## Capabilities

### New Capabilities

- `site-meta`: 站点级标题、描述、图标与社交分享元数据的口径与可抓取性

### Modified Capabilities

- 无

## Impact

| 范围 | 影响 |
|---|---|
| 线上 | 七牛桶根 `index.html` + `assets/img/share-icon.png`，需刷新 CDN（`max-age=31536000`） |
| 代码 | `origin/main` 的 `index.html` + 新增 PNG + 文档 |
| 页面正文 | **零改动**；线上部署版本落后 main 约 375 行，本次不顺带上线 |
| 其它页面 | 不改；本次只处理根首页 |
| 小程序 / 提审 | 不受影响，未提交审核 |

## 依据

- 线上响应头（七牛）：`Content-Length: 589259`、`X-Log` / `X-Reqid` / `Content-Md5`
- 品牌标准文件：`brand/logo-a.svg`（六爻方章）；`brand/favicon.svg` 是另一枚简化标，不采用
- `https://reader.js-dev.cn/brand/logo-a.svg` 与 `/assets/img/hero-qr.png` 实测 200
- 完整排查与验收：`docs/share-card-meta-2026-11-08.md`
