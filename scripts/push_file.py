#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 gh（已认证的 token）把本地文件 PUT 到 ae6623/we-read 仓库。
用法: python3 push_one.py <本地文件> <仓库内路径> <提交信息>
已存在则带 sha 更新，不存在则新建。branch=main。
"""
import sys, json, base64, subprocess, tempfile, os

def main():
    if len(sys.argv) < 4:
        print("用法: push_one.py <本地文件> <仓库内路径> <提交信息>")
        sys.exit(2)
    local, repo_path, msg = sys.argv[1], sys.argv[2], sys.argv[3]
    content = open(local, "rb").read()
    b64 = base64.b64encode(content).decode()

    # 取现有 sha（用于更新）
    sha = None
    r = subprocess.run(
        ["gh", "api", f"repos/ae6623/we-read/contents/{repo_path}", "--jq", ".sha"],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        s = r.stdout.strip().strip('"')
        if s and s != "null":
            sha = s

    payload = {"message": msg, "content": b64, "branch": "main"}
    if sha:
        payload["sha"] = sha
    tf = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump(payload, tf)
    tf.close()
    r2 = subprocess.run(
        ["gh", "api", "-X", "PUT", f"repos/ae6623/we-read/contents/{repo_path}", "--input", tf.name],
        capture_output=True, text=True,
    )
    os.unlink(tf.name)
    if r2.returncode == 0:
        try:
            j = json.loads(r2.stdout)
            print(f"OK {repo_path} -> commit {j.get('commit',{}).get('sha','?')[:10]}")
        except Exception:
            print(f"OK {repo_path} (无 JSON 回执)")
    else:
        print(f"ERR {repo_path}: {r2.stderr[:400]}")

if __name__ == "__main__":
    main()
