# 静态资源 CDN（七牛 + cdn.js-dev.cn）

状态：**基础设施方案与上传脚本已就绪，等待控制台开通**。
边界：阅读器（EPUB/PDF）继续走 `ae6623/we-read-assets` 的 GitHub Pages，**不迁到 CDN**；
这套 CDN 只承载「图片、音频、封面、大文档」等新素材。

## 1. 为什么是七牛

- `js-dev.cn` 已备案，满足国内 CDN 的域名要求；
- 免费额度：**10GB 存储 + 10GB 流量/月**，放几百 MB 素材够用；
- 配置简单：一个空间 + 一个 CNAME 即可，不需要动 GitHub 仓库。

## 2. 控制台一次性配置

1. **创建空间**：对象存储 → 新建空间，名称如 `we-read-assets`，访问控制选 **公开**。
2. **绑定域名**：空间设置 → 域名管理 → 绑定 `cdn.js-dev.cn`。
   七牛会给一个 CNAME 目标（形如 `xxx.qiniudns.com`），去域名解析处加：
   ```
   cdn.js-dev.cn  CNAME  <七牛给的地址>
   ```
3. **HTTPS**：域名管理里申请免费证书（Let's Encrypt），签好后强制 HTTPS。
4. **CORS**（关键）：域名管理 → 跨域设置，允许：
   ```
   Origin: *
   Method: GET, HEAD, OPTIONS
   Header: *
   缓存时间: 600
   ```
   页面如果跨域 `fetch` 素材，没有这条会被浏览器拦。
5. **缓存**：静态文件缓存 30 天；`index.html` 之类不要放这里。
6. **防盗链**：留空。开了 Referer 白名单后，阅读器和本地调试都可能被误伤。

## 3. 上传

脚本：[`scripts/upload_to_qiniu.py`](../scripts/upload_to_qiniu.py)，依赖官方 SDK：

```bash
pip install qiniu
```

```bash
# Windows
set QINIU_AK=<你的 AccessKey>
set QINIU_SK=<你的 SecretKey>

# 先看会传什么
python scripts/upload_to_qiniu.py --bucket we-read-assets --dir assets/img --prefix assets/img --dry-run

# 真传
python scripts/upload_to_qiniu.py --bucket we-read-assets --dir assets/img --prefix assets/img
```

参数：

| 参数 | 说明 |
| --- | --- |
| `--bucket` | 空间名 |
| `--dir` | 本地目录（相对仓库根） |
| `--prefix` | 上传后的路径前缀，建议与本地目录一致 |
| `--include` | 只传匹配的文件，如 `--include "*.jpg" "**/*.png"` |
| `--workers` | 并发数，默认 8 |
| `--dry-run` | 只列文件，不上传 |

密钥只从环境变量读，**不要写进仓库**。

## 4. 页面里怎么引用

绝对 URL，路径与本地结构保持一致：

```html
<!-- 本地 assets/img/cover/a.jpg -->
<img src="https://cdn.js-dev.cn/assets/img/cover/a.jpg" alt="">
```

需要在 JS 里 `fetch` 的（JSON、文本）同样用绝对 URL，依赖第 2 步的 CORS。

## 5. 什么该放、什么不该放

| 放 CDN | 留仓库 / GitHub Pages |
| --- | --- |
| 图片、封面、音频、视频 | HTML、CSS、JS |
| 大文档（PDF、压缩包） | EPUB（阅读器要同源 fetch） |
| 前端不需要按版本管理的素材 | 需要跟代码一起回滚的资源 |

## 6. 额度与费用

- 免费：10GB 存储、10GB 流量/月（仅 HTTP；**HTTPS 流量不计入免费额度**，按量计费）；
- 超出后按量计费，流量是大头；
- 估算：一本 5MB 的 PDF，10GB 流量约等于 2000 次下载。

## 7. 回滚

素材地址都是绝对 URL，换回 GitHub 或换服务商时，只需全局替换域名前缀；
上传脚本与目录结构不变，可直接重跑到另一家。

## 8. 证书到期与提醒

七牛免费证书有效期 **90 天，不会自动续期**。当前证书：

| 项 | 值 |
| --- | --- |
| 域名 | cdn.js-dev.cn |
| 签发 | TrustAsia LiteSSL（七牛免费证书） |
| 到期 | **2027-02-05 19:59:59 +08:00** |

首页已挂自动条幅 [`assets/js/cert-banner.js`](../assets/js/cert-banner.js)：

- 到期前 **7 天**开始，每个页面顶部出现提醒条（可点「去续期」跳控制台、可关闭）；
- 8–30 天只在浏览器控制台打印提示，不打扰读者；
- 已过期时条幅变红，提示素材可能加载失败。

**续期之后要同步改一处**：`assets/js/cert-banner.js` 顶部的 `EXPIRES` 常量，
改成新证书的到期时间，否则条幅会按旧日期继续提醒。

续期入口：<https://portal.qiniu.com/cdn/domain> → 选 `cdn.js-dev.cn` → HTTPS 配置 → 更换证书。
