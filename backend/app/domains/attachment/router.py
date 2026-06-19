import os
import urllib.parse
from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, File, Form, Request, Query
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.common.exceptions import BusinessException
from app.common.error_codes import UNAUTHORIZED, FORBIDDEN, NOT_FOUND
from app.domains.attachment import service
from app.domains.attachment.storage import get_full_path, build_object_key, StorageError

router = APIRouter(prefix="/api/v1/attachments", tags=["附件管理"])

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
ALLOWED_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.txt', '.csv', '.zip', '.rar', '.7z',
}
ALLOWED_MIME_PREFIXES = {
    'image/', 'application/pdf', 'application/msword',
    'application/vnd.openxmlformats', 'application/vnd.ms-',
    'text/plain', 'text/csv',
    'application/zip', 'application/x-rar', 'application/x-7z',
    'application/octet-stream',  # generic fallback for zip/rar
}

PRESIGN_EXPIRES = 600  # 10 minutes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _validate_ext(filename: str) -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext and ext not in ALLOWED_EXTENSIONS:
        raise BusinessException(message=f"不支持的文件类型: {ext}")
    return ext


def _validate_mime(content_type: Optional[str]) -> None:
    ct = (content_type or "").lower()
    if ct and ct != "application/octet-stream" and not any(ct.startswith(p) for p in ALLOWED_MIME_PREFIXES):
        raise BusinessException(message=f"不支持的内容类型: {ct}")


def _check_secrecy(att, current_user: dict) -> None:
    secrecy = getattr(att, "secrecy_level", "internal") or "internal"
    perms = current_user.get("permissions", [])
    if secrecy == "restricted" and "attachment:view_restricted" not in perms:
        raise BusinessException(message="此文件为受限密级，您没有下载权限")
    if secrecy == "confidential" and "attachment:view_confidential" not in perms:
        raise BusinessException(message="此文件为机密密级，您没有下载权限")


async def _authenticate(request: Request, token: Optional[str]) -> dict:
    """Authenticate from the Authorization header OR a ?token= query param.

    The query param is needed for file URLs used as <img>/<iframe>/<a href> where
    the browser cannot attach the Authorization header.
    """
    raw = None
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        raw = auth[7:]
    elif token:
        raw = token
    if not raw:
        raise BusinessException(code=UNAUTHORIZED, message="未认证")
    from app.domains.auth.jwt_handler import decode_token
    return decode_token(raw, expected_type="access")


# ---------------------------------------------------------------------------
# Upload (server-side multipart — used when backend is local storage)
# ---------------------------------------------------------------------------
@router.post("")
async def upload(
    file: UploadFile = File(...),
    biz_type: str = Form(None),
    biz_id: str = Form(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("attachment:upload")),
):
    filename = file.filename or "unknown"
    _validate_ext(filename)
    _validate_mime(file.content_type)

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise BusinessException(message=f"文件大小超过限制（最大 {MAX_FILE_SIZE // 1024 // 1024}MB）")

    try:
        att = await service.upload_attachment(
            db, tenant_id, current_user,
            filename, file.content_type or "application/octet-stream",
            content, biz_type, biz_id,
        )
    except StorageError as e:
        raise BusinessException(message=f"文件存储失败：{e}")
    return ok({
        "id": att.id, "original_name": att.original_name,
        "content_type": att.content_type, "file_size": att.file_size,
        "created_at": att.created_at.isoformat() if att.created_at else "",
    })


# ---------------------------------------------------------------------------
# Direct upload (browser → object storage) — 直传
# ---------------------------------------------------------------------------
class PresignUploadBody(BaseModel):
    filename: str
    content_type: Optional[str] = None
    file_size: Optional[int] = None
    biz_type: Optional[str] = None
    biz_id: Optional[str] = None


class RegisterBody(BaseModel):
    key: str
    original_name: str
    content_type: Optional[str] = None
    biz_type: Optional[str] = None
    biz_id: Optional[str] = None


@router.post("/presign-upload")
async def presign_upload(
    body: PresignUploadBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permissions("attachment:upload")),
):
    """Issue a presigned PUT URL for browser-direct upload.

    Returns {"mode": "multipart"} when the active backend is local storage —
    the client should then fall back to the regular POST /api/v1/attachments.
    """
    _validate_ext(body.filename)
    _validate_mime(body.content_type)
    if body.file_size and body.file_size > MAX_FILE_SIZE:
        raise BusinessException(message=f"文件大小超过限制（最大 {MAX_FILE_SIZE // 1024 // 1024}MB）")

    from app.domains.admin.service import resolve_storage_backend
    backend, storage_type = await resolve_storage_backend(db, tenant_id)
    if not backend.supports_direct():
        return ok({"mode": "multipart"})

    key = build_object_key(tenant_id, body.filename)
    try:
        url = backend.presign_put(key, expires=PRESIGN_EXPIRES, content_type=body.content_type)
    except StorageError as e:
        raise BusinessException(message=f"生成上传链接失败：{e}")
    return ok({
        "mode": "direct", "storage_backend": storage_type,
        "key": key, "upload_url": url, "method": "PUT", "expires_in": PRESIGN_EXPIRES,
    })


