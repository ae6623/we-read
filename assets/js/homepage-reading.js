(() => {
  const module = document.querySelector('[data-reading-module]');
  if (!module) return;
  const list = module.querySelector('[data-tablist]');
  const tabs = [...list.querySelectorAll('button[data-panel]')];
  const panels = tabs.map((tab) => document.getElementById(tab.dataset.panel));
  if (panels.some((panel) => !panel)) return;
  const hashByTabId = new Map([
    ['reading-tab-overview', 'tongDu'],
    ['reading-tab-series', 'xiLie'],
    ['reading-tab-archive', 'guiDang'],
  ]);
  // 2026-11-01 撤掉「精读」页签（书架卡片里已有精读入口），老链接 #jingDu 并回书架
  const legacyHash = { jingDu: 'tongDu' };
  const indexForHash = (hash) => {
    const want = legacyHash[hash] || hash;
    return tabs.findIndex((tab) => hashByTabId.get(tab.id) === want);
  };
  const indexFromLocation = () => indexForHash(window.location.hash.slice(1));

  // Progressive enhancement: without JS, all sections and their links remain visible.
  const activate = (index, focus = false, updateUrl = false) => {
    tabs.forEach((tab, position) => {
      const selected = position === index;
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
      panels[position].hidden = !selected;
    });
    if (updateUrl) {
      const hash = hashByTabId.get(tabs[index].id);
      if (hash && window.location.hash !== `#${hash}`) history.pushState(null, '', `#${hash}`);
    }
    if (focus) tabs[index].focus();
    syncSearchPanel(panels[index]); // 搜索目标跟随当前 Tab
  };
  list.setAttribute('role', 'tablist');
  tabs.forEach((tab, index) => {
    tab.setAttribute('role', 'tab');
    tab.setAttribute('aria-controls', panels[index].id);
    panels[index].setAttribute('role', 'tabpanel');
    panels[index].setAttribute('aria-labelledby', tab.id);
    panels[index].tabIndex = 0;
    tab.addEventListener('click', () => activate(index, false, true));
    tab.addEventListener('keydown', (event) => {
      let next;
      if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
      else if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
      else if (event.key === 'Home') next = 0;
      else if (event.key === 'End') next = tabs.length - 1;
      else return;
      event.preventDefault();
      activate(next, true, true);
    });
  });
  const syncTabFromLocation = () => {
    const index = indexFromLocation();
    if (index >= 0) activate(index);
  };
  window.addEventListener('hashchange', syncTabFromLocation);
  window.addEventListener('popstate', syncTabFromLocation);
  // 卡片按时间倒序（新书在最上）：有 data-ts 用 data-ts，否则取卡片内 <time>/搜索词中的日期。
  // 生成器写死的时间戳若同值，稳定排序保持原相对顺序；未来生产新书给更晚 ts 会自动上浮。
  const newestKey = (card) => {
    const ts = card.getAttribute('data-ts');
    if (ts) return ts;
    const t = card.querySelector('time') && card.querySelector('time').getAttribute('datetime');
    if (t) return t.length <= 10 ? `${t}T23:59:59` : t;
    const m = (card.getAttribute('data-search') || '').match(/(\d{4}-\d{2}-\d{2})/);
    return m ? `${m[1]}T00:00:00` : '0000';
  };
  const sortCardsNewest = (panel) => {
    const cards = [...panel.querySelectorAll('article.archive-card')];
    if (!cards.length) return;
    const groups = new Map();
    cards.forEach((c) => {
      const parent = c.parentNode;
      if (!groups.has(parent)) groups.set(parent, []);
      groups.get(parent).push(c);
    });
    groups.forEach((arr, parent) => {
      arr.sort((a, b) => newestKey(b).localeCompare(newestKey(a))); // 倒序；Array.sort 稳定
      arr.forEach((c) => parent.appendChild(c));
    });
  };
  panels.forEach(sortCardsNewest);

  // A recognized URL hash selects its tab; otherwise start on 精读.
  const defaultIndex = tabs.findIndex((tab) => tab.id === 'reading-tab-overview');
  const hashIndex = indexFromLocation();
  activate(hashIndex >= 0 ? hashIndex : (defaultIndex >= 0 ? defaultIndex : 0));
  module.setAttribute('data-tabs-ready', '');
  list.hidden = false;

  // ── 统一搜索（2026-10-30）：Tab 行放大镜 = 全站唯一搜索入口 ──
  // 一个输入框、一个浮层；筛选目标跟随当前激活的 Tab——在哪个 Tab 就只搜哪个 Tab 的笔记。
  const normalize = (value) => value.toLocaleLowerCase('zh-CN').replace(/[\s：:，,。.!！?？、-]/g, '');
  var searchReady = false; // activate() 初始化时就会调 syncSearchPanel（函数声明提升），用 var 标志挡住未初始化阶段
  // 分类筛选状态（2026-11-01）：与搜索叠加，catL1/catL2 为空即不参与过滤
  var catL1 = '';
  var catL2 = '';
  var catLoaded = false;
  var catSlug = {};            // slug -> [一级, 二级]
  var catTitle = {};           // 归一化书名 -> [一级, 二级]
  var catOfCard = new WeakMap();
  var catPanel = null;
  let searchPanel = null;
  let searchCards = [];
  const searchToggle = document.getElementById('shelf-search-toggle');
  const searchPop = document.getElementById('shelf-search-pop');
  const searchInput = searchPop ? searchPop.querySelector('input') : null;
  const searchStatus = document.querySelector('[data-search-status][for="shelf-search"]');

  const applySearch = () => {
    if (!searchPanel || !searchInput) return;
    if (catPanel !== searchPanel) { // 换页签：分类项与计数跟着该页签的卡片重算
      catPanel = searchPanel;
      if (catLoaded) rebuildCatOptions();
    }
    const query = normalize(searchInput.value.trim());
    const filtering = query !== '' || catL1 !== '' || catL2 !== '';
    let shown = 0;
    searchCards.forEach((card) => {
      const match = (!query || normalize(`${card.dataset.search || ''} ${card.textContent || ''}`).includes(query))
        && passCat(card);
      card.hidden = !match;
      if (match) shown += 1;
    });
    if (searchStatus) searchStatus.textContent = query ? `找到 ${shown} 本` : `共 ${searchCards.length} 本`;
    const empty = searchPanel.querySelector('[data-empty-state]');
    if (empty) empty.hidden = shown > 0;
    searchPanel.querySelectorAll('.reading-group').forEach((group) => {
      group.hidden = filtering && ![...group.querySelectorAll('.archive-card')].some((card) => !card.hidden);
    });
    refreshCatUi(shown);
  };

  const setSearchPanel = (panel) => {
    if (!panel || panel === searchPanel) return;
    if (searchPanel) { // 复位上一个面板的过滤痕迹，避免筛选串台
      searchCards.forEach((card) => { card.hidden = false; });
      searchPanel.querySelectorAll('.reading-group').forEach((group) => { group.hidden = false; });
      const oldEmpty = searchPanel.querySelector('[data-empty-state]');
      if (oldEmpty) oldEmpty.hidden = true;
    }
    searchPanel = panel;
    searchCards = [...panel.querySelectorAll('.archive-card, .series-preview')];
    applySearch();
  };

  function syncSearchPanel(panel) {
    if (searchReady) setSearchPanel(panel);
  }

  if (searchToggle && searchPop && searchInput) {
    const setSearchOpen = (open) => {
      searchToggle.setAttribute('aria-expanded', String(open));
      searchPop.hidden = !open;
      if (open) {
        const fp = document.getElementById('shelf-filter-pop');
        if (fp && !fp.hidden) { // 两个浮层都贴 Tab 行右侧，开一个就收另一个
          fp.hidden = true;
          const ft = document.getElementById('shelf-filter-toggle');
          if (ft) ft.setAttribute('aria-expanded', 'false');
        }
        setSearchPanel(panels.find((panel) => !panel.hidden) || null); // 打开时对准当前 Tab
        searchInput.focus();
        return;
      }
      if (searchInput.value) { // 收起即清空并复位，避免「看不见的过滤状态」
        searchInput.value = '';
        applySearch();
      }
    };
    searchToggle.addEventListener('click', () => setSearchOpen(searchPop.hidden));
    searchInput.addEventListener('input', applySearch);
    document.addEventListener('click', (event) => {
      if (searchPop.hidden) return;
      // 点 Tab 按钮不收起：关键词跟随切 Tab，继续筛新页签（syncSearchPanel 已挂 activate）
      if (event.target.closest('#shelf-search-pop, #shelf-search-toggle, .reading-tabs button[data-panel]')) return;
      setSearchOpen(false);
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && !searchPop.hidden) {
        setSearchOpen(false);
        searchToggle.focus();
      }
    });
    const clearBtn = module.querySelector('[data-clear-filters]');
    if (clearBtn && !clearBtn.dataset.clearBound) {
      clearBtn.dataset.clearBound = '';
      clearBtn.addEventListener('click', () => {
        searchInput.value = '';
        searchInput.focus();
        applySearch();
      });
    }
  }
  searchReady = true;
  setSearchPanel(panels.find((panel) => !panel.hidden) || null); // 对准初始 Tab

  // 首屏阅读理念横条（details/summary，默认收起）：展开状态记 localStorage
  const explain = document.querySelector('[data-explain-fold]');
  if (explain) {
    try {
      if (localStorage.getItem('we-read:reading-bar-open') === '1') explain.open = true;
      explain.addEventListener('toggle', () => {
        try { localStorage.setItem('we-read:reading-bar-open', explain.open ? '1' : '0'); } catch (e) { /* ignore */ }
      });
    } catch (e) { /* localStorage 不可用时保持默认收起 */ }
  }

  // ── 分类筛选（2026-11-01）：Tab 行漏斗 = 分类入口，和放大镜搜索共用一套 applySearch ──
  // 数据：assets/data/book-cats.json（发布时由书架台账 book_meta 生成，slug / 归一化书名双索引）。
  // 拿不到数据就收起入口，不给出点了没反应的按钮。
  const catNorm = (value) => String(value || '')
    .replace(/[\s\u3000]/g, '')
    .replace(/[《》<>〈〉「」『』【】\[\]（）()：:，,。.、·—–\-－_~～!！?？"'’‘“”…/\\|]+/g, '')
    .toLowerCase();

  function cardCat(card) {
    if (catOfCard.has(card)) return catOfCard.get(card);
    let pair = ['', ''];
    const a = card.querySelector('a[href*="reading-notes/books/"]');
    const m = a ? (a.getAttribute('href') || '').match(/reading-notes\/books\/([^\/]+)\//) : null;
    if (m) {
      const slug = decodeURIComponent(m[1]);
      if (catSlug[slug]) pair = catSlug[slug];
    }
    if (!pair[0]) {
      const t = card.querySelector('.card-title-link, .book-jd-link, h3 a, h3');
      const key = catNorm(t ? t.textContent : '');
      if (key && catTitle[key]) pair = catTitle[key];
    }
    catOfCard.set(card, pair);
    return pair;
  }

  function passCat(card) {
    if (!catL1 && !catL2) return true;
    if (card.classList.contains('series-preview')) return true;  // 系列导览卡不是书，不参与分类
    const pair = cardCat(card);
    const l1 = pair[0] || '__none__';
    if (catL1 && l1 !== catL1) return false;
    if (catL2 && (pair[1] || '') !== catL2) return false;
    return true;
  }

  function rebuildCatOptions() {
    const sel1 = document.getElementById('shelf-cat1');
    const sel2 = document.getElementById('shelf-cat2');
    if (!sel1 || !sel2) return;
    const l1Map = new Map();       // 一级 → { n, l2: Map }
    const bookCards = searchCards.filter((card) => !card.classList.contains('series-preview'));
    bookCards.forEach((card) => {
      const pair = cardCat(card);
      const key = pair[0] || '__none__';
      if (!l1Map.has(key)) l1Map.set(key, { n: 0, l2: new Map() });
      const node = l1Map.get(key);
      node.n += 1;
      const k2 = pair[1] || '';
      node.l2.set(k2, (node.l2.get(k2) || 0) + 1);
    });
    const label = (k) => (k === '__none__' ? '未分类' : k);
    if (catL1 && !l1Map.has(catL1)) catL1 = '';   // 换页签后旧选择可能不存在
    const rows = [...l1Map.entries()].sort((a, b) =>
      (a[0] === '__none__') - (b[0] === '__none__') || b[1].n - a[1].n || a[0].localeCompare(b[0], 'zh'));
    sel1.innerHTML = `<option value="">全部分类（${bookCards.length}）</option>`
      + rows.map(([k, v]) => `<option value="${k}">${label(k)}（${v.n}）</option>`).join('');
    sel1.value = catL1;
    const node = l1Map.get(catL1);
    if (!node) {
      catL2 = '';
      sel2.disabled = true;
      sel2.innerHTML = '<option value="">先选一级</option>';
    } else {
      const l2rows = [...node.l2.entries()].filter(([k]) => k !== '')
        .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], 'zh'));
      if (catL2 && !node.l2.has(catL2)) catL2 = '';
      sel2.disabled = false;
      sel2.innerHTML = `<option value="">全部二级（${node.n}）</option>`
        + l2rows.map(([k, v]) => `<option value="${k}">${k}（${v}）</option>`).join('');
      sel2.value = catL2;
    }
    const toggle = document.getElementById('shelf-filter-toggle');
    if (toggle) toggle.classList.toggle('is-active', !!(catL1 || catL2));
  }

  function refreshCatUi(shown) {
    const el = document.getElementById('shelf-cat-status');
    if (!el) return;
    if (!catLoaded) { el.textContent = '分类数据加载中…'; return; }
    if (!catL1 && !catL2) {
      const n = searchCards.filter((card) => !card.classList.contains('series-preview')).length;
      el.textContent = `未按分类筛选 · 当前页签 ${n} 本`;
      return;
    }
    const name = catL1 === '__none__' ? '未分类' : catL1;
    el.textContent = `分类：${catL2 ? `${name} · ${catL2}` : name} · 选出 ${shown} 本`;
  }

  (function initCatFilter() {
    const toggle = document.getElementById('shelf-filter-toggle');
    const pop = document.getElementById('shelf-filter-pop');
    const sel1 = document.getElementById('shelf-cat1');
    const sel2 = document.getElementById('shelf-cat2');
    if (!toggle || !pop || !sel1 || !sel2) return;
    const setOpen = (open) => {
      toggle.setAttribute('aria-expanded', String(open));
      pop.hidden = !open;
      if (!open) return;
      const sp = document.getElementById('shelf-search-pop');
      if (sp && !sp.hidden) { // 同位置的两个浮层：开筛选就收搜索
        const st = document.getElementById('shelf-search-toggle');
        if (st) st.click();
      }
      setSearchPanel(panels.find((panel) => !panel.hidden) || null);
      if (catLoaded) rebuildCatOptions();
    };
    toggle.addEventListener('click', () => setOpen(pop.hidden));
    sel1.addEventListener('change', () => {
      catL1 = sel1.value;
      catL2 = '';
      rebuildCatOptions();
      applySearch();
    });
    sel2.addEventListener('change', () => {
      catL2 = sel2.value;
      applySearch();
    });
    const clearBtn = document.getElementById('shelf-cat-clear');
    if (clearBtn) clearBtn.addEventListener('click', () => {
      catL1 = '';
      catL2 = '';
      rebuildCatOptions();
      applySearch();
    });
    document.addEventListener('click', (event) => {
      if (pop.hidden) return;
      if (event.target.closest('#shelf-filter-pop, #shelf-filter-toggle, .reading-tabs button[data-panel]')) return;
      setOpen(false);
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && !pop.hidden) {
        setOpen(false);
        toggle.focus();
      }
    });
    fetch('assets/data/book-cats.json', { cache: 'no-cache' })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status))))
      .then((data) => {
        catSlug = (data && data.books) || {};
        catTitle = (data && data.titles) || {};
        catLoaded = true;
        catOfCard = new WeakMap();      // 之前的空映射作废，重算
        rebuildCatOptions();
        applySearch();
      })
      .catch(() => {
        catLoaded = false;
        toggle.hidden = true;
        pop.hidden = true;
      });
  })();

  // ── 系列归并（2026-11-01）：套书按月归系列，不逐本挤在通读/精读里 ──
  // 数据：assets/data/series.json（title_has 命中书名即归入该系列）。
  // 做法：把命中的单书卡从「书架/精读」DOM 搬到「系列」Tab 的对应分组——不是复制，
  // 所以首页不再重复露脸；搜索与分类筛选对系列 Tab 一样生效（同一套 applySearch）。
  (function initSeries() {
    const seriesPanel = document.getElementById('reading-panel-series');
    if (!seriesPanel) return;
    fetch('assets/data/series.json', { cache: 'no-cache' })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status))))
      .then((data) => {
        const defs = ((data && data.series) || []).filter((d) => d && d.slug && (d.title_has || []).length);
        if (!defs.length) return;
        const route = seriesPanel.querySelector('.panel-route');
        const groups = new Map();
        defs.forEach((def) => {
          const sec = document.createElement('section');
          sec.className = 'reading-group series-group';
          sec.dataset.series = def.slug;
          const head = document.createElement('h3');
          head.className = 'reading-group-title';
          const name = document.createElement('a');
          name.href = def.page || '#';
          name.textContent = def.name;
          const meta = document.createElement('span');
          meta.textContent = def.sub || '';
          head.appendChild(name);
          head.appendChild(meta);
          const grid = document.createElement('div');
          grid.className = 'archive-grid';
          sec.appendChild(head);
          sec.appendChild(grid);
          seriesPanel.insertBefore(sec, route || null);
          groups.set(def.slug, { sec, grid, meta, def, n: 0 });
        });

        const cardTitle = (card) => {
          const t = card.querySelector('.card-title-link, .book-jd-link, h3 a, h3');
          return t ? t.textContent.replace(/[《》\s\u3000]/g, '') : '';
        };
        let moved = 0;
        const seen = new Set();          // 同一本书在书架/精读各有一张卡，系列组里只留一张
        ['reading-panel-overview', 'reading-panel-close'].forEach((id) => {
          const panel = document.getElementById(id);
          if (!panel) return;
          panel.querySelectorAll('article.archive-card').forEach((card) => {
            const title = cardTitle(card);
            if (!title) return;
            const def = defs.find((d) => d.title_has.some((k) => title.includes(k)));
            const node = def && groups.get(def.slug);
            if (!node) return;
            const a = card.querySelector('a[href*="reading-notes/books/"]');
            const m = a ? (a.getAttribute('href') || '').match(/books\/([^\/]+)\//) : null;
            const key = def.slug + '::' + (m ? m[1] : title);
            if (seen.has(key)) { card.remove(); return; }  // 第二个视角的重复卡，收掉
            seen.add(key);
            card.dataset.series = def.slug;
            node.grid.appendChild(card);   // 搬家，不是复制
            node.n += 1;
            moved += 1;
          });
          panel.querySelectorAll('.reading-group').forEach((g) => {   // 搬空的组别留标题
            if (!g.querySelector('article.archive-card')) g.hidden = true;
          });
        });
        groups.forEach((node) => {
          if (!node.n) { node.sec.hidden = true; return; }
          node.meta.textContent = `${node.def.sub ? node.def.sub + ' · ' : ''}${node.n} 本已发布`;
        });
        if (!moved) return;
        // 子 Tab 徽标是加载时算的，搬完要重算
        document.querySelectorAll('[data-subtablist] button[data-subpanel]').forEach((b) => {
          const panel = document.getElementById(b.dataset.subpanel);
          const badge = b.querySelector('.count');
          if (panel && badge) badge.textContent = panel.querySelectorAll('.archive-card').length;
        });
        // 卡片换了父节点，搜索/筛选的当前页签要重挂
        searchPanel = null;
        catPanel = null;
        setSearchPanel(panels.find((panel) => !panel.hidden) || null);
      })
      .catch(() => { /* 没有系列数据就当没这个功能，页面照旧 */ });
  })();

  // 整卡可点：点击卡片空白处等同点书名（书名即通读入口）；卡内真实链接不受影响
  module.querySelectorAll('.archive-card').forEach((card) => {
    const link = card.querySelector('.card-title-link');
    if (!link || card.dataset.cardClickable) return;
    card.dataset.cardClickable = '';
    card.classList.add('card-clickable');
    card.addEventListener('click', (event) => {
      if (event.target.closest('a, button, input, select, textarea, label')) return;
      if (event.selection && String(event.selection).length) return;
      link.click();
    });
  });
})();

