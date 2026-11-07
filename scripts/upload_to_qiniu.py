#!/usr/bin/env python3
"""把静态资源上传到七牛云（国内 CDN），保持目录结构。

为什么用它：we-read-assets 那套（EPUB/PDF）继续走 GitHub Pages，阅读器不动；
这个脚本是给「以后的图片、音频、封面、大文档」准备的上传通道，绑在
`cdn.js-dev.cn` 这种已备案域名上，读者从国内节点拿，比 GitHub Pages 快。

不需要装 SDK，只用标准库 + 七牛 HTTP API。

准备（控制台一次性）：
  1. 创建空间，访问控制选「公开」；
  2. 绑定自定义域名（如 cdn.js-dev.cn），按提示加 CNAME；
  3. 申请免费 HTTPS 证书；
  4. 跨域 CORS 允许 GET/HEAD/OPTIONS，Origin 填 *（页面要跨域 fetch 时必须）。

用法：
    set QINIU_AK=xxx & set QINIU_SK=xxx        # Windows
    export QINIU_AK=xxx QINIU_SK=xxx           # bash
    python scripts/upload_to_qiniu.py --bucket we-read-assets --dry-run
    python scripts/upload_to_qiniu.py --bucket we-read-assets --dir assets/img --prefix assets/img
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import mimetypes
import os
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UC_HOST = "https://uc.qbox.me"


def urlsafe_b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def upload_token(ak: str, sk: str, bucket: str, key: str, ttl: int = 3600) -> str:
    policy = json.dumps({"scope": f"{bucket}:{key}", "deadline": int(time.time()) + ttl}, separators=(",", ":"))
    encoded = urlsafe_b64(policy.encode())
    sign = hmac.new(sk.encode(), encoded.encode(), hashlib.sha1).digest()
    return f"{ak}:{urlsafe_b64(sign)}"


def upload_host(ak: str, bucket: str) -> str:
    url = f"{UC_HOST}/v3/query?ak={urllib.parse.quote(ak)}&bucket={urllib.parse.quote(bucket)}"
    with urllib.request.urlopen(url, timeout=20) as resp:
        data = json.loads(resp.read().decode())
    hosts = data.get("hosts") or {}
    for region in hosts.values():
        up = region.get("up") or []
        if up:
            return up[0]
    raise RuntimeError("无法解析上传域名，检查 AK / bucket 是否正确")


def post_file(host: str, token: str, key: str, path: Path) -> None:
    boundary = "----dsh" + hashlib.md5(key.encode()).hexdigest()[:16]
    ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    body = bytearray()
    for name, value in (("token", token), ("key", key)):
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
    body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\n".encode()
    body += f"Content-Type: {ctype}\r\n\r\n".encode()
    body += path.read_bytes() + b"\r\n"
    body += f"--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        f"https://{host}/",
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = json.loads(resp.read().decode())
    if "key" not in payload:
        raise RuntimeError(f"{key}: {payload}")


def collect(directory: Path, includes: list[str]) -> list[tuple[str, Path]]:
    files = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        if includes and not any(path.match(pattern) for pattern in includes):
            continue
        files.append((path.relative_to(directory).as_posix(), path))
    return files


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket", required=True, help="七牛空间名")
    parser.add_argument("--dir", default=".", help="本地目录（相对仓库根）")
    parser.add_argument("--prefix", default="", help="上传到 bucket 下的前缀，如 assets/img")
    parser.add_argument("--include", nargs="*", default=[], help="只传匹配的文件，如 '*.jpg' '**/*.png'")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--domain", default="https://cdn.js-dev.cn", help="用于打印访问 URL")
    args = parser.parse_args()

    ak, sk = os.environ.get("QINIU_AK"), os.environ.get("QINIU_SK")
    directory = (ROOT / args.dir).resolve()
    if not directory.exists():
        print(f"目录不存在: {directory}", file=sys.stderr)
        return 1

    files = collect(directory, args.include)
    total = sum(p.stat().st_size for _, p in files)
    print(f"{len(files)} 个文件 / {total / 1024 / 1024:.1f} MB -> {args.bucket}/{args.prefix}")
    if args.dry_run:
        for key, path in files[:10]:
            print(f"  {path.stat().st_size:>9,}  {args.prefix}/{key}".replace("//", "/"))
        return 0
    if not (ak and sk):
        print("缺少 QINIU_AK / QINIU_SK 环境变量", file=sys.stderr)
        return 1

    host = upload_host(ak, args.bucket)
    print(f"上传域名: {host}")
    failed = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {}
        for key, path in files:
            object_key = f"{args.prefix}/{key}".replace("//", "/").lstrip("/")
            futures[pool.submit(post_file, host, upload_token(ak, sk, args.bucket, object_key), object_key, path)] = object_key
        for future in as_completed(futures):
            key = futures[future]
            try:
                future.result()
            except Exception as error:  # noqa: BLE001
                failed.append((key, str(error)[:80]))

    ok = len(files) - len(failed)
    print(f"完成 {ok}/{len(files)}")
    if failed:
        for key, reason in failed[:10]:
            print(f"  ! {key}: {reason}")
        return 1
    print(f"示例 URL: {args.domain.rstrip('/')}/{args.prefix.strip('/')}/<文件名>".replace("//<", "/<"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
