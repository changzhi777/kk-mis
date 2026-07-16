# -*- coding: utf-8 -*-
"""把正文 PDF 与图文攻略 PDF 合并成一个带书签的成品。"""
from __future__ import annotations
from pypdf import PdfReader, PdfWriter


def merge(body_pdf: str, guide_pdf: str, out_pdf: str,
          body_label: str = "行程计划(正文)",
          guide_label: str = "图文攻略(附录)") -> str:
    w = PdfWriter()
    a = PdfReader(body_pdf)
    b = PdfReader(guide_pdf)
    for p in a.pages:
        w.add_page(p)
    n = len(a.pages)
    for p in b.pages:
        w.add_page(p)
    w.add_outline_item(body_label, 0)
    w.add_outline_item(guide_label, n)
    with open(out_pdf, "wb") as f:
        w.write(f)
    return out_pdf
