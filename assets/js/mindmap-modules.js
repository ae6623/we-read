/* 全站模块统一开关（一处修改、所有页面生效）
 *
 * 用法：把不要的模块置 false，刷新即全站隐藏；置 true 恢复。
 * 覆盖范围：
 *   1) 精读页模块区块 <section class="mmx-mod" aria-labelledby="…">——key = aria-labelledby；
 *   2) 任何带 data-module="key" 的元素（如首页「阅读理念」横条 reading-bar）；
 *   3) 逐章追问 <details class="mmx-ask">——key = "asks"，一键全站收起/隐藏。
 *
 * gen_mindmap.py 生成新精读页时也读取 docs/mindmap-modules.json（同一套开关）：
 * 关闭的模块不再生成到 HTML。本文件的开关额外负责「已生成页面」的运行时隐藏。
 * 2026-10-29 站主拍板：「来源与证据边界」(evib) 默认关闭。
 */
window.MINDMAP_MODULES = {
  oneline: true,       // 一句话主旨
  views: true,         // 核心观点初判
  top10: true,         // 原文金句 · 持续积累
  aiask: true,         // AI 问书
  higher: true,        // 用更高维度的知识看这本书
  verify: true,        // 阅读时要验证的问题
  thennow: true,       // 当年与今天 · 初步对照
  evib: false,         // 来源与证据边界
  coreask: true,       // 核心追问（第3批由 deep-read 合并而来）
  asks: true,          // 逐章追问 <details class="mmx-ask">（第3批合并产物）
  "reading-bar": true, // 首页「阅读理念」横条（data-module="reading-bar"）
  // —— 精读文章（日期笔记页）9 大板块，data-module 打在 section 上 ——
  "dn-metrics": true,   // 实际读了什么
  "dn-insight": true,   // 今天的核心理解
  "dn-mindmap": true,   // 思维导图
  "dn-framework": true, // 与整书框架的连接
  "dn-transfer": true,  // 可迁移的启发与问题
  "dn-thennow": true,   // 当年与今天
  "dn-top10": true,     // 原文段落 Top 10
  "dn-next": true,      // 下次从这里继续
  "dn-boundary": true   // 来源边界
};
// 兼容别名
window.SITE_MODULES = window.MINDMAP_MODULES;
(function () {
  "use strict";
  function apply() {
    var cfg = window.MINDMAP_MODULES || {};
    var i, key, nodes;
    // 1) 精读页模块区块
    nodes = document.querySelectorAll("section.mmx-mod");
    for (i = 0; i < nodes.length; i++) {
      key = nodes[i].getAttribute("aria-labelledby") || nodes[i].id;
      if (key && cfg[key] === false) {
        nodes[i].hidden = true;
        nodes[i].setAttribute("data-mm-off", "");
      }
    }
    // 2) 任意 data-module 元素
    nodes = document.querySelectorAll("[data-module]");
    for (i = 0; i < nodes.length; i++) {
      key = nodes[i].getAttribute("data-module");
      if (key && cfg[key] === false) {
        nodes[i].hidden = true;
        nodes[i].setAttribute("data-mm-off", "");
      }
    }
    // 3) 逐章追问
    if (cfg.asks === false) {
      nodes = document.querySelectorAll("details.mmx-ask");
      for (i = 0; i < nodes.length; i++) {
        nodes[i].hidden = true;
        nodes[i].setAttribute("data-mm-off", "");
      }
    }
  }
  // 4) 精读文章内容 JSON 填充：页面 <name>.html 同目录的 <name>.json 是内容数据源。
  //    改 JSON → 发布 → 刷新即生效，不必动 HTML。html 键为 null 时隐藏该模块。
  function fill() {
    var m = location.pathname.match(/\/([^\/]+)\.html$/);
    if (!m || !window.fetch) return;
    fetch(m[1] + ".json", { cache: "no-cache" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data || !data.modules) return;
        Object.keys(data.modules).forEach(function (k) {
          var el = document.querySelector('[data-module="' + k + '"]');
          if (!el) return;
          var v = data.modules[k];
          if (v === null) { el.hidden = true; el.setAttribute("data-mm-off", ""); return; }
          var html = (v && typeof v === "object") ? v.html : v;
          if (typeof html === "string") el.innerHTML = html;
        });
      })
      .catch(function () { /* 无 JSON 或离线预览时保持 HTML 原内容 */ });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { apply(); fill(); });
  } else {
    apply();
    fill();
  }
})();
