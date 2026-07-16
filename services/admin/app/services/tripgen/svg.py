# -*- coding: utf-8 -*-
"""SVG 组件库:线路示意图 + 美食/景点手绘插画。

插画为原创示意图(避免使用受版权的实拍照片),风格统一。
用 icon 键取图;未知键回退到通用图标。
"""
from __future__ import annotations
from typing import List
from .models import RouteMap, MapNode

# ---------------- 美食/景点插画 ----------------
# 每个值是 viewBox="0 0 100 90" 的内部 SVG 片段。
_ICONS = {
    "changfen": '<ellipse cx="50" cy="66" rx="40" ry="14" fill="#e0f2fe" stroke="#7dd3fc"/><path d="M18 62q10-14 22-8 12-14 24-6 10-8 18 2-4 12-22 12H26q-12 0-8-2z" fill="#fef9f3" stroke="#e5b78a" stroke-width="2"/><path d="M24 60q14-8 30 0t20 0" fill="none" stroke="#f59e0b" stroke-width="2"/><ellipse cx="40" cy="55" rx="4" ry="2.5" fill="#fca5a5"/><ellipse cx="58" cy="57" rx="4" ry="2.5" fill="#fca5a5"/><path d="M74 44l10-4-3 8z" fill="#92400e"/>',
    "noodle": '<path d="M18 40h64l-6 30a8 8 0 0 1-8 6H32a8 8 0 0 1-8-6z" fill="#fff7ed" stroke="#d97706" stroke-width="2"/><ellipse cx="50" cy="40" rx="32" ry="9" fill="#fde68a" stroke="#d97706" stroke-width="2"/><circle cx="42" cy="40" r="6" fill="#fca5a5" stroke="#b91c1c"/><circle cx="58" cy="41" r="6" fill="#fca5a5" stroke="#b91c1c"/><path d="M34 40q8-6 16 0t16 0" fill="none" stroke="#a16207" stroke-width="2"/><path d="M40 20c0 6-6 6-6 12M56 18c0 6-6 6-6 12" fill="none" stroke="#cbd5e1" stroke-width="2"/>',
    "dimsum": '<ellipse cx="50" cy="60" rx="34" ry="20" fill="#deb887" stroke="#8b5e34" stroke-width="2"/><ellipse cx="50" cy="54" rx="34" ry="18" fill="#f5deb3" stroke="#8b5e34" stroke-width="2"/><path d="M40 50l6-8 6 8M52 50l6-8 6 8" fill="#fde68a" stroke="#d97706" stroke-width="1.5"/><ellipse cx="43" cy="52" rx="5" ry="4" fill="#fca5a5"/><ellipse cx="58" cy="52" rx="5" ry="4" fill="#fca5a5"/><path d="M30 40q20-10 40 0" fill="none" stroke="#e2e8f0" stroke-width="3"/>',
    "herbtea": '<path d="M34 30h32l-4 40a6 6 0 0 1-6 5H44a6 6 0 0 1-6-5z" fill="#4b5563" stroke="#1f2937" stroke-width="2"/><ellipse cx="50" cy="30" rx="16" ry="5" fill="#374151"/><path d="M42 26c0-6 4-6 4-12M54 26c0-6-4-6-4-12" fill="none" stroke="#16a34a" stroke-width="2"/><path d="M40 44h20M39 56h22" stroke="#111827" stroke-width="1.5" opacity=".5"/>',
    "dessert": '<path d="M26 40h48l-5 28a8 8 0 0 1-8 7H39a8 8 0 0 1-8-7z" fill="#fff" stroke="#0369a1" stroke-width="2"/><ellipse cx="50" cy="40" rx="24" ry="7" fill="#fde68a" stroke="#0369a1" stroke-width="2"/><circle cx="42" cy="40" r="3" fill="#f59e0b"/><circle cx="52" cy="41" r="3" fill="#f59e0b"/><circle cx="58" cy="39" r="3" fill="#f59e0b"/><path d="M36 52h28" stroke="#38bdf8" stroke-width="2"/>',
    "milktea": '<path d="M38 20h24l-3 52a7 7 0 0 1-7 6h-4a7 7 0 0 1-7-6z" fill="#d9b38c" stroke="#8b5e34" stroke-width="2"/><path d="M39 34h22l-2 36a5 5 0 0 1-5 5h-8a5 5 0 0 1-5-5z" fill="#c8a06a"/><rect x="47" y="12" width="6" height="12" rx="2" fill="#94a3b8"/><path d="M40 26h20" stroke="#fff" stroke-width="2" opacity=".6"/>',
    "aquarium": '<rect x="14" y="20" width="72" height="50" rx="8" fill="#cffafe" stroke="#0369a1" stroke-width="2"/><path d="M14 56q18-8 36 0t36 0V64a6 6 0 0 1-6 6H20a6 6 0 0 1-6-6z" fill="#38bdf8" opacity=".5"/><path d="M40 44l14-7v14z" fill="#f97316"/><circle cx="38" cy="42" r="2.5" fill="#fff"/><path d="M60 34c6 0 8 4 8 6s-2 6-8 6" fill="none" stroke="#0284c7" stroke-width="2"/>',
    "hotpot": '<path d="M20 42h60l-5 26a10 10 0 0 1-10 8H35a10 10 0 0 1-10-8z" fill="#fca5a5" stroke="#b91c1c" stroke-width="2"/><ellipse cx="50" cy="42" rx="30" ry="8" fill="#fecdd3" stroke="#b91c1c" stroke-width="2"/><circle cx="40" cy="42" r="5" fill="#f9e4c8" stroke="#a16207"/><circle cx="52" cy="43" r="5" fill="#f9e4c8" stroke="#a16207"/><circle cx="60" cy="41" r="5" fill="#f9e4c8" stroke="#a16207"/><path d="M30 34c0-6 4-6 4-10M66 34c0-6-4-6-4-10" fill="none" stroke="#cbd5e1" stroke-width="2"/>',
    "oyster": '<circle cx="46" cy="52" r="30" fill="#4b5563" stroke="#1f2937" stroke-width="2"/><path d="M78 50h14" stroke="#1f2937" stroke-width="4"/><circle cx="46" cy="50" r="25" fill="#fde68a"/><path d="M30 50q8-8 16 0t16 0" fill="#a3e635" opacity=".6"/><ellipse cx="40" cy="48" rx="5" ry="4" fill="#e5e7eb" stroke="#6b7280"/><ellipse cx="54" cy="52" rx="5" ry="4" fill="#e5e7eb" stroke="#6b7280"/><circle cx="48" cy="46" r="3" fill="#fbbf24"/>',
    "goose": '<ellipse cx="50" cy="62" rx="36" ry="13" fill="#e2e8f0" stroke="#94a3b8"/><path d="M28 56q8-20 22-20 14 0 22 20z" fill="#8b5230" stroke="#5b3418" stroke-width="2"/><path d="M34 52q16-10 32 0" fill="none" stroke="#c2410c" stroke-width="2"/><ellipse cx="44" cy="48" rx="4" ry="3" fill="#a16207"/><path d="M60 40l8-4-2 7z" fill="#7c2d12"/>',
    "kuey": '<path d="M22 42h56l-6 28a9 9 0 0 1-9 7H37a9 9 0 0 1-9-7z" fill="#fff7ed" stroke="#b45309" stroke-width="2"/><ellipse cx="50" cy="42" rx="28" ry="8" fill="#fef3c7" stroke="#b45309" stroke-width="2"/><path d="M34 42q16-6 32 0" fill="none" stroke="#eab308" stroke-width="3"/><path d="M38 40q12-4 24 0" fill="none" stroke="#eab308" stroke-width="3"/><ellipse cx="52" cy="44" rx="6" ry="3" fill="#fca5a5"/>',
    "sweetball": '<path d="M26 42h48l-5 28a8 8 0 0 1-8 7H39a8 8 0 0 1-8-7z" fill="#fff" stroke="#0369a1" stroke-width="2"/><ellipse cx="50" cy="42" rx="24" ry="7" fill="#fce7f3" stroke="#0369a1" stroke-width="2"/><ellipse cx="42" cy="42" rx="6" ry="5" fill="#fff" stroke="#db2777"/><ellipse cx="56" cy="43" rx="6" ry="5" fill="#fff" stroke="#db2777"/><path d="M36 54h28" stroke="#38bdf8" stroke-width="2"/>',
    "teapot": '<path d="M30 42q0-12 20-12t20 12q6 2 6 8t-6 8q-2 10-20 10T30 58q-6-2-6-8t6-8z" fill="#a16207" stroke="#5b3418" stroke-width="2"/><path d="M70 44q8 0 8 8t-8 8" fill="none" stroke="#5b3418" stroke-width="2"/><rect x="44" y="20" width="12" height="10" rx="2" fill="#78350f"/><rect x="20" y="70" width="16" height="8" rx="2" fill="#e2e8f0" stroke="#94a3b8"/><rect x="64" y="70" width="16" height="8" rx="2" fill="#e2e8f0" stroke="#94a3b8"/>',
    "seafood": '<ellipse cx="34" cy="44" rx="18" ry="11" fill="#fca5a5" stroke="#b91c1c" stroke-width="2"/><path d="M52 44l14-8v16z" fill="#f87171"/><circle cx="28" cy="42" r="2.5" fill="#fff"/><path d="M8 62q16-5 32 0t32 0" stroke="#38bdf8" stroke-width="3" fill="none"/>',
    # 景点通用
    "spot": '<rect x="20" y="40" width="60" height="34" fill="#fde68a" stroke="#b45309" stroke-width="2"/><path d="M16 40l34-22 34 22z" fill="#fca5a5" stroke="#b45309" stroke-width="2"/><rect x="34" y="52" width="12" height="22" fill="#b45309"/><rect x="54" y="52" width="12" height="12" fill="#fff" stroke="#b45309"/>',
    "beach": '<rect x="6" y="54" width="88" height="24" fill="#38bdf8" opacity=".5"/><path d="M6 54q22-8 44 0t44 0" fill="#fde68a"/><circle cx="70" cy="28" r="10" fill="#fbbf24"/><path d="M20 54c0-10 6-16 6-22M26 32c-6 0-12 4-14 10M26 32c6 0 12 4 14 10" fill="none" stroke="#15803d" stroke-width="2"/>',
    "bowl": '<path d="M22 42h56l-6 28a9 9 0 0 1-9 7H37a9 9 0 0 1-9-7z" fill="#fff7ed" stroke="#b45309" stroke-width="2"/><ellipse cx="50" cy="42" rx="28" ry="8" fill="#fef3c7" stroke="#b45309" stroke-width="2"/>',
}


