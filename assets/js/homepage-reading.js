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
  // A recognized URL hash selects its tab; otherwise start on 精读.
  const defaultIndex = tabs.findIndex((tab) => tab.id === 'reading-tab-close');
  const hashIndex = indexFromLocation();
  activate(hashIndex >= 0 ? hashIndex : (defaultIndex >= 0 ? defaultIndex : 0));
  module.setAttribute('data-tabs-ready', '');
  list.hidden = false;

  const normalize = (value) => value.toLocaleLowerCase('zh-CN').replace(/[\s：:，,。.!！?？、-]/g, '');
  panels.forEach((panel) => {
    const input = panel.querySelector('[data-card-search]');
    if (!input) return;
    const cards = [...panel.querySelectorAll('.archive-card')];
    const status = panel.querySelector('[data-search-status]');
    const empty = panel.querySelector('[data-empty-state]');
    const update = () => {
      const query = normalize(input.value.trim());
      let shown = 0;
      cards.forEach((card) => {
        const match = !query || normalize(`${card.dataset.search || ''} ${card.textContent || ''}`).includes(query);
        card.hidden = !match;
        if (match) shown += 1;
      });
      status.textContent = query ? `找到 ${shown} 个匹配条目` : `显示全部 ${cards.length} 个条目`;
      empty.hidden = shown > 0;
      panel.querySelectorAll('.reading-group').forEach((group) => {
        group.hidden = query !== '' && ![...group.querySelectorAll('.archive-card')].some((card) => !card.hidden);
      });
    };
    input.addEventListener('input', update);
    update();
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
