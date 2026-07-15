"""扩展平台 — 表单引擎数据模型。

移植自 spt-lowcode app/models/form/*,适配 CRM 约定:
- 主键/外键/租户列使用 String(36)(而非原生 UUID),与 TenantScopedBase 一致;
- created_by / is_deleted 在需要处显式声明(CRM base 未内置);
- tenant_id 由 TenantScopedBase 提供并强制非空,应用层过滤保证隔离。

设计要点(与原平台一致):
- 表单模板版本化: FormTemplateVersion 冻结 field/layout/rule 三份 JSONB;
- 提交数据存 FormInstance.form_data(JSONB),并快照 field_definitions,
  使历史记录不依赖可改/可删的模板版本仍能正确渲染;
- 明细子表默认内联在 form_data 的 JSON 数组中;FormInstanceDetailRow 为可选去规范化侧表。
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Index, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class FormTemplate(TenantScopedBase):
    """表单模板(header)。"""
    __tablename__ = "lc_form_template"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 系统内置模板(如"客户""商机"迁移到表单引擎后):受保护,部分字段硬绑定,不可删除。
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default=text("false"))
    # 绑定的 CRM 业务实体(如 customer/project),NULL 表示纯自定义表单。
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 字段回收站: 保存表单时被删除的顶层字段进入此列表,可恢复或彻底删除。
    deleted_fields: Mapped[list] = mapped_column(JSONB, default=list, nullable=False, server_default="[]")
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default=text("false"))
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    __table_args__ = (
        Index("uq_lc_form_template_tenant_code", "tenant_id", "code", unique=True),
    )


class FormTemplateVersion(TenantScopedBase):
    """表单模板版本 — 冻结的 schema(字段/布局/规则三份 JSONB)。"""
    __tablename__ = "lc_form_template_version"

    template_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    field_definitions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    layout_definition: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    rule_definitions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class FormInstance(TenantScopedBase):
    """表单实例 — 一条提交记录。"""
    __tablename__ = "lc_form_instance"

    template_id: Mapped[str] = mapped_column(String(36), nullable=False)
    template_version_id: Mapped[str] = mapped_column(String(36), nullable=False)
    process_instance_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    business_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    initiator_id: Mapped[str] = mapped_column(String(36), nullable=False)
    initiator_dept_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    app_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    form_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    # 提交时保存的字段定义快照,使历史记录不依赖可删/可改的模板版本。为空则回退按版本解析。
    field_definitions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    share_token: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default=text("false"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    __table_args__ = (
        Index("ix_lc_form_instance_template_id", "template_id"),
        Index("ix_lc_form_instance_initiator", "initiator_id", "status"),
        Index("ix_lc_form_instance_business_no", "business_no"),
        Index("ix_lc_form_instance_status", "status"),
        # 数据列表主查询: WHERE tenant_id=? AND template_id=? AND is_deleted=false ORDER BY created_at DESC
        Index("ix_lc_form_instance_tpl_created", "tenant_id", "template_id", "created_at"),
        # 回收站到期扫描: WHERE is_deleted=true AND deleted_at<cutoff
        Index("ix_lc_form_instance_deleted_at", "deleted_at", postgresql_where=text("is_deleted")),
    )


class FormInstanceDetailRow(TenantScopedBase):
    """明细子表去规范化侧表(可选,主存储仍为 form_data JSONB)。"""
    __tablename__ = "lc_form_instance_detail_row"

    form_instance_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    field_key: Mapped[str] = mapped_column(String(64), nullable=False)
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    row_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class SerialCounter(TenantScopedBase):
    """流水号计数器(auto_number 字段用)。"""
    __tablename__ = "lc_serial_counter"

    template_id: Mapped[str] = mapped_column(String(36), nullable=False)
    field_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # 计数周期 key(如 "2026" / "2026-07" / "" 表示不按周期重置),配合前缀规则生成唯一序号。
    period_key: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    current_value: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        Index("uq_lc_serial_counter", "tenant_id", "template_id", "field_id", "period_key", unique=True),
    )
