"""通用工具函数"""
from datetime import datetime, timezone


def utcnow() -> datetime:
    """统一 UTC 当前时间（naive，兼容现有无时区 DateTime 列）。

    规避 ``datetime.utcnow()`` 在 Python 3.12+ 的 DeprecationWarning，
    全项目统一用此函数，语义与原 utcnow() 等价（返回无时区信息的 UTC 时间）。
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
