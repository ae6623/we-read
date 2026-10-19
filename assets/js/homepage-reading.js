(() => {
  const module = document.querySelector('[data-reading-module]');
  if (!module) return;
  const list = module.querySelector('[data-tablist]');
  const tabs = [...list.querySelectorAll('button[data-panel]')];
  const panels = tabs.map((tab) => document.getElementById(tab.dataset.panel));
  if (panels.some((panel) => !panel)) return;

  // Progressive enhancement: without JS, all sections and their links remain visible.
  const activate = (index, focus = false) => {
    tabs.forEach((tab, position) => {
      const selected = position === index;
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
      panels[position].hidden = !selected;
    });
    if (focus) tabs[index].focus();
  };
  list.setAttribute('role', 'tablist');
  tabs.forEach((tab, index) => {
    tab.setAttribute('role', 'tab');
    tab.setAttribute('aria-controls', panels[index].id);
    panels[index].setAttribute('role', 'tabpanel');
    panels[index].setAttribute('aria-labelledby', tab.id);
    panels[index].tabIndex = 0;
    tab.addEventListener('click', () => activate(index));
    tab.addEventListener('keydown', (event) => {
      let next;
      if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
      else if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
      else if (event.key === 'Home') next = 0;
      else if (event.key === 'End') next = tabs.length - 1;
      else return;
      event.preventDefault();
      activate(next, true);
    });
  });
  // Every fresh page load starts on 精读; no stored tab or URL state overrides it.
  const defaultIndex = tabs.findIndex((tab) => tab.id === 'reading-tab-close');
  activate(defaultIndex >= 0 ? defaultIndex : 0);
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
