# -*- coding: utf-8 -*-
"""可选联网增强(best-effort,失败即兜底到配置)。

设计原则:
  * 联网只做“补充/核实”,绝不覆盖用户在配置里写死的内容。
  * 任何网络异常、解析失败都被吞掉,行程照常用配置数据生成。
  * 通过 provider 接口可插拔;默认 provider 用 requests 查询公开的
    12306 车站-车次时刻页(仅示例,站点改版会失效,故必须兜底)。

⚠ 车次/票价/门票会随时变动,联网结果仅供参考,成品仍提示“以官方实时为准”。
"""
from __future__ import annotations
import re
from typing import Optional
from .models import Trip

_UA = {"User-Agent": "Mozilla/5.0 (tripgen; enrichment best-effort)"}


class TrainProvider:
    """车次核实 provider 接口。返回一段人类可读的核实说明,或 None。"""
    def verify(self, section: str, mode: str) -> Optional[str]:
        raise NotImplementedError


class HttpTrainProvider(TrainProvider):
    """最小实现:提取车次号,尝试从公开查询页确认其“存在”。

    仅作演示——不同站点结构不同且会改版,所以一律 try/except 兜底。
    """
    def verify(self, section: str, mode: str) -> Optional[str]:
        m = re.search(r"([GDCKZTSY]\d{1,4})", mode)
        if not m:
            return None
        train_no = m.group(1)
        try:
            import requests
        except ImportError:
            return None
        try:
            # 示例查询端点(仅演示;实际部署请替换为可用的官方/授权数据源)
            url = f"https://search.12306.cn/search/v1/train/search?keyword={train_no}"
            r = requests.get(url, headers=_UA, timeout=6)
            if r.ok and train_no in r.text:
                return f"{train_no} 已在公开数据中检索到(仍以 12306 实时为准)"
        except Exception:
            return None
        return None


def enrich_trip(trip: Trip, provider: Optional[TrainProvider] = None,
                verbose: bool = False) -> Trip:
    """就地增强 trip:标记已核实的车次,追加核实说明。返回同一个 trip。"""
    provider = provider or HttpTrainProvider()
    verified = []
    for seg in trip.segments:
        try:
            note = provider.verify(seg.section, seg.mode)
        except Exception:
            note = None
        if note:
            seg.verified = True
            verified.append(note)
            if verbose:
                print(f"  ✓ {seg.section}: {note}")
        elif verbose:
            print(f"  · {seg.section}: 未能联网核实,沿用配置")
    if verified:
        tail = "联网核实:" + ";".join(verified) + "。"
        trip.transport_note = (trip.transport_note + " " + tail).strip()
    return trip
