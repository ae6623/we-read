#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「书单路径列表」就地追加到首页书单 tab 的画廊入口卡下面（幂等）。

背景（2026-11-20）：
- 书单 tab 现在只有一张「书卡画廊」跳转卡（bl-entry），点了新标签打开 channel/。
- 一部分用户找不到书单入口，反馈「以前那种一屏看完路径的模式更好」。
- 本脚本在跳转卡**下面**追加完整路径列表（程度筛选 + 三步书目），
  跳转卡原样保留：想翻卡的去画廊，想直接读的就地展开。

与 inject_booklist.py 的分工：
- inject_booklist.py 会整体重建 booklist 块（CSS/PANEL/JS 全换），
  且它生成的还是旧的 bl-channel 入口；线上 index.html 的 rd-booklist-style
  里后来混入了全站 hero / 书墙样式，重跑会把它们一起删掉。
- 所以这里只做**局部替换**：panel 尾部插列表、样式块尾部追 CSS、替换书单脚本。

用法:
  python3 inject_paths.py --file ../../index.html          # 写入
  python3 inject_paths.py --file ../../index.html --check  # 只看差异
"""
import argparse
import html
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.abspath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(HERE, "booklist_paths.json")

PB = "<!-- bl-paths:begin -->"
PE = "<!-- bl-paths:end -->"
CS = "/* bl-paths v2:begin */"
CE = "/* bl-paths v2:end */"

LEVELS = {"start": "入门", "gen": "通识", "adv": "进阶"}
LEVEL_ALIAS = {"general": "gen", "mid": "adv", "beginner": "start"}
LIMIT = 4  # 默认先摊开几条，其余一键展开，避免一进 tab 就是上万像素

COVER_HUES = [162, 186, 205, 28, 36, 12, 258, 340]


def hue(slug):
    n = 0
    for ch in slug:
        n = (n * 31 + ord(ch)) % 9973
    return COVER_HUES[n % len(COVER_HUES)]


def short_title(title):
    return (re.sub(r"^[\s《〈“\"'「【·—-]+", "", title or "")[:2] or "阅")


def esc(s):
    return html.escape(s or "", quote=True)


_GIT_FILES = None


def git_files():
    """站点里真实存在的文件（工作区是 sparse checkout，不能拿 os.path.exists 判断）。"""
    global _GIT_FILES
    if _GIT_FILES is None:
        out = subprocess.run(["git", "-C", SITE, "ls-files"], capture_output=True, text=True)
        _GIT_FILES = set(out.stdout.split("\n"))
    return _GIT_FILES


def resolve_href(slug, u):
    """combined（最新全书领读）优先，overview 回退，最后才用数据里的 u。"""
    book = "reading-notes/books/%s/" % slug
    for cand in (book + "combined.html", book + "overview.html", u):
        if cand and cand in git_files():
            return cand
    return u or (book + "combined.html")


def build_css():
    return CS + """
/* 画廊入口下面的「就地书单」：与上方跳转卡是同一件事的两种读法，
   视觉上用一个细分隔 + 小标题切开，不抢入口卡的注意力。 */
#reading-panel-booklist .bl-sub{display:flex;align-items:baseline;gap:6px 12px;flex-wrap:wrap;
  margin:28px 0 14px;padding-top:20px;border-top:1px solid var(--line)}
#reading-panel-booklist .bl-sub h3{font:700 1.02rem/1.4 var(--serif);color:var(--ink);margin:0}
#reading-panel-booklist .bl-sub p{font:.75rem/1.65 var(--sans);color:var(--muted);margin:0}
#reading-panel-booklist .bl-toolbar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:0 0 18px}
#reading-panel-booklist .bl-toolbar .bl-filters{margin:0}
#reading-panel-booklist .bl-toolbar .bl-more{width:auto;padding:5px 13px;border-radius:999px;
  font:600 .76rem/1.4 var(--sans);border-style:solid}
#reading-panel-booklist .bl-more-wrap{margin:16px 0 0}
#reading-panel-booklist .bl-more{display:block;width:100%;padding:13px 16px;background:transparent;
  border:1px dashed var(--line);border-radius:12px;color:var(--green);
  font:600 .8rem/1.2 var(--sans);cursor:pointer;transition:.15s}
#reading-panel-booklist .bl-more:hover,#reading-panel-booklist .bl-more:focus-visible{
  border-color:var(--green);background:var(--sage)}
#reading-panel-booklist .bl-more[hidden]{display:none}
@media(max-width:560px){
  #reading-panel-booklist .bl-sub{margin:22px 0 12px;padding-top:16px}
  #reading-panel-booklist .bl-sub h3{font-size:.96rem}
}
/* 手机端跳转卡收紧成「字 + 两本小书」的横排：一屏内就能看到下面的列表标题，
   不然 440px 高的叠书卡会把「书单在哪」这个问题又推回原点。 */
