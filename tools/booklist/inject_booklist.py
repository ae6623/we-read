#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""幂等注入「书单」tab 到 we-read 首页 index.html（CDN 双写版）。

设计要点（沿用站内既有约定，最小改动）：
- 外部 homepage-reading.js 通用扫描 button[data-panel] + 同名 id 的 panel，
  因此只需「一个 tab 按钮 + 一个 section」，不用改 CDN 上的 JS，也不刷缓存。
- 全部内联（style / HTML / JS），不新建文件、不引外部依赖，跟着 index.html 走。
- 用 <!-- booklist:begin/end --> 标记包裹，重复执行先移除旧块再注入（幂等）。
- git 仓 index.html 是源、reader.js-dev.cn 读七牛 Kodo 产物，两份都要注入。
- 书目 URL 取 booklist_paths.json 每本的 u 字段；由 booklist_factory.py sync
  按线上探测回填「combined.html（最新全书领读页）优先，overview.html 回退」，
  缺省才回退旧 overview。不要再写死 overview.html（2026-11-11 修复）。
  封面沿用 https://cdn.js-dev.cn/assets/covers/<slug>.jpg + 占位降级（与「已阅」一致）。
- 点击书名会触发「已阅」的 capture 阶段记录，天然打通最近打开。

用法:
  python3 inject_booklist.py --file /path/to/index.html            # 注入/更新
  python3 inject_booklist.py --file /path/to/index.html --check    # 只看会改什么
  python3 inject_booklist.py --file /path/to/index.html --remove   # 移除书单块
"""
import argparse
import hashlib
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "booklist_paths.json")

BEGIN = "<!-- booklist:begin -->"
END = "<!-- booklist:end -->"

LEVELS = {
    "start": ("入门", "零基础起步"),
    "gen": ("通识", "搭完整脉络"),
    "adv": ("进阶", "已有基础往深走"),
}

# 与「已阅」rd-recent 相同的封面占位配色
COVER_HUES = [162, 186, 205, 28, 36, 12, 258, 340]


def hue(slug):
    n = 0
    for ch in slug:
        n = (n * 31 + ord(ch)) % 9973
    return COVER_HUES[n % len(COVER_HUES)]


def short_title(title):
    t = re.sub(r"^[\s《〈“\"'「【·—-]+", "", title or "")
    return (t[:2] or "阅")


def esc(s):
    return html.escape(s or "", quote=True)


def build_css():
    return """<style id="rd-booklist-style">
/* 书单 · 按领域走的读书路径（2026-11-11 新增，完全内联、零外部依赖）
   沿用 Aa / 已阅 面板的主题变量（--card/--ink/--muted/--line/--sage/--green），
   四套主题 cream/light/green/dark 自动适配；封面沿用 assets/covers/<slug>.jpg 约定。 */
#reading-panel-booklist .bl-head{margin:2px 0 18px}
#reading-panel-booklist .bl-head h2{font:700 1.18rem/1.45 var(--serif);color:var(--ink);margin:0 0 7px}
#reading-panel-booklist .bl-head p{font-size:.82rem;line-height:1.75;color:var(--muted);margin:0 0 6px;max-width:56em}
#reading-panel-booklist .bl-head .bl-hint{font-size:.74rem;color:var(--muted)}
#reading-panel-booklist .bl-filters{display:flex;flex-wrap:wrap;gap:7px;margin:0 0 18px;padding:0;list-style:none}
#reading-panel-booklist .bl-filter{font:600 .76rem/1.4 var(--sans);color:var(--muted);background:transparent;
  border:1px solid var(--line);border-radius:999px;padding:5px 13px;cursor:pointer;transition:.15s}
#reading-panel-booklist .bl-filter:hover{border-color:var(--green);color:var(--green)}
#reading-panel-booklist .bl-filter[aria-pressed="true"]{background:var(--green);border-color:var(--green);color:#fff}
#reading-panel-booklist .bl-filter .bl-fn{opacity:.7;font-weight:400;margin-left:3px}
#reading-panel-booklist .bl-paths{display:flex;flex-direction:column;gap:16px}
#reading-panel-booklist .bl-path{background:var(--card);border:1px solid var(--line);border-radius:14px;
  padding:16px 17px 14px;box-shadow:0 3px 12px rgba(var(--shadow),.06)}
#reading-panel-booklist .bl-path[hidden]{display:none!important}
#reading-panel-booklist .bl-path-head{display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:8px}
#reading-panel-booklist .bl-field{flex:none;font:600 .7rem/1 var(--sans);letter-spacing:.04em;
  color:var(--green);border:1px solid var(--green);border-radius:5px;padding:4px 7px}
