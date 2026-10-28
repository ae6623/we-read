/* mindmap.js — 全书结构区块的「全部展开 / 收起」控制（无依赖） */
(function () {
  'use strict';
  function each(list, fn) { Array.prototype.forEach.call(list, fn); }
  function init() {
    each(document.querySelectorAll('.mm'), function (mm) {
      each(mm.querySelectorAll('.mm-btn'), function (btn) {
        btn.addEventListener('click', function () {
          var open = btn.getAttribute('data-mm') === 'open';
          each(mm.querySelectorAll('details'), function (d) { d.open = open; });
        });
      });
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
