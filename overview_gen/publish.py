# -*- coding: utf-8 -*-
"""publish.py — 把生成的 overview.html 发布到 we-read 站点仓库（overview_gen）。

复用仓库根目录的 gh_api.py（GitHub HTTP API 事务式提交，不依赖 git 二进制，
云端/沙箱友好）。只提交真正变化的文件，无变化算成功。

目标路径固定为：reading-notes/books/<slug>/overview.html
（we-read 站点规范和线上路径一致，overview.html 在此目录引用 ../../../assets/css/）

用法（库）：
    from overview_gen.publish import publish_overview
    ok, msg, detail = publish_overview(slug, html_text, cfg, message="...")

用法（CLI）：见 cli.py 的 publish 子命令。
"""
import json
import os

def _gh_api():
    """延迟导入仓库根的 gh_api（只在真正发布时需要，避免 parse/build 也依赖它）。"""
    import sys
    here = os.path.dirname(os.path.abspath(__file__))      # overview_gen/
    repo_root = os.path.dirname(here)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from gh_api import from_config
    return from_config


def publish_overview(slug, html_text, cfg, message=None, dry_run=False):
    """发布一本 overview.html。返回 (ok, msg, detail)。"""
    from_config = _gh_api()
    api = from_config(cfg)
    path = "reading-notes/books/%s/overview.html" % slug
    if message is None:
        from datetime import datetime, timezone, timedelta
        cst = timezone(timedelta(hours=8))
        ts = datetime.now(cst).strftime("%Y-%m-%d %H:%M")
        message = "overview(读前通读): %s · 自动发布 %s" % (slug, ts)
    ok, msg, detail = api.publish_paths({path: html_text}, message, dry_run=dry_run)
    if ok and not dry_run:
        detail["url"] = "https://ae6623.github.io/we-read/reading-notes/books/%s/overview.html" % slug
    return ok, msg, detail


def load_cfg(config_path=None):
    if config_path is None:
        # 同仓默认值：仓库根的 config.json
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(here, "config.json")
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def publish_local_file(slug, overview_html_path, config_path=None, message=None, dry_run=False):
    cfg = load_cfg(config_path)
    html = open(overview_html_path, encoding="utf-8").read()
    return publish_overview(slug, html, cfg, message=message, dry_run=dry_run)
