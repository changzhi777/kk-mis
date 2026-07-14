"""Storage Protocol — 抽象接口（S3 兼容语义）。

引入理由：kk-mis 14 个写文件点直接 Path.write_bytes()，未来切 COS/OSS/S3 改造成本高。
本 Protocol 让业务代码只依赖抽象，admin 通过 STORAGE_BACKEND env 切换 local / cos 实现。

设计要点：
- async-first（FastAPI 友好）
- 不暴露对象存储后端细节（业务只见 ObjectKey / UploadRequest / UploadResult）
- 协议方法贴近 S3 行业惯例（put_object / get_object / head_object / multipart_*）
- presigned_upload / presigned_download 给前端直传
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import BinaryIO, Literal


# ── Domain Types ────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ObjectKey:
    """对象存储路径。

    约束：
    - 不含 '..'（防路径遍历）
    - 不以 '/' 开头（保持相对）
    - 总长度 ≤ 1024
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("ObjectKey.value 不能为空")
        if self.value.startswith("/"):
            raise ValueError("ObjectKey 不能以 '/' 开头")
        if any(segment == ".." for segment in self.value.split("/")):
            raise ValueError("ObjectKey 不允许含 '..' 段")
        if "\\" in self.value:
            raise ValueError("ObjectKey 不允许含反斜杠")
        if len(self.value) > 1024:
            raise ValueError("ObjectKey 长度超 1024")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class UploadRequest:
    """上传请求。"""

    key: ObjectKey
    data: bytes | BinaryIO
    content_type: str = "application/octet-stream"
    metadata: Mapping[str, str] | None = None
    cache_control: str | None = None


@dataclass(frozen=True, slots=True)
class UploadResult:
    """上传结果。"""

    key: ObjectKey
    url: str           # 公开 URL 或签名 URL（看 Storage 实现）
    etag: str
    size: int
    version_id: str | None = None


@dataclass(frozen=True, slots=True)
class ObjectMeta:
    """对象元数据（head / list 通用）。"""

    key: ObjectKey
    size: int
    etag: str
    content_type: str | None
    last_modified: datetime
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PresignedUpload:
    """前端直传预签名。"""

    url: str
    method: Literal["PUT", "POST"] = "PUT"
    key: ObjectKey | None = None
    expires_at: datetime | None = None
    required_headers: Mapping[str, str] = field(default_factory=dict)
    max_size: int | None = None


@dataclass(frozen=True, slots=True)
class PresignedDownload:
    """私有对象预签名下载。"""

    url: str
    expires_at: datetime


# ── Protocol ────────────────────────────────────────────────────────


class Storage(ABC):
    """对象存储抽象（ABC 风格）。

    实现要求：
    - 所有 IO 方法 async（local 也要 run_in_executor，不阻塞 event loop）
    - 错误必须抛 errors.py 内的 StorageError 子类
    - backend='cos' 在 Phase 1 才实装

    ABC 保证：子类必须实现所有 @abstractmethod，否则实例化时抛 TypeError。
    """

    @abstractmethod
    async def put(self, req: UploadRequest) -> UploadResult:
        """上传 bytes / file-like；返 etag + url + size。"""

    @abstractmethod
    async def get_stream(self, key: ObjectKey) -> AsyncIterator[bytes]:
        """流式读大文件；不存在抛 ObjectNotFound。"""

    @abstractmethod
    async def get_bytes(self, key: ObjectKey) -> bytes:
        """整读（小文件用）；不存在抛 ObjectNotFound。"""

    @abstractmethod
    async def head(self, key: ObjectKey) -> ObjectMeta | None:
        """元数据；不存在返 None。"""

    @abstractmethod
    async def exists(self, key: ObjectKey) -> bool:
        """存在与否。"""

    @abstractmethod
    async def delete(self, key: ObjectKey) -> bool:
        """删对象 + 可选清 sidecar；返是否实际删除。"""

    @abstractmethod
    async def presigned_upload(
        self,
        key: ObjectKey,
        *,
        content_type: str,
        expires: timedelta,
    ) -> PresignedUpload:
        """前端直传预签名（local backend 通常 NotImplementedError）。"""

    @abstractmethod
    async def presigned_download(
        self,
        key: ObjectKey,
        *,
        expires: timedelta,
    ) -> PresignedDownload:
        """私有对象预签名下载。"""

    @abstractmethod
    async def list_objects(
        self,
        prefix: str,
        *,
        recursive: bool = False,
    ) -> AsyncIterator[ObjectMeta]:
        """列 prefix 下的对象（异步迭代器）。"""

    @abstractmethod
    async def health(self) -> dict[str, str]:
        """返 backend / root_dir 等元数据。"""
