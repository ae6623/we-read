/* structure-map-v2.js — 「结构导图 v2」独立模块（2026-11-15）
 *
 * 与 reader-20261115.js 物理隔离：本文件不修改任何老函数，只暴露
 * window.__RD_STRUCT_V2__.render()，由 reader.js 的 loadStructV2() 调用。
 *
 * 职责：
 *   1) 读 section[data-key="merged_guide"] 的四级章节树
 *      章(details.mmx-cn) → 小节(div.sec>h4) → 要点(ul.point>li>b)
 *      → 原句(ul.quote>li)
 *   2) 在统一的结构导图模块（section#mod-svg / [data-key="svg"]）的
 *      **最上方**插入 figure.wr-struct-v2 —— 位置永远在原结构导图之上
 *   3) 老样式扁平 SVG（无 svg.mmx-mind）从 DOM 移除，由 v2 取代；
 *      新样式（svg.mmx-mind，initMindTree 会转成 .mmx-tree）一个节点不碰
 *   4) 点章展开小节、点小节展开要点、点空白放大；SPA 翻页幂等
 *
 * 数据源是页面已有 DOM，不新增字段、不重生成 339 本数据页、不调 LLM。
 */
(function () {
  'use strict';

  var MAX_CH = 12;
  var CSS_ID = 'wrStructV2Css';

  function q(sel, root) { return (root || document).querySelector(sel); }
  function qa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function txt(el) { return el ? String(el.textContent || '').replace(/\s+/g, ' ').trim() : ''; }
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  /* ── 样式：半透明蓝绿 + currentColor，浅色/深色主题都融得进去 ──── */
  var CSS = [
    '.wr-struct-v2{margin:0 0 22px;padding:0;border:0;background:none;color:inherit;font:inherit}',
    '.wr-struct-v2 figcaption{display:flex;align-items:center;gap:10px;flex-wrap:wrap;',
    '  margin:0 0 12px;font-size:12px;font-weight:700;letter-spacing:.04em;opacity:.82}',
    '.wr-struct-v2 figcaption .v2-hint{font-weight:400;opacity:.62}',
    '.wr-struct-v2 .v2-zoom{margin-left:auto;padding:4px 10px;border:1px solid currentColor;',
    '  border-radius:999px;background:transparent;color:inherit;font:inherit;font-weight:600;',
    '  cursor:zoom-in;opacity:.75}',
    '.wr-struct-v2 .v2-zoom:hover{opacity:1}',
    '.v2-root{max-width:440px;margin:0 auto 18px;padding:14px 18px;border-radius:10px;',
    '  background:#1a73e8;color:#fff;text-align:center;font-size:17px;font-weight:700;',
    '  line-height:1.4;box-shadow:0 2px 10px rgba(26,115,232,.18)}',
    '.v2-cols{display:flex;gap:36px;align-items:flex-start}',
    '.v2-col{flex:1 1 0;min-width:0;display:flex;flex-direction:column;gap:14px}',
    '.v2-ch{border:1px solid rgba(66,133,244,.38);border-radius:9px;overflow:hidden}',
    '.v2-ch.v2-green{border-color:rgba(52,168,83,.36)}',
    '.v2-ch-head,.v2-sec-head{display:flex;align-items:center;gap:10px;width:100%;',
    '  padding:0 12px;border:0;background:transparent;color:inherit;font:inherit;',
    '  text-align:left;cursor:pointer}',
    '.v2-ch-head{min-height:54px;background:rgba(66,133,244,.10)}',
    '.v2-ch.v2-green>.v2-ch-head{background:rgba(52,168,83,.11)}',
    '.v2-ch-head:hover,.v2-sec-head:hover{filter:brightness(1.12)}',
    '.v2-no{font-size:13px;font-weight:700;opacity:.72;min-width:16px}',
    '.v2-name{flex:1 1 auto;min-width:0;font-size:13.5px;font-weight:700;line-height:1.45}',
    '.v2-count,.v2-pt-count{font-size:11.5px;opacity:.55;white-space:nowrap}',
    '.v2-caret{font-size:11px;opacity:.5;width:12px;text-align:center;flex:0 0 auto}',
    '.v2-secs{padding:4px 0 10px 14px;border-left:1px solid currentColor;',
    '  margin-left:14px;border-color:rgba(120,128,140,.28)}',
    '.v2-sec{position:relative;margin:6px 12px 0 0}',
    '.v2-sec::before{content:"";position:absolute;left:-14px;top:18px;width:12px;',
    '  height:1px;background:currentColor;opacity:.24}',
    '.v2-sec-head{min-height:32px;padding:0 12px;border:1px solid rgba(120,128,140,.26);',
    '  border-radius:7px;background:rgba(120,128,140,.12);font-size:12px}',
    '.v2-sec-head .v2-name{font-weight:400;font-size:12px;opacity:.86}',
    '.v2-points{margin:4px 0 0 12px;padding:2px 0 6px 12px;',
    '  border-left:1px dashed rgba(120,128,140,.34)}',
    '.v2-point{position:relative;margin:5px 0;font-size:11.5px;line-height:1.6}',
    '.v2-point::before{content:"";position:absolute;left:-12px;top:10px;width:9px;',
    '  height:1px;background:currentColor;opacity:.22}',
    '.v2-point>b{font-weight:600;opacity:.9}',
    '.v2-quotes{margin:3px 0 0;padding:0 0 0 14px;list-style:none;opacity:.66}',
    '.v2-quotes li{position:relative;margin:2px 0;font-size:11px;line-height:1.55}',
    '.v2-quotes li::before{content:"「";opacity:.6}',
    '.v2-quotes li::after{content:"」";opacity:.6}',
    '.v2-empty{font-size:11.5px;opacity:.5;margin:6px 0 2px}',
    '.v2-more{margin:14px 0 0;text-align:right;font-size:10.5px;opacity:.45}',
    '@media(max-width:720px){.v2-cols{flex-direction:column;gap:0}.v2-col{width:100%}',
    '  .v2-col+.v2-col{margin-top:14px}}',
    /* 放大弹层：独立于 reader.js 的 rdSvgModal，互不干扰 */
    '.wr-v2-modal{position:fixed;inset:0;z-index:99999;display:flex;align-items:center;',
    '  justify-content:center;padding:24px;background:rgba(12,16,20,.86);color:#f2f4f7}',
    '.wr-v2-stage{position:relative;width:min(1100px,96vw);max-height:92vh;overflow:auto;',
    '  padding:22px;border-radius:14px;background:#1b2027;box-shadow:0 18px 60px rgba(0,0,0,.5)}',
    '.wr-v2-close{position:absolute;right:12px;top:10px;border:0;background:transparent;',
    '  color:inherit;font-size:22px;line-height:1;cursor:pointer;opacity:.7}',
    '.wr-v2-close:hover{opacity:1}',
    '.wr-v2-modal .wr-struct-v2{margin:0}'
  ].join('\n');

  function addCss() {
    if (document.getElementById(CSS_ID)) return;
    var s = document.createElement('style');
    s.id = CSS_ID;
    s.textContent = CSS;
    (document.head || document.documentElement).appendChild(s);
  }

  /* ── 四级章节树解析 ───────────────────────────────────────────── */
  function readTree() {
    var mg = q('section[data-key="merged_guide"]');
    if (!mg) return null;
    var ds = qa('details.mmx-cn', mg);
    if (!ds.length) return null;
    var items = [];
    for (var i = 0; i < ds.length && items.length < MAX_CH; i++) {
      var d = ds[i], sm = q('summary', d);
      if (!sm) continue;
      var num = txt(q('.mmx-no', sm));
      var name = txt(q('.mmx-name', sm)) || txt(sm).replace(/›/g, '').trim();
      if (!name) continue;
      var secs = [];
      qa('div.sec', d).forEach(function (se, j) {
        var sname = txt(q('h4', se)) || ('小节 ' + (j + 1));
        var points = [];
        /* 只取 ul.point > li；div.sec 末尾那个 ul.quote.quote-node 是汇总，不当要点 */
        qa('ul.point > li', se).forEach(function (li) {
          var pt = txt(q('b', li));
          var quotes = [];
          qa('ul.quote > li', li).forEach(function (ql) {
            var t = txt(ql);
            if (t) quotes.push(t);
          });
          if (pt || quotes.length) points.push({ text: pt || '（原句摘录）', quotes: quotes });
        });
        secs.push({ name: sname, points: points });
      });
      items.push({ num: num, name: name, secs: secs });
    }
    return items.length ? { items: items, total: ds.length } : null;
  }

  /* ── 渲染 ─────────────────────────────────────────────────────── */
  function chapterHtml(it, k) {
    var nSec = it.secs.length;
    var nPt = 0, nQ = 0;
    it.secs.forEach(function (s) {
      nPt += s.points.length;
      s.points.forEach(function (p) { nQ += p.quotes.length; });
    });
    var o = [];
    o.push('<div class="v2-ch' + (k % 2 ? ' v2-green' : '') + '" data-k="' + k + '">');
    o.push('<button type="button" class="v2-ch-head" aria-expanded="false">'
      + '<span class="v2-no">' + esc(it.num) + '</span>'
      + '<span class="v2-name">' + esc(it.name) + '</span>'
      + '<span class="v2-count">' + nSec + ' 节 · ' + nPt + ' 要点</span>'
      + '<span class="v2-caret">▸</span></button>');
    o.push('<div class="v2-secs" hidden>');
    if (!nSec) {
      o.push('<div class="v2-empty">本章暂无可展开的小节</div>');
    } else {
      it.secs.forEach(function (s) {
        o.push('<div class="v2-sec">');
        o.push('<button type="button" class="v2-sec-head" aria-expanded="false">'
          + '<span class="v2-name">' + esc(s.name) + '</span>'
          + '<span class="v2-pt-count">' + s.points.length + ' 要点</span>'
          + '<span class="v2-caret">▸</span></button>');
        o.push('<div class="v2-points" hidden>');
        if (!s.points.length) {
          o.push('<div class="v2-empty">本小节暂无要点</div>');
        } else {
          s.points.forEach(function (p) {
            o.push('<div class="v2-point"><b>' + esc(p.text) + '</b>');
            if (p.quotes.length) {
              o.push('<ul class="v2-quotes">');
              p.quotes.forEach(function (t) { o.push('<li>' + esc(t) + '</li>'); });
              o.push('</ul>');
            }
            o.push('</div>');
          });
        }
        o.push('</div></div>');
      });
    }
    o.push('</div></div>');
    return o.join('');
  }

  function figureHtml(data, title) {
    var items = data.items, n = items.length;
    var two = n > 3, per = two ? Math.ceil(n / 2) : n;
    var cols = [[], []];
    items.forEach(function (it, k) {
      var c = two ? Math.min(1, Math.floor(k / per)) : 0;
      cols[c].push(chapterHtml(it, k));
    });
    var colHtml = two
      ? '<div class="v2-col">' + cols[0].join('') + '</div>'
        + '<div class="v2-col">' + cols[1].join('') + '</div>'
      : '<div class="v2-col">' + cols[0].join('') + '</div>';
    var more = data.total > n
      ? '<p class="v2-more">另 ' + (data.total - n) + ' 章见 AI领读 / 章节目录</p>' : '';
    return '<figcaption><span>知识导图 · 章节脉络</span>'
      + '<span class="v2-hint">点章展开小节 · 点小节展开要点 · 点空白放大</span>'
      + '<button type="button" class="v2-zoom">⤢ 放大</button></figcaption>'
      + '<div class="v2-root">《' + esc(title) + '》</div>'
      + '<div class="v2-cols">' + colHtml + '</div>' + more;
  }

  /* ── 老/新样式分流：唯一判据 svg.mmx-mind ─────────────────────── */
  function swapLegacy(sec) {
    if (q('svg.mmx-mind', sec)) return false;   // 新样式：一个节点不碰
    var legacy = q('svg.mmx-svg', sec);
    if (legacy && legacy.parentNode) legacy.parentNode.removeChild(legacy);
    return true;
  }

  /* ── 放大：自有 overlay，不复用 reader.js 的 rdSvgModal ───────── */
  var modal = null;
  function openBig(fig) {
    if (!modal) {
      modal = document.createElement('div');
      modal.className = 'wr-v2-modal';
      modal.innerHTML = '<div class="wr-v2-stage"><button type="button" class="wr-v2-close" '
        + 'aria-label="关闭">✕</button><div class="wr-v2-holder"></div></div>';
      modal.style.display = 'none';
      document.body.appendChild(modal);
      function close() { modal.style.display = 'none'; }
      q('.wr-v2-close', modal).addEventListener('click', close);
      modal.addEventListener('click', function (e) { if (e.target === modal) close(); });
      document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && modal && modal.style.display !== 'none') close();
      });
    }
    var holder = q('.wr-v2-holder', modal);
    holder.innerHTML = '';
    var clone = fig.cloneNode(true);
    clone.querySelector('.v2-zoom') && clone.querySelector('.v2-zoom').remove();
    /* 弹层里默认展开全部章，方便一览；小节保持折叠，避免一次铺太长 */
    qa('.v2-secs', clone).forEach(function (x) { x.hidden = false; });
    qa('.v2-ch-head', clone).forEach(function (x) { x.setAttribute('aria-expanded', 'true'); });
    holder.appendChild(clone);
    bind(clone);
    modal.style.display = 'flex';
  }

  function bind(fig) {
    if (fig._v2Bound) return;
    fig._v2Bound = true;
    fig.addEventListener('click', function (e) {
      var t = e.target;
      if (!t || !t.closest) return;
      var ch = t.closest('.v2-ch-head');
      if (ch) {
        e.stopPropagation();
        var box = ch.parentNode.querySelector('.v2-secs');
        if (box) {
          box.hidden = !box.hidden;
          ch.setAttribute('aria-expanded', box.hidden ? 'false' : 'true');
          var c = ch.querySelector('.v2-caret');
          if (c) c.textContent = box.hidden ? '▸' : '▾';
        }
        return;
      }
      var sh = t.closest('.v2-sec-head');
      if (sh) {
        e.stopPropagation();
        var pb = sh.parentNode.querySelector('.v2-points');
        if (pb) {
          pb.hidden = !pb.hidden;
          sh.setAttribute('aria-expanded', pb.hidden ? 'false' : 'true');
          var c2 = sh.querySelector('.v2-caret');
          if (c2) c2.textContent = pb.hidden ? '▸' : '▾';
        }
        return;
      }
      if (t.closest('.v2-zoom')) {
        e.stopPropagation();
        openBig(fig);
        return;
      }
      /* 点卡片以外空白 → 放大；弹层内的副本不再触发放大 */
      if (!t.closest('.v2-ch') && !t.closest('.v2-root')
          && !fig.closest('.wr-v2-modal')) {
        openBig(fig);
      }
    });
  }

  /* ── 对外入口：SPA 翻页会重复调用，必须幂等 ─────────────────── */
  function render() {
    addCss();
    var sec = q('section#mod-svg') || q('section[data-key="svg"]');
    if (!sec) return 0;
    /* 先清掉本模块上次插入的 figure（老模块 wr-kmap 不动，由 reader.js 决定是否注入） */
    Array.prototype.slice.call(sec.children).forEach(function (c) {
      if (c.classList && c.classList.contains('wr-struct-v2')) sec.removeChild(c);
    });
    var data = readTree();
    if (!data) return 0;              // 没有章节树就不插，也不动结构导图
    swapLegacy(sec);                  // R2 / R3
    var title = (document.title || '').split('｜')[0].replace(/[《》]/g, '').trim() || '本书';
    var fig = document.createElement('figure');
    fig.className = 'wr-struct-v2';
    fig.innerHTML = figureHtml(data, title);
    sec.insertBefore(fig, sec.firstChild);   // R4：永远在结构导图上方
    bind(fig);
    return data.items.length;
  }

  window.__RD_STRUCT_V2__ = {
    version: '2026-11-15',
    render: render,
    /* 便于控制台自检 */
    stats: function () {
      var t = readTree();
      if (!t) return null;
      var s = 0, p = 0, qq = 0;
      t.items.forEach(function (c) {
        s += c.secs.length;
        c.secs.forEach(function (x) {
          p += x.points.length;
          x.points.forEach(function (y) { qq += y.quotes.length; });
        });
      });
      return { chapters: t.items.length, total: t.total, secs: s, points: p, quotes: qq };
    }
  };
})();
