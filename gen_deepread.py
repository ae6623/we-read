#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_deepread.py — 生成「全书精读」模块（可重复入口，幂等）。

模块定位：不是把章节切成块的导读，而是对全书核心论证的一次审视——
「一句话判断 → 论证链重构 → 存疑与取舍 → 证据边界」。内容全部从本站
已发布的 核心观点 / 核心追问 / 更高维度 / 阅读验证 / 往日今时 / AI 问书
模块二次提炼，明确标出哪些是书内主张、哪些是整理者的存疑与暂定判断，
不冒充亲读正文后的结论，也不编造书中事实。

**模块落在详情页里**：往 combined-data.html 追加 data-key="deepread"
的 section，reader.js 会把它装配进 #rdBody 并自动生成导航项「全书精读」；
首页不放任何入口。同时保留一份自包含的 deepread.html 独立页便于直达。

**样式对齐**：详情页片段只用站点现成的 mmx-* 类与 reader.css 主题变量，
不注入自定义 <style>，四套主题、时间轴编号、朗读高亮全部跟随既有区块。

用法：
    python3 gen_deepread.py                 # 预演，打印将写入的文件
    python3 gen_deepread.py --write         # 落盘
    python3 gen_deepread.py --write --seed # 连 JSON 一起按 SEED 重写

新增书目：往 data/deepread/<slug>.json 放一份同结构 JSON 后重跑即可。
JSON 字段：title, verdict, chain, units[{title,claim,doubt,call}], boundary。
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
SEC_BEGIN = "<!--DEEPREAD-SECTION-BEGIN-->"
SEC_END = "<!--DEEPREAD-SECTION-END-->"

