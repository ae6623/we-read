/*!
 * series-units.js — 「系列」Tab 底部套装单册卡片。
 *
 * 数据按系列拆成 assets/data/series-units/<slug>.json，
 * 展开时才 fetch，首页体积不随册数增长。
 */
(function () {
  'use strict';

  var BASE = 'assets/data/series-units/';

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function card(u) {
    var href = u.deep || ('reading-notes/books/' + u.slug + '/outline.html');
    var meta = [];
    if (u.author) meta.push(u.author);
    if (u.chapters) meta.push(u.chapters + ' 章 / ' + u.points + ' 条');
    return '<article class="unit-card">' +
      '<h3><a href="' + esc(href) + '" data-weread-id="' + esc(u.bookId) + '">' + esc(u.title) + '</a></h3>' +
      (meta.length ? '<p class="unit-meta">' + esc(meta.join('　·　')) + '</p>' : '') +
      '<a class="unit-link" href="reading-notes/books/' + esc(u.slug) + '/outline.html">章节大纲 →</a>' +
      '</article>';
  }

  function load(d) {
    var state = d.getAttribute('data-state');
    if (state === 'loading' || state === 'done') return;
    var grid = d.querySelector('.set-units-grid');
    var slug = d.getAttribute('data-units');
    d.setAttribute('data-state', 'loading');
    grid.innerHTML = '<p class="unit-loading">展开中…</p>';
    fetch(BASE + slug + '.json', { credentials: 'same-origin' })
      .then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      })
      .then(function (j) {
        grid.innerHTML = j.units.map(card).join('');
        d.setAttribute('data-state', 'done');
        if (window.WereadLink) window.WereadLink.bind(grid);
      })
      .catch(function () {
        grid.innerHTML = '<p class="unit-loading">没加载出来，<a href="reading-notes/series/' +
          esc(slug) + '/index.html">直接看分册清单 →</a></p>';
        d.setAttribute('data-state', 'error');
      });
  }

  function init() {
    var list = document.querySelectorAll('.set-group[data-units]');
    if (!list.length) return;
    Array.prototype.forEach.call(list, function (d) {
      if (d.hasAttribute('open')) load(d);
      d.addEventListener('toggle', function () {
        if (d.open) load(d);
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