#reading-panel-booklist .bl-level{flex:none;font:600 .7rem/1 var(--sans);border-radius:5px;padding:4px 8px;color:#fff}
#reading-panel-booklist .bl-level[data-lv="start"]{background:#4c8d6c}
#reading-panel-booklist .bl-level[data-lv="gen"]{background:#5b7ea8}
#reading-panel-booklist .bl-level[data-lv="adv"]{background:#a8763f}
#reading-panel-booklist .bl-meta{flex:none;font:.7rem/1 var(--sans);color:var(--muted)}
#reading-panel-booklist .bl-title{font:700 1rem/1.45 var(--serif);color:var(--ink);margin:0 0 9px}
#reading-panel-booklist .bl-goal{background:var(--sage);border-left:3px solid var(--green);border-radius:0 8px 8px 0;
  padding:9px 12px;margin:0 0 14px;font-size:.79rem;line-height:1.65;color:var(--ink)}
#reading-panel-booklist .bl-goal b{color:var(--green);font-weight:700}
#reading-panel-booklist .bl-stages{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
#reading-panel-booklist .bl-stage{position:relative;min-width:0;background:transparent;
  border:1px solid var(--line);border-radius:10px;padding:11px 11px 10px}
#reading-panel-booklist .bl-stage + .bl-stage::before{content:"→";position:absolute;left:-13px;top:14px;
  z-index:1;font:700 .9rem var(--sans);color:var(--green);opacity:.6}
#reading-panel-booklist .bl-step{display:flex;align-items:flex-start;gap:7px;margin-bottom:9px}
#reading-panel-booklist .bl-step-n{flex:none;width:20px;height:20px;border-radius:50%;background:var(--green);
  color:#fff;font:700 .72rem/20px var(--sans);text-align:center}
#reading-panel-booklist .bl-step-tx{min-width:0}
#reading-panel-booklist .bl-step-name{font:700 .79rem/1.4 var(--sans);color:var(--ink);margin:0}
#reading-panel-booklist .bl-step-aim{font:.69rem/1.5 var(--sans);color:var(--muted);margin:2px 0 0}
#reading-panel-booklist .bl-tip{font:.68rem/1.55 var(--sans);color:var(--muted);background:var(--sage);
  border-radius:6px;padding:6px 8px;margin:0 0 9px}
#reading-panel-booklist .bl-tip b{color:var(--green);font-weight:700}
#reading-panel-booklist .bl-books{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px}
#reading-panel-booklist .bl-book{margin:0;min-width:0}
#reading-panel-booklist .bl-book a{display:flex;align-items:center;gap:8px;padding:5px;border-radius:8px;
  text-decoration:none;color:var(--ink)}
#reading-panel-booklist .bl-book a:hover,#reading-panel-booklist .bl-book a:focus-visible{background:var(--sage)}
#reading-panel-booklist .bl-cover{position:relative;flex:none;width:32px;height:44px;border-radius:3px;overflow:hidden;
  background:linear-gradient(158deg,hsl(var(--cv-h,166) 27% 24%) 0%,hsl(calc(var(--cv-h,166) + 16) 33% 11%) 100%);
  box-shadow:0 1px 3px rgba(0,0,0,.16)}
#reading-panel-booklist .bl-cover img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:block}
#reading-panel-booklist .bl-cover-ph{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
  padding:2px;color:rgba(255,255,255,.92);font:600 .7rem/1.15 var(--serif);letter-spacing:.02em;
  text-align:center;pointer-events:none}
