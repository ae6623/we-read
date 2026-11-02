/* home-card.js — 卡片操作区（收藏 / 分享）
 *
 * 每张卡右下角一个 ⋯，点开是「收藏 / 分享」。
 * 收藏只存本地（localStorage `rd-fav`），不动服务端；分享优先调系统面板，
 * 不支持就复制链接。没有依赖，失败都静默降级。
 *
 * 为什么菜单打开时要挂到 <body>：卡片 hover 有 transform，fixed 会退化成
 * 「相对卡片定位」，菜单位置就全乱了；挂到 body 才是真正的视口坐标。
 */
(function () {
  'use strict';

  var KEY = 'rd-fav';
  var items = [];

  function load() {
    try {
      var v = JSON.parse(localStorage.getItem(KEY) || '[]');
      return Array.isArray(v) ? v : [];
    } catch (e) { return []; }
  }
  function save(list) {
    try { localStorage.setItem(KEY, JSON.stringify(list)); } catch (e) {}
  }

  function track(p, t) { if (window.rdTrack) window.rdTrack(p, t); }

  function titleOf(card) {
    var h = card.querySelector('h3');
    return ((h ? h.textContent : '') || '').trim().slice(0, 40) || keyOf(card);
  }

  function keyOf(card) {
    if (card.dataset.slug) return card.dataset.slug;
    var a = card.querySelector('.card-title-link, .book-jd-link, h3 a');
    return a ? a.getAttribute('href') : (card.querySelector('h3') || {}).textContent || '';
  }

  var toastEl, toastTimer;
  function toast(msg) {
    if (!toastEl) {
      toastEl = document.createElement('div');
      toastEl.className = 'rd-toast';
      toastEl.setAttribute('role', 'status');
      toastEl.setAttribute('aria-live', 'polite');
      document.body.appendChild(toastEl);
    }
    toastEl.textContent = msg;
    toastEl.classList.add('is-on');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.classList.remove('is-on'); }, 1800);
  }

  function closeAll(except) {
    items.forEach(function (it) {
      if (it === except) return;
      it.menu.hidden = true;
      it.more.setAttribute('aria-expanded', 'false');
    });
  }

  function paint(it, fav) {
    var btn = it.menu.querySelector('[data-act="fav"]');
    if (btn) {
      btn.setAttribute('aria-checked', fav ? 'true' : 'false');
      var s = btn.querySelector('span');
      if (s) s.textContent = fav ? '已收藏' : '收藏';
    }
    it.card.classList.toggle('is-fav', fav);
  }

  function share(it) {
    var a = it.card.querySelector('.card-title-link, .book-jd-link, h3 a');
    var title = ((it.card.querySelector('h3') || {}).textContent || document.title).trim();
    var url = a ? new URL(a.getAttribute('href'), location.href).href : location.href;

    if (navigator.share) {
      navigator.share({ title: title, url: url }).catch(function () {});
      return;
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(
        function () { toast('链接已复制'); },
        function () { toast('复制失败，可长按书名复制'); }
      );
      return;
    }
    toast(url);
  }

  function boot() {
    var favs = load();

    items = Array.prototype.slice.call(document.querySelectorAll('.archive-card'))
      .map(function (card) {
        var more = card.querySelector('.card-more');
        var menu = card.querySelector('.card-menu');
        return more && menu ? { card: card, more: more, menu: menu, key: keyOf(card) } : null;
      })
      .filter(Boolean);

    items.forEach(function (it) {
      var card = it.card, more = it.more, menu = it.menu, k = it.key;

      paint(it, favs.indexOf(k) >= 0);

      function place() {
        var r = more.getBoundingClientRect();
        // 按钮滚出视口就别挂着，避免菜单飘在空白处
        if (r.bottom < 4 || r.top > window.innerHeight - 4) {
          menu.hidden = true;
          more.setAttribute('aria-expanded', 'false');
          return;
        }
        var mh = menu.offsetHeight, gap = 6;
        var below = window.innerHeight - r.bottom;
        var top = below > mh + gap + 8 ? r.bottom + gap : r.top - mh - gap;
        top = Math.max(8, Math.min(top, window.innerHeight - mh - 8));
        menu.style.top = top + 'px';
        menu.style.bottom = 'auto';           // CSS 里有兜底 bottom，不清掉会把高度压成 0
        menu.style.right = Math.max(8, window.innerWidth - r.right) + 'px';
      }
      menu._place = place;

      more.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var open = menu.hidden;
        closeAll(it);
        if (open && menu.parentNode !== document.body) document.body.appendChild(menu);
        menu.hidden = !open;
        more.setAttribute('aria-expanded', open ? 'true' : 'false');
        if (open) {
          place();
          // 页面开了平滑滚动时，点按瞬间拿到的位置可能是动画中间态，补两帧校正
          requestAnimationFrame(place);
          setTimeout(place, 240);
          var first = menu.querySelector('button');
          if (first) first.focus({ preventScroll: true });
        }
      });

      menu.addEventListener('click', function (e) {
        var b = e.target.closest ? e.target.closest('button[data-act]') : null;
        if (!b) return;
        e.stopPropagation();
        var act = b.getAttribute('data-act');
        if (act === 'fav') {
          var list = load();
          var i = list.indexOf(k);
          var on = i < 0;
          if (on) { list.push(k); paint(it, true); toast('已收藏'); }
          else { list.splice(i, 1); paint(it, false); toast('已取消收藏'); }
          save(list);
          track('/ev/fav/' + (on ? 'on' : 'off') + '/' + k, (on ? '收藏 · ' : '取消收藏 · ') + titleOf(it.card));
        } else if (act === 'share') {
          share(it);
          track('/ev/share/' + k, '分享 · ' + titleOf(it.card));
        }
        menu.hidden = true;
        more.setAttribute('aria-expanded', 'false');
      });
    });

    document.addEventListener('click', function (e) {
      if (!e.target.closest || !e.target.closest('.card-more, .card-menu')) closeAll(null);
    });

    /* 点书名 = 打开这本书 → 上报一条，用来算「曝光→打开」的转化 */
    document.addEventListener('click', function (e) {
      var a = e.target.closest ? e.target.closest('.card-title-link, .book-jd-link') : null;
      if (!a) return;
      var card = a.closest ? a.closest('.archive-card') : null;
      var k = card ? keyOf(card) : a.getAttribute('href');
      track('/ev/open/' + k, '打开 · ' + (card ? titleOf(card) : k));
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeAll(null);
    });

    // 菜单是 fixed 的：滚动/缩放时跟着按钮走，而不是直接收起
    //（收起会让「点菜单项时浏览器微滚动」变成点不中）
    function follow() {
      items.forEach(function (it) {
        if (!it.menu.hidden) it.menu._place();
      });
    }
    window.addEventListener('scroll', follow, { passive: true });
    window.addEventListener('resize', follow);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
