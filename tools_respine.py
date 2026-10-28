"""重排某本书的主干分组（不改章级 gist/role/anchor）。

用途：`gen_mindmap.py` 按模型给的 spine 分组，遇到两类编排型书籍会失准：
  1. 元信息章（版权/序言/校注凡例/作者简介/导读）被抬成一条主干，
     和真正的正文主干并列，读者会误以为是全书的一条论证线；
  2. 同一部作品的「原文层 / 译文层 / 释义层」被压成一条线，
     看不出它们是同一批内容的重复呈现。

本工具只改 spine（线的名字、顺序、章归属）和 thesis，chapters 的
gist / role / anchor / 证据密度全部保留，因此重排不损失已生成的判断。

patch 文件格式（JSON）：
    {
      "<slug>": {
        "thesis": {"claim": "...", "boundary": "..."},   // 可省略
        "reorder": true,          // 按 spine 里章节出现的顺序重排 chapters
        "spine": [
          {"id": "A", "label": "...", "why": "...", "chapters": [1, 2, 3]}
        ]
      }
    }

漏章的兜底：patch 没覆盖到的章，归到它在原 spine 里所属那条线的位置，
并在报告里列出来（不静默丢章）。

用法：
    python tools_respine.py docs/mindmap-respine.json           # 预演
    python tools_respine.py docs/mindmap-respine.json --write   # 落盘并重渲染
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import gen_mindmap as M  # noqa: E402


def apply_one(slug: str, spec: dict, write: bool) -> str:
    p = M.DB_OUT / ("%s.json" % slug)
    if not p.exists():
        return "无 JSON"
    d = json.loads(p.read_text(encoding="utf-8"))
    chs = {c["no"]: c for c in d["chapters"]}
    old_spine = {c["no"]: c.get("spine") for c in d["chapters"]}

    new_spine, seen = [], set()
    for s in spec.get("spine") or []:
        nums = [int(n) for n in (s.get("chapters") or []) if int(n) in chs]
        nums = [n for n in nums if n not in seen]
        if not nums:
            continue
        seen.update(nums)
        new_spine.append({"id": s.get("id") or "?",
                          "label": (s.get("label") or "").strip(),
                          "why": (s.get("why") or "").strip(),
                          "chapters": nums})
    missing = [n for n in chs if n not in seen]
    if missing:
        # 不静默丢章：按原线归回就近的那条，实在没有就并到第一条
        for n in missing:
            tgt = None
            for s in new_spine:
                if old_spine.get(n) and any(old_spine.get(m) == old_spine.get(n)
                                            for m in s["chapters"]):
                    tgt = s
                    break
            (tgt or new_spine[0])["chapters"].append(n)
        missing = sorted(missing)

    owner = {}
    for s in new_spine:
        for n in s["chapters"]:
            owner[n] = s["id"]
    for n, c in chs.items():
        c["spine"] = owner[n]

    if spec.get("reorder"):
        order = [n for s in new_spine for n in s["chapters"]]
        d["chapters"] = [chs[n] for n in order]

    d["spine"] = new_spine
    th = spec.get("thesis")
    if th:
        d["thesis"] = {"claim": (th.get("claim") or d["thesis"].get("claim") or "").strip(),
                       "boundary": (th.get("boundary") or d["thesis"].get("boundary") or "").strip()}

    if write:
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        (M.BOOKS / slug / "mindmap.html").write_text(M.render(d), encoding="utf-8")
    tail = ("  ⚠ 漏章 %d：%s" % (len(missing), missing[:8])) if missing else ""
    return "%s 主干=%d 章=%d%s" % ("已写" if write else "预演",
                                  len(new_spine), len(d["chapters"]), tail)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("patch")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    raw = json.loads(Path(a.patch).read_text(encoding="utf-8"))
    for slug, spec in raw.items():
        if slug.startswith("_"):
            continue
        print("  %-52s %s" % (slug[:52], apply_one(slug, spec, a.write)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
