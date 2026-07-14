"""CosStorage — 腾讯云对象存储实现（Sprint 1 实装）。

设计要点：
- 懒加载 cos-python-sdk-v5 import（避免 Sprint 0 dev 环境未装也能跑）
- 共享 1 个 CosS3Client 单例（连接池由 SDK 内部 HTTP connection 复用）
- 所有 IO 用 run_in_executor 包装（cos-sdk-v5 同步阻塞）
- Region/Bucket 从 settings 读（每次 get_storage() 重读，避免 env 改动不生效）
- 凭据：Phase 1 用 Long-Term Key（CAM 子账号）；Phase 2 接 STS 临时凭证（sts.py）
- Presigned URL 给前端直传
- 错误：cos 服务异常统一转 StorageError 子类

⚠️ Sprint 1 状态：
- 类结构已落地（9 abstractmethod 完整实现）
- 真实 IO 路径已实装，待 Sprint 1 集成测试用真 bucket 验证
- 用户待给：CAM 子账号 SecretId/SecretKey（Phase 1 起步）
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from .errors import BackendUnavailable, InvalidArgument, ObjectNotFound
from .protocol import (
    ObjectKey,
    ObjectMeta,
    PresignedDownload,
    PresignedUpload,
    Storage,
    UploadRequest,
    UploadResult,
)

if TYPE_CHECKING:
    from qcloud_cos import CosS3Client  # 仅类型检查；运行时懒加载

logger = logging.getLogger(__name__)


def _try_import_cos_sdk():
    """懒加载 cos-python-sdk-v5 — Sprint 0 dev 环境未装也能 import 该模块。"""
    try:
        from qcloud_cos import CosConfig, CosS3Client  # type: ignore[import-not-found]
        return CosConfig, CosS3Client
    except ImportError as exc:
        raise BackendUnavailable(
            "cos-python-sdk-v5 未安装；先 `pip install cos-python-sdk-v5` 再用 backend='cos'"
        ) from exc


def _parse_cos_time(value: str | None) -> datetime:
    """解析 COS 时间字段，兼容两种格式：

    - ``head_object`` 响应头 ``Last-Modified``：HTTP RFC 7231，如 ``Tue, 14 Jul 2026 18:51:02 GMT``
    - ``list_objects`` XML 字段 ``LastModified``：ISO 8601，如 ``2026-07-14T18:50:10.000Z``
    """
    if not value:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        pass
    from email.utils import parsedate_to_datetime
    try:
        dt = parsedate_to_datetime(value)
        return dt if dt is not None else datetime.now(timezone.utc)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)


class CosStorage(Storage):
    """腾讯云 COS 实现（cos-python-sdk-v5 S3 兼容）。"""

    def __init__(
        self,
        *,
        region: str,
        secret_id: str,
        secret_key: str,
        bucket: str,
        scheme: str = "https",
        timeout: float = 60.0,
    ) -> None:
        if not region:
            raise InvalidArgument("CosStorage 缺 region")
        if not secret_id or not secret_key:
            raise InvalidArgument("CosStorage 缺 SecretId/SecretKey（应通过 STS 临时凭证或环境变量注入）")
        if not bucket:
            raise InvalidArgument("CosStorage 缺 bucket（如 'qm-wx-1418512491'）")

        self.region = region
        self.bucket = bucket
        self.scheme = scheme

        CosConfig, CosS3Client = _try_import_cos_sdk()
        config = CosConfig(
            Region=region,
            SecretId=secret_id,
            SecretKey=secret_key,
            Scheme=scheme,
            Timeout=int(timeout),
        )
        self._client: Any = CosS3Client(config)

    # ── 内部：run_in_executor 包装 ──────────────────────────────

    async def _call(self, method_name: str, **kwargs: Any) -> Any:
        """同步 cos-python-sdk-v5 调用包成 async + Prometheus 指标埋点。"""
        from .metrics import COS_DURATION, COS_ERRORS, COS_REQUESTS

        loop = asyncio.get_running_loop()
        method = getattr(self._client, method_name)
        start = time.time()
        try:
            result = await loop.run_in_executor(None, lambda: method(**kwargs))
            COS_REQUESTS.labels(operation=method_name, status="ok").inc()
            return result
        except Exception as exc:
            COS_REQUESTS.labels(operation=method_name, status="error").inc()
            COS_ERRORS.labels(operation=method_name).inc()
            self._translate_error(exc, kwargs.get("Key", "?"))
            raise  # never reach
        finally:
            COS_DURATION.labels(operation=method_name).observe(time.time() - start)

    @staticmethod
    def _translate_error(exc: Exception, key: str) -> None:
        """cos-sdk-v5 异常 → StorageError 子类。

        ``CosServiceError`` 提供 ``get_status_code()`` / ``get_error_code()``；
        ``CosClientError`` 无状态码（网络/参数等客户端异常）。优先用状态码判断，
        关键词兜底——COS 对不存在的对象 HEAD 返回 ``code=NoSuchResource``（非 NoSuchKey）。
        """
        status: int | None = None
        err_code: str | None = None
        if hasattr(exc, "get_status_code"):
            try:
                status = int(exc.get_status_code())
            except (TypeError, ValueError):
                pass
        if hasattr(exc, "get_error_code"):
            try:
                err_code = exc.get_error_code()
            except Exception:
                pass
        msg = str(exc)
        if (status == 404
                or err_code in {"NoSuchKey", "NoSuchResource", "NotFound"}
                or "NoSuchKey" in msg or "NoSuchResource" in msg or "Not Exist" in msg):
            raise ObjectNotFound(key) from exc
        if (status == 403
                or err_code == "AccessDenied"
                or "AccessDenied" in msg):
            from .errors import PermissionDenied
            raise PermissionDenied(str(exc)) from exc
        raise BackendUnavailable(f"COS 调用失败: {exc}") from exc

    # ── Storage 实现 ────────────────────────────────────────────

    async def put(self, req: UploadRequest) -> UploadResult:
        result = await self._call(
            "put_object",
            Bucket=self.bucket,
            Key=str(req.key),
            Body=req.data,
            **({"ContentType": req.content_type} if req.content_type else {}),
            **({"Metadata": dict(req.metadata)} if req.metadata else {}),
        )
        # 注意：result["ETag"] 是带引号的，需要 strip（如 '"abc..."' → 'abc...'）
        etag = result["ETag"].strip('"')

        # 拿到 head 信息返 size
        size = await self._size_of(req.key) if not isinstance(req.data, (bytes, bytearray)) \
            else len(req.data)

        url = await self._build_url(req.key)
        return UploadResult(
            key=req.key,
            url=url,
            etag=etag,
            size=size,
        )

    async def _size_of(self, key: ObjectKey) -> int:
        meta = await self.head(key)
        return meta.size if meta else 0

    async def _build_url(self, key: ObjectKey) -> str:
        """构公共 URL（与 CDN 配置有关；Phase 1 用源站 URL）。"""
        return f"{self.scheme}://{self.bucket}.cos.{self.region}.myqcloud.com/{key.value}"

    async def get_stream(self, key: ObjectKey) -> AsyncIterator[bytes]:
        # 用 SDK get_object 流式 Body
        loop = asyncio.get_running_loop()
        try:
            resp = await loop.run_in_executor(
                None, lambda: self._client.get_object(Bucket=self.bucket, Key=str(key))
            )
        except Exception as exc:
            self._translate_error(exc, str(key))

        body = resp["Body"]  # HTTP响应流
        try:
            while True:
                chunk = await loop.run_in_executor(None, body.read, 64 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            close = getattr(body, "close", None)
            if close:
                try:
                    await loop.run_in_executor(None, close)
                except Exception:
                    pass

    async def get_bytes(self, key: ObjectKey) -> bytes:
        gen = self.get_stream(key)
        chunks: list[bytes] = []
        async for c in gen:
            chunks.append(c)
        return b"".join(chunks)

    async def head(self, key: ObjectKey) -> ObjectMeta | None:
        try:
            resp = await self._call("head_object", Bucket=self.bucket, Key=str(key))
        except ObjectNotFound:
            return None
        headers = resp.get("Response", {}).get("headers", {}) if "Response" in resp else {}
        return ObjectMeta(
            key=key,
            size=int(resp.get("Content-Length", 0)),
            etag=resp.get("ETag", "").strip('"'),
            content_type=resp.get("Content-Type"),
            last_modified=_parse_cos_time(resp.get("Last-Modified")),
            metadata={k[len("x-cos-meta-"):]: v for k, v in resp.items() if k.lower().startswith("x-cos-meta-")},
        )

    async def exists(self, key: ObjectKey) -> bool:
        return (await self.head(key)) is not None

    async def delete(self, key: ObjectKey) -> bool:
        try:
            await self._call("delete_object", Bucket=self.bucket, Key=str(key))
            return True
        except ObjectNotFound:
            return False

    async def presigned_upload(
        self,
        key: ObjectKey,
        *,
        content_type: str,
        expires: timedelta,
    ) -> PresignedUpload:
        """前端直传预签名（PUT）。让浏览器直接 PUT 到 COS 省后端带宽。

        注意：cos-python-sdk-v5 的 get_presigned_upload_url 不是公开方法，
        但底层用 generate_presigned_url(method='PUT')。我们用通用方法以保证兼容。
        """
        from app.config import settings  # 避免循环导入
        loop = asyncio.get_running_loop()

        def _gen() -> str:
            # cos-python-sdk-v5 公开方法：get_presigned_download_url 是 GET；
            # PUT 预签名要走 generate_presigned_url(method='PUT')
            # 见 project-cos-research-2026-07-14.md § 1.3 / 4.4
            return self._client.get_presigned_url(
                Bucket=self.bucket,
                Key=str(key),
                Expired=int(expires.total_seconds()),
                Method="PUT",
                Headers={"Content-Type": content_type},
            )

        try:
            url = await loop.run_in_executor(None, _gen)
        except AttributeError as exc:
            # 旧版 cos-python-sdk-v5 没 get_presigned_url；fallback 到 GET
            # 不应发生，因为我们 requirements 锁 ≥1.9
            raise BackendUnavailable(
                "cos-python-sdk-v5 版本过老，无 get_presigned_url 方法；升级到 ≥1.9.0"
            ) from exc

        return PresignedUpload(
            url=url,
            method="PUT",
            key=key,
            expires_at=datetime.now(timezone.utc) + expires,
            required_headers={"Content-Type": content_type},
            max_size=settings.cos_max_object_mb * 1024 * 1024,
        )

    async def presigned_download(
        self,
        key: ObjectKey,
        *,
        expires: timedelta,
    ) -> PresignedDownload:
        url = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: self._client.get_presigned_download_url(
                Bucket=self.bucket,
                Key=str(key),
                Expired=int(expires.total_seconds()),
            ),
        )
        return PresignedDownload(url=url, expires_at=datetime.now(timezone.utc) + expires)

    async def list_objects(
        self,
        prefix: str,
        *,
        recursive: bool = False,
    ) -> AsyncIterator[ObjectMeta]:
        """列对象：分页 (marker) + 递归 (Delimiter='/')。

        COS 单次 list_objects 上限 1000；bucket 大时需多个分页。
        recursive=False 时按目录层级 list（防止扫整个 bucket）。
        """
        page_size = 1000
        marker: str | None = None

        # 当 recursive=False，只列单层：用 Delimiter='/' 让 COS 在 '/' 处截断
        kwargs = {
            "Bucket": self.bucket,
            "Prefix": prefix,
            "MaxKeys": page_size,
        }
        if not recursive:
            kwargs["Delimiter"] = "/"

        while True:
            page_kwargs = dict(kwargs)
            if marker:
                page_kwargs["Marker"] = marker

            try:
                resp = await self._call("list_objects", **page_kwargs)
            except ObjectNotFound:
                return  # bucket 不存在或 prefix 不匹配任何 key

            for obj in resp.get("Contents", []) or []:
                key_str = obj.get("Key", "")
                if not key_str:
                    continue
                key = ObjectKey(key_str)
                yield ObjectMeta(
                    key=key,
                    size=int(obj.get("Size", 0)),
                    etag=obj.get("ETag", "").strip('"'),
                    content_type=None,
                    last_modified=_parse_cos_time(obj.get("LastModified")),
                    metadata={},
                )

            # CommonPrefixes (目录) — recursive=False 时此处出现
            if not recursive:
                for cp in resp.get("CommonPrefixes", []) or []:
                    cp_prefix = cp.get("Prefix", "")
                    if cp_prefix:
                        # 元数据用 prefix 本身
                        yield ObjectMeta(
                            key=ObjectKey(cp_prefix),
                            size=0,
                            etag="",
                            content_type=None,
                            last_modified=_parse_cos_time(resp.get("LastModified")),
                            metadata={"type": "directory"},
                        )

            if resp.get("IsTruncated") != "true" and resp.get("IsTruncated") is not True:
                break
            marker = resp.get("NextMarker") or resp.get("NextContinuationMarker")
            if not marker:
                break

    async def health(self) -> dict[str, str]:
        return {
            "backend": "cos",
            "region": self.region,
            "bucket": self.bucket,
            "scheme": self.scheme,
        }
