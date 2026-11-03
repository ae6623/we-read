/*!
 * weread-link.js — 站内「去原书」跳转的唯一入口。
 *
 * 用法：<a href="{deepLink}" data-weread-id="{bookId}">书名</a>
 *
 * 2026-11-03 调整：统一走网页版。移动端不再尝试 weread:// 唤起 App
 * —— iOS 未安装时会弹「无法打开页面」，体验比直接开网页更差。
 * 现在所有端行为一致：跟随 href（官方深链）落到网页版书籍页。
 *
 * 保留本文件的意义：所有页面共用一处跳转约定，新增入口只加 data-weread-id，
 * 不各写一份内联脚本；href 缺失时由本组件兜底提示，避免出现死链。
 */
(function () {
  'use strict';

  function open(bookId, url) {
    if (url) {
      window.location.href = url;
      return false;
    }
    console.warn('[weread-link] 缺少 href，bookId=' + bookId);
    return false;
  }

  function bind(root) {
    var scope = root && root.querySelectorAll ? root : document;
    var links = scope.querySelectorAll('a[data-weread-id]');
    Array.prototype.forEach.call(links, function (a) {
      if (a.getAttribute('data-weread-bound')) return;
      a.setAttribute('data-weread-bound', '1');
      if (!a.getAttribute('href')) {
        a.setAttribute('href', '#');
        a.addEventListener('click', function (ev) {
          ev.preventDefault();
          open(a.getAttribute('data-weread-id'), '');
        });
      }
    });
  }

  window.WereadLink = { open: open, bind: bind, mode: 'web' };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { bind(); });
  } else {
    bind();
  }
})();
