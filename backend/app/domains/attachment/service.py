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


async def assert_attachment_visible(db: AsyncSession, tenant_id: str, user: dict | None, att: Attachment) -> None:
    """附件自身没有归属，可见性取决于它挂在哪些业务对象上。

    此前只按 tenant 取附件，任何人拿到 id（或 biz_type/biz_id）就能下载别人客户的合同扫描件。
    任一父对象可见即放行；上传者本人始终可见。
    未挂任何业务对象的附件（上传后尚未关联、导入产物等）无从判定，按原样放行。
    user=None 为系统内部调用（PDF 生成/导出任务等），跳过。
    """
    if user is None:
        return
    if att.uploader_id and att.uploader_id == user.get("sub"):
        return
    links = (await db.execute(
        select(AttachmentLink).where(
            AttachmentLink.tenant_id == tenant_id,
            AttachmentLink.attachment_id == att.id,
        )
    )).scalars().all()
    if not links:
        return

    from app.common.error_codes import FORBIDDEN
    from app.domains.activity.service import assert_biz_object_visible
    for ln in links:
        try:
            await assert_biz_object_visible(db, tenant_id, user, ln.biz_type, ln.biz_id, label="该附件")
            return
        except BusinessException:
            continue
    raise BusinessException(code=FORBIDDEN, message="无权访问该附件（不在您的数据范围内）")


async def list_by_biz(
    db: AsyncSession, tenant_id: str, biz_type: str, biz_id: str, user: dict | None = None,
) -> list[Attachment]:
    # 先确认父对象可见：此前只按 biz_type/biz_id 取，等于把任意记录的附件开放给全员
    from app.domains.activity.service import assert_biz_object_visible
    await assert_biz_object_visible(db, tenant_id, user, biz_type, biz_id, label="该业务对象的附件")

    link_q = select(AttachmentLink.attachment_id).where(
        AttachmentLink.tenant_id == tenant_id,
        AttachmentLink.biz_type == biz_type,
        AttachmentLink.biz_id == biz_id,
    )
    result = await db.execute(
        select(Attachment).where(Attachment.id.in_(link_q), Attachment.tenant_id == tenant_id).order_by(Attachment.created_at.desc())
    )
    return list(result.scalars().all())


async def get_attachment(db: AsyncSession, tenant_id: str, attachment_id: str, user: dict | None = None) -> Attachment:
    """按 id 取附件。传入 user 时按所挂业务对象校验可见性。user=None 为系统内部调用。"""
    att = (await db.execute(
        select(Attachment).where(Attachment.id == attachment_id, Attachment.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not att:
        raise BusinessException(code=NOT_FOUND, message="附件不存在")
    await assert_attachment_visible(db, tenant_id, user, att)
    return att


async def delete_attachment(db: AsyncSession, tenant_id: str, attachment_id: str, user: dict | None = None):
    att = await get_attachment(db, tenant_id, attachment_id, user)
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
