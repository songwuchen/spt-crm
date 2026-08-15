import logging
from datetime import datetime, timezone

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND, BUSINESS_ERROR, FORBIDDEN
from app.domains.approval.models import ApprovalFlow, ApprovalTask
from app.domains.approval.schemas import ApprovalSubmit
from app.domains.audit.service import log_action
from app.domains.notification.service import send_notification

logger = logging.getLogger("spt_crm.approval")


def _involved_clause(user: dict):
    """「与我相关」：我发起的，或有一个节点指派给我（含已办）。"""
    uid = user.get("sub")
    return or_(
        ApprovalFlow.submitted_by_id == uid,
        ApprovalFlow.id.in_(
            select(ApprovalTask.flow_id).where(ApprovalTask.assignee_id == uid)
        ),
    )


def _can_see_all_flows(user: dict) -> bool:
    perms = user.get("permissions", []) or []
    return "*" in perms or "approval:manage" in perms


async def list_flows(db: AsyncSession, tenant_id: str, biz_type: str | None = None, biz_id: str | None = None, status: str | None = None, page: int = 1, page_size: int = 50, user: dict | None = None, submitted_by_id: str | None = None):
    q = select(ApprovalFlow).where(ApprovalFlow.tenant_id == tenant_id)
    # 「所有审批」tab 过去对任何持 approval:view 的人开放全租户审批流（含标题里的客户名/项目名
    # 和详情里的 biz_detail）。approval:view 属于全员基础权限，等于全公司审批对所有人可见。
    if user is not None and not _can_see_all_flows(user):
        q = q.where(_involved_clause(user))
    if submitted_by_id:
        # 非管理员只能查自己发起的，避免借参数窥探他人
        if user is not None and not _can_see_all_flows(user) and submitted_by_id != user.get("sub"):
            submitted_by_id = user.get("sub")
        q = q.where(ApprovalFlow.submitted_by_id == submitted_by_id)
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


