# -*- coding: utf-8 -*-
"""cli.py — overview_gen 统一命令行入口。

完整流程（以一本书为例）：
    # 1) 解析大纲（确定性，不需要 LLM）
    python -m overview_gen parse outline.html -o mybook_parsed.json

    # 2) 撰写该书的 BOOK 配置，加到 books.py 的 BOOKS 里（见 README）

    # 3) 生成 overview.html（build + 自动跑质量门禁）
    python -m overview_gen gen --slug <slug> --parsed mybook_parsed.json -o overview.html

    # 4) 发布到 we-read 站点仓库（reading-notes/books/<slug>/overview.html）
    python -m overview_gen publish --slug <slug> --file overview.html

子命令：
    parse   解析 outline.html -> parsed.json
    build   用 books.py 里的配置 + parsed.json 渲染 overview.html
    gen     build 的快捷版：渲染后立即跑质量门禁
    gate    质量门禁（可批量，支持目录）
    publish 发布 overview.html 到站点仓库（复用根目录 gh_api.py）
"""
import argparse
import sys
import os

from .parse_outline import parse_outline
from .build_overview import build
from . import books as books_mod
from .quality_gate import check_all
from .publish import publish_local_file, load_cfg


def _default_parsed(slug):
    return "%s_parsed.json" % slug


def _default_out(slug):
    return "%s_overview.html" % slug


def _aiqa_html(book_title):
    """读 AI 问书真实问答（优先 SQLite 库，回退旧 JSON），渲染通读页「快答实录」区块。
    无数据返回 ''；同一问题只保留最新一条，最多展示 6 问。"""
    try:
        from weread_store import load_aiqa
        items = load_aiqa(book_title, limit=6)
    except Exception:
        items = []
    if not items:
        return ""
    blocks = []
    for i in items:
        a = (i.get("a") or "").strip().replace("\n", "<br>")
        blocks.append('<div class="aiqa-item"><h3>%s</h3><p>%s</p></div>'
                      % (i.get("q") or "", a))
    return ''.join(blocks)


def _quiz_answers(book_title):
    """读读完自测 3 问的补答（优先 SQLite 库，回退旧 JSON）；无则空列表。"""
    try:
        from weread_store import load_quiz
        return load_quiz(book_title)
    except Exception:
        return []


def _load_aiqa_data(slug):
    cfg = books_mod.BOOKS.get(slug) or {}
    title = cfg.get("title") or ""
    return _aiqa_html(title), _quiz_answers(title)


def cmd_parse(args):
    text = sys.stdin.read() if args.outline == '-' else open(args.outline, encoding="utf-8").read()
    chapters = parse_outline(text)
    out = args.output or _default_parsed(_slug_from_path(args.outline))
    with open(out, "w", encoding="utf-8") as f:
        import json
        json.dump(chapters, f, ensure_ascii=False, indent=1)
    print("%s -> %s 章节=%d" % (args.outline, out, len(chapters)))
    return 0


def _slug_from_path(path):
    base = os.path.basename(path)
    return base.replace("_outline.html", "").replace(".html", "")


def cmd_build(args):
    if args.slug not in books_mod.BOOKS:
        print("✗ 配置未找到：%s。请在 books.py 的 BOOKS 里加一项。" % args.slug)
        return 2
    parsed_path = args.parsed or _default_parsed(args.slug)
    import json
    chapters = json.load(open(parsed_path, encoding="utf-8"))
    aiqa_html, quiz_answers = _load_aiqa_data(args.slug)
    html = build(books_mod.BOOKS[args.slug], chapters,
                 aiqa_html=aiqa_html, quiz_answers=quiz_answers)
    out = args.output or _default_out(args.slug)
    open(out, "w", encoding="utf-8").write(html)
    style = html.count("<style")
    print("%s 字节=%d ch-item=%d 内联<style>=%d -> %s"
          % (out, len(html.encode("utf-8")), html.count('class="ch-item"'),
             style, out))
    if style:
        print("⚠ 检测到内联 <style>，违反 we-read 前端铁律（必须外置共享 CSS）。")
        return 1
    return 0


def cmd_gen(args):
    rc = cmd_build(args)
    if rc:
        return rc
    out = args.output or _default_out(args.slug)
    fails = check_all([out])
    return 1 if fails else 0


def cmd_gate(args):
    paths = []
    import glob
    for a in args.paths:
        if os.path.isdir(a):
            paths += glob.glob(os.path.join(a, "**", "overview.html"), recursive=True)
        else:
            paths += glob.glob(a)
    if not paths:
        print("未匹配到任何 overview.html")
        return 2
    return 1 if check_all(paths) else 0


