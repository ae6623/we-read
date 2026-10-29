(() => {
  const module = document.querySelector('[data-reading-module]');
  if (!module) return;
  const list = module.querySelector('[data-tablist]');
  const tabs = [...list.querySelectorAll('button[data-panel]')];
  const panels = tabs.map((tab) => document.getElementById(tab.dataset.panel));
  if (panels.some((panel) => !panel)) return;
  const hashByTabId = new Map([
    ['reading-tab-overview', 'tongDu'],
    ['reading-tab-close', 'jingDu'],
    ['reading-tab-series', 'xiLie'],
    ['reading-tab-archive', 'guiDang'],
  ]);
  const indexForHash = (hash) => tabs.findIndex((tab) => hashByTabId.get(tab.id) === hash);
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
  const defaultIndex = tabs.findIndex((tab) => tab.id === 'reading-tab-close');
  const hashIndex = indexFromLocation();
  activate(hashIndex >= 0 ? hashIndex : (defaultIndex >= 0 ? defaultIndex : 0));
  module.setAttribute('data-tabs-ready', '');
  list.hidden = false;

  // ── 统一搜索（2026-10-30）：Tab 行放大镜 = 全站唯一搜索入口 ──
  // 一个输入框、一个浮层；筛选目标跟随当前激活的 Tab——在哪个 Tab 就只搜哪个 Tab 的笔记。
  const normalize = (value) => value.toLocaleLowerCase('zh-CN').replace(/[\s：:，,。.!！?？、-]/g, '');
  var searchReady = false; // activate() 初始化时就会调 syncSearchPanel（函数声明提升），用 var 标志挡住未初始化阶段
  let searchPanel = null;
  let searchCards = [];
  const searchToggle = document.getElementById('shelf-search-toggle');
  const searchPop = document.getElementById('shelf-search-pop');
  const searchInput = searchPop ? searchPop.querySelector('input') : null;
  const searchStatus = document.querySelector('[data-search-status][for="shelf-search"]');

  const applySearch = () => {
    if (!searchPanel || !searchInput) return;
    const query = normalize(searchInput.value.trim());
    let shown = 0;
    searchCards.forEach((card) => {
      const match = !query || normalize(`${card.dataset.search || ''} ${card.textContent || ''}`).includes(query);
      card.hidden = !match;
      if (match) shown += 1;
    });
    if (searchStatus) searchStatus.textContent = query ? `找到 ${shown} 本` : `共 ${searchCards.length} 本`;
    const empty = searchPanel.querySelector('[data-empty-state]');
    if (empty) empty.hidden = shown > 0;
    searchPanel.querySelectorAll('.reading-group').forEach((group) => {
      group.hidden = query !== '' && ![...group.querySelectorAll('.archive-card')].some((card) => !card.hidden);
    });
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
