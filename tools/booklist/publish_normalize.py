#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布「首页卡片模板规范化」结果：以当下远端 git 源 + 当下线上产物分别修复后双写上线。

与 publish_booklist.py 同构，区别只在修复步骤换成本目录的 normalize_oldcards.py。

为什么要两边分别取基准：
  - 云端 compose 产线会持续往 main:index.html 追加新书卡；
  - 产物站根 key index.html 是用户实际访问的页面，与 git 源通常只差换行压缩。
  直接用旧副本覆盖会把云端新追加的书卡冲掉。两边各取当下最新版，只改
  archive-card 卡片本身，书单块 / 已阅面板 / tab / 其它内容逐字节不变。

强校验（--check 与实际发布都会做）：
  1. 修复后 normalize_oldcards.py check 必须归零；
  2. 剥离「所有 archive-card」后，前后文本必须逐字节相等（证明只动卡片）。

凭据全部来自环境变量，脚本内不含任何密钥：
  GITHUB_TOKEN / WR_AUTH_DIR、QINIU_AK / QINIU_SK、WR_REPO / WR_SITE（可选）

用法：
  python3 publish_normalize.py --check
  python3 publish_normalize.py
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
NORM = os.path.join(HERE, "normalize_oldcards.py")
REPO = os.environ.get("WR_REPO", "ae6623/we-read")
SITE = os.environ.get("WR_SITE", "https://reader.js-dev.cn/")
BUCKET = os.environ.get("QINIU_BUCKET", "we-read-assets")
UC_QUERY = "https://uc.qbox.me/v1/query"

CARD_RE = re.compile(
    r'[ \t]*(?:<!-- preread-card:[^\s]+ -->\s*)?'
    r'<article class="[^"]*archive-card[^"]*"[^>]*>.*?</article>'
    r'(?:\s*<!-- /preread-card -->)?\n?', re.S)


def b64u(b):
    return base64.urlsafe_b64encode(b).decode("ascii")


def token():
    t = os.environ.get("GITHUB_TOKEN")
    if t:
        return t
    d = os.environ.get("WR_AUTH_DIR")
    cred = os.path.join(d, "git-credentials") if d else None
    if cred and os.path.exists(cred):
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
            "User-Agent": "workbuddy-normalize",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
    )
    # GitHub 大 blob（>1MB）偶发 IncompleteRead，仅对 GET 重试；写操作不重试以免重复提交
    raw = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(r, timeout=40) as resp:
                raw = resp.read()
            break
        except OSError:
            if method != "GET" or attempt == 3:
                raise
            time.sleep(0.5 * (attempt + 1))
    return json.loads(raw.decode("utf-8", "replace"))


def http_get(url):
    r = urllib.request.Request(url, headers={"User-Agent": "workbuddy-normalize"})
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(r, timeout=40) as resp:
                return resp.read()
        except OSError as e:
            last = e
            if attempt < 3:
                time.sleep(0.5 * (attempt + 1))
    # 大文件在本网络下 urllib 读数易截断，curl 兜底
    try:
        out = subprocess.run(["curl", "-fsSL", "--max-time", "60", url],
                             capture_output=True, check=True)
        if out.stdout:
            return out.stdout
    except Exception:
        pass
    raise last


def strip_cards(s):
    """剥离所有 archive-card 卡片，剩下的用于逐字节比对。"""
    return CARD_RE.sub("", s)


