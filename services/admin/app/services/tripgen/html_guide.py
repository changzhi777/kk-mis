# -*- coding: utf-8 -*-
"""图文攻略 HTML(含 SVG 线路图 + 美食图鉴),可选 weasyprint 转 PDF。"""
from __future__ import annotations
import html as _html
from typing import List
from .models import Trip
from . import svg

_CSS = """
*{box-sizing:border-box;}
body{margin:0;background:#f7fafc;color:#1f2937;font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;line-height:1.7;}
.wrap{max-width:880px;margin:0 auto;padding:0 16px 60px;}
header{background:linear-gradient(135deg,#0e7490,#0369a1);color:#fff;padding:30px 20px 26px;text-align:center;}
header h1{margin:0 0 8px;font-size:23px;}
header .sub{opacity:.92;font-size:14px;}
h2{color:#0e7490;border-left:6px solid #0e7490;padding-left:10px;margin:32px 0 14px;font-size:20px;}
h2.sea{color:#0369a1;border-color:#0369a1;}
h2.warn{color:#b91c1c;border-color:#b91c1c;}
.mapbox{background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:12px;box-shadow:0 2px 10px rgba(0,0,0,.04);}
.legend{font-size:12px;color:#6b7280;text-align:center;margin-top:4px;}
.note{color:#6b7280;font-size:13px;margin:8px 2px;}
.srcline{font-size:12px;color:#0369a1;margin:4px 2px 0;}
.srcline a{color:#0369a1;text-decoration:none;}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,.04);font-size:14px;}
th{background:#0e7490;color:#fff;padding:8px 10px;text-align:left;}
td{padding:7px 10px;border-top:1px solid #e2e8f0;}
tr:nth-child(even) td{background:#f0f9ff;}
.timeline{display:grid;gap:10px;}
.day{display:flex;gap:12px;background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:12px 14px;box-shadow:0 2px 8px rgba(0,0,0,.04);}
.day .d{flex:0 0 66px;background:#0e7490;color:#fff;border-radius:8px;text-align:center;padding:8px 4px;font-weight:700;font-size:13px;height:fit-content;}
.day.sea .d{background:#0369a1;}
.day p{margin:0;font-size:14px;}
.cards{display:grid;grid-template-columns:1fr;gap:14px;}
.card{display:flex;gap:14px;background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:14px 16px;box-shadow:0 2px 10px rgba(0,0,0,.04);}
.card .ico{flex:0 0 78px;}
.card h3{margin:0 0 4px;font-size:16px;}
.card .tag{display:inline-block;background:#ecfeff;color:#0e7490;border-radius:20px;padding:1px 10px;font-size:12px;margin-left:6px;}
.card p{margin:5px 0;font-size:14px;}
.card .tip{background:#fffbeb;border-left:3px solid #b45309;padding:6px 10px;border-radius:6px;font-size:13px;color:#7c2d12;}
.card a{color:#0369a1;text-decoration:none;font-size:13px;}
.foodgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:12px;margin:6px 0 4px;}
.ftile{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:10px 8px 8px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,.04);}
.ftile svg{width:100%;height:88px;display:block;}
.ftile .fn{font-size:13px;font-weight:700;margin-top:6px;}
.ftile .fd{font-size:11px;color:#6b7280;margin-top:2px;line-height:1.4;}
.warnbox{background:#fef2f2;border:1px solid #fecaca;border-radius:12px;padding:14px 16px;}
.warnbox li{margin:6px 0;font-size:14px;}
.total{font-weight:700;color:#0e7490;}
"""


def _e(s: str) -> str:
    """允许 <b>/<br> 等富文本标签,其余转义。这里数据来自本地配置,直接放行。"""
    return s or ""


