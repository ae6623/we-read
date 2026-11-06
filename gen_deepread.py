#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_deepread.py — 生成「全书精读」新模块（可重复入口，幂等）。

模块定位：把一本书已发布的大纲 / 通读 / 精读素材，重组成「要点概述 +
主题分段 + 每段深读追问」的导读页，对应微信读书 App 的「AI 导读」版式，
但内容全部来自本站既有模块，不冒充官方原文。

用法：
    python3 gen_deepread.py            # 预演，打印将写入的文件
    python3 gen_deepread.py --write    # 落盘（含导航与首页卡片注入）

新增书目：往 data/deepread/<slug>.json 放一份同结构 JSON 后重跑即可。
JSON 字段：title, lead, points[], topics[{title, summary, questions[], anchor}]。
"""
import argparse
import html
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
BOOKS = HERE / "reading-notes" / "books"
DATA = HERE / "data" / "deepread"
INDEX = HERE / "index.html"
PANEL_BEGIN = "<!--DEEPREAD-PANEL-BEGIN-->"
PANEL_END = "<!--DEEPREAD-PANEL-END-->"
NAV_LINK = '<a class="navlink dr-navlink" href="deepread.html">全书精读</a>'

# ---------------------------------------------------------------- 首版 5 本
# 所有句子均由本站 combined-data.html 的 oneline / views / aiask / coreask
# 模块改写归纳，未亲读正文、不新增书中不存在的事实。
SEED = {
    "1984": {
        "title": "1984",
        "lead": "奥威尔写的不是「未来会怎样」，而是「当记录、语言、记忆都能被改写，人还能凭什么说什么是真的」。全书顺着温斯顿从私下写日记、到与朱莉娅建立私密空间、再到被捕改造的路线，把极权的着力点从『逼你说假话』一路推进到『由党决定何为真』。",
        "points": [
            "极权接管的是「判定何为真」的权力：记忆洞改写外部记录，新话删掉表达思想所需的词，一零一房间折断内在的确定性。",
            "「二加二等于五」不是算术题——先让记录可被改写，再让「还存在一个我能独自确认的事实」这件事失效。",
            "无产者占大洋国人口百分之八十五，却从未成为反抗力量：被彩票、啤酒、八卦消耗的多数只是统计数字。",
            "温斯顿最后被攻破的不是勇气，而是「人民会自动解放自己」的幻想。",
        ],
        "topics": [
            {"title": "老大哥之下", "summary": "监控、历史篡改与语言控制共同构成统治的日常；这一层解决的是「外部记录由谁保管」。",
             "questions": ["新话靠删词消灭思想，今天算法推荐造成的信息收窄与它差在哪？",
                           "记忆洞与「二加二等于四」分别守的是哪一层真实？"],
             "anchor": "核心观点初判 · 译序与极权现实 / AI 问书"},
            {"title": "缝隙里的两个人", "summary": "林中与杂货铺楼上的私密关系，是全书唯一一次把「私人事实」变成可触摸的东西，也让温斯顿相信还存在党进不去的角落。",
             "questions": ["温斯顿为什么把希望寄托在无产者，而不是身边的人？",
                           "收到那张神秘纸条之后，反叛意识靠什么维持？"],
             "anchor": "核心观点初判 · 反抗意识萌发 / 地下禁恋与避难"},
            {"title": "一零一房间", "summary": "肉体与思想的双重改造，终点不是「服从」，而是把服从替换成「热爱老大哥」。",
             "questions": ["党要替换的是答案，还是判断答案的能力？",
                           "奥布赖恩为什么必须同时是引路人和审讯者？"],
             "anchor": "核心观点初判 · 被捕与思想审讯 / 核心追问"},
            {"title": "合上书之后", "summary": "今天最该保留的是对「谁有权判定事实」的警觉，最需要修正的是它对监控机制的想象。",
             "questions": ["记录不再被删除而是被信息淹没时，这本书的机制想象哪里要改写？",
                           "温斯顿的失败是个人失败，还是机制设计使然？"],
             "anchor": "全书领读 · 往日今时 / 核心追问"},
        ],
    },
    "yuan-ze": {
        "title": "原则：绘本版(汉英对照)",
        "lead": "它把「原则」定义为可复用的决策规则：把每次选择背后的判断写下来，下次遇到同类问题就不必重新纠结。绘本版把原版的生活原则压成一条能教给孩子的五步闭环，代价是把一套需要长期博弈验证的系统，简化成一句流程口号。",
        "points": [
            "「目标—问题—诊断—方案—执行」构成循环，五步里最难的是「找出问题，并且不容忍问题」。",
            "「痛苦 + 反思 = 进步」：痛苦是信号，不是失败；反思产生的新原则让人能处理更大的目标。",
            "极度求真与极度透明，是为了让错误更早暴露；写下来的原则让组织不必依赖某个人的记忆。",
            "「头脑极度开放」被当作能力而非态度：主动找到「看到而你看不到的东西」的人，并按可信度加权。",
        ],
        "topics": [
            {"title": "五步闭环", "summary": "先明确要去哪，再承认现实与目标的差距，区分症状与病因，设计绕开病因的路径，最后执行。",
             "questions": ["把原书压成五步，损失了什么？",
                           "「找出问题，并且不容忍问题」为什么排在诊断之前？"],
             "anchor": "核心观点初判 / 核心追问"},
            {"title": "痛苦与反思", "summary": "进化是一个循环：目标带来问题，问题带来痛苦，痛苦逼出反思，反思产生新原则。成功是进化的副产品，不是终点。",
             "questions": ["为什么作者说「我们所追求的东西只是鱼饵」？",
                           "如果一次失败没有带来新原则，这个循环断在哪一环？"],
             "anchor": "AI 问书 / 核心观点初判"},
            {"title": "求真由谁认定", "summary": "作者的答案是让信息自由流动、让分歧公开暴露，再由可信度加权收敛；这套办法的前提是强人背书、可量化的反馈和能承受直白批评的人。",
             "questions": ["把求真从制度问题降格为个人修养，是必要的妥协还是偷换？",
                           "放到家庭或学校，三条前提里最先缺的是哪条？"],
             "anchor": "核心追问 / AI 问书"},
            {"title": "把它写下来", "summary": "人的判断在相似情境下会反复摇摆；写下来的原则是「预先承诺」——冷静时定规则，情绪化时执行。",
             "questions": ["不写下来，同类问题为什么会得出不同结论？",
                           "一条原则要具备什么条件，团队才能直接拿来对齐？"],
             "anchor": "核心追问 / 全书领读 · AI问书"},
        ],
    },
    "zhi-shen-shi-nei--zhong-guo-zheng-fu-yu-jing-ji": {
        "title": "置身事内：中国政府与经济发展",
        "lead": "它把中国经济拆成一台由地方政府驱动的机器：财税决定动机，土地决定资金，竞争决定行为。上篇讲微观机制，下篇把房价、债务、外贸摩擦都接回同一套地方发展模式——读这本书，先得读懂地方官员为何这么做、钱从哪来、债怎么滚。",
        "points": [
            "1994 年分税制把收入上收、事权留地方，收支矛盾一变，地方政府的行为方式随之改变。",
            "土地财政与土地金融是一体两面：卖地是收入，以地抵押借贷是杠杆，共同支撑了快速城市化与工业化。",
            "京东方、光伏说明地方政府能深度介入产业、实现从无到有的赶超；代价是比拼式招商带来的重复投资与产能过剩。",
            "「地方政府竞争驱动发展」的解释力很强，但偏重供给与制度侧，不宜当成唯一因果。",
        ],
        "topics": [
            {"title": "分税制之后", "summary": "中央定方向，地方定落地；大部分审批、土地供给、基建与招商都由地方完成，而地方动机由财税结构决定。",
             "questions": ["收入占比下降而支出责任未减，地方政府有哪些可选项？",
                           "为什么理解中国经济必须先从地方政府入手？"],
             "anchor": "AI领读 · 上篇 微观机制 / 核心追问"},
            {"title": "以地生财", "summary": "把未来的土地收益贴现到现在，为基建与城市建设提供资金，这是城市化速度的关键，也是风险的来源。",
             "questions": ["土地财政为什么既是动力也是风险？",
                           "它隐含了哪个一旦不成立就会断裂的假设？"],
             "anchor": "核心追问 / AI 问书"},
            {"title": "政府当投资人", "summary": "从直接投资到产业基金，地方政府深度介入实业与高新产业；案例讲的是成效，也讲的是补贴退坡后的僵尸产能。",
             "questions": ["京东方与光伏，成效和风险各是什么？",
                           "比拼式招商为什么会系统性地导向重复投资？"],
             "anchor": "核心观点初判 · 工业化产业政策 / 核心追问"},
            {"title": "增长的另一面", "summary": "房价、债务、内外失衡与内循环转型，被放回同一条解释链上；限定条件同样重要。",
             "questions": ["这套解释链条你接受到哪一步，哪里需要限定？",
                           "对全球周期、民企活力与个人选择，它还剩多少解释力？"],
             "anchor": "核心观点初判 · 宏观风险与失衡 / 核心追问"},
        ],
    },
    "ren-lei-jian-shi-xin-ban-cong-dong-wu-dao-shang-di": {
        "title": "人类简史（新版）：从动物到上帝",
        "lead": "智人如何从一个「没什么特别的动物」变成地球的主宰，以及这种统治的代价与尽头。全书用「认知革命—农业革命—人类的融合统一—科学革命」四段式，追问我们为何会相信自己讲的虚构故事，又为何被这些故事反向绑架。",
        "points": [
            "胜出的关键不在个体智力，而在能靠「虚构的故事」组织大规模陌生人协作。",
            "认知革命让语言可以谈论不存在的事物；金钱、帝国与宗教把千百万人纳进同一套秩序。",
            "农业革命被称作「史上最大的一桩骗局」：粮食总量增加，个体却更辛苦、饮食更差。",
            "判断任何「进步」都先换尺度：是物种繁衍、总量增长，还是个体体验。",
        ],
        "topics": [
            {"title": "认知革命", "summary": "大约七万年前，智人开始创造更复杂的架构「文化」；能谈论不存在之物，是大规模协作的起点。",
             "questions": ["为什么「虚构」反而比血缘和部落更能聚人？",
                           "语言谈论不存在的事物，具体改变了哪一种合作规模？"],
             "anchor": "AI领读 · 第一部分 认知革命 / AI 问书"},
            {"title": "小麦驯化了人", "summary": "作者不否认粮食总量增加，而是把尺度换成个体：农民比采集者更辛苦，人口爆炸又让退回采集变得不可能。",
             "questions": ["「不是人驯化了小麦」这个反转靠什么论证支撑？",
                           "这个隐喻有没有被推广到它撑不住的地方？"],
             "anchor": "AI 问书 / 核心追问"},
            {"title": "虚构的秩序", "summary": "金钱是最普遍也最有效的互信系统，帝国与宗教把千百万人纳入同一套秩序——三者都不是事实，而是集体想象。",
             "questions": ["金钱凭什么能让陌生人互信？",
                           "一套「不是事实」的秩序，靠什么维持不塌？"],
             "anchor": "AI 问书 / 核心观点初判"},
            {"title": "按谁的尺度算", "summary": "一心追求更轻松的生活，可能把自己锁进更辛苦的结构；先算它锁死哪些退路，再算它带来多少便利。",
             "questions": ["「进步」在物种、总量、个体三个尺度上会得出不同结论吗？",
                           "回到第 5 章，作者有没有把骗局说得太绝对？"],
             "anchor": "AI 问书 / 核心追问"},
        ],
    },
    "jiao-yi-xin-li-fen-xi": {
        "title": "交易心理分析",
        "lead": "市场里最难的不是看懂图表，而是看懂自己；当你能彻底接受「每笔结果都不确定」，纪律与自信才会从心底长出来。它不讲技术指标，讲的是长期赢家与别人的差别不在分析工具，而在思想结构。",
        "points": [
            "交易的核心矛盾是「概率思维」与「确定性渴望」的冲突。",
            "95% 的交易错误源于态度：对犯错、亏损、错过机会、赚不到钱的四种恐惧，让人在关键时刻偏离规则。",
            "「接受风险」不是心理暗示，是把单笔损失预先算进成本，让不利信息也能完整进入判断。",
            "稳定的交易者不是没有情绪，是不让情绪参与决策。",
        ],
        "topics": [
            {"title": "知道却做不到", "summary": "技术分析解决「看到什么」，执行由态度决定；知识在意识层，信念在更深的层，两者冲突时信念赢。",
             "questions": ["为什么「知道该止损」和「做得到止损」是两件事？",
                           "改变信念为什么不是消灭旧信念，而是转移能量？"],
             "anchor": "AI 问书 / 核心追问"},
            {"title": "把风险算进成本", "summary": "越觉得必须获利，就越不能容忍显示自己可能失败的信息；排除的信息越多，能看见的机会越少。",
             "questions": ["「接受风险」具体改变了信息进入判断的哪一步？",
                           "把单笔损失算进成本之后，止损为什么不再像认输？"],
             "anchor": "核心追问 / 核心观点初判"},
            {"title": "概率思维的地基", "summary": "「市场中任何事情都可能发生」把隐含假设从「我知道下一步」换成「我不知道，但我知道优势在哪里」。",
             "questions": ["为什么「需要知道下一步」的程度等于失败的程度？",
                           "怎样把每笔交易当成独立样本，而不是对错审判？"],
             "anchor": "核心追问 / 核心观点初判"},
            {"title": "把心态变成动作", "summary": "作者不让人「心态好点」，而是给出阶梯：接纳不确定 → 把控制点从市场移回自己 → 在规则中执行而非赌结果。",
             "questions": ["这个阶梯里，哪一步最容易被跳过？",
                           "对长期指数投资者，哪些部分需要降级使用？"],
             "anchor": "核心追问 / AI 问书"},
        ],
    },
}


def esc(s):
    return html.escape(str(s or ""), quote=True)


def render(slug, d):
    title = esc(d["title"])
    pts = "\n".join('      <li>%s</li>' % esc(p) for p in d["points"])
    topics = []
    for i, t in enumerate(d["topics"], 1):
        qs = "\n".join(
            '        <li>%s</li>' % esc(q) for q in t["questions"])
        topics.append("""    <article class="dr-topic">
      <div class="dr-num">%02d</div>
      <div class="dr-topic-body">
        <h3>%s</h3>
        <p class="dr-summary">%s</p>
        <p class="dr-qtitle">带着这些问题往回读</p>
        <ul class="dr-qs">
