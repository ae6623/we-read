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
    // 流水线说明句整类清除（读者不需要知道数据来自哪条管道）；
    // 但「尚未完成归纳」是占位书对读者的诚实交代，必须保留。
    return seg
      .replace(/<p class="mmx-mod-note">([\s\S]*?)<\/p>\s*/g, function (m, inner) {
        return inner.indexOf('暂不展示') >= 0 ? m : '';
      })
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
    /* 徽章行已废弃（第 20 批 n）：详情页顶部只留书名 / 作者 / 章节导航 */
    var box = q('#rdChips');
    if (box && box.parentNode) box.parentNode.removeChild(box);
    if (meta.title) {
      var h1 = q('#rdStick h1') || q('.combined-head h1');
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
    initMindTree();
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
     插到 header 之前 → 大图从网页最顶部开始（第 20 批）。
     FULL_HERO 白名单：卡片式满宽平铺变体（第 20 批 b/c）——封面 100vw×100svh
     铺满当背景，书名 h1 / chips / 章节导航 #rdNav 全部搬进图上（微信读书
     介绍页式），正文从第二屏开始。翻页重建前先 rescue 移回原位。
     SPA 翻页时随 curSlug 重建，非 full 书自动还原。 */
  /* 第 20 批 p：海报墙（满宽背景墙 + 独立吸顶标题条）改为**全站默认**，
     不再逐本白名单，也不用改任何壳页 html —— 版式完全由这里的 JS + reader.css 决定。
     需要退出这套版式的书，把 slug 写进 HERO_SKIP 即可（目前为空）。
     封面 404 的书会自动降级回普通版式，并记进 HERO_FAILED 防止反复重试。 */
  var HERO_SKIP = {};
  var HERO_FAILED = {};
  function rescueHeroNodes() {
    var head = document.querySelector('header.combined-head');
    if (!head) return;
    var stick = document.getElementById('rdStick');
    var h1 = (stick || document).querySelector('h1');
    var nav = document.getElementById('rdNav');
    if (h1 && h1.parentNode !== head) head.insertBefore(h1, head.firstChild);
    if (nav && head.parentNode && !head.parentNode.contains(nav)) {
      head.parentNode.insertBefore(nav, head.nextSibling);
    }
    var au = document.getElementById('rdHeroAuthor');
    if (au && au.parentNode) au.parentNode.removeChild(au);
    if (stick && stick.parentNode) stick.parentNode.removeChild(stick);
    document.body.classList.remove('rd-has-full');
    head.style.display = '';
  }
  /* 吸顶让位：标题条钉住后，左上「回首页」与右上「Aa」两颗浮动钮正好压在
     书名/作者上 → 滚动过墙后给标题条两侧留出避让内边距（CSS 里配 .rd-scrolled） */
  var edgeBound = false;
  function bindStickyEdge() {
    if (edgeBound) return;
    edgeBound = true;
    window.addEventListener('scroll', function () {
      var hero = document.getElementById('rdHero');
      if (!hero || !document.body.classList.contains('rd-has-full')) {
        document.body.classList.remove('rd-scrolled');
        return;
      }
      document.body.classList.toggle('rd-scrolled', (window.scrollY || 0) > hero.offsetHeight - 70);
    }, { passive: true });
  }
  /* 书名入口的 bookId：全站集中放 assets/data/bookids.json（有则列出），
     不再往 339 个壳页里写 data-book-id。壳页若自带则优先用壳页的。
     没有 bookId 的书 → 书名保持纯文本，不显示 ↗（点了也没地方去） */
  var HERO_DATA = null, heroLoading = false, heroQueue = [];
  function shellBookId(slug) {
    var own = (document.body.getAttribute('data-book-id') || '').trim();
    return (own && document.body.getAttribute('data-slug') === slug) ? own : '';
  }
  /* assets/data/hero.json = { ids:{slug:bookId}, nocover:[slug…] }
     3KB 的小表，一次请求供全站复用：有 bookId 的书名才可点，没封面的书不开墙 */
  function loadHeroData(cb) {
    if (HERO_DATA) { if (cb) cb(HERO_DATA); return; }
    if (cb) heroQueue.push(cb);
    if (heroLoading) return;
    heroLoading = true;
    fetch('../../../assets/data/hero.json', { credentials: 'same-origin' })
      .then(function (r) { return r.ok ? r.json() : {}; })
      .catch(function () { return {}; })
      .then(function (m) {
        HERO_DATA = { ids: (m && m.ids) || {}, nocover: (m && m.nocover) || [] };
        HERO_DATA.nocoverMap = {};
        HERO_DATA.nocover.forEach(function (x) { HERO_DATA.nocoverMap[x] = 1; });
        heroLoading = false;
        var q = heroQueue; heroQueue = [];
        q.forEach(function (f) { try { f(HERO_DATA); } catch (e) { /* 忽略 */ } });
      });
  }
  function hasCover(slug) {
    if (!HERO_DATA) return true;                       // 数据没到 → 先按有封面处理
    return !HERO_DATA.nocoverMap[slug];
  }
  function armTitleLink(a, slug) {
    var id = shellBookId(slug);
    if (id) { applyTitleHref(a, slug, id); return; }
    loadHeroData(function (d) {
      if (!a.isConnected || a.getAttribute('data-slug') !== slug) return;
      var v = d.ids && d.ids[slug];
      if (v) applyTitleHref(a, slug, v);
    });
  }
  function applyTitleHref(a, slug, id) {
    a.href = 'weread://reading?bId=' + encodeURIComponent(id) + '&type=1';
    a.setAttribute('data-book-id', id);
    a.setAttribute('aria-label', '在微信读书打开《' + (document.body.getAttribute('data-title') || '') + '》');
    a.classList.add('rd-title-on');
    wireWeread(a, id);
  }
  /* 有书没封面（全站 45 本）：不开海报墙，直接退回「标题 + 正文」的朴素版式 */
  function degradeHero(slug, sec) {
    HERO_FAILED[slug] = 1;
    rescueHeroNodes();
    if (sec && sec.parentNode) sec.parentNode.removeChild(sec);
  }
  /* 书名入口：点标题唤起微信读书 App 里这本书的详情页
     weread://reading?bId=<bookId>&type=1 → type=1 即书籍详情页。
     桌面浏览器 / 没装 App 点不动协议时，1.5 秒兜底打开网页版搜索页。 */
  function wireWeread(a, bookId) {
    a.addEventListener('click', function (e) {
      e.preventDefault();
      var left = false;
      var mark = function () { left = true; };
      document.addEventListener('visibilitychange', mark);
      window.addEventListener('blur', mark);
      try { window.location.href = 'weread://reading?bId=' + bookId + '&type=1'; } catch (err) { /* 忽略 */ }
      setTimeout(function () {
        document.removeEventListener('visibilitychange', mark);
        window.removeEventListener('blur', mark);
        if (left || document.hidden) return;
        var t = (document.body.getAttribute('data-title') || '').replace(/^《/, '').replace(/》$/, '');
        window.open('https://weread.qq.com/web/search/books?keyword=' + encodeURIComponent(t || bookId),
          '_blank', 'noopener');
      }, 1500);
    });
  }
  /* FULL_HERO 书：从同目录 overview.html 的 .meta 提取作者（如「沈联涛」），
     异步填进 hero；取不到就整行隐藏。 */
  function fillHeroAuthor(slug, au) {
    if (!au) return;
    au.setAttribute('data-slug', slug);
    fetch('overview.html', { credentials: 'same-origin' })
      .then(function (r) { return r.ok ? r.text() : ''; })
      .then(function (t) {
        if (!au.isConnected || au.getAttribute('data-slug') !== slug) return;
        var m = t.match(/<div class="meta">([\s\S]*?)<\/div>/);
        var meta = m ? m[1].replace(/<span[\s\S]*?<\/span>/g, '').replace(/<[^>]*>/g, '') : '';
        /* meta 形如「作者　·　在读 0%（累计 0 分钟）」。作者名本身也可能带「·」
           （乔治·奥威尔、丹尼尔·佩科…），所以只在「· 在读/已读」处截断，
           不能按第一个「·」切——那会把「乔治·奥威尔」切成「乔治」 */
        var author = meta.replace(/[\s\u3000]*[·・][\s\u3000]*(在读|已读|读至)[\s\S]*$/, '')
          .replace(/\s+/g, ' ').trim();
        if (author) au.textContent = author;
        else au.style.display = 'none';
      })
      .catch(function () {
        if (au.isConnected && au.getAttribute('data-slug') === slug) au.style.display = 'none';
      });
  }
  /* 书名吸顶条：FULL_HERO 书专用。书名滚出视口后顶部淡入固定，
     背景墙（fixed）始终钉死，hero 本体普通流滚动 */
  var titleBar = null;
  function ensureTitleBar() {
    if (titleBar) return titleBar;
    titleBar = document.createElement('div');
    titleBar.id = 'rdTitleBar';
    titleBar.className = 'rd-titlebar';
    titleBar.hidden = true;
    titleBar.innerHTML = '<div class="rd-titlebar-in"></div>';
    document.body.appendChild(titleBar);
    return titleBar;
  }
  function titleBarTick() {
    if (!titleBar || titleBar.hidden) return;
    var hero = document.getElementById('rdHero');
    var show = hero && (window.scrollY || 0) > hero.offsetHeight - 100;
    titleBar.classList.toggle('show', !!show);
  }
  window.addEventListener('scroll', titleBarTick, { passive: true });

  /* 封面地址：优先用首页写进 localStorage 的地址（浏览器已有缓存，秒出）；
     没有则回落到同目录相对的本地封面文件（即从 git 拿），都不行再走 404 兜底 */
  function coverSrc(slug) {
    var local = '../../../assets/covers/' + encodeURIComponent(slug) + '.jpg';
    try {
      var c = localStorage.getItem('rdCover:' + slug);
      if (c) return c;
    } catch (e) { /* 无痕模式忽略 */ }
    return local;
  }

  function addHero() {
    var main = q('#rdBody');
    if (!main) return;
    var slug = curSlug || (document.body.getAttribute('data-slug') || '');
    if (!slug) return;
    var prev = document.getElementById('rdHero');
    if (prev && prev.getAttribute('data-slug') === slug) return;   // 同一本已渲染，不重建（防重复下载/闪）

    rescueHeroNodes();
    if (prev && prev.parentNode) prev.parentNode.removeChild(prev);
    var sec = document.createElement('section');
    sec.id = 'rdHero';
    sec.setAttribute('data-slug', slug);
    var src = coverSrc(slug);
    var head = document.querySelector('header.combined-head');
    var h1 = head ? head.querySelector('h1') : null;
    var stick = document.getElementById('rdStick');
    if (!HERO_SKIP[slug] && !HERO_FAILED[slug] && hasCover(slug)) {
      /* 海报墙：只钉「背景 + 封面本体」，上下各留一段紧贴的背景；
         标题 / 作者 / 章节导航移到墙下方的 .rd-stick 吸顶条，自然吸顶 */
      sec.className = 'rd-hero rd-hero-full';
      sec.innerHTML = '<img class="rd-hero-bg" aria-hidden="true" alt="" decoding="async" src="' + src + '">'
        + '<img class="rd-hero-cover" alt="封面" loading="eager" fetchpriority="high" decoding="async" src="' + src + '">';
      // 缓存地址失效（换域名/图被删）→ 回落到本地封面文件再试一次；
      // 本地也没有 = 这本本来没封面 → 整体降级回普通版式，不留一大片空墙
      var cov = sec.querySelector('.rd-hero-cover');
      cov.addEventListener('error', function () {
        var local = '../../../assets/covers/' + encodeURIComponent(slug) + '.jpg';
        if (this.getAttribute('src') !== local) { this.setAttribute('src', local); return; }
        degradeHero(slug, sec);
      });
      if (!stick) {
        stick = document.createElement('div');
        stick.id = 'rdStick';
        stick.className = 'rd-stick';
      }
      stick.innerHTML = '';
      /* 标题行：书名（可点，唤起微信读书详情页）+ 作者（行尾，右对齐） */
      var row = document.createElement('div');
      row.className = 'rd-stick-row';
      var au = document.createElement('span');
      au.id = 'rdHeroAuthor';
      au.className = 'rd-hero-author';
      if (h1) {
        var tlink = document.createElement('a');
        tlink.className = 'rd-title';
        tlink.id = 'rdTitleLink';
        tlink.setAttribute('data-slug', slug);
        tlink.appendChild(h1);
        row.appendChild(tlink);
      }
      row.appendChild(au);
      stick.appendChild(row);
      fillHeroAuthor(slug, au);
      document.body.classList.add('rd-has-full');
      bindStickyEdge();
      var nav = document.getElementById('rdNav');
      if (nav) stick.appendChild(nav);
      if (head) head.style.display = 'none';
      if (head && head.parentNode) {
        head.parentNode.insertBefore(sec, head);
        head.parentNode.insertBefore(stick, head);
      } else {
        main.insertBefore(sec, main.firstChild);
        main.insertBefore(stick, sec.nextSibling);
      }
      /* 标题入口要等节点真正挂进 DOM 之后才上链接：hero.json 若已在内存里，
         armTitleLink 是同步回调，提前调用会因 a.isConnected=false 直接跳过 */
      var tlink2 = stick.querySelector('#rdTitleLink');
      if (tlink2) armTitleLink(tlink2, slug);
      return;
    }

    if (stick && stick.parentNode) stick.parentNode.removeChild(stick);
    sec.className = 'rd-hero';
    sec.innerHTML = '<img class="rd-hero-bg" aria-hidden="true" alt="" decoding="async" src="' + src + '">'
      + '<img class="rd-hero-img" alt="封面" loading="eager" fetchpriority="high" src="' + src + '">';
    var img = sec.querySelector('.rd-hero-img');
    if (img) img.addEventListener('error', function () {
      rescueHeroNodes();
      if (sec.parentNode) sec.parentNode.removeChild(sec);
    });
    if (head && head.parentNode) head.parentNode.insertBefore(sec, head);
    else main.insertBefore(sec, main.firstChild);
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
    /* 挂 body 而非 header：fixed 定位不依赖 DOM 位置，
       FULL_HERO 书的 header 会整块隐藏，挂 header 会连带按钮一起消失 */
    document.body.appendChild(a);
  }


  /* ── 窄屏导航折叠：一行塞得下几个就塞几个 ───────────────────────
     不是「只留当前 ±1」：按容器实际宽度，从当前项向两侧交替扩展，
     塞到放不下为止，两端剩下的才用省略号表示。宽屏不折叠，全部显示。 */
  var NAV_GAP = 6, NAV_MORE = 18, navW = [], navKey = '';

  function navMore() {
    var box = document.getElementById('rdNav');
    if (!box) return null;
    var l = box.querySelector('.nav-more-l'), r = box.querySelector('.nav-more-r');
    if (!l) {
      l = document.createElement('span');
      l.className = 'nav-more nav-more-l';
      l.textContent = '…';
      box.insertBefore(l, box.firstChild);
    }
    if (!r) {
      r = document.createElement('span');
      r.className = 'nav-more nav-more-r';
      r.textContent = '…';
      box.appendChild(r);
    }
    return { l: l, r: r, box: box };
  }

  /* 量一次自然宽度并缓存：容器宽度或标签数变了才重量（隐藏元素先临时显示再量） */
  function navMeasure(box, as) {
    var key = box.clientWidth + '|' + as.length;
    if (key === navKey && navW.length === as.length) return navW;
    var hid = [];
    as.forEach(function (a) {
      if (a.classList.contains('nav-hide')) { hid.push(a); a.classList.remove('nav-hide'); }
    });
    navW = as.map(function (a) { return Math.round(a.getBoundingClientRect().width); });
    hid.forEach(function (a) { a.classList.add('nav-hide'); });
    navKey = key;
    return navW;
  }

  function fitNav(active) {
    var m = navMore();
    if (!m) return;
    var as = qa('.navlink'), n = as.length;
    if (!n) return;
    navLastW = m.box.clientWidth;
    watchNavSize(m.box);
    if (!window.matchMedia('(max-width:720px)').matches) {
      as.forEach(function (a) { a.classList.remove('nav-hide'); });
      m.l.classList.remove('on');
      m.r.classList.remove('on');
      return;
    }
    var w = navMeasure(m.box, as);
    /* clientWidth 含左右 padding（吸顶时 nav 会加 12px 内边距），要减掉才是真可用宽度 */
    var cs = window.getComputedStyle(m.box);
    var avail = m.box.clientWidth
      - (parseFloat(cs.paddingLeft) || 0)
      - (parseFloat(cs.paddingRight) || 0) - 2;   /* 2px 余量防亚像素溢出 */
    var idx = Math.max(0, as.indexOf(active || as[0]));
    function spanW(lo, hi) {
      var s = NAV_GAP * (hi - lo);
      for (var i = lo; i <= hi; i++) s += w[i];
      if (lo > 0) s += NAV_GAP + NAV_MORE;
      if (hi < n - 1) s += NAV_GAP + NAV_MORE;
      return s;
    }
    var lo = idx, hi = idx;
    for (var guard = 0; guard < n * 2; guard++) {
      var canR = hi < n - 1, canL = lo > 0;
      if (!canR && !canL) break;
      var goR = (guard % 2 === 0) ? canR : !canL;  /* 左右交替，当前项尽量居中 */
      var nlo = goR ? lo : lo - 1, nhi = goR ? hi + 1 : hi;
      if (spanW(nlo, nhi) <= avail) { lo = nlo; hi = nhi; continue; }
      var alo = goR ? lo - 1 : lo, ahi = goR ? hi : hi + 1;  /* 这侧满了就试另一侧 */
      if (alo < 0 || ahi > n - 1 || spanW(alo, ahi) > avail) break;
      lo = alo; hi = ahi;
    }
    as.forEach(function (a, i) { a.classList.toggle('nav-hide', i < lo || i > hi); });
    m.l.classList.toggle('on', lo > 0);
    m.r.classList.toggle('on', hi < n - 1);
  }

  var navFitBound = false, navRO = null, navROEl = null, navLastW = 0;
  /* 吸顶后 rd-stick 两侧让位给按钮，nav 会突然变窄；只监听 window.resize
     接不住这种情况，得盯容器自身尺寸 */
  function watchNavSize(box) {
    if (!window.ResizeObserver || !box) return;
    if (!navRO) {
      navRO = new ResizeObserver(function () {
        var b = document.getElementById('rdNav');
        if (!b) return;
        var w = b.clientWidth;
        if (!w || Math.abs(w - navLastW) < 1) return;
        navLastW = w;
        navKey = '';
        fitNav(q('#rdNav .navlink.active'));
      });
    }
    if (navROEl !== box) { navROEl = box; navRO.observe(box); }
  }

  function bindNavFit() {
    if (navFitBound) return;
    navFitBound = true;
    var t;
    window.addEventListener('resize', function () {
      clearTimeout(t);
      t = setTimeout(function () { navKey = ''; fitNav(q('#rdNav .navlink.active')); }, 120);
    });
    if (document.fonts && document.fonts.ready) {
      /* 字体没加载完量出来的宽度是 fallback 的，晚一步重算 */
      document.fonts.ready.then(function () { navKey = ''; fitNav(q('#rdNav .navlink.active')); });
    }
  }

  function spy(links) {
    var as = qa('.navlink'), map = {};
    as.forEach(function (a) { map[a.getAttribute('href').slice(1)] = a; });
    var navBox = document.getElementById('rdNav');
    bindNavFit();
    function mark(a) {
      as.forEach(function (x) { x.classList.toggle('active', x === a); });
      fitNav(a);
    }
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
    /* 初始先点亮第一项：避免未滚动时整条无高亮 */
    if (as.length) mark(as[0]);
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
    clone.removeAttribute('style');
    // 按视口等比缩放：不再被 min-width 撑大、也不裁切；桌面/手机/横屏都完整可见
    var vb = (clone.getAttribute('viewBox') || '').trim().split(/[\s,]+/);
    if (vb.length === 4) {
      var W = parseFloat(vb[2]), H = parseFloat(vb[3]);
      if (W > 0 && H > 0) {
        var availW = Math.min(window.innerWidth - 32, 900);
        var availH = window.innerHeight - 72;
        var s = Math.min(availW / W, availH / H);
        clone.style.width = Math.max(1, Math.round(W * s)) + 'px';
        clone.style.height = Math.max(1, Math.round(H * s)) + 'px';
      }
    }
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

  /* ── 交互式结构导图：逐级下钻 ──────────────────────────────────
     静态 SVG 是一次性摊平的全景图，节点只是图元、点不动。这里在运行时
     从 SVG 里把「全书命题 / 议题 / 关键概念 / 论证说明」读回来，装配成一棵
     可折叠树：点议题 → 出概念；点概念 → 出这条线在论证什么。
     内容全部来自已归纳好的 SVG 文本，不新增、不编造；421 个数据页零改动。 */
  var MIND_COLORS = ['#8a9b6e', '#c58b5a', '#6f8fa8', '#a482a0',
                     '#b0a06a', '#7d9a9b', '#b5837f'];

  function parseMindSvg(svg) {
    var d = { title: '', thesis: '', branches: [] }, cur = null;
    var kids = svg.childNodes;
    for (var i = 0; i < kids.length; i++) {
      var el = kids[i];
      if (el.nodeType !== 1) continue;
      var cls = ' ' + (el.getAttribute('class') || '') + ' ';
      var tag = el.tagName.toLowerCase();
      if (tag === 'rect' && cls.indexOf(' m-br ') >= 0) {
        cur = { id: '', label: '', rel: '', note: '', points: [] };
        d.branches.push(cur);
        continue;
      }
      if (tag !== 'text') continue;
      var t = (el.textContent || '').trim();
      if (cls.indexOf(' m-t ') >= 0) d.title += t;
      else if (cls.indexOf(' m-th ') >= 0)
        d.thesis += t.replace(/^命题\s*·\s*/, '').replace(/^[　\s]+/, '');
      else if (!cur) continue;
      else if (cls.indexOf(' m-id ') >= 0) cur.id = t;
      else if (cls.indexOf(' m-lb ') >= 0) cur.label = t;
      else if (cls.indexOf(' m-rel ') >= 0) cur.rel = t.replace(/[【】]/g, '');
      else if (cls.indexOf(' m-note ') >= 0) cur.note += t;
      else if (cls.indexOf(' m-cp ') >= 0) cur.points.push(t);
    }
    return d;
  }

  function mindEl(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function mindHead(lv, o) {
    var b = mindEl('button', 'mmx-head mmx-head-lv' + lv);
    b.type = 'button';
    b.setAttribute('aria-expanded', o.open ? 'true' : 'false');
    b.appendChild(mindEl('span', 'mmx-caret', '▸'));
    if (o.badge) {
      var bd = mindEl('span', 'mmx-badge', o.badge);
      bd.style.background = o.color || MIND_COLORS[0];
      b.appendChild(bd);
    }
    if (o.kicker) b.appendChild(mindEl('span', 'mmx-kicker', o.kicker));
    b.appendChild(mindEl('span', 'mmx-name', o.name || ''));
    if (o.rel) b.appendChild(mindEl('span', 'mmx-reltag', o.rel));
    if (o.count) b.appendChild(mindEl('span', 'mmx-count', o.count + ' 概念'));
    return b;
  }

  function mindNode(lv, head, kids, open) {
    var n = mindEl('div', 'mmx-node mmx-lv' + lv);
    n.appendChild(head);
    if (kids) { kids.hidden = !open; n.appendChild(kids); }
    return n;
  }

  function buildMindTree(d, ev) {
    var tree = mindEl('div', 'mmx-tree');
    var tools = mindEl('div', 'mmx-tree-tools');
    var bAll = mindEl('button', 'mmx-tool', '全部展开');
    var bNone = mindEl('button', 'mmx-tool', '全部收起');
    var bPic = mindEl('button', 'mmx-tool', '全屏看图');
    bAll.type = bNone.type = bPic.type = 'button';
    tools.appendChild(bAll); tools.appendChild(bNone); tools.appendChild(bPic);
    tools.appendChild(mindEl('span', 'mmx-tree-tip', '点节点逐级展开'));
    tree.appendChild(tools);

    var l1kids = mindEl('div', 'mmx-kids');
    d.branches.forEach(function (br, i) {
      var l2kids = mindEl('div', 'mmx-kids');
      // 分支级「论证说明」只出现一次，不往每个概念里复制
      if (br.note) {
        var bn = mindEl('div', 'mmx-branch-note');
        bn.appendChild(mindEl('span', 'mmx-bn-kicker', '这条线在论证什么'));
        bn.appendChild(mindEl('p', 'mmx-bn-txt', br.note));
        l2kids.appendChild(bn);
      }
      var pts = br.points.length ? br.points : ['（暂无关键概念）'];
      pts.forEach(function (p) {
        var detail = mindEl('div', 'mmx-detail');
        var e = ev && (ev[p] || ev[String(p).trim()]);
        if (e && e.length) {
          // 真展开：书里支撑这个概念的具体事实 / 判断（由 LLM 从全书素材归纳）
          e.forEach(function (line) {
            detail.appendChild(mindEl('p', 'mmx-ev-txt', String(line)));
          });
          detail.appendChild(mindEl('p', 'mmx-detail-meta',
            '出自议题：' + (br.id ? br.id + ' ' : '') + br.label +
            (br.rel ? '　·　' + br.rel : '')));
        } else {
          // ev === null 是数据还在路上；确认无依据才如实说没补，不拿元信息伪装
          detail.appendChild(mindEl('p', 'mmx-detail-txt', ev === null
            ? '正在载入书内依据…' : '这一层尚未补充书内依据'));
          detail.appendChild(mindEl('p', 'mmx-detail-meta',
            '出自议题：' + (br.id ? br.id + ' ' : '') + br.label));
        }
        l2kids.appendChild(mindNode(3, mindHead(3, { name: p }), detail, false));
      });
      var h2 = mindHead(2, {
        badge: br.id || String.fromCharCode(65 + i), name: br.label,
        rel: br.rel, count: br.points.length,
        color: MIND_COLORS[i % MIND_COLORS.length]
      });
      l1kids.appendChild(mindNode(2, h2, l2kids, false));
    });

    var h1 = mindHead(1, { kicker: '全书命题', name: d.thesis || d.title, open: true });
    tree.appendChild(mindNode(1, h1, l1kids, true));

    tree.addEventListener('click', function (e) {
      if (e.target === bAll || e.target === bNone || e.target === bPic) {
        if (e.target === bPic) { openSvgModal(); return; }
        var all = e.target === bAll;
        qa('.mmx-head', tree).forEach(function (h) {
          var k = h.nextElementSibling;
          if (!k) return;
          // 收起时也保留根节点展开，否则整张图空掉
          var show = all || h.className.indexOf('mmx-head-lv1') >= 0;
          h.setAttribute('aria-expanded', show ? 'true' : 'false');
          k.hidden = !show;
        });
        return;
      }
      var h = e.target.closest ? e.target.closest('.mmx-head') : null;
      if (!h || !tree.contains(h)) return;
      var k = h.nextElementSibling;
      if (!k) return;
      var open = h.getAttribute('aria-expanded') === 'true';
      h.setAttribute('aria-expanded', open ? 'false' : 'true');
      k.hidden = open;
    });
    return tree;
  }

  function initMindTree() {
    var sec = q('section#mod-svg') || q('section[data-key="svg"]');
    // 段内 sr-only 的 h2 与 section 同 id，清掉重复（导航锚点仍指 section）
    if (sec) qa('[id="mod-svg"]', sec).forEach(function (x) {
      if (x !== sec) x.removeAttribute('id');
    });
    var svg = q('svg.mmx-mind');
    if (!svg || !sec) return;                          // 占位书无图
    if (sec.querySelector('.mmx-tree')) return;        // 已初始化
    var d = parseMindSvg(svg);
    if (!d.branches.length) return;

    // 静态全景图收进折叠区，主视图换成可逐级下钻的树
    var ov = document.createElement('details');
    ov.className = 'mmx-overview';
    ov.appendChild(mindEl('summary', '', '在页内展开静态全图'));
    svg.parentNode.insertBefore(ov, svg);
    ov.appendChild(svg);
    var tree = buildMindTree(d, null);
    sec.insertBefore(tree, ov);

    /* 第四层「书内依据」从归纳数据异步取，数据页 421 个一个都不用重刷。
       有依据 → 概念展开显示实质内容；没补到 → 如实标注，不再空转。 */
    var slug = (document.body && document.body.getAttribute('data-slug')) || '';
    if (!slug || !window.fetch) return;
    function applyEvidence(ev) {
      if (!tree.parentNode) return;
      var fresh = buildMindTree(d, ev);
      // 保住用户已经点开的层级，别因为异步刷新把展开状态清掉
      var a = qa('.mmx-head', tree), b2 = qa('.mmx-head', fresh);
      for (var i = 0; i < Math.min(a.length, b2.length); i++) {
        var open = a[i].getAttribute('aria-expanded') === 'true';
        b2[i].setAttribute('aria-expanded', open ? 'true' : 'false');
        var k = b2[i].nextElementSibling;
        if (k) k.hidden = !open;
      }
      tree.parentNode.replaceChild(fresh, tree);
      tree = fresh;
    }
    fetch('../../../data/mm-graph/' + encodeURIComponent(slug) + '.json')
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) { applyEvidence((j && j.evidence) || {}); })
      .catch(function () { applyEvidence({}); });
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

  /* ── 听书（TTS 点块朗读 + 右上角配置）──────────────────────
   * 改动只在本文件，所有书的 combined.html 自动生效（壳页不含渲染逻辑）。
   * - 右上角 #rdSpeakBtn 是唯一入口，点击展开 #rdSpeakPanel 配置面板：
   *   音色（女声/男声/台湾腔快捷 + 全部系统语音下拉）、语速、音调、音量、
   *   静音、停止。配置存 localStorage，改参数即时重读当前块。
   *   按钮位置由 placeBtn() 动态测量右上角已有 fixed 按钮向左避让，
   *   避免与 Aa(12) / 分享(54) / AI 大纲(96) 挤在一起。
   * - 点哪读哪：朗读「点击位置所属的最小语义块」，再点同一块暂停。
   *   粒度：原句 li > 要点 li > 小节 div.sec > 段落/标题 > section（兜底）。
   *   AI 领读的小节是 div.sec 而非 section 标签，整章才是一个 section。
   * - 默认静音：打开详情页不出声；首次点块自动开声（静音状态不持久化）。
   */
  function initSpeak() {
    if (!('speechSynthesis' in window) || typeof SpeechSynthesisUtterance === 'undefined') return;
    var synth = window.speechSynthesis;
    var main = q('#rdBody');
    if (!main) return;

    /* ── 用户配置（音色/语速/音调/音量持久化，静音每次打开都恢复默认）── */
    var CFG_KEY = 'rd-speak-cfg';
    function loadPrefs() {
      try { return JSON.parse(localStorage.getItem(CFG_KEY) || '{}') || {}; } catch (e) { return {}; }
    }
    function num(v, lo, hi, d) {
      var n = parseFloat(v);
      return isFinite(n) ? Math.min(hi, Math.max(lo, n)) : d;
    }
    var prefs = loadPrefs();
    var rate = num(prefs.rate, 0.5, 2, 1);
    var pitch = num(prefs.pitch, 0.5, 1.5, 1);
    var volume = num(prefs.volume, 0, 1, 1);
    var voiceURI = prefs.voiceURI || '__auto__';
    function savePrefs() {
      try {
        localStorage.setItem(CFG_KEY, JSON.stringify({
          rate: rate, pitch: pitch, volume: volume, voiceURI: voiceURI
        }));
      } catch (e) {}
    }

    var muted = true;        // 默认静音
    var curUnit = null;      // 当前正在朗读的单元
    var utter = null;
    var speaking = false;

    /* ── 朗读单元：从细到粗，closest 取 DOM 上最近的一个 ────────
       section 只作兜底，点 AI 领读里的内容时绝不能往上命中整章。 */
    var UNIT_SEL = [
      'ul.quote > li', 'ul.point > li',   // 原句 / 要点
      'div.sec',                          // AI 领读小节
      '.mmx-detail', '.mmx-node',         // 结构导图树节点
      'li', 'blockquote', 'p',            // 其它模块：列表项 / 引文 / 段落
      'h2', 'h3', 'h4', 'h5',
      'section'                           // 兜底：整模块
    ].join(', ');
    /* 交互元素 / 折叠控件 / 统计行 / 设置面板：只做原本的动作 */
    var SKIP_SEL = 'a, button, summary, [data-no-speak], .mmx-head, .mmx-caret, ' +
                   '.mmx-stat, input, select, textarea, label, .rd-speak-skip, ' +
                   '#rdSpeakPanel, #rdSpeakPanel *';

    function resolveUnit(t) {
      if (!t || !t.closest) return null;
      if (t.closest(SKIP_SEL)) return null;
      var unit = t.closest(UNIT_SEL);
      if (!unit || !main.contains(unit)) return null;
      // 点小标题 → 读它所属的整个小节，而不是只念标题那几个字
      if (/^H[2-5]$/.test(unit.tagName) && unit.parentNode &&
          unit.parentNode.classList && unit.parentNode.classList.contains('sec')) {
        unit = unit.parentNode;
      }
      return unit;
    }

    /* 取朗读文本：剔除样式/脚本、装饰符号、以及与要点重复的「本小节汇总」 */
    function collectText(unit) {
      if (unit.matches && unit.matches('.mmx-mod-note, .mmx-stat')) return '';
      var c = unit.cloneNode(true);
      qa('script, style, noscript, [aria-hidden="true"], [data-no-speak], ' +
         'ul.quote.quote-node, .mmx-stat, .mmx-caret, .mmx-mod-note', c)
        .forEach(function (n) { if (n.parentNode) n.parentNode.removeChild(n); });
      return (c.textContent || '').replace(/\s+/g, ' ').trim();
    }

    /* ── 语音：分类 + 选中 + 下拉 ───────────────────────────── */
    function allVoices() { return synth.getVoices() || []; }
    function isZh(v) { return /^zh|cmn|chinese/i.test(v.lang || ''); }
    function isFemale(v) {
      return /female|女|ting|xiao|yao|hui|mei|hanhan|yating|tracy|sinji|vivi|google.*(國語|普通话)/i.test(v.name || '');
    }
    function isMale(v) {
      return /male|男|daniel|kangkang|yunxi|zhiwei|jasper|liang|yunyang|yunqi/i.test(v.name || '');
    }
    function isTw(v) { return /tw|hant|taiwan|台灣|國語/i.test((v.lang || '') + ' ' + (v.name || '')); }
    function voiceKey(v) { return v.voiceURI || v.name || ''; }
    function voiceLabel(v) {
      var s = (v.lang || '') + ' ' + (v.name || '');
      var region = isTw(v) ? '台湾' : /hk|yue|粵|粤/i.test(s) ? '粤语'
                 : isZh(v) ? '普通话' : (v.lang || '其他');
      var sex = isFemale(v) ? '♀' : isMale(v) ? '♂' : '·';
      return '[' + region + sex + '] ' + (v.name || '') + ' · ' + (v.lang || '');
    }
    function autoVoice() {
      var vs = allVoices();
      if (!vs.length) return null;
      var zh = vs.filter(isZh), pool = zh.length ? zh : vs;
      var fem = pool.filter(isFemale);
      return fem[0] || pool[0] || null;
    }
    function currentVoice() {
      if (voiceURI !== '__auto__') {
        var vs = allVoices();
        for (var i = 0; i < vs.length; i++) if (voiceKey(vs[i]) === voiceURI) return vs[i];
      }
      return autoVoice();   // 语音列表可能异步加载，每次朗读现取
    }
    function firstBy(kind) {
      var vs = allVoices();
      var zh = vs.filter(isZh), pool = zh.length ? zh : vs, hit = [];
      if (kind === 'female') hit = pool.filter(isFemale);
      else if (kind === 'male') hit = pool.filter(isMale);
      else if (kind === 'tw') {
        hit = pool.filter(function (v) { return isTw(v) && isFemale(v); });
        if (!hit.length) hit = pool.filter(isTw);
      } else return '__auto__';
      return hit.length ? voiceKey(hit[0]) : '__auto__';
    }
    function fillVoices() {
      var sel = q('#rdSpVoice', panel);
      if (!sel) return;
      var vs = allVoices();
      sel.innerHTML = '';
      var o0 = document.createElement('option');
      o0.value = '__auto__'; o0.textContent = '自动（中文女声优先）';
      sel.appendChild(o0);
      vs.slice().sort(function (a, b) {
        var za = isZh(a) ? 1 : 0, zb = isZh(b) ? 1 : 0;
        if (za !== zb) return zb - za;
        return (a.name || '').localeCompare(b.name || '');
      }).forEach(function (v) {
        var o = document.createElement('option');
        o.value = voiceKey(v); o.textContent = voiceLabel(v);
        sel.appendChild(o);
      });
      sel.value = voiceURI;
      if (!sel.value) { sel.value = '__auto__'; voiceURI = '__auto__'; }
    }

    /* ── 唯一入口按钮 + 配置面板 ────────────────────────────── */
    var btn = document.createElement('button');
    btn.id = 'rdSpeakBtn';
    btn.type = 'button';
    btn.setAttribute('aria-label', '听书设置');

    var panel = document.createElement('div');
    panel.id = 'rdSpeakPanel';
    panel.hidden = true;
    panel.innerHTML =
      '<div class="rd-sp-head"><b>🎧 听书设置</b>' +
        '<button type="button" class="rd-sp-x" aria-label="关闭">×</button></div>' +
      '<div class="rd-sp-state" id="rdSpState">未朗读 · 默认静音</div>' +
      '<label class="rd-sp-lab">音色<select id="rdSpVoice"></select></label>' +
      '<div class="rd-sp-chips">' +
        '<button type="button" data-voice="female">女声</button>' +
        '<button type="button" data-voice="male">男声</button>' +
        '<button type="button" data-voice="tw">台湾腔</button>' +
        '<button type="button" data-voice="auto">自动</button>' +
      '</div>' +
      '<label class="rd-sp-lab">语速 <span id="rdSpRateVal">1.0×</span>' +
        '<input type="range" id="rdSpRate" min="0.5" max="2" step="0.1"></label>' +
      '<label class="rd-sp-lab">音调 <span id="rdSpPitchVal">1.0</span>' +
        '<input type="range" id="rdSpPitch" min="0.5" max="1.5" step="0.1"></label>' +
      '<label class="rd-sp-lab">音量 <span id="rdSpVolVal">100%</span>' +
        '<input type="range" id="rdSpVol" min="0" max="1" step="0.05"></label>' +
      '<div class="rd-sp-foot">' +
        '<button type="button" id="rdSpMute">🔇 已静音</button>' +
        '<button type="button" id="rdSpStop">⏹ 停止</button>' +
      '</div>' +
      '<p class="rd-sp-tip">点正文任意段落朗读，再点同一处暂停 · 设置自动保存</p>';

    document.body.appendChild(btn);
    document.body.appendChild(panel);

    function refresh() {
      btn.textContent = muted ? '🔇' : '🔊';
      btn.title = muted ? '听书设置（当前静音）· 点此配置音色 / 语速' : '听书设置（当前有声）· 点此配置音色 / 语速';
      btn.classList.toggle('on', !muted);
      var mb = q('#rdSpMute', panel);
      if (mb) mb.textContent = muted ? '🔇 已静音' : '🔊 有声';
      var st = q('#rdSpState', panel);
      if (st) st.textContent = speaking ? '正在朗读…' : (muted ? '未朗读 · 默认静音' : '未朗读 · 点正文开始');
    }

    /* 动态避让：测右上角已有 fixed 按钮，把入口放到它们最左侧再往左 8px。
       share.js / visit-stats.js 是延迟注入的，所以多跑几次 + 跟随 resize。 */
    function placeBtn() {
      var W = document.documentElement.clientWidth || window.innerWidth;
      var minLeft = W;
      qa('button, a').forEach(function (el) {
        if (el === btn || panel.contains(el)) return;
        var s = getComputedStyle(el);
        if (s.position !== 'fixed') return;
        var r = el.getBoundingClientRect();
        if (r.width < 12 || r.height < 12 || r.top > 60 || r.left < W * 0.5) return;
        if (r.left < minLeft) minLeft = r.left;
      });
      btn.style.right = Math.round(minLeft >= W ? 12 : W - minLeft + 8) + 'px';
    }

    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      var show = panel.hidden;
      if (show) {
        var rp = q('#rdPanel');           // 与「Aa」阅读设置面板互斥
        if (rp) rp.hidden = true;
        fillVoices();
      }
      panel.hidden = !show;
      refresh();
    });
    panel.addEventListener('click', function (e) { e.stopPropagation(); });
    document.addEventListener('click', function (e) {
      if (!panel.hidden && !panel.contains(e.target) && e.target !== btn) panel.hidden = true;
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') panel.hidden = true;
    });
    q('.rd-sp-x', panel).addEventListener('click', function () { panel.hidden = true; });
    /* 「Aa」阅读设置的 onclick 带 stopPropagation，document 上的关闭监听收不到；
       直接在同一元素补一个监听，保证两个面板互斥、不会叠在右上角。 */
    var fab = q('#rdFab');
    if (fab) fab.addEventListener('click', function () { panel.hidden = true; });

    /* 改配置后若正在朗读，重读当前块以立即生效（滑块拖动中不重读） */
    function relive() {
      var u = curUnit;
      if (u && speaking) speak(u); else refresh();
    }

    var sel = q('#rdSpVoice', panel);
    sel.addEventListener('change', function () {
      voiceURI = sel.value || '__auto__';
      qa('.rd-sp-chips button', panel).forEach(function (x) { x.classList.remove('on'); });
      savePrefs(); relive();
    });
    qa('.rd-sp-chips button', panel).forEach(function (b) {
      b.addEventListener('click', function () {
        voiceURI = firstBy(b.getAttribute('data-voice'));
        sel.value = voiceURI;
        if (!sel.value) { sel.value = '__auto__'; voiceURI = '__auto__'; }
        qa('.rd-sp-chips button', panel).forEach(function (x) { x.classList.toggle('on', x === b); });
        savePrefs(); relive();
      });
    });

    var rEl = q('#rdSpRate', panel), pEl = q('#rdSpPitch', panel), vEl = q('#rdSpVol', panel);
    function setLabel(el, txt) { el.textContent = txt; }
    rEl.value = rate; pEl.value = pitch; vEl.value = volume;
    setLabel(q('#rdSpRateVal', panel), rate.toFixed(1) + '×');
    setLabel(q('#rdSpPitchVal', panel), pitch.toFixed(1));
    setLabel(q('#rdSpVolVal', panel), Math.round(volume * 100) + '%');
    rEl.addEventListener('input', function () {
      rate = parseFloat(rEl.value);
      setLabel(q('#rdSpRateVal', panel), rate.toFixed(1) + '×');
      savePrefs();
    });
    pEl.addEventListener('input', function () {
      pitch = parseFloat(pEl.value);
      setLabel(q('#rdSpPitchVal', panel), pitch.toFixed(1));
      savePrefs();
    });
    vEl.addEventListener('input', function () {
      volume = parseFloat(vEl.value);
      setLabel(q('#rdSpVolVal', panel), Math.round(volume * 100) + '%');
      if (utter) utter.volume = muted ? 0 : volume;
      savePrefs();
    });
    rEl.addEventListener('change', relive);
    pEl.addEventListener('change', relive);
    vEl.addEventListener('change', relive);

    q('#rdSpMute', panel).addEventListener('click', function () {
      muted = !muted;
      if (utter) utter.volume = muted ? 0 : volume;
      refresh();
    });
    q('#rdSpStop', panel).addEventListener('click', function () { stopAll(); refresh(); });

    function stopAll() {
      // 无条件 cancel：speak() 刚调用时 speaking 可能仍是 false，但已有排队语音
      try { synth.cancel(); } catch (e) {}
      speaking = false; curUnit = null; utter = null;
      qa('#rdBody .speaking').forEach(function (s) { s.classList.remove('speaking'); });
    }

    function speak(unit) {
      var txt = collectText(unit);
      if (!txt) return;
      stopAll();
      utter = new SpeechSynthesisUtterance(txt);
      utter.lang = 'zh-CN';
      var v = currentVoice();
      if (v) utter.voice = v;
      utter.rate = rate; utter.pitch = pitch; utter.volume = muted ? 0 : volume;
      utter.onend = function () {
        unit.classList.remove('speaking');
        speaking = false; curUnit = null; utter = null; refresh();
      };
      utter.onerror = utter.onend;
      unit.classList.add('speaking');
      curUnit = unit; speaking = true;
      synth.speak(utter);
      refresh();
    }

    main.addEventListener('click', function (e) {
      var unit = resolveUnit(e.target);
      if (!unit) return;
      if (curUnit === unit && speaking) { stopAll(); refresh(); return; }  // 再点同一块 → 暂停
      if (muted) { muted = false; refresh(); }                            // 首次点块自动开声
      speak(unit);
    });

    if (typeof synth.onvoiceschanged !== 'undefined') {
      synth.onvoiceschanged = function () { fillVoices(); };
    }
    fillVoices();
    refresh();
    placeBtn();
    setTimeout(placeBtn, 300);
    setTimeout(placeBtn, 1200);
    window.addEventListener('resize', placeBtn);

    // 切书/翻页/离开时停掉，避免后台继续朗读
    window.addEventListener('beforeunload', stopAll);
  }

  function boot() {
    initSettings();
    initSpeak();
    addHomeLink();
    /* 先立海报墙：封面立刻开始下载，不等正文数据。
       但要先知道这本有没有封面（没封面的书不开墙）——3KB 的 hero.json 一般
       几十毫秒就到，最多等 150ms，之后不管有没有都照常立墙，避免卡首屏 */
    var heroStarted = false;
    var startHero = function () { if (heroStarted) return; heroStarted = true; addHero(); };
    loadHeroData(startHero);
    setTimeout(startHero, 150);

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


/* we-read 访问统计徽章 · 自举（workbuddy-agent 2026-11-04，勿删） */
(function(){
  if(window.__wrVisitBoot)return;window.__wrVisitBoot=1;
  function boot(){
    var base=location.pathname.replace(/\/reading-notes\/.*$/,'/');
    var s=document.createElement('script');
    s.src=base+'assets/js/visit-stats.js?v=20261104b';
    s.defer=true;
    (document.body||document.documentElement).appendChild(s);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();