# ---------------------------------------------------------------- 首批 5 本
# 全部由本站 combined-data.html 的 coreask / higher / verify / thennow /
# aiask / views 模块二次提炼；"存疑""取舍"是整理者的判断，不是作者结论。
# 不新增书中不存在的事实、页码、数据或引语。
SEED = {
    "1984": {
        "title": "1984",
        "verdict": "全书真正被拆掉的，不是勇气，也不是「敢不敢说真话」，而是「还存在一个我能独自确认的事实」这个前提——所以它最锋利的地方是认识论，不是政治预言。",
        "chain": "顺序本身就是论证：记忆洞先让外部记录可被改写，新话再删掉表达思想所需的词，一零一房间最后折断内在的确定性。若党只要求人说假话，那仍是谎言，谎言还得拿真话做背景；它要的是「由党决定何为真」，于是真理从符合事实变成服从权威。温斯顿的终点不是被说服，是被换成热爱。",
        "units": [
            {"title": "新话若真成立，温斯顿的反抗意识从哪来？",
             "claim": "奥布赖恩说新话要让思想罪根本不可能再犯，因为没有词可以表达它——前提是党垄断了语言生产。",
             "doubt": "把语言与思想绑得这么紧，反而给小说自己制造了难题：若词没了经验就不可想，书中的反抗意识、以及「二加二等于四」的执念，靠什么存下来？「希望就在无产者身上」紧接私人生活章节后急转落空，更像作者对理论前提的一次自我保留，而不是严密论证。",
             "call": "接受它作为「事实如何被制度性取消」的思想实验；在「语言决定思想的边界」上保留存疑，不把设定当结论。"},
            {"title": "该修正的是结论，还是机制想象？",
             "claim": "1949 年能设想的监控是电幕与思想警察，稀缺且昂贵，所以必须集中配置；记忆洞之可怖，正因当年改写记录要物理地处理纸张。",
             "doubt": "后来显现的是另一种形态：记录不被删除而被过剩信息淹没，监控不必集中、常由当事人主动交出，权力更少靠禁止、更多靠排序与推荐。令人放弃判断的未必是恐惧，也可能是便利与娱乐。",
             "call": "保留「谁有权判定事实」的警觉，修正「靠恐惧」的机制想象——差别不改变结论的分量，却改变了防范的位置。"},
            {"title": "多数为什么没有自动变成力量",
             "claim": "无产者占大洋国人口约 85%，温斯顿把希望寄在他们身上。",
             "doubt": "但他们被彩票、啤酒、八卦消耗，从不组织。奥威尔的冷酷在于：未被唤醒且被日常麻痹的多数只是统计数字；一零一房间击碎的不是温斯顿一个人，而是「人民会自动解放自己」这个幻想。",
             "call": "把「多数≠力量」当作全书最经得起迁移的一条，同时提醒自己这是小说给出的悲观判断，不是可验证的社会命题。"},
        ],
        "boundary": "本页基于本站「核心追问 / 更高维度 / 阅读验证 / 往日今时 / AI 问书」模块二次整理，未亲读正文。「新话削词即削思想」应核对附录《新话的原则》原文，确认是书中明示机制还是读者引申；「二加二等于五」需区分小说内部设定与历史宣传的互文，避免张冠李戴；引用金句请注明译本。本页的存疑与取舍是整理者判断，不是作者结论。",
    },
    "yuan-ze": {
        "title": "原则：绘本版(汉英对照)",
        "verdict": "它把一套「在市场中用真金白银验证过」的组织决策系统，降维成孩子也记得住的五步闭环——代价是可证伪性下降：越传播越像道理，越不需要被检验。",
        "chain": "原版的两大支柱是可信度加权的决策机制，与「痛苦 + 反思 = 进步」背后的组织设计；绘本版只取生活原则的一半，把「目标—问题—诊断—方案—执行」串成一条个人可执行的最小闭环，再配人生弧线练习。它的价值在可教，代价是把需要长期博弈验证的系统，简化成一句流程口号。",
        "units": [
            {"title": "用结果反推原则，逻辑是不是倒置的？",
             "claim": "原书以桥水的成功为这套原则背书。",
             "doubt": "站点已列出两条批评：一是幸存者偏差，桥水的成绩无法排除宏观周期与时代红利；二是循环论证，案例多为回顾性叙述，先有结果后总结原则，原则的因果效力被高估。「痛苦 + 反思 = 进步」作为经验命题成立，作为因果命题缺对照证据。",
             "call": "把它当「遇到问题有一套拆解顺序」来用，别当「照做就能成功」来信；成功与原则之间的因果，留给读者自己判断。"},
            {"title": "被抽掉的制度前提，恰恰是它最贵的部分",
             "claim": "极度求真与极度透明，原本靠信息自由流动、分歧公开暴露、可信度加权收敛来运转。",
             "doubt": "这套办法在桥水能转，前提是强人背书、可量化的业绩反馈、能承受直白批评的人；放到家庭或学校，三样全缺。绘本版把它改写成「独立思考、头脑极度开放」，等于把求真从制度问题降格为个人修养——若承认错误会被惩罚，透明就变成自我暴露；目标不一致，透明就变成信息战。",
             "call": "先问「三样前提在我这里成立几条」，再决定照搬多少；理解条件，比照搬做法重要。"},
            {"title": "当它从手册变成童书，谁来检验它",
             "claim": "2017 年出版时它被当作对冲基金的操作手册，到绘本版已成通用的自我管理话术。",
             "doubt": "当一套原则从「在市场中用真金白银验证过」变成「可以讲给孩子听的道理」，没人会拿孩子的成长去和它对照，可证伪性就下降了。传播越广，检验越松——这是所有被成功学化的方法论共同的命运。还有个更前置的问题：目标是谁的？",
             "call": "当提问清单用，不当答案清单用：目标是不是我自己的、我说的是症状还是病因、诊断有没有第二意见、方案能不能在两周内被证伪、执行时我在回避什么。这五问不需要相信作者的世界观也能用。"},
        ],
        "boundary": "本页基于本站「核心追问 / 更高维度 / 阅读验证 / 往日今时 / AI 问书」模块二次整理，未亲读正文，也不代表原版《原则》。绘本版是简写改编，五步流程省略了可信度加权等关键机制，不能据它推断桥水的实际决策方式；「人生弧线」三阶段是作者自传式框架，不是发展阶段理论。本页存疑与取舍为整理者判断。",
    },
    "zhi-shen-shi-nei--zhong-guo-zheng-fu-yu-jing-ji": {
        "title": "置身事内：中国政府与经济发展",
        "verdict": "这本书给的是一副「制度—激励—行为」的眼镜，不是一份政策判决书；它最强的地方——用一条链串起房价、债务与外贸——恰恰也是最该警惕的地方：解释力太强，就容易把解释当成辩护。",
        "chain": "作者的推法是从制度倒推行为：1994 年分税制把收入上收、事权留地方，地方收支出现缺口，于是以土地出让和抵押融资补钱，形成土地财政与土地金融的闭环；再叠上以增长为目标的地区竞争，地方政府深度介入招商与产业投资；增长、房价、债务、外贸失衡便被接回同一套地方发展模式。上篇讲机制，下篇把宏观现象逐项挂回这条链。",
        "units": [
            {"title": "一条能解释一切的链，可证伪性在哪？",
             "claim": "书里明说这套「地方政府竞争驱动发展」解释力很强，能串起房价、债务与贸易冲突。",
             "doubt": "但站点已标出限定：它偏重供给与制度侧，对全球周期、民企活力与个人选择解释不足。一个几乎不漏现象的解释，往往不是因为对，而是因为没给「什么情况下它会失效」划界。",
             "call": "把它当「读来路的地图」照单收下，不当「唯一因果」；凡遇到它解释不了的变量，先记下来而不是硬塞进链条。"},
            {"title": "土地财政依赖的那个假设，后来被现实替它验证了",
             "claim": "「以地生财」的本质是把未来土地收益贴现到现在，可持续性取决于地价持续上涨，而债务是刚性的。",
             "doubt": "书出版于 2020 年、语气是解释机制而非给方案。后来房地产下行、地方财政压力显性化，恰好撞上这个假设的边界——但这是框架预见了风险，还是事后用现实给框架补证据？要分清。",
             "call": "接受「依赖地价上涨」这条机制判断；不接受把事后验证倒推成作者的预测能力。"},
            {"title": "把政府放回分析中心，会不会又变成把政府当唯一变量",
             "claim": "作者主张脱离政府行为谈市场等于拿错地图，政府既是裁判也是运动员。",
             "doubt": "站点提醒「理解之同情」容易滑向为现状背书，读者须保留对效率与公平的双重审视。解释政府为何这么做，不等于评估这么做值不值。",
             "call": "机制层照它的框架走，评价层另找标尺；这本书明确不做的那件事，别替它做。"},
        ],
        "boundary": "本页基于本站「核心观点 / 核心追问 / 更高维度 / 阅读验证 / 往日今时」模块二次整理，未亲读正文。涉及分税制、土地财政、城投、京东方与光伏等处均为书内既有论述的转述，具体数据、章节与政策口径请回原文及相关章节核对；本页的「存疑」「取舍」是整理者的判断，不是作者结论。",
    },
    "ren-lei-jian-shi-xin-ban-cong-dong-wu-dao-shang-di": {
        "title": "人类简史（新版）：从动物到上帝",
        "verdict": "全书最该带走的不是「虚构故事让智人胜出」这个结论，而是它反复示范的那个动作——换尺度：同一件事在物种、总量、个体三个尺度上，结论可以完全相反。",
        "chain": "作者用四段式铺开：认知革命让语言能谈论不存在之物，金钱、帝国、宗教把千百万人纳进同一套「不是事实」的集体想象秩序，农业革命把粮食总量做上去却让个体更辛苦、更难回头，科学革命再把这套相信虚构的能力推向尽头。支撑「胜出」的不是个体智力，而是大规模陌生人协作。",
        "units": [
            {"title": "「史上最大的一桩骗局」，是论证还是隐喻",
             "claim": "作者不否认粮食总量增加，而是把尺度换成个体：农民比采集者更辛苦、饮食更差，人口爆炸又让退回采集变得不可能，于是「不是人驯化了小麦，而是小麦驯化了人」。",
             "doubt": "反转靠换尺度成立，也靠隐喻扩散。站点已提示要回第 5 章核对其论证与划线，再判断这个隐喻有没有被推广到它撑不住的地方；对比采集时代寿命、暴力率的数据来源是否单一、个别遗址能否代表全体，都是代表性限度。",
             "call": "接受「换尺度」这个方法，对「骗局」这个定论保留存疑；把它当提问框架，不当史实。"},
            {"title": "三大秩序是因果机制，还是叙事框架",
             "claim": "金钱、帝国、宗教被写成统一人类的三大秩序，都不是事实而是集体想象。",
             "doubt": "站点明确提醒：这是作者的归纳框架，并非互不重叠的因果机制，警惕把叙事框架直接当作史实清单。同样，「快乐取决于预期而非客观条件」更接近叔本华与佛教的哲学立场，不是可证伪的心理学结论——读时要标清哪些是思想史引述，哪些是他自己的综合判断。",
             "call": "把它放回「大历史」与「模因」的谱系里读，看它如何解释文化演化能独立于生物演化加速；同时把「主张 / 引述 / 作者综合」分开记。"},
            {"title": "连「约数」也别当成确定史实",
             "claim": "全书以「约 7 万年前认知革命」「智人走出非洲」这类年代与考古叙述作为叙事支点。",
             "doubt": "站点列出需核对处：关键年代与考古证据要核对，避免把作者使用的约数当确定史实；「智人末日」以生化人、智神人为雏形，今天基因编辑与脑机接口让它从科幻更接近政策议题，但这是后来显现的变化，不是书里的预测。",
             "call": "保留「先算锁死哪些退路、再算带来多少便利」这条可迁移的判断；其余把大历史叙事当一副眼镜，而非一份年表。"},
        ],
        "boundary": "本页基于本站「AI 问书 / 核心追问 / 更高维度 / 阅读验证 / 往日今时」模块二次整理，未亲读正文。本站该书的一句话主旨与核心观点仍是按章序机械切分的结构事实，故本页判断主要取自问答与更高维度模块；涉及年代、考古数据、个案代表性处请回原文核对。本页存疑与取舍为整理者判断，不是作者结论。",
    },
    "jiao-yi-xin-li-fen-xi": {
        "title": "交易心理分析",
        "verdict": "它最实在的贡献，是把玄虚的「心态」翻译成「接纳不确定 → 把控制点移回自己 → 在规则中执行」这条可训练阶梯；但它自己也没跨过「经验知识 vs 实证科学」那道坎。",
        "chain": "作者的推法是：技术分析与基本面解决「看到什么」，执行却由态度决定；对犯错、亏损、错过、赚不到钱的四种恐惧，让人在关键时刻偏离规则；于是把隐含假设从「我知道下一步」换成「我不知道，但我知道优势在哪里」；事先承认任何一笔都可能亏，不利信息才能完整进入判断；长期优势才稳定兑现。",
        "units": [
            {"title": "「95% 的错误源于态度」，这个数字能当结论用吗",
             "claim": "道格拉斯把绝大多数交易错误归到态度而非分析工具。",
             "doubt": "站点已标出：「95%」是经验估计、不是统计结论，不宜当精确数据引用；结论多来自作者作为交易教练的观察，缺随机对照研究，属经验知识而非实证科学；与卡尼曼的前景理论对照，四大恐惧本质是损失厌恶、后悔厌恶、错失恐惧的临床版本。",
             "call": "接受它对恐惧机制的描述，把「95%」当修辞而非数据；引用时别替它补上它没做的实验。"},
            {"title": "心态能改善判断，但能替代系统吗",
             "claim": "全书重心在「接受风险」「以概率思考」「不因单笔结果否定系统」。",
             "doubt": "站点提醒方向别搞反：心态不能替代正期望的交易系统，没有优势，心态再好也不赚钱。「接受风险」改变的是信息进入判断的那一步，不是收益的来源。另有适用范围限定——书的对象是高频、主动、带杠杆的交易者，对长期指数投资者很多问题本就不存在。",
             "call": "把「与不确定性共处」当通用态度收下，把「四大恐惧清单」按自己的交易频率降级使用；先确认自己有没有正期望系统，再谈心态。"},
            {"title": "框架没过时，只是战场换了",
             "claim": "当年基于场内、电话下单的散户与交易员辅导经验，心理误区集中在「敢不敢下手」。",
             "doubt": "算法与量化把执行速度交给机器后，人类角色转向「设规则与扛回撤」，心理议题从「敢不敢下手」变成「能不能不干预系统」；什么时候信任模型、什么时候手动干预，成了新的心理战场。书中「随机报酬」「过度干预」在量化时代反而更典型。",
             "call": "保留「把盈亏（不可控）与执行（可控）分开」这条，它几乎就是斯多葛「区分可控与不可控」的工程版；其余按新战场重读，不必照搬旧场景。"},
        ],
        "boundary": "本页基于本站「核心追问 / 更高维度 / 阅读验证 / 往日今时 / AI 问书」模块二次整理，未亲读正文。「95%」等数值为书中经验表述，非本站统计；交易心理训练缺少随机对照研究，效果因人而异，需结合自身交易系统验证。本页存疑与取舍为整理者判断，不是作者结论，也不构成投资建议。",
    },
}


