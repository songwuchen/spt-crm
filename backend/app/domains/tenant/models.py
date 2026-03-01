from sqlalchemy import String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.database import PlatformBase


class PlatformTenant(PlatformBase):
    __tablename__ = "platform_tenants"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(String(50), default="free")  # free / pro / enterprise
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    contact_name: Mapped[str | None] = mapped_column(String(100))
    contact_phone: Mapped[str | None] = mapped_column(String(30))
    contact_email: Mapped[str | None] = mapped_column(String(200))
    remark: Mapped[str | None] = mapped_column(Text)
