/* 卡片主链接自愈（2026-11-04）
   背景：系列 Tab 的书卡曾一度把「AI 大纲」(outline.html) 当主入口，
   后来统一改成领读详情 (combined.html)。但 GitHub Pages 有 CDN 缓存、
   浏览器也可能留着旧 HTML，导致「明明改了还是点进大纲」。
   这里在运行时兜底：主链接（书名 / 整卡点击目标）若仍指向 outline.html，
   就地改写成 combined.html。明确标着「AI 大纲」的次级入口不受影响。 */
(() => {
  const SUB = ['weread-jump', 'ai-outline-link'];

  const isSecondary = (a) =>
    SUB.some((c) => a.classList.contains(c)) ||
    a.closest('.entry-links') ||
    a.closest('.card-actions');

  const fix = (a) => {
    const href = a.getAttribute('href') || '';
    if (!/\/outline\.html(\?|#|$)/.test(href)) return;
    if (isSecondary(a)) return;
    a.setAttribute('href', href.replace(/\/outline\.html/, '/combined.html'));
  };

  const run = () => {
    document
      .querySelectorAll('a.card-title-link, h3 a, a.card-link, a.book-jd-link')
      .forEach(fix);
  };

  run();
  // 书架卡是异步搬进系列组的，搬完再扫一遍
  if (typeof MutationObserver === 'function') {
    let t = 0;
    new MutationObserver(() => {
      clearTimeout(t);
      t = setTimeout(run, 120);
    }).observe(document.body, { childList: true, subtree: true });
  }
})();