def cmd_publish(args):
    cfg = load_cfg(args.config)
    return 0 if publish_local_file(
        args.slug, args.file, config_path=args.config,
        message=args.message, dry_run=args.dry_run)[0] else 1


def cmd_auto(args):
    """通用一键生产：给书名（--names，换行/逗号分隔；或逐行从 stdin），
    匹配 → 解析大纲 → 自动派生或用手写精修配置 → 生成 →（可选）发布。"""
    from .auto import auto_generate, find_book
    if args.names:
        names = args.names
    elif not sys.stdin.isatty():
        names = sys.stdin.read()
    else:
        names = ""
    results = auto_generate(names, publish=args.publish, dry_run=args.dry_run)
    if not results:
        print("未解析到任何书名（--names 留空且无 stdin 输入）。")
        return 2
    ok = 0
    for r in results:
        flag = {"ok": "✅", "missing_outline": "⚠️ ", "parse_error": "❌",
                "empty_outline": "❌", "build_error": "❌", "gate_fail": "❌",
                "publish_fail": "❌", "publish_error": "❌"}.get(r["status"], "❓")
        act = {"created": "新建", "compensated": "补偿"}.get(r["action"] or "", "")
        line = "%s 《%s》 slug=%s %s" % (flag, r["title"], r["slug"], act)
        if r["status"] == "ok":
            line += "  字节=%d 发布=%s" % (r["bytes"], r["published"])
            ok += 1
        else:
            line += "  [%s] %s" % (r["status"], (r["error"] or "")[:160])
        print(line)
    print("\n成功 %d / %d。" % (ok, len(results)))
    return 0 if ok == len(results) else 1


def cmd_books(args):
    """列出 data/overview 下已有书（及其大纲/概览状态）。"""
    from .auto import iter_data_books, OVERVIEW_ROOT, outline_path, overview_cache_path
    rows = []
    for slug, m in iter_data_books():
        rows.append((slug, m.get("title"), m.get("author"),
                     outline_path(slug).exists(), overview_cache_path(slug).exists()))
    if not rows:
        print("data/overview/ 下还没有任何已生成的书。")
        print("把某书的微信读书 AI 大纲放到 data/overview/<slug>/outline.html，"
              "再跑：python -m overview_gen auto --names \"书名\"")
        return 0
    print("%-40s%-22s%s" % ("slug", "书名", "大纲/概览"))
    print("-" * 100)
    for slug, title, author, has_o, has_v in rows:
        print("%-40s%-22s大纲=%s 概览=%s" % (slug, (title or "")[:20],
                                             "✓" if has_o else "✗", "✓" if has_v else "✗"))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="overview_gen",
                                 description="读前通读（全书视角）页生成器")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("parse", help="解析 outline.html -> parsed.json")
    p.add_argument("outline", help="outline.html 路径（'-' = stdin）")
    p.add_argument("-o", "--output", default="", help="输出 parsed.json")
    p.set_defaults(func=cmd_parse)

    p = sub.add_parser("build", help="渲染 overview.html（仅 build，不跑门禁）")
    p.add_argument("--slug", required=True)
    p.add_argument("--parsed", default="", help="parsed.json 路径")
    p.add_argument("-o", "--output", default="", help="输出 overview.html")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("gen", help="build + 自动质量门禁")
    p.add_argument("--slug", required=True)
    p.add_argument("--parsed", default="", help="parsed.json 路径")
    p.add_argument("-o", "--output", default="", help="输出 overview.html")
    p.set_defaults(func=cmd_gen)

    p = sub.add_parser("gate", help="质量门禁（可批量/目录）")
    p.add_argument("paths", nargs="+")
    p.set_defaults(func=cmd_gate)

    p = sub.add_parser("publish", help="发布 overview.html 到站点仓库")
    p.add_argument("--slug", required=True)
    p.add_argument("--file", required=True, help="要发布的 overview.html 路径")
    p.add_argument("--config", default="", help="we-read-auto 的 config.json 路径")
    p.add_argument("--message", default="", help="提交信息")
    p.add_argument("--dry-run", action="store_true", help="只检查差异不提交")
    p.set_defaults(func=cmd_publish)

    p = sub.add_parser("auto", help="通用一键生产：给书名 → 匹配 → 自动生成")
    p.add_argument("--names", default="", help="书名（换行/逗号分隔；也可用 stdin 逐行输入）")
    p.add_argument("--publish", action="store_true", help="生成后发布到站点仓库")
    p.add_argument("--dry-run", action="store_true", help="发布时只检查差异不提交")
    p.set_defaults(func=cmd_auto)

    p = sub.add_parser("books", help="列出 data/overview 下已有书")
    p.set_defaults(func=cmd_books)

    a = ap.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
