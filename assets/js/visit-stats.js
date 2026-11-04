/*!
 * visit-stats.js — we-read 访问统计徽章（首页 + 书籍详情页通用）
 *
 * 数据源：GoatCounter counter API，复用站点已有 ae6623 账号，零后端、零新服务。
 *   全站总数：/counter/TOTAL.json                  （实测当前 470）
 *   单本书  ：/counter/detail/view/<slug>.json    （事件通道，见下）
 *
 * ⚠️ 官方限制（goatcounter.com/help/visitor-counter）：
 *    counter API 的 count 是「去重访客数」；count_unique 只是向后兼容字段且值与
 *    count 完全相同，官方明确写了「should not be used for new code」。因此
 *    「次访问 / 位访客」「阅读次数 / 阅读人数」这两组数字，纯前端拿不到两个
 *    互相独立的真实值：下面两组都填同一个真实数字。要真正拆开 PV / UV，需要
 *    再接一个能分别返回两者的统计源（或带 token 的后端代理 /api/v0/stats）。
 *
 * 行为：
 *  - 页面已有 #gc_site_pv_num / #gc_site_uv_num（首页 visit-badge）→ 只回填，不新建 DOM
 *  - 否则（详情页）→ 在 body 末尾自动创建徽章，含「本站」与「本书」两组
 *  - 详情页按 body[data-slug] 或 URL 里的 /books/<slug>/ 上报一次「打开」事件
 *    （走现有 home-track.js 的 rdTrack 事件通道，不进 PV、不影响全站总数）
 *  - 取数失败 / 尚无数据显示「–」，不再用 localStorage 造演示假数
 *
 * 引入方式（放在 </body> 前，相对路径按文件深度调整）：
 *   <script src="../../../assets/js/visit-stats.js?v=20261104a" defer></script>
 */
(function () {
  'use strict';

  var CODE = 'ae6623';
  var BASE = 'https://' + CODE + '.goatcounter.com/counter';
  var BOOK_EVENT = '/detail/view/';

  /* ---------- 取数：只认 count，count_unique 与它同值，不用 ---------- */
  function stat(path) {
    return fetch(BASE + path + '.json', { credentials: 'omit', cache: 'no-store' })
      .then(function (r) { return r.text(); })
      .then(function (t) {
        try {
          var d = JSON.parse(t);
          var n = parseInt(String(d.count).replace(/[^0-9]/g, ''), 10);
          return isFinite(n) && n > 0 ? n : null;
        } catch (e) { return null; }
      })
      .catch(function () { return null; });
  }

  function num(n) { return n == null ? '–' : String(n); }

  /* ---------- 当前书 slug ---------- */
  function bookSlug() {
    var b = document.body || {};
    if (b.dataset && b.dataset.slug) return b.dataset.slug;
    var m = location.pathname.match(/\/books\/([^/]+)\//);
    return m ? m[1] : null;
  }

  /* ---------- 上报「打开这本书」：一次页面加载只发一次 ---------- */
  var tracked = false;
  function trackBook(slug) {
    if (!slug || tracked) return;
    tracked = true;
    var path = BOOK_EVENT + slug;
    var title = (document.body && document.body.dataset && document.body.dataset.title) || slug;
    var label = '详情页·打开：' + title;

    if (typeof window.rdTrack === 'function') {           // combined.html 走这里
      try { window.rdTrack(path, label); return; } catch (e) { /* 落到兜底 */ }
    }

    /* overview / outline / mindmap 等没引 home-track.js 的页面 */
    var tries = 0;
    var timer = setInterval(function () {
      if (window.goatcounter && typeof window.goatcounter.count === 'function') {
        clearInterval(timer);
        try { window.goatcounter.count({ path: path, title: label, event: true }); } catch (e) {}
      } else if (++tries > 40) {
        clearInterval(timer);
      }
    }, 200);
  }

  /* ---------- 样式：内联兜底，不依赖站点 CSS 版本 ---------- */
  function ensureStyles() {
    if (document.getElementById('wrVisitStyle')) return;
    var s = document.createElement('style');
    s.id = 'wrVisitStyle';
    s.textContent = [
      '#wrVisit{margin:30px auto 12px;padding:0 16px;max-width:820px;display:flex;gap:10px;flex-wrap:wrap;justify-content:center;',
      'font:14px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;color:#8a8f98}',
      '#wrVisit .wr-card{display:flex;align-items:baseline;gap:7px;padding:8px 15px;border-radius:999px;',
      'border:1px solid rgba(127,127,127,.24);background:rgba(127,127,127,.07)}',
      '#wrVisit .wr-label{font-size:12px;opacity:.75;letter-spacing:.04em}',
      '#wrVisit b{font-size:17px;font-weight:700;color:#e0b26b;font-variant-numeric:tabular-nums}',
      '#wrVisit .wr-unit{font-size:12px;opacity:.8}',
      '#wrVisit .wr-sep{opacity:.45}',
      '@media(max-width:520px){#wrVisit{gap:8px}#wrVisit .wr-card{padding:6px 11px}#wrVisit b{font-size:15px}}'
    ].join('');
    document.head.appendChild(s);
  }

  /* ---------- 详情页徽章 DOM ---------- */
  function ensureBadge() {
    var el = document.getElementById('wrVisit');
    if (el) return el;
    ensureStyles();
    el = document.createElement('div');
    el.id = 'wrVisit';
    el.setAttribute('role', 'group');
    el.setAttribute('aria-label', '站点与本书访问统计');
    el.innerHTML =
      '<div class="wr-card">' +
        '<span class="wr-label">本站</span>' +
        '<b id="wr_site_pv">–</b><span class="wr-unit">次访问</span>' +
        '<span class="wr-sep">·</span>' +
        '<b id="wr_site_uv">–</b><span class="wr-unit">位访客</span>' +
      '</div>' +
      '<div class="wr-card">' +
        '<span class="wr-label">本书</span>' +
        '<b id="wr_book_pv">–</b><span class="wr-unit">次阅读</span>' +
        '<span class="wr-sep">·</span>' +
        '<b id="wr_book_uv">–</b><span class="wr-unit">人读过</span>' +
      '</div>';
    document.body.appendChild(el);
    return el;
  }

  function put(id, v) {
    var e = document.getElementById(id);
    if (e) e.textContent = v;
  }

  /* ---------- 主流程 ---------- */
  function init() {
    var hasSite = !!(document.getElementById('gc_site_pv_num') || document.getElementById('gc_site_uv_num'));
    var slug = bookSlug();

    /* 全站总数：有真数据就用真的，取不到就显示 – */
    stat('/TOTAL').then(function (n) {
      var v = num(n);
      if (hasSite) {
        put('gc_site_pv_num', v);
        put('gc_site_uv_num', v);
      } else {
        put('wr_site_pv', v);
        put('wr_site_uv', v);
      }
    });

    if (!slug) return;   /* 首页：只显示全站总数 */

    ensureBadge();
    trackBook(slug);

    /* 本书：读回 /detail/view/<slug> 事件累计值 */
    stat(BOOK_EVENT + slug).then(function (n) {
      var v = num(n);
      put('wr_book_pv', v);
      put('wr_book_uv', v);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
