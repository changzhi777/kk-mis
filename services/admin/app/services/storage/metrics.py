"""COS 操作 Prometheus 指标（Phase 5 监控）。

cos.py 的 _call 方法自动埋点：每次 COS 调用计 1 次 + 耗时直方图 + 错误计数。
/metrics 端点（main.py）暴露给 Prometheus 抓取。
"""
from prometheus_client import Counter, Histogram

COS_REQUESTS = Counter(
    "cos_requests_total",
    "COS 操作总次数",
    ["operation", "status"],  # operation: put_object/get_object/head_object/...; status: ok|error
)

COS_ERRORS = Counter(
    "cos_errors_total",
    "COS 操作错误总数",
    ["operation"],
)

COS_DURATION = Histogram(
    "cos_duration_seconds",
    "COS 操作耗时（秒）",
    ["operation"],
)
