#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布书单：以「当前远端 git 源」与「当前线上产物」分别注入后双写上线。

为什么两边分别取基准：
  - git 源（main:index.html）会被云端 compose 持续追加新书卡；
  - 产物站根 key index.html 是用户实际访问的页面，与 git 源通常只差换行压缩。
  直接用旧副本覆盖会把云端新追加的书卡冲掉。两边各取当下最新版，
  只替换 <!-- booklist:begin/end --> 块，书单块外零改动。

流程：
  1. GitHub Git Data API 读 main 的 index.html（不 clone、不 fetch）
  2. GET 产物站首页读当前线上版本
  3. 各自跑 inject_booklist.py（幂等：先 strip 旧块再注入）
  4. git 侧：blob → tree(base_tree) → commit → PATCH ref
  5. 产物站侧：七牛 Kodo putPolicy 直传根 key index.html

凭据（脚本内不含任何密钥，全部来自环境变量）：
  GITHUB_TOKEN           GitHub PAT；或设 WR_AUTH_DIR 指向含 git-credentials 的目录
  QINIU_AK / QINIU_SK    七牛凭据；--check 模式不需要
  WR_REPO / WR_SITE      可选，覆盖仓库与站点域名
  WR_AUTH_DIR            可选，凭据目录

用法：
  python3 publish_booklist.py --check     # 只预览差异，不写远端
  python3 publish_booklist.py             # 实际双写上线