def render_html(trip: Trip) -> str:
    P: List[str] = []
    P.append('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">')
    P.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
    P.append(f"<title>{_html.escape(trip.title)}</title><style>{_CSS}</style></head><body>")
    sub = " · ".join(x for x in [trip.party, trip.origin and f"{trip.origin}出发",
                                 trip.dates] if x)
    P.append(f'<header><h1>{_e(trip.title)}</h1>'
             f'<div class="sub">{_e(trip.subtitle or sub)}</div></header><div class="wrap">')

    # 线路图
    if trip.route_map:
        P.append(f'<h2>{_e(trip.route_map.title)}</h2><div class="mapbox">')
        P.append(svg.route_map_svg(trip.route_map))
        if trip.route_map.legend:
            P.append(f'<div class="legend">{_e(trip.route_map.legend)}</div>')
        P.append('</div>')

    # 逐日行程
    if trip.days:
        P.append('<h2>逐日行程</h2><div class="timeline">')
        for d in trip.days:
            cls = "day sea" if d.sea else "day"
            P.append(f'<div class="{cls}"><div class="d">'
                     f'{_e(d.label).replace(chr(10), "<br>")}</div>'
                     f'<p>{_e(d.text)}</p></div>')
        P.append('</div>')

    # 景点卡片(带插画)
    if trip.attractions:
        P.append('<h2>景点 / 取景地</h2><div class="cards">')
        for a in trip.attractions:
            tag = f'<span class="tag">{_e(a.tag)}</span>' if a.tag else ""
            tip = f'<p class="tip">{_e(a.tip)}</p>' if a.tip else ""
            link = f'<a href="{_html.escape(a.link)}" target="_blank">↗ 实拍/详情</a>' if a.link else ""
            P.append(f'<div class="card"><div class="ico">{svg.icon(a.icon)}</div>'
                     f'<div><h3>{_e(a.name)}{tag}</h3><p>{_e(a.desc)}</p>{tip}{link}</div></div>')
        P.append('</div>')

    # 美食图鉴 + 分组表
    if trip.foods:
        P.append('<h2 class="sea">必吃美食</h2>')
        P.append('<div class="foodgrid">')
        for f in trip.foods:
            P.append(f'<div class="ftile">{svg.icon(f.icon)}'
                     f'<div class="fn">{_e(f.name)}</div>'
                     f'<div class="fd">{_e(f.desc[:22])}</div></div>')
        P.append('</div>')
        P.append('<p class="srcline">插画为原创示意图(不使用受版权实拍照片)。</p>')
        for g in trip.food_groups():
            P.append(f'<p style="margin:8px 0 4px;font-weight:700;color:#0369a1;">【{_e(g)}】</p>')
            P.append('<table><tr><th>美食</th><th>推荐店/说明</th><th>人均</th></tr>')
            for f in trip.foods_in(g):
                P.append(f'<tr><td><b>{_e(f.name)}</b></td><td>{_e(f.desc)}</td>'
                         f'<td>{_e(f.price)}</td></tr>')
            P.append('</table>')

    # 住宿
    if trip.lodging:
        P.append('<h2>住宿建议</h2><table>'
                 '<tr><th>地点/晚数</th><th>推荐</th><th>参考价</th><th>订房/联系</th></tr>')
        for l in trip.lodging:
            P.append(f'<tr><td>{_e(l.place)}</td><td>{_e(l.rec)}</td>'
                     f'<td>{_e(l.price)}</td><td>{_e(l.channel)}</td></tr>')
        P.append('</table>')

    # 交通总览
    if trip.segments:
        P.append('<h2>交通总览</h2><table>'
                 '<tr><th>区段</th><th>方式/车次</th><th>耗时</th><th>参考票价</th></tr>')
        for s in trip.segments:
            P.append(f'<tr><td>{_e(s.section)}</td><td>{_e(s.mode)}</td>'
                     f'<td>{_e(s.duration)}</td><td>{_e(s.price)}</td></tr>')
        P.append('</table>')
        if trip.transport_note:
            P.append(f'<p class="note">{_e(trip.transport_note)}</p>')

    # 预算
    if trip.budget:
        P.append('<h2>费用预算</h2><table><tr><th>项目</th><th>参考金额</th></tr>')
        for b in trip.budget:
            P.append(f'<tr><td>{_e(b.item)}</td><td>{_e(b.amount)}</td></tr>')
        if trip.budget_total:
            P.append(f'<tr><td class="total">合计参考</td>'
                     f'<td class="total">{_e(trip.budget_total)}</td></tr>')
        P.append('</table>')

    # 天气/安全
    if trip.warnings:
        P.append('<h2 class="warn">天气与安全建议</h2><div class="warnbox"><ul>')
        for w in trip.warnings:
            P.append(f'<li>{_e(w)}</li>')
        P.append('</ul></div>')

    P.append('</div></body></html>')
    return "".join(P)


def write_html(trip: Trip, out_path: str) -> str:
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(render_html(trip))
    return out_path


def html_to_pdf(html_path: str, pdf_path: str) -> str:
    from weasyprint import HTML
    HTML(html_path).write_pdf(pdf_path)
    return pdf_path
