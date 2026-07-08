"""unify stage names: S3 方案报价 / S6 交付验收 (align DB with frontend labels)

统一阶段定义显示名，与前端 stageLabels / 看板 / 仪表盘保持一致：
  S3 方案制定 → 方案报价
  S6 交付执行 → 交付验收
仅更新仍为旧默认名的行，不覆盖租户自定义过的阶段名。
（S5 后端一直为「合同签订」，无需变更；前端 locale 已同步为「合同签订」。）

Revision ID: c3d4e5f6a7b1
Revises: b2c3d4e5f6a9
Create Date: 2026-07-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "c3d4e5f6a7b1"
down_revision = "b2c3d4e5f6a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    if "stage_definitions" not in insp.get_table_names():
        return
    op.execute(sa.text(
        "UPDATE stage_definitions SET name = '方案报价' "
        "WHERE stage_code = 'S3' AND name = '方案制定'"
    ))
    op.execute(sa.text(
        "UPDATE stage_definitions SET name = '交付验收' "
        "WHERE stage_code = 'S6' AND name = '交付执行'"
    ))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    if "stage_definitions" not in insp.get_table_names():
        return
    op.execute(sa.text(
        "UPDATE stage_definitions SET name = '方案制定' "
        "WHERE stage_code = 'S3' AND name = '方案报价'"
    ))
    op.execute(sa.text(
        "UPDATE stage_definitions SET name = '交付执行' "
        "WHERE stage_code = 'S6' AND name = '交付验收'"
    ))
