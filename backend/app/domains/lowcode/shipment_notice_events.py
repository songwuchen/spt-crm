"""发货通知 → 外部集成（TMS）的 Outbox 领域事件。

事件类型（开放平台 Webhook 可订阅）：
  crm.shipment_notice.submitted  — 离开草稿（提交/进入流程）
  crm.shipment_notice.acted      — 流程中有审批动作
  crm.shipment_notice.completed  — 流程通过结束
  crm.shipment_notice.cancelled  — 驳回 / 撤回

payload 保持精简；下游应再拉 form-instances / wf instances 取全量。
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

TEMPLATE_CODE = "shipment_notice"
EVENT_SUBMITTED = "crm.shipment_notice.submitted"
EVENT_ACTED = "crm.shipment_notice.acted"
EVENT_COMPLETED = "crm.shipment_notice.completed"
EVENT_CANCELLED = "crm.shipment_notice.cancelled"


async def _template_code(db, tenant_id: str, form_instance_id: str | None) -> str | None:
    if not form_instance_id:
        return None
    try:
        from app.domains.lowcode.models import FormInstance, FormTemplate
        fi = await db.get(FormInstance, form_instance_id)
        if not fi or fi.tenant_id != tenant_id:
            return None
        tpl = await db.get(FormTemplate, fi.template_id)
        return tpl.code if tpl else None
    except Exception as e:
        logger.warning("shipment_notice template lookup failed: %s", e)
        return None


async def emit_for_form(
    db, tenant_id: str, event_type: str, form_instance,
    extra: dict | None = None,
) -> None:
    """在调用方事务内写入 outbox（须在 commit 之前）。"""
    try:
        from app.domains.outbox.service import emit_event
        payload = {
            "form_instance_id": getattr(form_instance, "id", None),
            "business_no": getattr(form_instance, "business_no", None),
            "status": getattr(form_instance, "status", None),
            "process_instance_id": getattr(form_instance, "process_instance_id", None),
            "title": getattr(form_instance, "title", None),
        }
        if extra:
            payload.update(extra)
        await emit_event(
            db, tenant_id, event_type,
            aggregate_type="shipment_notice",
            aggregate_id=form_instance.id,
            payload=payload,
        )
    except Exception as e:
        logger.warning("shipment_notice emit %s failed: %s", event_type, e)


async def emit_submitted(db, tenant_id: str, form_instance, template_code: str | None = None) -> None:
    code = template_code
    if code is None:
        code = await _template_code(db, tenant_id, getattr(form_instance, "id", None))
    if code != TEMPLATE_CODE:
        return
    if getattr(form_instance, "status", None) == "draft":
        return
    await emit_for_form(db, tenant_id, EVENT_SUBMITTED, form_instance)


async def emit_from_process(
    db, tenant_id: str, event_type: str, process_inst, extra: dict | None = None,
) -> None:
    """流程实例维度：确认关联表单是发货通知后再发。"""
    fid = getattr(process_inst, "form_instance_id", None)
    code = await _template_code(db, tenant_id, fid)
    if code != TEMPLATE_CODE:
        return
    try:
        from app.domains.lowcode.models import FormInstance
        fi = await db.get(FormInstance, fid) if fid else None
        if not fi:
            return
        payload_extra = {
            "process_instance_id": process_inst.id,
            "process_status": getattr(process_inst, "status", None),
        }
        if extra:
            payload_extra.update(extra)
        await emit_for_form(db, tenant_id, event_type, fi, payload_extra)
    except Exception as e:
        logger.warning("shipment_notice emit_from_process failed: %s", e)