@media(max-width:640px){
  #reading-panel-booklist .bl-entry{grid-template-columns:minmax(0,1fr) 96px;gap:12px;
    padding:16px 16px 15px;align-items:center}
  #reading-panel-booklist .bl-entry-art{order:0;height:132px}
  #reading-panel-booklist .bl-entry-card{width:64px}
  #reading-panel-booklist .bl-entry-card.c3{display:none}
  #reading-panel-booklist .bl-entry-copy{margin:0 0 12px}
  #reading-panel-booklist .bl-entry-tip{display:none}
}
""" + CE


def build_list(paths):
    counts = {"all": len(paths)}
    for k in LEVELS:
        counts[k] = sum(1 for p in paths if p["levelKey"] == k)

    out = [PB]
    out.append('<div class="bl-sub">')
    out.append('<h3>全部 %d 条路径 · 就在这里读</h3>' % len(paths))
    out.append('<p>不想开新页的话，往下直接看：三步顺序、每步书目都在，点书名进全书领读。</p>')
    out.append('</div>')

    out.append('<div class="bl-toolbar">')
    out.append('<ul class="bl-filters" role="group" aria-label="按程度筛选书单">')
    for k, name in [("all", "全部"), ("start", "入门"), ("gen", "通识"), ("adv", "进阶")]:
        out.append('<li style="display:inline-block"><button type="button" class="bl-filter" '
                   'data-bl-level="%s" aria-pressed="%s">%s<span class="bl-fn">%d</span></button></li>'
                   % (k, "true" if k == "all" else "false", name, counts[k]))
    out.append('</ul>')
    # 展开按钮：筛选行右侧就有一个，省得手机滑 4000px 才看到
    out.append('<button type="button" class="bl-more" aria-controls="reading-panel-booklist" '
               'aria-expanded="false"></button>')
    out.append('</div>')

    out.append('<div class="bl-paths">')
    for pi, p in enumerate(paths):
        total = sum(len(s["items"]) for s in p["stages"])
        lv_name = LEVELS[p["levelKey"]]
        out.append('<article class="bl-path" data-level="%s" data-bl-id="%s" data-bl-idx="%d">'
                   % (esc(p["levelKey"]), esc(p["id"]), pi))
        out.append('<div class="bl-path-head">')
        out.append('<span class="bl-field">%s</span>' % esc(p["field"]))
        out.append('<span class="bl-level" data-lv="%s">%s</span>' % (esc(p["levelKey"]), esc(lv_name)))
        out.append('<span class="bl-meta">%d 本 · %d 步</span>' % (total, len(p["stages"])))
        out.append('</div>')
        out.append('<h4 class="bl-title">%s</h4>' % esc(p["title"]))
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
                href = resolve_href(slug, it.get("u"))
                cover = "https://cdn.js-dev.cn/assets/covers/%s.jpg" % slug
                out.append('<li class="bl-book" data-bl-slug="%s">' % esc(slug))
                out.append('<a href="%s" title="%s · 打开本书笔记页">' % (esc(href), esc(title)))
                out.append('<span class="bl-cover" style="--cv-h:%d">' % hue(slug))
                out.append('<span class="bl-cover-ph" aria-hidden="true">%s</span>' % esc(short_title(title)))
                out.append('<img src="%s" alt="" loading="lazy" decoding="async" draggable="false" '
                           'onerror="this.remove()" '
                           'onload="var b=this.closest(\'.bl-book\');if(b)b.classList.add(\'has-img\')">'
                           % esc(cover))
                out.append('</span>')
                out.append('<span class="bl-book-meta"><span class="bl-book-t">%s</span>'
                           '<span class="bl-book-w">%s</span></span>' % (esc(title), esc(why)))
                out.append('</a></li>')
            out.append('</ul></div>')
        out.append('</div></article>')
    out.append('</div>')
    out.append('<div class="bl-more-wrap"><button type="button" class="bl-more" '
               'aria-controls="reading-panel-booklist" aria-expanded="false"></button></div>')
    out.append(PE)
    return "".join(out)


def build_js():
    return """<!-- booklist:begin --><script>
/* 书单（2026-11-20 v2）：上方画廊跳转卡 + 下方就地路径列表。
   1) 程度筛选只切 data-level；
   2) 默认先摊 LIMIT 条，其余「展开」，避免一进 tab 就是上万像素；
   3) 封面缺失时保留书名占位。tab 显隐仍交给既有 homepage-reading.js。 */
