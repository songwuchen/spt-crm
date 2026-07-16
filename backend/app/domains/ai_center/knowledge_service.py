"""Knowledge base service — document management, chunking, and RAG search."""

import logging
import re
from typing import Optional
from sqlalchemy import select, func, or_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND
from app.domains.ai_center.knowledge_models import KnowledgeDocument, KnowledgeChunk

logger = logging.getLogger("spt_crm.ai.knowledge")

# 进程级缓存:knowledge_chunks 是否有 pgvector 的 embedding 列(部署后进程重启即刷新)
_HAS_EMBED_COL: bool | None = None

# search_chunks 的 emb_cfg 哨兵:区分"未传入→自行解析"与"显式传 None→不用嵌入"
_RESOLVE = object()


async def _has_embedding_column(db: AsyncSession) -> bool:
    global _HAS_EMBED_COL
    if _HAS_EMBED_COL is not None:
        return _HAS_EMBED_COL
    try:
        r = await db.execute(text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'knowledge_chunks' AND column_name = 'embedding'"
        ))
        _HAS_EMBED_COL = bool(r.scalar())
    except Exception:
        _HAS_EMBED_COL = False
    return _HAS_EMBED_COL


async def _resolve_embedding_cfg(db: AsyncSession, tenant_id: str) -> dict | None:
    """租户已启用且配置了嵌入模型时返回解密配置,否则 None。"""
    from app.domains.admin.service import resolve_ai_config
    cfg = await resolve_ai_config(db, tenant_id)
    return cfg.get("embedding")


async def _embed_document_chunks(db: AsyncSession, tenant_id: str, doc_id: str) -> None:
    """尽力而为地为文档的所有 chunk 生成并写入向量。失败不影响文档本身。"""
    cfg = await _resolve_embedding_cfg(db, tenant_id)
    if not cfg or not await _has_embedding_column(db):
        return
    from app.common.ai_embedding import embed_texts, _to_vec_literal
    rows = (await db.execute(
        select(KnowledgeChunk).where(
            KnowledgeChunk.document_id == doc_id,
            KnowledgeChunk.tenant_id == tenant_id,
        ).order_by(KnowledgeChunk.chunk_index)
    )).scalars().all()
    if not rows:
        return
    try:
        vecs = await embed_texts(cfg, [r.content for r in rows])
    except Exception as e:
        logger.warning("知识库嵌入失败(doc=%s): %s", doc_id, e)
        return
    for r, v in zip(rows, vecs):
        await db.execute(
            text("UPDATE knowledge_chunks SET embedding = (:v)::vector WHERE id = :id AND tenant_id = :t"),
            {"v": _to_vec_literal(v), "id": r.id, "t": tenant_id},
        )
    await db.commit()


async def _vector_search(
    db: AsyncSession, tenant_id: str, query: str,
    doc_type: Optional[str], top_k: int, emb_cfg: dict,
) -> Optional[list[dict]]:
    """pgvector 余弦近邻检索。成功返回结果列表,任何失败返回 None 以触发关键词回退。"""
    from app.common.ai_embedding import embed_query, _to_vec_literal
    try:
        qvec = await embed_query(emb_cfg, query)
    except Exception as e:
        logger.warning("查询向量化失败,回退关键词: %s", e)
        return None
    if not qvec:
        return None
    lit = _to_vec_literal(qvec)
    sql = (
        "SELECT c.id AS chunk_id, c.document_id, c.chunk_index, c.content, "
        "       d.title AS doc_title, 1 - (c.embedding <=> (:q)::vector) AS score "
        "FROM knowledge_chunks c "
        "JOIN knowledge_documents d ON c.document_id = d.id "
        "WHERE c.tenant_id = :t AND d.tenant_id = :t "
        "      AND d.is_deleted = false AND d.status = 'active' "
        "      AND c.embedding IS NOT NULL "
        + ("AND d.doc_type = :dt " if doc_type else "")
        + "ORDER BY c.embedding <=> (:q)::vector LIMIT :k"
    )
    params = {"q": lit, "t": tenant_id, "k": top_k}
    if doc_type:
        params["dt"] = doc_type
    try:
        rows = (await db.execute(text(sql), params)).mappings().all()
    except Exception as e:
        logger.warning("向量检索失败,回退关键词: %s", e)
        return None
    return [
        {
            "chunk_id": r["chunk_id"],
            "document_id": r["document_id"],
            "doc_title": r["doc_title"],
            "chunk_index": r["chunk_index"],
            "content": r["content"],
            "score": round(float(r["score"]), 4),
        }
        for r in rows
    ]


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
    await _embed_document_chunks(db, tenant_id, doc.id)
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
    if "content_text" in data:
        await _embed_document_chunks(db, tenant_id, doc.id)
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
    emb_cfg=_RESOLVE,
) -> list[dict]:
    """语义检索(pgvector 余弦)优先,未启用嵌入/无向量列时回退关键词匹配。

    emb_cfg: 传入已解析的嵌入配置可省一次 resolve_ai_config(DB+解密);默认 _RESOLVE 自行解析。
    """
    # ---- 向量检索路径 ----
    if emb_cfg is _RESOLVE:
        emb_cfg = await _resolve_embedding_cfg(db, tenant_id)
    if emb_cfg and await _has_embedding_column(db):
        vec = await _vector_search(db, tenant_id, query, doc_type, top_k, emb_cfg)
        if vec is not None:
            return vec

    # ---- 关键词回退路径 ----
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


async def retrieve_context(
    db: AsyncSession, tenant_id: str, query: str,
    doc_type: Optional[str] = None, top_k: int = 6, max_tokens: int = 2500,
    emb_cfg=_RESOLVE,
) -> tuple[str, list[dict]]:
    """为 RAG 问答检索片段。返回 (拼接的上下文字符串, 引用来源列表)。

    来源列表元素: {index, document_id, doc_title, score}。
    emb_cfg: 透传给 search_chunks,调用方已解析时可复用,避免重复 resolve。
    """
    chunks = await search_chunks(db, tenant_id, query, doc_type=doc_type, top_k=top_k, emb_cfg=emb_cfg)
    parts: list[str] = []
    sources: list[dict] = []
    total = 0
    for i, c in enumerate(chunks):
        est = _estimate_tokens(c["content"])
        if total + est > max_tokens:
            break
        idx = i + 1
        parts.append(f"[片段{idx}] 《{c['doc_title']}》\n{c['content']}")
        sources.append({
            "index": idx,
            "document_id": c["document_id"],
            "doc_title": c["doc_title"],
            "score": c.get("score"),
        })
        total += est
    return "\n\n".join(parts), sources


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
