"""add workflow engine + org extension tables (Phase 3)

新增: 组织扩展 posts/user_posts/user_agents;可视化审批引擎 wf_process_definition(+version)
/wf_process_instance/wf_node_instance/wf_task_instance/wf_task_action_log/wf_process_comment/wf_process_cc。
纯新增表,不改动既有业务表(含旧 approval_* 引擎),可安全前滚/回滚。

Revision ID: lc002b2c3d4e
Revises: lc001a1b2c3d
Create Date: 2026-07-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "lc002b2c3d4e"
down_revision = "lc001a1b2c3d"
branch_labels = None
depends_on = None


def _ts_cols():
    return [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    ]


def upgrade():
    # ---- 组织扩展 ----
    op.create_table(
        "posts", *_ts_cols(),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
    )
    op.create_index("uq_posts_tenant_code", "posts", ["tenant_id", "code"], unique=True)

    op.create_table(
        "user_posts", *_ts_cols(),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("post_id", sa.String(36), nullable=False),
    )
    op.create_index("ix_user_posts_user", "user_posts", ["user_id"])
    op.create_index("ix_user_posts_post", "user_posts", ["post_id"])

    op.create_table(
        "user_agents", *_ts_cols(),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("agent_id", sa.String(36), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("note", sa.String(500), nullable=True),
    )
    op.create_index("ix_user_agents_user", "user_agents", ["user_id"])
    op.create_index("ix_user_agents_agent", "user_agents", ["agent_id"])

    # ---- 流程定义 ----
    op.create_table(
        "wf_process_definition", *_ts_cols(),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("icon", sa.String(128), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("form_template_id", sa.String(36), nullable=True),
        sa.Column("biz_type", sa.String(64), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_by", sa.String(36), nullable=True),
    )
    op.create_index("uq_wf_process_definition_tenant_code", "wf_process_definition", ["tenant_id", "code"], unique=True)

    op.create_table(
        "wf_process_definition_version", *_ts_cols(),
        sa.Column("process_definition_id", sa.String(36), nullable=False, index=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("node_definitions", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("route_definitions", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("approver_rules", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("form_template_version_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by", sa.String(36), nullable=True),
    )

    # ---- 流程运行 ----
    op.create_table(
        "wf_process_instance", *_ts_cols(),
        sa.Column("process_definition_id", sa.String(36), nullable=False),
        sa.Column("process_version_id", sa.String(36), nullable=False),
        sa.Column("form_instance_id", sa.String(36), nullable=True),
        sa.Column("biz_type", sa.String(64), nullable=True),
        sa.Column("biz_id", sa.String(36), nullable=True),
        sa.Column("business_no", sa.String(64), nullable=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("initiator_id", sa.String(36), nullable=False),
        sa.Column("initiator_dept_id", sa.String(36), nullable=True),
        sa.Column("parent_process_id", sa.String(36), nullable=True),
        sa.Column("parent_node_instance_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sla_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sla_status", sa.String(20), nullable=True),
        sa.Column("is_test", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("nominated_approvers", postgresql.JSONB(), nullable=True),
        sa.Column("pending_joins", postgresql.JSONB(), nullable=True),
    )
    op.create_index("ix_wf_process_instance_initiator", "wf_process_instance", ["initiator_id", "status"])
    op.create_index("ix_wf_process_instance_status", "wf_process_instance", ["status"])
    op.create_index("ix_wf_process_instance_biz", "wf_process_instance", ["biz_type", "biz_id"])

    op.create_table(
        "wf_node_instance", *_ts_cols(),
        sa.Column("process_instance_id", sa.String(36), nullable=False, index=True),
        sa.Column("node_def_id", sa.String(64), nullable=False),
        sa.Column("node_type", sa.String(32), nullable=False),
        sa.Column("node_name", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "wf_task_instance", *_ts_cols(),
        sa.Column("process_instance_id", sa.String(36), nullable=False),
        sa.Column("node_instance_id", sa.String(36), nullable=False),
        sa.Column("assignee_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("opinion", sa.Text(), nullable=True),
        sa.Column("action_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("task_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_wf_task_assignee_status", "wf_task_instance", ["assignee_id", "status"])
    op.create_index("ix_wf_task_process_instance", "wf_task_instance", ["process_instance_id"])
    op.create_index("ix_wf_task_node_instance", "wf_task_instance", ["node_instance_id"])

    op.create_table(
        "wf_task_action_log", *_ts_cols(),
        sa.Column("process_instance_id", sa.String(36), nullable=False, index=True),
        sa.Column("node_instance_id", sa.String(36), nullable=True),
        sa.Column("task_instance_id", sa.String(36), nullable=True),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("actor_name", sa.String(128), nullable=True),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("opinion", sa.Text(), nullable=True),
        sa.Column("extra", postgresql.JSONB(), nullable=True),
    )

    op.create_table(
        "wf_process_comment", *_ts_cols(),
        sa.Column("process_instance_id", sa.String(36), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("user_name", sa.String(128), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
    )

    op.create_table(
        "wf_process_cc", *_ts_cols(),
        sa.Column("process_instance_id", sa.String(36), nullable=False, index=True),
        sa.Column("node_instance_id", sa.String(36), nullable=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_wf_process_cc_user", "wf_process_cc", ["user_id", "is_read"])


def downgrade():
    for t in [
        "wf_process_cc", "wf_process_comment", "wf_task_action_log", "wf_task_instance",
        "wf_node_instance", "wf_process_instance", "wf_process_definition_version",
        "wf_process_definition", "user_agents", "user_posts", "posts",
    ]:
        op.drop_table(t)
