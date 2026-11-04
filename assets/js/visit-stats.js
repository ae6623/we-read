/*!
 * visit-stats.js — we-read 访问统计徽章（首页 + 书籍详情页通用）
 * v2 · 2026-11-04
 *
 * 数据源：GoatCounter（复用已有 ae6623 账号），零后端、零新服务。
 *
 * ── v1 的两个致命 bug（v2 已修）─────────────────────────────
 * 1) 事件名不能以 / 开头。
 *    GoatCounter 官方文档：「The path doubles as the event name. This cannot
 *    have / as the first character.」v1 用 /detail/view/<slug> 上报，服务端
 *    直接丢弃，所以详情页永远是 0、也从来没有 +1。
 *    → v2 改用 detail-view-<slug>，实测可正常入库、可读回。
 *
 * 2) 上报依赖 gc.zgo.at 的 count.js。
 *    国内访问 gc.zgo.at 经常超时（实测直连 3/3 超时），count.js 加载不到就
 *    没有 window.goatcounter，事件静默丢失。
 *    → v2 不再依赖 count.js，直接向 ae6623.goatcounter.com/count 打像素。
 *      该域名可取数（/counter/TOTAL.json 能通），写数同理。
 *
 * ── 关于数字口径（必须知道）─────────────────────────────────
 * counter API 只返回 count（= 去重访客数），count_unique 是兼容字段、值相同，
 * 官方明确「should not be used for new code」。前端拿不到独立的 PV / UV。
 * 所以只显示一个数，标签写「位访客 / 人读过」，不再摆两个一样的数。
 * 另：该接口 CDN 强缓存（最长 4 小时），刚访问完读数不会立刻 +1，属正常。
 *
 * ── 行为 ─────────────────────────────────────────────────
 *  - 首页已有 #gc_site_pv_num / #gc_site_uv_num → 只回填 pv，并隐藏重复的 uv
 *  - 详情页 → body 末尾自动生成徽章：「本站 N 位访客」「本书 N 人读过」
 *  - 只在主详情页（combined.html）上报一次，overview/outline/mindmap 等
 *    子页面只读不报，避免一次阅读被记成好几次
 *
 * 引入方式（放在 </body> 前，相对路径按文件深度调整）：
 *   <script src="../../../assets/js/visit-stats.js?v=20261104b" defer></script>
 */

(function () {
  'use strict';

  var CODE = 'ae6623';
  var BASE = 'https://' + CODE + '.goatcounter.com';
  var COUNTER = BASE + '/counter';
  var EVENT_PREFIX = 'detail-view-';   /* 关键：不能以 / 开头 */

  /* ---------- 取数 ---------- */
  function stat(path) {
    return fetch(COUNTER + path + '.json', { credentials: 'omit', cache: 'no-store' })
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

  /* ---------- 上报：直接打像素，不依赖 count.js ---------- */
  function ping(name, title) {
    try {
      var q = '?p=' + encodeURIComponent(name) +
              '&t=' + encodeURIComponent(title || name) +
              '&e=1&b=0&r=' + encodeURIComponent(location.href);
      var img = new Image(1, 1);
      img.src = BASE + '/count' + q + '&_=' + Date.now();
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

  /* ---------- 去重：同一会话同一本只报一次 ---------- */
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
      '#wrVisit .wr-card{display:flex;align-items:baseline;gap:7px;padding:8px 15px;border-radius:999px;',
      'border:1px solid rgba(127,127,127,.24);background:rgba(127,127,127,.07)}',
      '#wrVisit .wr-label{font-size:12px;opacity:.75;letter-spacing:.04em}',
      '#wrVisit b{font-size:17px;font-weight:700;color:#e0b26b;font-variant-numeric:tabular-nums}',
      '#wrVisit .wr-unit{font-size:12px;opacity:.8}',
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
        '<b id="wr_site">–</b><span class="wr-unit">位访客</span>' +
      '</div>' +
      '<div class="wr-card">' +
        '<span class="wr-label">本书</span>' +
        '<b id="wr_book">–</b><span class="wr-unit">人读过</span>' +
      '</div>';
    document.body.appendChild(el);
    return el;
  }

  function put(id, v) {
    var e = document.getElementById(id);
    if (e) e.textContent = v;
  }

  /* ---------- 首页：只留一个数，隐藏重复的「位访客」 ---------- */
  function hideDupUv() {
    var nodes = document.querySelectorAll('.visit-badge-uv');
    for (var i = 0; i < nodes.length; i++) nodes[i].style.display = 'none';
  }

  /* ---------- 主流程 ---------- */
  function init() {
    var hasSite = !!(document.getElementById('gc_site_pv_num') || document.getElementById('gc_site_uv_num'));
    var slug = bookSlug();

    /* 全站数：首页与详情页都要 */
    stat('/TOTAL').then(function (n) {
      var v = num(n);
      if (hasSite) {
        put('gc_site_pv_num', v);
        hideDupUv();
      } else if (slug) {
        put('wr_site', v);
      }
    });

    if (!slug || hasSite) return;   /* 首页到此为止 */

    ensureBadge();
    trackBook(slug);

    stat('/' + EVENT_PREFIX + slug).then(function (n) {
      put('wr_book', num(n));
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