#reading-panel-booklist .bl-book.has-img .bl-cover-ph{display:none}
#reading-panel-booklist .bl-book-meta{min-width:0;display:flex;flex-direction:column;gap:2px}
#reading-panel-booklist .bl-book-t{font:600 .75rem/1.35 var(--sans);word-break:break-all;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
#reading-panel-booklist .bl-book-w{font:.66rem/1.4 var(--sans);color:var(--muted);
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
#reading-panel-booklist .bl-foot{margin:16px 2px 0;font:.71rem/1.7 var(--sans);color:var(--muted)}
@media(max-width:760px){
  #reading-panel-booklist .bl-stages{grid-template-columns:1fr;gap:10px}
  #reading-panel-booklist .bl-stage + .bl-stage::before{content:"↓";left:auto;right:14px;top:-15px}
}
</style>"""


def build_tab_button():
    # 紧跟「归档」之后，与既有三个 tab 同级
    return ('<button type="button" id="reading-tab-booklist" data-panel="reading-panel-booklist" '
            'aria-label="书单 · 按领域走的读书路径">书单</button>')


def build_panel(paths):
    counts = {"all": len(paths)}
    for k in LEVELS:
        counts[k] = sum(1 for p in paths if p["levelKey"] == k)

    out = []
    out.append('<section id="reading-panel-booklist" class="reading-panel" aria-label="书单">')
    out.append('<div class="bl-head">')
    out.append('<h2>书单 · 按领域走的读书路径</h2>')
    out.append('<p>想弄懂一个领域，最怕打开 App 看排名随手点一本，读完还是零散的。这里把每个领域'
               '拆成「第一步 → 第二步 → 第三步」，每步一到几本、整条 10 本左右，'
               '先建框架再看公司／事件，最后收口成自己的判断。每条路径开头都写明'
               '<b>读完你能到什么程度</b>，按自己的起点挑一条即可。</p>')
    out.append('<p class="bl-hint">书名可直接点进本书笔记页（优先最新版全书领读）；封面缺失时显示书名占位。'
               '程度：<b>入门</b> 零基础起步 · <b>通识</b> 搭完整脉络 · <b>进阶</b> 已有基础往深走。</p>')
    out.append('</div>')

    out.append('<ul class="bl-filters" role="group" aria-label="按程度筛选书单">')
    labels = [("all", "全部"), ("start", "入门"), ("gen", "通识"), ("adv", "进阶")]
    for k, name in labels:
        pressed = "true" if k == "all" else "false"
        out.append('<li style="display:inline-block"><button type="button" class="bl-filter" '
                   'data-bl-level="%s" aria-pressed="%s">%s<span class="bl-fn">%d</span></button></li>'
                   % (k, pressed, name, counts[k]))
    out.append('</ul>')

    out.append('<div class="bl-paths">')
    for p in paths:
        total = sum(len(s["items"]) for s in p["stages"])
        lv_name = LEVELS[p["levelKey"]][0]
        out.append('<article class="bl-path" data-level="%s" data-bl-id="%s">'
                   % (esc(p["levelKey"]), esc(p["id"])))
        out.append('<div class="bl-path-head">')
        out.append('<span class="bl-field">%s</span>' % esc(p["field"]))
        out.append('<span class="bl-level" data-lv="%s">%s</span>' % (esc(p["levelKey"]), esc(lv_name)))
        out.append('<span class="bl-meta">%d 本 · %d 步</span>' % (total, len(p["stages"])))
        out.append('</div>')
        out.append('<h3 class="bl-title">%s</h3>' % esc(p["title"]))
        out.append('<div class="bl-goal"><b>读完你能：</b>%s</div>' % esc(p["goal"]))
        out.append('<div class="bl-stages">')
        for idx, s in enumerate(p["stages"], 1):
            out.append('<div class="bl-stage">')
            out.append('<div class="bl-step"><span class="bl-step-n">%d</span><div class="bl-step-tx">'
                       '<p class="bl-step-name">%s</p><p class="bl-step-aim">%s</p></div></div>'
                       % (idx, esc(s["name"]), esc(s.get("aim", ""))))
            if s.get("tip"):
                out.append('<p class="bl-tip"><b>一步到位：</b>%s</p>' % esc(s["tip"]))
            out.append('<ul class="bl-books">')
            for it in s["items"]:
                slug, title, why = it["s"], it["t"], it["w"]
                # 链接由数据源 u 字段指定：booklist_factory.py sync 会按线上探测结果
                # 回填「combined.html（最新全书领读）优先，overview.html 回退」。
                # 缺省才回退旧 overview，保证老数据源仍可注入。
                href = it.get("u") or ("reading-notes/books/%s/overview.html" % slug)
                cover = "https://cdn.js-dev.cn/assets/covers/%s.jpg" % slug
                out.append('<li class="bl-book" data-bl-slug="%s">' % esc(slug))
                out.append('<a href="%s" title="%s · 打开本书笔记页">' % (esc(href), esc(title)))
                out.append('<span class="bl-cover" style="--cv-h:%d">' % hue(slug))
                out.append('<span class="bl-cover-ph" aria-hidden="true">%s</span>' % esc(short_title(title)))
                out.append('<img src="%s" alt="" loading="lazy" decoding="async" draggable="false" '
                           'onerror="this.remove()" '
                           'onload="var b=this.closest(\'.bl-book\');if(b)b.classList.add(\'has-img\')">' % esc(cover))
                out.append('</span>')
                out.append('<span class="bl-book-meta"><span class="bl-book-t">%s</span>'
                           '<span class="bl-book-w">%s</span></span>' % (esc(title), esc(why)))
                out.append('</a></li>')
            out.append('</ul></div>')
        out.append('</div></article>')
    out.append('</div>')
    out.append('<p class="bl-foot">书目均取自本站已归档书架，按主题与阅读先后编排；'
               '同一本书可能出现在不同路径里，不必重复读。路径是建议而非清单，读到某一步已有整体感即可停下。</p>')
    out.append('</section>')
    return "\n".join(out)


def build_js():
    return """<script>
