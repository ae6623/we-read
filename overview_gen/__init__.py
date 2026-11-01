# -*- coding: utf-8 -*-
"""overview_gen — 读前通读（全书视角）页生成器（we-read-auto）。

把「微信读书 AI 大纲」自动转成站点可用的 overview.html，并经质量门禁后发布。
详见同级 README.md。
"""
__all__ = ["parse_outline", "build_overview", "books", "quality_gate", "publish"]
