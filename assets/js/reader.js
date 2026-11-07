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
      /* AI 领读标题下的流水线说明句（「章节目录与 AI 大纲融合为一棵树…」）：
         全站 339 本都有，改这里一处即可，不动任何 combined-data.html。 */
      .replace(/<p class="small">([\s\S]*?)<\/p>\s*/g, function (m, inner) {
        return /章节目录|AI\s*大纲融合|融合为一棵树/.test(inner) ? '' : m;
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
    markModelTags(main);
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
    var local = 'https://cdn.js-dev.cn/assets/covers/' + encodeURIComponent(slug) + '.jpg';
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
        var local = 'https://cdn.js-dev.cn/assets/covers/' + encodeURIComponent(slug) + '.jpg';
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
        /* 书名上移到顶部标题栏（与 ← / ☰ / 分享 / Aa 同处一行），
           吸顶条里不再重复显示，避免独占一行、中间留白 */
        var tt = document.getElementById('rdTopTitle');
        if (!tt) { tt = document.createElement('div'); tt.id = 'rdTopTitle'; tt.className = 'rd-toptitle'; document.body.appendChild(tt); }
        tt.innerHTML = '';
        tt.appendChild(tlink);
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
         armTitleLink 是同步回调，提前调用会因 a.isConnected=false 直接跳过。
         书名已移到顶部标题栏 #rdTopTitle（tt），从这里取链接节点 */
      var tlink2 = (tt || stick).querySelector('#rdTitleLink');
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
  /* 模型在「更高维度 / 往日今时」里自带的【书中主张】【外部证据】标签，
     纯文本时埋在长段落中间谁也看不见。提成小徽章后，读者一眼看出这段是
     主张、证据还是综合判断。只动这两块的直接子段落，别的模块不碰。 */
  function markModelTags(root) {
    var ps = qa('section[data-key="higher"]>p, section[data-key="thennow"]>p', root);
    ps.forEach(function (p) {
      if (!/【[^】]{2,10}】/.test(p.innerHTML)) return;
      p.innerHTML = p.innerHTML.replace(/【([^】]{2,10})】/g, '<b class="rd-tag">$1</b>');
    });
  }

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

  /* ── 听书（TTS 点块朗读）v4 ───────────────────────────────────
   * - 入口并入壳页已有的「Aa」阅读设置面板 #rdPanel（和字号/段距/主题放一起），
   *   右上角不再新增任何按钮；点 Aa 才展开配置、才枚举系统语音（按需调用）。
   * - 朗读时底部浮出控制条 #rdSpeakBar（暂停/继续、停止、静音、设置），
   *   移动端拇指可达，不必去右上角找按钮。
   * - 点正文任意语义块朗读该块（细粒度），再点同一块暂停；默认静音，
   *   首次点块自动开声（静音状态不持久化）。
   * - 设备/浏览器缺 Web Speech API 时 UI 照常创建，朗读时给明确提示，
   *   不再整体 return（否则移动端会出现「点文字没反应、也找不到按钮」）。
   */
  function initSpeak() {
    var main = q('#rdBody');
    if (!main) return;
    var hasTTS = ('speechSynthesis' in window) &&
                 typeof window.SpeechSynthesisUtterance !== 'undefined';
    var synth = hasTTS ? window.speechSynthesis : null;
    /* 服务端 TTS 代理地址。设置后一级模块播放键用 <audio> 播放合成音频，
       任何浏览器（含微信 webview）都能出声；留空则退回 Web Speech。
       默认走 WorkBuddy 云端托管（tools/tts-proxy/ 同一份代码）；
       想换成自己的服务器，只要在页面里前置 window.RD_TTS_BASE = 'https://your.host/tts'。 */
    var TTS_DEFAULT = 'https://a32eb29ccf0373711.app.workbuddy.host/tts?sharecode=N3AWQXFAIQ';
    var TTS_BASE = (typeof window.RD_TTS_BASE === 'string' && window.RD_TTS_BASE.trim())
      ? window.RD_TTS_BASE.trim() : TTS_DEFAULT;

    /* ── 用户配置（音色/语速/音调/音量持久化，静音每次打开恢复默认）── */
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

    /* ── 云端音色（只收「念书不刺耳」的四个）────────────────────
       所有设备默认都走服务端 edge-tts 的晓晓（最早那个自然女声），
       不跟着历史配置乱变；本机 SAPI 语音只在下拉里显式选中时才用。
       其余三个是给人挑的备选，选完会记住。
       必须与服务端 tools/tts-proxy 白名单一致，否则会被静默换成晓晓。 */
    var CLOUD_VOICES = [
      { uri: 'zh-CN-XiaoxiaoNeural',  label: '晓晓 · 默认女声' },
      { uri: 'zh-CN-XiaoyiNeural',    label: '晓伊 · 年轻女声' },
      { uri: 'zh-CN-YunxiNeural',     label: '云希 · 少年男声' },
      { uri: 'zh-TW-HsiaoChenNeural', label: '曉臻 · 台湾女声' }
    ];
    var CLOUD_DEFAULT = CLOUD_VOICES[0].uri;
    function isCloudVoice(u) { return /Neural$/.test(u || ''); }
    function cloudLabel(u) {
      for (var i = 0; i < CLOUD_VOICES.length; i++) {
        if (CLOUD_VOICES[i].uri === u) return CLOUD_VOICES[i].label;
      }
      return '';
    }
    var voiceURI = prefs.voiceURI || '__auto__';
    /* 历史配置里可能残留上一版列过的云端音色（曉雨 / 雲哲 …），
       现在不在清单里就回默认，免得又被带成别的腔调。 */
    if (isCloudVoice(voiceURI) && !cloudLabel(voiceURI)) voiceURI = '__auto__';
    /* 一次性迁移：老版本在 Windows 上把「默认」写成了本机 SAPI 语音
       （Huihui / Yaoyao …），刷新后仍停在机械音。旧配置里的本机音色
       统一回到云端晓晓；之后用户再显式选本机语音会被记住。 */
    try {
      if (voiceURI !== '__auto__' && !isCloudVoice(voiceURI) &&
          localStorage.getItem('rd-speak-v2') !== '1') voiceURI = '__auto__';
    } catch (e) {}
    function savePrefs() {
      try {
        localStorage.setItem('rd-speak-v2', '1');
        localStorage.setItem(CFG_KEY, JSON.stringify({
          rate: rate, pitch: pitch, volume: volume, voiceURI: voiceURI
        }));
      } catch (e) {}
    }

    var muted = true;        // 默认静音
    var curUnit = null;      // 当前正在朗读的单元
    var lastUnit = null;     // 暂停后用于「继续」
    var utter = null;
    var speaking = false;
    var activeChip = voiceURI === '__auto__' ? 'auto' : null;  // 当前音色快捷项

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
    /* 交互元素 / 折叠控件 / 统计行 / 两个听书 UI：只做原本的动作 */
    var SKIP_SEL = 'a, button, summary, [data-no-speak], .mmx-head, .mmx-caret, ' +
                   '.mmx-stat, input, select, textarea, label, .rd-speak-skip, ' +
                   '#rdSpeakBar, #rdSpeakBar *, #rdPanel, #rdPanel *';

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

    /* ── 语音：分类 + 选中 + 下拉（缺 TTS 时 allVoices 恒为空数组）── */
    function allVoices() { return (synth && synth.getVoices()) || []; }
    function isZh(v) { return /^zh|cmn|chinese/i.test(v.lang || ''); }
    function isFemale(v) {
      return /female|女|ting|xiao|yao|hui|mei|hanhan|yating|tracy|sinji|vivi|hsiao|meijia|曉|晓|慧|婷|雅|臻|google.*(國語|普通话)/i.test(v.name || '');
    }
    function isMale(v) {
      /* Azure / Windows / macOS 常见中文男声名；名字不含性别词的系统语音
         无法自动判定，用户可直接在「音色」下拉里按标签 [地区♂] 手选。 */
      return /male|男|daniel|kangkang|yunxi|yunyang|yunqi|yunye|yunxia|yunjian|yunfeng|yunhao|yunze|zhiwei|zhiming|zhigang|zhiqiang|jasper|liang|云希|云扬|云健|康康|志伟|志强/i.test(v.name || '');
    }
    function isTw(v) {
      var s = (v.lang || '') + ' ' + (v.name || '');
      return /zh[-_]?tw|zh[-_]?hant|cmn[-_]?hant|taiwan|台灣|台湾|國語|国语|hsiao|yunjhe|meijia/i.test(s);
    }
    /* 快捷项对应的云端音色（本机没这个音色时兜底）；粤语服务端还没发布，先不给 */
    function cloudKind(kind) {
      if (kind === 'auto' || kind === 'female') return CLOUD_DEFAULT;
      if (kind === 'male') return 'zh-CN-YunxiNeural';
      if (kind === 'tw') return 'zh-TW-HsiaoChenNeural';
      return null;
    }
    /* 某个快捷音色能不能用：云端有同名音色就优先云端，否则看本机是否装了 */
    function hasKind(kind) {
      if (kind === 'auto') return true;
      if (TTS_BASE && cloudKind(kind)) return true;   // 云端优先：自然音色
      return firstBy(kind) !== '__auto__';            // 云端没开才退回本机
    }
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
    /* 下拉里只列中文 / 英文 / 德文：系统语音动辄几十种，[it-IT] [fr-FR] 这种
       占满一屏还找不到想要的。朗读本身不受影响（自动 / 快捷键照旧按中文挑）。 */
    var LANG_OK = /^(zh|cmn|yue|en|de)([-_]|$)/i;
    function isListed(v) {
      if (!v.lang) return true;        // 系统没给 lang，别误删唯一可用音色
      if (LANG_OK.test(v.lang)) return true;
      return /chinese|english|german|中文|普通话|粤语|粵語/i.test((v.name || '') + ' ' + v.lang);
    }
    function fillVoices() {
      var sel = q('#rdSpVoice', box);
      if (!sel) return;
      var vs = allVoices().filter(isListed);
      sel.innerHTML = '';
      var o0 = document.createElement('option');
      o0.value = '__auto__';
      o0.textContent = TTS_BASE ? '默认 · 晓晓（云端）'
                     : vs.length ? '默认（本机中文女声）'
                     : '当前设备没有可用语音';
      sel.appendChild(o0);
      var rank = function (v) {
        var s = (v.lang || '') + (v.name || '');
        return isZh(v) ? 2 : /yue|粵|粤/i.test(s) ? 1 : 0;   // 普通话 → 粤语 → 英/德
      };
      vs.slice().sort(function (a, b) {
        var za = rank(a), zb = rank(b);
        if (za !== zb) return zb - za;
        return (a.name || '').localeCompare(b.name || '');
      }).forEach(function (v) {
        var o = document.createElement('option');
        o.value = voiceKey(v); o.textContent = voiceLabel(v);
        sel.appendChild(o);
      });
      /* 默认项在所有设备上都固定代表晓晓，所以云端组只挂另外三个备选，
         不重复列一个「晓晓」。手机 / Windows 看到的清单因此完全一致。 */
      if (TTS_BASE) {
        var grp = document.createElement('optgroup');
        grp.label = '云端音色（需联网）';
        CLOUD_VOICES.slice(1).forEach(function (c) {
          var o = document.createElement('option');
          o.value = c.uri; o.textContent = c.label;
          grp.appendChild(o);
        });
        sel.appendChild(grp);
      }
      sel.value = voiceURI;
      if (!sel.value) { sel.value = '__auto__'; voiceURI = '__auto__'; }
      sel.disabled = !vs.length && !TTS_BASE;
      setHint(voiceSummary());
      refreshChips();
    }

    /* ── 配置区：注入已有的「Aa」阅读设置面板 ─────────────────── */
    var rdPanel = q('#rdPanel');
    var box = null;
    if (rdPanel) {
      box = document.createElement('div');
      box.className = 'rd-speak-box rd-speak-skip';
      box.innerHTML =
        '<div class="rd-sp-hd">🎧 听书 <span id="rdSpState">默认静音</span></div>' +
        '<div class="rd-sp-voice">' +
          '<label class="rd-sp-lab">音色<select id="rdSpVoice"></select></label>' +
          '<button type="button" id="rdSpTry" class="rd-sp-try">试听</button>' +
        '</div>' +
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
        '<p class="rd-sp-hint" id="rdSpHint" hidden></p>' +
        '<p class="rd-sp-tip">点正文任意段落朗读，再点同一处暂停 · 设置自动保存</p>' +
        '<details class="rd-sp-help"><summary>没有男声 / 台湾腔？</summary>' +
          '<p>音色由设备系统提供，网页无法下发语音包；灰显的按钮表示本机没装这类语音。' +
          'Windows：设置 → 时间和语言 → 语音 → 添加语音（选中文(台湾)等）；' +
          'macOS：系统设置 → 辅助功能 → 朗读内容 → 系统声音 → 管理声音；' +
          '手机：在系统设置里添加中文语音包后刷新本页。也可直接在上方「音色」下拉里' +
          '按 [地区♀/♂] 标签挑一个本机已有的。</p>' +
        '</details>';
      rdPanel.appendChild(box);
      rdPanel.classList.add('rd-has-speak');
    }

    /* ── 底部朗读控制条：移动端拇指可达 ───────────────────────── */
    var bar = document.createElement('div');
    bar.id = 'rdSpeakBar';
    bar.hidden = true;
    bar.setAttribute('role', 'group');
    bar.setAttribute('aria-label', '听书控制');
    bar.innerHTML =
      '<span class="rd-sb-txt" id="rdSbTxt"></span>' +
      '<button type="button" id="rdSbPause" aria-label="暂停">⏸</button>' +
      '<button type="button" id="rdSbStop" aria-label="停止">⏹</button>' +
      '<button type="button" id="rdSbMute" aria-label="静音">🔇</button>' +
      '<button type="button" id="rdSbSet" aria-label="听书设置">⚙</button>';
    document.body.appendChild(bar);
    /* 控制条上的点击不要冒泡：否则会触发 Aa 面板的「点外部关闭」监听 */
    bar.addEventListener('click', function (e) { e.stopPropagation(); });

    function refresh() {
      var st = q('#rdSpState', box);
      var can = usingLocal() || !!TTS_BASE;
      if (st) st.textContent = !can ? '当前设备没有可用语音'
                            : speaking ? (usingLocal() ? '本机语音朗读中…' : '云端语音朗读中…')
                            : (muted ? '默认静音' : '点正文或模块 ▶ 开始');
      var mb = q('#rdSpMute', box);
      if (mb) mb.textContent = muted ? '🔇 已静音' : '🔊 有声';
      var bm = q('#rdSbMute', bar);
      if (bm) { bm.textContent = muted ? '🔇' : '🔊'; bm.setAttribute('aria-label', muted ? '取消静音' : '静音'); }
      var bp = q('#rdSbPause', bar);
      if (bp) {
        var on = playing && !paused;
        bp.textContent = on ? '⏸' : '▶';
        bp.setAttribute('aria-label', on ? '暂停' : '继续');
      }
      refreshChips();
    }
    /* 配置面板内的反馈：本机语音数量 + 音色不可用的明确原因。
       之前 chunk 无匹配时静默回落到「自动」却照样高亮，用户会以为点了没生效。 */
    function setHint(msg, warn) {
      var h = q('#rdSpHint', box);
      if (!h) return;
      h.textContent = msg || '';
      h.hidden = !msg;
      h.classList.toggle('warn', !!warn);
    }
    function refreshChips() {
      qa('.rd-sp-chips button', box).forEach(function (x) {
        var kind = x.getAttribute('data-voice'), ok = hasKind(kind);
        x.classList.toggle('on', kind === activeChip);
        x.classList.toggle('na', !ok);
        x.title = ok ? '' : '本机未安装该音色（点此查看添加方法）';
      });
    }
    function voiceSummary() {
      var all = allVoices(), vs = all.filter(isListed), zh = vs.filter(isZh).length;
      if (!vs.length) {
        return TTS_BASE
          ? '本机没有系统语音，朗读走云端晓晓（另有 ' + (CLOUD_VOICES.length - 1) + ' 个备选）· 需联网，首次约 1 秒'
          : '当前设备没有可用语音，建议换 Chrome / Edge / Safari 打开';
      }
      var hid = all.length - vs.length;
      /* 已经显式选了别的音色时，别再说「默认走云端晓晓」，免得和下拉选中项矛盾 */
      var lead = (TTS_BASE && voiceURI === '__auto__') ? '默认走云端晓晓 · ' : '';
      return lead + '本机可用语音 ' + vs.length + ' 个（中文 ' + zh + ' 个）' +
             (hid > 0 ? '，已隐藏非中/英/德 ' + hid + ' 个' : '') +
             (TTS_BASE ? ' · 云端备选 ' + (CLOUD_VOICES.length - 1) + ' 个（晓晓在默认项）' : '');
    }
    function showBar(txt, warn) {
      var t = q('#rdSbTxt', bar);
      if (t) t.textContent = txt || '';
      bar.classList.toggle('rd-sb-warn', !!warn);
      bar.hidden = false;
      refresh();
    }
    function hideBar() { bar.hidden = true; refresh(); }

    /* ── 一级模块播放键 + 服务端 TTS 音频播放 ─────────────────────
     * 移动端整块不好点，为每个一级模块（#rdBody 直接子 section）加一个显式播放键。
     * - 配了 TTS_BASE：把模块文本按句切成小块，逐块向服务端取 MP3，用 <audio>
     *   顺序播放（任何浏览器含微信都能出声），支持暂停/继续/停止。
     * - 没配：退回 Web Speech 整段朗读；本机也无语音时仅脉冲 + 提示。
     */
    var ttsAudio = null, modSec = null, modFallback = false;
    var ttsSeq = 0, ttsObjUrl = null;
    /* ── 统一朗读引擎：按 DOM 单元排队 ──────────────────────────
       之前一套「整模块切块喂服务端」、一套「单个单元喂 Web Speech」，
       结果是：点块不切换、暂停键管不到音频、高亮对不上、还闪一下。
       现在只有一条路：queue 里放 DOM 单元，读完一个高亮一个。
       - 本机有中文语音包就优先本地（零延迟，不请求服务端）
       - 没有（手机/微信 webview 常见）才走服务端合成
    */
    var queue = [], qi = -1, playing = false, paused = false, seqLocal = 0;
    var preIdx = -1, preBlob = null;          // 服务端下一块预取
    var LEAF_SEL = 'ul.quote > li, ul.point > li, div.sec, .mmx-detail, .mmx-node, ' +
                   'li, blockquote, p, h2, h3, h4, h5';

    /* 默认项（__auto__）固定走云端晓晓：Windows / macOS 自带的 SAPI 语音
       （Huihui / Yaoyao / Kangkang …）是老式拼接音，和手机上那个自然女声
       不是一回事。只有用户在下拉里明确挑了某个本机语音，才用 Web Speech；
       云端服务不可用时 playServer 会自动回退本机，离线仍能出声。 */
    function usingLocal() {
      if (isCloudVoice(voiceURI)) return false;
      if (voiceURI === '__auto__' && TTS_BASE) return false;
      return hasTTS && allVoices().length > 0;
    }

    /* 收集容器内所有「最小语义单元」，按文档顺序 */
    function unitsIn(root) {
      var out = [];
      qa(LEAF_SEL, root).forEach(function (e) {
        if (e.closest(SKIP_SEL)) return;
        var p = e.parentNode;
        while (p && p !== root) {              // li / div.sec 里的 p 归外层单元
          if (p.matches && p.matches('div.sec, li, blockquote')) return;
          p = p.parentNode;
        }
        if (collectText(e)) out.push(e);
      });
      if (!out.length && collectText(root)) out.push(root);
      return out;
    }

    function markNow(u) {
      qa('#rdBody .speaking').forEach(function (s) { if (s !== u) s.classList.remove('speaking'); });
      if (!u) return;
      u.classList.add('speaking');
      /* 核心追问的朗读单元是里层的问句 / 答句，序号圆点画在外层 .mmx-qa 上，
         同步一份 class，序号才会跟着转绿 */
      var wrap = u.closest && u.closest('.mmx-qa');
      if (wrap && wrap !== u && !wrap.classList.contains('speaking')) wrap.classList.add('speaking');
      /* 读到的单元跑到屏幕外时轻轻拉回视口，让高亮始终看得见；
         已在视野内就不动，避免打断用户自己翻看。
         qi === 0 是刚被点的那一块（用户手指就在那儿），绝不滚 —— 安卓上
         平滑滚动本身就是一次整屏重绘，看起来像「闪一下」。 */
      if (playing && !paused && qi > 0) {
        var r = u.getBoundingClientRect(), vh = window.innerHeight;
        if (r.bottom < 96 || r.top > vh - 40) {
          try { u.scrollIntoView({ block: 'center', behavior: 'smooth' }); }
          catch (e) { try { u.scrollIntoView(); } catch (e2) {} }
        }
      }
    }
    function textOf(u) {
      var t = u ? collectText(u) : '';
      return t.length > 26 ? t.slice(0, 26) + '…' : t;
    }
    function barLabel() {
      var name = modSec ? modLabel(modSec) : '';
      return (name ? name + ' · ' : '') + (paused ? '已暂停' : '朗读中');
    }
    function ensureAudio() {
      if (ttsAudio) return ttsAudio;
      ttsAudio = new Audio();
      ttsAudio.preload = 'auto';
      ttsAudio.addEventListener('ended', function () { if (playing) nextUnit(); });
      ttsAudio.addEventListener('error', function () {
        if (!playing || !curUnit) return;
        /* 单块音频解码失败：本地有语音就改本地，否则跳过这块 */
        if (!modFallback && hasTTS && allVoices().length > 0) {
          modFallback = true;
          playLocal(collectText(curUnit));
          return;
        }
        nextUnit();
      });
      return ttsAudio;
    }
    function pickTtsVoice() {
      if (isCloudVoice(voiceURI)) return voiceURI;   // 下拉里明确选了云端备选
      if (activeChip === 'male') return 'zh-CN-YunxiNeural';
      if (activeChip === 'tw') return 'zh-TW-HsiaoChenNeural';
      return CLOUD_DEFAULT;   // 自动 / 女声 / 默认
    }
    function rateStr() {
      var pct = Math.round((rate - 1) * 100);
      return (pct >= 0 ? '+' : '') + pct + '%';
    }
    /* 文本走 POST body：GET 的 query 在网关/nginx 上会被长度上限截断，
       长段落会被静默砍掉一半（读着读着就断）。 */
    function ttsFetch(txt, voice) {
      var clean = TTS_BASE.replace(/[?&]$/, '');
      return fetch(clean, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: txt, voice: voice || pickTtsVoice(), rate: rateStr() })
      }).then(function (r) {
        if (!r.ok) throw new Error('tts ' + r.status);
        return r.blob();
      });
    }
    /* 试听：用当前下拉里的音色念一句样句，方便几个音色来回比。
       会先停掉正在进行的朗读（不然两路声音叠在一起）。 */
    var TRY_TXT = '这是当前音色的试听，听着顺耳就用它。';
    function previewVoice() {
      var sel = q('#rdSpVoice', box);
      var uri = sel ? (sel.value || '__auto__') : '__auto__';
      stopAll();
      var lv = null;
      /* 默认项走云端晓晓：只有下拉里明确选了某个本机语音时，试听才用
         Web Speech，保证「试听」和「点正文」听到的是同一个声音。 */
      if (uri !== '__auto__' && !isCloudVoice(uri) && hasTTS) {
        var vs = allVoices();
        for (var i = 0; i < vs.length; i++) {
          if (voiceKey(vs[i]) === uri) { lv = vs[i]; break; }
        }
      }
      if (lv && synth) {                       // 本机音色：直接念
        try {
          var u = new window.SpeechSynthesisUtterance(TRY_TXT);
          u.lang = lv.lang || 'zh-CN';
          /* 个别内核的 voice 对象不合法，赋值会抛错并让整句静音 → 单独兜住，
             失败时退回只设 lang，仍能出声 */
          try { u.voice = lv; } catch (e2) {}
          u.rate = rate; u.pitch = pitch; u.volume = volume;
          try { synth.cancel(); } catch (e3) {}
          synth.speak(u);
          setHint('试听：本机 ' + (lv.name || lv.lang), false);
        } catch (e) {
          setHint('这台设备放不出这个音色，换一个试试', true);
        }
        return;
      }
      if (!TTS_BASE) {
        setHint('这台设备没有可用语音，换浏览器或联网后再试', true);
        return;
      }
      var v = isCloudVoice(uri) ? uri : pickTtsVoice();
      setHint('合成中…', false);
      ttsFetch(TRY_TXT, v).then(function (b) {
        setAudioSrc(b);
        var p = ensureAudio().play();
        if (p && p.catch) p.catch(function () {});
        setHint('试听：' + (cloudLabel(v) || v), false);
      }).catch(function () {
        setHint('试听失败，检查网络后重试', true);
      });
    }
    function setAudioSrc(blob) {
      var a = ensureAudio();
      if (ttsObjUrl) { try { URL.revokeObjectURL(ttsObjUrl); } catch (e) {} }
      ttsObjUrl = URL.createObjectURL(blob);
      a.src = ttsObjUrl;
    }
    /* 开始一个朗读会话：units 为单元数组，sec 为所属模块（没有就 null） */
    function playQueue(units, sec) {
      stopAll();
      if (!units || !units.length) return;
      queue = units; qi = 0; playing = true; paused = false; speaking = true;
      modSec = sec || null;
      if (muted) muted = false;
      runUnit();
    }

    function runUnit() {
      if (!playing) return;
      if (qi < 0 || qi >= queue.length) { finishAll(); return; }
      var u = queue[qi];
      curUnit = u; lastUnit = u;
      markNow(u);
      var txt = collectText(u);
      if (!txt) { nextUnit(); return; }
      if (usingLocal()) playLocal(txt);
      else if (TTS_BASE) playServer(txt);
      else { finishAll(); }
      refreshModBtns(); refresh();
    }

    function playLocal(txt) {
      if (!synth) { nextUnit(); return; }
      var my = ++seqLocal;
      utter = new window.SpeechSynthesisUtterance(txt);
      var v = currentVoice();
      /* lang 跟随所选音色：写死 zh-CN 会让 Safari 按 lang 覆盖 voice，台湾腔失效。
         个别 webview 的 voice 对象不合法，赋值会抛错并让整段静音 → 单独兜住。 */
      try {
        utter.lang = (v && v.lang) || 'zh-CN';
        if (v) utter.voice = v;
      } catch (e) { utter.lang = 'zh-CN'; }
      utter.rate = rate; utter.pitch = pitch; utter.volume = muted ? 0 : volume;
      utter.onend = function () { if (my === seqLocal) nextUnit(); };
      utter.onerror = function () { if (my === seqLocal) nextUnit(); };
      try { synth.speak(utter); } catch (e) { nextUnit(); }
      showBar(barLabel(), false);
    }

    function playServer(txt) {
      var my = ++ttsSeq;
      var blob = null;
      if (preIdx === qi && preBlob) { blob = preBlob; preIdx = -1; preBlob = null; }
      if (blob) { startServerAudio(blob, my); return; }
      showBar((modSec ? modLabel(modSec) : textOf(curUnit)) + ' · 合成中…', false);
      ttsFetch(txt).then(function (b) {
        if (my !== ttsSeq || !playing) return;
        startServerAudio(b, my);
      }).catch(function () {
        if (my !== ttsSeq || !playing) return;
        if (!modFallback && hasTTS && allVoices().length > 0) {   // 服务端挂了，本地能读就本地
          modFallback = true;
          playLocal(collectText(curUnit));
          return;
        }
        if (qi === 0) {
          var nm = modSec ? modLabel(modSec) : '语音';
          stopAll();
          showBar(nm + ' · 语音服务暂时不可用，请稍后再试', true);
          setTimeout(hideBar, 3200);
          return;
        }
        nextUnit();     // 中途某块失败就跳过，别整段中断
      });
    }

    function startServerAudio(blob, my) {
      setAudioSrc(blob);
      if (my !== ttsSeq) return;
      showBar(barLabel(), false);
      if (!paused) {
        var p = ensureAudio().play();
        if (p && p.catch) p.catch(function () {});
      }
      prefetchNext();
    }

    /* 预取下一块：块与块之间的合成间隙从 1~2 秒压到接近 0 */
    function prefetchNext() {
      if (!TTS_BASE || usingLocal()) return;
      var j = qi + 1;
      if (j >= queue.length || preIdx === j) return;
      var t = collectText(queue[j]);
      if (!t) return;
      var my = ttsSeq;
      preIdx = j;
      ttsFetch(t).then(function (b) { if (my === ttsSeq && preIdx === j) preBlob = b; })
                  .catch(function () { if (preIdx === j) { preIdx = -1; preBlob = null; } });
    }

    function nextUnit() {
      if (!playing) return;
      qi++;
      if (qi >= queue.length) { finishAll(); return; }
      runUnit();
    }

    function finishAll() {
      playing = false; paused = false; speaking = false;
      markNow(null);
      queue = []; qi = -1; curUnit = null; utter = null;
      modSec = null; preIdx = -1; preBlob = null;
      refreshModBtns(); hideBar(); refresh();
    }

    function togglePause() {
      if (!playing) return;
      paused = !paused; speaking = !paused;
      if (usingLocal() && synth) {
        try { paused ? synth.pause() : synth.resume(); } catch (e) {}
      }
      if (ttsAudio) {
        try { paused ? ttsAudio.pause() : ttsAudio.play(); } catch (e) {}
      }
      showBar(barLabel(), false);
      refreshModBtns(); refresh();
    }

    function modLabel(sec) {
      var h = sec.querySelector('h2, h3');
      return h ? (h.textContent || '').trim().slice(0, 16) : '本模块';
    }
    function refreshModBtns() {
      qa('#rdBody > section > .rd-mod-play').forEach(function (b) {
        var sec = b.parentNode;
        var on = (sec === modSec && playing) || (sec === curUnit && playing);
        b.classList.toggle('on', !!on);
        var ic = b.querySelector('.rd-mp-ico');
        if (ic) ic.textContent = on ? (paused ? '▶' : '⏸') : '▶';
      });
    }
    function toggleModule(sec) {
      /* 同一模块在播 → 暂停/继续；换模块 → 从该模块第一个单元读起 */
      if (sec === modSec && playing) { togglePause(); return; }
      var units = unitsIn(sec);
      if (!units.length) return;
      if (!usingLocal() && !TTS_BASE) {
        showBar('当前设备没有可用语音，请用 Chrome / Edge / Safari 打开', true);
        setTimeout(hideBar, 2600);
        return;
      }
      playQueue(units, sec);
    }
    function addModulePlays() {
      qa('#rdBody > section').forEach(function (sec) {
        if (sec.getAttribute('data-rd-play') === '1') return;
        if (sec.hasAttribute('data-no-speak')) return;
        sec.setAttribute('data-rd-play', '1');
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'rd-mod-play';
        btn.setAttribute('data-no-speak', '');
        btn.setAttribute('aria-label', '朗读本模块');
        btn.title = '朗读本模块';
        btn.innerHTML = '<span class="rd-mp-ico" aria-hidden="true">▶</span>';
        btn.addEventListener('click', function (e) {
          e.preventDefault(); e.stopPropagation(); toggleModule(sec);
        });
        sec.appendChild(btn);
      });
    }

    /* 改配置后若正在朗读，重读当前块以立即生效（滑块拖动中不重读） */
    function relive() {
      var u = curUnit, m = modSec;
      if (u && playing) playQueue([u], m); else refresh();
    }

    if (box) {
      var sel = q('#rdSpVoice', box);
      sel.addEventListener('change', function () {
        voiceURI = sel.value || '__auto__';
        activeChip = voiceURI === '__auto__' ? 'auto' : null;
        var nm = isCloudVoice(voiceURI) ? cloudLabel(voiceURI) : '';
        setHint(nm ? '已选「' + nm + '」· 点试听先听一句'
                   : voiceSummary() + ' · 已选下拉音色');
        savePrefs(); relive();
      });
      var tryBtn = q('#rdSpTry', box);
      if (tryBtn) tryBtn.addEventListener('click', function (e) {
        e.preventDefault();
        previewVoice();
      });
      qa('.rd-sp-chips button', box).forEach(function (b) {
        b.addEventListener('click', function () {
          var kind = b.getAttribute('data-voice');
          /* 本机没这个音色就直说，绝不静默回落到「自动」还把按钮点亮 */
          if (!hasKind(kind)) {
            setHint('本机没有「' + b.textContent + '」语音，已保持原设置。展开下方「没有男声 / 台湾腔？」' +
                    '看添加方法，或在「音色」下拉里挑一个可用项。', true);
            return;
          }
          activeChip = kind;
          /* 云端有对应音色就一律用云端，别让 Windows 自带的 Huihui 把
             「女声」又变回机械音；本机语音仍可在下拉里显式选。 */
          voiceURI = kind === 'auto' ? '__auto__'
                   : ((TTS_BASE && cloudKind(kind)) || firstBy(kind));
          sel.value = voiceURI;
          if (!sel.value) { sel.value = '__auto__'; voiceURI = '__auto__'; }
          setHint(voiceSummary() + ' · 已选「' + b.textContent + '」');
          savePrefs(); relive();
        });
      });

      var rEl = q('#rdSpRate', box), pEl = q('#rdSpPitch', box), vEl = q('#rdSpVol', box);
      function setLabel(el, txt) { el.textContent = txt; }
      rEl.value = rate; pEl.value = pitch; vEl.value = volume;
      setLabel(q('#rdSpRateVal', box), rate.toFixed(1) + '×');
      setLabel(q('#rdSpPitchVal', box), pitch.toFixed(1));
      setLabel(q('#rdSpVolVal', box), Math.round(volume * 100) + '%');
      rEl.addEventListener('input', function () {
        rate = parseFloat(rEl.value);
        setLabel(q('#rdSpRateVal', box), rate.toFixed(1) + '×'); savePrefs();
      });
      pEl.addEventListener('input', function () {
        pitch = parseFloat(pEl.value);
        setLabel(q('#rdSpPitchVal', box), pitch.toFixed(1)); savePrefs();
      });
      vEl.addEventListener('input', function () {
        volume = parseFloat(vEl.value);
        setLabel(q('#rdSpVolVal', box), Math.round(volume * 100) + '%');
        if (utter) utter.volume = muted ? 0 : volume;
        savePrefs();
      });
      rEl.addEventListener('change', relive);
      pEl.addEventListener('change', relive);
      vEl.addEventListener('change', relive);

      q('#rdSpMute', box).addEventListener('click', function () {
        muted = !muted;
        if (utter) utter.volume = muted ? 0 : volume;
        refresh();
      });
      q('#rdSpStop', box).addEventListener('click', function () { stopAll(); hideBar(); });
    }

    /* 底部控制条按钮 */
    q('#rdSbPause', bar).addEventListener('click', function () {
      if (playing) { togglePause(); return; }       // 本地/云端都能暂停
      if (lastUnit) speak(lastUnit);
      else showBar('点正文任意段落开始朗读', true);
    });
    q('#rdSbStop', bar).addEventListener('click', function () { stopAll(); hideBar(); });
    q('#rdSbMute', bar).addEventListener('click', function () {
      muted = !muted;
      if (utter) utter.volume = muted ? 0 : volume;
      refresh();
    });
    q('#rdSbSet', bar).addEventListener('click', function () {
      if (rdPanel) { rdPanel.hidden = false; fillVoices(); refresh(); }
    });

    function stopAll() {
      if (synth) { try { synth.cancel(); } catch (e) {} }   // 无条件 cancel
      seqLocal++;                                           // 作废本地回调
      ttsSeq++;                                             // 作废在途的合成请求
      if (ttsAudio) { try { ttsAudio.pause(); ttsAudio.removeAttribute('src'); } catch (e) {} }
      if (ttsObjUrl) { try { URL.revokeObjectURL(ttsObjUrl); } catch (e) {} ttsObjUrl = null; }
      playing = false; paused = false;
      queue = []; qi = -1; speaking = false;
      curUnit = null; utter = null; modSec = null; modFallback = false;
      preIdx = -1; preBlob = null;
      qa('#rdBody .speaking').forEach(function (s) { s.classList.remove('speaking'); });
      refreshModBtns();
    }

    /* 单个单元朗读（点正文触发）：只在没有播会话时开新会话 */
    function speak(unit) {
      if (!unit) return;
      if (!usingLocal() && !TTS_BASE) {
        showBar('当前浏览器不支持语音朗读，建议用 Chrome / Edge / Safari 打开', true);
        return;
      }
      playQueue([unit], null);
    }

    main.addEventListener('click', function (e) {
      var unit = resolveUnit(e.target);
      if (!unit) return;
      /* 不再做点击闪光：朗读时由 .speaking 常驻高亮「读到哪」，点的时候不闪 */
      if (unit === curUnit && playing) { togglePause(); return; }   // 再点同一块 → 暂停/继续
      /* 播放中点了别的块：直接切到该块（之前会继续播旧内容） */
      if (!usingLocal() && !TTS_BASE) return;
      if (muted) muted = false;
      speak(unit);
    });

    /* 点「Aa」打开设置面板时才枚举系统语音（按需调用，不进页面就扫一遍） */
    var fab = q('#rdFab');
    if (fab) fab.addEventListener('click', function () {
      if (rdPanel && !rdPanel.hidden) { fillVoices(); refresh(); }
    });
    if (hasTTS && synth && typeof synth.onvoiceschanged !== 'undefined') {
      synth.onvoiceschanged = function () { if (rdPanel && !rdPanel.hidden) fillVoices(); };
    }
    /* 初始化时填一次下拉：无 TTS 时才能立刻置灰并显示「不支持」；
       点 Aa 打开面板时再刷新一次，捕获异步加载完成的系统语音。
       这里只枚举本地语音列表，不会发声——真正调用 TTS 引擎在点正文之后。 */
    fillVoices();
    refresh();

    /* 一级模块播放键：数据异步注入，先补一次，再监听 #rdBody 子节点变化补挂 */
    addModulePlays();
    if (window.MutationObserver) {
      try {
        new MutationObserver(function () { addModulePlays(); }).observe(main, { childList: true });
      } catch (e) { /* 忽略 */ }
    }

    // 切书/翻页/离开时停掉，避免后台继续朗读
    window.addEventListener('beforeunload', stopAll);
  }

  /* ── Aa 面板 · 正文字体（按需加载；不改任何一本书的 HTML）──────
     静态站不能运行时遍历目录：优先读 assets/fonts/fonts.json 清单，
     清单缺失时回退 GitHub Contents API 真遍历目录（结果缓存 1 小时）。
     字体只在用户主动选中时才下载，font-display:swap 不挡首屏。 */
  function initFonts() {
    var panel = q('#rdPanel');
    if (!panel) return;
    /* 字体走 CDN（cdn.js-dev.cn），本地 assets/fonts/ 作为兜底：
       两者同路径，@font-face 里写成 src 列表，CDN 不可用时浏览器自动回落到本地。
       跨域加载字体需要 CORS，七牛已配 Access-Control-Allow-Origin: *。 */
    var FONT_DIR = 'https://cdn.js-dev.cn/assets/fonts/';
    var FONT_FALLBACK = '../../../assets/fonts/';
    var API = 'https://api.github.com/repos/ae6623/we-read/contents/assets/fonts';
    var CFG = 'rd-font-cfg', CACHE = 'rd-font-list', FACE_ID = 'rdFontFace';
    var FAM = 'RD-UserFont';
    var saved = '';
    try { saved = localStorage.getItem(CFG) || ''; } catch (e) {}
    var ORIG = null;
    function orig() {
      if (ORIG) return ORIG;
      var cs = window.getComputedStyle(document.documentElement);
      ORIG = {
        serif: (cs.getPropertyValue('--serif') || '').trim() || '"Noto Serif SC","Songti SC",Georgia,serif',
        sans: (cs.getPropertyValue('--sans') || '').trim() ||
              '-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif'
      };
      return ORIG;
    }

    var row = document.createElement('div');
    row.className = 'rd-row rd-font-row';
    row.innerHTML = '<span>字体</span><select id="rdFontSel" class="rd-font-sel" ' +
                    'aria-label="正文字体"><option value="">系统默认</option></select>';
    var note = document.createElement('p');
    note.className = 'rd-font-note';
    note.id = 'rdFontNote';
    note.textContent = '首次选中才下载字体文件';
    var speakBox = q('.rd-speak-box', panel);
    if (speakBox) { panel.insertBefore(row, speakBox); panel.insertBefore(note, speakBox); }
    else { panel.appendChild(row); panel.appendChild(note); }
    var sel = q('#rdFontSel', panel);
    var list = [];

    function fmt(n) {
      n = n || 0;
      return n >= 1048576 ? (n / 1048576).toFixed(1) + ' MB'
           : n >= 1024 ? Math.round(n / 1024) + ' KB' : n + ' B';
    }
    function status(t) { note.textContent = t; }
    function byName(n) {
      for (var i = 0; i < list.length; i++) if (list[i].file === n) return list[i];
      return null;
    }
    function apply(f, store) {
      var d = document.documentElement;
      var st = q('#' + FACE_ID);
      if (!f) {
        if (st && st.parentNode) st.parentNode.removeChild(st);
        d.style.removeProperty('--serif');
        d.style.removeProperty('--sans');
        if (store !== false) { saved = ''; try { localStorage.removeItem(CFG); } catch (e) {} }
        status('已恢复系统默认（不加载字体文件）');
        return;
      }
      var o = orig();
      if (!st) { st = document.createElement('style'); st.id = FACE_ID; document.head.appendChild(st); }
      var ext = (f.file.split('.').pop() || '').toLowerCase();
      var ftype = ext === 'woff2' ? 'woff2' : ext === 'woff' ? 'woff'
                : ext === 'otf' ? 'opentype' : 'truetype';
      st.textContent = '@font-face{font-family:"' + FAM + '";src:url("' + FONT_DIR + f.file + '") format("woff2"),url("' + FONT_FALLBACK + f.file +
        '") format("' + ftype + '");font-display:swap;font-weight:100 900;font-style:normal;}';
      d.style.setProperty('--serif', '"' + FAM + '", ' + o.serif);
      d.style.setProperty('--sans', '"' + FAM + '", ' + o.sans);
      if (store !== false) { saved = f.file; try { localStorage.setItem(CFG, saved); } catch (e) {} }
      status('加载中 ' + f.name + '（' + fmt(f.bytes) + '）…');
      if (document.fonts && document.fonts.load) {
        document.fonts.load('16px "' + FAM + '"').then(function (faces) {
          status(faces && faces.length ? '已加载 ' + f.name + ' · 仅首次下载，之后走浏览器缓存'
                                      : '加载失败，已回退系统字体');
        }, function () { status('加载失败，已回退系统字体'); });
      }
    }
    function fill(items) {
      list = items || [];
      var html = '<option value="">系统默认（不下载）</option>';
      list.forEach(function (f) {
        html += '<option value="' + f.file + '">' + f.name +
                (f.bytes ? '（' + fmt(f.bytes) + '）' : '') + '</option>';
      });
      sel.innerHTML = html;
      sel.value = saved;
      if (saved) apply(byName(saved), false);
    }
    sel.addEventListener('change', function () { apply(byName(sel.value), true); });

    function cached() { try { return JSON.parse(localStorage.getItem(CACHE) || 'null'); } catch (e) { return null; } }
    function saveCache(v) { try { localStorage.setItem(CACHE, JSON.stringify({ t: Date.now(), v: v })); } catch (e) {} }
    function fromApi() {
      return fetch(API, { headers: { Accept: 'application/vnd.github+json' } })
        .then(function (r) { if (!r.ok) throw 0; return r.json(); })
        .then(function (arr) {
          var all = (arr || []).filter(function (x) {
            return /\.(woff2?|ttf|otf)$/i.test(x.name || '');
          }).map(function (x) {
            return { file: x.name, name: x.name.replace(/\.(woff2?|ttf|otf)$/i, ''), bytes: x.size || 0 };
          });
          /* 有 woff2 就不列同名的原始 TTF/OTF，避免误点 18MB 的文件 */
          var w2 = {};
          all.forEach(function (x) { if (/\.woff2$/i.test(x.file)) w2[x.name] = 1; });
          return all.filter(function (x) { return /\.woff2$/i.test(x.file) || !w2[x.name]; });
        });
    }
    /* 直接往 assets/fonts/ 传新字体、没跑 scan_fonts.py 也能认出来：
       首次展开 Aa 面板时向 GitHub API 查一次目录（结果缓存 1 小时），
       只把清单里没有的文件追加进下拉，不覆盖已有中文名和体积。 */
    var apiChecked = false;
    function syncFromApi() {
      var c = cached();
      if (apiChecked || (c && c.t && Date.now() - c.t < 3600000)) return;
      apiChecked = true;
      fromApi().then(function (v) {
        saveCache(v);
        var have = {};
        list.forEach(function (x) { have[x.file] = 1; });
        var extra = v.filter(function (x) { return !have[x.file]; });
        extra.forEach(function (x) {
          var o = document.createElement('option');
          o.value = x.file;
          o.textContent = x.name + '（' + fmt(x.bytes) +
            (/\.(ttf|otf)$/i.test(x.file) ? ' · 原始文件' : '') + '）';
          sel.appendChild(o);
        });
        list = list.concat(extra);
      }, function () {});
    }
    var fab = q('#rdFab');
    if (fab) fab.addEventListener('click', function () { if (!panel.hidden) syncFromApi(); });

    fetch(FONT_DIR + 'fonts.json')
      .then(function (r) { if (!r.ok) throw 0; return r.json(); })
      .catch(function () { return fetch(FONT_FALLBACK + 'fonts.json', { credentials: 'same-origin' }).then(function (r) { if (!r.ok) throw 0; return r.json(); }); })
      .then(function (j) { var v = j && j.fonts; if (!v || !v.length) throw 0; return v; })
      .catch(function () {
        var c = cached();
        if (c && c.v && Date.now() - c.t < 3600000) return c.v;
        return fromApi().then(function (v) { saveCache(v); return v; });
      })
      .then(function (items) { fill(items); })
      .catch(function () { status('字体清单读取失败，暂用系统默认'); sel.disabled = true; });
  }

  function boot() {
    initSettings();
    initSpeak();
    initFonts();
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
    s.src=base+'assets/js/visit-stats.js?v=20261105a';
    s.defer=true;
    (document.body||document.documentElement).appendChild(s);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();
