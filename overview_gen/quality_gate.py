# -*- coding: utf-8 -*-
"""quality_gate.py — overview.html 发布前质量门禁（overview_gen）。

对应 we-read / luoyu-reading 规范。生成 overview.html 后、publish 前跑一遍：
任何一项 FAIL 都阻断发布，避免漏出「机械模板占位 / 空白待补 / 0字节」的糟粕稿。

用法（库）：
    from overview_gen.quality_gate import check, check_all
    fails = check_all(["reading-notes/books/x/overview.html", ...])   # 返回失败文件数

用法（CLI）：
    python -m overview_gen.quality_gate path/to/overview.html
    python -m overview_gen.quality_gate reading-notes/books/*/overview.html   # 批量
退出码：0=全部通过，1=存在 FAIL。
"""
import sys
import re
import glob
import os

# 三个「取长补短」借来的栏目（迁移与行动 / 全书思考 / 复习标记）属增强项，
# 缺失仅 WARN，不阻断历史页面发布。
BORROWED_SECTIONS = ["迁移与行动", "全书思考", "复习"]


def check(path):
    try:
        html = open(path, encoding="utf-8").read()
    except Exception as e:
        return [(path, "FILE", "FAIL", "无法读取: %s" % e)]

    b = len(html.encode("utf-8"))
    res = []

    # 1) 空文件 / 极小值
    if b < 1500:
        res.append((path, "EMPTY", "FAIL", "文件仅 %d 字节，疑似失败跑批的空/残稿" % b))
    else:
        res.append((path, "EMPTY", "PASS", "%d 字节" % b))

    # 2) 机械模板占位（坏稿特征串）
    if re.search(r"用什么证据支撑全书主线|哪一步推理最容易被质疑", html):
        res.append((path, "MECH_TPL", "FAIL", "仍含机械模板占位句，未按书-specific 重写"))
    else:
        res.append((path, "MECH_TPL", "PASS", "无机械模板占位句"))

    # 3) 空白「待补」占位
    blank = (len(re.findall(r'class="tag">待补</span>', html))
             + len(re.findall(r'>\s*待补\s*<', html)))
    if blank > 0:
        res.append((path, "BLANK_TODO", "FAIL",
                    "存在 %d 处空白「待补」占位，须填真实内容或删除" % blank))
    else:
        res.append((path, "BLANK_TODO", "PASS", "无空白待补占位"))

    # 4) 数字/引文须有来源标签
    num_blocks = re.findall(
        r"[\u4e00-\u9fff]{0,12}(\d{3,}|[0-9]{1,3}%|19\d{2}年|20\d{2}年)[\u4e00-\u9fff]{0,12}",
        html)
    if num_blocks and "来源" not in html and "src" not in html.lower():
        res.append((path, "SRC_TAG", "WARN",
                    "含 %d 处数字/年份但未见来源标签，请核对规范" % len(num_blocks)))
    else:
        res.append((path, "SRC_TAG", "PASS", "数字/年份处有来源标注意识"))

    # 5) 取长补短：三个借来增强栏目是否存在（缺失仅 WARN）
    miss = [s for s in BORROWED_SECTIONS if s not in html]
    if miss:
        res.append((path, "BORROWED", "WARN",
                    "缺借来栏目: %s（增强项，历史页可后续补）" % ",".join(miss)))
    else:
        res.append((path, "BORROWED", "PASS", "含全部三个借来增强栏目"))

    return res


def check_all(paths):
    total_fail = 0
    print("%-54s%-12s%-6s说明" % ("文件", "规则", "结果"))
    print("-" * 112)
    for p in sorted(set(paths)):
        for (fp, rule, status, note) in check(p):
            name = os.path.relpath(p)
            print("%-54s%-12s%-6s%s" % (name, rule, status, note))
            if status == "FAIL":
                total_fail += 1
        print("-" * 112)
    if total_fail:
        print("\n❌ 共 %d 项 FAIL，阻断发布。" % total_fail)
    else:
        print("\n✅ 全部通过，可发布。")
    return total_fail


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="overview_gen.quality_gate",
                                 description="overview.html 发布前质量门禁")
    ap.add_argument("paths", nargs="+", help="overview.html 或含 overview.html 的目录")
    a = ap.parse_args(argv)
    paths = []
    for arg in a.paths:
        if os.path.isdir(arg):
            paths += glob.glob(os.path.join(arg, "**", "overview.html"), recursive=True)
        else:
            paths += glob.glob(arg)
    if not paths:
        print("未匹配到任何 overview.html")
        return 2
    return 1 if check_all(paths) else 0


if __name__ == "__main__":
    raise SystemExit(main())
