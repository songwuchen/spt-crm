"""低代码表单数据日志（通用：创建 / 编辑 / 审批写回）。"""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.audit_diff import enrich_changes_with_labels, labels_from_field_defs
from app.common.audit_display import enrich_form_changes_for_display, filter_create_log_changes
from app.domains.audit.service import log_action


async def log_form_instance_changes(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    user_name: str | None,
    form_instance_id: str,
    field_defs: list[dict[str, Any]] | None,
    changes: dict[str, dict[str, Any]],
    action: str,
    summary: str,
    create_mode: bool = False,
) -> None:
    """写入 form_instance 数据日志（字段 diff + 可读展示值）。"""
    if not changes:
        return
    if create_mode:
        changes = filter_create_log_changes(changes)
    if not changes:
        return
    labeled = enrich_changes_with_labels(changes, labels_from_field_defs(field_defs))
    displayed = await enrich_form_changes_for_display(db, tenant_id, labeled, field_defs)
    await log_action(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        user_name=user_name,
        action=action,
        resource_type="form_instance",
        resource_id=form_instance_id,
        summary=summary,
        detail={"changes": displayed},
    )
