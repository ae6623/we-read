/* 精读页模块统一开关（全站唯一配置，一处修改、所有精读页生效）
 *
 * 用法：把不要的模块置 false，刷新即全站隐藏；置 true 恢复。
 * key = 精读页模块区块 <section class="mmx-mod" aria-labelledby="…"> 的锚点 id。
 *
 * gen_mindmap.py 生成新页时也读取本配置：关闭的模块不再生成到 HTML。
 * 2026-10-29 站主拍板：「来源与证据边界」(evib) 默认关闭。
 */
window.MINDMAP_MODULES = {
  oneline: true,   // 一句话主旨
  views: true,     // 核心观点初判
  top10: true,     // 原文金句 · 持续积累
  aiask: true,     // AI 问书
  higher: true,    // 用更高维度的知识看这本书
  verify: true,    // 阅读时要验证的问题
  thennow: true,   // 当年与今天 · 初步对照
  evib: false      // 来源与证据边界
};
(function () {
  "use strict";
  function apply() {
    var cfg = window.MINDMAP_MODULES || {};
    var secs = document.querySelectorAll("section.mmx-mod");
    for (var i = 0; i < secs.length; i++) {
      var key = secs[i].getAttribute("aria-labelledby") || secs[i].id;
      if (key && cfg[key] === false) {
        secs[i].hidden = true;
        secs[i].setAttribute("data-mm-off", "");
      }
    }
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", apply);
  } else {
    apply();
  }
})();
