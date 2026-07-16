# -*- coding: utf-8 -*-
"""配置加载:YAML/JSON -> Trip,缺关键字段时交互兜底。"""
from __future__ import annotations
import json
import os
import sys
from typing import Any, Dict

from .models import (Trip, Day, Segment, Attraction, Food, Lodging,
                     BudgetItem, RouteMap, MapNode)

REQUIRED = ["title"]
PROMPTABLE = [
    ("title", "行程标题(如:潮汕+南澳岛 亲子4天)"),
    ("origin", "出发地(如:长沙)"),
    ("party", "同行人(如:一大一小)"),
    ("dates", "日期(如:7/29晚–8/3)"),
]


def _load_raw(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if path.endswith((".yaml", ".yml")):
        try:
            import yaml
        except ImportError:
            sys.exit("需要 PyYAML 读取 YAML:pip install pyyaml,或改用 .json 配置。")
        return yaml.safe_load(text) or {}
    return json.loads(text)


def _interactive_fill(raw: Dict[str, Any], assume_yes: bool) -> Dict[str, Any]:
    """对缺失的关键字段做交互兜底(非 TTY 或 --yes 时跳过)。"""
    if assume_yes or not sys.stdin.isatty():
        return raw
    for key, label in PROMPTABLE:
        if not raw.get(key):
            try:
                val = input(f"· {label}: ").strip()
            except EOFError:
                val = ""
            if val:
                raw[key] = val
    return raw


def _map(raw: Dict[str, Any]) -> RouteMap | None:
    m = raw.get("route_map")
    if not m:
        return None
    nodes = [MapNode(name=n["name"], x=float(n.get("x", 0.5)),
                     y=float(n.get("y", 0.5)), kind=n.get("kind", "city"))
             for n in m.get("nodes", [])]
    return RouteMap(title=m.get("title", "线路图"), nodes=nodes,
                    legend=m.get("legend", ""))


def build_trip(path: str, assume_yes: bool = False) -> Trip:
    raw = _load_raw(path)
    raw = _interactive_fill(raw, assume_yes)
    missing = [k for k in REQUIRED if not raw.get(k)]
    if missing:
        sys.exit(f"配置缺少必填字段: {', '.join(missing)}")
    return trip_from_dict(raw)


def trip_from_dict(raw: Dict[str, Any]) -> Trip:
    """从已解析的字典构造 Trip(供 Web 界面/程序化调用)。"""
    return Trip(
        title=raw.get("title", ""),
        subtitle=raw.get("subtitle", ""),
        origin=raw.get("origin", ""),
        party=raw.get("party", ""),
        dates=raw.get("dates", ""),
        days=[Day(label=d.get("label", ""), text=d.get("text", ""),
                  sea=bool(d.get("sea", False))) for d in raw.get("days", [])],
        segments=[Segment(section=s.get("section", ""), mode=s.get("mode", ""),
                          duration=s.get("duration", ""), price=s.get("price", ""),
                          verified=bool(s.get("verified", False)))
                  for s in raw.get("segments", [])],
        attractions=[Attraction(name=a.get("name", ""), desc=a.get("desc", ""),
                                 tag=a.get("tag", ""), tip=a.get("tip", ""),
                                 link=a.get("link", ""), icon=a.get("icon", "spot"))
                     for a in raw.get("attractions", [])],
        foods=[Food(name=f.get("name", ""), desc=f.get("desc", ""),
                    price=f.get("price", ""), group=f.get("group", "美食"),
                    icon=f.get("icon", "bowl"), link=f.get("link", ""))
               for f in raw.get("foods", [])],
        lodging=[Lodging(place=l.get("place", ""), rec=l.get("rec", ""),
                         price=l.get("price", ""), channel=l.get("channel", ""))
                 for l in raw.get("lodging", [])],
        budget=[BudgetItem(item=b.get("item", ""), amount=b.get("amount", ""))
                for b in raw.get("budget", [])],
        budget_total=raw.get("budget_total", ""),
        warnings=list(raw.get("warnings", [])),
        route_map=_map(raw),
        transport_note=raw.get("transport_note", ""),
    )
