"""只读验证迁移清单及相对文件；不安装、不联网、不改任何阅读状态。"""
import argparse
import json
import re
import sys
from pathlib import Path


def check(root):
    errors = []
    root = root.resolve()
    manifest_path = root / "skills/reading-team-bootstrap/team-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = {
        "reading-admin", "cue-qingyouji-reader", "wechat-reading-browser",
        "local-pdf-reader", "weread-auto",
    }
    roles = manifest["roles"]
    keys = [r["role_key"] for r in roles]
    if set(keys) != expected or len(keys) != len(expected):
        errors.append("角色缺失或重复")
    files = [manifest["launcher"], manifest["shared_memory"]]
    files += [f"skills/{manifest[k]}/SKILL.md" for k in ("bootstrap_skill", "shared_skill")]
    for role in roles:
        files += [role["skill_file"], role["memory_file"]]
        if role["skill_file"] != f"skills/{role['skill']}/SKILL.md":
            errors.append(f"Skill路径与名称不一致: {role['role_key']}")
    for relative in files:
        p = (root / relative).resolve()
        if not p.is_relative_to(root):
            errors.append(f"越出包根目录: {relative}")
            continue
        if not p.is_file() or not p.read_text(encoding="utf-8").strip():
            errors.append(f"缺少或空文件: {relative}")
    # 仅扫描新增便携角色资料，不把原仓库的历史协调状态当迁移配置。
    paths = [root / r["skill_file"] for r in roles if r["role_key"] != "reading-admin"]
    paths += [root / r["memory_file"] for r in roles]
    paths += list((root / "skills/reading-team-bootstrap/references").glob("*.md"))
    paths += [manifest_path, root / manifest["launcher"]]
    sensitive = [
        r"gh[pousr]_[A-Za-z0-9_]{20,}", r"github_pat_[A-Za-z0-9_]{20,}",
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        r"\{\{secret:", r"(?i)[A-Z]:\\Users\\[^\s`]+",
        r"/home/(?:ubuntu|[^/\s]+)/", r"/workspace/",
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    ]
    for p in paths:
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8")
        if "[TODO" in text:
            errors.append(f"未完成占位: {p.relative_to(root)}")
        if any(re.search(pattern, text) for pattern in sensitive):
            errors.append(f"检测到凭据引用、机器路径或个人UID格式，需人工核查: {p.relative_to(root)}")
        for target in re.findall(r"\]\(([^)]+)\)", text):
            if "://" in target or target.startswith("#"):
                continue
            linked = (p.parent / target.split("#", 1)[0]).resolve()
            if not linked.is_relative_to(root) or not linked.is_file():
                errors.append(f"无效本地链接: {p.relative_to(root)} -> {target}")
    return errors, len(files), len(paths)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    args = parser.parse_args()
    try:
        errors, files, scanned = check(args.repo)
    except (OSError, ValueError, KeyError) as exc:
        print(f"FAIL: {exc}")
        return 1
    if errors:
        print("\n".join(f"FAIL: {e}" for e in errors))
        return 1
    print(f"PASS: 5个角色，{files}个必需入口，{scanned}个便携资料文件；只读检查，无安装或运行。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
