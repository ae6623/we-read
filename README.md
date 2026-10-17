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

复制 `templates/reading-note.html` 创建日期笔记，按实际阅读范围填写；整本书完成后再用 `templates/book-collection.html` 制作主题汇编。公开仓库只收录已单独确认可以公开的内容；之后新产生的笔记默认留在私有位置，除非另行批准。

## 当前示例

- 两篇 2026-10-17 日期笔记
- 《挪威极夜：独处时才能成为自己（轻游记）》的 HTML 主题汇编及 EPUB

站点由 `main` 分支根目录通过 GitHub Pages 发布。
