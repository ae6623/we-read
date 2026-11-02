/* reader.js — 合并页（全书领读）运行时：数据装配 + 阅读设置 + 导航高亮
 *
 * 设计目标：页面是「壳」，数据是「内容」，本文件是「渲染逻辑」。
 * 以后改样式改 reader.css、改交互改本文件 —— 339 本书一个字节都不用重生成。
 *
 * 页面约定（由 combine_page.py 产出的壳页提供）：
 *   <body data-slug="xxx" data-title="书名" data-cat1="一级分类" data-cat2="二级分类">
 *   <nav class="nav" id="rdNav"></nav>
 *   <main id="rdBody"></main>
 *   <button id="rdFab">Aa</button>
 *   <div id="rdPanel" hidden>…</div>
 * 数据约定：同目录下 combined-data.html
 *   首行 <!--META {...json}-->（书名/分类等），其后是若干 <section data-key="…">…</section>
 */
(function () {
  'use strict';

  /* ── 配置：改这里 = 全站生效 ───────────────────────────── */

  // 模块顺序：前置 → 精读自然顺序 → 后置。data 里没有的模块自动跳过。
  var ORDER_HEAD = ['svg', 'oneline', 'merged_guide'];
  var ORDER_TAIL = ['quiz'];

  // 导航与模块标题同一份（一律 ≤4 字）
  var LABELS = {
    svg: '结构导图', oneline: '核心主旨', merged_guide: 'AI领读',
    views: '核心观点', top10: '原文金句', aiask: 'AI 问书',
    coreask: '核心追问', higher: '更高维度', verify: '阅读验证',
    thennow: '往日今时', quiz: '读完自测'
  };

  // 字号 / 段距档位
  var FS = [0.86, 0.90, 0.94, 1.00, 1.08, 1.18];
  var PM = [0.6, 1, 1.5];
  var DEF_THEME = 'dark', DEF_FS = 0.94, DEF_PM = 1.5;

  /* ── 工具 ─────────────────────────────────────────────── */

  function q(sel, root) { return (root || document).querySelector(sel); }
  function qa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  /* ── 装配：把 data 片段切成模块，排序 / 改名 / 清废话 ───── */

  function parseData(html) {
    var meta = {};
    var mm = html.match(/<!--META\s*([\s\S]*?)\s*-->/);
    if (mm) { try { meta = JSON.parse(mm[1]) || {}; } catch (e) { meta = {}; } }
    var body = mm ? html.slice(mm.index + mm[0].length) : html;

    // 用括号配对切出顶层 <section>（兼容嵌套 section）
    var re = /<section\b[\s\S]*?<\/section>/g, m, secs = [];
    while ((m = re.exec(body))) {
      var seg = m[0];
      // 只取顶层：内部 section 开闭标签数相同则视为完整
      var open = (seg.match(/<section\b/g) || []).length;
      var close = (seg.match(/<\/section>/g) || []).length;
      if (open === close) secs.push(seg);
    }

    var map = {}, order = [];
    secs.forEach(function (seg) {
      var km = seg.match(/data-key="([^"]+)"/);
      var key = km ? km[1] : (seg.match(/aria-labelledby="([^"]+)"/) || [])[1];
      if (!key || map[key]) return;
      map[key] = seg;
      order.push(key);
    });
    return { meta: meta, map: map, order: order };
  }

  function orderedKeys(order) {
    var keys = ORDER_HEAD.filter(function (k) { return order.indexOf(k) >= 0; });
    order.forEach(function (k) {
      if (keys.indexOf(k) < 0 && k !== 'thesis') keys.push(k);
    });
    ORDER_TAIL.forEach(function (k) {
      if (order.indexOf(k) >= 0 && keys.indexOf(k) < 0) keys.push(k);
    });
    return keys;
  }

  function stripFiller(seg) {
    // 流水线说明句整类清除（读者不需要知道数据来自哪条管道）
    return seg
      .replace(/<p class="mmx-mod-note">[\s\S]*?<\/p>\s*/g, '')
      .replace(/<p class="eyebrow">[^<]*带书内引源[^<]*<\/p>\s*/g, '');
  }

  function retitle(seg, text, inject) {
    var pat = /(<h2[^>]*>)[\s\S]*?(<\/h2>)/;
    if (pat.test(seg)) return seg.replace(pat, function (_, a, b) { return a + text + b; });
    if (inject) return seg.replace(/(<section\b[^>]*>)/, '$1<h2>' + text + '</h2>');
    return seg;
  }

  function addId(seg, id) {
    if (/\sid="/.test(seg.slice(0, seg.indexOf('>') + 1))) {
      return seg.replace(/(\s)id="[^"]*"/, '$1id="' + id + '"');
    }
    return seg.replace(/(<section\b[^>]*?)>/, '$1 id="' + id + '">');
  }

  function polish(html) {
    // 站内文案规范（含嵌入大纲笔记里的旧叫法）
    return html
      .replace(/微信读书/g, 'AI 读书').replace(/微信/g, 'AI')
      .replace(/当年与今天/g, '往日今时')
      .replace(/全书结构导图/g, '结构导图');
  }

  function renderChips(meta) {
    var box = q('#rdChips');
    if (!box) return;
    var chips = [meta.cat1 || '通读 + 精读', meta.cat2 || 'Gemini pro', 'AI 生产'];
    var spans = qa('.chip', box);
    if (spans.length === 3) {
      // 壳页已直出三个占位 chip → 就地改文本，避免重建导致的闪动
      spans.forEach(function (el, i) { el.textContent = chips[i]; });
    } else {
      box.innerHTML = chips.map(function (t) {
        return '<span class="chip">' + String(t).replace(/[<>&]/g, '') + '</span>';
      }).join('');
    }
    if (meta.title) {
      var h1 = q('.combined-head h1');
      if (h1) h1.textContent = '《' + meta.title + '》';
      document.title = '《' + meta.title + '》｜全书领读';
    }
  }

  function render(data) {
    var keys = orderedKeys(data.order);
    var nav = q('#rdNav'), main = q('#rdBody');
    if (!main) return;

    var parts = [], links = [];
    keys.forEach(function (k) {
      var seg = stripFiller(data.map[k] || '');
      // 主旨只剩流水线兜底文案 → 整块不出
      if (k === 'oneline' && seg.indexOf('结构化重算') >= 0) return;

      var label = LABELS[k] || (seg.match(/<h2[^>]*>([\s\S]*?)<\/h2>/) || [])[1];
      if (label && label.indexOf('<') >= 0) label = label.replace(/<[^>]+>/g, '').trim();
      if (LABELS[k]) seg = retitle(seg, LABELS[k], k === 'svg');

      parts.push(addId(seg, 'mod-' + k));
      links.push({ id: 'mod-' + k, label: LABELS[k] || label || k });
    });

    main.innerHTML = polish(parts.join('\n'));
    main.removeAttribute('aria-busy');
    main.classList.add('rd-in');   // 内容淡入，替代骨架的突兀切换
    dedupQuoteNodes(main);
    loaded();

    // 导航：壳页已直出全套标签 → 就地删掉本书没有的、补上缺的（不重建，避免宽度闪动）
    if (nav) {
      var have = {};
      links.forEach(function (l) { have[l.id] = l.label; });
      var existing = qa('.navlink', nav);
      if (existing.length) {
        existing.forEach(function (a) {
          var id = (a.getAttribute('href') || '').replace(/^#/, '');
          if (!have[id]) a.parentNode.removeChild(a);
          else a.textContent = have[id];
        });
        links.forEach(function (l) {
          if (!q('.navlink[href="#' + l.id + '"]', nav)) {
            nav.insertAdjacentHTML('beforeend',
              '<a class="navlink" href="#' + l.id + '">' + l.label + '</a>');
          }
        });
      } else {
        nav.innerHTML = links.map(function (l) {
          return '<a class="navlink" href="#' + l.id + '">' + l.label + '</a>';
        }).join('');
      }
    }
    renderChips(data.meta || {});
    addHero();
    spy(links);
    hookSvgModal();
    pnRender();
  }

  /* ── 导航滚动高亮 ─────────────────────────────────────── */

  /* 书名号包装：book-order.json 的书名有的整体带《》（取自首页 h3），
     有的是「《xxx》在说什么」这类自带前书名号的形式 → 只要以《开头就不再包，
     否则会出现《《xxx》》或《《xxx》在说什么》 */
  function wrapShu(t) {
    t = esc(String(t || '').trim());
    return t.indexOf('《') === 0 ? t : '《' + t + '》';
  }

  /* 详情页顶部大封面模块（参考微信读书书籍介绍页）：
     居中竖版大图 + 主题绿光晕底；封面 404 → 整块隐藏，不留空洞。
     SPA 翻页时随 curSlug 重建。 */
  function addHero() {
    var main = q('#rdBody');
    if (!main) return;
    var old = document.getElementById('rdHero');
    if (old && old.parentNode) old.parentNode.removeChild(old);
    var slug = curSlug || (document.body.getAttribute('data-slug') || '');
    if (!slug) return;
    var sec = document.createElement('section');
    sec.id = 'rdHero';
    sec.className = 'rd-hero';
    var src = '../../../assets/covers/' + encodeURIComponent(slug) + '.jpg';
    sec.innerHTML = '<img class="rd-hero-bg" aria-hidden="true" alt="" src="' + src + '">'
      + '<img class="rd-hero-img" alt="封面" loading="eager" src="' + src + '">';
    var img = sec.querySelector('.rd-hero-img');
    img.addEventListener('error', function () {
      if (sec.parentNode) sec.parentNode.removeChild(sec);
    });
    main.insertBefore(sec, main.firstChild);
  }

  /* 「原句 · 本小节汇总」去重：小节里如果所有 ul.quote 的原句加起来
     和汇总节点一字不差（只有一个来源时必然如此），汇总就是纯重复 → 整块删掉。
     汇总里有任何一条新增内容则保留不动。 */
  function dedupQuoteNodes(root) {
    var nodes;
    try { nodes = root.querySelectorAll('ul.quote.quote-node'); } catch (e) { return; }
    function flat(ul) {
      var out = [];
      Array.prototype.forEach.call(ul.children, function (li) {
        if (li.tagName !== 'LI') return;
        var t = (li.textContent || '').replace(/\s+/g, '');
        if (t) out.push(t);
      });
      return out;
    }
    Array.prototype.forEach.call(nodes, function (node) {
      var sec = node.closest ? node.closest('.sec') : null;
      if (!sec) return;
      var src = sec.querySelectorAll('ul.quote:not(.quote-node)');
      if (!src.length) return;               // 小节里没有别的原句 → 汇总是唯一来源，保留
      var want = [], have = flat(node);
      Array.prototype.forEach.call(src, function (ul) {
        want = want.concat(flat(ul));
      });
      if (!have.length || want.length !== have.length) return;
      for (var i = 0; i < have.length; i++) if (have[i] !== want[i]) return;
      node.parentNode.removeChild(node);
    });
  }

  /* 详情页顶部「回首页」入口：注入到 header 顶部，点击上报埋点。
     埋点走 goatcounter 事件通道（combined.html 已带 no_onload 的 count.js +
     home-track.js，详情页只报事件、不计 PV）。 */
  function addHomeLink() {
    if (document.getElementById('rdHome')) return;
    var head = q('header.combined-head');
    if (!head) return;
    var a = document.createElement('a');
    a.id = 'rdHome';
    a.className = 'rd-home';
    a.href = '../../../index.html';
    a.innerHTML = '<span aria-hidden="true">←</span>';
    a.title = '回首页';
    a.setAttribute('aria-label', '回首页');
    a.addEventListener('click', function () {
      try { if (window.rdTrack) rdTrack('/detail/back-home', '详情页·回首页'); } catch (e) {}
    });
    head.insertBefore(a, head.firstChild);
  }


  function spy(links) {
    var as = qa('.navlink'), map = {};
    as.forEach(function (a) { map[a.getAttribute('href').slice(1)] = a; });
    function mark(a) { as.forEach(function (x) { x.classList.toggle('active', x === a); }); }
    if ('IntersectionObserver' in window) {
      var cur = null;
      var io = new IntersectionObserver(function (es) {
        es.forEach(function (e) {
          if (e.isIntersecting) {
            var a = map[e.target.id];
            if (a && cur !== a) { cur = a; mark(a); }
          }
        });
      }, { rootMargin: '-15% 0px -75% 0px' });
      Object.keys(map).forEach(function (id) {
        var el = document.getElementById(id);
        if (el) io.observe(el);
      });
    }
    as.forEach(function (a) {
      a.addEventListener('click', function () { mark(a); });
    });
  }

  /* ── 结构导图全屏弹层 ────────────────────────────────────────────
     导航里的「结构导图」和图本身都可点：点开大屏看图，右上角 ✕ 关闭
     （点遮罩 / Esc 也关）。弹层全局唯一，每次渲染后往里填当前书的图。 */
  var svgModal = null;

  function ensureSvgModal() {
    if (svgModal) return svgModal;
    var m = document.createElement('div');
    m.id = 'rdSvgModal';
    m.hidden = true;
    m.innerHTML =
      '<div class="rd-svg-mask"></div>' +
      '<figure class="rd-svg-stage"><div class="rd-svg-holder"></div></figure>' +
      '<button class="rd-svg-close" type="button" aria-label="关闭大图">✕</button>';
    document.body.appendChild(m);
    function close() { m.hidden = true; qa('.rd-svg-holder svg', m).forEach(function (s) { s.remove(); }); }
    m.querySelector('.rd-svg-close').addEventListener('click', close);
    m.querySelector('.rd-svg-mask').addEventListener('click', close);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !m.hidden) close();
    });
    svgModal = m;
    return m;
  }

  function openSvgModal() {
    var src = q('#mod-svg svg');
    if (!src) {                              // 本书没有结构导图 → 退回锚点跳转
      var sec = q('#mod-svg');
      if (sec) sec.scrollIntoView({ behavior: 'smooth' });
      return;
    }
    var m = ensureSvgModal();
    var holder = q('.rd-svg-holder', m);
    holder.innerHTML = '';
    var clone = src.cloneNode(true);
    clone.removeAttribute('style');          // 内联尺寸交给弹层 CSS 管
    holder.appendChild(clone);
    m.hidden = false;
  }

  function hookSvgModal() {
    qa('.navlink[href="#mod-svg"]').forEach(function (a) {
      if (a._rdSvgHook) return;
      a._rdSvgHook = true;
      a.addEventListener('click', function (e) { e.preventDefault(); openSvgModal(); });
    });
    var svg = q('#mod-svg svg');
    if (svg) {
      svg.style.cursor = 'zoom-in';
      svg.addEventListener('click', openSvgModal);   // 每次渲染都是新节点，不会重复挂
    }
  }

  /* ── 上一篇 / 下一篇 ─────────────────────────────────────────────
     顺序 = 首页书架的卡片序（assets/data/book-order.json，由首页卡片生成，
     最新在前）：上一篇 = 更新一篇，下一篇 = 更早一篇。
     点击不整页跳转：fetch 那本的 combined-data.html 原地重渲染，
     URL 用 pushState 换成目标页，前进/后退都能用；渲染失败整页兜底跳转。 */
  var pnOrder = null;                        // [{slug,title}]
  var pnIdx = -1;
  var curSlug = (document.body && document.body.getAttribute('data-slug')) || '';

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function pnLoad(cb) {
    if (pnOrder) return cb();
    fetch('../../../assets/data/book-order.json', { credentials: 'same-origin' })
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (list) {
        pnOrder = (Array.isArray(list) ? list : []).map(function (x) {
          return { slug: x[0], title: x[1] };
        });
      })
      .catch(function () { pnOrder = []; })
      .then(cb);
  }

  function pnRender() {
    pnLoad(function () {
      var host = q('#rdPn');
      if (!host) {
        var main = q('#rdBody');
        if (!main) return;
        host = document.createElement('nav');
        host.id = 'rdPn';
        host.setAttribute('aria-label', '上一篇 / 下一篇');
        main.parentNode.appendChild(host);
      }
      pnIdx = -1;
      for (var i = 0; i < pnOrder.length; i++) if (pnOrder[i].slug === curSlug) { pnIdx = i; break; }
      if (pnIdx < 0) { host.innerHTML = ''; host.hidden = true; return; }
      host.hidden = false;
      var prev = pnIdx > 0 ? pnOrder[pnIdx - 1] : null;
      var next = pnIdx < pnOrder.length - 1 ? pnOrder[pnIdx + 1] : null;
      host.innerHTML =
        '<a class="rd-pn rd-pn-prev' + (prev ? '' : ' is-off') + '"' + (prev ? ' href="#pn-prev"' : '') + '>' +
          '<span class="rd-pn-k">上一篇</span>' +
          '<span class="rd-pn-t">' + (prev ? wrapShu(prev.title) : '已经是最新一篇') + '</span></a>' +
        '<a class="rd-pn rd-pn-next' + (next ? '' : ' is-off') + '"' + (next ? ' href="#pn-next"' : '') + '>' +
          '<span class="rd-pn-k">下一篇</span>' +
          '<span class="rd-pn-t">' + (next ? wrapShu(next.title) : '已经是最早一篇') + '</span></a>';
      var ap = q('.rd-pn-prev', host), an = q('.rd-pn-next', host);
      if (prev && ap) ap.addEventListener('click', function (e) { e.preventDefault(); goBook(prev.slug); });
      if (next && an) an.addEventListener('click', function (e) { e.preventDefault(); goBook(next.slug); });
    });
  }

  function goBook(slug, push) {
    if (!slug || slug === curSlug) return;
    var main = q('#rdBody');
    if (main) main.setAttribute('aria-busy', 'true');
    if (svgModal && !svgModal.hidden) svgModal.hidden = true;
    fetch('../' + slug + '/combined-data.html?v=' + encodeURIComponent(slug), { credentials: 'same-origin' })
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.text(); })
      .then(function (html) {
        if (!html || html.indexOf('<section') < 0) throw new Error('空数据');
        curSlug = slug;
        render(parseData(html));
        if (push !== false) {
          try { history.pushState({ rdBook: slug }, '', '../' + slug + '/combined.html'); } catch (e) {}
        }
        window.scrollTo(0, 0);
      })
      .catch(function () {
        // 原地渲染失败 → 整页跳过去，别把读者卡死在本页
        location.href = '../' + slug + '/combined.html';
      });
  }

  window.addEventListener('popstate', function () {
    var m = location.pathname.match(/\/books\/([^/]+)\/combined\.html$/);
    if (m && m[1] && m[1] !== curSlug) goBook(m[1], false);
  });

  /* ── 阅读设置：主题 / 字号 / 段距（localStorage 持久化） ── */

  var CFG_KEY = 'rd-cfg';

  function loadCfg() {
    try { return JSON.parse(localStorage.getItem(CFG_KEY) || '{}') || {}; } catch (e) { return {}; }
  }
  function saveCfg(c) { try { localStorage.setItem(CFG_KEY, JSON.stringify(c)); } catch (e) {} }

  function nearest(arr, v, def) {
    var i = arr.indexOf(parseFloat(v));
    if (i >= 0) return i;
    var best = 0, bd = Infinity;
    arr.forEach(function (x, j) { var d = Math.abs(x - (parseFloat(v) || def)); if (d < bd) { bd = d; best = j; } });
    return best;
  }

  function initSettings() {
    var d = document.documentElement;
    var c = loadCfg();
    var fi = nearest(FS, c.fs, DEF_FS);
    var pi = nearest(PM, c.pm, DEF_PM);
    var panel = q('#rdPanel'), fab = q('#rdFab');
    if (!panel || !fab) return;

    fab.onclick = function (e) { e.stopPropagation(); panel.hidden = !panel.hidden; };
    document.addEventListener('click', function (e) {
      if (!panel.hidden && !panel.contains(e.target) && e.target.id !== 'rdFab') panel.hidden = true;
    });
    panel.addEventListener('click', function (e) {
      var b = e.target.closest ? e.target.closest('button[data-rd]') : null;
      if (!b) return;
      var k = b.getAttribute('data-rd');
      if (k === 'fs-') fi = Math.max(0, fi - 1);
      else if (k === 'fs+') fi = Math.min(FS.length - 1, fi + 1);
      else if (k === 'pm-') pi = Math.max(0, pi - 1);
      else if (k === 'pm0') pi = 1;
      else if (k === 'pm+') pi = Math.min(PM.length - 1, pi + 1);
      else if (k.indexOf('th-') === 0) c.theme = k.slice(3);
      apply();
    });

    var THEME_COLOR = { dark: '#15171a', cream: '#f7f8f3', light: '#ffffff', green: '#cfe8d2' };
    var tcMeta = q('meta[name="theme-color"]');

    // store=false → 只应用不落盘：没主动选过主题的人，不该被顺手写入「默认夜间」，
    // 否则回到首页（默认米白）会突然变黑。
    function apply(store) {
      var th = c.theme || DEF_THEME;
      d.setAttribute('data-theme', th);
      if (tcMeta) tcMeta.setAttribute('content', THEME_COLOR[th] || '#15171a');
      d.style.setProperty('--fs', FS[fi]);
      d.style.setProperty('--pm', PM[pi]);
      if (store !== false) { c.fs = FS[fi]; c.pm = PM[pi]; saveCfg(c); }
      qa('button[data-rd^="th-"]', panel).forEach(function (b) {
        var on = b.getAttribute('data-rd') === 'th-' + (c.theme || DEF_THEME);
        b.style.borderColor = on ? 'var(--head)' : '';
        b.style.color = on ? 'var(--head)' : '';
      });
    }
    apply(false);
  }

  /* ── 启动 ─────────────────────────────────────────────── */

  // 顶部进度条收尾（成功/失败都要收，否则一直转 = 看起来像卡死）
  function loaded() {
    var bar = q('#rdBar');
    if (!bar) return;
    bar.classList.add('rd-done');
    setTimeout(function () { if (bar.parentNode) bar.parentNode.removeChild(bar); }, 420);
  }

  function fail(msg) {
    var main = q('#rdBody');
    if (main) {
      main.removeAttribute('aria-busy');
      main.classList.remove('rd-in');
      // 线上失败基本是网络问题；只有 file:// 才需要解释同源策略
      var tip = location.protocol === 'file:'
        ? '页面需通过站点（http/https）访问：直接双击本地文件会被浏览器的同源策略拦截。'
        : '多半是网络不稳，点下面重新加载即可。';
      main.innerHTML = '<p class="rd-fail"><b>内容没能加载出来</b>' + (msg || '') + '<br>'
        + tip + '<br><button class="rd-retry" type="button">重新加载</button></p>';
      var btn = q('.rd-retry', main);
      if (btn) btn.onclick = function () { location.reload(); };
    }
    loaded();
  }

  function boot() {
    initSettings();
    addHomeLink();

    // ① 内联数据（standalone 单文件预览）优先，② 否则 fetch 同目录数据文件
    var inline = document.getElementById('rdData');
    if (inline) {
      try { render(parseData(inline.textContent)); return; } catch (e) { /* 落到 fetch */ }
    }

    var body = document.body;
    var slug = (body && body.getAttribute('data-slug')) || '';
    var url = 'combined-data.html' + (slug ? '?v=' + encodeURIComponent(slug) : '');

    fetch(url, { credentials: 'same-origin' }).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.text();
    }).then(function (html) {
      if (!html || html.indexOf('<section') < 0) throw new Error('空数据');
      render(parseData(html));
    }).catch(function (err) {
      fail(err && err.message ? '（' + err.message + '）' : '');
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
