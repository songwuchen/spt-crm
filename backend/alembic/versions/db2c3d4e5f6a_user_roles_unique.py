"""dedup user_roles and add unique (tenant_id, user_id, role_id)

Ensures a user cannot hold the same role twice. Required so the dept->role
auto-assignment can use INSERT ... ON CONFLICT DO NOTHING (idempotent, race-safe)
and so concurrent role assignment never creates duplicate rows.

Revision ID: db2c3d4e5f6a
Revises: da1b2c3d4e5f
Create Date: 2026-07-18

"""
from alembic import op

revision = "db2c3d4e5f6a"
down_revision = "da1b2c3d4e5f"
branch_labels = None
depends_on = None


def upgrade():
    # 1) 先清理历史重复行：每个 (tenant_id, user_id, role_id) 只保留 id 最小的一行。
    op.execute(
        """
        DELETE FROM user_roles a
        USING user_roles b
        WHERE a.tenant_id = b.tenant_id
          AND a.user_id   = b.user_id
          AND a.role_id   = b.role_id
          AND a.id > b.id
        """
    )
    # 2) 建唯一索引兜底。
    op.create_index(
        "uq_user_role",
        "user_roles",
        ["tenant_id", "user_id", "role_id"],
        unique=True,
    )


def downgrade():
    op.drop_index("uq_user_role", table_name="user_roles")
