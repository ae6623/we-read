## ADDED Requirements

### Requirement: 站点标题 SHALL 与用户指定一致

根首页 `<title>` SHALL 精确为 `落雨·阅读札记`，MUST NOT 带 `｜we-read` 等后缀。
`og:title`、`og:site_name`、`twitter:title`、`itemprop=name` SHALL 同值。

#### Scenario: 抓取首页

- **WHEN** 爬虫请求 `https://reader.js-dev.cn/`
- **THEN** `<title>` 为 `落雨·阅读札记`
- **AND** `og:title` / `twitter:title` / `itemprop=name` 同为 `落雨·阅读札记`

### Requirement: 站点描述 SHALL 与用户指定一致

`meta[name=description]`、`og:description`、`twitter:description`、`itemprop=description`
SHALL 精确为 `通过阅读，感知你我本心，快来一起读书吧。`。

#### Scenario: 抓取描述

- **WHEN** 爬虫请求根首页
- **THEN** 四处描述均为 `通过阅读，感知你我本心，快来一起读书吧。`
- **AND** 不再出现「个人阅读笔记与主题汇编归档。按日期和书目浏览。」

### Requirement: 分享图标 SHALL 采用六爻方章且 MUST 为可抓取的方图

图标 SHALL 取自 `brand/logo-a.svg`（水天需 · 六爻方章）的八笔矩形与配色。
实现 MUST NOT 使用 `brand/favicon.svg`（圆 + 波浪简化标）或
`brand/luoyu-flagship-1200.png`（1200×260 横幅，会被裁切）。
`og:image` SHALL 指向一张 ≥300×300 的方图，URL MUST 为 HTTPS 绝对地址且可公开访问。

#### Scenario: 图片可用

- **WHEN** 请求 `https://reader.js-dev.cn/assets/img/share-icon.png`
- **THEN** 返回 200 且为 512×512 PNG
- **AND** `og:image` / `twitter:image` / `itemprop=image` / `image_src` 均指向该地址

#### Scenario: 浏览器标签

- **WHEN** 用户在浏览器打开首页
- **THEN** 标签图标优先使用 `brand/logo-a.svg`，PNG 作兜底
- **AND** iOS 添加到主屏使用同一张 PNG

### Requirement: 改动 MUST NOT 改变首页正文

本次变更 SHALL 只修改根首页 `<head>` 并新增一张图片，MUST NOT 改动 `<body>`、
CSS、JS、书卡数据。线上部署版本落后 `main` 约 375 行内容，本次 MUST NOT 顺带上线这些变化。

#### Scenario: 正文比对

- **WHEN** 对比改动前后的线上首页
- **THEN** 除 `<head>` 内新增/修改的标签外，字节内容一致
- **AND** `git diff` 中 `index.html` 的改动仅限 `<head>`

### Requirement: CDN 缓存 MUST 刷新

因响应头 `Cache-Control: max-age=31536000`，上传后 SHALL 刷新根 URL、
`index.html` 与 `share-icon.png` 的 CDN 缓存，否则改动不生效。

#### Scenario: 上线复核

- **WHEN** 完成上传与刷新
- **THEN** `curl` 首页返回新 `<title>` 与新 `description`
- **AND** `og:image` 指向的图片返回 200

### Requirement: 微信缓存 MUST 由换 URL 破除

微信对已分享过的链接有卡片缓存。验证 SHALL 使用带文件名的新 URL
（如 `https://reader.js-dev.cn/index.html?v=2`），MUST NOT 期待重发旧链接立即生效。
**`https://reader.js-dev.cn/?v=2` MUST NOT 用作验证地址** —— 实测 404 / 30 字节，
七牛目录索引只在无查询串时生效。
静态站无公众号 JS-SDK 签名能力，实现 MUST NOT 声称可用 `updateAppMessageShareData` 兜底。
