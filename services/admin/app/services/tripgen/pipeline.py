# -*- coding: utf-8 -*-
"""生成流水线:Trip -> 文件。CLI 与 Web 界面共用。"""
from __future__ import annotations
import os
from typing import List, Optional, Callable

from . import fonts, pdf_body, html_guide, merge
from .models import Trip


def slug(title: str) -> str:
    keep = "".join(c for c in title if c.isalnum() or c in "+-_（）()·")
    return keep[:40] or "trip"


def generate(trip: Trip, out_dir: str, online: bool = False,
             font: Optional[str] = None, font_bold: Optional[str] = None,
             log: Optional[Callable[[str], None]] = None) -> List[str]:
    """生成全部可用产物,返回文件路径列表。log 可用于回传进度。"""
    say = log or (lambda s: None)
    os.makedirs(out_dir, exist_ok=True)
    base = slug(trip.title)

    if online:
        from . import enrich
        say("联网核实车次(best-effort,失败自动兜底)…")
        enrich.enrich_trip(trip)

    outputs = []

    # 1) 图文攻略 HTML(不依赖字体/weasyprint)
    html_path = os.path.join(out_dir, f"{base}_图文攻略.html")
    html_guide.write_html(trip, html_path)
    say(f"HTML 攻略:{os.path.basename(html_path)}")
    outputs.append(html_path)

    # 2) 正文 PDF(需中文字体)
    body_pdf = None
    try:
        reg, bold = fonts.build_fonts(out_dir, trip.used_chars() + pdf_body.UI_LITERALS,
                                      reg=font, bold=font_bold)
        body_pdf = os.path.join(out_dir, f"{base}_行程正文.pdf")
        pdf_body.build(trip, body_pdf, reg, bold)
        say(f"正文 PDF:{os.path.basename(body_pdf)}")
        outputs.append(body_pdf)
    except FileNotFoundError as e:
        say(f"⚠ 跳过正文 PDF(缺中文字体):{e}")
        return outputs

    # 3) 攻略 PDF(weasyprint,可选)
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
    if body_pdf and guide_pdf:
        merged = os.path.join(out_dir, f"{base}_行程计划+图文攻略(含附录).pdf")
        merge.merge(body_pdf, guide_pdf, merged)
        say(f"合并成品:{os.path.basename(merged)}")
        outputs.append(merged)

    return outputs
