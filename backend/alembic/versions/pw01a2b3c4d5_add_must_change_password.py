"""add must_change_password to users

钉钉组织同步代建的账号，密码是全租户共享的默认值（Changeme@123），
用户本人从未设过、也无从知晓。该标记让这类账号首次「修改密码」免填原密码，
自助改密成功后置回 false。

Revision ID: pw01a2b3c4d5
Revises: wf01n2o3p4q5
Create Date: 2026-07-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "pw01a2b3c4d5"
down_revision = "wf01n2o3p4q5"
branch_labels = None
depends_on = None


def _has_column(insp, table: str, col: str) -> bool:
    return table in insp.get_table_names() and col in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    if not _has_column(insp, "users", "must_change_password"):
        op.add_column(
            "users",
            sa.Column(
                "must_change_password",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    if _has_column(insp, "users", "must_change_password"):
        op.drop_column("users", "must_change_password")
