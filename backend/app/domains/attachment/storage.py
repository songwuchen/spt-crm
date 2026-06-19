"""Pluggable file storage backends.

Supports three backends, selectable per-tenant from 系统设置 → 文件存储:
- local : local filesystem under settings.UPLOAD_DIR (default, no config needed)
- minio : MinIO / any S3-compatible object storage
- oss   : Aliyun OSS

Each :class:`StorageBackend` works on an opaque ``key`` (the value stored in
``attachments.stored_path``, e.g. ``"<tenant>/<YYYY-MM>/<uuid>.ext"``). The same
key is reused as the object key in MinIO/OSS, so a file can be located regardless
of which backend it lives on.

The third-party SDKs (``minio``, ``oss2``) are imported lazily inside each backend
so the application starts even when they are not installed.
"""

import asyncio
import io
import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone

import aiofiles

from app.config import settings

STORAGE_TYPES = ("local", "minio", "oss")


def build_object_key(tenant_id: str, filename: str) -> str:
    """Build a unique, collision-free storage key for a new upload."""
    now = datetime.now(timezone.utc)
    ext = os.path.splitext(filename)[1] if "." in filename else ""
    stored_name = f"{uuid.uuid4()}{ext}"
    return f"{tenant_id}/{now.strftime('%Y-%m')}/{stored_name}"


def get_full_path(stored_path: str) -> str:
    """Absolute path of a locally-stored file."""
    return os.path.join(settings.UPLOAD_DIR, stored_path)


class StorageError(Exception):
    """Raised when a storage backend operation fails."""


class StorageBackend(ABC):
    type: str = "base"

    @abstractmethod
    async def save(self, key: str, content: bytes, content_type: str | None = None) -> None: ...

    @abstractmethod
    async def read(self, key: str) -> bytes: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    def test_connection(self) -> tuple[bool, str | None]:
        """Synchronous connectivity check. Returns (ok, error_message)."""
        return True, None


class LocalBackend(StorageBackend):
    type = "local"

    async def save(self, key: str, content: bytes, content_type: str | None = None) -> None:
        full_path = get_full_path(key)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        async with aiofiles.open(full_path, "wb") as f:
            await f.write(content)

    async def read(self, key: str) -> bytes:
        full_path = get_full_path(key)
        if not os.path.exists(full_path):
            raise StorageError("文件不存在")
        async with aiofiles.open(full_path, "rb") as f:
            return await f.read()

    async def delete(self, key: str) -> None:
        full_path = get_full_path(key)
        if os.path.exists(full_path):
            os.remove(full_path)


class MinioBackend(StorageBackend):
    type = "minio"

    def __init__(self, config: dict):
        self.endpoint = (config.get("endpoint") or "").replace("http://", "").replace("https://", "").strip("/")
        self.access_key = config.get("access_key") or ""
        self.secret_key = config.get("secret_key") or ""
        self.bucket = config.get("bucket") or ""
        self.secure = bool(config.get("secure", False))
        self.region = config.get("region") or None
        if not (self.endpoint and self.bucket):
            raise StorageError("MinIO 配置不完整（缺少 endpoint 或 bucket）")

    def _client(self):
        try:
            from minio import Minio
        except ImportError as e:
            raise StorageError("未安装 minio 依赖，请运行 pip install minio") from e
        return Minio(
            self.endpoint, access_key=self.access_key,
            secret_key=self.secret_key, secure=self.secure, region=self.region,
        )

    def _save_sync(self, key: str, content: bytes, content_type: str | None) -> None:
        client = self._client()
        if not client.bucket_exists(self.bucket):
            client.make_bucket(self.bucket)
        client.put_object(
            self.bucket, key, io.BytesIO(content), length=len(content),
            content_type=content_type or "application/octet-stream",
        )

    def _read_sync(self, key: str) -> bytes:
        client = self._client()
        resp = None
        try:
            resp = client.get_object(self.bucket, key)
            return resp.read()
        finally:
            if resp is not None:
                resp.close()
                resp.release_conn()

    def _delete_sync(self, key: str) -> None:
        self._client().remove_object(self.bucket, key)

    async def save(self, key: str, content: bytes, content_type: str | None = None) -> None:
        await asyncio.to_thread(self._save_sync, key, content, content_type)

    async def read(self, key: str) -> bytes:
        return await asyncio.to_thread(self._read_sync, key)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._delete_sync, key)

    def test_connection(self) -> tuple[bool, str | None]:
        try:
            self._client().bucket_exists(self.bucket)
            return True, None
        except Exception as e:  # noqa: BLE001 — surface any SDK/connection error to the admin
            return False, str(e)


class OssBackend(StorageBackend):
    type = "oss"

    def __init__(self, config: dict):
        self.endpoint = config.get("endpoint") or ""
        self.access_key = config.get("access_key") or ""
        self.secret_key = config.get("secret_key") or ""
        self.bucket = config.get("bucket") or ""
        if not (self.endpoint and self.bucket):
            raise StorageError("阿里云 OSS 配置不完整（缺少 endpoint 或 bucket）")

    def _bucket(self):
        try:
            import oss2
        except ImportError as e:
            raise StorageError("未安装 oss2 依赖，请运行 pip install oss2") from e
        auth = oss2.Auth(self.access_key, self.secret_key)
        return oss2.Bucket(auth, self.endpoint, self.bucket)

    async def save(self, key: str, content: bytes, content_type: str | None = None) -> None:
        headers = {"Content-Type": content_type} if content_type else None
        await asyncio.to_thread(lambda: self._bucket().put_object(key, content, headers=headers))

    async def read(self, key: str) -> bytes:
        return await asyncio.to_thread(lambda: self._bucket().get_object(key).read())

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(lambda: self._bucket().delete_object(key))

    def test_connection(self) -> tuple[bool, str | None]:
        try:
            self._bucket().get_bucket_info()
            return True, None
        except Exception as e:  # noqa: BLE001 — surface any SDK/connection error to the admin
            return False, str(e)


def get_backend(storage_type: str | None, config: dict | None = None) -> StorageBackend:
    """Build a storage backend from a (decrypted) provider config dict."""
    storage_type = (storage_type or "local").lower()
    if storage_type == "minio":
        return MinioBackend(config or {})
    if storage_type == "oss":
        return OssBackend(config or {})
    return LocalBackend()


async def save_file(tenant_id: str, filename: str, content: bytes) -> str:
    """Backward-compatible helper: save to local storage and return the key."""
    key = build_object_key(tenant_id, filename)
    await LocalBackend().save(key, content)
    return key
