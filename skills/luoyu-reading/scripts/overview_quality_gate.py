#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
overview 质量门禁（对应 PRD 5.6.6 质量抽检 / F06 AI问答链路）

用途：weread-auto / luoyu-reading 生成 overview.html 后、commit 前跑一遍。
任何一项 FAIL 都阻断发布，避免再漏出「机械模板占位 / 空白待补 / 0字节」的糟粕稿。

用法：
    python3 overview_quality_gate.py path/to/overview.html
    python3 overview_quality_gate.py reading-notes/books/*/overview.html   # 批量

退出码：0=全部通过，1=存在 FAIL。
"""
import sys, re, glob, os

# ---- 规则：与 PRD 5.6.6 / pre-read-overview.html 模板对齐 ----
# 三个“取长补短”借来的栏目（迁移与行动 / 读完自测 / 复习标记），
# 属新增增强，缺失仅 WARN，不阻断历史页面发布。
BORROWED_SECTIONS = ["迁移与行动", "读完自测", "复习"]

def check(path):
    try:
        html = open(path, encoding="utf-8").read()
    except Exception as e:
        return [(path, "FILE", "FAIL", f"无法读取: {e}")]

    b = len(html.encode("utf-8"))
    res = []

    # 1) 空文件 / 极小值（PRD 5.4.5：输出为空应重试/转下一模型，不应提交）
    if b < 1500:
        res.append((path, "EMPTY", "FAIL", f"文件仅 {b} 字节，疑似失败跑批的空/残稿"))
    else:
        res.append((path, "EMPTY", "PASS", f"{b} 字节"))

    # 2) 机械模板占位（坏稿特征串：逐章复读「用什么证据支撑全书主线？哪一步推理最容易被质疑？」）
    if re.search(r"用什么证据支撑全书主线|哪一步推理最容易被质疑", html):
        res.append((path, "MECH_TPL", "FAIL", "仍含机械模板占位句，未按书-specific 重写"))
    else:
        res.append((path, "MECH_TPL", "PASS", "无机械模板占位句"))

    # 3) 空白「待补」占位：<span class="tag">待补</span> 或 >待补< 这类空壳
    blank = len(re.findall(r'class="tag">待补</span>', html)) + len(re.findall(r'>\s*待补\s*<', html))
    if blank > 0:
        res.append((path, "BLANK_TODO", "FAIL", f"存在 {blank} 处空白「待补」占位，须填真实内容或删除"))
    else:
        res.append((path, "BLANK_TODO", "PASS", "无空白待补占位"))

    # 4) AI 问书栏目：模板要求必须有「实际来源与获取／整理时间」真实填写
    if "AI 问书" in html or "ai-ask" in html.lower():
        src_line = re.search(r"实际来源与获取[／/]整理时间[：:]\s*([^\n<]{0,40})", html)
        val = (src_line.group(1).strip() if src_line else "")
        if not val or val in ("{{", "待补", "无"):
            res.append((path, "AIASK_SRC", "FAIL", "「AI 问书」来源/时间未真实填写（占位或缺失）"))
        else:
            res.append((path, "AIASK_SRC", "PASS", f"AI 问书来源已填: {val[:30]}"))
    else:
        # 没有 AI 问书栏目也允许，但必须在页内明确标「无平台 AI · 自主整理·非微信读书返回」
        if "非微信读书返回" in html or "无平台 AI" in html or "入口不可用" in html:
            res.append((path, "AIASK_SRC", "PASS", "已明确标注非微信读书返回/入口不可用（符合模板）"))
        else:
            res.append((path, "AIASK_SRC", "WARN", "既无 AI 问书栏目，也未标注无平台 AI 来源——须二选一"))

    # 5) 数字/引文须有来源标签（PRD：缺来源句子标「缺来源」不得发布）
    num_blocks = re.findall(r"[\u4e00-\u9fff]{0,12}(\d{3,}|[0-9]{1,3}%|19\d{2}年|20\d{2}年)[\u4e00-\u9fff]{0,12}", html)
    if num_blocks and "来源" not in html and "src" not in html.lower():
        res.append((path, "SRC_TAG", "WARN", f"含 {len(num_blocks)} 处数字/年份但未见来源标签，请核对 PRD 5.6"))
    else:
        res.append((path, "SRC_TAG", "PASS", "数字/年份处有来源标注意识"))

    # 6) 取长补短：三个借来的增强栏目是否存在（缺失仅 WARN，不阻断）
    miss = [s for s in BORROWED_SECTIONS if s not in html]
    if miss:
        res.append((path, "BORROWED", "WARN", f"缺借来栏目: {','.join(miss)}（模板升级后新增，历史页可后续补）"))
    else:
        res.append((path, "BORROWED", "PASS", "含全部三个借来增强栏目"))

    return res


def main():
    paths = []
    for a in sys.argv[1:]:
        if os.path.isdir(a):
            paths += glob.glob(os.path.join(a, "**", "overview.html"), recursive=True)
        else:
            paths += glob.glob(a)
    if not paths:
        print("用法: python3 overview_quality_gate.py <overview.html 或 目录>")
        sys.exit(2)

    total_fail = 0
    print(f"{'文件':<54}{'规则':<12}{'结果':<6}说明")
    print("-" * 112)
    for p in sorted(set(paths)):
        for (fp, rule, status, note) in check(p):
            name = os.path.relpath(p)
            print(f"{name:<54}{rule:<12}{status:<6}{note}")
            if status == "FAIL":
                total_fail += 1
        print("-" * 112)

    if total_fail:
        print(f"\n❌ 共 {total_fail} 项 FAIL，阻断发布。请回到生成流程按 PRD 5.6.6 修复后再提交。")
        sys.exit(1)
    else:
        print("\n✅ 全部通过，可发布。")
        sys.exit(0)


if __name__ == "__main__":
    main()
