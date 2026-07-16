# -*- coding: utf-8 -*-
"""数据模型:一次行程的结构化描述。

所有生成器(PDF 正文 / HTML 攻略 / 合并)都以 Trip 为唯一数据源。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Segment:
    """一段交通。"""
    section: str            # 区段,如 "长沙 → 广州"
    mode: str               # 方式/车次,如 "K9275 卧铺 22:52→06:20"
    duration: str = ""      # 耗时
    price: str = ""         # 参考票价
    verified: bool = False  # 是否已核实(联网增强会置 True)


@dataclass
class Day:
    """一天的行程。"""
    label: str              # 如 "Day 1\n7/30 四"
    text: str               # 正文描述(可含 <b> 标签)
    sea: bool = False       # 海岛/主题色标记


@dataclass
class Attraction:
    """一个景点/取景地。"""
    name: str
    desc: str
    tag: str = ""           # 标签,如 "核心取景"
    tip: str = ""           # 贴士
    link: str = ""          # 官方/实拍图链接
    icon: str = "spot"      # svg.py 中的插画键


@dataclass
class Food:
    """一类美食。"""
    name: str
    desc: str               # 推荐店/说明
    price: str = ""         # 人均
    group: str = "美食"     # 分组,如 "汕头" / "潮州" / "广州"
    icon: str = "bowl"      # svg.py 中的美食插画键
    link: str = ""


@dataclass
class Lodging:
    place: str              # 地点/晚数
    rec: str                # 推荐
    price: str = ""
    channel: str = ""       # 订房渠道 / 联系方式(携程/美团/电话等)


@dataclass
class BudgetItem:
    item: str
    amount: str


@dataclass
class MapNode:
    """线路图上的一个节点(相对坐标 0-1)。"""
    name: str
    x: float
    y: float
    kind: str = "city"      # city / transfer / sea / origin


@dataclass
class RouteMap:
    title: str
    nodes: List[MapNode] = field(default_factory=list)
    legend: str = ""


@dataclass
class Trip:
    title: str
    subtitle: str = ""
    origin: str = ""
    party: str = ""                 # 如 "一大一小"
    dates: str = ""
    days: List[Day] = field(default_factory=list)
    segments: List[Segment] = field(default_factory=list)
    attractions: List[Attraction] = field(default_factory=list)
    foods: List[Food] = field(default_factory=list)
    lodging: List[Lodging] = field(default_factory=list)
    budget: List[BudgetItem] = field(default_factory=list)
    budget_total: str = ""
    warnings: List[str] = field(default_factory=list)
    route_map: Optional[RouteMap] = None
    transport_note: str = ""

    # ---- 便捷方法 ----
    def food_groups(self) -> List[str]:
        seen = []
        for f in self.foods:
            if f.group not in seen:
                seen.append(f.group)
        return seen

    def foods_in(self, group: str) -> List[Food]:
        return [f for f in self.foods if f.group == group]

    def used_chars(self) -> str:
        """收集所有会渲染到 PDF 的中文字符,用于字体子集化。"""
        buf = [self.title, self.subtitle, self.origin, self.party, self.dates,
               self.budget_total, self.transport_note]
        for d in self.days:
            buf += [d.label, d.text]
        for s in self.segments:
            buf += [s.section, s.mode, s.duration, s.price]
        for a in self.attractions:
            buf += [a.name, a.desc, a.tag, a.tip]
        for f in self.foods:
            buf += [f.name, f.desc, f.price, f.group]
        for l in self.lodging:
            buf += [l.place, l.rec, l.price, l.channel]
        for b in self.budget:
            buf += [b.item, b.amount]
        buf += self.warnings
        if self.route_map:
            buf.append(self.route_map.title)
            buf.append(self.route_map.legend)
            for n in self.route_map.nodes:
                buf.append(n.name)
        return "".join(x for x in buf if x)
