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

  /* 详情页的「上一篇 / 下一篇」是无刷新换书（fetch + pushState），
     本脚本不会重新执行。所以 URL / 标题一律现取，不能在加载时快照，
     否则换书后分享的还是进来的那一本。 */
  function pageUrl() { return location.href.split('#')[0]; }
  function pageTitle() {
    return (document.title || document.querySelector('h1') && document.querySelector('h1').textContent || '')
      .replace(/｜.*$/, '').trim();
  }
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
      var m = SELF_SRC.match(/^(.*?)\/assets\/js\/share[^\/]*\.js/);
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
    /* 无刷新换书会 pushState 换 URL，但 body[data-slug] 是壳页写死的旧值；
       以 URL 为准才拿得到「当前这一本」。 */
    var m = location.pathname.match(/\/books\/([^\/]+)\//);
    if (m) return safeDecode(m[1]);
    return (document.body.getAttribute('data-slug') || '').trim();
  }

  function bookTitle() {
    /* renderChips() 换书时会更新 document.title 与 h1，优先用它们；
       body[data-title] 只在两者都缺时兜底（壳页写死，可能已过期）。 */
    var t = (document.title || '').replace(/[｜|][^｜|]*$/, '').trim();
    if (!t) {
      var h1 = document.querySelector('header.combined-head h1') || document.querySelector('h1');
      if (h1) t = (h1.textContent || '').trim();
    }
    if (!t) t = safeDecode((document.body.getAttribute('data-title') || '').trim());
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

    var hasBook = !!pageSlug();
    var mask = buildPanel({ hasBook: hasBook, title: bookTitle() });
    var box = mask.querySelector('.share-box');
    var qrBox = mask.querySelector('.share-qr');
    var tip = mask.querySelector('.share-tip');
    var layoutBtn = mask.querySelector('.share-layout');
    var coverImg = mask.querySelector('.share-hero-cover');
    var coverBg = mask.querySelector('.share-hero-bg');
    var bt = mask.querySelector('.share-bt');
    var weiboA = mask.querySelector('[data-act="weibo"]');
    var qzoneA = mask.querySelector('[data-act="qzone"]');
    var lastQrText = '';

    /* 封面取不到就整块收起；换书后新封面加载成功要把降级类撤掉 */
    if (coverImg) {
      coverImg.addEventListener('error', function () { box.classList.add('is-nocover'); });
      coverImg.addEventListener('load', function () { box.classList.remove('is-nocover'); });
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
    if (hasBook) {
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

    /* 每次打开面板（以及换书事件）都按「当前这一本」重算：
       书名 / 封面 / 二维码 / 外链 / 复制链接，不能留着上一本的快照。 */
    function syncPanel(force) {
      var url = pageUrl();
      var title = bookTitle();
      var slug = pageSlug();
      var pt = pageTitle();

      if (bt) bt.textContent = '《' + title + '》';
      if (coverImg && slug) {
        var src = 'https://cdn.js-dev.cn/assets/covers/' + encodeURIComponent(slug) + '.jpg';
        coverImg.alt = title + ' 封面';
        if (coverImg.getAttribute('src') !== src) {
          box.classList.remove('is-nocover');
          coverImg.src = src;
          if (coverBg) coverBg.src = src;
        }
      }
      if (weiboA) weiboA.href = 'https://service.weibo.com/share/share.php?url=' + enc(url) + '&title=' + enc(pt);
      if (qzoneA) qzoneA.href = 'https://sns.qzone.qq.com/cgi-bin/qzshare/cgi_qzshare_onekey?url=' + enc(url) + '&title=' + enc(pt);

      if (force || url !== lastQrText) {
        lastQrText = url;
        if (window.QRCode) {
          qrBox.innerHTML = '';
          qrBox.classList.remove('is-pulse');
          new window.QRCode(qrBox, {
            text: url,
            /* 生成 264px，再按布局用 CSS 缩到 112~176 —— 缩小不糊，放大也不虚 */
            width: 264,
            height: 264,
            colorDark: '#183c34',
            colorLight: '#fffefa',
            correctLevel: window.QRCode.CorrectLevel.M
          });
        }
        tip.textContent = TIPS.wechat;
      }
    }

    function openPanel() {
      syncPanel(true);          /* 换书 / 前进后退后，强制按当前页重建二维码 */
      mask.hidden = false;
      document.body.style.overflow = 'hidden';
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

    /* 无刷新换书：reader.js 渲染完会派发 wr:bookchange；浏览器前进后退走
       popstate。面板恰好开着时也立即重建二维码，不留上一本的码。 */
    function refreshIfOpen() { if (!mask.hidden) syncPanel(true); }
    document.addEventListener('wr:bookchange', refreshIfOpen);
    window.addEventListener('popstate', function () { setTimeout(refreshIfOpen, 0); });

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
      var url = pageUrl();      /* 换书后复制的必须是当前这本，不是进来的那本 */
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(function () { done && done(true); },
          function () { window.prompt('复制链接', url); done && done(false); });
        return;
      }
      window.prompt('复制链接', url);
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
