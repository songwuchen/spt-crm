import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND
from app.domains.change.models import ChangeRequest
from app.domains.change.schemas import ChangeRequestCreate, ChangeRequestUpdate
from app.domains.audit.service import log_action
from app.common.code_generator import generate_code

logger = logging.getLogger("spt_crm.change")



async def list_by_project(db: AsyncSession, tenant_id: str, project_id: str):
    result = await db.execute(
        select(ChangeRequest).where(ChangeRequest.tenant_id == tenant_id, ChangeRequest.project_id == project_id)
        .order_by(ChangeRequest.created_at.desc())
    )
    return result.scalars().all()


async def get(db: AsyncSession, tenant_id: str, cr_id: str) -> ChangeRequest:
    cr = (await db.execute(
        select(ChangeRequest).where(ChangeRequest.id == cr_id, ChangeRequest.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not cr:
        raise BusinessException(code=NOT_FOUND, message="变更单不存在")
    return cr


async def create(db: AsyncSession, tenant_id: str, project_id: str, data: ChangeRequestCreate, user: dict) -> ChangeRequest:
    cr = ChangeRequest(
        id=generate_uuid(), tenant_id=tenant_id, project_id=project_id,
        change_no=await generate_code(db, tenant_id, "change"),
        created_by_id=user["sub"], created_by_name=user.get("real_name") or user.get("username"),
        **data.model_dump(exclude_unset=True),
    )
    db.add(cr)
    await db.commit()
    await db.refresh(cr)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="change_request", resource_id=cr.id,
                     summary=f"创建变更单: {cr.change_no}")

    # Auto-trigger approval：优先新表单引擎工作流（灰度按 biz_type 切换），未绑定则回退旧引擎
    try:
        title = f"变更审批: {cr.change_no}"
        from app.domains.lowcode.workflow_service import start_for_biz
        pinst = await start_for_biz(db, tenant_id, "change_request", cr.id, user, title=title)
        if pinst is None:
            from app.domains.approval.service import auto_trigger_approval
            await auto_trigger_approval(db, tenant_id, "change_request", cr.id, title, user)
    except Exception as e:
        logger.warning("Auto-trigger approval for change request failed: %s", e)

    return cr


VALID_STATUS_TRANSITIONS = {
    "draft": {"reviewing"},
    "reviewing": {"approved", "rejected"},
    "approved": {"implemented"},
    "rejected": {"draft"},
    "implemented": set(),
}


async def update(db: AsyncSession, tenant_id: str, cr_id: str, data: ChangeRequestUpdate, user: dict) -> ChangeRequest:
    cr = await get(db, tenant_id, cr_id)
    update_data = data.model_dump(exclude_unset=True)
    # Validate status transition
    new_status = update_data.get("status")
    if new_status and new_status != cr.status:
        allowed = VALID_STATUS_TRANSITIONS.get(cr.status, set())
        if new_status not in allowed:
            raise BusinessException(
                code=42200,
                message=f"变更单状态不能从 {cr.status} 变为 {new_status}，允许: {', '.join(allowed) if allowed else '无'}",
            )
    for field, val in update_data.items():
        setattr(cr, field, val)
    await db.commit()
    await db.refresh(cr)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="update", resource_type="change_request", resource_id=cr_id,
                     summary=f"更新变更单: {cr.change_no} → {cr.status}")

    # Auto-activity: record status change on project timeline
    if new_status and new_status != cr.status:
        try:
            from app.common.auto_activity import record_activity
            status_labels = {"draft": "草稿", "reviewing": "评审中", "approved": "已批准", "rejected": "已驳回", "implemented": "已实施"}
            await record_activity(db, tenant_id, "project", cr.project_id, "system",
                                  f"变更单 {cr.change_no} 状态: {status_labels.get(cr.status, cr.status)}", None,
                                  user["sub"], user.get("real_name") or user.get("username"))
        except Exception as e:
            logger.warning("Auto-activity record for change status update failed: %s", e)

    return cr


async def estimate_impact(db: AsyncSession, tenant_id: str, cr_id: str, user: dict) -> dict:
    """Estimate the impact of a change request based on scope: affected milestones + budget deviation."""
    cr = await get(db, tenant_id, cr_id)

    # Gather delivery milestones for this project
    from app.domains.delivery.models import DeliveryMilestone
    ms_result = await db.execute(
        select(DeliveryMilestone).where(
            DeliveryMilestone.tenant_id == tenant_id,
            DeliveryMilestone.project_id == cr.project_id,
        ).order_by(DeliveryMilestone.sort_order)
    )
    milestones = ms_result.scalars().all()

    # Determine affected milestones based on change_type
    affected_milestones = []
    delivery_types = {"delivery", "requirement", "scope"}
    if cr.change_type in delivery_types:
        # All not-yet-completed milestones are potentially affected
        affected_milestones = [
            {"id": m.id, "code": m.milestone_code, "name": m.name, "status": m.status,
             "plan_date": str(m.plan_date) if m.plan_date else None}
            for m in milestones if m.status not in ("done", "completed")
        ]
    else:
        # Quote / contract changes: only affect milestones after current doing milestone
        found_doing = False
        for m in milestones:
            if m.status in ("doing", "in_progress"):
                found_doing = True
                continue
            if found_doing and m.status not in ("done", "completed"):
                affected_milestones.append({
                    "id": m.id, "code": m.milestone_code, "name": m.name,
                    "status": m.status, "plan_date": str(m.plan_date) if m.plan_date else None,
                })

    # Calculate budget deviation from project amount + quote totals
    from app.domains.project.models import OpportunityProject
    proj = (await db.execute(
        select(OpportunityProject).where(
            OpportunityProject.id == cr.project_id,
            OpportunityProject.tenant_id == tenant_id,
        )
    )).scalar_one_or_none()

    budget_info = {}
    if proj:
        budget_info["project_amount_expect"] = float(proj.amount_expect) if proj.amount_expect else None
        budget_info["project_name"] = proj.name

    # Build impact assessment
    impact = {
        "change_type": cr.change_type,
        "affected_milestones": affected_milestones,
        "affected_milestone_count": len(affected_milestones),
        "total_milestone_count": len(milestones),
        "budget": budget_info,
        "risk_summary": [],
    }

    if len(affected_milestones) > 3:
        impact["risk_summary"].append("影响超过3个里程碑，建议重新评估项目计划")
    if cr.change_type in ("quote", "contract"):
        impact["risk_summary"].append("涉及报价/合同变更，可能影响利润率")
    delayed_count = sum(1 for m in milestones if m.status == "delayed")
    if delayed_count > 0:
        impact["risk_summary"].append(f"当前已有 {delayed_count} 个延迟里程碑，变更可能加剧延期风险")

    # Store the impact back to the change request
    cr.impact_json = impact
    await db.commit()
    await db.refresh(cr)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"],
                     user_name=user.get("real_name") or user.get("username"),
                     action="update", resource_type="change_request", resource_id=cr_id,
                     summary=f"评估变更影响: {cr.change_no}, 影响 {len(affected_milestones)} 个里程碑")

    return impact


async def delete(db: AsyncSession, tenant_id: str, cr_id: str, user: dict):
    cr = await get(db, tenant_id, cr_id)
    await db.delete(cr)
    await db.commit()
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="delete", resource_type="change_request", resource_id=cr_id,
                     summary=f"删除变更单: {cr.change_no}")
