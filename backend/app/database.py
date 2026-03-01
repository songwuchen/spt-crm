import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class TenantScopedBase(Base):
    """Base class for all tenant-scoped models. Enforces tenant_id column."""

    __abstract__ = True

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class PlatformBase(Base):
    """Base class for platform-level models (not scoped to tenant)."""

    __abstract__ = True

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