"""
import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
INJECT = os.path.join(HERE, "inject_booklist.py")
REPO = os.environ.get("WR_REPO", "ae6623/we-read")
SITE = os.environ.get("WR_SITE", "https://reader.js-dev.cn/")
BUCKET = os.environ.get("QINIU_BUCKET", "we-read-assets")
UC_QUERY = "https://uc.qbox.me/v1/query"

B = "<!-- booklist:begin -->"
E = "<!-- booklist:end -->"


def b64u(b):
    return base64.urlsafe_b64encode(b).decode("ascii")


def token():
    t = os.environ.get("GITHUB_TOKEN")
    if t:
        return t
    d = os.environ.get("WR_AUTH_DIR")
    cred = os.path.join(d, "git-credentials") if d else None
    if cred and os.path.exists(cred):
        # 形如 https://<user>:<token>@github.com
        return open(cred, encoding="utf-8").read().strip().split(":", 2)[-1].split("@")[0]
    raise RuntimeError("缺少 GITHUB_TOKEN（或设置 WR_AUTH_DIR 指向凭据目录）")


def qiniu_creds():
    ak, sk = os.environ.get("QINIU_AK"), os.environ.get("QINIU_SK")
    if not (ak and sk):
        raise RuntimeError("缺少 QINIU_AK / QINIU_SK 环境变量")
    return ak, sk


def gh(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(
        "https://api.github.com/repos/%s%s" % (REPO, path),
        data=data, method=method,
        headers={
            "Authorization": "Bearer " + token(),
            "User-Agent": "workbuddy-booklist",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(r, timeout=40) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def http_get(url):
    r = urllib.request.Request(url, headers={"User-Agent": "workbuddy-booklist"})
    with urllib.request.urlopen(r, timeout=40) as resp:
        return resp.read()


def strip_blocks(s):
    return re.sub(re.escape(B) + r"\s*.*?" + re.escape(E) + r"\n?", "", s, flags=re.S)


def inject(text, tag):
    p = "/tmp/booklist_%s.html" % tag
    Path(p).write_text(text, encoding="utf-8")
    subprocess.run([sys.executable, INJECT, "--file", p], check=True)
    out = Path(p).read_text(encoding="utf-8")
    assert strip_blocks(out) == strip_blocks(text), "注入改动了书单块以外的内容: " + tag
    return out


# ---- 七牛 Kodo 直传（复用 cdn-upload.py 的协议实现，凭据改由环境变量注入）----

def up_hosts(ak):
    url = UC_QUERY + "?" + urllib.parse.urlencode({"ak": ak, "bucket": BUCKET})
    with urllib.request.urlopen(url, timeout=20) as r:
        d = json.load(r)
    hosts, seen = [], set()
    for scheme in ("https", "http"):
        for h in (d.get(scheme) or {}).get("up") or []:
            if not isinstance(h, str):
                continue
            for tok in h.split():
                if tok.startswith("http"):
                    h = tok
                    break
            if h.startswith("http") and h not in seen:
                seen.add(h)
                hosts.append(h)
    hosts.sort(key=lambda x: 0 if x.startswith("https") else 1)
    return hosts or ["https://upload.qiniup.com"]


def upload_token(ak, sk, key, deadline):
    policy = json.dumps({"scope": BUCKET + ":" + key, "deadline": deadline},
                        separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    enc = b64u(policy)
    sign = b64u(hmac.new(sk.encode(), enc.encode("ascii"), hashlib.sha1).digest())
    return ak + ":" + sign + ":" + enc


def put(host, key, path, tok):
    boundary = "----wr" + uuid.uuid4().hex
    parts = []
    for name, value in (("token", tok), ("key", key)):
        parts.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                      % (boundary, name, value)).encode("utf-8"))
    parts.append(("--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"%s\"\r\n"
                  "Content-Type: text/html; charset=utf-8\r\n\r\n"
                  % (boundary, path.name)).encode("utf-8"))
    parts.append(path.read_bytes())
    parts.append(("\r\n--%s--\r\n" % boundary).encode("utf-8"))
    req = urllib.request.Request(
        host.rstrip("/") + "/", data=b"".join(parts), method="POST",
        headers={"Content-Type": "multipart/form-data; boundary=" + boundary})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def upload_index(path):
    ak, sk = qiniu_creds()
    hosts = up_hosts(ak)
    tok = upload_token(ak, sk, "index.html", int(time.time()) + 3600)
    last = None
    for h in hosts:
        try:
            ret = put(h, "index.html", path, tok)
            if ret.get("key") != "index.html":
                raise RuntimeError("返回 key 不匹配: " + str(ret)[:100])
            return path.stat().st_size, h
        except Exception as e:
            last = e
    raise RuntimeError("所有上传域名失败: %s" % last)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--message", default="feat(booklist): 书单链接指向最新版模板 + 新增领域路径")
    args = ap.parse_args()

    # 1) 当前远端 git 源
    ref = gh("GET", "/git/ref/heads/main")
    head_sha = ref["object"]["sha"]
    commit = gh("GET", "/git/commits/" + head_sha)
    tree_sha = commit["tree"]["sha"]
    tree = gh("GET", "/git/trees/" + tree_sha)
    entry = next(x for x in tree["tree"] if x["path"] == "index.html")
    blob = gh("GET", "/git/blobs/" + entry["sha"])
    git_html = base64.b64decode(blob["content"]).decode("utf-8")

    # 2) 当前线上产物
    site_html = http_get(SITE).decode("utf-8")

    print("远端 main:", head_sha[:12], "| git index.html %d 字符" % len(git_html))
    print("线上产物: %d 字符" % len(site_html))

    new_git = inject(git_html, "git")
    new_site = inject(site_html, "site")
    print("注入后: git %d 字符 (+%d) / 产物 %d 字符 (+%d)" % (
        len(new_git), len(new_git) - len(git_html),
        len(new_site), len(new_site) - len(site_html)))

    if args.check:
        print("--check 模式：未写远端")
        return 0

    # 3) git 侧：blob → tree → commit → ref
    nb = gh("POST", "/git/blobs", {
        "content": base64.b64encode(new_git.encode("utf-8")).decode("ascii"),
        "encoding": "base64",
    })
    nt = gh("POST", "/git/trees", {
        "base_tree": tree_sha,
        "tree": [{"path": "index.html", "mode": "100644", "type": "blob", "sha": nb["sha"]}],
    })
    nc = gh("POST", "/git/commits", {
        "message": args.message,
        "tree": nt["sha"],
        "parents": [head_sha],
    })
    gh("PATCH", "/git/refs/heads/main", {"sha": nc["sha"]})
    print("git 已提交:", nc["sha"][:12])

    # 4) 产物站侧：直传根 key
    sp = Path("/tmp/booklist_site.html")
    sp.write_text(new_site, encoding="utf-8")
    size, host = upload_index(sp)
    print("产物站已上传: index.html %d B via %s" % (size, host))
    print("完成。CDN cache-control=max-age=60，最多 1 分钟后全网生效。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
