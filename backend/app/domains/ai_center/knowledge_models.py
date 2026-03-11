"""Knowledge base models for RAG (Retrieval-Augmented Generation)."""

from sqlalchemy import String, Text, JSON, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class KnowledgeDocument(TenantScopedBase):
    """A document uploaded to the knowledge base."""
    __tablename__ = "knowledge_documents"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # faq / product / process / policy / manual / other
    source_filename: Mapped[str | None] = mapped_column(String(500))
    content_text: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    # {"tags": ["产品", "报价"], "category": "sales"}
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    # active / archived
    created_by_id: Mapped[str | None] = mapped_column(String(36))
    created_by_name: Mapped[str | None] = mapped_column(String(100))
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class KnowledgeChunk(TenantScopedBase):
    """A text chunk from a knowledge document, used for RAG retrieval."""
    __tablename__ = "knowledge_chunks"

    document_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    # {"heading": "第三章 报价流程", "page": 5}
