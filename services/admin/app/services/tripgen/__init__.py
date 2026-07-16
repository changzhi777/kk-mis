# -*- coding: utf-8 -*-
"""tripgen — 把旅游路线规划生成 PDF 行程正文 + 图文攻略(含 SVG 插画/线路图)。

集成到 admin 后：CLI 入口在 app/cli/tripgen.py，API 端点在 app/routes/tripgen.py，
前端在 OfficeCenter.vue 行程攻略 tab。原 http.server webapp.py + __main__.py 已移除（DEPRECATED）。

设计：PDF 子模块（pdf_body / fonts / html_guide 的 html_to_pdf / merge）采用 lazy import，
不在顶层 import reportlab/weasyprint/pypdf，避免 admin app 启动硬依赖。
未安装 PDF 库时，调用方显式 import 或运行 pipeline.generate() 才会触发 ImportError（合理失败点）。
"""
__version__ = "0.1.0"

# 仅导出轻量子模块（无 PDF 依赖）—— 防 namespace 漂移
from . import config, models  # noqa: E402,F401
# pipeline 模块不顶层导入：其内部会触发 fonts/pdf_body/html_guide/merge 的 PDF 库硬依赖。
# 调用方需显式: from app.services.tripgen import pipeline; pipeline.generate(trip, out_dir)
# 或通过 app.routes.tripgen（路由模块顶层仅 import pipeline 模块本身，PDF 库延迟到 generate()）。