@router.post("/register")
async def register_uploaded(
    body: RegisterBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("attachment:upload")),
):
    """Register an attachment after a successful browser-direct upload."""
    import asyncio
    _validate_ext(body.original_name)
    # The key was minted by /presign-upload with the tenant prefix — re-check it.
    if not body.key.startswith(f"{tenant_id}/"):
        raise BusinessException(message="非法的存储路径")

    from app.domains.admin.service import resolve_storage_backend
    backend, storage_type = await resolve_storage_backend(db, tenant_id)
    if not backend.supports_direct():
        raise BusinessException(message="当前存储后端不支持直传")

    # Trust the object store, not the client, for size/content-type.
    try:
        st = await asyncio.to_thread(backend.stat, body.key)
    except Exception:
        st = None
    if not st:
        raise BusinessException(message="文件未上传成功，请重试")
    if st["size"] > MAX_FILE_SIZE:
        try:
            await backend.delete(body.key)
        except Exception:
            pass
        raise BusinessException(message=f"文件大小超过限制（最大 {MAX_FILE_SIZE // 1024 // 1024}MB）")

    att = await service.register_uploaded(
        db, tenant_id, current_user, body.key, body.original_name,
        body.content_type or st.get("content_type"), int(st["size"]),
        storage_type, body.biz_type, body.biz_id,
    )
    return ok({
        "id": att.id, "original_name": att.original_name,
        "content_type": att.content_type, "file_size": att.file_size,
        "created_at": att.created_at.isoformat() if att.created_at else "",
    })


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------
@router.get("/by_biz")
async def list_by_biz(
    biz_type: str,
    biz_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("attachment:download")),
):
    items = await service.list_by_biz(db, tenant_id, biz_type, biz_id)
    return ok([{
        "id": a.id, "original_name": a.original_name,
        "content_type": a.content_type, "file_size": a.file_size,
        "uploader_name": a.uploader_name,
        "secrecy_level": getattr(a, "secrecy_level", "internal") or "internal",
        "storage_backend": getattr(a, "storage_backend", "local") or "local",
        "created_at": a.created_at.isoformat() if a.created_at else "",
    } for a in items])


# ---------------------------------------------------------------------------
# Download / preview
# ---------------------------------------------------------------------------
@router.get("/{attachment_id}/url")
async def get_download_url(
    attachment_id: str,
    request: Request,
    download: int = Query(0, description="1=下载(attachment) 0=预览(inline)"),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("attachment:download")),
):
    """Return a directly-usable URL for preview/download.

    Object storage → a presigned URL (browser fetches OSS/MinIO directly).
    Local storage  → a short token-bearing URL back to this API.
    """
    att = await service.get_attachment(db, tenant_id, attachment_id)
    _check_secrecy(att, current_user)
    storage_type = att.storage_backend or "local"
    inline = not download

    if storage_type != "local":
        from app.domains.admin.service import resolve_storage_backend
        try:
            backend, _ = await resolve_storage_backend(db, tenant_id, storage_type)
            url = backend.presign_get(att.stored_path, expires=PRESIGN_EXPIRES, filename=att.original_name, inline=inline)
        except StorageError as e:
            raise BusinessException(message=f"生成链接失败：{e}")
        if url:
            return ok({"url": url, "direct": True, "expires_in": PRESIGN_EXPIRES})

    # Local (or presign unsupported): self URL carrying the caller's token.
    raw = request.headers.get("Authorization", "")
    raw = raw[7:] if raw.startswith("Bearer ") else ""
    inline_flag = 1 if inline else 0
    url = (
        f"/api/v1/attachments/{attachment_id}/download"
        f"?inline={inline_flag}&token={urllib.parse.quote(raw)}"
    )
    return ok({"url": url, "direct": False, "expires_in": 0})


@router.get("/{attachment_id}/download")
async def download(
    attachment_id: str,
    request: Request,
    token: Optional[str] = Query(None),
    inline: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    current_user = await _authenticate(request, token)
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise BusinessException(code=UNAUTHORIZED, message="租户信息缺失")
    if "attachment:download" not in current_user.get("permissions", []):
        raise BusinessException(code=FORBIDDEN, message="缺少权限: attachment:download")

    att = await service.get_attachment(db, tenant_id, attachment_id)
    _check_secrecy(att, current_user)

    storage_type = att.storage_backend or "local"
    media_type = att.content_type or "application/octet-stream"
    disposition = "inline" if inline else "attachment"

    if storage_type == "local":
        full_path = get_full_path(att.stored_path)
        if not os.path.exists(full_path):
            raise BusinessException(code=NOT_FOUND, message="文件不存在")
        return FileResponse(
            path=full_path, filename=att.original_name,
            media_type=media_type, content_disposition_type=disposition,
        )

    # Object storage: redirect to a presigned URL (browser fetches directly).
    from app.domains.admin.service import resolve_storage_backend
    try:
        backend, _ = await resolve_storage_backend(db, tenant_id, storage_type)
        url = backend.presign_get(att.stored_path, expires=PRESIGN_EXPIRES, filename=att.original_name, inline=bool(inline))
    except StorageError:
        raise BusinessException(code=NOT_FOUND, message="文件不存在")
    if not url:
        raise BusinessException(message="文件下载失败，请检查存储配置")
    return RedirectResponse(url)


@router.delete("/{attachment_id}")
async def delete_attachment(
    attachment_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("attachment:upload")),
):
    await service.delete_attachment(db, tenant_id, attachment_id)
    return ok(None)
