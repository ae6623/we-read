# 微信分享卡片：标题 / 描述 / 图标 · 需求与方案

> 日期：2026-11-08 16:33
> 提出：用户发微信时链接卡片只有 `reader.js-dev.cn` 一行域名，没有站名、描述、图
> 状态：**线上已生效**（2026-11-08 16:50 复核通过），待微信侧换 URL 验证

## 一、需求（用户原话口径）

| 项 | 值 |
|---|---|
| 网站标题 | `落雨·阅读札记` |
| icon | 主站左上角那个「卦」，取自品牌标准文件 `brand/logo-a.svg`（水天需 · 六爻方章） |
| 描述 | `通过阅读，感知你我本心，快来一起读书吧。` |

## 二、排查：为什么卡片只有域名

**关键事实：`reader.js-dev.cn/` 不是 GitHub Pages 直接服务，而是七牛 CDN 上的一个 `index.html` 对象。**
响应头含 `X-Log` / `X-Reqid` / `Content-Md5` / `Content-Disposition: inline; filename="index.html"`，
`Content-Length: 589259`。本地对应源文件是 `we-read-main/index.html`（字节数一致）。

抓下来的线上 `<head>` **原本就有**：

```html
<title>落雨·阅读札记｜we-read</title>
<meta name="description" content="落雨·阅读札记：个人阅读笔记与主题汇编归档。按日期和书目浏览。">
```

但 `og:*` 命中 **0**、`rel="icon"` 命中 **0**，`canonical`、`image_src`、`apple-touch-icon` 全无。

结论：

1. **没有任何分享专用标签和图标** → 微信抓不到缩略图，也拿不到结构化的标题/描述，
   容易退化成只显示域名的纯链接卡片。
2. **微信侧有分享卡片缓存**：同一个链接以前分享过，微信服务器缓存了旧结果，
   改完页面后旧链接不会立刻变。破缓存只能换 URL（见第五节）。
3. 普通静态站没有公众号 JS-SDK 签名能力，无法主动调用 `updateAppMessageShareData`
   改写卡片，只能靠 `<head>` 元数据让爬虫抓取。

## 三、解决方案

改 `index.html` 的 `<head>`（幂等补丁脚本见会话内 `_share_meta_tools.py`）：

| 改动 | 说明 |
|---|---|
| `<title>` → `落雨·阅读札记` | 去掉 `｜we-read` 尾巴，按用户指定 |
| `meta[name=description]` → 用户指定文案 | 同上 |
| 新增 `og:site_name/title/description/url/type/image` + `og:image:width/height` | 微信 / 大部分社交爬虫的结构化来源 |
| 新增 `twitter:card/title/description/image` | 兜底其它爬虫 |
| 新增 `itemprop=name/description/image` | 兜底 schema.org 抓取 |
| 新增 `link rel=canonical`、`image_src` | 规范地址 + 老式缩略图声明 |
| 新增 `rel=icon`（SVG + PNG）、`apple-touch-icon` | 浏览器标签页与 iOS 图标 |
| 新增 `assets/img/share-icon.png` | 512×512 方图，按 `brand/logo-a.svg` 的八笔矩形与配色绘制 |

图标绝对地址统一用 `https://reader.js-dev.cn/...`（已实测该域名下
`brand/logo-a.svg` 与 `assets/img/hero-qr.png` 均返回 200）。

**为什么不用 `brand/luoyu-flagship-1200.png`**：它是 1200×260 横幅，微信卡片缩略图
需要方图，会被裁得只剩中间一条；`brand/favicon.svg` 是圆+波浪的简化版，**不是**用户
指的那个卦。用户要的是 `brand/logo-a.svg` 的六爻方章。

## 四、部署口径（重要，别改错文件）

| 目标 | 做法 |
|---|---|
| 线上立即生效 | 把改好 head 的 **线上版本** `index.html` 上传到七牛桶根 key `index.html`；上传 `assets/img/share-icon.png`；刷新 CDN URL 缓存 |
| 代码留痕 | 在 `origin/main` 上提交 `index.html` + `assets/img/share-icon.png` + 本文档 + openspec 变更 |

> 线上部署版本落后于 `main` 约 375 行首页内容。本次**只改 head**，不把 main 的
> 375 行内容顺带上线，避免用户没要求的首页内容变化。两份 head 改动一致。
>
> `we-read-main` 工作副本的本地历史与 `origin/main` 分叉，`git pull --rebase` 会触发
> 几十个 `add/add` 冲突，已 `git rebase --abort` 回滚。本次改用
> `git clone --depth 1 --single-branch --branch main` 拉干净副本提交。

CDN 缓存 `max-age=31536000`，**不刷新等于一年不生效**。

## 五、验收与微信缓存

1. `curl https://reader.js-dev.cn/` 的 `<title>` = `落雨·阅读札记`
2. `description` = `通过阅读，感知你我本心，快来一起读书吧。`
3. `https://reader.js-dev.cn/assets/img/share-icon.png` 返回 200、512×512 PNG
4. `og:image` 指向该 PNG
5. **微信里验证必须换 URL**：分享 **`https://reader.js-dev.cn/index.html?v=2`**（或任意新参数），
   微信会当新链接重新抓取；直接重发旧链接仍可能是缓存里的旧卡片。
   ⚠️ **不要写成 `https://reader.js-dev.cn/?v=2`** —— 实测返回 404 / 30 字节：
   七牛目录索引只在无查询串时生效，带参数必须带文件名。
   若仍不行，等微信缓存自然过期，或用公众号 JS-SDK 定制分享（需 AppID + 签名，静态站做不到）。

### 线上复核结果（2026-11-08 16:50）

| 检查 | 结果 |
|---|---|
| `https://reader.js-dev.cn/` | 200，590741 字节，`<title>落雨·阅读札记</title>`，`og:title` 命中 1 |
| `https://reader.js-dev.cn/index.html` | 200，同上，`X-Cache-Status: HIT` / `Age: 17` |
| `.../index.html?v=2` | 200，新元数据，可用于破微信缓存 |
| `.../assets/img/share-icon.png` | 200，512×512 PNG，1834 字节 |
| description | `通过阅读，感知你我本心，快来一起读书吧。` |

**CDN 刷新过程**：URL 刷新配额当天已用尽（500/500，`code 400034`）。目录刷新提交成功
但未让根对象失效；最终用**预热 `prefetch_urls`** 把最新内容拉到边缘节点，
`X-Cache-Status` 由 `HIT / Age 59883` 变为 `MISS → HIT / Age 17`，
`Last-Modified` 更新为 `Sun, 08 Nov 2026 08:46:50 GMT`，线上生效。

## 六、不做清单

- 不改首页正文、不动 375 行 main 新增内容
- 不改 CSS / JS / 书卡数据
- 不改小程序仓库
- 不提交任何审核