%s
        </ul>
        <p class="dr-anchor">素材锚点 · %s</p>
      </div>
    </article>""" % (i, esc(t["title"]), esc(t["summary"]), qs, esc(t["anchor"])))
    topics_html = "\n".join(topics)
    return """<!DOCTYPE html>
<html lang="zh-CN" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#15171a">
<title>《%s》｜全书精读</title>
<link rel="stylesheet" href="../../../assets/css/site.css">
<link rel="stylesheet" href="../../../assets/css/mmx-guide.css">
<style>
:root{--bg:#15171a;--card:#1c1f23;--line:#33383e;--ink:#f2ede2;--dim:#a8a49a;--accent:#c9a227;--green:#7fae8b}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:"Noto Serif SC","Songti SC",Georgia,serif;line-height:1.85;-webkit-font-smoothing:antialiased}
.dr-wrap{max-width:820px;margin:0 auto;padding:32px 22px 80px}
.dr-back{display:inline-block;color:var(--dim);text-decoration:none;font-size:14px;margin-bottom:30px;border-bottom:1px solid transparent}
.dr-back:hover{color:var(--accent);border-color:var(--accent)}
.dr-head{border-bottom:1px solid var(--line);padding-bottom:26px;margin-bottom:38px}
.dr-eyebrow{font-size:12px;letter-spacing:.28em;color:var(--accent);text-transform:uppercase;margin-bottom:14px}
h1{font-size:clamp(26px,5vw,38px);line-height:1.35;margin:0 0 10px;font-weight:700}
.dr-sub{color:var(--dim);font-size:15px;margin:0 0 18px;letter-spacing:.05em}
.dr-chips{display:flex;flex-wrap:wrap;gap:8px}
.dr-chip{font-size:12px;color:var(--dim);border:1px solid var(--line);border-radius:999px;padding:3px 12px;font-family:system-ui,sans-serif}
.dr-sec{margin-bottom:46px}
.dr-sec h2{font-size:21px;margin:0 0 20px;padding-left:14px;border-left:3px solid var(--accent);letter-spacing:.08em}
.dr-lead{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px 22px;margin:0 0 22px;font-size:16px;color:#e6e0d4}
.dr-points{list-style:none;counter-reset:p;margin:0;padding:0}
.dr-points li{counter-increment:p;position:relative;padding:12px 0 12px 44px;border-bottom:1px dashed var(--line);font-size:15.5px}
.dr-points li:before{content:counter(p,decimal-leading-zero);position:absolute;left:0;top:12px;color:var(--accent);font-family:system-ui,sans-serif;font-size:13px;letter-spacing:.05em}
.dr-topic{display:flex;gap:18px;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:22px;margin-bottom:18px}
.dr-num{flex:0 0 auto;font-family:system-ui,sans-serif;font-size:13px;color:var(--bg);background:var(--green);width:30px;height:30px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-weight:700}
.dr-topic-body{flex:1;min-width:0}
.dr-topic h3{margin:2px 0 10px;font-size:18px;letter-spacing:.05em}
.dr-summary{margin:0 0 16px;color:#ddd6c8;font-size:15px}
.dr-qtitle{font-family:system-ui,sans-serif;font-size:12px;letter-spacing:.16em;color:var(--accent);margin:0 0 8px}
.dr-qs{margin:0 0 14px;padding-left:18px}
.dr-qs li{font-size:14.5px;color:#cfc9bc;margin:5px 0;line-height:1.7}
.dr-anchor{font-family:system-ui,sans-serif;font-size:11.5px;color:#7d8880;margin:0;letter-spacing:.03em}
.dr-foot{border-top:1px solid var(--line);padding-top:20px;color:var(--dim);font-size:13px;line-height:1.9}
.dr-foot a{color:var(--green)}
@media(max-width:520px){.dr-wrap{padding:22px 16px 60px}.dr-topic{padding:16px;gap:12px}.dr-topic h3{font-size:16.5px}}
</style>
</head>
<body data-slug="%s" data-title="%s">
<div class="dr-wrap">
  <a class="dr-back" href="combined.html">← 返回《%s》全书领读</a>
  <header class="dr-head">
    <div class="dr-eyebrow">新模块 · 全书精读</div>
    <h1>《%s》</h1>
    <p class="dr-sub">要点概述 · 主题分段 · 深读追问</p>
    <div class="dr-chips"><span class="dr-chip">AI 自主整理</span><span class="dr-chip">基于本站大纲 / 通读 / 精读素材</span><span class="dr-chip">非微信读书 AI 导读原文</span></div>
  </header>
  <main>
    <section class="dr-sec">
      <h2>要点概述</h2>
      <p class="dr-lead">%s</p>
      <ol class="dr-points">
%s
      </ol>
    </section>
    <section class="dr-sec">
      <h2>主题分段</h2>
%s
    </section>
  </main>
  <footer class="dr-foot">
    来源与证据边界：本页内容由本站已发布的「AI 大纲 / 全书领读 / AI 问书 / 核心追问」模块归纳改写，<strong>不是微信读书 App「AI 导读」的原文</strong>，也不构成亲读正文后的结论。标注的「素材锚点」指向对应模块，便于回到原页核对。<br>
    <a href="../../../index.html">← 返回首页</a>　·　<a href="combined.html">全书领读（通读＋精读）</a>　·　<a href="outline.html">AI 大纲</a>
  </footer>
</div>
</body>
</html>
""" % (title, esc(slug), title, title, title, esc(d["lead"]), pts, topics_html)


def inject_nav(slug):
    p = BOOKS / slug / "combined.html"
    if not p.exists():
        return None
    s = p.read_text(encoding="utf-8", errors="ignore")
    if 'href="deepread.html"' in s:
        return None
    if '<nav class="nav" id="rdNav"' in s:
        s = s.replace('</nav>', '  ' + NAV_LINK + '\n</nav>', 1)
    else:
        return None
    return (p, s)


def panel_html(entries):
    cards = "\n".join(
        '      <a class="dr-card" href="reading-notes/books/%s/deepread.html"><b>《%s》</b><span>%s</span><em>全书精读 →</em></a>'
        % (esc(s), esc(d["title"]), esc(d["points"][0])) for s, d in entries)
    return """%s
<section class="dr-panel" id="deepread-panel">
  <style>
  .dr-panel{max-width:1100px;margin:26px auto 0;padding:22px 20px 26px;border:1px solid #33383e;border-radius:16px;background:#1c1f23;font-family:system-ui,sans-serif}
  .dr-panel h2{margin:0 0 6px;font-size:19px;color:#f2ede2;letter-spacing:.08em}
  .dr-panel .dr-note{margin:0 0 18px;font-size:12.5px;color:#a8a49a;line-height:1.7}
  .dr-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:12px}
  .dr-card{display:flex;flex-direction:column;gap:7px;padding:15px 15px 13px;border:1px solid #33383e;border-radius:11px;background:#15171a;text-decoration:none;transition:border-color .2s,transform .2s}
  .dr-card:hover{border-color:#c9a227;transform:translateY(-2px)}
  .dr-card b{color:#f2ede2;font-size:14.5px;font-family:"Noto Serif SC",Georgia,serif}
  .dr-card span{color:#a8a49a;font-size:12px;line-height:1.6;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
  .dr-card em{color:#c9a227;font-size:11.5px;font-style:normal;letter-spacing:.06em;margin-top:auto}
  </style>
  <h2>全书精读 · 新模块</h2>
  <p class="dr-note">要点概述 + 主题分段 + 深读追问。基于本站大纲 / 通读 / 精读素材整理，非微信读书 App「AI 导读」原文。</p>
  <div class="dr-grid">
%s
  </div>
</section>
%s""" % (PANEL_BEGIN, cards, PANEL_END)


def inject_index(entries):
    if not INDEX.exists():
        return None
    s = INDEX.read_text(encoding="utf-8", errors="ignore")
    block = panel_html(entries)
    # 面板放在 <main> 之外：首页 main 是网格布局，塞进去会占掉一格。
    anchor = '<main id="main" class="layout">'
    if PANEL_BEGIN in s:
        # 只删面板本身，别把后面 <div> 的缩进一起吃掉
        s = re.sub(re.escape(PANEL_BEGIN) + r".*?" + re.escape(PANEL_END),
                   "", s, flags=re.S)
    s = s.replace(anchor, block + '\n' + anchor, 1)
    return (INDEX, s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--seed", action="store_true", help="重写 data/deepread/*.json")
    args = ap.parse_args()

    DATA.mkdir(parents=True, exist_ok=True)
    for slug, d in SEED.items():
        f = DATA / (slug + ".json")
        if args.seed or not f.exists():
            f.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    entries = []
    for f in sorted(DATA.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        entries.append((f.stem, d))

    writes = []
    for slug, d in entries:
        out = BOOKS / slug / "deepread.html"
        writes.append((out, render(slug, d)))
    for slug, d in entries:
        r = inject_nav(slug)
        if r:
            writes.append(r)
    r = inject_index(entries)
    if r:
        writes.append(r)

    for p, _ in writes:
        print("write", p.relative_to(HERE))
    print("共 %d 本 / %d 个写入" % (len(entries), len(writes)))
    if args.write:
        for p, s in writes:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(s, encoding="utf-8", newline="\n")
        print("done")


if __name__ == "__main__":
    main()
