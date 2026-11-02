/* ============================================================
   home-track.js — 首页埋点（走 GoatCounter 的 event 通道）

   为什么用它：页脚「次访问 / 位访客」本来就走 ae6623.goatcounter.com，
   同一个账号支持自定义事件（count({event:true})），事件不进 PV 统计，
   单独出现在后台 Events 列表里，还能用 /counter/<path>.json 读回来。
   所以不用再引第三方 SDK、不用自建服务。

   接口：window.rdTrack(path, title)
     path  —— 上报路径，约定见 note-spec/README.md「埋点口径」
     title —— 后台显示的文案（可选）

   去重：同一次页面访问里，同一个 path 只发一次（曝光这类幂等事件天然适用）。
   限流：单次访问最多发 MAX 条，防止无限滚动时把配额打满。
   ============================================================ */
(function () {
  'use strict';

  var MAX = 60;
  var sent = {};
  var queue = [];
  var count = 0;
  var ready = false;

  function api() {
    return (window.goatcounter && typeof window.goatcounter.count === 'function')
      ? window.goatcounter : null;
  }

  function flush() {
    var gc = api();
    if (!gc) return;
    ready = true;
    while (queue.length && count < MAX) {
      var e = queue.shift();
      try {
        gc.count({ path: e.p, title: e.t, event: true });
        count++;
      } catch (x) { /* 统计失败不能影响页面 */ }
    }
    if (!queue.length) queue = [];
  }

  function push(path, title) {
    if (!path || sent[path]) return;
    sent[path] = 1;
    queue.push({ p: path, t: title || path });
    if (ready) flush();
  }

  /* count.js 是 async 加载的，等它挂上 window.goatcounter 再发；
     8 秒还没等到（被拦截 / 离线）就放弃，队列清空，不重试。 */
  var tries = 0;
  var timer = setInterval(function () {
    if (api()) { clearInterval(timer); flush(); return; }
    if (++tries > 40) { clearInterval(timer); queue = []; }
  }, 200);

  window.rdTrack = push;

  /* 调试用：控制台 rdTrackLog() 看本次访问报了哪些路径 */
  window.rdTrackLog = function () { return Object.keys(sent); };
})();
