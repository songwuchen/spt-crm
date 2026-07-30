"""Drop unused jdy_contract_sync_state (CRM no longer polls 简道云)."""
from alembic import op
import sqlalchemy as sa

revision = "ct03c4d5e6f7"
down_revision = "ct02b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = sa.inspect(bind).get_table_names()
    if "jdy_contract_sync_state" in tables:
        op.drop_table("jdy_contract_sync_state")


def downgrade() -> None:
    bind = op.get_bind()
    tables = sa.inspect(bind).get_table_names()
    if "jdy_contract_sync_state" not in tables:
        op.create_table(
            "jdy_contract_sync_state",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
            sa.Column("source_key", sa.String(64), nullable=False),
            sa.Column("cursor", sa.Text),
            sa.Column("last_success_at", sa.DateTime(timezone=True)),
            sa.Column("last_error", sa.Text),
            sa.Column("created_at", sa.DateTime(timezone=True)),
            sa.Column("updated_at", sa.DateTime(timezone=True)),
            sa.UniqueConstraint("tenant_id", "source_key", name="uq_jdy_contract_sync_tenant_source"),
        )
