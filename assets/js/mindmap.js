/* mindmap.js — 全书结构区块的「全部展开 / 收起」控制 + 折叠点击兜底（无依赖） */
(function () {
  'use strict';

  function each(list, fn) { Array.prototype.forEach.call(list, fn); }

  function closestTag(el, tag) {
    while (el && el.nodeType === 1) {
      if (el.tagName === tag) return el;
      el = el.parentElement;
    }
    return null;
  }

  /* 「全部展开 / 全部收起」 */
  function initButtons() {
    each(document.querySelectorAll('.mm'), function (mm) {
      each(mm.querySelectorAll('.mm-btn'), function (btn) {
        btn.addEventListener('click', function () {
          var open = btn.getAttribute('data-mm') === 'open';
          each(mm.querySelectorAll('details'), function (d) { d.open = open; });
        });
      });
    });
  }

  /* 兜底：部分 WebKit 上 summary 的点击热区会丢（summary 内是 flex / 图标时最容易中招），
     点了没反应。这里在捕获阶段记下点击前的 open 状态，稍后若仍未变就补一次切换；
     原生已正常处理的不会被重复触发。 */
  function initFallback() {
    document.addEventListener('click', function (e) {
      var s = closestTag(e.target, 'SUMMARY');
      if (!s) return;
      var d = s.parentNode;
      if (!d || d.tagName !== 'DETAILS') return;
      var was = d.open;
      setTimeout(function () {
        if (d.isConnected === false) return;
        if (d.open === was) d.open = !was;
      }, 180);
    }, true);
  }

  function init() { initButtons(); initFallback(); }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
