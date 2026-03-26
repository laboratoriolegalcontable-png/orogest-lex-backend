"""Initial migration — all OroGest Lex tables

Revision ID: 001_initial
Revises: None
Create Date: 2026-03-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")  # For fuzzy text search

    # ── Users ──
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("director", "abogado", "asistente", "pasante", name="user_role"),
            nullable=False,
            server_default="pasante",
        ),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), default=False, index=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── Cases ──
    op.create_table(
        "cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("case_number", sa.String(100), nullable=True, index=True),
        sa.Column("internal_id", sa.String(50), unique=True, nullable=False, index=True),
        sa.Column("caption", sa.String(500), nullable=False),
        sa.Column("branch", sa.String(50), nullable=False, index=True),
        sa.Column("status", sa.String(50), default="activa", index=True),
        sa.Column("jurisdiction", sa.String(100), nullable=True),
        sa.Column("court", sa.String(255), nullable=True),
        sa.Column("judge", sa.String(255), nullable=True),
        sa.Column("prosecutor", sa.String(255), nullable=True),
        sa.Column("client_name", sa.String(255), nullable=False),
        sa.Column("client_role", sa.String(50), nullable=True),
        sa.Column("risk_score", sa.Float(), nullable=True),
        sa.Column("risk_details", postgresql.JSONB(), nullable=True),
        sa.Column("filing_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), default=False, index=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_cases_branch_status", "cases", ["branch", "status"])
    op.create_index("ix_cases_next_deadline", "cases", ["next_deadline"])

    # ── Documents ──
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("doc_type", sa.String(50), nullable=False, index=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("file_path", sa.String(1000), nullable=True),
        sa.Column("file_hash", sa.String(64), nullable=True),
        sa.Column("verification_flags", postgresql.JSONB(), nullable=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cases.id"), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("version", sa.Integer(), default=1),
        sa.Column("parent_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), default=False, index=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── Properties ──
    op.create_table(
        "properties",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("province", sa.String(100), nullable=False),
        sa.Column("country", sa.String(10), default="ARG"),
        sa.Column("property_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), default="captado", index=True),
        sa.Column("asking_price_usd", sa.Float(), nullable=True),
        sa.Column("asking_price_ars", sa.Float(), nullable=True),
        sa.Column("folio_real", sa.String(100), nullable=True),
        sa.Column("matricula", sa.String(100), nullable=True),
        sa.Column("dd_checklist", postgresql.JSONB(), nullable=True),
        sa.Column("dd_risk_level", sa.String(10), nullable=True),
        sa.Column("dd_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner_name", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), default=False, index=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── AI Conversations ──
    op.create_table(
        "ai_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cases.id"), nullable=True),
        sa.Column("workflow", sa.String(50), nullable=True),
        sa.Column("messages", postgresql.JSONB(), default=list),
        sa.Column("tokens_used", sa.Integer(), default=0),
        sa.Column("model_used", sa.String(100), default="claude-sonnet-4-20250514"),
        sa.Column("verification_flags_count", sa.Integer(), default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ai_conv_user_created", "ai_conversations", ["user_id", "created_at"])

    # ── Audit Logs ──
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False, index=True),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("resource_id", sa.String(100), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("previous_hash", sa.String(64), nullable=False, server_default="GENESIS"),
        sa.Column("current_hash", sa.String(64), nullable=False, unique=True),
    )
    op.create_index("ix_audit_resource", "audit_logs", ["resource_type", "resource_id"])

    # ── Memory Chunks ──
    op.create_table(
        "memory_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_type", sa.String(50), nullable=False, index=True),
        sa.Column("source_id", sa.String(100), nullable=False, index=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), default=0),
        sa.Column("branch", sa.String(50), nullable=True, index=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tags", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_memory_source", "memory_chunks", ["source_type", "source_id"])

    # ── Full-text search indexes ──
    op.execute(
        "CREATE INDEX ix_cases_caption_trgm ON cases USING gin (caption gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_documents_title_trgm ON documents USING gin (title gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_memory_content_trgm ON memory_chunks USING gin (content gin_trgm_ops)"
    )


def downgrade() -> None:
    op.drop_table("memory_chunks")
    op.drop_table("audit_logs")
    op.drop_table("ai_conversations")
    op.drop_table("properties")
    op.drop_table("documents")
    op.drop_table("cases")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS user_role")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    op.execute("DROP EXTENSION IF EXISTS vector")
