/* ============================================================
   weights.js — 通用权重引擎（外置 JSON 驱动，任意元素可加权）

   设计目标（2026-11-13）：
   - 权重规则全部放在 assets/data/weights.json，改配置不改代码。
   - 支持任意作用域：书籍卡片(home) / 系列模块(series) / 详情模块(modules)
     / 任意 CSS 容器(elements)，新增作用域只要往 JSON 里加一段。
   - 三种命中维度：类目(cat1/cat2) · 书名/slug 关键词 · 任意 data-* 属性。
   - 单条规则可设 priority（高者胜），同优先级取 |weight| 大者。

   分桶语义（weight>0 置顶 / =0 中间 / <0 沉底）：
     置顶池按 weight 降序；中间池保持传入顺序（首页由 home-feed 随机打散，
     即用户要的「其他随机」）；沉底池按 weight 升序（越负越靠后）。
   稳定排序：用 index 作 tie-break，不依赖浏览器 sort 稳定性。

   对外 API（window.WeReadWeights）：
     sort(list, scope)      数组重排（供 home-feed.scatter 调用）
     applyDOM(scope)        容器级 DOM 重排（供 series / elements 调用）
     onReady(cb)            配置与类目数据就绪后回调（可多次、幂等）
     ready / config / cats  状态只读
   ============================================================ */