(function(){'use strict';
  var panel=document.getElementById('reading-panel-booklist');
  if(!panel)return;
  var chips=panel.querySelectorAll('[data-bl-level]');
  var cards=panel.querySelectorAll('.bl-path');
  var mores=panel.querySelectorAll('.bl-more');
  var LIMIT=%d, level='all', expanded=false;
  function render(){
    var shown=0, matched=0;
    for(var i=0;i<cards.length;i++){
      var c=cards[i], ok=(level==='all'||c.getAttribute('data-level')===level);
      if(ok) matched++;
      /* 只看某一档时不再分批，避免「进阶 5 条」还只露 4 条 */
      var vis=ok&&(expanded||level!=='all'||shown<LIMIT);
      if(vis) shown++;
      c.hidden=!vis;
    }
    for(var j=0;j<chips.length;j++){
      chips[j].setAttribute('aria-pressed', chips[j].getAttribute('data-bl-level')===level?'true':'false');
    }
    for(var m=0;m<mores.length;m++){
      var b=mores[m];
      b.hidden = (level!=='all')||matched<=LIMIT;
      b.setAttribute('aria-expanded', expanded?'true':'false');
      b.textContent = expanded ? '收起 ↑' : '展开全部 '+matched+' 条 ↓';
    }
  }
  for(var k=0;k<chips.length;k++){
    chips[k].addEventListener('click',function(){ level=this.getAttribute('data-bl-level'); render(); });
  }
  for(var q=0;q<mores.length;q++){
    mores[q].addEventListener('click',function(){ expanded=!expanded; render(); });
  }
  render();
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
</script>""" % LIMIT


def replace_span(text, start_marker, end_marker, payload):
    """把 [start_marker … end_marker] 换成 payload；不存在则返回 None。"""
    i = text.find(start_marker)
    if i < 0:
        return None
    j = text.find(end_marker, i)
    if j < 0:
        return None
    return text[:i] + payload + text[j + len(end_marker):]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--data", default=DATA)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    orig = open(args.file, encoding="utf-8").read()
    paths = json.load(open(args.data, encoding="utf-8"))
    for p in paths:
        p["levelKey"] = LEVEL_ALIAS.get(p["levelKey"], p["levelKey"])

    new = orig

    # 1) 列表 HTML：插在 panel 的最后一个 </div>（bl-entry 结束）之后
    i = new.find('<section id="reading-panel-booklist"')
    j = new.find("</section>", i)
    if i < 0 or j < 0:
        raise SystemExit("找不到书单 panel")
    panel = new[i:j]
    base = panel[:panel.find(PB)] if PB in panel else panel   # 先剥掉上次注入的列表
    k = base.rfind("</div>")
    if k < 0:
        raise SystemExit("panel 结构异常")
    panel_new = base[:k + len("</div>")] + "\n" + build_list(paths) + "\n" + base[k + len("</div>"):]
    new = new[:i] + panel_new + new[j:]

    # 2) CSS：追加在 rd-booklist-style 块末尾
    cs = new.find('<style id="rd-booklist-style">')
    ce = new.find("</style>", cs)
    if cs < 0 or ce < 0:
        raise SystemExit("找不到 rd-booklist-style")
    css = new[cs:ce]
    if CS in css:
        css = css[:css.find(CS)]
    new = new[:cs] + css.rstrip("\n") + "\n" + build_css() + "\n" + new[ce:]

    # 3) JS：整块替换旧的书单脚本（只认「BEGIN + script + 书单筛选」那一段，
    #    避免误伤页面上其它 booklist:begin 块）
    mjs = re.search(r"<!--\s*booklist:begin\s*-->\s*<script>\s*/\*\s*书单", new)
    if mjs:
        sj = new.find("</script>", mjs.end())
        new = new[:mjs.start()] + build_js() + new[sj + len("</script>"):]
    else:
        bi = new.rfind("</body>")
        if bi < 0:
            raise SystemExit("找不到 </body>")
        new = new[:bi] + build_js() + new[bi:]

    delta = len(new) - len(orig)
    print("文件: %s" % args.file)
    print("原始 %d B → 新 %d B（%+d）" % (len(orig), len(new), delta))
    print("路径卡: %d | 书链接: %d | 默认展开: %d" % (
        new.count('class="bl-path"'), new.count('class="bl-book"'), LIMIT))
    missing = []
    for p in paths:
        for st in p["stages"]:
            for it in st["items"]:
                if resolve_href(it["s"], it.get("u")) not in git_files():
                    missing.append(it["s"])
    print("链接目标缺失: %d %s" % (len(missing), missing[:3]))

    if args.check:
        print("--check：未写入")
        return 0
    if new == orig:
        print("无变化")
        return 0
    open(args.file, "w", encoding="utf-8").write(new)
    print("已写入")


if __name__ == "__main__":
    sys.exit(main())
