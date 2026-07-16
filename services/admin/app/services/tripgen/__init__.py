# -*- coding: utf-8 -*-
"""tripgen — 把旅游路线规划生成 PDF 行程正文 + 图文攻略(含 SVG 插画/线路图)。

集成到 admin 后：CLI 入口在 app/cli/tripgen.py，API 端点在 app/routes/tripgen.py，
前端在 OfficeCenter.vue 行程攻略 tab。原 http.server webapp.py + __main__.py 已移除（DEPRECATED）。
"""
__version__ = "0.1.0"

# 显式导出核心模块（O3：防 namespace 漂移）
from . import config, pipeline, models  # noqa: E402,F401
