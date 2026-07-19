"""drop legacy field_rules from tenant security policy

旧的 field_rules（tenant_profiles.security_policy_json 里的 {resource, field, roles, action}
数组）没有任何后端执行点、前端也无人消费，配置了等于没配。字段级可见/脱敏/可编辑已统一
由扩展平台字段权限承担（lowcode/field_permission.py，列表/详情/导出均由后端强制）。

这里只摘掉那个 JSON 键，同列的 pool_rules / report_schedules 原样保留。

Revision ID: fp01a2b3c4d5
Revises: db2c3d4e5f6a
"""
from alembic import op

revision = "fp01a2b3c4d5"
down_revision = "db2c3d4e5f6a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # security_policy_json 是 sa.JSON（PG json），删键要先转 jsonb 再转回来
    op.execute(
        """
        UPDATE tenant_profiles
        SET security_policy_json = ((security_policy_json::jsonb) - 'field_rules')::json
        WHERE security_policy_json IS NOT NULL
          AND (security_policy_json::jsonb) ? 'field_rules'
        """
    )


def downgrade() -> None:
    # 旧规则本就不生效，无需也无法恢复其内容
    pass