(function () {
  'use strict';

  // 相对路径优先（同源、本地也跑得通），失败再退回 CDN 绝对地址。
  // 站点所有页面都在站根下一层内，'assets/…' 在 /index.html 下解析为 /assets/…
  var CFG_URL = 'assets/data/weights.json?v=20261113b';
  var CFG_URL_ALT = 'https://cdn.js-dev.cn/assets/data/weights.json?v=20261113b';
  var CATS_URL = 'assets/data/book-cats.json?v=20261113b';
  var CATS_URL_ALT = 'https://cdn.js-dev.cn/assets/data/book-cats.json?v=20261113b';

  var config = null, cats = { books: {}, titles: {} };
  var ready = false, cbs = [];

  function fetchJSON(url, cb, alt) {
    var done = false;
    function ok(d) { if (!done) { done = true; cb(d || null); } }
    try {
      fetch(url, { cache: 'no-cache' })
        .then(function (r) { return r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status)); })
        .then(function (d) { ok(d); })
        .catch(function () {
          if (!alt) return ok(null);
          try {
            fetch(alt, { cache: 'no-cache' })
              .then(function (r) { return r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status)); })
              .then(function (d) { ok(d); })
              .catch(function () { ok(null); });
          } catch (e2) { ok(null); }
        });
    } catch (e) { ok(null); }
  }

  function fireReady() {
    if (ready) return;
    ready = true;
    try { applyDOM('series'); } catch (e) {}
    try { applyDOM('elements'); } catch (e) {}
    try { watchSeries(); } catch (e) {}
    var list = cbs.slice(); cbs.length = 0;
    list.forEach(function (fn) { try { fn(); } catch (e) {} });
  }

  function onReady(cb) {
    if (typeof cb !== 'function') return;
    if (ready) { try { cb(); } catch (e) {} } else cbs.push(cb);
  }

  /* ── 规则匹配 ───────────────────────────────────────────────── */
  function norm(s) {
    return String(s || '').toLowerCase().replace(/[\s\u3000《》「」·,，.。:：]/g, '');
  }

  function catOf(card) {
    var slug = card.getAttribute && card.getAttribute('data-slug');
    if (slug && cats.books[slug]) return cats.books[slug];
    var t = card.querySelector && card.querySelector('.card-title-link, h3 a, h3');
    var key = norm(t ? t.textContent : '');
    if (key && cats.titles[key]) return cats.titles[key];
    return ['', ''];
  }

  function matchOne(m, card) {
    if (!m) return false;
    var slug = (card.getAttribute && card.getAttribute('data-slug')) || '';
    var text = norm((card.getAttribute && card.getAttribute('data-search')) || '') +
               ' ' + norm(card.textContent || '') + ' ' + norm(slug);
    var pair = catOf(card);

    if (m.cat1 && m.cat1.length && m.cat1.indexOf(pair[0]) < 0) return false;
    if (m.cat2 && m.cat2.length && m.cat2.indexOf(pair[1]) < 0) return false;
    if (m.slug_eq && slug !== m.slug_eq) return false;
    if (m.slug_any) {
      var s = norm(slug);
      if (!m.slug_any.some(function (k) { return s.indexOf(norm(k)) >= 0; })) return false;
    }
    if (m.text_any) {
      if (!m.text_any.some(function (k) { return text.indexOf(norm(k)) >= 0; })) return false;
    }
    if (m.attr) {
      var keys = Object.keys(m.attr);
      for (var i = 0; i < keys.length; i++) {
        var v = card.getAttribute && card.getAttribute(keys[i]);
        if (v !== m.attr[keys[i]]) return false;
      }
    }
    // 一个 match 里若什么条件都没有，不作为命中（避免空规则全中）
    return !!(m.cat1 || m.cat2 || m.slug_eq || m.slug_any || m.text_any || m.attr);
  }

  function scoreOf(card, scope) {
    var sc = config && config.scopes && config.scopes[scope];
    if (!sc || sc.enabled === false || !sc.rules || !sc.rules.length) return 0;
    var best = null;
    sc.rules.forEach(function (r) {
      if (!matchOne(r.match, card)) return;
      var p = r.priority || 0, w = +r.weight || 0;
      if (!best || p > best.p || (p === best.p && Math.abs(w) > Math.abs(best.w))) {
        best = { p: p, w: w };
      }
    });
    return best ? best.w : 0;
  }

  /* ── 数组分桶重排（稳定） ───────────────────────────────────── */
  function bucket(list, scope) {
    var top = [], mid = [], bottom = [];
    for (var i = 0; i < list.length; i++) {
      var w = scoreOf(list[i], scope), rec = { el: list[i], w: w, i: i };
      if (w > 0) top.push(rec);
      else if (w < 0) bottom.push(rec);
      else mid.push(rec);
    }
    top.sort(function (a, b) { return b.w - a.w || a.i - b.i; });
    bottom.sort(function (a, b) { return a.w - b.w || a.i - b.i; });
    return top.concat(mid, bottom).map(function (r) { return r.el; });
  }

  function sort(list, scope) {
    if (!ready || !config) return list;          // 配置未到：保持原序（纯随机）
    var sc = config.scopes && config.scopes[scope || 'home'];
    if (!sc || sc.enabled === false) return list;
    return bucket(list, scope || 'home');
  }

  /* ── 容器级 DOM 重排（系列 / 任意元素） ─────────────────────── */
  var applying = false;
  function applyDOM(scope) {
    if (!config || applying) return 0;
    var sc = config.scopes && config.scopes[scope];
    if (!sc || sc.enabled === false || !sc.containers) return 0;
    applying = true;
    var moved = 0;
    try {
      sc.containers.forEach(function (box) {
        var root = document.querySelector(box.selector);
        if (!root) return;
        var items = [].slice.call(root.children).filter(function (n) {
          return n.matches && n.matches(box.item);
        });
        if (items.length < 2) return;
        // 用临时作用域装本容器的规则
        var virt = '_c_' + scope;
        config.scopes[virt] = { enabled: true, rules: box.rules || [] };
        var ordered = bucket(items, virt);
        delete config.scopes[virt];
        // 顺序已正确就不动 DOM（幂等，避免 MutationObserver 死循环）
        var same = true;
        for (var i = 0; i < ordered.length; i++) {
          if (ordered[i] !== items[i]) { same = false; break; }
        }
        if (same) return;
        var frag = document.createDocumentFragment();
        ordered.forEach(function (n) { frag.appendChild(n); });
        root.insertBefore(frag, root.firstChild);
        moved += ordered.length;
      });
    } finally {
      applying = false;
    }
    return moved;
  }

  /* 系列 Tab 里 homepage-reading.js 会异步 fetch series.json 后动态插入
     系列组；插入完成后轻游记可能被挤下去。监听容器子节点变化，防抖重排，
     保证「权重置顶」无论搬卡何时发生都成立。 */
  function watchSeries() {
    if (!config || typeof MutationObserver !== 'function') return;
    var panel = document.getElementById('reading-panel-series');
    if (!panel) return;
    var t = 0;
    new MutationObserver(function () {
      if (applying) return;
      clearTimeout(t);
      t = setTimeout(function () { applyDOM('series'); }, 120);
    }).observe(panel, { childList: true, subtree: true });
  }

  /* ── 初始化：两个 JSON 都到（或失败）即就绪 ─────────────────── */
  var got = 0;
  function done() { if (++got >= 2) fireReady(); }
  fetchJSON(CFG_URL, function (d) { config = d; done(); }, CFG_URL_ALT);
  fetchJSON(CATS_URL, function (d) {
    if (d) cats = { books: d.books || {}, titles: d.titles || {} };
    done();
  }, CATS_URL_ALT);

  window.WeReadWeights = {
    sort: sort,
    applyDOM: applyDOM,
    onReady: onReady,
    scoreOf: function (c, s) { return scoreOf(c, s || 'home'); },
    get ready() { return ready; },
    get config() { return config; },
    get cats() { return cats; }
  };
})();