async def get_flow(db: AsyncSession, tenant_id: str, flow_id: str, user: dict | None = None) -> ApprovalFlow:
    """取审批流。传入 user 时校验「与我相关」——审批详情会带出 biz_detail（被审业务对象的
    公司名/金额等），不能让任何持 approval:view 的人按 id 翻别人的审批。

    user=None 为内部调用（撤回/重提/引擎回调自身另有身份校验）。
    """
    f = (await db.execute(
        select(ApprovalFlow).where(ApprovalFlow.id == flow_id, ApprovalFlow.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not f:
        raise BusinessException(code=NOT_FOUND, message="审批流不存在")
    if user is not None and not _can_see_all_flows(user):
        uid = user.get("sub")
        involved = f.submitted_by_id == uid or (await db.execute(
            select(ApprovalTask.id).where(
                ApprovalTask.flow_id == flow_id,
                ApprovalTask.tenant_id == tenant_id,
                ApprovalTask.assignee_id == uid,
            ).limit(1)
        )).scalar_one_or_none() is not None
        if not involved:
            raise BusinessException(code=FORBIDDEN, message="无权查看该审批（不是发起人或审批人）")
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
                context["contract_id"] = ver.contract_id
                c = (await db.execute(
                    select(Contract).where(Contract.id == ver.contract_id, Contract.tenant_id == tenant_id)
                )).scalar_one_or_none()
                if c:
                    amt = _safe_float(c.amount_total)
                    context["amount"] = amt
                    context["amount_total"] = amt
                    context["change_type"] = c.change_type
                    context["department_id"] = c.department_id
                    reg = c.registration_json if isinstance(c.registration_json, dict) else {}
                    context["industry"] = reg.get("industry")
                    context["is_export"] = reg.get("is_export")
                    # 对齐简道云合同登记运营分支（标准交付 / 方式 / 旋振筛）
                    context["standard_delivery"] = reg.get("standard_delivery")
                    context["delivery_mode"] = reg.get("delivery_mode")
                    context["is_rotary_sieve"] = reg.get("is_rotary_sieve")
                    # 二级节点审批人：采购填的采购员 / 质检填的质检员
                    context["purchasers"] = reg.get("purchasers")
                    context["inspectors"] = reg.get("inspectors")
                    context["fill_code"] = reg.get("fill_code")
        elif biz_type == "contract_review":
            from app.domains.contract_review.models import ContractReview
            rv = (await db.execute(
                select(ContractReview).where(ContractReview.id == biz_id, ContractReview.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if rv:
                context["contract_amount"] = _safe_float(rv.contract_amount)
                context["is_export"] = rv.is_export
                context["need_install"] = rv.need_install
                context["need_pricing"] = rv.need_pricing
                context["department_id"] = rv.department_id
                context["department_name"] = rv.department_name
                context["owner_id"] = rv.owner_id
                context["customer_type"] = rv.customer_type
                context["payment_term"] = rv.payment_term
                context["review_type"] = rv.review_type
                context["region_manager_id"] = rv.region_manager_id
                rj = rv.review_json if isinstance(rv.review_json, dict) else {}
                context["industry"] = rj.get("industry")
                # 简道云财务意见后分支：合同评审 + 是否反馈=否 → 产采质
                context["need_feedback"] = rj.get("need_feedback") or getattr(rv, "need_feedback", None)
                for risk_key in (
                    "legal_risk", "tech_risk", "biz_risk",
                    "finance_risk", "purchase_risk", "export_risk",
                ):
                    context[risk_key] = rj.get(risk_key)
        elif biz_type == "tech_agreement_review":
            from app.domains.tech_agreement_review.models import TechAgreementReview
            rv = (await db.execute(
                select(TechAgreementReview).where(
                    TechAgreementReview.id == biz_id, TechAgreementReview.tenant_id == tenant_id,
                )
            )).scalar_one_or_none()
            if rv:
                context["owner_id"] = rv.owner_id
                context["applicant_id"] = rv.applicant_id
                context["department_id"] = rv.department_id
                context["department_name"] = rv.department_name
                context["need_pricing"] = rv.need_pricing
                context["has_smart"] = rv.has_smart
                context["has_objection"] = rv.has_objection
                fj = rv.form_json if isinstance(rv.form_json, dict) else {}
                context["design_approver_ids"] = fj.get("design_approver_ids")
                context["design_approver_2_ids"] = fj.get("design_approver_2_ids")
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
                # 可视化流程「表单人员/部门字段」抄送、条件分支用
                context["owner_id"] = ld.owner_id
                context["reporter_id"] = ld.reporter_id
                context["created_by_id"] = ld.created_by_id
                context["department_id"] = ld.department_id
        elif biz_type == "customer":
            from app.domains.customer.models import Customer
            cu = (await db.execute(
                select(Customer).where(Customer.id == biz_id, Customer.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if cu:
                context["owner_id"] = cu.owner_id
                context["department_id"] = cu.department_id
                context["is_foreign_trade"] = cu.is_foreign_trade
                context["need_info_distribute"] = getattr(cu, "need_info_distribute", None)
                context["is_smart_filing"] = cu.is_smart_filing
                context["industry"] = cu.industry
                context["level"] = cu.level
                context["source"] = cu.source
        # solution: no condition fields — always matches (approver-only policy)
    except Exception as e:
        logger.warning("Build policy context failed for %s/%s: %s", biz_type, biz_id, e)
    return context


async def _resolve_policy_approvers(
    db: AsyncSession, tenant_id: str, biz_type: str, biz_id: str,
    submitter_id: str | None = None,
) -> tuple[list[str], list[str], str] | None:
    """Try to resolve approvers from approval_policies table. Returns (ids, names, mode) or None.

    submitter_id: 提交人。解析结果会尽量把提交人排除，避免「自己审自己」；但若排除后
    一个审批人都不剩，则保留提交人——否则单据会永远卡在待审批（宁可自审也不死锁）。
    """
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
        want_dept_leader = False
        for rule in rules:
            rule_type = rule.get("type", "")
            rule_value = rule.get("value", "")
            if rule_type == "role" and rule_value:
                role_codes.append(rule_value)
            elif rule_type == "user" and rule_value:
                user_ids.append(rule_value)
            elif rule_type == "department_leader":
                # 前端「部门领导」选项提交的是无 value 的 {type:'department_leader'}，
                # 历史上后端不认这个类型 → 解析为空 → 管理员以为配置生效了其实没有。
                want_dept_leader = True

        # 部门领导：取提交人所在各部门的负责人
        if want_dept_leader and submitter_id:
            from app.domains.organization.models import Department, UserDepartment
            leader_rows = (await db.execute(
                select(Department.leader_id)
                .join(UserDepartment, UserDepartment.department_id == Department.id)
                .where(
                    Department.tenant_id == tenant_id,
                    UserDepartment.tenant_id == tenant_id,
                    UserDepartment.user_id == submitter_id,
                    Department.leader_id.isnot(None),
                )
            )).scalars().all()
            user_ids.extend([lid for lid in leader_rows if lid])

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

        # Single query for all user-based approvers（含部门领导；同样过滤停用账号，
        # 否则离职/停用的人会被派单，审批永远无人处理）
        if user_ids:
            direct_users = (await db.execute(
                select(User).where(
                    User.id.in_(user_ids), User.tenant_id == tenant_id,
                    User.is_active == True,  # noqa: E712
                )
            )).scalars().all()
            for u in direct_users:
                if u.id not in approver_ids:
                    approver_ids.append(u.id)
                    approver_names.append(u.real_name or u.username)

        # 排除提交人（避免自己审自己）；排除后为空则保留，避免单据永久卡住
        if submitter_id and submitter_id in approver_ids:
            kept = [(i, n) for i, n in zip(approver_ids, approver_names) if i != submitter_id]
            if kept:
                approver_ids = [i for i, _ in kept]
                approver_names = [n for _, n in kept]

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
            link=f"/approvals?flow={flow.id}", mobile_link=f"/m/approvals/{flow.id}",
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
        resolved = await _resolve_policy_approvers(db, tenant_id, data.biz_type, data.biz_id, user.get("sub"))
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

    # Notifications（站内同步；群消息/钉钉待办后台发，避免拖慢提交）
    if mode == "sequential":
        await send_notification(
            db, tenant_id, data.assignee_ids[0],
            type="approval_pending",
            title=f"您有新的审批待处理: {data.title or data.biz_type}",
            content=f"{flow.submitted_by_name} 提交了审批请求",
            biz_type="approval_flow", biz_id=flow.id,
            sender_name=flow.submitted_by_name,
        )
    else:
        for i, aid in enumerate(data.assignee_ids):
            await send_notification(
                db, tenant_id, aid,
                type="approval_pending",
                title=f"您有新的审批待处理: {data.title or data.biz_type}",
                content=f"{flow.submitted_by_name} 提交了审批请求（{mode}模式）",
                biz_type="approval_flow", biz_id=flow.id,
                sender_name=flow.submitted_by_name,
            )

    import asyncio
    flow_id = flow.id
    title_for_msg = data.title or data.biz_type
    mode_for_msg = mode
    biz_for_msg = data.biz_type
    names0 = names[0] if names else (data.assignee_ids[0] if data.assignee_ids else "")

    async def _bg_external():
        from app.database import async_session_factory
        try:
            async with async_session_factory() as s:
                if mode_for_msg == "sequential":
                    await _dispatch_msg_safe(
                        s, tenant_id, "审批待处理通知",
                        f"**审批人**: {names0}\n\n**业务类型**: {biz_for_msg}\n\n"
                        f"**审批对象**: {title_for_msg}\n\n请尽快登录系统处理审批。",
                    )
                else:
                    await _dispatch_msg_safe(
                        s, tenant_id, "审批待处理通知",
                        f"**审批模式**: {mode_for_msg}\n\n**业务类型**: {biz_for_msg}\n\n"
                        f"**审批对象**: {title_for_msg}\n\n请相关审批人尽快处理。",
                    )
                fl = (await s.execute(
                    select(ApprovalFlow).where(ApprovalFlow.id == flow_id, ApprovalFlow.tenant_id == tenant_id)
                )).scalar_one_or_none()
                if not fl:
                    return
                for t in await get_flow_tasks(s, tenant_id, flow_id):
                    if t.status == "pending":
                        await _create_todo_for_task(s, tenant_id, fl, t)
        except Exception as e:
            logger.warning("background approval notify failed: %s", e)

    try:
        asyncio.get_running_loop().create_task(_bg_external())
    except RuntimeError:
        await _bg_external()

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
        # 任一：第一个做出决定的人（通过或驳回）即为最终结果，其余审批人的待办立即作废。
        # （原逻辑要求「全部驳回」才算驳回，导致一人驳回后其他人待办仍在，不符合「任一」直觉。）
        flow.status = "approved" if action == "approved" else "rejected"
        all_tasks = await get_flow_tasks(db, tenant_id, flow.id)
        for t in all_tasks:
            if t.id != task.id and t.status == "pending":
                t.status = "cancelled"

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
                # 旧引擎路径：推送给申报人（业务员）
                recipient = ld.reporter_id or ld.owner_id
                if recipient and ld.status not in ("qualified", "discarded"):
                    try:
                        from app.common.auto_notify import notify_lead_review_approved
                        await notify_lead_review_approved(
                            db, tenant_id,
                            lead_id=ld.id, lead_title=ld.title or "线索",
                            owner_id=recipient, lead_code=ld.lead_code,
                        )
                    except Exception as ne:
                        logger.warning("lead reporter notify on legacy approve failed: %s", ne)
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

    tasks = await get_flow_tasks(db, tenant_id, flow.id)
    if any(t.status == "approved" for t in tasks):
        raise BusinessException(code=BUSINESS_ERROR, message="下一节点已审批，无法撤回")

    flow.status = "withdrawn"

    # Cancel all pending/waiting tasks
    current_assignees = []
    for t in tasks:
        if t.status in ("pending", "waiting"):
            if t.status == "pending":
                current_assignees.append(t.assignee_id)
            t.status = "cancelled"

    # 业务单据回写可再编辑状态（与低代码撤回一致）
    try:
        from app.domains.lowcode.wf_biz_writeback import writeback
        if flow.biz_type and flow.biz_id:
            await writeback(db, tenant_id, flow.biz_type, flow.biz_id, "withdrawn")
    except Exception as e:
        logger.warning("legacy withdraw writeback failed: %s", e)

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
    """Resubmit a rejected/withdrawn approval flow, creating a new flow linked to the original."""
    original = await get_flow(db, tenant_id, flow_id)
    if original.status not in ("rejected", "withdrawn"):
        raise BusinessException(code=BUSINESS_ERROR, message="只能重新提交已驳回或已撤回的审批流")
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
    resolved = await _resolve_policy_approvers(db, tenant_id, biz_type, biz_id, user.get("sub"))
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


async def get_statistics(db: AsyncSession, tenant_id: str, date_from: str | None = None, date_to: str | None = None, user: dict | None = None) -> dict:
    """Get approval statistics for the tenant using SQL aggregation.

    传入 user 且其无 approval:manage 时，只统计与本人相关的审批——
    否则 工作台「审批SLA概览」会把全公司审批量、通过率和审批人排行摊给每个销售看。
    """
    from sqlalchemy import extract, case

    # Build shared WHERE conditions
    conditions = [ApprovalFlow.tenant_id == tenant_id]
    if user is not None and not _can_see_all_flows(user):
        conditions.append(_involved_clause(user))
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
    # 注意这里查的是 ApprovalTask，不受上面 conditions 约束，需要单独限范围，
    # 否则「审批人排行」会把全公司同事的审批次数列给普通销售看。
    task_conditions = [
        ApprovalTask.tenant_id == tenant_id,
        ApprovalTask.status.in_(["approved", "rejected"]),
    ]
    if user is not None and not _can_see_all_flows(user):
        task_conditions.append(
            ApprovalTask.flow_id.in_(
                select(ApprovalFlow.id).where(
                    ApprovalFlow.tenant_id == tenant_id, _involved_clause(user)
                )
            )
        )
    task_base = select(
        ApprovalTask.assignee_name,
        func.count(ApprovalTask.id).label("cnt"),
    ).where(*task_conditions).group_by(ApprovalTask.assignee_name).order_by(func.count(ApprovalTask.id).desc()).limit(10)
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
                def _put(label: str, val) -> None:
                    if val is None or val == "":
                        return
                    detail[label] = val

                _put("版本号", ver.version_no)
                _put("风险等级", ver.risk_level)
                c = (await db.execute(select(Contract).where(Contract.id == ver.contract_id, Contract.tenant_id == tenant_id))).scalar_one_or_none()
                if c:
                    _put("合同编号", c.contract_no)
                    _put(
                        "合同金额",
                        f"¥{float(c.amount_total):,.2f}" if c.amount_total is not None else None,
                    )
                    change_labels = {"new": "新签", "change": "变更", "renew": "续签"}
                    _put("变更类型", change_labels.get(c.change_type or "", c.change_type))
                    _put("所属部门", c.department_name)
                    reg = c.registration_json if isinstance(c.registration_json, dict) else {}
                    _put("行业", reg.get("industry"))
                    _put("是否出口", reg.get("is_export"))
                    _put("是否标准交付", reg.get("standard_delivery"))
                    _put("交付方式", reg.get("delivery_mode"))
                    _put("是否旋振筛", reg.get("is_rotary_sieve"))

        elif biz_type == "contract_review":
            from app.domains.contract_review.models import ContractReview
            from app.domains.contract_review.service import _hydrate_display_names
            rv = (await db.execute(
                select(ContractReview).where(ContractReview.id == biz_id, ContractReview.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if rv:
                await _hydrate_display_names(db, tenant_id, [rv])

                def _put(label: str, val) -> None:
                    if val is None:
                        return
                    s = str(val).strip() if not isinstance(val, (int, float)) else str(val)
                    if s == "" or s == "None":
                        return
                    detail[label] = s if not isinstance(val, (int, float)) else val

                status_labels = {
                    "draft": "草稿", "submitted": "已提交",
                    "approved": "已通过", "rejected": "已驳回",
                }
                _put("评审编号", rv.review_code)
                _put("评审类型", rv.review_type)
                _put("公司名称", rv.company_name)
                _put("项目名称", rv.project_title)
                _put("业务员", rv.owner_name)
                _put("业务部门", rv.department_name)
                _put("区域经理", rv.region_manager_name)
                _put("是否出口合同", rv.is_export)
                _put("是否核价", rv.need_pricing)
                _put("是否需要安装", rv.need_install)
                _put("客户类型", rv.customer_type)
                _put("电控装置", rv.elec_ctrl)
                _put(
                    "合同价格",
                    f"¥{float(rv.contract_amount):,.2f}" if rv.contract_amount is not None else None,
                )
                _put("账期", rv.payment_term)
                _put("状态", status_labels.get(rv.status or "", rv.status))
        elif biz_type == "tech_agreement_review":
            from app.domains.auth.models import User
            from app.domains.tech_agreement_review.models import TechAgreementReview
            from app.domains.tech_agreement_review.service import _hydrate_display_names
            rv = (await db.execute(
                select(TechAgreementReview).where(
                    TechAgreementReview.id == biz_id, TechAgreementReview.tenant_id == tenant_id,
                )
            )).scalar_one_or_none()
            if rv:
                await _hydrate_display_names(db, tenant_id, [rv])

                def _put(label: str, val) -> None:
                    if val is None:
                        return
                    s = str(val).strip() if not isinstance(val, (int, float)) else str(val)
                    if s == "" or s == "None":
                        return
                    detail[label] = s if not isinstance(val, (int, float)) else val

                async def _person_labels(raw) -> str | None:
                    ids: list[str] = []
                    if isinstance(raw, str) and raw.strip():
                        ids = [raw.strip()]
                    elif isinstance(raw, (list, tuple)):
                        ids = [str(x).strip() for x in raw if x]
                    if not ids:
                        return None
                    rows = (await db.execute(
                        select(User).where(User.tenant_id == tenant_id, User.id.in_(ids))
                    )).scalars().all()
                    by_id = {
                        u.id: (u.real_name or u.username or "").strip() or u.id
                        for u in rows
                    }
                    return "、".join(by_id.get(i, i) for i in ids) or None

                status_labels = {
                    "draft": "草稿", "submitted": "已提交",
                    "approved": "已通过", "rejected": "已驳回",
                }
                fj = rv.form_json if isinstance(rv.form_json, dict) else {}
                _put("流水号", rv.review_code)
                if rv.apply_at is not None:
                    try:
                        _put("日期时间", rv.apply_at.strftime("%Y-%m-%d %H:%M"))
                    except Exception:
                        _put("日期时间", str(rv.apply_at))
                _put("申请人", rv.applicant_name)
                _put("业务员", rv.owner_name)
                _put("业务部门", rv.department_name)
                _put("公司名称", rv.company_name)
                _put("所属行业", rv.industry)
                _put("地址", rv.address)
                _put("电控装置", rv.elec_ctrl)
                _put("项目名称及应用", rv.project_title)
                _put("是否有重量要求", rv.has_weight_req)
                _put("是否趁用呆滞设备", rv.use_idle_equip)
                _put("合同是否含智能化部分", rv.has_smart)
                _put("是否核价", rv.need_pricing)
                _put("合同签订依据及情况", rv.sign_basis)
                _put("参考合同号", rv.ref_contract_no)
                _put("前期沟通人", rv.pre_contact)
                _put("备注", rv.remark)
                _put("设计审批", await _person_labels(fj.get("design_approver_ids")))
                _put("设计审批2", await _person_labels(fj.get("design_approver_2_ids")))
                _put("是否有异议", rv.has_objection)
                _put("状态", status_labels.get(rv.status or "", rv.status))
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
            # 线索审核已切到扩展平台工作流：审批抽屉无自定义表单，必须靠 biz_detail
            # 把「申报信息（创建时填写）」铺全，并翻译字典码为中文标签。
            from app.domains.lead.models import Lead
            ld = (await db.execute(
                select(Lead).where(Lead.id == biz_id, Lead.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if ld:
                def _put(label: str, val) -> None:
                    if val is None:
                        return
                    s = str(val).strip() if not isinstance(val, (int, float)) else str(val)
                    if s == "" or s == "None":
                        return
                    detail[label] = s if not isinstance(val, (int, float)) else val

                async def _dict_label(dict_type: str, code: str | None) -> str | None:
                    if not code:
                        return None
                    try:
                        from app.domains.admin.models import DataDictionary
                        lab = (await db.execute(
                            select(DataDictionary.dict_label).where(
                                DataDictionary.tenant_id == tenant_id,
                                DataDictionary.dict_type == dict_type,
                                DataDictionary.dict_code == code,
                                DataDictionary.is_deleted == False,  # noqa: E712
                            ).limit(1)
                        )).scalar_one_or_none()
                        return lab or code
                    except Exception:
                        return code

                cat_labels = {"self_reported": "自报", "distributed": "分发"}
                country_labels = {"domestic": "国内", "overseas": "国外"}

                _put("项目编号", ld.lead_code)
                _put("来源", cat_labels.get(ld.category or "", ld.category))
                _put("项目名称", ld.title)
                _put("公司名称", ld.company_name)
                _put("客户类型", await _dict_label("customer_type", ld.customer_type))

                if ld.country_type == "overseas":
                    _put(
                        "国别",
                        f"{country_labels['overseas']}"
                        + (f" · {ld.country_name}" if ld.country_name else ""),
                    )
                    _put("国家", ld.country_name)
                elif ld.country_type:
                    _put("国别", country_labels.get(ld.country_type, ld.country_type))

                loc = " / ".join([p for p in (ld.province, ld.city, ld.district) if p])
                _put("项目地址（省市区）", loc or None)
                _put("详细地址", ld.region)
                _put("是否内部冲突", getattr(ld, "has_internal_conflict", None))
                _put("备注：请示部门经理的结果", getattr(ld, "conflict_note", None))
                _put("行业", await _dict_label("industry", ld.industry))
                _put("中标情况", getattr(ld, "bid_result", None))
                _put("原因", getattr(ld, "bid_fail_reason", None))
                _put("委托状态", getattr(ld, "entrust_status", None))
                if getattr(ld, "entrust_issued_at", None):
                    _put(
                        "委托开具日期",
                        ld.entrust_issued_at.isoformat(sep=" ", timespec="minutes"),
                    )
                _put("委托期限", getattr(ld, "entrust_term", None))

                _put("填表人", ld.created_by_name)
                if ld.department_id:
                    from app.domains.organization.models import Department
                    dept = (await db.execute(
                        select(Department.name).where(
                            Department.id == ld.department_id, Department.tenant_id == tenant_id,
                        )
                    )).scalar_one_or_none()
                    _put("部门", dept)
                _put("申报人", ld.reporter_name)
                if ld.reported_at:
                    _put("申报时间", ld.reported_at.isoformat(sep=" ", timespec="minutes"))
                _put("负责人", ld.owner_name)
                _put("项目动态", getattr(ld, "project_activity", None))
                _put("备注1（线索内容）", ld.demand_summary)

                # 业务反馈（若有）
                _put("项目近况", getattr(ld, "project_recent", None))
                _put("跟进进度", getattr(ld, "follow_progress", None))
                _put("实地拜访情况", getattr(ld, "site_visit", None))
                _put("项目状态", getattr(ld, "report_project_status", None))

                # 联系人等扩展
                _put("联系人", ld.contact_name)
                _put("联系电话", ld.contact_phone)
                _put("联系邮箱", ld.contact_email)
                src_lab = await _dict_label("lead_source", ld.source)
                _put("线索来源", src_lab if ld.source else None)
                if ld.biz_date:
                    _put("业务日期", str(ld.biz_date))
                _put("备注", ld.remark)

                # 已有评估信息（审批侧只读回显；裁定仍用情报表单）
                if getattr(ld, "customer_newness", None) == "new":
                    _put("新/老客户", "新")
                elif getattr(ld, "customer_newness", None) == "old":
                    _put("新/老客户", "老")
                rev_labels = {
                    "pending": "待审", "approved": "收录",
                    "rejected": "回退", "attacked": "袭击",
                }
                rs = getattr(ld, "review_status", None)
                if rs:
                    _put("项目最终状态", rev_labels.get(rs, rs))
                _put("回退原因", getattr(ld, "reject_reason", None))
                _put("备注2", getattr(ld, "assess_remark", None))
                _put("操作意见", getattr(ld, "review_opinion", None))
                _put("评分", ld.score)

                cf = ld.custom_fields_json if isinstance(ld.custom_fields_json, dict) else None
                if cf:
                    label_map: dict[str, str] = {}
                    try:
                        from app.domains.admin.models import CustomFieldDef
                        rows = (await db.execute(
                            select(CustomFieldDef.field_key, CustomFieldDef.field_label).where(
                                CustomFieldDef.tenant_id == tenant_id,
                                CustomFieldDef.entity_type == "lead",
                            )
                        )).all()
                        label_map = {k: (lab or k) for k, lab in rows}
                    except Exception:
                        try:
                            from app.domains.lowcode.service import get_entity_fields
                            for fd in await get_entity_fields(db, tenant_id, "lead"):
                                fid = fd.get("id") or fd.get("field_key")
                                if fid:
                                    label_map[fid] = fd.get("label") or fd.get("title") or fid
                        except Exception:
                            label_map = {}
                    for k, v in cf.items():
                        if v is None or v == "" or v == []:
                            continue
                        if isinstance(v, (list, dict)):
                            import json as _json
                            try:
                                v = _json.dumps(v, ensure_ascii=False)
                            except Exception:
                                v = str(v)
                        _put(label_map.get(k, k), v)
        elif biz_type == "customer":
            # 客户信息审批：无自定义表单，靠 biz_detail 铺申报字段供审批人审阅。
            from app.domains.customer.models import Customer
            cu = (await db.execute(
                select(Customer).where(Customer.id == biz_id, Customer.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if cu:
                def _put(label: str, val) -> None:
                    if val is None:
                        return
                    if isinstance(val, bool):
                        detail[label] = "是" if val else "否"
                        return
                    s = str(val).strip() if not isinstance(val, (int, float)) else str(val)
                    if s == "" or s == "None":
                        return
                    detail[label] = s if not isinstance(val, (int, float)) else val

                async def _dict_label(dict_type: str, code: str | None) -> str | None:
                    if not code:
                        return None
                    try:
                        from app.domains.admin.models import DataDictionary
                        lab = (await db.execute(
                            select(DataDictionary.dict_label).where(
                                DataDictionary.tenant_id == tenant_id,
                                DataDictionary.dict_type == dict_type,
                                DataDictionary.dict_code == code,
                                DataDictionary.is_deleted == False,  # noqa: E712
                            ).limit(1)
                        )).scalar_one_or_none()
                        return lab or code
                    except Exception:
                        return code

                def _yn(v) -> str | None:
                    if v is True:
                        return "是"
                    if v is False:
                        return "否"
                    return None

                rev_labels = {
                    "draft": "草稿", "pending": "审批中",
                    "approved": "已通过", "rejected": "已驳回",
                }

                _put("客户编号", cu.customer_code)
                _put("客户名称", cu.name)
                _put("客户简称", cu.short_name)
                _put("是否智能化客户信息备案", _yn(getattr(cu, "is_smart_filing", None)))
                _put("是否外贸客户", _yn(getattr(cu, "is_foreign_trade", None)))
                _put("信息分发-客户", _yn(getattr(cu, "need_info_distribute", None)))
                _put("所属行业", await _dict_label("industry", cu.industry))
                _put("客户类型", cu.level)
                _put("客户性质", getattr(cu, "customer_nature", None))
                _put("客户关系", getattr(cu, "customer_relation", None))
                _put("主联系人职位", getattr(cu, "primary_contact_title", None))
                _put("客户工资及保险情况", getattr(cu, "wage_insurance_status", None))
                if getattr(cu, "registered_capital", None) is not None:
                    _put("注册资金（万元）", float(cu.registered_capital))
                if getattr(cu, "paid_in_capital", None) is not None:
                    _put("实缴资本（万元）", float(cu.paid_in_capital))
                _put("成立年份", getattr(cu, "founded_year", None))
                _put("母公司或者控股公司情况及性质说明", getattr(cu, "parent_company_note", None))
                loc = " / ".join([p for p in (cu.province, cu.city, cu.district) if p])
                _put("省市区", loc or None)
                _put("详细地址", cu.address)
                _put("国家/地区", cu.region)
                _put("国别", getattr(cu, "country", None))
                _put("客户代码", getattr(cu, "foreign_customer_code", None))
                _put("外贸客户类型", getattr(cu, "foreign_customer_type", None))
                _put("关注产品", getattr(cu, "focus_product", None))
                _put("邮箱", getattr(cu, "customer_email", None))
                _put("主页", cu.website)
                mp = getattr(cu, "main_products_json", None)
                if isinstance(mp, list) and mp:
                    _put("主营产品", "、".join(str(x) for x in mp if x))
                src_lab = await _dict_label("customer_source", cu.source)
                _put("客户来源", src_lab if cu.source else None)
                _put("业务员", cu.owner_name)
                _put("业务部门", getattr(cu, "department_name", None))
                _put("录入人", cu.created_by_name)
                _put("企业法人", getattr(cu, "legal_person", None))
                _put("企业员工人数", getattr(cu, "headcount", None))
                _put("所属行业分类", getattr(cu, "smart_industry_category", None))
                _put("年运行天数", getattr(cu, "annual_run_days", None))
                _put("占地面积", getattr(cu, "floor_area", None))
                _put("企业财务状况", getattr(cu, "financial_status", None))
                _put("企业经营状况", getattr(cu, "business_status", None))
                _put("年用电量", getattr(cu, "annual_power_usage", None))
                _put("日运营小时数", getattr(cu, "daily_operate_hours", None))
                _put("是否公司客户", _yn(getattr(cu, "is_company_customer", None)))
                _put("纳税人识别号", getattr(cu, "taxpayer_id", None))
                _put("地址电话", getattr(cu, "invoice_address_phone", None))
                _put("开户行帐号", getattr(cu, "bank_account", None))
                if getattr(cu, "budget_amount", None) is not None:
                    _put("客户预算(元)", f"¥{float(cu.budget_amount):,.2f}")
                if getattr(cu, "expected_purchase_date", None):
                    _put("预计采购时间", str(cu.expected_purchase_date))
                _put("核心需求", getattr(cu, "demand", None))
                _put("备注", cu.remark)
                rs = getattr(cu, "review_status", None)
                if rs:
                    _put("审核状态", rev_labels.get(rs, rs))
                _put("驳回原因", getattr(cu, "reject_reason", None))

                cf = cu.custom_fields_json if isinstance(cu.custom_fields_json, dict) else None
                if cf:
                    label_map: dict[str, str] = {}
                    try:
                        from app.domains.admin.models import CustomFieldDef
                        rows = (await db.execute(
                            select(CustomFieldDef.field_key, CustomFieldDef.field_label).where(
                                CustomFieldDef.tenant_id == tenant_id,
                                CustomFieldDef.entity_type == "customer",
                            )
                        )).all()
                        label_map = {k: (lab or k) for k, lab in rows}
                    except Exception:
                        try:
                            from app.domains.lowcode.service import get_entity_fields
                            for fd in await get_entity_fields(db, tenant_id, "customer"):
                                fid = fd.get("id") or fd.get("field_key")
                                if fid:
                                    label_map[fid] = fd.get("label") or fd.get("title") or fid
                        except Exception:
                            label_map = {}
                    for k, v in cf.items():
                        if v is None or v == "" or v == []:
                            continue
                        if isinstance(v, (list, dict)):
                            import json as _json
                            try:
                                v = _json.dumps(v, ensure_ascii=False)
                            except Exception:
                                v = str(v)
                        _put(label_map.get(k, k), v)
    except Exception as e:
        logger.warning("Failed to resolve biz detail for %s/%s: %s", biz_type, biz_id, e)
    return detail


async def list_my_pending(db: AsyncSession, tenant_id: str, user_id: str, limit: int = 100):
    """List pending approval tasks assigned to a user."""
    result = await db.execute(
        select(ApprovalTask, ApprovalFlow).join(
            ApprovalFlow, ApprovalTask.flow_id == ApprovalFlow.id
        ).where(
            ApprovalTask.tenant_id == tenant_id,
            ApprovalTask.assignee_id == user_id,
            ApprovalTask.status == "pending",
            ApprovalFlow.status == "pending",
        ).order_by(ApprovalTask.created_at.desc()).limit(limit)
    )
    return result.all()


async def list_my_done_tasks(db: AsyncSession, tenant_id: str, user_id: str, limit: int = 50):
    """我已处理过的旧引擎任务（通过/驳回/转交），供统一已办聚合。"""
    result = await db.execute(
        select(ApprovalTask, ApprovalFlow).join(
            ApprovalFlow, ApprovalTask.flow_id == ApprovalFlow.id
        ).where(
            ApprovalTask.tenant_id == tenant_id,
            ApprovalTask.assignee_id == user_id,
            ApprovalTask.status.in_(("approved", "rejected", "transferred")),
        ).order_by(ApprovalTask.decided_at.desc(), ApprovalTask.created_at.desc()).limit(limit)
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
