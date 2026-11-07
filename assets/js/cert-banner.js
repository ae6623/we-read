/* 证书到期提醒条幅
 *
 * 七牛免费证书有效期 90 天、不会自动续期。这里在到期前 7 天开始，
 * 于每个页面顶部显示一条提醒，点「去续期」直接跳到七牛控制台。
 *
 * 续期后只需要改下面的 EXPIRES 常量（或让 Agent 改）。
 */
(function () {
  'use strict';

  // 当前证书到期时间（七牛控制台 → 域名管理 → HTTPS 配置 里可查）
  var EXPIRES = Date.parse('2027-02-05T19:59:59+08:00');
  var WARN_DAYS = 7;
  var CONSOLE_URL = 'https://portal.qiniu.com/cdn/domain';
  var KEY = 'cert-banner-dismissed';

  if (!EXPIRES || isNaN(EXPIRES)) return;

  var daysLeft = Math.ceil((EXPIRES - Date.now()) / 86400000);

  // 8–30 天只在控制台提示，不打扰读者
  if (daysLeft > WARN_DAYS && daysLeft <= 30) {
    console.warn('[cert] 七牛 CDN 证书还有 ' + daysLeft + ' 天到期，记得续期：' + CONSOLE_URL);
    return;
  }
  if (daysLeft > WARN_DAYS) return;
  try {
    if (sessionStorage.getItem(KEY) === '1') return;
  } catch (e) { /* 隐私模式下忽略 */ }

  var expired = daysLeft <= 0;
  var text = expired
    ? '七牛 CDN 证书已过期（' + fmt(EXPIRES) + '），图片等素材可能无法加载'
    : '七牛 CDN 证书 ' + daysLeft + ' 天后到期（' + fmt(EXPIRES) + '），请及时续期';

  function fmt(ts) {
    var d = new Date(ts);
    return (d.getMonth() + 1) + '月' + d.getDate() + '日';
  }

  function mount() {
    var bar = document.createElement('div');
    bar.setAttribute('role', 'status');
    bar.style.cssText = [
      'position:fixed', 'left:0', 'right:0', 'top:0', 'z-index:2147483000',
      'display:flex', 'align-items:center', 'gap:12px', 'justify-content:center',
      'padding:10px 16px', 'box-sizing:border-box',
      'font:14px/1.5 -apple-system,"Segoe UI","PingFang SC",sans-serif',
      'color:#3a2a00', 'background:' + (expired ? '#fde2e1' : '#fff4d6'),
      'border-bottom:1px solid ' + (expired ? '#e8a3a0' : '#e8d39a')
    ].join(';');

    var label = document.createElement('span');
    label.textContent = text;

    var link = document.createElement('a');
    link.href = CONSOLE_URL;
    link.target = '_blank';
    link.rel = 'noopener';
    link.textContent = '去续期';
    link.style.cssText = 'color:#0b5cad;font-weight:600;text-decoration:underline;white-space:nowrap';

    var close = document.createElement('button');
    close.type = 'button';
    close.textContent = '知道了';
    close.style.cssText = [
      'border:1px solid ' + (expired ? '#e8a3a0' : '#e8d39a'),
      'background:#fff', 'color:#3a2a00', 'border-radius:999px',
      'padding:2px 12px', 'font:inherit', 'cursor:pointer', 'white-space:nowrap'
    ].join(';');
    close.addEventListener('click', function () {
      bar.remove();
      document.body.style.paddingTop = previousPadding;
      try { sessionStorage.setItem(KEY, '1'); } catch (e) { /* ignore */ }
    });

    bar.appendChild(label);
    bar.appendChild(link);
    bar.appendChild(close);
    document.body.appendChild(bar);

    // 让出条幅高度，避免盖住页面顶部内容
    var previousPadding = document.body.style.paddingTop;
    document.body.style.paddingTop = (bar.offsetHeight || 40) + 'px';
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount);
  } else {
    mount();
  }
})();