// 子 Tab：通读面板内的「全书视角 / 即将上线」分段切换（独立于顶层 Tab，互不干扰）
(() => {
  document.querySelectorAll('[data-subtablist]').forEach((list) => {
    const btns = [...list.querySelectorAll('button[data-subpanel]')];
    const panels = btns.map((b) => document.getElementById(b.dataset.subpanel));
    if (panels.some((p) => !p)) return;
    const activate = (i) => {
      btns.forEach((b, j) => {
        const selected = j === i;
        b.setAttribute('aria-selected', String(selected));
        b.tabIndex = selected ? 0 : -1;
        panels[j].hidden = !selected;
      });
    };
    list.setAttribute('role', 'tablist');
    btns.forEach((b, i) => {
      const panel = panels[i];
      b.setAttribute('role', 'tab');
      b.setAttribute('aria-controls', panel.id);
      panel.setAttribute('role', 'tabpanel');
      panel.setAttribute('aria-labelledby', b.id);
      panel.tabIndex = 0;
      // 自动统计该面板卡片数并注入徽标，避免硬编码随增删漂移
      const n = panel.querySelectorAll('.archive-card').length;
      if (n > 0 && !b.querySelector('.count')) {
        const c = document.createElement('span');
        c.className = 'count';
        c.textContent = n;
        b.appendChild(c);
      }
      b.addEventListener('click', () => activate(i));
      b.addEventListener('keydown', (e) => {
        let next;
        if (e.key === 'ArrowRight' || e.key === 'ArrowDown') next = (i + 1) % btns.length;
        else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') next = (i - 1 + btns.length) % btns.length;
        else if (e.key === 'Home') next = 0;
        else if (e.key === 'End') next = btns.length - 1;
        else return;
        e.preventDefault();
        activate(next);
        btns[next].focus();
      });
    });
    activate(0);
  });
})();
