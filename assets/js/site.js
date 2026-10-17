(() => {
  const input = document.querySelector('#archive-search');
  const cards = [...document.querySelectorAll('.archive-card')];
  const status = document.querySelector('#search-status');
  const empty = document.querySelector('#empty-state');
  if (!input || !cards.length) return;

  const normalize = (value) => value.toLocaleLowerCase('zh-CN').replace(/[\s：:，,。.!！?？、-]/g, '');
  const update = () => {
    const query = normalize(input.value.trim());
    let shown = 0;
    for (const card of cards) {
      const haystack = normalize(`${card.dataset.search || ''} ${card.textContent || ''}`);
      const match = !query || haystack.includes(query);
      card.hidden = !match;
      if (match) shown += 1;
    }
    status.textContent = query ? `找到 ${shown} 个匹配条目` : `显示全部 ${cards.length} 个条目`;
    empty.hidden = shown > 0;
  };
  input.addEventListener('input', update);
})();
