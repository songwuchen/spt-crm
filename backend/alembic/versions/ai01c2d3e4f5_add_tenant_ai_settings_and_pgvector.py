"""add tenant AI model settings + (env-adaptive) pgvector embedding column

Adds:
- tenant_ai_settings: per-tenant 对话模型/向量嵌入模型接入配置(密钥AES加密)
- knowledge_chunks.embedding: vector(1024) 列 + HNSW 余弦索引 —— 仅在数据库
  支持 pgvector 扩展时创建。CI / 普通 postgres 镜像不带 pgvector,此时跳过
  向量列,只建设置表,迁移照常通过(运行时检索自动回退关键词匹配)。

生产切换到 pgvector 镜像后,若本迁移当时已在无 pgvector 环境执行过(未建列),
可幂等重跑同样的 DDL 补齐,见 docs 交付说明。

Revision ID: ai01c2d3e4f5
Revises: lc004d4e5f6a
Create Date: 2026-07-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "ai01c2d3e4f5"
down_revision = "lc004d4e5f6a"
branch_labels = None
depends_on = None


def _pgvector_available(bind) -> bool:
    """True 当且仅当数据库镜像自带 pgvector 扩展(可被 CREATE EXTENSION 安装)。

    只做只读查询 pg_available_extensions,不会因缺扩展而报错、也不会污染事务。
    """
    try:
        row = bind.execute(
            sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")
        ).scalar()
        return bool(row)
    except Exception:
        return False


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)

    if "tenant_ai_settings" not in insp.get_table_names():
        op.create_table(
            "tenant_ai_settings",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("chat_provider", sa.String(32), nullable=True, server_default="mock"),
            sa.Column("chat_config_json", sa.JSON(), nullable=True),
            sa.Column("embedding_provider", sa.String(32), nullable=True, server_default="none"),
            sa.Column("embedding_config_json", sa.JSON(), nullable=True),
            sa.Column("enabled", sa.Boolean(), nullable=True, server_default=sa.false()),
        )

    # ---- 向量列(仅当数据库支持 pgvector) ----
    if _pgvector_available(bind):
        bind.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
        cols = {c["name"] for c in insp.get_columns("knowledge_chunks")}
        if "embedding" not in cols:
            bind.execute(sa.text(
                "ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS embedding vector(1024)"
            ))
        bind.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_embedding "
            "ON knowledge_chunks USING hnsw (embedding vector_cosine_ops)"
        ))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)

    try:
        cols = {c["name"] for c in insp.get_columns("knowledge_chunks")}
        if "embedding" in cols:
            bind.execute(sa.text("DROP INDEX IF EXISTS ix_knowledge_chunks_embedding"))
            bind.execute(sa.text("ALTER TABLE knowledge_chunks DROP COLUMN IF EXISTS embedding"))
    except Exception:
        pass

    if "tenant_ai_settings" in insp.get_table_names():
        op.drop_table("tenant_ai_settings")
