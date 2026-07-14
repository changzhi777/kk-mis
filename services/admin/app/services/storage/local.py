"""LocalStorage — 本地文件系统实现（默认 backend）。

特点：
- 后端兼容老的 cms/media.py 行为（写 storage/uploads/{uuid}_{name}）
- 异步接口内部用 asyncio.to_thread（不阻塞 event loop）
- 元数据存 JSON sidecar（{filename}.meta.json），避免数据库 join
- presigned_upload 不支持 → 返 NotImplementedError（前端走 admin 中转）
"""

from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import os
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .errors import BackendUnavailable, ObjectNotFound
from .protocol import (
    ObjectKey,
    ObjectMeta,
    PresignedDownload,
    PresignedUpload,
    Storage,
    UploadRequest,
    UploadResult,
)

logger = logging.getLogger(__name__)

_META_SUFFIX = ".meta.json"


class LocalStorage(Storage):
    """本地文件 + JSON sidecar 元数据。"""

    def __init__(self, root_dir: str | Path) -> None:
        self.root = Path(root_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    # ── Path 安全 ──────────────────────────────────────────────

    def _resolve(self, key: ObjectKey) -> Path:
        """ObjectKey → 物理路径，拒绝越界。"""
        p = (self.root / key.value).resolve()
        try:
            p.relative_to(self.root)
        except ValueError as exc:
            from .errors import InvalidArgument
            raise InvalidArgument(f"ObjectKey 越界: {key.value}") from exc
        return p

    @staticmethod
    def _detect_content_type(key: ObjectKey) -> str:
        ctype, _ = mimetypes.guess_type(str(key))
        return ctype or "application/octet-stream"

    # ── Storage 实现 ────────────────────────────────────────────

    async def put(self, req: UploadRequest) -> UploadResult:
        def _sync_put() -> tuple[Path, int, str]:
            target = self._resolve(req.key)
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(req.data, (bytes, bytearray)):
                target.write_bytes(bytes(req.data))
                size = len(req.data)
            else:
                size = 0
                with target.open("wb") as f:
                    while True:
                        chunk = req.data.read(1024 * 1024)
                        if not chunk:
                            break
                        size += len(chunk)
                        f.write(chunk)
            meta = {
                "etag": uuid.uuid4().hex,             # 本地无 etag，用 uuid 占位（兼容 cos）
                "size": size,
                "content_type": req.content_type,
                "last_modified": datetime.now(timezone.utc).isoformat(),
                "metadata": dict(req.metadata or {}),
            }
            (target.with_name(target.name + _META_SUFFIX)).write_text(
                json.dumps(meta, ensure_ascii=False), encoding="utf-8"
            )
            return target, size, meta["etag"]

        try:
            target, size, etag = await asyncio.to_thread(_sync_put)
        except OSError as exc:
            raise BackendUnavailable(f"本地写文件失败: {exc}") from exc

        logger.debug("LocalStorage.put %s size=%d", req.key, size)
        return UploadResult(
            key=req.key,
            url=str(target.relative_to(self.root)),
            etag=etag,
            size=size,
        )

    async def get_stream(self, key: ObjectKey) -> AsyncIterator[bytes]:
        """流式读：Queue 桥接同步 producer 与 async consumer。"""
        path = self._resolve(key)
        if not path.is_file():
            raise ObjectNotFound(str(key))

        CHUNK = 1024 * 256
        queue: asyncio.Queue = asyncio.Queue(maxsize=4)
        loop = asyncio.get_running_loop()

        async def _run() -> None:
            def _producer() -> None:
                try:
                    with path.open("rb") as f:
                        while True:
                            chunk = f.read(CHUNK)
                            if not chunk:
                                break
                            loop.call_soon_threadsafe(queue.put_nowait, chunk)
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, None)  # EOF sentinel

            await asyncio.to_thread(_producer)

        task = asyncio.create_task(_run())
        try:
            while True:
                chunk = await queue.get()
                if chunk is None:
                    return  # async generator end
                yield chunk
        finally:
            if not task.done():
                task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass

    async def get_bytes(self, key: ObjectKey) -> bytes:
        path = self._resolve(key)
        if not path.is_file():
            raise ObjectNotFound(str(key))

        def _read() -> bytes:
            return path.read_bytes()

        try:
            return await asyncio.to_thread(_read)
        except OSError as exc:
            raise BackendUnavailable(f"本地读文件失败: {exc}") from exc

    async def head(self, key: ObjectKey) -> ObjectMeta | None:
        def _stat() -> tuple[Path, dict[str, Any]] | None:
            p = self._resolve(key)
            if not p.is_file():
                return None
            meta_path = p.with_name(p.name + _META_SUFFIX)
            if meta_path.is_file():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    meta = {}
            else:
                meta = {}
            return p, meta

        try:
            result = await asyncio.to_thread(_stat)
        except Exception as exc:  # 越界 → InvalidArgument 不吞
            if "越界" in str(exc) or "InvalidArgument" in type(exc).__name__:
                raise
            logger.warning("head 失败 %s: %s", key, exc)
            return None

        if result is None:
            return None
        p, meta = result
        st = await asyncio.to_thread(p.stat)
        ctime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
        return ObjectMeta(
            key=key,
            size=st.st_size,
            etag=meta.get("etag", ""),
            content_type=meta.get("content_type") or self._detect_content_type(key),
            last_modified=datetime.fromisoformat(meta["last_modified"]) if meta.get("last_modified") else ctime,
            metadata=meta.get("metadata", {}),
        )

    async def exists(self, key: ObjectKey) -> bool:
        try:
            return await asyncio.to_thread(self._resolve(key).is_file)
        except Exception:
            return False

    async def delete(self, key: ObjectKey) -> bool:
        def _rm() -> bool:
            try:
                p = self._resolve(key)
            except Exception:
                return False
            removed = False
            if p.is_file():
                p.unlink()
                removed = True
            meta_path = p.with_name(p.name + _META_SUFFIX)
            if meta_path.is_file():
                meta_path.unlink(missing_ok=True)
            return removed

        try:
            return await asyncio.to_thread(_rm)
        except OSError as exc:
            raise BackendUnavailable(f"本地删文件失败: {exc}") from exc

    async def presigned_upload(
        self,
        key: ObjectKey,
        *,
        content_type: str,
        expires: timedelta,
    ) -> PresignedUpload:
        """Local backend 不支持浏览器直传 —— 走 admin 中转。"""
        raise NotImplementedError(
            "LocalStorage 不支持 presigned_upload；前端请走 admin 中转 API"
        )

    async def presigned_download(
        self,
        key: ObjectKey,
        *,
        expires: timedelta,
    ) -> PresignedDownload:
        """本地后端：直接返相对路径（admin 路由 /file/{key} 服务）。"""
        # local backend 没有真正签名机制；返相对 key 让 admin 自己的鉴权保护
        url = f"/admin/api/v1/cms/media/file/{key.value}"
        return PresignedDownload(
            url=url,
            expires_at=datetime.now(timezone.utc) + expires,
        )

    async def list_objects(
        self,
        prefix: str,
        *,
        recursive: bool = False,
    ) -> AsyncIterator[ObjectMeta]:
        """扫 root 下以 prefix 开头的对象。"""
        # 简单实现：glob，相对 root
        base = self.root / prefix if prefix else self.root
        if not base.exists():
            return

        def _iter() -> list[Path]:
            if recursive or not base.exists():
                return sorted(base.rglob("*"))
            return sorted(base.glob("*"))

        files = await asyncio.to_thread(_iter)
        for f in files:
            if not f.is_file() or f.name.endswith(_META_SUFFIX):
                continue
            rel = str(f.relative_to(self.root))
            try:
                meta = await self.head(ObjectKey(rel))
            except Exception:
                continue
            if meta:
                yield meta

    async def health(self) -> dict[str, str]:
        return {
            "backend": "local",
            "root": str(self.root),
            "writable": "yes" if os.access(self.root, os.W_OK) else "no",
        }
