#!/usr/bin/env python3
"""精确刷新七牛 CDN 上「同名覆盖」的 URL。

背景：Kodo 覆盖上传只换源站对象，边缘节点仍按 `max-age=31536000` 返回旧图
（2026-11-15 实测：8 张封面同名覆盖后线上仍是旧真封 / gen_fallback 素封，
加随机 query 绕缓存则 8/8 已是新真封）。所以发布链路必须显式刷一次。

用法（AK/SK 只在 GitHub Actions secrets，本地不落盘）：
    export QINIU_AK=xxx QINIU_SK=xxx
    python scripts/refresh_cdn.py --file assets/data/cdn-refresh.txt
    python scripts/refresh_cdn.py --file ... --dry-run   # 无凭据也能预览清单

清单格式：每行一条；完整 URL 原样使用，`/assets/...` 相对路径会在
`--domain` 指定的每个域名下各刷一条（默认两个线上域）。
以 `#` 开头或空行忽略；清单为空时安全跳过。
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DOMAINS = ("https://cdn.js-dev.cn", "https://reader.js-dev.cn")
BATCH = 60  # 七牛单次刷新 URL 上限，保守分批


def load_urls(path: Path, domains: tuple[str, ...]) -> list[str]:
    urls: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("http://") or s.startswith("https://"):
            urls.append(s)
        else:
            if not s.startswith("/"):
                s = "/" + s
            urls += [d.rstrip("/") + s for d in domains]
    seen: set[str] = set()
    return [u for u in urls if not (u in seen or seen.add(u))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="assets/data/cdn-refresh.txt")
    ap.add_argument("--domain", action="append", default=[],
                    help="可重复；缺省时刷 cdn.js-dev.cn 与 reader.js-dev.cn")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    p = Path(args.file)
    if not p.is_absolute():
        p = ROOT / p
    if not p.exists():
        print("清单不存在，跳过刷新:", p)
        return 0
    domains = tuple(args.domain) or DEFAULT_DOMAINS
    urls = load_urls(p, domains)
    print(f"待刷新 {len(urls)} 条 URL（域名: {', '.join(domains)}）")
    for u in urls[:6]:
        print("  ", u)
    if len(urls) > 6:
        print("   ...")
    if not urls:
        print("清单为空，无需刷新")
        return 0
    if args.dry_run:
        return 0

    ak, sk = os.environ.get("QINIU_AK"), os.environ.get("QINIU_SK")
    if not (ak and sk):
        print("缺少 QINIU_AK / QINIU_SK，跳过刷新", file=sys.stderr)
        return 1

    from qiniu import Auth, CdnManager

    cdn = CdnManager(Auth(ak, sk))
    fn = getattr(cdn, "refresh_urls", None) or getattr(cdn, "refreshUrls", None)
    if fn is None:
        print("七牛 SDK 无 refresh_urls，请检查 qiniu 版本", file=sys.stderr)
        return 1
    ok = 0
    for i in range(0, len(urls), BATCH):
        batch = urls[i:i + BATCH]
        ret, info = fn(batch)
        if getattr(info, "status_code", None) == 200:
            ok += len(batch)
            print(f"批次 {i // BATCH + 1}: 已提交刷新 {len(batch)} 条")
        else:
            print(f"批次 {i // BATCH + 1}: HTTP {getattr(info, 'status_code', None)} "
                  f"{getattr(info, 'error', '')}", file=sys.stderr)
    print(f"刷新完成 {ok}/{len(urls)}")
    return 0 if ok == len(urls) else 1


if __name__ == "__main__":
    raise SystemExit(main())
