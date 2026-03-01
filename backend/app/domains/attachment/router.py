import os
from fastapi import APIRouter, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.common.exceptions import BusinessException
from app.domains.attachment import service
from app.domains.attachment.storage import get_full_path

router = APIRouter(prefix="/api/v1/attachments", tags=["附件管理"])

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
ALLOWED_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.txt', '.csv', '.zip', '.rar', '.7z',
}


@router.post("")
async def upload(
    file: UploadFile = File(...),
    biz_type: str = Form(None),
    biz_id: str = Form(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("attachment:upload")),
):
    # Validate file extension
    filename = file.filename or "unknown"
    ext = os.path.splitext(filename)[1].lower()
    if ext and ext not in ALLOWED_EXTENSIONS:
        raise BusinessException(message=f"不支持的文件类型: {ext}")

    content = await file.read()

    # Validate file size
    if len(content) > MAX_FILE_SIZE:
        raise BusinessException(message=f"文件大小超过限制（最大 {MAX_FILE_SIZE // 1024 // 1024}MB）")

    att = await service.upload_attachment(
        db, tenant_id, current_user,
        file.filename or "unknown", file.content_type or "application/octet-stream",
        content, biz_type, biz_id,
    )
    return ok({
        "id": att.id, "original_name": att.original_name,
        "content_type": att.content_type, "file_size": att.file_size,
        "created_at": att.created_at.isoformat() if att.created_at else "",
    })


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
        "created_at": a.created_at.isoformat() if a.created_at else "",
    } for a in items])


@router.get("/{attachment_id}/download")
async def download(
    attachment_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("attachment:download")),
):
    att = await service.get_attachment(db, tenant_id, attachment_id)

    # Secrecy level check
    secrecy = getattr(att, "secrecy_level", "internal") or "internal"
    user_perms = current_user.get("permissions", [])
    if secrecy == "restricted" and "attachment:view_restricted" not in user_perms:
        raise BusinessException(message="此文件为受限密级，您没有下载权限")
    if secrecy == "confidential" and "attachment:view_confidential" not in user_perms:
        raise BusinessException(message="此文件为机密密级，您没有下载权限")

    full_path = get_full_path(att.stored_path)
    if not os.path.exists(full_path):
        from app.common.error_codes import NOT_FOUND
        raise BusinessException(code=NOT_FOUND, message="文件不存在")

    return FileResponse(
        path=full_path,
        filename=att.original_name,
        media_type=att.content_type or "application/octet-stream",
    )


@router.delete("/{attachment_id}")
async def delete_attachment(
    attachment_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("attachment:upload")),
):
    await service.delete_attachment(db, tenant_id, attachment_id)
    return ok(None)
