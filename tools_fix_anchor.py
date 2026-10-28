"""把 mindmap.json 里锚点缺失的章，改成该书该章的首句原句。

为什么不接受模型给的引文：`gen_mindmap.py` 的 anchor 要过「逐字命中该章原句」校验，
不命中就留空并计入 `bad_anchor`。这个严格是对的（拒绝编造），但页面上空一格不如
给出该章真实的第一句——库里本来就有。

本脚本不调 LLM，纯本地：读 JSON → 用 `first_anchor()` 补 → 重算 evidence → 重渲染。
幂等，可重复跑。

用法：
    python tools_fix_anchor.py            # 只报告
    python tools_fix_anchor.py --write    # 修补并重渲染
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import gen_mindmap as M  # noqa: E402


def fix_one(slug: str, write: bool) -> tuple:
    p = M.DB_OUT / ("%s.json" % slug)
    if not p.exists():
        return (slug, "无 JSON", 0, 0)
    d = json.loads(p.read_text(encoding="utf-8"))
    bad = [c for c in d["chapters"] if not c.get("anchor_ok") or not c.get("anchor")]
    if not bad:
        return (slug, "无需修补", 0, 0)
    ctx = M.build_ctx(slug)
    if not ctx:
        return (slug, "库中无大纲", len(bad), 0)
    by_no = {c["no"]: c for c in ctx["chapters"]}
    filled = 0
    for c in bad:
        src = by_no.get(c["no"])
        if not src:
            continue
        a = M.first_anchor(src)
        if a:
            c["anchor"] = a
            c["anchor_ok"] = True
            filled += 1
    d["bad_anchor"] = [c["no"] for c in d["chapters"]
                       if not c.get("anchor_ok") or not c.get("anchor")]
    if write:
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        (M.BOOKS / slug / "mindmap.html").write_text(M.render(d), encoding="utf-8")
    return (slug, "已补" if write else "待补", len(bad), filled)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--slug")
    a = ap.parse_args(argv)
    files = ([M.DB_OUT / ("%s.json" % a.slug)] if a.slug
             else sorted(M.DB_OUT.glob("*.json")))
    tot_bad = tot_fill = done = 0
    for f in files:
        if f.name.startswith("_"):
            continue
        slug, st, nbad, nfill = fix_one(f.stem, a.write)
        if nbad:
            print("  %-6s %-50s 缺%3d 补%3d" % (st, slug[:50], nbad, nfill))
            tot_bad += nbad
            tot_fill += nfill
            done += 1
    print("涉及 %d 本 / 缺 %d 处 / 补 %d 处%s"
          % (done, tot_bad, tot_fill, "" if a.write else "（试运行，加 --write 落盘）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
