/*!
 * weread-link.js — 站内「去原书」跳转的唯一入口。
 *
 * 用法：<a href="{deepLink}" data-weread-id="{bookId}">书名</a>
 *   - PC / 桌面浏览器：直接跟随 href（官方深链，落到网页版）
 *   - 移动端：先尝试 weread://reading?bId=<bookId> 唤起 App，
 *             未唤起则 600ms 后回落到 href，不会白屏
 *
 * 页面只需引入本文件 + 给链接加 data-weread-id，不要各写一份内联脚本。
 */
(function () {
  'use strict';

  var MOBILE = /Mobi|Android|iPhone|iPad|iPod|HarmonyOS|MicroMessenger/i.test(navigator.userAgent);

  function open(bookId, fallbackUrl) {
    if (!bookId) {
      if (fallbackUrl) location.href = fallbackUrl;
      return;
    }
    if (!MOBILE) {
      if (fallbackUrl) location.href = fallbackUrl;
      return;
    }
    var t0 = Date.now();
    try {
      location.href = 'weread://reading?bId=' + encodeURIComponent(bookId);
    } catch (e) { /* 不支持 scheme 的环境直接回落 */ }
    setTimeout(function () {
      if (Date.now() - t0 < 1500 && fallbackUrl) location.href = fallbackUrl;
    }, 600);
  }

  function bind(root) {
    var scope = root && root.querySelectorAll ? root : document;
    var links = scope.querySelectorAll('a[data-weread-id]');
    Array.prototype.forEach.call(links, function (a) {
      if (a.getAttribute('data-weread-bound')) return;
      a.setAttribute('data-weread-bound', '1');
      a.addEventListener('click', function (ev) {
        var bid = a.getAttribute('data-weread-id');
        if (!bid) return;
        var href = a.getAttribute('href') || '';
        // PC 端交给浏览器默认行为，保证直接落到官方 url
        if (!MOBILE) return;
        ev.preventDefault();
        open(bid, href);
      });
    });
  }

  window.WereadLink = { open: open, bind: bind, isMobile: MOBILE };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { bind(); });
  } else {
    bind();
  }
})();
