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

  /* ── 章节数搬到卡片右下 ─────────────────────────────────────────
     原来「34 章 / 790 条」在书名下面独占一行、靠左，白吃一行高度；
     挪到 card-foot 右侧后：日期在右上、章节数在右下，元信息连成一条右列，
     书名单独占中间，卡片也能矮掉一行（瀑布流靠这个错落）。 */
  var META_RE = /^\s*[\d,]+\s*章(\s*\/\s*[\d,]+\s*条)?\s*$/;

  function moveMeta() {
    var cards = document.querySelectorAll('.archive-card');
    for (var i = 0; i < cards.length; i++) {
      var card = cards[i];
      if (card.querySelector('.card-meta')) continue;
      var foot = card.querySelector('.card-foot');
      if (!foot) continue;
      var ps = card.querySelectorAll('p');
      for (var j = 0; j < ps.length; j++) {
        var p = ps[j];
        // 只搬纯元信息；描述型段落（系列 / 归档卡）留在原位，别把正文塞进底栏
        if (!META_RE.test((p.textContent || '').trim())) continue;
        p.classList.add('card-meta');
        var more = foot.querySelector('.card-more');
        foot.insertBefore(p, more || null);
        break;
      }
    }
  }

  /* ── 卡片封面（一排一 / 一排二才显示，一排三隐藏） ──────────────
     库里目前没有书籍封面图（只有 epub），所以默认渲染「按 slug 哈希上色的占位封面 +
     书名」，让用户先看到带封面的版式效果。若日后把真封面放到 assets/covers/<slug>.jpg，
     <img> 会自动盖上去、占位层透明退场（onerror 移除）。 */
  function hashHue(s) {
    var h = 0;
    s = s || '';
    for (var i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) % 360;
    return h;
  }

  function addCovers() {
    var cards = document.querySelectorAll('.archive-card');
    for (var i = 0; i < cards.length; i++) {
      var card = cards[i];
      if (card.querySelector('.card-cover')) continue;
      var slug = card.dataset.slug || '';
      var h3 = card.querySelector('h3');
      var title = ((h3 ? h3.textContent : '') || '').trim();
      var cover = document.createElement('div');
      cover.className = 'card-cover';
      cover.style.setProperty('--ch', hashHue(slug || title || String(i)) + 'deg');
      if (title) {
        var t = document.createElement('span');
        t.className = 'card-cover-title';
        // 只当「书封题字」用：去掉书名号等前导标点后取前两个字，完整书名在下方 h3
        t.textContent = title.replace(/^[\s《〈“"'「【·—-]+/, '').slice(0, 2);
        cover.appendChild(t);
      }
      if (slug) {
        var img = document.createElement('img');
        img.className = 'card-cover-img';
        img.loading = 'lazy';
        img.alt = title;
        img.src = 'assets/covers/' + slug + '.jpg';
        img.addEventListener('error', function () { this.remove(); });
        cover.appendChild(img);
      }
      // 把除封面外的所有子节点（含隐藏的 ⋯ 菜单）包进 card-body，
      // 方便「封面置顶（一排二）/ 封面置左（一排一）」两种版式切换
      var body = document.createElement('div');
      body.className = 'card-body';
      while (card.firstChild) body.appendChild(card.firstChild);
      card.appendChild(cover);
      card.appendChild(body);
    }
  }

  function boot() {
    moveMeta();
    addCovers();
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
