from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND, BUSINESS_ERROR
from app.domains.approval.models import ApprovalFlow, ApprovalTask
from app.domains.approval.schemas import ApprovalSubmit
from app.domains.audit.service import log_action
from app.domains.notification.service import send_notification


async def list_flows(db: AsyncSession, tenant_id: str, biz_type: str | None = None, biz_id: str | None = None, status: str | None = None):
    q = select(ApprovalFlow).where(ApprovalFlow.tenant_id == tenant_id)
    if biz_type:
        q = q.where(ApprovalFlow.biz_type == biz_type)
    if biz_id:
        q = q.where(ApprovalFlow.biz_id == biz_id)
    if status:
        q = q.where(ApprovalFlow.status == status)
    result = await db.execute(q.order_by(ApprovalFlow.created_at.desc()))
    return result.scalars().all()


async def get_flow(db: AsyncSession, tenant_id: str, flow_id: str) -> ApprovalFlow:
    f = (await db.execute(
        select(ApprovalFlow).where(ApprovalFlow.id == flow_id, ApprovalFlow.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not f:
        raise BusinessException(code=NOT_FOUND, message="审批流不存在")
    return f


async def get_flow_tasks(db: AsyncSession, tenant_id: str, flow_id: str) -> list[ApprovalTask]:
    result = await db.execute(
        select(ApprovalTask).where(
            ApprovalTask.flow_id == flow_id, ApprovalTask.tenant_id == tenant_id
        ).order_by(ApprovalTask.node_order)
    )
    return list(result.scalars().all())


async def _check_margin_redline(db: AsyncSession, tenant_id: str, biz_type: str, biz_id: str) -> dict | None:
    """Check if quote version margin violates redline policies. Returns warning/block info or None."""
    if biz_type != "quote_version":
        return None
    try:
        from app.domains.quote.models import QuoteVersion
        from app.domains.admin.models import MarginPolicy
        ver = (await db.execute(
            select(QuoteVersion).where(QuoteVersion.id == biz_id, QuoteVersion.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not ver or ver.margin_rate is None:
            return None

        # Load active margin policies
        policies = (await db.execute(
            select(MarginPolicy).where(MarginPolicy.tenant_id == tenant_id, MarginPolicy.enabled == True)
        )).scalars().all()

        margin = float(ver.margin_rate)
        for policy in policies:
            redline = float(policy.redline_rate) if policy.redline_rate else 0
            if margin < redline:
                if policy.action == "block":
                    return {
                        "action": "block",
                        "message": f"毛利率 {margin:.1%} 低于红线 {redline:.1%}（策略: {policy.policy_code}），禁止提交审批。",
                        "policy_code": policy.policy_code,
                        "margin_rate": margin,
                        "redline_rate": redline,
                    }
                elif policy.action == "need_approval":
                    return {
                        "action": "warn",
                        "message": f"毛利率 {margin:.1%} 低于红线 {redline:.1%}（策略: {policy.policy_code}），需要额外审批。",
                        "policy_code": policy.policy_code,
                    }
                # "warn" action just logs, doesn't block
    except Exception:
        pass
    return None


async def submit_approval(db: AsyncSession, tenant_id: str, data: ApprovalSubmit, user: dict) -> ApprovalFlow:
    # Margin redline check for quote approvals
    margin_check = await _check_margin_redline(db, tenant_id, data.biz_type, data.biz_id)
    if margin_check and margin_check["action"] == "block":
        raise BusinessException(code=BUSINESS_ERROR, message=margin_check["message"])

    # Check no pending flow for this biz
    existing = (await db.execute(
        select(ApprovalFlow).where(
            ApprovalFlow.tenant_id == tenant_id,
            ApprovalFlow.biz_type == data.biz_type,
            ApprovalFlow.biz_id == data.biz_id,
            ApprovalFlow.status == "pending",
        )
    )).scalar_one_or_none()
    if existing:
        raise BusinessException(code=BUSINESS_ERROR, message="该对象已有进行中的审批流")

    if not data.assignee_ids:
        raise BusinessException(code=BUSINESS_ERROR, message="至少指定一个审批人")

    flow = ApprovalFlow(
        id=generate_uuid(), tenant_id=tenant_id,
        biz_type=data.biz_type, biz_id=data.biz_id,
        title=data.title,
        status="pending",
        current_node=1,
        total_nodes=len(data.assignee_ids),
        submitted_by_id=user["sub"],
        submitted_by_name=user.get("real_name") or user.get("username"),
    )
    db.add(flow)

    names = data.assignee_names or [None] * len(data.assignee_ids)
    for i, aid in enumerate(data.assignee_ids):
        task = ApprovalTask(
            id=generate_uuid(), tenant_id=tenant_id,
            flow_id=flow.id,
            node_order=i + 1,
            assignee_id=aid,
            assignee_name=names[i] if i < len(names) else None,
            status="pending" if i == 0 else "waiting",
        )
        db.add(task)

    await db.commit()
    await db.refresh(flow)

    await log_action(
        db, tenant_id=tenant_id, user_id=user["sub"],
        user_name=user.get("real_name") or user.get("username"),
        action="submit_approval", resource_type=data.biz_type, resource_id=data.biz_id,
        summary=f"提交审批: {data.title or data.biz_type}"
    )

    # Notify first approver
    await send_notification(
        db, tenant_id, data.assignee_ids[0],
        type="approval_pending",
        title=f"您有新的审批待处理: {data.title or data.biz_type}",
        content=f"{flow.submitted_by_name} 提交了审批请求",
        biz_type="approval_flow", biz_id=flow.id,
        sender_name=flow.submitted_by_name,
    )
    return flow


async def decide(db: AsyncSession, tenant_id: str, task_id: str, action: str, comment: str | None, user: dict) -> ApprovalFlow:
    if action not in ("approved", "rejected"):
        raise BusinessException(code=BUSINESS_ERROR, message="action 必须为 approved 或 rejected")

    task = (await db.execute(
        select(ApprovalTask).where(ApprovalTask.id == task_id, ApprovalTask.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not task:
        raise BusinessException(code=NOT_FOUND, message="审批任务不存在")
    if task.status not in ("pending",):
        raise BusinessException(code=BUSINESS_ERROR, message="该审批任务已处理")
    if task.assignee_id != user["sub"]:
        raise BusinessException(code=BUSINESS_ERROR, message="您不是该审批任务的审批人")

    flow = await get_flow(db, tenant_id, task.flow_id)
    if flow.status != "pending":
        raise BusinessException(code=BUSINESS_ERROR, message="审批流已结束")

    # Enforce sequential node order
    if task.node_order != flow.current_node:
        raise BusinessException(code=BUSINESS_ERROR, message="请等待前序审批节点完成")

    now = datetime.now(timezone.utc).isoformat()
    task.status = action
    task.comment = comment
    task.decided_at = now

    if action == "rejected":
        flow.status = "rejected"
    elif action == "approved":
        if task.node_order >= flow.total_nodes:
            flow.status = "approved"
        else:
            flow.current_node = task.node_order + 1
            # Activate next node task: waiting → pending
            tasks = await get_flow_tasks(db, tenant_id, flow.id)
            next_task = next((t for t in tasks if t.node_order == flow.current_node), None)
            if next_task and next_task.status == "waiting":
                next_task.status = "pending"

    await db.commit()
    await db.refresh(flow)

    await log_action(
        db, tenant_id=tenant_id, user_id=user["sub"],
        user_name=user.get("real_name") or user.get("username"),
        action=f"approval_{action}", resource_type=flow.biz_type, resource_id=flow.biz_id,
        summary=f"审批{('通过' if action == 'approved' else '驳回')}: {flow.title or flow.biz_type}"
    )

    user_name = user.get("real_name") or user.get("username")
    # Notify submitter of result
    await send_notification(
        db, tenant_id, flow.submitted_by_id,
        type="approval_decided",
        title=f"审批已{'通过' if action == 'approved' else '驳回'}: {flow.title or flow.biz_type}",
        content=f"审批人 {user_name} {'通过' if action == 'approved' else '驳回'}了审批",
        biz_type="approval_flow", biz_id=flow.id,
        sender_name=user_name,
    )

    # If approved and there's a next node, notify next approver
    if action == "approved" and flow.status == "pending":
        tasks = await get_flow_tasks(db, tenant_id, flow.id)
        next_task = next((t for t in tasks if t.node_order == flow.current_node), None)
        if next_task:
            await send_notification(
                db, tenant_id, next_task.assignee_id,
                type="approval_pending",
                title=f"您有新的审批待处理: {flow.title or flow.biz_type}",
                content=f"第 {flow.current_node}/{flow.total_nodes} 节点",
                biz_type="approval_flow", biz_id=flow.id,
                sender_name=user_name,
            )

    # Approval completion callback — auto-update biz object status
    if flow.status == "approved":
        await _on_approval_completed(db, tenant_id, flow)

    # Auto-activity: record approval decision on the biz object timeline
    try:
        from app.common.auto_activity import record_activity
        # Map biz_type to activity biz_type
        biz_type_map = {
            "quote_version": "project", "contract_version": "project",
            "change_request": "project", "solution": "project",
        }
        activity_biz_type = biz_type_map.get(flow.biz_type, flow.biz_type)
        # For quote/contract versions, need to resolve project_id
        activity_biz_id = flow.biz_id
        if flow.biz_type in ("quote_version", "contract_version"):
            try:
                if flow.biz_type == "quote_version":
                    from app.domains.quote.models import QuoteVersion, Quote
                    ver = (await db.execute(select(QuoteVersion).where(QuoteVersion.id == flow.biz_id))).scalar_one_or_none()
                    if ver:
                        q = (await db.execute(select(Quote).where(Quote.id == ver.quote_id))).scalar_one_or_none()
                        if q:
                            activity_biz_id = q.project_id
                elif flow.biz_type == "contract_version":
                    from app.domains.contract.models import ContractVersion, Contract
                    ver = (await db.execute(select(ContractVersion).where(ContractVersion.id == flow.biz_id))).scalar_one_or_none()
                    if ver:
                        c = (await db.execute(select(Contract).where(Contract.id == ver.contract_id))).scalar_one_or_none()
                        if c:
                            activity_biz_id = c.project_id
            except Exception:
                pass
        elif flow.biz_type == "change_request":
            try:
                from app.domains.change.models import ChangeRequest
                cr = (await db.execute(select(ChangeRequest).where(ChangeRequest.id == flow.biz_id))).scalar_one_or_none()
                if cr:
                    activity_biz_id = cr.project_id
            except Exception:
                pass

        decision_label = "通过" if action == "approved" else "驳回"
        await record_activity(db, tenant_id, activity_biz_type, activity_biz_id, "system",
                              f"审批{decision_label}: {flow.title or flow.biz_type}", comment,
                              user["sub"], user_name)
    except Exception:
        pass

    return flow


async def _on_approval_completed(db: AsyncSession, tenant_id: str, flow: ApprovalFlow):
    """Update biz object status when approval is fully approved."""
    try:
        if flow.biz_type == "quote_version":
            from app.domains.quote.models import QuoteVersion
            ver = (await db.execute(
                select(QuoteVersion).where(QuoteVersion.id == flow.biz_id, QuoteVersion.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if ver:
                ver.status = "approved"
                await db.commit()
        elif flow.biz_type == "contract_version":
            from app.domains.contract.models import ContractVersion
            ver = (await db.execute(
                select(ContractVersion).where(ContractVersion.id == flow.biz_id, ContractVersion.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if ver:
                ver.status = "approved"
                await db.commit()
        elif flow.biz_type == "change_request":
            from app.domains.change.models import ChangeRequest
            cr = (await db.execute(
                select(ChangeRequest).where(ChangeRequest.id == flow.biz_id, ChangeRequest.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if cr:
                cr.status = "approved"
                await db.commit()
    except Exception:
        pass


async def list_my_pending(db: AsyncSession, tenant_id: str, user_id: str):
    """List pending approval tasks assigned to a user."""
    result = await db.execute(
        select(ApprovalTask, ApprovalFlow).join(
            ApprovalFlow, ApprovalTask.flow_id == ApprovalFlow.id
        ).where(
            ApprovalTask.tenant_id == tenant_id,
            ApprovalTask.assignee_id == user_id,
            ApprovalTask.status == "pending",
            ApprovalFlow.status == "pending",
        ).order_by(ApprovalTask.created_at.desc())
    )
    return result.all()
