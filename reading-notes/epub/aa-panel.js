/* aa-panel.js — EPUB 阅读器「Aa」配置面板（详情页组件通用版）
 *
 * 来源：assets/js/reader.js 的 initSettings / initSpeak / initFonts 三段，
 * 去掉合并页数据装配依赖，改成通过 hooks 适配任意阅读器（这里是 epub.js）。
 * 沿用详情页同款：#rdFab / #rdPanel / .rd-speak-box / #rdSpeakBar，
 * 同款云端 edge-tts 晓晓、音色/语速/音调/音量、按需加载字体。
 * 新增图二「控制选项」：屏幕方向、摇动手机、上下/左右区域点击、长按、
 * 方向键与硬件按键、双栏阅读。
 *
 * 用法：EpubAA.init(hooks); EpubAA.bindFrame(rendition);
 * hooks: onCfg(cfg), page(dir), chapter(dir), back(), pageText(), highlight(el),
 *        onRelocated(cb), resize(), notify(msg), escape(), focusSearch()
 */
(function () {
  'use strict';

  var KEY = 'epub-aa-cfg-v1';
  var DEF = {
    theme: 'dark',            // 默认夜色
    fs: 108, lh: 1.85, font: '',
    spread: 'none', flow: 'paginated',
    orient: 'auto', shake: 'none',
    tapMode: 'vertical',
    tapTop: 'prev', tapBottom: 'next',
    tapLeft: 'prev', tapRight: 'next', tapCenter: 'none',
    longPress: 'copy',
    keyUp: 'prev', keyDown: 'next', keyLeft: 'prev', keyRight: 'next',
    volumeUp: 'prev', volumeDown: 'next', keyBack: 'back', keyMenu: 'settings',
    rate: 1, pitch: 1, volume: 1, voiceURI: '__auto__'   // 默认云端晓晓
  };
  var THEMES = ['dark', 'cream', 'light', 'green'];
  var FS = [80, 88, 96, 108, 116, 128, 140, 160, 180];
  var LH = [1.55, 1.7, 1.85, 2.05, 2.3];
  var ACTIONS = [
    ['none', '无'], ['prev', '向上翻页'], ['next', '向下翻页'],
    ['prevChapter', '上一章'], ['nextChapter', '下一章'],
    ['settings', '打开设置'], ['speak', '听书 / 停止'],
    ['copy', '页面文字摘录'], ['back', '返回书架']
  ];
  var TAP_ACTIONS = ACTIONS.filter(function (a) { return a[0] !== 'back'; });
  var CLOUD = [
    { uri: 'zh-CN-XiaoxiaoNeural', label: '晓晓 · 默认女声' },
    { uri: 'zh-CN-XiaoyiNeural', label: '晓伊 · 年轻女声' },
    { uri: 'zh-CN-YunxiNeural', label: '云希 · 少年男声' },
    { uri: 'zh-TW-HsiaoChenNeural', label: '曉臻 · 台湾女声' }
  ];
  var TTS_BASE = 'https://a32eb29ccf0373711.app.workbuddy.host/tts?sharecode=N3AWQXFAIQ';
  var FONT_JSON = new URL('../../assets/fonts/fonts.json', location.href).href;
  var FONT_DIR = new URL('../../assets/fonts/', location.href).href;

  var cfg = loadCfg(), H = {};
  var panel, fab, bar, speakFab, box, fonts = [], activeChip = 'auto';
  var nativeLocked = false, motionBound = false, lastAcc = null, lastShake = 0;
  var suppressClickUntil = 0, press = null, pressTimer = null;

  function loadCfg() {
    var o = {}, c = {}, k;
    try { o = JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch (e) { o = {}; }
    for (k in DEF) if (DEF.hasOwnProperty(k)) c[k] = (o[k] === undefined ? DEF[k] : o[k]);
    return c;
  }
  function saveCfg() { try { localStorage.setItem(KEY, JSON.stringify(cfg)); } catch (e) {} }
  function q(s, r) { return (r || document).querySelector(s); }
  function qa(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function notify(msg) { if (H.notify) H.notify(msg, 2200); }
  function num(v, lo, hi, d) { var n = parseFloat(v); return isFinite(n) ? Math.min(hi, Math.max(lo, n)) : d; }

  /* ── 配置应用 ─────────────────────────────────────────────── */
  function apply(store) {
    if (store !== false) saveCfg();
    document.documentElement.setAttribute('data-theme', cfg.theme);
    var meta = q('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', { dark: '#17181b', cream: '#f7f8f3', light: '#fbfaf7', green: '#cfe8d2' }[cfg.theme] || '#17181b');
    if (H.onCfg) H.onCfg(cfg);
    syncRotate();
    refresh();
  }
  function stepFont(d) {
    var i = FS.indexOf(cfg.fs);
    if (i < 0) { i = 0; FS.forEach(function (v, j) { if (Math.abs(v - cfg.fs) < Math.abs(FS[i] - cfg.fs)) i = j; }); }
    cfg.fs = FS[Math.max(0, Math.min(FS.length - 1, i + d))];
    apply();
  }
  function stepLH(d) {
    var i = LH.indexOf(cfg.lh);
    if (i < 0) i = 2;
    cfg.lh = LH[Math.max(0, Math.min(LH.length - 1, i + d))];
    apply();
  }
  function cycleTheme() { cfg.theme = THEMES[(THEMES.indexOf(cfg.theme) + 1 + THEMES.length) % THEMES.length]; apply(); }
  function toggleFlow() { cfg.flow = cfg.flow === 'paginated' ? 'scrolled-doc' : 'paginated'; apply(); }
  function toggleSpread() { cfg.spread = cfg.spread === 'none' ? 'auto' : 'none'; apply(); }
  function setTheme(t) { if (THEMES.indexOf(t) >= 0) { cfg.theme = t; apply(); } }

  /* ── 面板构建 ─────────────────────────────────────────────── */
  function btn(k, label) { return '<button type="button" data-rd="' + k + '">' + label + '</button>'; }
  function opts(list, val) {
    return list.map(function (o) {
      return '<option value="' + esc(o[0]) + '"' + (String(o[0]) === String(val) ? ' selected' : '') + '>' + esc(o[1]) + '</option>';
    }).join('');
  }
  function selRow(label, key, list) {
    return '<label class="rd-opt"><span>' + label + '</span><select data-k="' + key + '">' + opts(list, cfg[key]) + '</select></label>';
  }
  function buildPanel() {
    panel = document.createElement('div');
    panel.id = 'rdPanel'; panel.hidden = true;
    panel.innerHTML =
      '<div class="rd-row"><span>主题</span><span class="rd-btns">' +
        btn('th-dark', '夜色') + btn('th-cream', '米白') + btn('th-light', '纯白') + btn('th-green', '护眼') +
      '</span></div>' +
      '<div class="rd-row"><span>字号</span><span class="rd-btns">' +
        btn('fs-', 'A−') + btn('fs+', 'A＋') +
        '<button type="button" data-rd="lh-">行距−</button><button type="button" data-rd="lh+">行距＋</button>' +
      '</span></div>' +
      '<div class="rd-row rd-font-row"><span>字体</span>' +
        '<select data-k="font" id="rdFontSel" aria-label="正文字体"><option value="">系统默认</option></select></div>' +
      '<div class="rd-row"><span>版式</span><span class="rd-btns">' +
        '<button type="button" data-rd="spread" id="rdSpreadBtn">双栏阅读</button>' +
        '<button type="button" data-rd="flow" id="rdFlowBtn">滚动阅读</button>' +
      '</span></div>' +

      '<div class="rd-sec">屏幕方向</div>' +
      selRow('屏幕方向', 'orient', [['auto', '自动（感应器）'], ['portrait', '竖屏'], ['landscape', '横屏']]) +
      selRow('摇动手机', 'shake', [['none', '无'], ['next', '向下翻页'], ['prev', '向上翻页']]) +

      '<div class="rd-sec">屏幕触摸事件</div>' +
      '<div class="rd-row"><span>切换为左右模式</span>' +
        '<button type="button" id="rdTapMode" class="rd-switch" aria-label="切换为左右模式"><i></i></button></div>' +
      selRow('点击上面', 'tapTop', TAP_ACTIONS) +
      selRow('点击下面', 'tapBottom', TAP_ACTIONS) +
      selRow('点击左边', 'tapLeft', TAP_ACTIONS) +
      selRow('点击右边', 'tapRight', TAP_ACTIONS) +
      selRow('点击中间', 'tapCenter', TAP_ACTIONS) +
      selRow('长按屏幕', 'longPress', TAP_ACTIONS) +
      '<p class="rd-note">上下模式按屏幕纵向分上/中/下三区；左右模式按横向分左/中/右三区。链接与选中文字不触发翻页。</p>' +

      '<div class="rd-sec">按键</div>' +
      selRow('↑ 上方向键', 'keyUp', ACTIONS) +
      selRow('↓ 下方向键', 'keyDown', ACTIONS) +
      selRow('← 左方向键', 'keyLeft', ACTIONS) +
      selRow('→ 右方向键', 'keyRight', ACTIONS) +
      '<div class="rd-sec">硬件按键</div>' +
      selRow('音量加大键', 'volumeUp', ACTIONS) +
      selRow('音量减小键', 'volumeDown', ACTIONS) +
      selRow('返回键 / Esc', 'keyBack', ACTIONS) +
      selRow('菜单键', 'keyMenu', ACTIONS) +
      '<p class="rd-note">PageUp / PageDown / 空格固定为上/下翻页；音量键需浏览器把按键事件交给网页。</p>' +

      '<div class="rd-speak-box">' +
        '<div class="rd-sp-hd">🎧 听书 <span id="rdSpState">默认 · 晓晓（云端）</span></div>' +
        '<div class="rd-sp-voice">' +
          '<label class="rd-sp-lab">音色<select id="rdSpVoice"></select></label>' +
          '<button type="button" id="rdSpTry" class="rd-sp-try">试听</button>' +
        '</div>' +
        '<div class="rd-sp-chips">' +
          '<button type="button" data-voice="female">女声</button>' +
          '<button type="button" data-voice="male">男声</button>' +
          '<button type="button" data-voice="tw">台湾腔</button>' +
          '<button type="button" data-voice="auto">晓晓</button>' +
        '</div>' +
        '<label class="rd-sp-lab">语速 <span id="rdSpRateVal">1.0×</span>' +
          '<input type="range" id="rdSpRate" min="0.5" max="2" step="0.1"></label>' +
        '<label class="rd-sp-lab">音调 <span id="rdSpPitchVal">1.0</span>' +
          '<input type="range" id="rdSpPitch" min="0.5" max="1.5" step="0.1"></label>' +
        '<label class="rd-sp-lab">音量 <span id="rdSpVolVal">100%</span>' +
          '<input type="range" id="rdSpVol" min="0" max="1" step="0.05"></label>' +
        '<div class="rd-sp-foot">' +
          '<button type="button" id="rdSpMute">🔇 已静音</button>' +
          '<button type="button" id="rdSpStop">⏹ 停止</button>' +
        '</div>' +
        '<p class="rd-sp-hint" id="rdSpHint" hidden></p>' +
        '<p class="rd-sp-tip">点右下角 🎧 从当前页开始连续朗读，读完自动翻页 · 设置自动保存</p>' +
        '<details class="rd-sp-help"><summary>听不出声？</summary>' +
          '<p>默认走云端晓晓（需联网）；云端不可用时回退本机系统语音。' +
          '想换声音可在上方「音色」下拉里挑，或点「试听」先听一句。</p></details>' +
      '</div>';
    document.body.appendChild(panel);
    box = q('.rd-speak-box', panel);

    panel.addEventListener('click', function (e) {
      var b = e.target.closest ? e.target.closest('button[data-rd]') : null;
      if (b) {
        var k = b.getAttribute('data-rd');
        if (k === 'fs-') stepFont(-1);
        else if (k === 'fs+') stepFont(1);
        else if (k === 'lh-') stepLH(-1);
        else if (k === 'lh+') stepLH(1);
        else if (k === 'spread') toggleSpread();
        else if (k === 'flow') toggleFlow();
        else if (k.indexOf('th-') === 0) setTheme(k.slice(3));
        return;
      }
      var sw = e.target.closest ? e.target.closest('#rdTapMode') : null;
      if (sw) { cfg.tapMode = cfg.tapMode === 'vertical' ? 'horizontal' : 'vertical'; apply(); return; }
      var chip = e.target.closest ? e.target.closest('.rd-sp-chips button') : null;
      if (chip) onChip(chip);
    });
    panel.addEventListener('change', function (e) {
      var el = e.target;
      if (!el.matches || !el.matches('select[data-k]')) return;
      var k = el.getAttribute('data-k'), v = el.value;
      cfg[k] = (k === 'rate' || k === 'pitch' || k === 'volume') ? parseFloat(v) : v;
      if (k === 'orient') { applyOrient(true); }
      if (k === 'shake') { enableShake(true); }
      apply();
    });
    /* 滑块即时显示 + 松手后按新参数重读当前块 */
    ['rate', 'pitch', 'volume'].forEach(function (k) {
      var el = q('#rdSp' + ({ rate: 'Rate', pitch: 'Pitch', volume: 'Vol' })[k], panel);
      if (!el) return;
      el.addEventListener('input', function () {
        cfg[k] = parseFloat(el.value); updateLabels(); saveCfg();
      });
      el.addEventListener('change', function () { if (playing) relive(); });
    });
    q('#rdSpVoice', panel).addEventListener('change', function () {
      cfg.voiceURI = this.value || '__auto__';
      activeChip = cfg.voiceURI === '__auto__' ? 'auto' : null;
      saveCfg(); relive(); refresh();
    });
    q('#rdSpTry', panel).addEventListener('click', previewVoice);
    q('#rdSpMute', panel).addEventListener('click', toggleMute);
    q('#rdSpStop', panel).addEventListener('click', function () { stopAll(); hideBar(); });
    panel.addEventListener('click', function (e) { e.stopPropagation(); });
  }

  function buildFab() {
    fab = document.createElement('button');
    fab.id = 'rdFab'; fab.type = 'button'; fab.textContent = 'Aa';
    fab.title = '阅读设置'; fab.setAttribute('aria-label', '阅读设置');
    fab.onclick = function (e) { e.stopPropagation(); togglePanel(); };
    document.body.appendChild(fab);
    speakFab = document.createElement('button');
    speakFab.id = 'rdSpeakFab'; speakFab.type = 'button'; speakFab.textContent = '🎧';
    speakFab.title = '听书：从当前页开始'; speakFab.setAttribute('aria-label', '听书');
    speakFab.onclick = function (e) { e.stopPropagation(); toggleSpeak(); };
    document.body.appendChild(speakFab);
  }
  function buildBar() {
    bar = document.createElement('div');
    bar.id = 'rdSpeakBar'; bar.hidden = true;
    bar.setAttribute('role', 'group'); bar.setAttribute('aria-label', '听书控制');
    bar.innerHTML =
      '<span class="rd-sb-txt" id="rdSbTxt"></span>' +
      '<button type="button" id="rdSbPause" aria-label="暂停">⏸</button>' +
      '<button type="button" id="rdSbStop" aria-label="停止">⏹</button>' +
      '<button type="button" id="rdSbMute" aria-label="静音">🔇</button>' +
      '<button type="button" id="rdSbSet" aria-label="听书设置">⚙</button>';
    document.body.appendChild(bar);
    bar.addEventListener('click', function (e) { e.stopPropagation(); });
    q('#rdSbPause', bar).onclick = function () { if (playing) togglePause(); else toggleSpeak(); };
    q('#rdSbStop', bar).onclick = function () { stopAll(); hideBar(); };
    q('#rdSbMute', bar).onclick = toggleMute;
    q('#rdSbSet', bar).onclick = function () { togglePanel(true); };
  }
  function togglePanel(force) {
    panel.hidden = force === true ? false : !panel.hidden;
    fab.classList.toggle('on', !panel.hidden);
    if (!panel.hidden) { fillVoices(); loadFonts(); refresh(); }
  }
  function updateLabels() {
    var set = function (id, v) { var el = q(id, panel); if (el) el.textContent = v; };
    set('#rdSpRateVal', cfg.rate.toFixed(1) + '×');
    set('#rdSpPitchVal', cfg.pitch.toFixed(1));
    set('#rdSpVolVal', Math.round(cfg.volume * 100) + '%');
    var r = q('#rdSpRate', panel), p = q('#rdSpPitch', panel), v = q('#rdSpVol', panel);
    if (r) r.value = cfg.rate; if (p) p.value = cfg.pitch; if (v) v.value = cfg.volume;
  }
  function refresh() {
    if (!panel) return;
    qa('button[data-rd^="th-"]', panel).forEach(function (b) {
      b.classList.toggle('on', b.getAttribute('data-rd') === 'th-' + cfg.theme);
    });
    qa('#rdSpreadBtn,#rdFlowBtn', panel).forEach(function (b) {
      var k = b.id === 'rdSpreadBtn' ? 'spread' : 'flow';
      b.classList.toggle('on', k === 'spread' ? cfg.spread !== 'none' : cfg.flow !== 'paginated');
    });
    var sw = q('#rdTapMode', panel);
    if (sw) sw.classList.toggle('on', cfg.tapMode === 'horizontal');
    var st = q('#rdSpState', panel);
    if (st) st.textContent = playing ? (usingLocal() ? '本机语音朗读中…' : '云端语音朗读中…')
      : (cfg.voiceURI === '__auto__' ? '默认 · 晓晓（云端）' : '已选音色');
    var mb = q('#rdSpMute', panel); if (mb) mb.textContent = muted ? '🔇 已静音' : '🔊 有声';
    var bm = q('#rdSbMute', bar); if (bm) bm.textContent = muted ? '🔇' : '🔊';
    var bp = q('#rdSbPause', bar); if (bp) bp.textContent = playing && !paused ? '⏸' : '▶';
    if (speakFab) speakFab.classList.toggle('on', playing);
    qa('.rd-sp-chips button', panel).forEach(function (b) {
      b.classList.toggle('on', b.getAttribute('data-voice') === activeChip);
    });
    updateLabels();
  }

  /* ── 字体：沿用详情页 fonts.json 清单，按需加载 ─────────────── */
  var fontLoaded = false, fontLoading = false;
  function loadFonts() {
    if (fontLoaded || fontLoading) return;
    fontLoading = true;
    fetch(FONT_JSON).then(function (r) { if (!r.ok) throw 0; return r.json(); })
      .then(function (j) {
        fonts = (j && j.fonts) || [];
        var sel = q('#rdFontSel', panel), html = '<option value="">系统默认</option>' +
          '<optgroup label="系统字体">' +
          '<option value="sys:serif">宋体 / 衬线</option>' +
          '<option value="sys:sans">黑体 / 无衬线</option>' +
          '<option value="sys:kai">楷体</option>' +
          '<option value="sys:mono">等宽</option></optgroup>' +
          '<optgroup label="站内字体（首次选中才下载）">';
        fonts.forEach(function (f) {
          html += '<option value="' + esc(f.file) + '">' + esc(f.name) +
            (f.bytes ? '（' + (f.bytes / 1048576).toFixed(1) + ' MB）' : '') + '</option>';
        });
        html += '</optgroup>';
        sel.innerHTML = html; sel.value = cfg.font;
        fontLoaded = true;
      })
      .catch(function () { var s = q('#rdFontSel', panel); if (s) s.disabled = true; })
      .then(function () { fontLoading = false; });
  }
  function fontFamily() {
    var f = cfg.font;
    if (!f) return '';
    if (f === 'sys:serif') return '"Noto Serif CJK SC","Songti SC",SimSun,serif';
    if (f === 'sys:sans') return '"PingFang SC","Microsoft YaHei",sans-serif';
    if (f === 'sys:kai') return 'KaiTi,"Kaiti SC",STKaiti,serif';
    if (f === 'sys:mono') return 'Consolas,"Courier New",monospace';
    return '"RD-UserFont","Noto Serif CJK SC","Songti SC",serif';
  }
  function fontFaceRule() {
    if (!cfg.font || cfg.font.indexOf('sys:') === 0) return '';
    return '@font-face{font-family:"RD-UserFont";src:url("' + FONT_DIR + encodeURIComponent(cfg.font) +
      '") format("woff2");font-display:swap;font-weight:100 900;font-style:normal;}';
  }
  function hint(msg, warn) {
    var h = q('#rdSpHint', panel); if (!h) return;
    h.textContent = msg || ''; h.hidden = !msg; h.classList.toggle('warn', !!warn);
  }

  /* ── 屏幕方向 ─────────────────────────────────────────────── */
  function syncRotate() {
    if (!document.documentElement) return;
    var isLand = window.innerWidth > window.innerHeight;
    var need = !nativeLocked && cfg.orient !== 'auto' &&
      ((cfg.orient === 'landscape' && !isLand) || (cfg.orient === 'portrait' && isLand));
    document.documentElement.classList.toggle('aa-rotate', !!need);
    if (H.resize) setTimeout(function () { H.resize(); }, 220);
  }
  function applyOrient(user) {
    var so = screen.orientation || screen.mozOrientation || screen.msOrientation;
    nativeLocked = false;
    if (cfg.orient === 'auto') {
      try { if (so && so.unlock) so.unlock(); } catch (e) {}
      try { if (document.fullscreenElement && document.exitFullscreen) document.exitFullscreen(); } catch (e) {}
      syncRotate(); return;
    }
    if (!user) { syncRotate(); return; }   // 初始化没有用户手势，不弹全屏
    var type = cfg.orient === 'portrait' ? 'portrait' : 'landscape';
    var el = document.documentElement, p;
    try {
      p = (el.requestFullscreen && !document.fullscreenElement)
        ? Promise.resolve(el.requestFullscreen()) : Promise.resolve();
    } catch (e) { p = Promise.resolve(); }
    Promise.resolve(p).catch(function () {}).then(function () {
      if (so && so.lock) return Promise.resolve(so.lock(type));
      throw 0;
    }).then(function () {
      nativeLocked = true; syncRotate();
      notify('已锁定' + (type === 'portrait' ? '竖屏' : '横屏'));
    }).catch(function () {
      syncRotate();
      notify('浏览器不支持方向锁定，已用页面旋转兜底');
    });
  }

  /* ── 摇动手机（DeviceMotion，iOS 首次需授权） ──────────────── */
  function onMotion(e) {
    if (cfg.shake === 'none') return;
    var a = e.accelerationIncludingGravity || e.acceleration;
    if (!a) return;
    var m = Math.sqrt((a.x || 0) * (a.x || 0) + (a.y || 0) * (a.y || 0) + (a.z || 0) * (a.z || 0));
    if (lastAcc !== null && Math.abs(m - lastAcc) > 18 && Date.now() - lastShake > 1500) {
      lastShake = Date.now(); act(cfg.shake);
    }
    lastAcc = m;
  }
  function enableShake(user) {
    if (cfg.shake === 'none') { if (motionBound) window.removeEventListener('devicemotion', onMotion); motionBound = false; return; }
    var start = function () {
      if (motionBound) return;
      window.addEventListener('devicemotion', onMotion); motionBound = true;
    };
    if (user && window.DeviceMotionEvent && window.DeviceMotionEvent.requestPermission) {
      Promise.resolve(window.DeviceMotionEvent.requestPermission()).then(function (s) {
        if (s === 'granted') start(); else notify('摇一摇需要授权动作与方向权限');
      }).catch(function () { notify('摇一摇需要授权动作与方向权限'); });
    } else start();
  }

  /* ── 动作派发 ─────────────────────────────────────────────── */
  function act(name, e) {
    if (!name || name === 'none') return;
    switch (name) {
      case 'prev': case 'next': if (H.page) H.page(name === 'next' ? 1 : -1); break;
      case 'prevChapter': case 'nextChapter': if (H.chapter) H.chapter(name === 'nextChapter' ? 1 : -1); break;
      case 'settings': togglePanel(true); break;
      case 'speak': toggleSpeak(); break;
      case 'copy': copyAt(e); break;
      case 'back': if (H.back) H.back(); break;
    }
  }
  function copyAt(e) {
    var t = e && e.target, el = null;
    if (t && t.closest) el = t.closest('p, li, blockquote, section.page, div, h2, h3');
    var txt = el ? String(el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim() : '';
    if (!txt) { notify('这里没有可摘录的文字'); return; }
    var done = function () { notify('已摘录本段（' + txt.length + ' 字）'); };
    var fallback = function () {
      try {
        var ta = document.createElement('textarea'); ta.value = txt;
        ta.style.position = 'fixed'; ta.style.opacity = '0';
        document.body.appendChild(ta); ta.select(); document.execCommand('copy');
        document.body.removeChild(ta);
      } catch (err) {}
      done();
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(txt).then(done, fallback);
    } else fallback();
  }

  /* ── 区域点击 / 长按 ──────────────────────────────────────── */
  function pt(e) {
    if (e.touches && e.touches.length) return { x: e.touches[0].clientX, y: e.touches[0].clientY };
    if (e.changedTouches && e.changedTouches.length) return { x: e.changedTouches[0].clientX, y: e.changedTouches[0].clientY };
    return { x: e.clientX || 0, y: e.clientY || 0 };
  }
  function zoneOf(e) {
    var p = pt(e), w = e.view, W = (w && w.innerWidth) || window.innerWidth,
        Hh = (w && w.innerHeight) || window.innerHeight;
    if (cfg.tapMode === 'horizontal') {
      if (p.x < W * 0.32) return 'left';
      if (p.x > W * 0.68) return 'right';
      return 'center';
    }
    if (p.y < Hh * 0.34) return 'top';
    if (p.y > Hh * 0.66) return 'bottom';
    return 'center';
  }
  function handleTap(e) {
    if (Date.now() < suppressClickUntil) return;
    if (e && e.defaultPrevented) return;
    var t = e.target;
    if (t && t.closest && t.closest('a, button, input, select, textarea')) return;
    try {
      var s = e.view && e.view.getSelection && String(e.view.getSelection());
      if (s && s.trim().length > 1) return;
    } catch (err) {}
    var z = zoneOf(e), key = { top: 'tapTop', bottom: 'tapBottom', left: 'tapLeft', right: 'tapRight', center: 'tapCenter' }[z];
    act(cfg[key], e);
  }
  function cancelPress() { if (pressTimer) clearTimeout(pressTimer); pressTimer = null; press = null; }
  function startPress(e) {
    if (cfg.longPress === 'none') return;
    cancelPress();
    var p = pt(e); press = { x: p.x, y: p.y };
    var ev = e;
    pressTimer = setTimeout(function () {
      suppressClickUntil = Date.now() + 800;
      act(cfg.longPress, ev);
      press = null; pressTimer = null;
    }, 560);
  }
  function movePress(e) {
    if (!press) return;
    var p = pt(e);
    if (Math.abs(p.x - press.x) > 12 || Math.abs(p.y - press.y) > 12) cancelPress();
  }
  function onKey(e) {
    var t = e.target, tag = t && t.tagName ? t.tagName.toUpperCase() : '';
    if (/INPUT|TEXTAREA|SELECT/.test(tag) || (t && t.isContentEditable)) return;
    var k = e.key;
    if (k === '/') { if (H.focusSearch) { H.focusSearch(); e.preventDefault(); } return; }
    if (k === 'Escape') {
      if (H.escape && H.escape()) { e.preventDefault(); return; }
      if (panel && !panel.hidden) { panel.hidden = true; fab.classList.remove('on'); e.preventDefault(); return; }
      act(cfg.keyBack, e); e.preventDefault(); return;
    }
    var name = null;
    if (k === 'ArrowUp') name = cfg.keyUp;
    else if (k === 'ArrowDown') name = cfg.keyDown;
    else if (k === 'ArrowLeft') name = cfg.keyLeft;
    else if (k === 'ArrowRight') name = cfg.keyRight;
    else if (k === 'PageUp') name = 'prev';
    else if (k === 'PageDown' || k === ' ' || k === 'Spacebar') name = 'next';
    else if (k === 'AudioVolumeUp' || k === 'VolumeUp') name = cfg.volumeUp;
    else if (k === 'AudioVolumeDown' || k === 'VolumeDown') name = cfg.volumeDown;
    else if (k === 'Menu' || k === 'ContextMenu') name = cfg.keyMenu;
    if (name && name !== 'none') { act(name, e); e.preventDefault(); }
  }
  function bindFrame(rend) {
    if (!rend) return;
    /* epub.js 自带的事件转发是 passive:true，preventDefault 会被忽略，
       方向键会连同 iframe 默认滚动一起翻两页。这里给每个新章节直接挂
       一个非 passive 的 keydown，按键才拦得住。 */
    if (rend.hooks && rend.hooks.content && rend.hooks.content.register) {
      rend.hooks.content.register(function (contents) {
        try { contents.document.addEventListener('keydown', onKey, false); } catch (e) {}
      });
    }
    if (!rend.on) return;
    var types = ['click', 'touchstart', 'touchmove', 'touchend', 'touchcancel',
                 'mousedown', 'mousemove', 'mouseup'];
    types.forEach(function (type) {
      rend.on(type, function (e) {
        switch (type) {
          case 'click': handleTap(e); break;
          case 'touchstart': case 'mousedown': startPress(e); break;
          case 'touchmove': case 'mousemove': movePress(e); break;
          case 'touchend': case 'touchcancel': case 'mouseup': cancelPress(); break;
        }
      });
    });
  }

  /* ── 听书（详情同款云端晓晓 + 本机 Web Speech 兜底） ─────────── */
  var hasTTS = ('speechSynthesis' in window) && typeof window.SpeechSynthesisUtterance !== 'undefined';
  var synth = hasTTS ? window.speechSynthesis : null;
  var audio = null, objUrl = null, ttsSeq = 0, localSeq = 0;
  var queue = [], qi = -1, playing = false, paused = false, muted = true;
  var waitingPage = false, lastFirst = '', preIdx = -1, preBlob = null, utter = null;

  function isCloud(u) { return /Neural$/.test(u || ''); }
  function cloudLabel(u) {
    for (var i = 0; i < CLOUD.length; i++) if (CLOUD[i].uri === u) return CLOUD[i].label;
    return '';
  }
  function localVoices() { return (hasTTS && synth.getVoices) ? (synth.getVoices() || []) : []; }
  function usingLocal() {
    if (isCloud(cfg.voiceURI)) return false;
    if (cfg.voiceURI === '__auto__') return false;   // 默认项固定云端晓晓
    return hasTTS && localVoices().length > 0;
  }
  function pickVoice() { return isCloud(cfg.voiceURI) ? cfg.voiceURI : CLOUD[0].uri; }
  function rateStr() { var p = Math.round((cfg.rate - 1) * 100); return (p >= 0 ? '+' : '') + p + '%'; }
  function ttsFetch(txt, voice) {
    return fetch(TTS_BASE.replace(/[?&]$/, ''), {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: txt, voice: voice || pickVoice(), rate: rateStr() })
    }).then(function (r) { if (!r.ok) throw new Error('tts ' + r.status); return r.blob(); });
  }
  function fillVoices() {
    var sel = q('#rdSpVoice', panel); if (!sel) return;
    var html = '<option value="__auto__">默认 · 晓晓（云端）</option>';
    CLOUD.slice(1).forEach(function (v) {
      html += '<option value="' + v.uri + '">' + esc(v.label) + '</option>';
    });
    localVoices().forEach(function (v) {
      if (!/zh|cmn/i.test((v.lang || '') + (v.name || ''))) return;
      html += '<option value="' + esc(v.voiceURI || v.name) + '">本机 · ' + esc(v.name) + '</option>';
    });
    sel.innerHTML = html; sel.value = cfg.voiceURI;
    if (!sel.value) { sel.value = '__auto__'; cfg.voiceURI = '__auto__'; }
  }
  function onChip(b) {
    var kind = b.getAttribute('data-voice');
    activeChip = kind;
    cfg.voiceURI = kind === 'auto' ? '__auto__'
      : kind === 'female' ? CLOUD[1].uri
      : kind === 'male' ? CLOUD[2].uri : CLOUD[3].uri;
    var sel = q('#rdSpVoice', panel); if (sel) sel.value = cfg.voiceURI;
    saveCfg(); relive(); refresh();
  }
  function previewVoice() {
    var txt = '这是当前音色的试听，听着顺耳就用它。';
    stopAll(); hint('合成中…');
    var uri = cfg.voiceURI;
    if (!isCloud(uri) && uri !== '__auto__' && hasTTS) {
      var lv = localVoices().filter(function (v) { return (v.voiceURI || v.name) === uri; })[0];
      if (lv) {
        try {
          var u = new window.SpeechSynthesisUtterance(txt);
          u.lang = lv.lang || 'zh-CN'; try { u.voice = lv; } catch (e2) {}
          u.rate = cfg.rate; u.pitch = cfg.pitch; u.volume = cfg.volume;
          synth.speak(u); hint('试听：本机 ' + (lv.name || lv.lang)); return;
        } catch (e) {}
      }
    }
    ttsFetch(txt, isCloud(uri) ? uri : CLOUD[0].uri).then(function (b) {
      setAudioSrc(b); var p = ensureAudio().play(); if (p && p.catch) p.catch(function () {});
      hint('试听：' + (cloudLabel(isCloud(uri) ? uri : CLOUD[0].uri) || '晓晓'));
    }).catch(function () { hint('试听失败，检查网络后重试', true); });
  }
  function ensureAudio() {
    if (audio) return audio;
    audio = new Audio(); audio.preload = 'auto';
    audio.addEventListener('ended', function () { if (playing) nextChunk(); });
    audio.addEventListener('error', function () { if (playing) { fallbackLocal(); } });
    return audio;
  }
  function setAudioSrc(blob) {
    var a = ensureAudio();
    if (objUrl) { try { URL.revokeObjectURL(objUrl); } catch (e) {} }
    objUrl = URL.createObjectURL(blob); a.src = objUrl;
  }
  function showBar(txt, warn) {
    var t = q('#rdSbTxt', bar); if (t) t.textContent = txt || '';
    bar.classList.toggle('rd-sb-warn', !!warn); bar.hidden = false; refresh();
  }
  function hideBar() { if (bar) bar.hidden = true; refresh(); }

  /* 把当前可见页的段落切成 ≤240 字的朗读块，标点处断句 */
  function chunksOf(items) {
    var out = [];
    (items || []).forEach(function (it) {
      var t = String(it.text || '').replace(/\s+/g, ' ').trim();
      if (t.length < 2) return;
      var parts = t.match(/[^。！？；，,.!?;]+[。！？；，,.!?;]?/g) || [t], buf = '';
      parts.forEach(function (s) {
        while (s.length > 240) {
          if (buf) { out.push({ text: buf, el: it.el }); buf = ''; }
          out.push({ text: s.slice(0, 240), el: it.el }); s = s.slice(240);
        }
        if (buf.length + s.length > 240) { out.push({ text: buf, el: it.el }); buf = ''; }
        buf += s;
      });
      if (buf.trim()) out.push({ text: buf.trim(), el: it.el });
    });
    return out;
  }
  function fallbackLocal() {
    if (!hasTTS || !localVoices().length) { nextChunk(); return; }
    var it = queue[qi]; if (!it) { nextChunk(); return; }
    playLocal(it.text);
  }
  function playQueue(items) {
    stopAll();
    if (!items || !items.length) { notify('本页没有可朗读的文字'); return; }
    queue = items; qi = 0; playing = true; paused = false; muted = false;
    lastFirst = items[0].text;
    runChunk();
  }
  function runChunk() {
    if (!playing) return;
    if (qi >= queue.length) { autoNextPage(); return; }
    var it = queue[qi];
    if (H.highlight) H.highlight(it.el);
    showBar('朗读中 · 第 ' + (qi + 1) + '/' + queue.length + ' 段');
    if (usingLocal()) playLocal(it.text);
    else playServer(it.text);
  }
  function playLocal(txt) {
    if (!synth) { nextChunk(); return; }
    var my = ++localSeq;
    var u = new window.SpeechSynthesisUtterance(txt);
    var lv = localVoices().filter(function (v) { return (v.voiceURI || v.name) === cfg.voiceURI; })[0];
    try { u.lang = (lv && lv.lang) || 'zh-CN'; if (lv) u.voice = lv; } catch (e) { u.lang = 'zh-CN'; }
    u.rate = cfg.rate; u.pitch = cfg.pitch; u.volume = muted ? 0 : cfg.volume;
    u.onend = function () { if (my === localSeq) nextChunk(); };
    u.onerror = function () { if (my === localSeq) nextChunk(); };
    utter = u;
    try { synth.speak(u); } catch (e) { nextChunk(); }
  }
  function playServer(txt) {
    var my = ++ttsSeq, blob = null;
    if (preIdx === qi && preBlob) { blob = preBlob; preIdx = -1; preBlob = null; }
    if (blob) { startAudio(blob, my); return; }
    showBar('合成中…');
    ttsFetch(txt).then(function (b) { if (my === ttsSeq && playing) startAudio(b, my); })
      .catch(function () {
        if (my !== ttsSeq || !playing) return;
        if (qi === 0) { stopAll(); showBar('语音服务暂时不可用，请稍后再试', true); setTimeout(hideBar, 3200); }
        else fallbackLocal();
      });
  }
  function startAudio(blob, my) {
    setAudioSrc(blob);
    if (my !== ttsSeq) return;
    showBar('朗读中 · 第 ' + (qi + 1) + '/' + queue.length + ' 段');
    ensureAudio().volume = muted ? 0 : cfg.volume;
    if (!paused) { var p = ensureAudio().play(); if (p && p.catch) p.catch(function () {}); }
    prefetch();
  }
  function prefetch() {
    var j = qi + 1;
    if (j >= queue.length || preIdx === j || usingLocal()) return;
    var my = ttsSeq; preIdx = j;
    ttsFetch(queue[j].text).then(function (b) { if (my === ttsSeq && preIdx === j) preBlob = b; })
      .catch(function () { if (preIdx === j) { preIdx = -1; preBlob = null; } });
  }
  function nextChunk() { if (!playing) return; qi++; runChunk(); }
  function autoNextPage() {
    if (!playing || waitingPage) return;
    waitingPage = true;
    showBar('本页读完，正在翻页…');
    if (H.page) H.page(1);
    setTimeout(function () { if (waitingPage) refill(); }, 1400);
  }
  function refill() {
    if (!playing) return;
    waitingPage = false;
    var items = H.pageText ? H.pageText() : [], chunks = chunksOf(items);
    if (!chunks.length || (chunks[0] && chunks[0].text === lastFirst)) {
      stopAll(); showBar('已读到章节末，听书结束'); setTimeout(hideBar, 2600); return;
    }
    lastFirst = chunks[0].text; queue = chunks; qi = 0; runChunk();
  }
  function toggleSpeak() {
    if (playing) { stopAll(); hideBar(); return; }
    var items = H.pageText ? H.pageText() : [], chunks = chunksOf(items);
    if (!chunks.length && H.page) { H.page(1); setTimeout(function () {
      if (!playing) { var c2 = chunksOf(H.pageText ? H.pageText() : []); playQueue(c2); }
    }, 500); return; }
    playQueue(chunks);
  }
  function togglePause() {
    if (!playing) return;
    paused = !paused;
    if (usingLocal() && synth) { try { paused ? synth.pause() : synth.resume(); } catch (e) {} }
    if (audio) { try { paused ? audio.pause() : audio.play(); } catch (e) {} }
    showBar(paused ? '已暂停' : '朗读中'); refresh();
  }
  function toggleMute() {
    muted = !muted;
    if (utter) utter.volume = muted ? 0 : cfg.volume;
    if (audio) audio.volume = muted ? 0 : cfg.volume;
    refresh();
  }
  function relive() {
    if (playing && queue[qi]) {
      var it = queue[qi];
      playQueue([it]);      // 参数变了，重读当前段立即生效
    } else refresh();
  }
  function stopAll() {
    if (synth) { try { synth.cancel(); } catch (e) {} }
    localSeq++; ttsSeq++;
    if (audio) { try { audio.pause(); audio.removeAttribute('src'); } catch (e) {} }
    if (objUrl) { try { URL.revokeObjectURL(objUrl); } catch (e) {} objUrl = null; }
    playing = false; paused = false; waitingPage = false; queue = []; qi = -1;
    utter = null; preIdx = -1; preBlob = null;
    if (H.highlight) H.highlight(null);
    refresh();
  }

  /* ── 初始化 ───────────────────────────────────────────────── */
  function init(hooks) {
    H = hooks || {};
    cfg.rate = num(cfg.rate, 0.5, 2, 1);
    cfg.pitch = num(cfg.pitch, 0.5, 1.5, 1);
    cfg.volume = num(cfg.volume, 0, 1, 1);
    buildFab(); buildPanel(); buildBar();
    document.addEventListener('keydown', onKey);
    document.addEventListener('click', function (e) {
      if (!panel || panel.hidden) return;
      if (panel.contains(e.target) || e.target === fab || e.target === speakFab ||
          (bar && bar.contains(e.target))) return;
      panel.hidden = true; fab.classList.remove('on');
    });
    window.addEventListener('resize', syncRotate);
    window.addEventListener('orientationchange', function () {
      syncRotate(); setTimeout(function () { if (H.resize) H.resize(); }, 350);
    });
    window.addEventListener('beforeunload', stopAll);
    if (H.onRelocated) H.onRelocated(function () { if (waitingPage) refill(); });
    if (hasTTS && synth && 'onvoiceschanged' in synth) {
      synth.onvoiceschanged = function () { if (panel && !panel.hidden) fillVoices(); };
    }
    if (cfg.shake !== 'none') enableShake(false);
    applyOrient(false);
    fillVoices();
    apply(false);
    return api;
  }

  var api = {
    init: init,
    bindFrame: bindFrame,
    cfg: function () { return cfg; },
    fontFamily: fontFamily,
    fontFaceRule: fontFaceRule,
    reapply: function () { if (H.onCfg) H.onCfg(cfg); },
    stepFont: stepFont,
    cycleTheme: cycleTheme,
    toggleFlow: toggleFlow,
    togglePanel: togglePanel,
    theme: setTheme,
    pageText: function () { return H.pageText ? H.pageText() : []; },
    notify: notify,
    onRelocated: function () { if (waitingPage) refill(); }
  };
  window.EpubAA = api;
})();