/* 书单筛选（纯前端，只切 data-level；tab 显隐交给既有 homepage-reading.js） */
(function(){'use strict';
  var panel=document.getElementById('reading-panel-booklist');
  if(!panel)return;
  var chips=panel.querySelectorAll('[data-bl-level]');
  var cards=panel.querySelectorAll('.bl-path');
  function apply(level){
    for(var i=0;i<chips.length;i++){
      chips[i].setAttribute('aria-pressed', chips[i].getAttribute('data-bl-level')===level?'true':'false');
    }
    for(var j=0;j<cards.length;j++){
      cards[j].hidden = !(level==='all' || cards[j].getAttribute('data-level')===level);
    }
  }
  for(var k=0;k<chips.length;k++){
    chips[k].addEventListener('click',function(){ apply(this.getAttribute('data-bl-level')); });
  }
  apply('all');
  /* 封面降级：占位层兜底 + img onerror 移除自身、onload 给 .bl-book 加 has-img 隐藏占位。
     另扫一遍已缓存完成的图片（complete && naturalWidth>0），补上 onload 未触发的情况。 */
  var imgs=panel.querySelectorAll('.bl-cover img');
  for(var n=0;n<imgs.length;n++){
    (function(img){
      if(img.complete && img.naturalWidth>0){
        var b=img.closest ? img.closest('.bl-book') : null;
        if(b) b.classList.add('has-img');
      }
    })(imgs[n]);
  }
})();
</script>"""


def block(content):
    """统一块格式：BEGIN / 内容 / END / 换行。所有块自带换行，块外不再补 \n。"""
    return BEGIN + "\n" + content + "\n" + END + "\n"


def strip_all(text):
    """移除所有书单注入块（css / tab / panel / js），用于 --remove 或重新注入。

    每个块都以 BEGIN 开头、END 结尾，块内不含这两个标记，因此一条非贪婪正则
    即可逐对清除；末尾的 \\n? 吃掉块自带换行，保证重复执行增量为 0。
    """
    return re.sub(re.escape(BEGIN) + r"\s*.*?" + re.escape(END) + r"\n?",
                  "", text, flags=re.S)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--data", default=DATA)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--remove", action="store_true")
    args = ap.parse_args()

    with open(args.file, encoding="utf-8") as f:
        orig = f.read()
    with open(args.data, encoding="utf-8") as f:
        paths = json.load(f)

    stripped = strip_all(orig)
    if args.remove:
        new = stripped
    else:
        css = build_css()
        tab = build_tab_button()
        panel = build_panel(paths)
        js = build_js()

        # 1) tab 按钮：紧跟「归档」之后
        m = re.search(r'(<button type="button" id="reading-tab-archive"[^>]*>归档</button>)', stripped)
        if not m:
            raise RuntimeError("找不到「归档」tab 按钮锚点")
        stripped = stripped[:m.end()] + block(tab) + stripped[m.end():]

        # 2) panel：紧跟 archive panel 的 </section> 之后、reading-module 的 </div> 之前
        m = re.search(r'(<p id="empty-state"[^>]*>[^<]*</p></section>)', stripped)
        if not m:
            raise RuntimeError("找不到 archive panel 结束锚点")
        stripped = stripped[:m.end()] + block(panel) + stripped[m.end():]

        # 3) css：放在 </head> 前
        idx = stripped.find("</head>")
        if idx < 0:
            raise RuntimeError("找不到 </head> 锚点")
        stripped = stripped[:idx] + block(css) + stripped[idx:]

        # 4) js：放在 </body> 前
        idx = stripped.rfind("</body>")
        if idx < 0:
            raise RuntimeError("找不到 </body> 锚点")
        stripped = stripped[:idx] + block(js) + stripped[idx:]

        new = stripped

    delta = len(new) - len(orig)
    print("文件: %s" % args.file)
    print("原始: %d B | 新: %d B | 增量: %+d B" % (len(orig), len(new), delta))
    print("书单块: CSS=%s TAB=%s PANEL=%s JS=%s" % (
        "rd-booklist-style" in new,
        "reading-tab-booklist" in new,
        'id="reading-panel-booklist"' in new,
        "书单筛选" in new))
    print("data-panel 按钮数: %d | book 链接数: %d | 路径数: %d" % (
        new.count("data-panel="), new.count('class="bl-book"'), len(paths)))
    if not args.remove:
        print("书单链接世代: 最新 combined=%d / 旧 overview=%d（后者为产线尚未补产的书）" % (
            panel.count("/combined.html"), panel.count("/overview.html")))

    if args.check:
        print("--check 模式：未写入")
        return 0
    if new == orig:
        print("无变化，未写入")
        return 0
    with open(args.file, "w", encoding="utf-8") as f:
        f.write(new)
    print("已写入")
    return 0


if __name__ == "__main__":
    sys.exit(main())
