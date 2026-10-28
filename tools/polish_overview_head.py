"""通读页头部精修（2026-10-28 用户反馈）：

1. 删掉顶部卡片里的工具口径句「本页依据本书 outline.json（…）与公开资料建立。
   全书尚未开读，亲读范围 0%。大纲条目顺序…待亲读核对。」——
   读者不关心 outline.json、条目重排这些实现细节（「尚未开读」顶部 tag 已有）。
   保留书的第一句介绍与「来源：…」。
2. 「读前口碑」卡里 <p class="notice">（金框大提示条）改成 <p class="src">
   （小灰字），去掉边框——用户嫌那个框难看。
3. 「章节导读」整节移到「读前口碑」之后（两者都存在的书）。

幂等：三项各按特征判断，重复跑无变化。用法：
    python tools_polish_overview_head.py            # 预览
    python tools_polish_overview_head.py --write    # 落盘
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BOOKS = REPO / "reading-notes" / "books"
WRITE = "--write" in sys.argv


def cut_sections(s: str):
    """把正文切成 [前缀, sec0, sec1, ...]，每个 sec 从 <section 起到下一个 <section 前。"""
    starts = [m.start() for m in re.finditer(r"<section\b", s)]
    head = s[: starts[0]] if starts else s
    secs = [s[a:b] for a, b in zip(starts, starts[1:] + [len(s)])]
    return head, secs


def sec_key(sec: str):
    if 'aria-labelledby="pre-read-fit-title"' in sec:
        return "pre"
    if 'aria-labelledby="chapter-guide-title"' in sec:
        return "guide"
    return None


def drop_meta_sentence(s: str):
    """删「本页依据本书 outline.json …」到「来源：」前的工具口径句（含 <strong>）。"""
    new = re.sub(r"本页依据本书.*?(?=来源：)", "", s, count=1)
    return new, new != s


def notice_to_src(sec: str):
    if 'aria-labelledby="pre-read-fit-title"' not in sec:
        return sec, False
    new = sec.replace('<p class="notice">', '<p class="src">')
    return new, new != sec


def move_guide_after_pre(secs: list):
    keys = [sec_key(x) for x in secs]
    if "pre" not in keys or "guide" not in keys:
        return secs, False
    gi = keys.index("guide")
    pi = keys.index("pre")
    if gi == pi + 1:          # 已经紧跟在后
        return secs, False
    guide = secs.pop(gi)
    pi = keys.index("pre")    # pop 后重算
    secs.insert(pi + 1, guide)
    return secs, True


def main():
    changed = dropped = restyled = moved = 0
    for p in sorted(BOOKS.glob("*/overview.html")):
        s = p.read_text(encoding="utf-8")
        orig = s

        s2, d = drop_meta_sentence(s)
        if d:
            dropped += 1
        s = s2

        head, secs = cut_sections(s)
        secs2 = [notice_to_src(x)[0] for x in secs]
        n = sum(a != b for a, b in zip(secs, secs2))
        if n:
            restyled += n
        secs, m = move_guide_after_pre(secs2)
        if m:
            moved += 1
        s = head + "".join(secs)

        if s != orig:
            changed += 1
            print("  ~", p.parent.name)
            if WRITE:
                p.write_text(s, encoding="utf-8", newline="\n")

    tag = "WRITE" if WRITE else "PREVIEW"
    print("[%s] 改动 %d 本；删口径句 %d；notice→src %d 处；导读移位 %d 本"
          % (tag, changed, dropped, restyled, moved))


if __name__ == "__main__":
    main()
