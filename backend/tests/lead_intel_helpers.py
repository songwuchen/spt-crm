"""线索情报审批测试辅助（指定人员规则与 CI 测试库对齐）。"""

from sqlalchemy import select

from app.database import generate_uuid

DEMO_TENANT = "00000000-0000-0000-0000-000000000001"


async def pending_intel_task(db, lead_id: str, reviewer_id: str | None = None):
    from app.domains.lowcode.workflow_models import WfProcessInstance, WfTaskInstance

    inst = (await db.execute(select(WfProcessInstance).where(
        WfProcessInstance.biz_type == "lead", WfProcessInstance.biz_id == lead_id,
    ))).scalar_one()
    q = select(WfTaskInstance).where(
        WfTaskInstance.process_instance_id == inst.id,
        WfTaskInstance.status == "pending",
    )
    if reviewer_id:
        q = q.where(WfTaskInstance.assignee_id == reviewer_id)
    task = (await db.execute(q)).scalars().first()
    assert task is not None, f"no pending intel task for lead={lead_id} assignee={reviewer_id}"
    return task


async def approve_lead_intel_include(db, lead_id: str, reviewer_id: str) -> None:
    from app.domains.lead import service as lead_svc

    task = await pending_intel_task(db, lead_id, reviewer_id)
    await lead_svc.intel_review_lead(
        db, DEMO_TENANT, lead_id,
        {"sub": reviewer_id, "real_name": "测试内勤"},
        decision="include", task_id=task.id, customer_newness="new",
    )
