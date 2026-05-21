"""Knowledge base service — document management, chunking, and RAG search."""

import re
from typing import Optional
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND
from app.domains.ai_center.knowledge_models import KnowledgeDocument, KnowledgeChunk


# ==================== Document CRUD ====================

async def list_documents(
    db: AsyncSession, tenant_id: str,
    doc_type: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = 1, page_size: int = 20,
):
    q = (
        select(KnowledgeDocument)
        .where(KnowledgeDocument.tenant_id == tenant_id, KnowledgeDocument.is_deleted == False)
        .order_by(KnowledgeDocument.created_at.desc())
    )
    if doc_type:
        q = q.where(KnowledgeDocument.doc_type == doc_type)
    if keyword:
        q = q.where(KnowledgeDocument.title.ilike(f"%{keyword}%"))

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    rows = (await db.execute(q.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return rows, total


async def get_document(db: AsyncSession, tenant_id: str, doc_id: str) -> KnowledgeDocument:
    doc = (await db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == doc_id,
            KnowledgeDocument.tenant_id == tenant_id,
            KnowledgeDocument.is_deleted == False,
        )
    )).scalar_one_or_none()
    if not doc:
        raise BusinessException(code=NOT_FOUND, message="文档不存在")
    return doc


async def create_document(
    db: AsyncSession, tenant_id: str, data: dict, current_user: dict,
) -> KnowledgeDocument:
    content_text = data.get("content_text", "")
    doc = KnowledgeDocument(
        id=generate_uuid(),
        tenant_id=tenant_id,
        title=data["title"],
        doc_type=data.get("doc_type", "other"),
        source_filename=data.get("source_filename"),
        content_text=content_text,
        metadata_json=data.get("metadata_json"),
        created_by_id=current_user.get("sub"),
        created_by_name=current_user.get("real_name", ""),
    )
    db.add(doc)
    await db.flush()

    # Auto-chunk the content
    chunks = _chunk_text(content_text)
    for i, chunk_text in enumerate(chunks):
        chunk = KnowledgeChunk(
            id=generate_uuid(),
            tenant_id=tenant_id,
            document_id=doc.id,
            chunk_index=i,
            content=chunk_text,
            token_count=_estimate_tokens(chunk_text),
        )
        db.add(chunk)

    doc.chunk_count = len(chunks)
    await db.commit()
    await db.refresh(doc)
    return doc


async def update_document(
    db: AsyncSession, tenant_id: str, doc_id: str, data: dict,
) -> KnowledgeDocument:
    doc = await get_document(db, tenant_id, doc_id)
    for k, v in data.items():
        if k in ("title", "doc_type", "metadata_json", "status"):
            setattr(doc, k, v)

    # If content changed, re-chunk
    if "content_text" in data and data["content_text"] != doc.content_text:
        doc.content_text = data["content_text"]
        # Delete old chunks
        old_chunks = (await db.execute(
            select(KnowledgeChunk).where(
                KnowledgeChunk.document_id == doc_id,
                KnowledgeChunk.tenant_id == tenant_id,
            )
        )).scalars().all()
        for c in old_chunks:
            await db.delete(c)
        # Create new chunks
        chunks = _chunk_text(data["content_text"])
        for i, chunk_text in enumerate(chunks):
            chunk = KnowledgeChunk(
                id=generate_uuid(),
                tenant_id=tenant_id,
                document_id=doc.id,
                chunk_index=i,
                content=chunk_text,
                token_count=_estimate_tokens(chunk_text),
            )
            db.add(chunk)
        doc.chunk_count = len(chunks)

    await db.commit()
    await db.refresh(doc)
    return doc


async def delete_document(db: AsyncSession, tenant_id: str, doc_id: str):
    doc = await get_document(db, tenant_id, doc_id)
    doc.is_deleted = True
    await db.commit()


# ==================== RAG Search ====================

async def search_chunks(
    db: AsyncSession, tenant_id: str,
    query: str,
    doc_type: Optional[str] = None,
    top_k: int = 5,
) -> list[dict]:
    """Search knowledge chunks by keyword matching. Returns top_k most relevant chunks."""
    q = (
        select(KnowledgeChunk, KnowledgeDocument.title.label("doc_title"))
        .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
        .where(
            KnowledgeChunk.tenant_id == tenant_id,
            KnowledgeDocument.tenant_id == tenant_id,
            KnowledgeDocument.is_deleted == False,
            KnowledgeDocument.status == "active",
        )
    )
    if doc_type:
        q = q.where(KnowledgeDocument.doc_type == doc_type)

    # Keyword-based search: split query into terms and match any
    terms = [t.strip() for t in query.split() if t.strip()]
    if terms:
        conditions = [KnowledgeChunk.content.ilike(f"%{term}%") for term in terms]
        q = q.where(or_(*conditions))

    q = q.limit(top_k * 3)  # fetch more, then rank
    rows = (await db.execute(q)).all()

    # Simple relevance scoring: count matching terms
    scored = []
    for row in rows:
        chunk = row[0]
        doc_title = row[1]
        score = sum(1 for term in terms if term.lower() in chunk.content.lower())
        scored.append({
            "chunk_id": chunk.id,
            "document_id": chunk.document_id,
            "doc_title": doc_title,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "score": score,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


async def get_rag_context(
    db: AsyncSession, tenant_id: str, query: str,
    doc_type: Optional[str] = None, max_tokens: int = 2000,
) -> str:
    """Build RAG context string from relevant knowledge chunks."""
    chunks = await search_chunks(db, tenant_id, query, doc_type=doc_type, top_k=8)
    if not chunks:
        return ""

    context_parts = []
    total_tokens = 0
    for c in chunks:
        est = _estimate_tokens(c["content"])
        if total_tokens + est > max_tokens:
            break
        context_parts.append(f"[{c['doc_title']}]\n{c['content']}")
        total_tokens += est

    return "\n\n---\n\n".join(context_parts)


# ==================== Helpers ====================

def _chunk_text(text: str, max_chunk_size: int = 500) -> list[str]:
    """Split text into chunks, respecting paragraph boundaries."""
    if not text:
        return []

    # Split by double newlines (paragraphs) or section headers
    paragraphs = re.split(r'\n{2,}', text.strip())

    chunks = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current_chunk) + len(para) + 2 <= max_chunk_size:
            current_chunk = (current_chunk + "\n\n" + para).strip()
        else:
            if current_chunk:
                chunks.append(current_chunk)
            # If a single paragraph exceeds max_chunk_size, split by sentences
            if len(para) > max_chunk_size:
                sentences = re.split(r'(?<=[。！？.!?])\s*', para)
                current_chunk = ""
                for sent in sentences:
                    if len(current_chunk) + len(sent) + 1 <= max_chunk_size:
                        current_chunk = (current_chunk + " " + sent).strip()
                    else:
                        if current_chunk:
                            chunks.append(current_chunk)
                        current_chunk = sent
            else:
                current_chunk = para

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def _estimate_tokens(text: str) -> int:
    """Rough token estimation: ~1.5 tokens per Chinese char, ~0.75 per English word."""
    chinese = len(re.findall(r'[\u4e00-\u9fff]', text))
    other = len(text) - chinese
    return int(chinese * 1.5 + other * 0.25)
