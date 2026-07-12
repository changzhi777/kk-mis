"""通用工具函数"""
import csv
import io
from datetime import datetime, timezone


def utcnow() -> datetime:
    """统一 UTC 当前时间（naive，兼容现有无时区 DateTime 列）。

    规避 ``datetime.utcnow()`` 在 Python 3.12+ 的 DeprecationWarning，
    全项目统一用此函数，语义与原 utcnow() 等价（返回无时区信息的 UTC 时间）。
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _csv_cell(v) -> str:
    """单元格值规范化（datetime → ISO，None → 空，Decimal → str）"""
    if v is None:
        return ""
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


def to_csv(rows: list[dict], columns: list[tuple[str, str]]) -> bytes:
    """生成 UTF-8 BOM 的 CSV 字节串（Excel 中文兼容，双击不乱码）。

    :param rows: 数据字典列表
    :param columns: [(字段名, 表头显示名), ...] —— 顺序即列顺序
    """
    buf = io.StringIO()
    buf.write("﻿")  # UTF-8 BOM
    writer = csv.writer(buf)
    writer.writerow([c[1] for c in columns])
    for row in rows:
        writer.writerow([_csv_cell(row.get(c[0])) for c in columns])
    return buf.getvalue().encode("utf-8")
