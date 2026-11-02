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
    var chips = [meta.cat1 || '通读 + 精读', meta.cat2 || 'AI领读', 'AI 生产'];
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
    spy(links);
  }

  /* ── 导航滚动高亮 ─────────────────────────────────────── */

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

    function apply() {
      d.setAttribute('data-theme', c.theme || DEF_THEME);
      if (tcMeta) tcMeta.setAttribute('content', THEME_COLOR[c.theme || DEF_THEME] || '#15171a');
      d.style.setProperty('--fs', FS[fi]);
      d.style.setProperty('--pm', PM[pi]);
      c.fs = FS[fi]; c.pm = PM[pi];
      saveCfg(c);
      qa('button[data-rd^="th-"]', panel).forEach(function (b) {
        var on = b.getAttribute('data-rd') === 'th-' + (c.theme || DEF_THEME);
        b.style.borderColor = on ? 'var(--head)' : '';
        b.style.color = on ? 'var(--head)' : '';
      });
    }
    apply();
  }

  /* ── 启动 ─────────────────────────────────────────────── */

  function fail(msg) {
    var main = q('#rdBody');
    if (main) {
      main.removeAttribute('aria-busy');
      main.innerHTML = '<p class="rd-fail">内容加载失败：' + msg + '</p>';
    }
  }

  function boot() {
    initSettings();

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
      fail('内容加载失败（' + err.message + '）。本站页面需通过站点访问（http/https），'
         + '直接双击打开本地文件会被浏览器的同源策略拦截。');
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
