/*!
 * share.js — 页面分享组件（封面 + 二维码 + 微博 / QQ空间 / 复制链接）
 *
 * 用法：引入本文件即可。脚本会自动找挂载点放一个分享图标：
 *   - 系列页：.series-nav 右侧
 *   - 书籍详情页：header.combined-head 右上角
 * 不需要在每个页面模板里手写按钮，新增页面漏不掉。
 *
 * 微信、朋友圈没有可用的网页分享协议（需 JS-SDK 与公众号授权），
 * 统一用「当前页二维码」实现：扫一扫或截图发出去。
 *
 * 详情页会在二维码旁边带上本书封面，可一键切换「横版（书左码右）/
 * 竖版（书上码下）」，选择记在 localStorage，小屏默认竖版。
 */
(function () {
  'use strict';

  var PAGE_URL = location.href.split('#')[0];
  var PAGE_TITLE = (document.title || document.querySelector('h1') && document.querySelector('h1').textContent || '').replace(/｜.*$/, '').trim();
  var SELF_SRC = (document.currentScript && document.currentScript.src) || '';
  var LAYOUT_KEY = 'wrShareLayout';

  var TIPS = {
    wechat: '用微信扫一扫，或长按识别二维码',
    moments: '保存二维码图片，发朋友圈时带上即可',
    copy: '链接已复制'
  };

  function enc(s) { return encodeURIComponent(s || ''); }
  function esc(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function safeDecode(s) {
    if (!/%[0-9a-fA-F]{2}/.test(s)) return s;
    try { return decodeURIComponent(s); } catch (e) { return s; }
  }
  /* share.js 在 assets/js/ 下，按脚本自身地址反推站点根，兼容任意层级页面 */
  function siteRoot() {
    if (SELF_SRC) {
      var m = SELF_SRC.match(/^(.*?)\/assets\/js\/share\.js/);
      if (m) return m[1] + '/';
    }
    return '../../../';
  }

  /* 四个渠道的线性图标：跟面板同一套 1.6px 描边，不引外部图标库 */
  var ICON = {
    wechat:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9.4 4.2c-3.5 0-6.4 2.3-6.4 5.2 0 1.7.9 3.1 2.4 4.1l-.6 2 2.2-1.1c.6.2 1.3.3 2 .4"/>' +
      '<path d="M21 14.1c0-2.6-2.4-4.7-5.4-4.7S10.2 11.5 10.2 14c0 2.6 2.4 4.7 5.4 4.7.7 0 1.4-.1 2-.3l1.9 1-.4-1.8c1.2-.8 1.9-2.1 1.9-3.5z"/>' +
      '<circle cx="7.1" cy="8.5" r=".85" fill="currentColor" stroke="none"/><circle cx="11.2" cy="8.5" r=".85" fill="currentColor" stroke="none"/>' +
      '<circle cx="13.7" cy="13.2" r=".75" fill="currentColor" stroke="none"/><circle cx="17.1" cy="13.2" r=".75" fill="currentColor" stroke="none"/></svg>',
    moments:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.4"/>' +
      '<circle cx="12" cy="12" r="2.1" fill="currentColor" stroke="none"/>' +
      '<circle cx="12" cy="5.3" r="1" fill="currentColor" stroke="none"/><circle cx="12" cy="18.7" r="1" fill="currentColor" stroke="none"/>' +
      '<circle cx="5.3" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="18.7" cy="12" r="1" fill="currentColor" stroke="none"/></svg>',
    weibo:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><ellipse cx="10.6" cy="13.8" rx="7.4" ry="5.1"/>' +
      '<circle cx="10.6" cy="13.8" r="2.1" fill="currentColor" stroke="none"/>' +
      '<path d="M17.3 8.6c1.6-.4 2.8.6 2.6 2.1"/><path d="M16.6 5.6c3.1-.7 5.3 1.3 4.7 4"/></svg>',
    qzone:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.7l2.5 5.1 5.6.8-4.1 3.9 1 5.6-5-2.7-5 2.7 1-5.6-4.1-3.9 5.6-.8z"/></svg>',
    /* 切换图标画的是「点了会变成的版式」：横版时显示竖排块，反之亦然 */
    toV:
      '<svg viewBox="0 0 24 24" aria-hidden="true" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round">' +
      '<rect x="6.5" y="3.5" width="11" height="7" rx="1.4"/><rect x="6.5" y="13.5" width="11" height="7" rx="1.4"/></svg>',
    toH:
      '<svg viewBox="0 0 24 24" aria-hidden="true" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round">' +
      '<rect x="3.5" y="6.5" width="7" height="11" rx="1.4"/><rect x="13.5" y="6.5" width="7" height="11" rx="1.4"/></svg>'
  };

  function pageSlug() {
    var s = (document.body.getAttribute('data-slug') || '').trim();
    if (s) return s;
    var m = location.pathname.match(/\/books\/([^\/]+)\//);
    return m ? safeDecode(m[1]) : '';
  }

  function bookTitle() {
    var t = safeDecode((document.body.getAttribute('data-title') || '').trim());
    if (!t) {
      var h1 = document.querySelector('header.combined-head h1') || document.querySelector('h1');
      if (h1) t = h1.textContent || '';
    }
    if (!t) t = PAGE_TITLE;
    t = t.replace(/[｜|][^｜|]*$/, '').replace(/\s+/g, ' ').trim();
    return t.replace(/^《/, '').replace(/》$/, '');
  }

  function buildPanel(info) {
    /* 有书：照详情页页头的做法，同一张封面放大模糊当背景，清晰封面浮在中间 */
    var poster = info.hasBook
      ? '<div class="share-poster">' +
          '<div class="share-hero">' +
            '<img class="share-hero-bg" alt="" aria-hidden="true" decoding="async">' +
            '<img class="share-hero-cover" alt="' + esc(info.title) + ' 封面" loading="eager" decoding="async">' +
          '</div>' +
          '<div class="share-book">' +
            '<p class="share-bt">《' + esc(info.title) + '》</p>' +
            '<p class="share-bs">阅读笔记 · 全书领读</p>' +
          '</div>' +
          '<div class="share-qrcol">' +
            '<div class="share-qr" aria-label="当前页二维码"></div>' +
            '<p class="share-tip">用微信扫一扫，或长按识别二维码</p>' +
          '</div>' +
        '</div>'
      : '<div class="share-qr" aria-label="当前页二维码"></div>' +
        '<p class="share-tip">用微信扫一扫，或长按识别二维码</p>';

    var mask = document.createElement('div');
    mask.className = 'share-mask';
    mask.hidden = true;
    mask.innerHTML =
      '<div class="share-box' + (info.hasBook ? ' has-hero' : '') + '" role="dialog" aria-modal="true" aria-label="分享本篇笔记">' +
        (info.hasBook ? '<button type="button" class="share-layout" aria-label="切换竖版"></button>' : '') +
        '<button type="button" class="share-x" aria-label="关闭">×</button>' +
        '<p class="share-eyebrow">SHARE · 分享</p>' +
        '<h2 class="share-h">分享本篇笔记</h2>' +
        poster +
        '<div class="share-acts">' +
          '<button type="button" data-act="wechat">' + ICON.wechat + '<span>微信</span></button>' +
          '<button type="button" data-act="moments">' + ICON.moments + '<span>朋友圈</span></button>' +
          '<a data-act="weibo" href="#" target="_blank" rel="noopener">' + ICON.weibo + '<span>微博</span></a>' +
          '<a data-act="qzone" href="#" target="_blank" rel="noopener">' + ICON.qzone + '<span>QQ空间</span></a>' +
        '</div>' +
        '<button type="button" class="share-copy">复制链接</button>' +
      '</div>';
    document.body.appendChild(mask);
    return mask;
  }

  function init() {
    var nav = document.querySelector('.series-page .series-nav') || document.querySelector('.series-nav');
    var head = document.querySelector('header.combined-head');
    if (!nav && !head) return;

    var btn = document.createElement('button');
    btn.type = 'button';
    btn.setAttribute('aria-label', '分享本篇笔记');
    btn.title = '分享本篇笔记';
    btn.innerHTML =
      '<svg viewBox="0 0 24 24" aria-hidden="true" width="16" height="16">' +
      '<circle cx="18" cy="5" r="2.6" fill="none" stroke="currentColor" stroke-width="1.8"/>' +
      '<circle cx="6" cy="12" r="2.6" fill="none" stroke="currentColor" stroke-width="1.8"/>' +
      '<circle cx="18" cy="19" r="2.6" fill="none" stroke="currentColor" stroke-width="1.8"/>' +
      '<path d="M8.3 10.7l7.4-4.3M8.3 13.3l7.4 4.3" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>' +
      '</svg>';

    if (nav && !head) {
      /* 系列页：放进顶部导航右侧 */
      btn.className = 'share-btn';
      nav.appendChild(btn);
    } else {
      /* 详情页：右上角浮动，和 Aa 设置钮并排（页面有两种头部形态，
         浮动按钮不受 header 是否被隐藏影响） */
      btn.className = 'share-btn share-btn--float';
      document.body.appendChild(btn);
    }

    var slug = pageSlug();
    var title = bookTitle();
    var mask = buildPanel({ hasBook: !!slug, title: title });
    var box = mask.querySelector('.share-box');
    var qrBox = mask.querySelector('.share-qr');
    var tip = mask.querySelector('.share-tip');
    var layoutBtn = mask.querySelector('.share-layout');
    var qrDone = false;

    /* 封面：本地文件，取不到就整块收起，版式退回单列 */
    var coverImg = mask.querySelector('.share-hero-cover');
    if (coverImg && slug) {
      var coverSrc = 'https://cdn.js-dev.cn/assets/covers/' + encodeURIComponent(slug) + '.jpg';
      coverImg.addEventListener('error', function () {
        box.classList.add('is-nocover');
      });
      coverImg.src = coverSrc;
      var coverBg = mask.querySelector('.share-hero-bg');
      if (coverBg) coverBg.src = coverSrc;
    }

    /* 横版 = 书左码右；竖版 = 书上码下。小屏默认竖版 */
    function applyLayout(v, save) {
      box.setAttribute('data-layout', v);
      if (layoutBtn) {
        layoutBtn.innerHTML = v === 'h' ? ICON.toV : ICON.toH;
        layoutBtn.setAttribute('aria-label', v === 'h' ? '切换为竖版' : '切换为横版');
        layoutBtn.title = v === 'h' ? '竖版排版' : '横版排版';
      }
      if (save) { try { localStorage.setItem(LAYOUT_KEY, v); } catch (e) { /* 无痕模式忽略 */ } }
    }
    if (slug) {
      var saved = null;
      try { saved = localStorage.getItem(LAYOUT_KEY); } catch (e) { /* 忽略 */ }
      var small = window.matchMedia && window.matchMedia('(max-width:560px)').matches;
      applyLayout(saved === 'h' || saved === 'v' ? saved : (small ? 'v' : 'h'), false);
    }

    if (layoutBtn) {
      layoutBtn.addEventListener('click', function () {
        applyLayout(box.getAttribute('data-layout') === 'h' ? 'v' : 'h', true);
      });
    }

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
          /* 生成 264px，再按布局用 CSS 缩到 112~176 —— 缩小不糊，放大也不虚 */
          width: 264,
          height: 264,
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
        // 微信 / 朋友圈没有网页分享协议，点了也跳不过去：
        // 直接把当前页链接写进剪贴板，用户切到微信粘贴即可
        tip.textContent = TIPS[act] || '';
        copyLink(function (ok) {
          if (!ok) return;
          tip.textContent = act === 'moments'
            ? '链接已复制，去朋友圈粘贴即可'
            : '链接已复制，去微信粘贴给好友';
        });
        qrBox.classList.remove('is-pulse');
        void qrBox.offsetWidth;
        qrBox.classList.add('is-pulse');
      });
    });

    function copyLink(done) {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(PAGE_URL).then(function () { done && done(true); },
          function () { window.prompt('复制链接', PAGE_URL); done && done(false); });
        return;
      }
      window.prompt('复制链接', PAGE_URL);
      done && done(false);
    }

    mask.querySelector('.share-copy').addEventListener('click', function () {
      copyLink(function () { tip.textContent = TIPS.copy; });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
