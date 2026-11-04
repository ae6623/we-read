/*!
 * visit-stats.js — we-read 访问统计徽章（首页 + 书籍详情页通用）
 * v3 · 2026-11-05
 *
 * ── 两个数字分别是哪来的 ────────────────────────────────────
 *  访问次数（次访问 / 次阅读）
 *      Abacus 计数器（https://abacus.jasoncameron.dev），每个页面打开就
 *      /hit 一次，真实 +1，实时。站点 key = site，每本书 key = book-<slug>。
 *      Abacus 的 /set 要付费版，所以历史数据用下面的公式补：
 *          PV = abacus 值 + 当前 GoatCounter 访客数
 *      逻辑上「历史累计访问次数 ≥ 历史访客数」成立，把它当下界用，
 *      上线时两个数相同，之后每次访问 PV 都会跑在前面。
 *
 *  访客人数（位访客 / 人读过）
 *      GoatCounter：站点 /counter/TOTAL.json，单书 /counter/detail-view-<slug>.json
 *      该接口只给去重访客数，拿不到 PV —— 这正是要引入 Abacus 的原因。
 *      接口有 CDN 强缓存（最长 4 小时），刚访问完读数不会立刻变，属正常。
 *
 * ── 历史坑（别再踩）──────────────────────────────────────
 * 1) GoatCounter 事件名不能以 / 开头（官方文档原文），v1 用 /detail/view/<slug>
 *    上报被服务端直接丢弃，所以详情页永远 0。现在用 detail-view-<slug>。
 * 2) 上报不能依赖 gc.zgo.at 的 count.js —— 国内经常超时，脚本加载不到就静默丢事件。
 *    现在直接向 ae6623.goatcounter.com/count 打像素。
 * 3) 只在主详情页 combined.html 上报/+1，overview/outline/mindmap 等子页面
 *    只读不报，否则一次阅读会被记成好几次。
 *
 * ── 引入方式（放 </body> 前，相对路径按文件深度调整）─────────
 *   <script src="../../../assets/js/visit-stats.js?v=20261105a" defer></script>
 */

