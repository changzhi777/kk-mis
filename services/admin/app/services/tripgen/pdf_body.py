# -*- coding: utf-8 -*-
"""行程正文 PDF(reportlab / Platypus)。"""
from __future__ import annotations
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, HRFlowable, ListFlowable, ListItem)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from .models import Trip

# 生成器自身写死的所有中文字面量 —— 必须一并进入字体子集,否则会出现豆腐块(□)。
UI_LITERALS = (
    "一二三四五六七八九十、"
    "交通总览逐日行程景点取景地介绍必吃美食住宿建议费用预算天气与安全建议"
    "区段方式车次耗时参考票价项目参考金额合计"
    "出发订房联系人均贴士推荐店说明"
    "由生成车次票价门票以官方实时为准"
    "【】()（） · | ::;/+-"
)

INK = colors.HexColor("#1f2937"); MUTED = colors.HexColor("#6b7280")
ACC = colors.HexColor("#0e7490"); SEA = colors.HexColor("#0369a1")
HEAD = colors.HexColor("#0e7490"); LIGHT = colors.HexColor("#ecfeff")
LIGHT2 = colors.HexColor("#f0f9ff")

_FONT_REGISTERED = False


def _register(reg: str, bold: str):
    global _FONT_REGISTERED
    pdfmetrics.registerFont(TTFont("TG", reg))
    pdfmetrics.registerFont(TTFont("TG-B", bold))
    pdfmetrics.registerFontFamily("TG", normal="TG", bold="TG-B",
                                  italic="TG", boldItalic="TG-B")
    _FONT_REGISTERED = True


def _P(t, size=10, leading=14, color=INK, font="TG", align=TA_LEFT, sa=0, sb=0):
    return Paragraph(t, ParagraphStyle("p", fontName=font, fontSize=size,
        leading=leading, textColor=color, alignment=align,
        spaceAfter=sa, spaceBefore=sb))


def _H(t, color=ACC):
    return _P(t, 12.5, 16, color, "TG-B", sb=8, sa=3)


def _tc(t, size=8.4, color=INK, font="TG", align=TA_LEFT):
    return _P(t, size=size, leading=11, color=color, font=font, align=align)


