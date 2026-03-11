import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND
from app.domains.attachment.models import Attachment, AttachmentLink
from app.domains.attachment.storage import save_file

logger = logging.getLogger("spt_crm.attachment")


async def upload_attachment(
    db: AsyncSession, tenant_id: str, user: dict,
    filename: str, content_type: str, content: bytes,
    biz_type: str | None = None, biz_id: str | None = None,
) -> Attachment:
    stored_path = await save_file(tenant_id, filename, content)

    att = Attachment(
        id=generate_uuid(), tenant_id=tenant_id,
        original_name=filename, stored_path=stored_path,
        content_type=content_type, file_size=len(content),
        uploader_id=user["sub"], uploader_name=user.get("real_name") or user.get("username"),
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
        select(Attachment).where(Attachment.id.in_(link_q)).order_by(Attachment.created_at.desc())
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
    # Delete DB record first, then attempt file cleanup
    await db.delete(att)
    await db.commit()

    # Best-effort file deletion — DB record already removed
    import os
    from app.domains.attachment.storage import get_full_path
    full_path = get_full_path(att.stored_path)
    try:
        if os.path.exists(full_path):
            os.remove(full_path)
    except OSError as e:
        logger.warning("Failed to delete attachment file %s: %s", full_path, e)
