import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND, BUSINESS_ERROR
from app.domains.approval.models import ApprovalFlow, ApprovalTask
from app.domains.approval.schemas import ApprovalSubmit
from app.domains.audit.service import log_action
from app.domains.notification.service import send_notification

logger = logging.getLogger("spt_crm.approval")


async def list_flows(db: AsyncSession, tenant_id: str, biz_type: str | None = None, biz_id: str | None = None, status: str | None = None, page: int = 1, page_size: int = 50):
    q = select(ApprovalFlow).where(ApprovalFlow.tenant_id == tenant_id)
    if biz_type:
        q = q.where(ApprovalFlow.biz_type == biz_type)
    if biz_id:
        q = q.where(ApprovalFlow.biz_id == biz_id)
    if status:
        q = q.where(ApprovalFlow.status == status)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    items = (await db.execute(
        q.order_by(ApprovalFlow.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return items, total


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
    except Exception as e:
        logger.warning("Margin redline policy check failed: %s", e)
    return None


def _safe_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


async def _build_policy_context(db: AsyncSession, tenant_id: str, biz_type: str, biz_id: str) -> dict:
    """Build the field context used to match approval policy conditions.

    Each business type exposes the fields that make sense for it (see the
    frontend FIELD_CATALOG). Keep the field names here in sync with that catalog
    so a condition configured in the UI can actually be evaluated.
    """
    context: dict = {}
    try:
        if biz_type == "quote_version":
            from app.domains.quote.models import QuoteVersion
            ver = (await db.execute(
                select(QuoteVersion).where(QuoteVersion.id == biz_id, QuoteVersion.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if ver:
                context["amount"] = _safe_float(ver.price_total)
                context["margin_rate"] = _safe_float(ver.margin_rate)
                context["discount_total"] = _safe_float(ver.discount_total)
        elif biz_type == "contract_version":
            from app.domains.contract.models import ContractVersion, Contract
            ver = (await db.execute(
                select(ContractVersion).where(ContractVersion.id == biz_id, ContractVersion.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if ver:
                context["risk_level"] = ver.risk_level
                c = (await db.execute(
                    select(Contract).where(Contract.id == ver.contract_id, Contract.tenant_id == tenant_id)
                )).scalar_one_or_none()
                if c:
                    context["amount"] = _safe_float(c.amount_total)
        elif biz_type == "change_request":
            from app.domains.change.models import ChangeRequest
            cr = (await db.execute(
                select(ChangeRequest).where(ChangeRequest.id == biz_id, ChangeRequest.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if cr:
                context["change_type"] = cr.change_type
                impact = cr.impact_json if isinstance(cr.impact_json, dict) else {}
                context["cost_impact"] = _safe_float(impact.get("cost"))
        elif biz_type == "service_ticket":
            from app.domains.service_ticket.models import ServiceTicket
            t = (await db.execute(
                select(ServiceTicket).where(ServiceTicket.id == biz_id, ServiceTicket.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if t:
                context["priority"] = t.priority
                context["type"] = t.type
        elif biz_type == "order":
            from app.domains.order.models import Order
            o = (await db.execute(
                select(Order).where(Order.id == biz_id, Order.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if o:
                context["amount"] = _safe_float(o.amount)
        elif biz_type == "lead":
            from app.domains.lead.models import Lead
            ld = (await db.execute(
                select(Lead).where(Lead.id == biz_id, Lead.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if ld:
                context["score"] = _safe_float(ld.score)
                context["source"] = ld.source
                context["customer_type"] = ld.customer_type
                context["category"] = ld.category
                context["country_type"] = ld.country_type
                context["industry"] = ld.industry
        # solution: no condition fields — always matches (approver-only policy)
    except Exception as e:
        logger.warning("Build policy context failed for %s/%s: %s", biz_type, biz_id, e)
    return context


async def _resolve_policy_approvers(db: AsyncSession, tenant_id: str, biz_type: str, biz_id: str) -> tuple[list[str], list[str], str] | None:
    """Try to resolve approvers from approval_policies table. Returns (ids, names, mode) or None."""
    try:
        from app.domains.admin.service import match_approval_policy
        context = await _build_policy_context(db, tenant_id, biz_type, biz_id)

        policy = await match_approval_policy(db, tenant_id, biz_type, context)
        if not policy or not policy.approver_rules_json:
            return None

        from app.domains.auth.models import User, UserRole, Role
        approver_ids = []
        approver_names = []
        rules = policy.approver_rules_json if isinstance(policy.approver_rules_json, list) else [policy.approver_rules_json]

        # Batch: collect all role codes and user ids first to minimize queries
        role_codes = []
        user_ids = []
        for rule in rules:
            rule_type = rule.get("type", "")
            rule_value = rule.get("value", "")
            if rule_type == "role" and rule_value:
                role_codes.append(rule_value)
            elif rule_type == "user" and rule_value:
                user_ids.append(rule_value)

        # Single query for all role-based approvers
        if role_codes:
            role_users = (await db.execute(
                select(User)
                .join(UserRole, UserRole.user_id == User.id)
                .join(Role, Role.id == UserRole.role_id)
                .where(User.tenant_id == tenant_id, Role.code.in_(role_codes), User.is_active == True)
            )).scalars().all()
            for u in role_users:
                if u.id not in approver_ids:
                    approver_ids.append(u.id)
                    approver_names.append(u.real_name or u.username)

        # Single query for all user-based approvers
        if user_ids:
            direct_users = (await db.execute(
                select(User).where(User.id.in_(user_ids), User.tenant_id == tenant_id)
            )).scalars().all()
            for u in direct_users:
                if u.id not in approver_ids:
                    approver_ids.append(u.id)
                    approver_names.append(u.real_name or u.username)

        if approver_ids:
            return approver_ids, approver_names, policy.approval_mode or "sequential"
    except Exception as e:
        logger.warning("Approver resolution from policy failed: %s", e)
    return None


async def _dispatch_msg_safe(db: AsyncSession, tenant_id: str, title: str, content: str, msg_type: str = "approval"):
    """Dispatch external message notification (non-critical, never throws)."""
    try:
        from app.common.msg_integration import dispatch_message
        await dispatch_message(db, tenant_id, title, content, msg_type=msg_type)
    except Exception as e:
        logger.warning("Dispatch external message failed: %s", e)


async def _create_todo_for_task(db: AsyncSession, tenant_id: str, flow: ApprovalFlow, task: ApprovalTask):
    """尽力为一个待处理审批任务创建钉钉个人待办，并把 todo_id 记到任务上。

    未配置钉钉企业应用 / 审批人无手机号时安全跳过（站内通知已兜底）。深链 PC→审批中心、
    移动端→该审批详情页，实现「PC/移动端不同页面」。
    """
    if not task or task.status != "pending" or not task.assignee_id:
        return
    try:
        from app.common.msg_integration import dispatch_todo
        title = f"审批待处理: {flow.title or flow.biz_type}"
        content = f"{flow.submitted_by_name or ''} 提交了审批，请尽快处理。"
        res = await dispatch_todo(
            db, tenant_id, task.assignee_id, title, content,
            link="/approvals", mobile_link=f"/m/approvals/{flow.id}",
        )
        todo_id = res.get("todo_id")
        if todo_id:
            task.dingtalk_todo_id = todo_id
            await db.commit()
    except Exception as e:
        logger.warning("Create DingTalk todo for task failed: %s", e)


async def _complete_todo_for_task(db: AsyncSession, tenant_id: str, task: ApprovalTask):
    """审批任务被处理/取消时，完结其钉钉个人待办（避免钉钉待办里一直挂着已处理项）。"""
    todo_id = getattr(task, "dingtalk_todo_id", None) if task else None
    if not todo_id or not task.assignee_id:
        return
    try:
        from app.common.msg_integration import complete_todo_for_user
        await complete_todo_for_user(db, tenant_id, task.assignee_id, todo_id)
    except Exception as e:
        logger.warning("Complete DingTalk todo for task failed: %s", e)


async def _enqueue_approval_event(db: AsyncSession, tenant_id: str, event_type: str, flow: ApprovalFlow, extra: dict | None = None):
    """Enqueue an outbox event for the approval lifecycle (must be called before db.commit)."""
    try:
        from app.domains.outbox.service import enqueue_event
        from app.domains.outbox.schemas import OutboxEventCreate
        payload = {
            "flow_id": flow.id,
            "biz_type": flow.biz_type,
            "biz_id": flow.biz_id,
            "title": flow.title,
            "status": flow.status,
            "approval_mode": flow.approval_mode,
            "submitted_by_id": flow.submitted_by_id,
            "submitted_by_name": flow.submitted_by_name,
        }
        if extra:
            payload.update(extra)
        await enqueue_event(db, tenant_id, OutboxEventCreate(
            event_type=event_type,
            aggregate_type="approval_flow",
            aggregate_id=flow.id,
            payload_json=payload,
        ))
    except Exception as e:
        logger.warning("Outbox event enqueue failed for %s: %s", event_type, e)


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

    # If no assignees provided, try to resolve from approval policies
    if not data.assignee_ids:
        resolved = await _resolve_policy_approvers(db, tenant_id, data.biz_type, data.biz_id)
        if resolved:
            data.assignee_ids = resolved[0]
            data.assignee_names = resolved[1]
            if not data.approval_mode:
                data.approval_mode = resolved[2]

    if not data.assignee_ids:
        raise BusinessException(code=BUSINESS_ERROR, message="至少指定一个审批人")

    mode = data.approval_mode or "sequential"

    flow = ApprovalFlow(
        id=generate_uuid(), tenant_id=tenant_id,
        biz_type=data.biz_type, biz_id=data.biz_id,
        title=data.title,
        status="pending",
        approval_mode=mode,
        current_node=1,
        total_nodes=len(data.assignee_ids),
        submitted_by_id=user["sub"],
        submitted_by_name=user.get("real_name") or user.get("username"),
    )
    db.add(flow)

    names = data.assignee_names or [None] * len(data.assignee_ids)
    for i, aid in enumerate(data.assignee_ids):
        if mode == "sequential":
            task_status = "pending" if i == 0 else "waiting"
        else:
            # parallel / any_one: all tasks start as pending
            task_status = "pending"
        task = ApprovalTask(
            id=generate_uuid(), tenant_id=tenant_id,
            flow_id=flow.id,
            node_order=i + 1,
            assignee_id=aid,
            assignee_name=names[i] if i < len(names) else None,
            status=task_status,
        )
        db.add(task)

    # Outbox event (before commit)
    await _enqueue_approval_event(db, tenant_id, "approval.submitted", flow)

    await db.commit()
    await db.refresh(flow)

    await log_action(
        db, tenant_id=tenant_id, user_id=user["sub"],
        user_name=user.get("real_name") or user.get("username"),
        action="submit_approval", resource_type=data.biz_type, resource_id=data.biz_id,
        summary=f"提交审批: {data.title or data.biz_type}"
    )

    # Notifications
    if mode == "sequential":
        # Notify first approver only
        await send_notification(
            db, tenant_id, data.assignee_ids[0],
            type="approval_pending",
            title=f"您有新的审批待处理: {data.title or data.biz_type}",
            content=f"{flow.submitted_by_name} 提交了审批请求",
            biz_type="approval_flow", biz_id=flow.id,
            sender_name=flow.submitted_by_name,
        )
        await _dispatch_msg_safe(db, tenant_id,
            "审批待处理通知",
            f"**审批人**: {names[0] or data.assignee_ids[0]}\n\n**业务类型**: {data.biz_type}\n\n**审批对象**: {data.title or data.biz_type}\n\n请尽快登录系统处理审批。")
    else:
        # parallel / any_one: notify all approvers
        for i, aid in enumerate(data.assignee_ids):
            await send_notification(
                db, tenant_id, aid,
                type="approval_pending",
                title=f"您有新的审批待处理: {data.title or data.biz_type}",
                content=f"{flow.submitted_by_name} 提交了审批请求（{mode}模式）",
                biz_type="approval_flow", biz_id=flow.id,
                sender_name=flow.submitted_by_name,
            )
        await _dispatch_msg_safe(db, tenant_id,
            "审批待处理通知",
            f"**审批模式**: {mode}\n\n**业务类型**: {data.biz_type}\n\n**审批对象**: {data.title or data.biz_type}\n\n请相关审批人尽快处理。")

    # 钉钉个人待办：给当前待处理审批人逐个下发
    for t in await get_flow_tasks(db, tenant_id, flow.id):
        if t.status == "pending":
            await _create_todo_for_task(db, tenant_id, flow, t)

    return flow


async def decide(db: AsyncSession, tenant_id: str, task_id: str, action: str, comment: str | None, user: dict) -> ApprovalFlow:
    if action not in ("approved", "rejected"):
        raise BusinessException(code=BUSINESS_ERROR, message="action 必须为 approved 或 rejected")

    # Lock task row to prevent concurrent decisions
    task = (await db.execute(
        select(ApprovalTask).where(ApprovalTask.id == task_id, ApprovalTask.tenant_id == tenant_id)
        .with_for_update()
    )).scalar_one_or_none()
    if not task:
        raise BusinessException(code=NOT_FOUND, message="审批任务不存在")
    if task.status == "waiting":
        raise BusinessException(code=BUSINESS_ERROR, message="前序审批节点尚未完成，请等待轮到您再处理")
    if task.status != "pending":
        raise BusinessException(code=BUSINESS_ERROR, message="该审批任务已处理")
    if task.assignee_id != user["sub"]:
        raise BusinessException(code=BUSINESS_ERROR, message="您不是该审批任务的审批人")

    # Lock flow row to prevent concurrent state transitions
    flow = (await db.execute(
        select(ApprovalFlow).where(ApprovalFlow.id == task.flow_id, ApprovalFlow.tenant_id == tenant_id)
        .with_for_update()
    )).scalar_one_or_none()
    if not flow:
        raise BusinessException(code=NOT_FOUND, message="审批流不存在")
    if flow.status != "pending":
        raise BusinessException(code=BUSINESS_ERROR, message="审批流已结束")

    mode = flow.approval_mode or "sequential"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    task.status = action
    task.comment = comment
    task.decided_at = now

    if mode == "sequential":
        # Enforce sequential node order
        if task.node_order != flow.current_node:
            raise BusinessException(code=BUSINESS_ERROR, message="请等待前序审批节点完成")

        if action == "rejected":
            flow.status = "rejected"
        elif action == "approved":
            if task.node_order >= flow.total_nodes:
                flow.status = "approved"
            else:
                flow.current_node = task.node_order + 1
                tasks = await get_flow_tasks(db, tenant_id, flow.id)
                next_task = next((t for t in tasks if t.node_order == flow.current_node), None)
                if next_task and next_task.status == "waiting":
                    next_task.status = "pending"

    elif mode == "parallel":
        # All must approve; any reject => flow rejected
        if action == "rejected":
            flow.status = "rejected"
            # Cancel remaining pending tasks
            all_tasks = await get_flow_tasks(db, tenant_id, flow.id)
            for t in all_tasks:
                if t.id != task.id and t.status == "pending":
                    t.status = "cancelled"
        elif action == "approved":
            # Check if all other tasks are also approved
            all_tasks = await get_flow_tasks(db, tenant_id, flow.id)
            all_decided = all(t.status in ("approved", "cancelled") for t in all_tasks if t.id != task.id)
            all_approved = all(t.status == "approved" for t in all_tasks)
            if all_approved:
                flow.status = "approved"

    elif mode == "any_one":
        # Any approve => flow approved; all reject => flow rejected
        if action == "approved":
            flow.status = "approved"
            # Cancel remaining pending tasks
            all_tasks = await get_flow_tasks(db, tenant_id, flow.id)
            for t in all_tasks:
                if t.id != task.id and t.status == "pending":
                    t.status = "cancelled"
        elif action == "rejected":
            # Check if all other tasks are also rejected
            all_tasks = await get_flow_tasks(db, tenant_id, flow.id)
            all_rejected = all(t.status in ("rejected", "cancelled") for t in all_tasks)
            if all_rejected:
                flow.status = "rejected"

    # Outbox event (before commit)
    if flow.status in ("approved", "rejected"):
        event_type = "approval.approved" if flow.status == "approved" else "approval.rejected"
        await _enqueue_approval_event(db, tenant_id, event_type, flow, {"decided_by": user["sub"]})

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

    # If sequential, approved, and there's a next node, notify next approver
    if mode == "sequential" and action == "approved" and flow.status == "pending":
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

    # External message on flow completion
    if flow.status in ("approved", "rejected"):
        result_label = "通过" if flow.status == "approved" else "驳回"
        await _dispatch_msg_safe(db, tenant_id,
            f"审批{result_label}通知",
            f"**审批对象**: {flow.title or flow.biz_type}\n\n**结果**: {result_label}\n\n**审批人**: {user_name}")

    # Approval completion callback — auto-update biz object status
    if flow.status == "approved":
        await _on_approval_completed(db, tenant_id, flow)
    elif flow.status == "rejected":
        await _on_approval_rejected(db, tenant_id, flow, comment)

    # Auto-activity: record approval decision on the biz object timeline
    try:
        from app.common.auto_activity import record_activity
        biz_type_map = {
            "quote_version": "project", "contract_version": "project",
            "change_request": "project", "solution": "project",
        }
        activity_biz_type = biz_type_map.get(flow.biz_type, flow.biz_type)
        activity_biz_id = flow.biz_id
        if flow.biz_type in ("quote_version", "contract_version"):
            try:
                if flow.biz_type == "quote_version":
                    from app.domains.quote.models import QuoteVersion, Quote
                    ver = (await db.execute(select(QuoteVersion).where(QuoteVersion.id == flow.biz_id, QuoteVersion.tenant_id == tenant_id))).scalar_one_or_none()
                    if ver:
                        q = (await db.execute(select(Quote).where(Quote.id == ver.quote_id, Quote.tenant_id == tenant_id))).scalar_one_or_none()
                        if q:
                            activity_biz_id = q.project_id
                elif flow.biz_type == "contract_version":
                    from app.domains.contract.models import ContractVersion, Contract
                    ver = (await db.execute(select(ContractVersion).where(ContractVersion.id == flow.biz_id, ContractVersion.tenant_id == tenant_id))).scalar_one_or_none()
                    if ver:
                        c = (await db.execute(select(Contract).where(Contract.id == ver.contract_id, Contract.tenant_id == tenant_id))).scalar_one_or_none()
                        if c:
                            activity_biz_id = c.project_id
            except Exception as e:
                logger.warning("Failed to resolve project_id from %s: %s", flow.biz_type, e)
        elif flow.biz_type == "change_request":
            try:
                from app.domains.change.models import ChangeRequest
                cr = (await db.execute(select(ChangeRequest).where(ChangeRequest.id == flow.biz_id, ChangeRequest.tenant_id == tenant_id))).scalar_one_or_none()
                if cr:
                    activity_biz_id = cr.project_id
            except Exception as e:
                logger.warning("Failed to resolve project_id from change_request: %s", e)

        decision_label = "通过" if action == "approved" else "驳回"
        await record_activity(db, tenant_id, activity_biz_type, activity_biz_id, "system",
                              f"审批{decision_label}: {flow.title or flow.biz_type}", comment,
                              user["sub"], user_name)
    except Exception as e:
        logger.warning("Failed to record approval activity: %s", e)

    # 钉钉待办同步
    await _complete_todo_for_task(db, tenant_id, task)  # 本人已决策 → 完结其待办
    if flow.status in ("approved", "rejected"):
        # parallel 驳回 / any_one 通过会取消其余待处理任务 → 一并完结它们的待办
        for t in await get_flow_tasks(db, tenant_id, flow.id):
            if t.status == "cancelled" and t.id != task.id:
                await _complete_todo_for_task(db, tenant_id, t)
    elif mode == "sequential" and action == "approved":
        # 顺序审批推进 → 给新的待处理审批人下发待办
        nt = next((t for t in await get_flow_tasks(db, tenant_id, flow.id)
                   if t.node_order == flow.current_node and t.status == "pending"), None)
        if nt:
            await _create_todo_for_task(db, tenant_id, flow, nt)

    return flow


async def _on_approval_completed(db: AsyncSession, tenant_id: str, flow: ApprovalFlow):
    """Update biz object status when approval is fully approved."""
    try:
        updated = False
        if flow.biz_type == "quote_version":
            from app.domains.quote.models import QuoteVersion
            ver = (await db.execute(
                select(QuoteVersion).where(QuoteVersion.id == flow.biz_id, QuoteVersion.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if ver:
                ver.status = "approved"
                updated = True
        elif flow.biz_type == "contract_version":
            from app.domains.contract.models import ContractVersion
            ver = (await db.execute(
                select(ContractVersion).where(ContractVersion.id == flow.biz_id, ContractVersion.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if ver:
                ver.status = "approved"
                updated = True
        elif flow.biz_type == "change_request":
            from app.domains.change.models import ChangeRequest
            cr = (await db.execute(
                select(ChangeRequest).where(ChangeRequest.id == flow.biz_id, ChangeRequest.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if cr:
                cr.status = "approved"
                updated = True
        elif flow.biz_type == "solution":
            from app.domains.solution.models import Solution
            sol = (await db.execute(
                select(Solution).where(Solution.id == flow.biz_id, Solution.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if sol:
                sol.status = "approved"
                updated = True
        elif flow.biz_type == "lead":
            from app.domains.lead.models import Lead
            ld = (await db.execute(
                select(Lead).where(Lead.id == flow.biz_id, Lead.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if ld:
                ld.review_status = "approved"
                ld.reject_reason = None
                updated = True
        if updated:
            await db.commit()
    except Exception as e:
        logger.warning("Approval completion callback failed for %s/%s: %s", flow.biz_type, flow.biz_id, e)


async def _on_approval_rejected(db: AsyncSession, tenant_id: str, flow: ApprovalFlow, comment: str | None = None):
    """Update biz object status when approval is rejected.

    Symmetric to `_on_approval_completed`: without this, a rejected单据 keeps its
    pre-approval status (reviewing/submitted) or even a stale "approved", so the
    business page never reflects the驳回 (issue #82). Set it to "rejected" so the
    detail page shows「已驳回」and the owner can revise & resubmit."""
    try:
        updated = False
        if flow.biz_type == "quote_version":
            from app.domains.quote.models import QuoteVersion
            ver = (await db.execute(
                select(QuoteVersion).where(QuoteVersion.id == flow.biz_id, QuoteVersion.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if ver:
                ver.status = "rejected"
                updated = True
        elif flow.biz_type == "contract_version":
            from app.domains.contract.models import ContractVersion
            ver = (await db.execute(
                select(ContractVersion).where(ContractVersion.id == flow.biz_id, ContractVersion.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if ver:
                ver.status = "rejected"
                updated = True
        elif flow.biz_type == "change_request":
            from app.domains.change.models import ChangeRequest
            cr = (await db.execute(
                select(ChangeRequest).where(ChangeRequest.id == flow.biz_id, ChangeRequest.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if cr:
                cr.status = "rejected"
                updated = True
        elif flow.biz_type == "solution":
            from app.domains.solution.models import Solution
            sol = (await db.execute(
                select(Solution).where(Solution.id == flow.biz_id, Solution.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if sol:
                sol.status = "rejected"
                updated = True
        elif flow.biz_type == "lead":
            from app.domains.lead.models import Lead
            ld = (await db.execute(
                select(Lead).where(Lead.id == flow.biz_id, Lead.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if ld:
                ld.review_status = "rejected"
                ld.reject_reason = comment
                updated = True
        if updated:
            await db.commit()
    except Exception as e:
        logger.warning("Approval rejection callback failed for %s/%s: %s", flow.biz_type, flow.biz_id, e)


async def withdraw_flow(db: AsyncSession, tenant_id: str, flow_id: str, reason: str | None, user: dict) -> ApprovalFlow:
    """Withdraw a pending approval flow (only by the submitter)."""
    flow = await get_flow(db, tenant_id, flow_id)
    if flow.status != "pending":
        raise BusinessException(code=BUSINESS_ERROR, message="只能撤回进行中的审批流")
    if flow.submitted_by_id != user["sub"]:
        raise BusinessException(code=BUSINESS_ERROR, message="只有发起人可以撤回审批")

    flow.status = "withdrawn"

    # Cancel all pending/waiting tasks
    tasks = await get_flow_tasks(db, tenant_id, flow.id)
    current_assignees = []
    for t in tasks:
        if t.status in ("pending", "waiting"):
            if t.status == "pending":
                current_assignees.append(t.assignee_id)
            t.status = "cancelled"

    # Outbox event (before commit)
    await _enqueue_approval_event(db, tenant_id, "approval.withdrawn", flow, {"reason": reason})

    await db.commit()
    await db.refresh(flow)

    user_name = user.get("real_name") or user.get("username")
    await log_action(
        db, tenant_id=tenant_id, user_id=user["sub"], user_name=user_name,
        action="withdraw_approval", resource_type=flow.biz_type, resource_id=flow.biz_id,
        summary=f"撤回审批: {flow.title or flow.biz_type}" + (f"（原因: {reason}）" if reason else ""),
    )

    # Notify current approvers
    for assignee_id in current_assignees:
        await send_notification(
            db, tenant_id, assignee_id,
            type="approval_withdrawn",
            title=f"审批已撤回: {flow.title or flow.biz_type}",
            content=f"发起人 {user_name} 撤回了审批" + (f"，原因: {reason}" if reason else ""),
            biz_type="approval_flow", biz_id=flow.id,
            sender_name=user_name,
        )

    await _dispatch_msg_safe(db, tenant_id,
        "审批撤回通知",
        f"**审批对象**: {flow.title or flow.biz_type}\n\n**发起人**: {user_name}\n\n**操作**: 已撤回" + (f"\n\n**原因**: {reason}" if reason else ""))

    # 完结被撤回而取消的审批任务对应的钉钉待办
    for t in await get_flow_tasks(db, tenant_id, flow.id):
        if t.status == "cancelled":
            await _complete_todo_for_task(db, tenant_id, t)

    return flow


async def delegate_task(db: AsyncSession, tenant_id: str, task_id: str, target_user_id: str, reason: str | None, user: dict) -> ApprovalTask:
    """Delegate an approval task to another user."""
    task = (await db.execute(
        select(ApprovalTask).where(ApprovalTask.id == task_id, ApprovalTask.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not task:
        raise BusinessException(code=NOT_FOUND, message="审批任务不存在")
    if task.status != "pending":
        raise BusinessException(code=BUSINESS_ERROR, message="只能转交待处理的审批任务")
    if task.assignee_id != user["sub"]:
        raise BusinessException(code=BUSINESS_ERROR, message="您不是该审批任务的审批人")

    flow = await get_flow(db, tenant_id, task.flow_id)
    if flow.status != "pending":
        raise BusinessException(code=BUSINESS_ERROR, message="审批流已结束")

    # Resolve target user
    from app.domains.auth.models import User
    target = (await db.execute(
        select(User).where(User.id == target_user_id, User.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not target:
        raise BusinessException(code=NOT_FOUND, message="目标用户不存在")

    original_name = task.assignee_name
    old_todo_id = task.dingtalk_todo_id
    old_assignee_id = task.assignee_id
    task.assignee_id = target_user_id
    task.assignee_name = target.real_name or target.username
    task.dingtalk_todo_id = None

    await db.commit()
    await db.refresh(task)

    user_name = user.get("real_name") or user.get("username")
    await log_action(
        db, tenant_id=tenant_id, user_id=user["sub"], user_name=user_name,
        action="delegate_approval", resource_type=flow.biz_type, resource_id=flow.biz_id,
        summary=f"转交审批: {flow.title or flow.biz_type} → {target.real_name or target.username}" + (f"（原因: {reason}）" if reason else ""),
    )

    # Notify new assignee
    await send_notification(
        db, tenant_id, target_user_id,
        type="approval_pending",
        title=f"您有新的审批待处理（转交）: {flow.title or flow.biz_type}",
        content=f"{user_name} 将审批任务转交给您" + (f"，原因: {reason}" if reason else ""),
        biz_type="approval_flow", biz_id=flow.id,
        sender_name=user_name,
    )

    # Notify original assignee
    await send_notification(
        db, tenant_id, user["sub"],
        type="approval_delegated",
        title=f"审批已转交: {flow.title or flow.biz_type}",
        content=f"已转交给 {target.real_name or target.username}",
        biz_type="approval_flow", biz_id=flow.id,
        sender_name="系统",
    )

    # 钉钉待办：完结原审批人的待办，给转交对象新建待办
    if old_todo_id:
        try:
            from app.common.msg_integration import complete_todo_for_user
            await complete_todo_for_user(db, tenant_id, old_assignee_id, old_todo_id)
        except Exception as e:
            logger.warning("Complete delegated DingTalk todo failed: %s", e)
    await _create_todo_for_task(db, tenant_id, flow, task)

    return task


async def resubmit_approval(db: AsyncSession, tenant_id: str, flow_id: str, data, user: dict) -> ApprovalFlow:
    """Resubmit a rejected approval flow, creating a new flow linked to the original."""
    original = await get_flow(db, tenant_id, flow_id)
    if original.status != "rejected":
        raise BusinessException(code=BUSINESS_ERROR, message="只能重新提交已驳回的审批流")
    if original.submitted_by_id != user["sub"]:
        raise BusinessException(code=BUSINESS_ERROR, message="只有原发起人可以重新提交")

    # Build submit data using original flow as defaults
    assignee_ids = data.assignee_ids if data.assignee_ids else []
    assignee_names = data.assignee_names

    # If no new approvers provided, reuse original flow's approvers
    if not assignee_ids:
        original_tasks = await get_flow_tasks(db, tenant_id, original.id)
        assignee_ids = [t.assignee_id for t in original_tasks]
        assignee_names = [t.assignee_name for t in original_tasks]

    submit_data = ApprovalSubmit(
        biz_type=data.biz_type or original.biz_type,
        biz_id=data.biz_id or original.biz_id,
        title=data.title or original.title,
        assignee_ids=assignee_ids,
        assignee_names=assignee_names,
        approval_mode=data.approval_mode or original.approval_mode,
    )

    new_flow = await submit_approval(db, tenant_id, submit_data, user)
    # Link to original
    new_flow.parent_flow_id = original.id
    new_flow.revision_no = original.revision_no + 1
    await db.commit()
    await db.refresh(new_flow)

    return new_flow


async def auto_trigger_approval(db: AsyncSession, tenant_id: str, biz_type: str, biz_id: str, title: str, user: dict) -> ApprovalFlow | None:
    """Auto-trigger approval if a matching policy exists. Returns the flow or None.
    When no policy matches, notify the submitter so the submission isn't silently
    stuck in 'submitted' with no approver (was a silent no-op before)."""
    resolved = await _resolve_policy_approvers(db, tenant_id, biz_type, biz_id)
    if not resolved:
        try:
            from app.domains.notification.service import send_notification
            await send_notification(
                db, tenant_id, recipient_id=user["sub"], type="system",
                title=f"已提交，但未配置审批流程：{title}",
                content="未找到匹配的审批策略，该单据不会自动进入审批。请联系管理员在「系统配置 → 审批策略」中配置后再提交。",
                biz_type=biz_type, biz_id=biz_id,
            )
        except Exception:
            logger.warning("No-policy notify failed for %s/%s", biz_type, biz_id)
        return None
    ids, names, mode = resolved
    data = ApprovalSubmit(
        biz_type=biz_type, biz_id=biz_id, title=title,
        assignee_ids=ids, assignee_names=names, approval_mode=mode,
    )
    return await submit_approval(db, tenant_id, data, user)


async def bulk_decide(db: AsyncSession, tenant_id: str, task_ids: list[str], action: str, comment: str | None, user: dict) -> list[dict]:
    """Bulk approve/reject multiple tasks. Returns list of results."""
    results = []
    for tid in task_ids:
        try:
            flow = await decide(db, tenant_id, tid, action, comment, user)
            results.append({"task_id": tid, "success": True, "flow_status": flow.status})
        except BusinessException as e:
            results.append({"task_id": tid, "success": False, "error": e.message})
        except Exception as e:
            results.append({"task_id": tid, "success": False, "error": str(e)})
    return results


async def get_statistics(db: AsyncSession, tenant_id: str, date_from: str | None = None, date_to: str | None = None) -> dict:
    """Get approval statistics for the tenant using SQL aggregation."""
    from sqlalchemy import extract, case

    # Build shared WHERE conditions
    conditions = [ApprovalFlow.tenant_id == tenant_id]
    if date_from:
        conditions.append(ApprovalFlow.created_at >= date_from)
    if date_to:
        conditions.append(ApprovalFlow.created_at <= date_to)

    # 1. Total count
    total_q = select(func.count(ApprovalFlow.id)).where(*conditions)
    total = (await db.execute(total_q)).scalar() or 0

    # 2. Status breakdown via GROUP BY
    status_q = select(
        ApprovalFlow.status,
        func.count(ApprovalFlow.id),
    ).where(*conditions).group_by(ApprovalFlow.status)
    status_rows = (await db.execute(status_q)).all()
    status_breakdown = {row[0]: row[1] for row in status_rows}

    # 3. By biz_type via GROUP BY
    biz_q = select(
        ApprovalFlow.biz_type,
        func.count(ApprovalFlow.id),
    ).where(*conditions).group_by(ApprovalFlow.biz_type)
    biz_rows = (await db.execute(biz_q)).all()
    by_biz_type = {row[0]: row[1] for row in biz_rows}

    # 4. Average approval hours via SQL AVG on approved flows
    avg_q = select(
        func.avg(
            extract("epoch", ApprovalFlow.updated_at - ApprovalFlow.created_at) / 3600
        )
    ).where(
        *conditions,
        ApprovalFlow.status == "approved",
        ApprovalFlow.created_at.isnot(None),
        ApprovalFlow.updated_at.isnot(None),
    )
    avg_hours_raw = (await db.execute(avg_q)).scalar()
    avg_hours = round(float(avg_hours_raw), 1) if avg_hours_raw else 0

    # 5. Approval rate
    approved_count = status_breakdown.get("approved", 0)
    rejected_count = status_breakdown.get("rejected", 0)
    decided_total = approved_count + rejected_count
    approval_rate = round(approved_count / decided_total, 2) if decided_total > 0 else 0

    # 6. SLA compliance via SQL
    from app.domains.admin.models import ApprovalPolicy
    policies = (await db.execute(
        select(ApprovalPolicy).where(ApprovalPolicy.tenant_id == tenant_id, ApprovalPolicy.enabled == True)
    )).scalars().all()
    sla_map = {p.biz_type: p.sla_hours for p in policies if p.sla_hours}

    sla_total = 0
    sla_compliant = 0
    if sla_map:
        # Count decided flows that have an SLA policy, and check compliance
        sla_conditions = [
            *conditions,
            ApprovalFlow.status.in_(["approved", "rejected"]),
            ApprovalFlow.biz_type.in_(list(sla_map.keys())),
            ApprovalFlow.created_at.isnot(None),
            ApprovalFlow.updated_at.isnot(None),
        ]
        # Total SLA-applicable flows
        sla_total_q = select(func.count(ApprovalFlow.id)).where(*sla_conditions)
        sla_total = (await db.execute(sla_total_q)).scalar() or 0

        if sla_total > 0:
            # Build CASE expression for compliance: compliant if hours <= sla for that biz_type
            hours_expr = extract("epoch", ApprovalFlow.updated_at - ApprovalFlow.created_at) / 3600
            compliant_whens = [
                (ApprovalFlow.biz_type == biz_type, hours_expr <= sla_hours)
                for biz_type, sla_hours in sla_map.items()
            ]
            compliant_case = case(*compliant_whens, else_=False)
            sla_compliant_q = select(
                func.count(ApprovalFlow.id)
            ).where(*sla_conditions, compliant_case)
            sla_compliant = (await db.execute(sla_compliant_q)).scalar() or 0

    sla_rate = round(sla_compliant / sla_total, 2) if sla_total > 0 else 1.0

    # 7. Top approvers via GROUP BY (already uses SQL)
    task_base = select(
        ApprovalTask.assignee_name,
        func.count(ApprovalTask.id).label("cnt"),
    ).where(
        ApprovalTask.tenant_id == tenant_id,
        ApprovalTask.status.in_(["approved", "rejected"]),
    ).group_by(ApprovalTask.assignee_name).order_by(func.count(ApprovalTask.id).desc()).limit(10)
    top_rows = (await db.execute(task_base)).all()
    top_approvers = [{"name": r[0] or "未知", "count": r[1]} for r in top_rows]

    return {
        "total_flows": total,
        "status_breakdown": status_breakdown,
        "avg_approval_hours": avg_hours,
        "approval_rate": approval_rate,
        "sla_compliance_rate": sla_rate,
        "by_biz_type": by_biz_type,
        "top_approvers": top_approvers,
    }


async def _resolve_biz_detail(db: AsyncSession, tenant_id: str, biz_type: str, biz_id: str) -> dict:
    """Resolve business object key information for approval detail display."""
    detail = {}
    try:
        if biz_type == "quote_version":
            from app.domains.quote.models import QuoteVersion, Quote
            ver = (await db.execute(
                select(QuoteVersion).where(QuoteVersion.id == biz_id, QuoteVersion.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if ver:
                detail["margin_rate"] = f"{float(ver.margin_rate) * 100:.1f}%" if ver.margin_rate is not None else "-"
                detail["price_total"] = f"¥{float(ver.price_total):,.2f}" if ver.price_total is not None else "-"
                detail["version_no"] = ver.version_no
                q = (await db.execute(select(Quote).where(Quote.id == ver.quote_id, Quote.tenant_id == tenant_id))).scalar_one_or_none()
                if q:
                    detail["quote_no"] = q.quote_no
        elif biz_type == "contract_version":
            from app.domains.contract.models import ContractVersion, Contract
            ver = (await db.execute(
                select(ContractVersion).where(ContractVersion.id == biz_id, ContractVersion.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if ver:
                detail["version_no"] = ver.version_no
                c = (await db.execute(select(Contract).where(Contract.id == ver.contract_id, Contract.tenant_id == tenant_id))).scalar_one_or_none()
                if c:
                    detail["contract_no"] = c.contract_no
                    detail["amount_total"] = f"¥{float(c.amount_total):,.2f}" if c.amount_total is not None else "-"
        elif biz_type == "change_request":
            from app.domains.change.models import ChangeRequest
            cr = (await db.execute(
                select(ChangeRequest).where(ChangeRequest.id == biz_id, ChangeRequest.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if cr:
                detail["change_no"] = cr.change_no
                detail["change_type"] = cr.change_type
                detail["scope_description"] = cr.scope_description
        elif biz_type == "lead":
            from app.domains.lead.models import Lead
            ld = (await db.execute(
                select(Lead).where(Lead.id == biz_id, Lead.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if ld:
                if ld.lead_code:
                    detail["lead_code"] = ld.lead_code
                if ld.company_name:
                    detail["company_name"] = ld.company_name
                if ld.owner_name:
                    detail["owner_name"] = ld.owner_name
                if ld.source:
                    detail["source"] = ld.source
                if ld.budget_range:
                    detail["budget_range"] = ld.budget_range
                contact = " ".join([p for p in (ld.contact_name, ld.contact_phone) if p])
                if contact:
                    detail["contact"] = contact
    except Exception as e:
        logger.warning("Failed to resolve biz detail for %s/%s: %s", biz_type, biz_id, e)
    return detail


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


async def check_sla_overdue(db: AsyncSession, tenant_id: str) -> int:
    """Check for approval tasks that have exceeded SLA hours and send reminder notifications."""
    from app.domains.admin.models import ApprovalPolicy

    policies_result = await db.execute(
        select(ApprovalPolicy).where(
            ApprovalPolicy.tenant_id == tenant_id,
            ApprovalPolicy.enabled == True,
            ApprovalPolicy.sla_hours.isnot(None),
        )
    )
    policies = {p.biz_type: p for p in policies_result.scalars().all()}
    if not policies:
        return 0

    # Only fetch flows whose biz_type has an SLA policy
    pending_flows = await db.execute(
        select(ApprovalFlow).where(
            ApprovalFlow.tenant_id == tenant_id,
            ApprovalFlow.status == "pending",
            ApprovalFlow.biz_type.in_(list(policies.keys())),
        )
    )
    flows = pending_flows.scalars().all()

    # Batch-load all pending tasks for these flows in a single query (fix N+1)
    flow_ids = [f.id for f in flows]
    tasks_by_flow: dict[str, list[ApprovalTask]] = {}
    if flow_ids:
        all_tasks_result = await db.execute(
            select(ApprovalTask).where(
                ApprovalTask.tenant_id == tenant_id,
                ApprovalTask.flow_id.in_(flow_ids),
            ).order_by(ApprovalTask.node_order)
        )
        for t in all_tasks_result.scalars().all():
            tasks_by_flow.setdefault(t.flow_id, []).append(t)

    notified = 0
    now = datetime.now(timezone.utc)
    for flow in flows:
        policy = policies.get(flow.biz_type)
        if not policy or not policy.sla_hours:
            continue

        if not flow.created_at:
            continue
        created = flow.created_at if flow.created_at.tzinfo else flow.created_at.replace(tzinfo=timezone.utc)
        elapsed_hours = (now - created).total_seconds() / 3600
        if elapsed_hours <= policy.sla_hours:
            continue

        flow_tasks = tasks_by_flow.get(flow.id, [])
        pending_task = next((t for t in flow_tasks if t.status == "pending"), None)
        if not pending_task:
            continue

        # Escalation chain handling
        escalation = policy.escalation_json if hasattr(policy, 'escalation_json') and policy.escalation_json else None
        if escalation and isinstance(escalation, list):
            for i, step in enumerate(escalation):
                if i < flow.escalation_level:
                    continue  # Already handled
                after_hours = step.get("after_hours", 0)
                if elapsed_hours < after_hours:
                    break
                action_type = step.get("action", "remind")
                if action_type == "remind":
                    try:
                        await send_notification(
                            db, tenant_id, pending_task.assignee_id,
                            type="approval_sla_overdue",
                            title=f"审批超时提醒（第{i+1}级）: {flow.title or flow.biz_type}",
                            content=f"审批已等待 {int(elapsed_hours)} 小时，超过 SLA 要求的 {policy.sla_hours} 小时。",
                            biz_type="approval_flow", biz_id=flow.id,
                            sender_name="系统",
                        )
                        await _dispatch_msg_safe(db, tenant_id,
                            "审批超时升级通知",
                            f"**审批对象**: {flow.title or flow.biz_type}\n\n**已等待**: {int(elapsed_hours)}小时\n\n**SLA**: {policy.sla_hours}小时\n\n请尽快处理。")
                        notified += 1
                    except Exception as e:
                        logger.warning("SLA escalation notification failed for flow %s: %s", flow.id, e)
                elif action_type == "auto_approve":
                    # SLA auto-approve: nobody acted in time, so push the WHOLE flow
                    # through. Approve every not-yet-decided task (pending + the
                    # downstream 'waiting' nodes of a sequential flow) and complete
                    # the flow — otherwise a multi-node sequential flow would approve
                    # only the current node and hang forever (escalation_level is
                    # already maxed, so it never retries).
                    try:
                        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
                        for t in flow_tasks:
                            if t.status in ("pending", "waiting"):
                                t.status = "approved"
                                t.comment = f"SLA超时自动通过（{int(elapsed_hours)}小时）"
                                t.decided_at = ts
                        flow.current_node = flow.total_nodes
                        flow.status = "approved"
                        await _on_approval_completed(db, tenant_id, flow)
                        notified += 1
                    except Exception as e:
                        logger.warning("SLA auto-approve failed for flow %s: %s", flow.id, e)
                flow.escalation_level = i + 1
            await db.commit()
        else:
            # Simple SLA notification (no escalation chain)
            try:
                await send_notification(
                    db, tenant_id, pending_task.assignee_id,
                    type="approval_sla_overdue",
                    title=f"审批超时提醒: {flow.title or flow.biz_type}",
                    content=f"审批已等待 {int(elapsed_hours)} 小时，超过 SLA 要求的 {policy.sla_hours} 小时，请尽快处理。",
                    biz_type="approval_flow", biz_id=flow.id,
                    sender_name="系统",
                )
                await _dispatch_msg_safe(db, tenant_id,
                    "审批超时提醒",
                    f"**审批对象**: {flow.title or flow.biz_type}\n\n**已等待**: {int(elapsed_hours)}小时\n\n请尽快处理。")
                notified += 1
            except Exception as e:
                logger.warning("SLA overdue notification failed for flow %s: %s", flow.id, e)

    return notified
