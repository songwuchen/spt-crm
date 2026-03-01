from sqlalchemy import String, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class Attachment(TenantScopedBase):
    __tablename__ = "attachments"

    original_name: Mapped[str] = mapped_column(String(500), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(200))
    file_size: Mapped[int] = mapped_column(BigInteger, default=0)
    uploader_id: Mapped[str] = mapped_column(String(36), nullable=False)
    uploader_name: Mapped[str | None] = mapped_column(String(100))
    secrecy_level: Mapped[str | None] = mapped_column(String(16), default="internal")
    # public / internal / confidential / restricted


class AttachmentLink(TenantScopedBase):
    __tablename__ = "attachment_links"

    attachment_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    biz_type: Mapped[str] = mapped_column(String(50), nullable=False)  # customer / lead / contact
    biz_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
