# -*- coding: utf-8 -*-
"""生成流水线:Trip -> 文件。CLI 与 Web 界面共用。

PDF 子模块（fonts / pdf_body / html_guide / merge）采用 lazy import，
仅在 generate() 各步骤按需导入；模块顶层不依赖 reportlab / weasyprint / pypdf，
让 admin app 启动不再硬依赖这些可选库。

设计原则（CLAUDE.md §7.24）：
- HTML 攻略不需要任何 PDF 库（pdf_body/merge 缺失时 HTML 仍可正常输出）
- 正文 PDF 需要 reportlab；缺时记日志跳过该步骤，不影响其他产物
- 攻略 PDF 需要 weasyprint；缺时记日志跳过
- 合并 PDF 需要 pypdf；缺时记日志跳过
- 中文字体缺失时跳过正文 PDF（FileNotFoundError 已处理）
"""
from __future__ import annotations
import os
from typing import List, Optional, Callable

from .models import Trip


def slug(title: str) -> str:
    keep = "".join(c for c in title if c.isalnum() or c in "+-_（）()·")
    return keep[:40] or "trip"


def _try_import(name: str):
    """延迟加载 tripgen 内部子模块；ImportError 返回 None（不让单点缺失阻塞其他步骤）。

    用 importlib 动态按名加载，避免在模块顶层写死 from . import xxx。
    """
    import importlib
    try:
        return importlib.import_module(f".{name}", __name__)
    except ImportError:
        return None


def generate(trip: Trip, out_dir: str, online: bool = False,
             font: Optional[str] = None, font_bold: Optional[str] = None,
             log: Optional[Callable[[str], None]] = None) -> List[str]:
    """生成全部可用产物,返回文件路径列表。log 可用于回传进度。

    行为：
    - HTML 攻略总是先产出（不依赖 PDF 库）
    - PDF 库缺失（reportlab/pypdf/weasyprint）→ 仅跳过对应步骤，其他产物照常输出
    - 中文字体缺失 → 跳过正文 PDF（FileNotFoundError）
    """
    say = log or (lambda s: None)
    os.makedirs(out_dir, exist_ok=True)
    base = slug(trip.title)

    if online:
        from . import enrich
        say("联网核实车次(best-effort,失败自动兜底)…")
        enrich.enrich_trip(trip)

    # 延迟加载 PDF 子模块；缺哪个就跳过对应步骤，不让单点缺失阻塞全部。
    # html_guide 顶层无 PDF 依赖，可安全导入
    from . import html_guide
    fonts = _try_import("fonts")
    pdf_body = _try_import("pdf_body")
    merge = _try_import("merge")

    outputs = []

    # 1) 图文攻略 HTML(不依赖字体/weasyprint)
    html_path = os.path.join(out_dir, f"{base}_图文攻略.html")
    html_guide.write_html(trip, html_path)
    say(f"HTML 攻略:{os.path.basename(html_path)}")
    outputs.append(html_path)

    # 2) 正文 PDF(需中文字体 + reportlab)
    body_pdf = None
    if fonts is None or pdf_body is None:
        say("⚠ 跳过正文 PDF(reportlab 不可用)")
    else:
        try:
            reg, bold = fonts.build_fonts(out_dir, trip.used_chars() + pdf_body.UI_LITERALS,
                                          reg=font, bold=font_bold)
            body_pdf = os.path.join(out_dir, f"{base}_行程正文.pdf")
            pdf_body.build(trip, body_pdf, reg, bold)
            say(f"正文 PDF:{os.path.basename(body_pdf)}")
            outputs.append(body_pdf)
        except FileNotFoundError as e:
            say(f"⚠ 跳过正文 PDF(缺中文字体):{e}")

    # 3) 攻略 PDF(weasyprint,可选；html_guide 内部已经 lazy import weasyprint)
    guide_pdf = None
    try:
        guide_pdf = os.path.join(out_dir, f"{base}_图文攻略.pdf")
        html_guide.html_to_pdf(html_path, guide_pdf)
        say(f"攻略 PDF:{os.path.basename(guide_pdf)}")
        outputs.append(guide_pdf)
    except Exception as e:
        say(f"⚠ 攻略 PDF 跳过(weasyprint 不可用):{e}")
        guide_pdf = None

    # 4) 合并含附录
    if body_pdf and guide_pdf and merge is not None:
        merged = os.path.join(out_dir, f"{base}_行程计划+图文攻略(含附录).pdf")
        try:
            merge.merge(body_pdf, guide_pdf, merged)
            say(f"合并成品:{os.path.basename(merged)}")
            outputs.append(merged)
        except Exception as e:
            say(f"⚠ 合并 PDF 跳过(pypdf 失败):{e}")
    elif body_pdf and guide_pdf and merge is None:
        say("⚠ 合并 PDF 跳过(pypdf 不可用)")

    return outputs