(function () {
  'use strict';

  var GC = 'https://ae6623.goatcounter.com';
  var COUNTER = GC + '/counter';
  var EVENT_PREFIX = 'detail-view-';   /* 关键：不能以 / 开头 */
  var ABACUS = 'https://abacus.jasoncameron.dev';
  var NS = 'ae6623-we-read';

  /* ---------- GoatCounter：访客数 ---------- */
  function gcStat(path) {
    return fetch(COUNTER + path + '.json', { credentials: 'omit', cache: 'no-store' })
      .then(function (r) { return r.text(); })
      .then(function (t) {
        try {
          var d = JSON.parse(t);
          var n = parseInt(String(d.count).replace(/[^0-9]/g, ''), 10);
          return isFinite(n) ? n : null;
        } catch (e) { return null; }
      })
      .catch(function () { return null; });
  }

  /* ---------- Abacus：访问次数，每次调用 +1 ---------- */
  function abacusHit(key) {
    if (!window.fetch) return Promise.resolve(null);
    var opt = { credentials: 'omit', cache: 'no-store' };
    var ctrl = null, timer = null;
    if (window.AbortController) {
      ctrl = new AbortController();
      opt.signal = ctrl.signal;
      timer = setTimeout(function () { try { ctrl.abort(); } catch (e) {} }, 4000);
    }
    return fetch(ABACUS + '/hit/' + NS + '/' + encodeURIComponent(key), opt)
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (timer) clearTimeout(timer);
        var n = parseInt(d && d.value, 10);
        return isFinite(n) ? n : null;
      })
      .catch(function () { if (timer) clearTimeout(timer); return null; });
  }

  /* ---------- 上报事件：直接打像素，不依赖 count.js ---------- */
  function ping(name, title) {
    try {
      var q = '?p=' + encodeURIComponent(name) +
              '&t=' + encodeURIComponent(title || name) +
              '&e=1&b=0&r=' + encodeURIComponent(location.href);
      var img = new Image(1, 1);
      img.src = GC + '/count' + q + '&_=' + Date.now();
      img.onload = img.onerror = function () { img = null; };
    } catch (e) { /* 统计失败不能影响页面 */ }
  }

  /* ---------- 当前书 slug ---------- */
  function bookSlug() {
    var b = document.body || {};
    if (b.dataset && b.dataset.slug) return b.dataset.slug;
    var m = location.pathname.match(/\/books\/([^/]+)\//);
    return m ? m[1] : null;
  }

  function isMainDetail() {
    return /\/combined\.html$/.test(location.pathname);
  }

  /* 同一会话同一本只报一次事件（PV 的 +1 不受此限制，那是「访问次数」） */
  function once(name) {
    try {
      var k = '__wr_ev_' + name;
      if (sessionStorage.getItem(k)) return false;
      sessionStorage.setItem(k, '1');
      return true;
    } catch (e) { return true; }
  }

  function trackBook(slug) {
    if (!slug || !isMainDetail()) return;
    var name = EVENT_PREFIX + slug;
    if (!once(name)) return;
    var title = (document.body && document.body.dataset && document.body.dataset.title) || slug;
    ping(name, '详情页·打开：' + title);
  }

  /* ---------- 样式 ---------- */
  function ensureStyles() {
    if (document.getElementById('wrVisitStyle')) return;
    var s = document.createElement('style');
    s.id = 'wrVisitStyle';
    s.textContent = [
      '#wrVisit{margin:30px auto 12px;padding:0 16px;max-width:820px;display:flex;gap:10px;flex-wrap:wrap;justify-content:center;',
      'font:14px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;color:#8a8f98}',
      '#wrVisit .wr-card{display:flex;align-items:baseline;gap:6px;padding:8px 15px;border-radius:999px;',
      'border:1px solid rgba(127,127,127,.24);background:rgba(127,127,127,.07)}',
      '#wrVisit .wr-label{font-size:12px;opacity:.75;letter-spacing:.04em;margin-right:2px}',
      '#wrVisit b{font-size:17px;font-weight:700;color:#e0b26b;font-variant-numeric:tabular-nums}',
      '#wrVisit .wr-unit{font-size:12px;opacity:.8}',
      '#wrVisit .wr-sep{font-size:12px;opacity:.35;margin:0 1px}',
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
    if (e && v != null) e.textContent = v;
  }

  /* ---------- 首页：把「次访问」补上（内联脚本只填了访客数） ----------
     不读 DOM，自己取一次 GoatCounter —— 内联脚本的 fetch 是异步的，
     直接读 gc_site_uv_num 很可能还是占位符「–」，会把下界算成 0。 */
  function fillHomePv() {
    gcStat('/TOTAL').then(function (uv) {
      if (uv != null) put('gc_site_uv_num', String(uv));
      abacusHit('site').then(function (n) {
        if (n != null) put('gc_site_pv_num', String(n + (uv || 0)));
        else if (uv != null) put('gc_site_pv_num', String(uv));
      });
    });
  }

  /* ---------- 主流程 ---------- */
  function init() {
    var hasSite = !!(document.getElementById('gc_site_pv_num') || document.getElementById('gc_site_uv_num'));

    if (hasSite) {
      /* 首页有自己的内联脚本填访客数，这里补「次访问」 */
      fillHomePv();
      return;
    }

    var slug = bookSlug();
    if (!slug) return;

    ensureBadge();
    trackBook(slug);

    var uvSite = null, uvBook = null;

    gcStat('/TOTAL').then(function (n) {
      uvSite = n;
      put('wr_site_uv', n == null ? null : String(n));
      abacusHit('site').then(function (v) {
        if (v != null) put('wr_site_pv', String(v + (uvSite || 0)));
        else if (uvSite != null) put('wr_site_pv', String(uvSite));   /* 降级：至少不空 */
      });
    });

    gcStat('/' + EVENT_PREFIX + slug).then(function (n) {
      uvBook = n;
      put('wr_book_uv', n == null ? null : String(n));
      if (!isMainDetail()) return;   /* 子页面不 +1，避免一次阅读被算多次 */
      abacusHit('book-' + slug).then(function (v) {
        if (v != null) put('wr_book_pv', String(v + (uvBook || 0)));
        else if (uvBook != null) put('wr_book_pv', String(uvBook));
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
