/* home-theme.js — 首页阅读偏好（字号 / 段距 / 四主题）
 *
 * 与书页共用 localStorage `rd-cfg`：一处调整，两处生效。
 * 默认值与书页区分（书页夜间、首页米白），但用户主动选过就都听用户的。
 * 样式真源在 assets/css/home-theme.css，这里只负责应用与持久化。
 */
(function () {
  'use strict';

  var KEY = 'rd-cfg';
  var FS = [0.72, 0.74, 0.76, 0.78, 0.80, 0.83, 0.86, 0.90, 0.94, 1.00, 1.08];
  var PM = [0.55, 1, 1.5];
  var DEF_THEME = 'cream', DEF_FS = 0.76, DEF_PM = 1;
  var CFG_VER = 4;           // 默认值变过就升版本，见 boot() 里的迁移
  var THEME_COLOR = { cream: '#f6f3ed', light: '#ffffff', green: '#cfe8d2', dark: '#15171a' };

  var d = document.documentElement;

  function q(s, r) { return (r || document).querySelector(s); }
  function qa(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }

  function load() {
    try { return JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch (e) { return {}; }
  }
  function save(c) { try { localStorage.setItem(KEY, JSON.stringify(c)); } catch (e) {} }

  function idx(arr, v, def) {
    var f = parseFloat(v);
    if (arr.indexOf(f) >= 0) return arr.indexOf(f);
    var best = 0, bd = Infinity;
    arr.forEach(function (x, j) { var dd = Math.abs(x - (isFinite(f) ? f : def)); if (dd < bd) { bd = dd; best = j; } });
    return best;
  }

  function boot() {
    var c = load();
    /* 老配置迁移：字号默认 .80 → .76、列数默认 3 → 2（第 15 批改回一排二）。
       存着旧默认值的人其实没主动选过，跟着新默认走；自己调过的不动。只迁一次。 */
    if ((c.ver || 1) < CFG_VER) {
      if (c.fs === 0.8) c.fs = DEF_FS;
      if (c.cols === 3) c.cols = 2;
      c.ver = CFG_VER;
      if (Object.keys(c).length) save(c);
    }
    var fi = idx(FS, c.fs, DEF_FS);
    var pi = idx(PM, c.pm, DEF_PM);
    if (c.pm == null) pi = -1;              // 未设置 → 用首页自己的紧凑档

    var panel = q('#rdPanel'), fab = q('#rdFab');
    var tc = q('meta[name="theme-color"]');

    // 只落盘用户真正动过的字段：只调字号的人，主题不该被顺手写成 cream
    function apply(touch) {
      var th = c.theme || DEF_THEME;
      d.setAttribute('data-theme', th);
      if (tc) tc.setAttribute('content', THEME_COLOR[th] || '#f6f3ed');
      d.style.setProperty('--fs', FS[fi]);
      d.style.setProperty('--pm', pi < 0 ? DEF_PM : PM[pi]);
      if (touch) {
        if (touch.fs) c.fs = FS[fi];
        if (touch.pm && pi >= 0) c.pm = PM[pi];
        save(c);
      }
      qa('button[data-rd^="th-"]', panel).forEach(function (b) {
        b.setAttribute('aria-pressed', b.getAttribute('data-rd') === 'th-' + th ? 'true' : 'false');
      });
      // 段距三档也要标出当前档，否则看不出「紧/中/松」现在停在哪
      var pmKeys = ['pm-', 'pm0', 'pm+'];
      qa('button[data-rd^="pm"]', panel).forEach(function (b) {
        b.setAttribute('aria-pressed', pmKeys.indexOf(b.getAttribute('data-rd')) === pi ? 'true' : 'false');
      });
    }

    if (panel && fab) {
      fab.onclick = function (e) { e.stopPropagation(); panel.hidden = !panel.hidden; };
      document.addEventListener('click', function (e) {
        if (!panel.hidden && !panel.contains(e.target) && e.target.id !== 'rdFab') panel.hidden = true;
      });
      document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && !panel.hidden) panel.hidden = true;
      });
      panel.addEventListener('click', function (e) {
        var b = e.target.closest ? e.target.closest('button[data-rd]') : null;
        if (!b) return;
        var k = b.getAttribute('data-rd'), touch = {};
        if (k === 'fs-') { fi = Math.max(0, fi - 1); touch.fs = 1; }
        else if (k === 'fs+') { fi = Math.min(FS.length - 1, fi + 1); touch.fs = 1; }
        else if (k === 'pm-') { pi = 0; touch.pm = 1; }
        else if (k === 'pm0') { pi = 1; touch.pm = 1; }
        else if (k === 'pm+') { pi = 2; touch.pm = 1; }
        else if (k.indexOf('th-') === 0) { c.theme = k.slice(3); touch.theme = 1; }
        apply(touch);
      });
    }

    // ── 列数：一排二（默认）→ 一排三 → 一排一，点一下循环 ──────────
    (function () {
      var btn = q('#rdCols');
      if (!btn) return;
      var ORDER = ['2', '3', '1'];
      var CN = { 1: '一', 2: '二', 3: '三' };
      function current() {
        var v = d.getAttribute('data-cols');
        return ORDER.indexOf(v) >= 0 ? v : '2';
      }
      function paint() {
        var cur = current();
        var next = ORDER[(ORDER.indexOf(cur) + 1) % ORDER.length];
        btn.setAttribute('aria-pressed', cur === '1' ? 'true' : 'false');
        btn.title = '当前一排' + CN[cur] + ' · 点按切一排' + CN[next];
      }
      function set(v, touch) {
        d.setAttribute('data-cols', v);
        if (touch) { c.cols = parseInt(v, 10); save(c); }
        paint();
      }

      if (c.cols === 1 || c.cols === 2 || c.cols === 3) set(String(c.cols), false);
      else set('2', false);

      btn.addEventListener('click', function () {
        set(ORDER[(ORDER.indexOf(current()) + 1) % ORDER.length], true);
      });
    })();

    // 首次进入只应用、不写盘：用户没选过就保持默认，别把「默认」变成「用户偏好」
    apply(null);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