def icon(key: str) -> str:
    """返回一个完整 <svg> 元素(含内部片段)。"""
    body = _ICONS.get(key, _ICONS["bowl"])
    return (f'<svg viewBox="0 0 100 90" xmlns="http://www.w3.org/2000/svg">'
            f'{body}</svg>')


# ---------------- 线路示意图 ----------------
_NODE_COLORS = {
    "origin": "#0e7490", "city": "#b45309", "transfer": "#334155", "sea": "#0369a1",
}


def route_map_svg(rm: RouteMap, width: int = 860, height: int = 300) -> str:
    """把 RouteMap(相对坐标)渲染成一张连线示意图 SVG。"""
    if not rm or not rm.nodes:
        return ""
    W, H = width, height
    parts = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" width="100%">',
             f'<rect x="0" y="0" width="{W}" height="{H}" fill="#f8fafc"/>']
    pts = [(n, n.x * W, n.y * H) for n in rm.nodes]
    # 连线(按节点顺序)
    for i in range(len(pts) - 1):
        _, x1, y1 = pts[i]
        _, x2, y2 = pts[i + 1]
        parts.append(f'<path d="M{x1:.0f},{y1:.0f} L{x2:.0f},{y2:.0f}" '
                     f'stroke="#94a3b8" stroke-width="3" stroke-dasharray="8 6" fill="none"/>')
    # 节点
    for n, x, y in pts:
        c = _NODE_COLORS.get(n.kind, "#b45309")
        r = 9 if n.kind in ("origin", "sea") else 7
        parts.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r}" fill="{c}"/>')
        anchor = "start" if x < W * 0.8 else "end"
        dx = 12 if anchor == "start" else -12
        parts.append(f'<text x="{x+dx:.0f}" y="{y-12:.0f}" font-size="13" '
                     f'font-weight="700" fill="#0f172a" text-anchor="{anchor}">{n.name}</text>')
    parts.append('</svg>')
    return "".join(parts)