def esc(s):
    return html.escape(str(s or ""), quote=True)


def qa_block(u):
    """一个思辨单元：复用站点 .mmx-qa（问 / 答），自动进时间轴编号。"""
    return (
        '<div class="mmx-qa">'
        f'<p class="mmx-q">{esc(u["title"])}</p>'
        f'<p class="mmx-a">{esc(u["claim"])}<br>'
        f'<b>存疑 · </b>{esc(u["doubt"])}<br>'
        f'<b>取舍 · </b>{esc(u["call"])}</p>'
        '</div>'
    )


def render_section(slug, d):
    """详情页模块片段：只用站点现成 mmx-* 类，不注入任何自定义样式。

    - .mmx-oneline  ：一句话判断（左侧绿线强调块，不参与编号）
    - <h3>          ：分组小标题（.mmx-mod > h3 统一绿色）
    - <p> / .mmx-qa ：自动获得 reader.css 的时间轴圆点编号与朗读高亮
    """
    units = "\n".join(qa_block(u) for u in d["units"])
    return f"""{SEC_BEGIN}
<section class="mmx-mod" data-key="deepread">
<h2>全书精读</h2>
<p class="mmx-oneline"><b>一句话判断 · </b>{esc(d["verdict"])}</p>
<h3>作者是怎么把结论推出来的</h3>
<p>{esc(d["chain"])}</p>
<h3>几个得停下来想一想的地方</h3>
{units}
<h3>读完之后，哪些先不下结论</h3>
<p>{esc(d["boundary"])}</p>
</section>
{SEC_END}"""


