"""add contracts.serial_no (合同登记流水号)

Revision ID: ct04d5e6f7a8
Revises: lr02b3c4d5e6
Create Date: 2026-08-25
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect, text

revision = "ct04d5e6f7a8"
down_revision = "lr02b3c4d5e6"
branch_labels = None
depends_on = None

TEMPLATE_ID = "00000000-0000-4000-a001-000000000001"
FIELD_ID = "serial_no"


def _format_serial(dt: datetime, seq: int) -> str:
    return f"1.2.3-{dt.strftime('%Y%m%d')}{seq:05d}"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("contracts")}
    indexes = {i["name"] for i in inspector.get_indexes("contracts")}

    if "serial_no" not in cols:
        op.add_column("contracts", sa.Column("serial_no", sa.String(64), nullable=True))
    if "ix_contracts_serial_no" not in indexes:
        op.create_index("ix_contracts_serial_no", "contracts", ["serial_no"])
    if "uq_contracts_tenant_serial_no" not in indexes:
        op.create_index(
            "uq_contracts_tenant_serial_no",
            "contracts",
            ["tenant_id", "serial_no"],
            unique=True,
            postgresql_where=sa.text("serial_no IS NOT NULL"),
        )

    rows = bind.execute(
        text(
            "SELECT id, tenant_id, created_at, card_date FROM contracts "
            "WHERE serial_no IS NULL OR serial_no = '' "
            "ORDER BY tenant_id, created_at ASC, id ASC"
        )
    ).fetchall()
    if not rows:
        return

    year_seq: dict[tuple[str, str], int] = defaultdict(int)
    counter_seed: dict[tuple[str, str], int] = defaultdict(int)

    for rid, tenant_id, created_at, card_date in rows:
        ref = card_date or created_at
        if isinstance(ref, str):
            ref_dt = datetime.fromisoformat(ref.replace("Z", "+00:00"))
        elif isinstance(ref, datetime):
            ref_dt = ref if ref.tzinfo else ref.replace(tzinfo=timezone.utc)
        else:
            ref_dt = datetime.now(timezone.utc)
        year_key = (str(tenant_id), ref_dt.strftime("%Y"))
        year_seq[year_key] += 1
        seq = year_seq[year_key]
        counter_seed[year_key] = max(counter_seed[year_key], seq)
        serial = _format_serial(ref_dt, seq)
        bind.execute(
            text("UPDATE contracts SET serial_no = :sn WHERE id = :id"),
            {"sn": serial, "id": rid},
        )

    for (tenant_id, year), max_seq in counter_seed.items():
        bind.execute(
            text(
                "INSERT INTO lc_serial_counter "
                "(id, tenant_id, template_id, field_id, period_key, current_value, created_at, updated_at) "
                "VALUES (:id, :tenant, :tpl, :fid, :pkey, :val, now(), now()) "
                "ON CONFLICT (tenant_id, template_id, field_id, period_key) "
                "DO UPDATE SET current_value = GREATEST(lc_serial_counter.current_value, EXCLUDED.current_value), "
                "updated_at = now()"
            ),
            {
                "id": __import__("uuid").uuid4().hex,
                "tenant": tenant_id,
                "tpl": TEMPLATE_ID,
                "fid": FIELD_ID,
                "pkey": year,
                "val": max_seq,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    indexes = {i["name"] for i in inspector.get_indexes("contracts")}
    cols = {c["name"] for c in inspector.get_columns("contracts")}
    if "uq_contracts_tenant_serial_no" in indexes:
        op.drop_index("uq_contracts_tenant_serial_no", table_name="contracts")
    if "ix_contracts_serial_no" in indexes:
        op.drop_index("ix_contracts_serial_no", table_name="contracts")
    if "serial_no" in cols:
        op.drop_column("contracts", "serial_no")