def normalize(text, tag):
    src = Path("/tmp/norm_%s_in.html" % tag)
    out = Path("/tmp/norm_%s_out.html" % tag)
    src.write_text(text, encoding="utf-8")
    subprocess.run([sys.executable, NORM, "fix", "--file", str(src), "--out", str(out)],
                   check=True, stdout=subprocess.DEVNULL)
    new = out.read_text(encoding="utf-8")
    # 门禁：修复后旧卡必须归零
    chk = subprocess.run([sys.executable, NORM, "check", "--file", str(out)],
                         capture_output=True, text=True)
    if chk.returncode != 0:
        raise RuntimeError("check 未通过 [%s]: %s" % (tag, chk.stdout[-400:]))
    # 强校验：卡片以外逐字节不变
    if strip_cards(new) != strip_cards(text):
        raise RuntimeError("修复改动了卡片以外的内容: " + tag)
    return new


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
    ap.add_argument("--message", default="fix(home): 统一首页卡片模板，补齐 data-slug/标题链接/标准结构，消除读前通读旧模板与重复文案")
    ap.add_argument("--git-file", help="本地 git 源 index.html（须与当前 HEAD 的 blob 逐字节一致）；用于绕开 GitHub 大文件下载不稳")
    ap.add_argument("--site-file", help="本地线上产物 index.html；不指定则从线上站点实时抓取")
    ap.add_argument("--expect-head", help="期望的远端 main HEAD sha（写前二次校验，防止提交瞬间被产线覆盖）")
    args = ap.parse_args()

    ref = gh("GET", "/git/ref/heads/main")
    head_sha = ref["object"]["sha"]
    commit = gh("GET", "/git/commits/" + head_sha)
    tree_sha = commit["tree"]["sha"]

    # 大 index.html 下载在本网络下会 IncompleteRead/超时；支持传入本地已校验基准。
    if args.git_file:
        git_html = Path(args.git_file).read_text(encoding="utf-8")
        # 用 git blob sha 证明本地基准与当前 HEAD 的 index.html 逐字节一致
        blob = hashlib.sha1(b"blob " + str(len(git_html.encode("utf-8"))).encode()
                           + b"\0" + git_html.encode("utf-8")).hexdigest()
        tree = gh("GET", "/git/trees/" + tree_sha)
        entry = next(x for x in tree["tree"] if x["path"] == "index.html")
        if blob != entry["sha"]:
            raise RuntimeError("本地 git 基准与 HEAD index.html 不一致（本地 %s / 远端 %s），拒绝提交"
                               % (blob[:12], entry["sha"][:12]))
        print("本地 git 基准 blob sha 校验通过:", blob[:12])
    else:
        git_html = http_get("https://raw.githubusercontent.com/%s/%s/index.html"
                            % (REPO, head_sha)).decode("utf-8")
    site_html = (Path(args.site_file).read_text(encoding="utf-8") if args.site_file
                 else http_get(SITE).decode("utf-8"))

    print("远端 main:", head_sha[:12], "| git index.html %d 字符" % len(git_html))
    print("线上产物: %d 字符" % len(site_html))

    new_git = normalize(git_html, "git")
    new_site = normalize(site_html, "site")
    print("规范化后: git %d 字符 (+%d) / 产物 %d 字符 (+%d)" % (
        len(new_git), len(new_git) - len(git_html),
        len(new_site), len(new_site) - len(site_html)))
    print("卡片外内容: 逐字节一致（强校验通过）")

    if args.check:
        print("--check 模式：未写远端")
        return 0

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
    # 写前二次校验：若产线在构建期间又推了新提交，放弃本次 ref 更新，避免覆盖
    cur = gh("GET", "/git/ref/heads/main")["object"]["sha"]
    expected = args.expect_head or head_sha
    if cur != expected:
        raise RuntimeError("写前检测到远端 HEAD 已变化（期望 %s / 当前 %s），已放弃更新 ref，请重跑"
                           % (expected[:12], cur[:12]))
    gh("PATCH", "/git/refs/heads/main", {"sha": nc["sha"]})
    print("git 已提交:", nc["sha"][:12], "| 写前 HEAD 校验通过")

    sp = Path("/tmp/norm_site_final.html")
    sp.write_text(new_site, encoding="utf-8")
    size, host = upload_index(sp)
    print("产物站已上传: index.html %d B via %s" % (size, host))
    print("完成。CDN cache-control=max-age=60，最多 1 分钟后全网生效。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
