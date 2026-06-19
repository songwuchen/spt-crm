import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND
from app.domains.attachment.models import Attachment, AttachmentLink
from app.domains.attachment.storage import build_object_key

logger = logging.getLogger("spt_crm.attachment")


async def upload_attachment(
    db: AsyncSession, tenant_id: str, user: dict,
    filename: str, content_type: str, content: bytes,
    biz_type: str | None = None, biz_id: str | None = None,
) -> Attachment:
    from app.domains.admin.service import resolve_storage_backend
    backend, storage_type = await resolve_storage_backend(db, tenant_id)
    stored_path = build_object_key(tenant_id, filename)
    await backend.save(stored_path, content, content_type)

    att = Attachment(
        id=generate_uuid(), tenant_id=tenant_id,
        original_name=filename, stored_path=stored_path,
        content_type=content_type, file_size=len(content),
        uploader_id=user["sub"], uploader_name=user.get("real_name") or user.get("username"),
        storage_backend=storage_type,
    )
    db.add(att)

    if biz_type and biz_id:
        link = AttachmentLink(
            id=generate_uuid(), tenant_id=tenant_id,
            attachment_id=att.id, biz_type=biz_type, biz_id=biz_id,
        )
        db.add(link)

    await db.commit()
    await db.refresh(att)
    return att


async def register_uploaded(
    db: AsyncSession, tenant_id: str, user: dict,
    stored_path: str, filename: str, content_type: str | None, file_size: int,
    storage_type: str, biz_type: str | None = None, biz_id: str | None = None,
) -> Attachment:
    """Create an attachment record for a file already uploaded directly to object storage."""
    att = Attachment(
        id=generate_uuid(), tenant_id=tenant_id,
        original_name=filename, stored_path=stored_path,
        content_type=content_type, file_size=file_size,
        uploader_id=user["sub"], uploader_name=user.get("real_name") or user.get("username"),
        storage_backend=storage_type,
    )
    db.add(att)

    if biz_type and biz_id:
        link = AttachmentLink(
            id=generate_uuid(), tenant_id=tenant_id,
            attachment_id=att.id, biz_type=biz_type, biz_id=biz_id,
        )
        db.add(link)

    await db.commit()
    await db.refresh(att)
    return att


async def list_by_biz(db: AsyncSession, tenant_id: str, biz_type: str, biz_id: str) -> list[Attachment]:
    link_q = select(AttachmentLink.attachment_id).where(
        AttachmentLink.tenant_id == tenant_id,
        AttachmentLink.biz_type == biz_type,
        AttachmentLink.biz_id == biz_id,
    )
    result = await db.execute(
        select(Attachment).where(Attachment.id.in_(link_q), Attachment.tenant_id == tenant_id).order_by(Attachment.created_at.desc())
    )
    return list(result.scalars().all())


async def get_attachment(db: AsyncSession, tenant_id: str, attachment_id: str) -> Attachment:
    att = (await db.execute(
        select(Attachment).where(Attachment.id == attachment_id, Attachment.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not att:
        raise BusinessException(code=NOT_FOUND, message="附件不存在")
    return att


async def delete_attachment(db: AsyncSession, tenant_id: str, attachment_id: str):
    att = await get_attachment(db, tenant_id, attachment_id)
    # Delete links
    links = (await db.execute(
        select(AttachmentLink).where(AttachmentLink.attachment_id == attachment_id)
    )).scalars().all()
    for link in links:
        await db.delete(link)
    # Capture storage location before the record is removed
    stored_path, storage_type = att.stored_path, att.storage_backend or "local"

    # Delete DB record first, then attempt file cleanup
    await db.delete(att)
    await db.commit()

    # Best-effort file deletion on whichever backend the file lives — DB record already removed
    from app.domains.admin.service import resolve_storage_backend
    try:
        backend, _ = await resolve_storage_backend(db, tenant_id, storage_type)
        await backend.delete(stored_path)
    except Exception as e:  # noqa: BLE001 — never fail the request on cleanup
        logger.warning("Failed to delete attachment file %s (%s): %s", stored_path, storage_type, e)
