"""
OroGest Lex — Memory Service (Fase 9)
Semantic memory using pgvector for RAG (Retrieval Augmented Generation).

How it works:
1. Documents/cases/conversations get embedded via Claude API
2. Embeddings stored in PostgreSQL with pgvector
3. When AI queries come in, relevant context is retrieved by similarity
4. Retrieved context is injected into the Claude system prompt

This is NOT magic memory — it's vector similarity search over stored text chunks.
"""

import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import Column, DateTime, Float, Index, Integer, String, Text, select, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import get_settings
from app.db.base import Base, UUIDPrimaryKeyMixin, TimestampMixin

settings = get_settings()

# pgvector dimension — Anthropic embeddings are not yet public,
# so we use a lightweight approach: chunk text + store for BM25-like retrieval,
# with optional embedding upgrade path.
EMBEDDING_DIM = 1536  # placeholder for future OpenAI/Cohere embeddings


class MemoryChunk(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A chunk of text stored for retrieval.
    Each chunk belongs to a source (case, document, conversation, property).
    """
    __tablename__ = "memory_chunks"

    # Source reference
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # "case" | "document" | "conversation" | "property" | "note"
    source_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)

    # Metadata for filtering
    branch: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    # penal / inmobiliario / etc.
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    # comma-separated: "nulidad,casación,cadena_custodia"

    # Future: embedding vector column
    # embedding = mapped_column(Vector(EMBEDDING_DIM), nullable=True)

    __table_args__ = (
        Index("ix_memory_source", "source_type", "source_id"),
        Index("ix_memory_branch", "branch"),
    )


# ═══════════════════════════════════════════
# TEXT CHUNKING
# ═══════════════════════════════════════════
def chunk_text(text: str, max_chars: int = 1500, overlap: int = 200) -> list[str]:
    """
    Split text into overlapping chunks for storage.
    Uses paragraph boundaries when possible.
    """
    if len(text) <= max_chars:
        return [text]

    chunks = []
    paragraphs = text.split("\n\n")
    current_chunk = ""

    for para in paragraphs:
        if len(current_chunk) + len(para) + 2 <= max_chars:
            current_chunk += ("\n\n" + para if current_chunk else para)
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            # If paragraph itself is too long, split by sentences
            if len(para) > max_chars:
                sentences = para.replace(". ", ".\n").split("\n")
                current_chunk = ""
                for sent in sentences:
                    if len(current_chunk) + len(sent) + 1 <= max_chars:
                        current_chunk += (" " + sent if current_chunk else sent)
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = sent
            else:
                current_chunk = para

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    # Add overlap between chunks
    if overlap > 0 and len(chunks) > 1:
        overlapped = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_tail = chunks[i - 1][-overlap:] if len(chunks[i - 1]) > overlap else chunks[i - 1]
            overlapped.append(prev_tail + " " + chunks[i])
        chunks = overlapped

    return chunks


# ═══════════════════════════════════════════
# MEMORY OPERATIONS
# ═══════════════════════════════════════════
async def store_memory(
    db: AsyncSession,
    content: str,
    source_type: str,
    source_id: str,
    branch: str | None = None,
    user_id: uuid.UUID | None = None,
    tags: str | None = None,
) -> list[MemoryChunk]:
    """Store text as chunked memory entries."""
    chunks = chunk_text(content)
    memory_chunks = []

    for i, chunk_text_content in enumerate(chunks):
        chunk = MemoryChunk(
            source_type=source_type,
            source_id=source_id,
            content=chunk_text_content,
            chunk_index=i,
            branch=branch,
            user_id=user_id,
            tags=tags,
        )
        db.add(chunk)
        memory_chunks.append(chunk)

    await db.flush()
    return memory_chunks


async def search_memory(
    db: AsyncSession,
    query: str,
    branch: str | None = None,
    source_type: str | None = None,
    limit: int = 5,
) -> list[MemoryChunk]:
    """
    Search memory chunks by keyword matching.
    This is BM25-style full-text search — NOT vector similarity yet.
    For vector similarity, pgvector extension + embeddings needed.
    """
    # PostgreSQL full-text search
    stmt = select(MemoryChunk).where(
        MemoryChunk.content.ilike(f"%{query}%")
    )

    if branch:
        stmt = stmt.where(MemoryChunk.branch == branch)
    if source_type:
        stmt = stmt.where(MemoryChunk.source_type == source_type)

    stmt = stmt.order_by(MemoryChunk.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def delete_memory_by_source(
    db: AsyncSession,
    source_type: str,
    source_id: str,
) -> int:
    """Delete all memory chunks for a given source."""
    result = await db.execute(
        select(MemoryChunk).where(
            MemoryChunk.source_type == source_type,
            MemoryChunk.source_id == source_id,
        )
    )
    chunks = result.scalars().all()
    count = len(chunks)
    for chunk in chunks:
        await db.delete(chunk)
    await db.flush()
    return count


async def get_context_for_query(
    db: AsyncSession,
    query: str,
    case_id: str | None = None,
    branch: str | None = None,
    max_context_chars: int = 4000,
) -> str:
    """
    Build a context string from relevant memory chunks.
    This is injected into the Claude system prompt for RAG.
    """
    chunks = await search_memory(db, query, branch=branch, limit=8)

    # If we have a case_id, also fetch case-specific chunks
    if case_id:
        case_chunks = await search_memory(
            db, query, source_type="case", limit=3
        )
        # Merge, dedup by id
        seen_ids = {c.id for c in chunks}
        for cc in case_chunks:
            if cc.id not in seen_ids:
                chunks.append(cc)

    if not chunks:
        return ""

    # Build context string, respecting max chars
    context_parts = []
    total_chars = 0
    for chunk in chunks:
        if total_chars + len(chunk.content) > max_context_chars:
            break
        context_parts.append(
            f"[{chunk.source_type.upper()} — {chunk.branch or 'general'}]\n{chunk.content}"
        )
        total_chars += len(chunk.content)

    return "\n\n---\n\n".join(context_parts)
