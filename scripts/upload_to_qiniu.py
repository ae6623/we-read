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


"""七牛上传（官方 SDK）。需要先 `pip install qiniu`。"""


def _remote_size(auth, bucket: str, key: str):
    """查远端对象大小；不存在或查询失败返回 None。"""
    from qiniu import BucketManager

    ret, info = BucketManager(auth).stat(bucket, key)
    if info.status_code == 200 and ret:
        return ret.get("fsize")
    return None


def local_etag(path: Path) -> str | None:
    """七牛对象 etag（qetag v1），与 stat 返回的 hash 可直接比对。

    优先用 SDK（保证与 put_file_v2 的分片规则一致）；SDK 缺失时按官方
    算法自算：单块 0x16 + sha1(data)；多块 0x96 + sha1(concat(sha1(block)))。

    注意：>4MB 的文件若当年是用非 4MB 分片传的，etag 会对不上 —— 那种
    情况下这里只会「多传一次」，不会误跳过，安全方向是对的。
    """
    try:
        from qiniu import etag as _etag

        return _etag(str(path))
    except Exception:  # noqa: BLE001
        pass

    import base64
    import hashlib

    block = 4 * 1024 * 1024
    digests = []
    with path.open("rb") as f:
        while True:
            chunk = f.read(block)
            if not chunk:
                break
            digests.append(hashlib.sha1(chunk).digest())
    if not digests:
        digests = [hashlib.sha1(b"").digest()]
    if len(digests) == 1:
        raw = b"\x16" + digests[0]
    else:
        raw = b"\x96" + hashlib.sha1(b"".join(digests)).digest()
    return base64.urlsafe_b64encode(raw).decode()


def remote_meta(auth, bucket: str, keys: list[str], chunk: int = 500) -> dict:
    """批量查远端 {key: (fsize, hash)}，只返回存在的对象。

    用七牛 batch 接口，500 个 key 一次请求；比逐个 stat 快两个数量级。
    batch 部分失败（对象不存在）时对应项 code=612，直接跳过。
    """
    from qiniu import BucketManager, build_batch_stat

    manager = BucketManager(auth)
    out: dict = {}
    for i in range(0, len(keys), chunk):
        part = keys[i:i + chunk]
        try:
            res = manager.batch(build_batch_stat(bucket, part))
        except Exception:  # noqa: BLE001  SDK 版本差异/接口抖动 → 退回逐个 stat
            for key in part:
                ret, info = manager.stat(bucket, key)
                if info.status_code == 200 and ret:
                    out[key] = (ret.get("fsize"), ret.get("hash"))
            continue
        # SDK 7.18 返回 list[dict]，老版本返回 (rets, infos) —— 两种都接
        if isinstance(res, list) and (not res or isinstance(res[0], dict)):
            for key, item in zip(part, res):
                if isinstance(item, dict) and item.get("code") == 200 and item.get("data"):
                    data = item["data"]
                    out[key] = (data.get("fsize"), data.get("hash"))
        elif isinstance(res, tuple) and len(res) == 2:
            rets, infos = res
            for key, ret, info in zip(part, rets, infos):
                if info.status_code == 200 and ret and ret.get("code", 200) == 200:
                    out[key] = (ret.get("fsize"), ret.get("hash"))
    return out


def upload_one(auth, bucket: str, key: str, path: Path, attempts: int = 3) -> None:
    """上传单个对象，幂等。

    614 = 对象已存在（七牛对同 key 同内容返回 614，不当失败）。
    部署是幂等的：远端大小与本地一致就视为成功，否则才算真失败。
    其余错误（网络/5xx）指数退避重试，重试耗尽才抛。
    """
    from qiniu import put_file_v2

    local_size = path.stat().st_size
    last = ""
    for attempt in range(attempts):
        token = auth.upload_token(bucket, key, 3600)
        ret, info = put_file_v2(token, key, str(path))
        if info.status_code == 200 and ret and ret.get("key") == key:
            return
        if info.status_code == 614:
            remote = _remote_size(auth, bucket, key)
            if remote == local_size:
                return
            raise RuntimeError(
                f"{key}: 已存在但大小不一致（远端 {remote} / 本地 {local_size}）"
            )
        last = f"HTTP {info.status_code} {getattr(info, 'error', '')}".strip()
        if attempt + 1 < attempts:
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{key}: {last}")


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
    parser.add_argument(
        "--no-incremental", dest="incremental", action="store_false",
        help="关闭增量：无条件重传所有文件（默认先比对远端 hash，只传变化）",
    )
    parser.set_defaults(incremental=True)
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

    from qiniu import Auth

    auth = Auth(ak, sk)
    keys = [f"{args.prefix}/{key}".replace("//", "/").lstrip("/") for key, _ in files]
    by_key = {k: p for (_, p), k in zip(files, keys)}

    # ── 增量：先批量拉远端 (size, hash)，一致的文件直接跳过 ──────────────
    # 旧逻辑是「每个文件 PUT 一遍、撞 614 才算已存在」，等于每次把整站
    # 674MB 重传一遍；改成长轮询 stat 后，日常一次提交通常只传几 MB。
    if args.incremental:
        t0 = time.time()
        meta = remote_meta(auth, args.bucket, keys) if keys else {}
        todo, skipped_bytes = [], 0
        with ThreadPoolExecutor(max_workers=min(16, args.workers * 2)) as pool:
            etags = dict(zip(keys, pool.map(lambda k: local_etag(by_key[k]), keys)))
        for key in keys:
            path = by_key[key]
            size = path.stat().st_size
            remote = meta.get(key)
            if remote and remote[0] == size and remote[1] and remote[1] == etags[key]:
                skipped_bytes += size
                continue
            todo.append((key, path))
        print(
            f"增量检查 {len(keys)} 个对象（{time.time() - t0:.1f}s）："
            f"未变 {len(keys) - len(todo)} 个 / 跳过 {skipped_bytes / 1024 / 1024:.1f} MB，"
            f"待传 {len(todo)} 个"
        )
        files = todo
        if not files:
            print("全部已是最新，跳过上传")
            return 0

    failed = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {}
        for object_key in [k for k, _ in files]:
            path = by_key[object_key]
            futures[pool.submit(upload_one, auth, args.bucket, object_key, path)] = object_key
        for future in as_completed(futures):
            key = futures[future]
            try:
                future.result()
            except Exception as error:  # noqa: BLE001
                failed.append((key, str(error)[:160]))

    ok = len(files) - len(failed)
    print(f"完成 {ok}/{len(files)}")
    if failed:
        for key, reason in failed[:10]:
            # reason 已含 key（upload_one 拼的），别重复打两遍路径
            print(f"  ! {reason}" if reason.startswith(key) else f"  ! {key}: {reason}")
        return 1
    print(f"示例 URL: {args.domain.rstrip('/')}/{args.prefix.strip('/')}/<文件名>".replace("//<", "/<"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
