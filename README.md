# we-read：阅读笔记归档

一个无需构建工具的静态阅读笔记站点，可直接通过 GitHub Pages 发布。主页提供轻量搜索，笔记与整书汇编使用分开的目录和模板。

## 目录结构

- `index.html`：主页与归档索引
- `assets/css/site.css`：共享响应式样式
- `assets/js/site.js`：主页搜索筛选
- `notes/YYYY/`：按年份存放日期笔记
- `books/<slug>/`：按书目存放整书汇编与 EPUB
- `templates/`：日期笔记与整书汇编模板
- `.github/workflows/pages.yml`：GitHub Pages 自动发布

## 使用方式

复制 `templates/reading-note.html` 创建日期笔记，按实际阅读范围填写；整本书完成后再用 `templates/book-collection.html` 制作主题汇编。此类面向用户的微信读书阅读笔记已获持续公开授权，今后默认公开，无需逐篇再次确认；内部协调、原始场次与活动运行元数据以及跨书综合仍保持私有，其他内容按各自授权范围处理。

## 当前示例

- 按书目与日期保留阅读笔记，含《世界这么大，我想到处躺》2026-10-17 与 2026-10-18 两篇独立日期笔记
- 《挪威极夜：独处时才能成为自己（轻游记）》的 HTML 主题汇编及 EPUB

站点由 `main` 分支根目录通过 GitHub Pages 发布。