def build(trip: Trip, out_path: str, font_reg: str, font_bold: str) -> str:
    _register(font_reg, font_bold)
    doc = SimpleDocTemplate(out_path, pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.1 * cm, bottomMargin=1.0 * cm,
        title=trip.title, author="tripgen")
    S = []
    # 标题
    S.append(_P(trip.title, 18, 23, ACC, "TG-B", TA_CENTER))
    meta = " | ".join(x for x in [trip.party, trip.origin and f"{trip.origin}出发",
                                  trip.dates] if x)
    if trip.subtitle:
        S.append(_P(trip.subtitle, 9, 13, MUTED, "TG", TA_CENTER, sb=3))
    if meta:
        S.append(_P(meta, 9, 13, MUTED, "TG", TA_CENTER, sb=2))
    S.append(Spacer(1, 4))
    S.append(HRFlowable(width="100%", thickness=1.4, color=ACC, spaceAfter=6))

    n = 0
    def sec(title, color=ACC):
        nonlocal n
        n += 1
        cn = "一二三四五六七八九十"[n - 1] if n <= 10 else str(n)
        S.append(_H(f"{cn}、{title}", color))

    # 交通总览
    if trip.segments:
        sec("交通总览")
        rows = [[_tc(x, 8.6, colors.white, "TG-B", TA_CENTER)
                 for x in ["区段", "方式 / 车次", "耗时", "参考票价"]]]
        for s in trip.segments:
            rows.append([_tc(s.section, 8.3, INK, "TG-B"), _tc(s.mode),
                         _tc(s.duration, 8.4, INK, "TG", TA_CENTER),
                         _tc(s.price, 8.4, INK, "TG", TA_CENTER)])
        t = Table(rows, colWidths=[3.4*cm, 8.4*cm, 2.5*cm, 2.9*cm], repeatRows=1)
        t.setStyle(_grid(len(rows)))
        S.append(t)
        if trip.transport_note:
            S.append(_P(trip.transport_note, 7.9, 11, MUTED, sb=2))

    # 逐日行程
    if trip.days:
        sec("逐日行程")
        drows = []
        for d in trip.days:
            drows.append([_P(d.label.replace("\n", "<br/>"), 9, 12,
                             colors.white, "TG-B", TA_CENTER), _P(d.text, 9, 13)])
        dt = Table(drows, colWidths=[2.3*cm, 14.9*cm])
        ds = [("VALIGN", (0, 0), (-1, -1), "TOP"),
              ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
              ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
              ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cfe8ef"))]
        for i, d in enumerate(trip.days):
            ds.append(("BACKGROUND", (0, i), (0, i), SEA if d.sea else ACC))
            if i % 2 == 1:
                ds.append(("BACKGROUND", (1, i), (1, i), LIGHT2))
        dt.setStyle(TableStyle(ds))
        S.append(dt)

    # 景点
    if trip.attractions:
        sec("景点 / 取景地介绍")
        items = [f"<b>{a.name}</b>{('('+a.tag+')') if a.tag else ''}:{a.desc}"
                 + (f" 贴士:{a.tip}" if a.tip else "") for a in trip.attractions]
        S.append(_bullets(items, ACC))

    # 美食(按分组)
    if trip.foods:
        sec("必吃美食")
        for g in trip.food_groups():
            S.append(_P(f"<b>【{g}】</b>", 9, 12.6, SEA, "TG-B", sb=2))
            items = [f"<b>{f.name}</b>:{f.desc}" + (f" · 人均{f.price}" if f.price else "")
                     for f in trip.foods_in(g)]
            S.append(_bullets(items, SEA))

    # 住宿
    if trip.lodging:
        sec("住宿建议")
        items = []
        for l in trip.lodging:
            line = f"<b>{l.place}</b> — {l.rec}"
            if l.price:
                line += f"(参考价 {l.price})"
            if l.channel:
                line += f";<b>订房/联系:{l.channel}</b>"
            items.append(line)
        S.append(_bullets(items, ACC))

    # 预算
    if trip.budget:
        sec("费用预算")
        rows = [[_P(x, 8.6, 11, colors.white, "TG-B")
                 for x in ["项目", f"参考金额({trip.party})" if trip.party else "参考金额"]]]
        for b in trip.budget:
            rows.append([_P(b.item, 8.4), _P(b.amount, 8.4, 11, INK, "TG", TA_CENTER)])
        if trip.budget_total:
            rows.append([_P("合计参考", 9, 11.5, ACC, "TG-B"),
                         _P(trip.budget_total, 9.4, 11.5, ACC, "TG-B", TA_CENTER)])
        t = Table(rows, colWidths=[11.7*cm, 5.5*cm])
        t.setStyle(_grid(len(rows)))
        S.append(t)

    # 天气/安全建议
    if trip.warnings:
        sec("天气与安全建议")
        S.append(_bullets(trip.warnings, colors.HexColor("#b91c1c")))

    S.append(Spacer(1, 6))
    S.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#cfe8ef")))
    S.append(_P("由 tripgen 生成 · 车次/票价/门票以官方实时为准。", 7.6, 10.6, MUTED, align=TA_CENTER))
    doc.build(S)
    return out_path


def _grid(nrows):
    st = [("BACKGROUND", (0, 0), (-1, 0), HEAD), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("TOPPADDING", (0, 0), (-1, -1), 3.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.2),
          ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
          ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cfe8ef"))]
    for i in range(1, nrows):
        if i % 2 == 0:
            st.append(("BACKGROUND", (0, i), (-1, i), LIGHT))
    return TableStyle(st)


def _bullets(items, color):
    return ListFlowable(
        [ListItem(_P(x, 9, 12.6), leftIndent=6, value="•") for x in items],
        bulletType="bullet", start="•", leftIndent=12,
        bulletFontName="TG", bulletColor=color)
