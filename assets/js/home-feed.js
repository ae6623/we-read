/* ============================================================
   home-feed.js — 书架瀑布流 + 分页 + 曝光埋点

   三件事：
   1. 瀑布流：卡片高度不一，用绝对定位按「当前最短列」摆放，
      只写 style 不动结构 —— 搜索/筛选那套（card.hidden）照旧有效。
   2. 分页：默认一页 15 张，下滑到底自动加载下一页，也可点按钮。
      未加载的卡只加 data-pg="off"（CSS 隐藏），不销毁 DOM。
   3. 曝光：卡片进入视口时按「页 / A·B·C 位」上报一次。

   为什么不用 CSS 多列：column-count 每次追加都会把已有卡片重新灌流
   一次，滚动到底加载时整屏会跳；绝对定位只影响新卡片。

   注意：homepage-reading.js 会在启动后把卡片在网格之间搬来搬去
   （系列分组），所以「这个网格有哪些卡」必须每次现算，不能快照。
   ============================================================ */
(function () {
  'use strict';

  var PAGE = 15;
  var BOOT = Date.now();
  var d = document.documentElement;
  var track = function (p, t) { if (window.rdTrack) window.rdTrack(p, t); };

  var LABEL = { whole: '全书视角', soon: '即将上线', series: '系列', archive: '归档' };
  var states = [];
  var pageSeen = {};
  var hasWM = typeof WeakMap === 'function';
  var meta = hasWM ? new WeakMap() : null;

  /* ── 曝光观察器 ────────────────────────────────────────────────── */
  var io = (typeof IntersectionObserver === 'function')
    ? new IntersectionObserver(function (entries) {
        for (var i = 0; i < entries.length; i++) {
          var e = entries[i];
          if (!e.isIntersecting) continue;
          io.unobserve(e.target);
          var m = hasWM ? meta.get(e.target) : null;
          if (!m || pageSeen[m.key]) continue;
          pageSeen[m.key] = 1;
          track('/ev/expose/' + m.pane + '/p' + m.page + '/' + m.slot,
            m.slot + ' 位曝光 · ' + (LABEL[m.base] || m.base) + ' 第 ' + m.page + ' 页 · ' + m.n + ' 张');
        }
      }, { rootMargin: '0px 0px -12% 0px', threshold: 0.34 })
    : null;

  function isCard(el) {
    return el && el.nodeType === 1 && el.classList && el.classList.contains('archive-card');
  }
  function kids(grid) {
    var out = [], ch = grid.children;
    for (var i = 0; i < ch.length; i++) if (isCard(ch[i])) out.push(ch[i]);
    return out;
  }
  function shownOf(c) {
    return !c.hidden && c.getAttribute('data-pg') !== 'off';
  }

  function paneOf(grid, idx) {
    var el = grid.parentElement, base = 'x';
    while (el && el !== document.body) {
      if (el.id) { base = el.id.replace(/^reading-panel-/, '').replace(/^panel-/, ''); break; }
      el = el.parentElement;
    }
    return { base: base, key: base + (idx ? '-' + idx : '') };
  }

  /* ── 瀑布流排版 ────────────────────────────────────────────────── */
  function layout(s) {
    var grid = s.grid;
    if (!s.pure) {                        // 混排网格（系列页有 .series-preview）交回 CSS 网格
      if (s.dirtyMixed) {
        for (var d0 = 0; d0 < s.cards.length; d0++) {
          s.cards[d0].style.position = '';
          s.cards[d0].style.width = '';
          s.cards[d0].style.left = '';
          s.cards[d0].style.top = '';
          s.cards[d0].style.margin = '';
        }
        grid.style.height = '';
        grid.style.position = '';
        s.dirtyMixed = false;
      }
      return;
    }
    var W = grid.clientWidth;
    if (!W) return;                       // 面板还藏在 display:none 里

    var cs = getComputedStyle(grid);
    var gx = parseFloat(cs.columnGap) || 12;
    var gy = parseFloat(cs.rowGap) || 12;
    var cols = d.getAttribute('data-cols') === '1' ? 1 : 2;
    var colW = (W - gx * (cols - 1)) / cols;
    if (colW <= 1) return;

    var cards = s.cards, vis = [], i, k;
    for (i = 0; i < cards.length; i++) if (shownOf(cards[i])) vis.push(cards[i]);

    grid.style.position = 'relative';

    // 1) 先统一定宽（同一批写入，只触发一次重排）
    for (i = 0; i < vis.length; i++) {
      vis[i].style.position = 'absolute';
      vis[i].style.width = colW + 'px';
      vis[i].style.margin = '0';
    }
    // 2) 再量高：宽度定下来后高度才是真的
    var hs = [];
    for (i = 0; i < vis.length; i++) hs.push(vis[i].offsetHeight);

    // 3) 依次放进当前最短的列
    var ys = [];
    for (k = 0; k < cols; k++) ys[k] = 0;
    var maxY = 0;
    for (i = 0; i < vis.length; i++) {
      var m = 0;
      for (k = 1; k < cols; k++) if (ys[k] < ys[m]) m = k;
      vis[i].style.left = (m * (colW + gx)) + 'px';
      vis[i].style.top = ys[m] + 'px';
      ys[m] += hs[i] + gy;
      if (ys[m] > maxY) maxY = ys[m];
    }
    grid.style.height = Math.max(0, maxY - gy) + 'px';
    watchFoot(s);
  }

  /* ── 分页写回 DOM ──────────────────────────────────────────────── */
  function applyPg(s) {
    for (var i = 0; i < s.cards.length; i++) {
      if (i < s.shown) s.cards[i].removeAttribute('data-pg');
      else s.cards[i].setAttribute('data-pg', 'off');
    }
  }

  function paintFoot(s) {
    if (!s.foot) return;
    var left = s.cards.length - s.shown;
    if (left <= 0) {
      s.foot.innerHTML = '<p class="feed-end">— 全部 ' + s.cards.length + ' 本 —</p>';
      s.foot.classList.add('is-end');
      return;
    }
    var label = '下滑继续 · 还有 ' + left + ' 本<span>（已显示 ' + s.shown + ' / ' + s.cards.length + '）</span>';
    s.foot.classList.remove('is-end');
    /* 有 IntersectionObserver 时页脚只是状态条：往下滑自动就加载了，
       摆个按钮反而永远点不到（它出现的瞬间就开始加载）。
       老浏览器没有观察器，才给一个真按钮当手动入口。 */
    if (typeof IntersectionObserver === 'function') {
      s.foot.innerHTML = '<p class="feed-note">' + label + '</p>';
      return;
    }
    s.foot.innerHTML = '<button type="button" class="feed-more">' + label + '</button>';
    s.foot.querySelector('.feed-more').addEventListener('click', function () { reveal(s, PAGE, 'click'); });
  }

  function makeFoot(s) {
    var foot = document.createElement('div');
    foot.className = 'feed-foot';
    s.grid.parentNode.insertBefore(foot, s.grid.nextSibling);
    s.foot = foot;
    s.watch = false;        // 等第一次排版完再挂观察器，见 watchFoot()
  }

  /* 为什么要等：卡片是绝对定位的，没排版前网格高度是 0，
     页脚就贴在顶部 → 观察器一挂上就判定「已进入视口」，立刻又加载一页。 */
  function watchFoot(s) {
    if (s.watch || !s.foot || typeof IntersectionObserver !== 'function') return;
    s.watch = true;
    new IntersectionObserver(function (es) {
      for (var j = 0; j < es.length; j++) {
        if (!es[j].isIntersecting) continue;
        var now = Date.now();
        // 首屏别急着加载：启动那几百毫秒里，上游脚本还在搬卡片、改 hidden，
        // 网格高度会短暂塌下去，页脚「假进入」视口。
        if (now - BOOT < 900) continue;
        // 首屏只给第一页：用户还没下滑就不续页（慢网下卡片重排会让页脚「假进入」视口）
        if (window.scrollY < 120 && s.shown <= PAGE) continue;
        if (now - s.auto < 320) continue;       // 别一口气全加载
        if (!nearFoot(s.foot)) continue;        // 回读一次真实位置再说
        s.auto = now;
        reveal(s, PAGE, 'auto');
      }
    }, { rootMargin: '240px 0px' }).observe(s.foot);
  }

  function nearFoot(el, margin) {
    margin = margin || 240;
    var r = el.getBoundingClientRect();
    return r.top < window.innerHeight + margin && r.bottom > -margin;
  }

  /* ── 加载下一页 ────────────────────────────────────────────────── */
  function reveal(s, n, reason) {

    if (s.shown >= s.cards.length) return;
    var from = s.shown;
    s.shown = Math.min(s.cards.length, s.shown + n);

    var page = Math.ceil(s.shown / PAGE);
    var slot = page <= 1 ? 'A' : (page <= 3 ? 'B' : 'C');
    var size = s.shown - from;

    for (var i = from; i < s.shown; i++) {
      var c = s.cards[i];
      c.removeAttribute('data-pg');
      if (io && hasWM) {
        meta.set(c, { pane: s.key, base: s.base, page: page, slot: slot, n: size, key: s.key + '|' + page });
        io.observe(c);
      }
    }

    track('/ev/load/' + s.key + '/p' + page + '/' + (reason || 'auto'),
      '加载第 ' + page + ' 页 · ' + (reason === 'click' ? '点按' : '自动') + ' · ' + size + ' 张');

    layout(s);
    paintFoot(s);
  }

  /* ── 建立/同步网格状态 ─────────────────────────────────────────── */
  function ensure(grid, idx) {
    for (var i = 0; i < states.length; i++) if (states[i].grid === grid) return states[i];
    var p = paneOf(grid, idx);
    var s = { grid: grid, key: p.key, base: p.base, cards: [], shown: PAGE, foot: null, auto: 0, pure: true, dirtyMixed: false };
    states.push(s);
    return s;
  }

  function syncOne(grid, idx, boot) {
    var s = ensure(grid, idx);
    var now = kids(grid);
    if (now.length === s.cards.length && !boot) return s;

    /* 只有「整格都是卡片」才做瀑布流 + 分页。
       系列页的网格里混着 .series-preview 导览块，绝对定位会把它们压叠在一起，
       这种网格保持原来的 CSS 网格排布，也不分页（本来就只有几十张）。 */
    var pure = now.length === grid.children.length;
    if (pure !== s.pure) { s.dirtyMixed = s.pure === true; s.pure = pure; }

    var grew = now.length > s.cards.length;
    s.cards = now;
    if (s.shown > now.length) s.shown = now.length;

    if (!pure) {                          // 混排：全部显示，不留页脚
      s.shown = now.length;
      for (var j = 0; j < now.length; j++) now[j].removeAttribute('data-pg');
      if (s.foot) { s.foot.parentNode.removeChild(s.foot); s.foot = null; s.watch = false; }
      return s;
    }

    applyPg(s);

    if (now.length > PAGE) {
      if (!s.foot) makeFoot(s);
      paintFoot(s);
    } else if (s.foot) {
      s.foot.parentNode.removeChild(s.foot);
      s.foot = null;
      s.watch = false;
    }

    if (boot && grew && now.length > PAGE) {
      /* 首屏这一页也算一次加载，便于对比「进来多少 / 滑了多少」 */
      var size = Math.min(s.shown, PAGE);
      for (var i = 0; i < size; i++) {
        if (io && hasWM) {
          meta.set(s.cards[i], { pane: s.key, base: s.base, page: 1, slot: 'A', n: size, key: s.key + '|1' });
          io.observe(s.cards[i]);
        }
      }
      track('/ev/load/' + s.key + '/p1/init', '首屏 · ' + size + ' 张');
    }
    return s;
  }

  function syncAll(boot) {
    var grids = [].slice.call(document.querySelectorAll('.archive-grid'));
    for (var i = 0; i < grids.length; i++) syncOne(grids[i], i, boot);
  }

  /* ── 重排调度 ──────────────────────────────────────────────────── */
  var raf = 0;
  function relayout() {
    for (var i = 0; i < states.length; i++) layout(states[i]);
  }
  function schedule() {
    if (raf) return;
    raf = requestAnimationFrame(function () { raf = 0; relayout(); });
  }

  var syncTimer = 0;
  function scheduleSync() {
    clearTimeout(syncTimer);
    syncTimer = setTimeout(function () { syncAll(false); schedule(); }, 60);
  }

  function boot() {
    if (!d.getAttribute('data-cols')) d.setAttribute('data-cols', '2');   // 默认一排二
    syncAll(true);
    relayout();

    // 搜索 / 筛选会把卡片一个个 hidden，分页藏起来的那些会看不见 → 全放出来
    function revealAll() {
      for (var i = 0; i < states.length; i++) {
        var s = states[i];
        if (s.shown < s.cards.length) { s.shown = s.cards.length; applyPg(s); paintFoot(s); }
      }
      schedule();
    }
    var search = document.getElementById('shelf-search');
    if (search) search.addEventListener('input', revealAll);
    ['shelf-cat1', 'shelf-cat2'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.addEventListener('change', revealAll);
    });

    if (typeof MutationObserver === 'function') {
      // 卡片被搬动 / 换页签 → 网格成员变了，得重新分页
      new MutationObserver(scheduleSync).observe(document.body, { childList: true, subtree: true });
      // 显隐 / 列数 / 字号 / 主题 → 位置变了，重排
      new MutationObserver(schedule).observe(document.body, {
        subtree: true, attributes: true, attributeFilter: ['hidden', 'data-pg']
      });
      new MutationObserver(schedule).observe(d, {
        attributes: true, attributeFilter: ['data-cols', 'style', 'data-theme']
      });
    }

    var rz = 0;
    window.addEventListener('resize', function () {
      clearTimeout(rz);
      rz = setTimeout(relayout, 140);
    });
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(relayout);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