# 独立页专用样式（自包含，不依赖 reader.css 变量；详情页不走这里）
PAGE_CSS = """
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
.dr-lead{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px 22px;margin:0;font-size:16px;color:#e6e0d4;line-height:1.9}
.dr-topic{display:flex;gap:18px;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:22px;margin-bottom:18px}
.dr-num{flex:0 0 auto;font-family:system-ui,sans-serif;font-size:13px;color:var(--bg);background:var(--green);width:30px;height:30px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-weight:700}
.dr-topic-body{flex:1;min-width:0}
.dr-topic h3{margin:2px 0 12px;font-size:18px;letter-spacing:.05em}
.dr-summary{margin:0 0 14px;color:#ddd6c8;font-size:15px;line-height:1.85}
.dr-summary:last-child{margin-bottom:0}
.dr-qtitle{font-family:system-ui,sans-serif;font-size:12px;letter-spacing:.16em;color:var(--accent);margin:0 0 6px}
.dr-foot{border-top:1px solid var(--line);padding-top:20px;color:var(--dim);font-size:13px;line-height:1.9}
.dr-foot a{color:var(--green)}
@media(max-width:520px){.dr-wrap{padding:22px 16px 60px}.dr-topic{padding:16px;gap:12px}.dr-topic h3{font-size:16.5px}}
"""


