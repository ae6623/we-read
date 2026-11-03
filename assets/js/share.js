/*!
 * share.js — 页面分享组件（二维码 + 微博 / QQ空间 / 复制链接）
 *
 * 用法：引入本文件即可。脚本会在 .series-page 的导航右侧自动放一个分享图标，
 * 不需要在每个页面模板里手写按钮，新增页面漏不掉。
 *
 * 微信、朋友圈没有可用的网页分享协议（需 JS-SDK 与公众号授权），
 * 统一用「当前页二维码」实现：扫一扫或截图发出去。
 */
(function () {
  'use strict';

  var PAGE_URL = location.href.split('#')[0];
  var PAGE_TITLE = (document.title || document.querySelector('h1') && document.querySelector('h1').textContent || '').replace(/｜.*$/, '').trim();

  var TIPS = {
    wechat: '用微信扫一扫，或长按识别二维码',
    moments: '保存二维码图片，发朋友圈时带上即可',
    copy: '链接已复制'
  };

  function enc(s) { return encodeURIComponent(s || ''); }

  function buildPanel() {
    var mask = document.createElement('div');
    mask.className = 'share-mask';
    mask.hidden = true;
    mask.innerHTML =
      '<div class="share-box" role="dialog" aria-modal="true" aria-label="分享这一页">' +
        '<button type="button" class="share-x" aria-label="关闭">×</button>' +
        '<p class="share-eyebrow">SHARE · 分享</p>' +
        '<h2 class="share-h">分享这一页</h2>' +
        '<div class="share-qr" aria-label="当前页二维码"></div>' +
        '<p class="share-tip">用微信扫一扫，或长按识别二维码</p>' +
        '<div class="share-acts">' +
          '<button type="button" data-act="wechat">微信</button>' +
          '<button type="button" data-act="moments">朋友圈</button>' +
          '<a data-act="weibo" href="#" target="_blank" rel="noopener">微博</a>' +
          '<a data-act="qzone" href="#" target="_blank" rel="noopener">QQ空间</a>' +
        '</div>' +
        '<button type="button" class="share-copy">复制链接</button>' +
      '</div>';
    document.body.appendChild(mask);
    return mask;
  }

  function init() {
    var nav = document.querySelector('.series-page .series-nav') || document.querySelector('.series-nav');
    if (!nav) return;

    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'share-btn';
    btn.setAttribute('aria-label', '分享这一页');
    btn.title = '分享这一页';
    btn.innerHTML =
      '<svg viewBox="0 0 24 24" aria-hidden="true" width="16" height="16">' +
      '<circle cx="18" cy="5" r="2.6" fill="none" stroke="currentColor" stroke-width="1.8"/>' +
      '<circle cx="6" cy="12" r="2.6" fill="none" stroke="currentColor" stroke-width="1.8"/>' +
      '<circle cx="18" cy="19" r="2.6" fill="none" stroke="currentColor" stroke-width="1.8"/>' +
      '<path d="M8.3 10.7l7.4-4.3M8.3 13.3l7.4 4.3" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>' +
      '</svg>';
    nav.appendChild(btn);

    var mask = buildPanel();
    var qrBox = mask.querySelector('.share-qr');
    var tip = mask.querySelector('.share-tip');
    var qrDone = false;

    mask.querySelector('[data-act="weibo"]').href =
      'https://service.weibo.com/share/share.php?url=' + enc(PAGE_URL) + '&title=' + enc(PAGE_TITLE);
    mask.querySelector('[data-act="qzone"]').href =
      'https://sns.qzone.qq.com/cgi-bin/qzshare/cgi_qzshare_onekey?url=' + enc(PAGE_URL) + '&title=' + enc(PAGE_TITLE);

    function openPanel() {
      mask.hidden = false;
      document.body.style.overflow = 'hidden';
      if (!qrDone && window.QRCode) {
        qrDone = true;
        new window.QRCode(qrBox, {
          text: PAGE_URL,
          width: 176,
          height: 176,
          colorDark: '#183c34',
          colorLight: '#fffefa',
          correctLevel: window.QRCode.CorrectLevel.M
        });
      }
      var close = mask.querySelector('.share-x');
      if (close) close.focus();
    }

    function closePanel() {
      mask.hidden = true;
      document.body.style.overflow = '';
      btn.focus();
    }

    btn.addEventListener('click', openPanel);
    mask.querySelector('.share-x').addEventListener('click', closePanel);
    mask.addEventListener('click', function (ev) {
      if (ev.target === mask) closePanel();
    });
    document.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape' && !mask.hidden) closePanel();
    });

    Array.prototype.forEach.call(mask.querySelectorAll('[data-act="wechat"],[data-act="moments"]'), function (el) {
      el.addEventListener('click', function () {
        var act = el.getAttribute('data-act');
        tip.textContent = TIPS[act] || '';
        qrBox.classList.remove('is-pulse');
        void qrBox.offsetWidth;
        qrBox.classList.add('is-pulse');
      });
    });

    mask.querySelector('.share-copy').addEventListener('click', function () {
      var done = function () { tip.textContent = TIPS.copy; };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(PAGE_URL).then(done, function () { window.prompt('复制链接', PAGE_URL); });
      } else {
        window.prompt('复制链接', PAGE_URL);
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
