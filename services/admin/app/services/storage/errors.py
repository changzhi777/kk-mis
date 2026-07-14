"""Storage 异常体系 — 收敛 S3/File 异常为业务层可识别的域错误。"""

from __future__ import annotations


class StorageError(Exception):
    """Storage 抽象根异常。"""


class ObjectNotFound(StorageError):
    """请求的对象不存在（head/get/stream/delete）。"""


class PermissionDenied(StorageError):
    """权限不足（403 / EPERM 等）。"""


class BackendUnavailable(StorageError):
    """后端不可用（5xx / 网络错误 / COS 凭据丢失）。"""


class InvalidArgument(StorageError):
    """参数非法（如 ObjectKey 含 '..'、存储路径越界）。"""