def render(slug, d):
    """自包含独立页：内容与详情页同源，样式是它自己的深色版式。"""
    title = esc(d["title"])
    units = []
    for i, u in enumerate(d["units"], 1):
        units.append(f"""    <article class="dr-topic">
      <div class="dr-num">{i:02d}</div>
      <div class="dr-topic-body">
        <h3>{esc(u["title"])}</h3>
        <p class="dr-summary">{esc(u["claim"])}</p>
        <p class="dr-qtitle">存疑</p>
        <p class="dr-summary">{esc(u["doubt"])}</p>
        <p class="dr-qtitle">暂定取舍</p>
        <p class="dr-summary">{esc(u["call"])}</p>
      </div>
    </article>""")
    units_html = "\n".join(units)
    return f"""<!DOCTYPE html>
<html lang="zh-CN" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#15171a">
<title>《{title}》｜全书精读</title>
<style>{PAGE_CSS}</style>
</head>
<body data-slug="{esc(slug)}" data-title="{title}">
<div class="dr-wrap">
  <a class="dr-back" href="combined.html">← 返回《{title}》全书领读</a>
  <header class="dr-head">
    <div class="dr-eyebrow">全书精读</div>
    <h1>《{title}》</h1>
    <p class="dr-sub">一句话判断 · 论证链 · 存疑与取舍 · 证据边界</p>
    <div class="dr-chips"><span class="dr-chip">AI 自主整理</span><span class="dr-chip">基于本站深读模块二次提炼</span><span class="dr-chip">非 App「AI 导读」原文</span></div>
  </header>
  <main>
    <section class="dr-sec">
      <h2>一句话判断</h2>
      <p class="dr-lead">{esc(d["verdict"])}</p>
    </section>
    <section class="dr-sec">
      <h2>作者是怎么把结论推出来的</h2>
      <p class="dr-lead">{esc(d["chain"])}</p>
    </section>
    <section class="dr-sec">
      <h2>几个得停下来想一想的地方</h2>
{units_html}
    </section>
    <section class="dr-sec">
      <h2>读完之后，哪些先不下结论</h2>
      <p class="dr-lead">{esc(d["boundary"])}</p>
    </section>
  </main>
  <footer class="dr-foot">
    <a href="../../../index.html">← 返回首页</a>　·　<a href="combined.html">全书领读（通读＋精读）</a>　·　<a href="outline.html">AI 大纲</a>
  </footer>
</div>
</body>
</html>
"""


def inject_combined_data(slug, d):
    """把模块追加进详情页数据源；幂等：带标记则整体替换。"""
    p = BOOKS / slug / "combined-data.html"
    if not p.exists():
        return None
    s = p.read_text(encoding="utf-8", errors="ignore")
    block = render_section(slug, d)
    if SEC_BEGIN in s:
        s = re.sub(re.escape(SEC_BEGIN) + r"[\s\S]*?" + re.escape(SEC_END),
                   lambda m: block, s, count=1)
    else:
        s = s.rstrip() + "\n" + block + "\n"
    return (p, s)


def cleanup_index():
    """首页不放模块：清掉早期版本注入的面板（若有）。"""
    if not INDEX.exists():
        return None
    s = INDEX.read_text(encoding="utf-8", errors="ignore")
    if PANEL_BEGIN not in s:
        return None
    s = re.sub(r"\s*" + re.escape(PANEL_BEGIN) + r"[\s\S]*?" + re.escape(PANEL_END),
               "", s, count=1)
    return (INDEX, s)


def cleanup_nav(slug):
    """清掉早期版本写进 combined.html 壳页的静态导航链接（reader.js 会重建导航）。"""
    p = BOOKS / slug / "combined.html"
    if not p.exists():
        return None
    s = p.read_text(encoding="utf-8", errors="ignore")
    if 'class="navlink dr-navlink"' not in s:
        return None
    s = re.sub(r'\s*<a class="navlink dr-navlink"[^>]*>[^<]*</a>', "", s, count=1)
    return (p, s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--seed", action="store_true", help="按 SEED 重写 data/deepread/*.json")
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
        r = inject_combined_data(slug, d)
        if r:
            writes.append(r)
        r = cleanup_nav(slug)
        if r:
            writes.append(r)
    r = cleanup_index()
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
