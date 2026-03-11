import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND, BUSINESS_ERROR
from app.domains.project.models import OpportunityProject, ProjectStageHistory
from app.domains.project.schemas import ProjectCreate, ProjectUpdate
from app.domains.audit.service import log_action

logger = logging.getLogger("spt_crm.project")

STAGE_ORDER = ["S1", "S2", "S3", "S4", "S5", "S6"]

# ==================== Stage Gate Rule Definitions ====================
# Each stage defines rules that must pass before entering that stage.
# Rules check for presence of data/attachments/related entities.

GATE_RULES: dict[str, list[dict]] = {
    "S2": [
        {"code": "HAS_CUSTOMER", "name": "已关联客户", "check": "field_required", "field": "customer_id",
         "message": "请先关联客户，再进入需求分析阶段。", "fix_action": "link_customer"},
    ],
    "S3": [
        {"code": "HAS_REQUIREMENTS", "name": "需求已填写", "check": "json_not_empty", "field": "key_requirements_json",
         "message": "请先填写关键需求信息。", "fix_action": "edit_project"},
    ],
    "S4": [
        {"code": "HAS_SOLUTION", "name": "已有方案", "check": "has_related", "entity": "solution",
         "message": "请先创建至少一个方案，再进入商务谈判。", "fix_action": "create_solution"},
        {"code": "HAS_APPROVED_SOLUTION", "name": "方案已审批", "check": "has_approved_solution",
         "message": "请确保至少一个方案已通过审批。", "fix_action": "approve_solution"},
        {"code": "HAS_QUOTE", "name": "已有报价", "check": "has_related", "entity": "quote",
         "message": "请先创建至少一个报价。", "fix_action": "create_quote"},
    ],
    "S5": [
        {"code": "HAS_QUOTE", "name": "已有报价", "check": "has_related", "entity": "quote",
         "message": "请先创建报价，再进入合同签订阶段。", "fix_action": "create_quote"},
        {"code": "HAS_ATTACHMENT", "name": "已上传附件", "check": "has_attachment",
         "message": "请上传至少一个项目附件（如技术规格书或报价确认函）。", "fix_action": "upload_attachment"},
    ],
    "S6": [
        {"code": "HAS_CONTRACT", "name": "已有合同", "check": "has_related", "entity": "contract",
         "message": "请先创建合同，再进入交付验收阶段。", "fix_action": "create_contract"},
        {"code": "MIN_AMOUNT", "name": "金额已确认", "check": "min_amount", "min_value": 0,
         "message": "请确认预期金额大于零。", "fix_action": "edit_project"},
    ],
}


async def _load_gate_rules_from_db(db: AsyncSession, tenant_id: str, to_stage: str) -> list[dict] | None:
    """Try to load gate rules from StageDefinition table. Returns None if not configured."""
    try:
        from app.domains.admin.models import StageDefinition
        sd = (await db.execute(
            select(StageDefinition).where(
                StageDefinition.tenant_id == tenant_id,
                StageDefinition.stage_code == to_stage,
                StageDefinition.enabled == True,
            )
        )).scalar_one_or_none()
        if sd and sd.gate_rules_json:
            return sd.gate_rules_json if isinstance(sd.gate_rules_json, list) else None
    except Exception as e:
        logger.warning("Failed to load gate rules from DB for stage %s: %s", to_stage, e)
    return None


async def _load_allowed_transitions_from_db(db: AsyncSession, tenant_id: str, from_stage: str) -> list[str] | None:
    """Try to load allowed transitions from StageDefinition table. Returns None if not configured."""
    try:
        from app.domains.admin.models import StageDefinition
        sd = (await db.execute(
            select(StageDefinition).where(
                StageDefinition.tenant_id == tenant_id,
                StageDefinition.stage_code == from_stage,
                StageDefinition.enabled == True,
            )
        )).scalar_one_or_none()
        if sd and sd.allowed_transitions_json:
            return sd.allowed_transitions_json if isinstance(sd.allowed_transitions_json, list) else None
    except Exception as e:
        logger.warning("Failed to load allowed transitions from DB for stage %s: %s", from_stage, e)
    return None


async def check_gate_rules(db: AsyncSession, tenant_id: str, project: OpportunityProject, to_stage: str) -> list[dict]:
    """Check gate rules for a stage transition. Returns list of failed rules.
    First tries DB-configured rules, falls back to hardcoded GATE_RULES."""
    # Try DB-configured rules first
    db_rules = await _load_gate_rules_from_db(db, tenant_id, to_stage)
    rules = db_rules if db_rules is not None else GATE_RULES.get(to_stage, [])
    if not rules:
        return []

    failed = []
    for rule in rules:
        passed = True
        check_type = rule["check"]

        if check_type == "field_required":
            val = getattr(project, rule["field"], None)
            if not val:
                passed = False

        elif check_type == "json_not_empty":
            val = getattr(project, rule["field"], None)
            if not val or (isinstance(val, dict) and len(val) == 0):
                passed = False

        elif check_type == "has_related":
            entity = rule["entity"]
            count = 0
            if entity == "solution":
                from app.domains.solution.models import Solution
                count = (await db.execute(
                    select(func.count(Solution.id)).where(Solution.tenant_id == tenant_id, Solution.project_id == project.id)
                )).scalar() or 0
            elif entity == "quote":
                from app.domains.quote.models import Quote
                count = (await db.execute(
                    select(func.count(Quote.id)).where(Quote.tenant_id == tenant_id, Quote.project_id == project.id)
                )).scalar() or 0
            elif entity == "contract":
                from app.domains.contract.models import Contract
                count = (await db.execute(
                    select(func.count(Contract.id)).where(Contract.tenant_id == tenant_id, Contract.project_id == project.id)
                )).scalar() or 0
            if count == 0:
                passed = False

        elif check_type == "has_approved_solution":
            from app.domains.solution.models import Solution
            approved_count = (await db.execute(
                select(func.count(Solution.id)).where(
                    Solution.tenant_id == tenant_id,
                    Solution.project_id == project.id,
                    Solution.status == "approved",
                )
            )).scalar() or 0
            if approved_count == 0:
                passed = False

        elif check_type == "has_attachment":
            from app.domains.attachment.models import AttachmentLink
            att_count = (await db.execute(
                select(func.count(AttachmentLink.id)).where(
                    AttachmentLink.tenant_id == tenant_id,
                    AttachmentLink.biz_type == "project",
                    AttachmentLink.biz_id == project.id,
                )
            )).scalar() or 0
            if att_count == 0:
                passed = False

        elif check_type == "min_amount":
            min_val = rule.get("min_value", 0)
            amount = float(project.amount_expect or 0)
            if amount <= min_val:
                passed = False

        if not passed:
            item = {
                "code": rule["code"],
                "name": rule["name"],
                "message": rule["message"],
            }
            if rule.get("fix_action"):
                item["fix_action"] = rule["fix_action"]
            failed.append(item)

    return failed


def _generate_project_code() -> str:
    now = datetime.now(timezone.utc)
    import random
    seq = random.randint(1000, 9999)
    return f"PRJ-{now.strftime('%Y%m%d')}-{seq}"


async def _unique_project_code(db: AsyncSession, tenant_id: str) -> str:
    """Generate a unique project code with collision retry."""
    for _ in range(10):
        code = _generate_project_code()
        exists = (await db.execute(
            select(func.count(OpportunityProject.id)).where(
                OpportunityProject.tenant_id == tenant_id,
                OpportunityProject.project_code == code,
            )
        )).scalar()
        if not exists:
            return code
    return _generate_project_code()  # fallback


async def list_projects(
    db: AsyncSession, tenant_id: str, page_no: int = 1, page_size: int = 20,
    keyword: str | None = None, stage_code: str | None = None,
    customer_id: str | None = None, status: str | None = None,
    owner_id: str | None = None, current_user: dict | None = None,
):
    base = select(OpportunityProject).where(OpportunityProject.tenant_id == tenant_id, OpportunityProject.is_deleted == False)
    if keyword:
        base = base.where(
            OpportunityProject.name.ilike(f"%{keyword}%") | OpportunityProject.project_code.ilike(f"%{keyword}%")
        )
    if stage_code:
        base = base.where(OpportunityProject.stage_code == stage_code)
    if customer_id:
        base = base.where(OpportunityProject.customer_id == customer_id)
    if status:
        base = base.where(OpportunityProject.status == status)
    if owner_id:
        base = base.where(OpportunityProject.owner_id == owner_id)

    # Apply data scope (non-admin only sees owned/shared records)
    if current_user:
        from app.common.data_scope import apply_data_scope
        base = await apply_data_scope(base, db, tenant_id, current_user, OpportunityProject, "project")

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar()
    items = (await db.execute(
        base.order_by(OpportunityProject.created_at.desc()).offset((page_no - 1) * page_size).limit(page_size)
    )).scalars().all()
    return items, total


async def get_project(db: AsyncSession, tenant_id: str, project_id: str) -> OpportunityProject:
    p = (await db.execute(
        select(OpportunityProject).where(OpportunityProject.id == project_id, OpportunityProject.tenant_id == tenant_id, OpportunityProject.is_deleted == False)
    )).scalar_one_or_none()
    if not p:
        raise BusinessException(code=NOT_FOUND, message="商机项目不存在")
    return p


async def create_project(db: AsyncSession, tenant_id: str, data: ProjectCreate, user: dict) -> OpportunityProject:
    project = OpportunityProject(
        id=generate_uuid(), tenant_id=tenant_id,
        project_code=await _unique_project_code(db, tenant_id),
        owner_id=user["sub"], owner_name=user.get("real_name") or user.get("username"),
        **data.model_dump(),
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="project", resource_id=project.id,
                     summary=f"创建商机项目: {project.name}")
    return project


async def update_project(db: AsyncSession, tenant_id: str, project_id: str, data: ProjectUpdate, user: dict) -> OpportunityProject:
    project = await get_project(db, tenant_id, project_id)
    update_data = data.model_dump(exclude_unset=True)

    # Validate won/lost transition
    new_status = update_data.get("status")
    if new_status and new_status != project.status:
        if new_status == "won":
            from app.domains.contract.models import Contract
            contract_count = (await db.execute(
                select(func.count(Contract.id)).where(
                    Contract.tenant_id == tenant_id,
                    Contract.project_id == project_id,
                    Contract.status == "signed",
                )
            )).scalar() or 0
            if contract_count == 0:
                raise BusinessException(code=BUSINESS_ERROR, message="标记赢单前需至少有一份已签署的合同")

    changes = {}
    for field, val in update_data.items():
        old_val = getattr(project, field, None)
        if old_val != val:
            changes[field] = {"old": old_val if not hasattr(old_val, 'isoformat') else str(old_val), "new": val}
        setattr(project, field, val)
    await db.commit()
    await db.refresh(project)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="update", resource_type="project", resource_id=project.id,
                     summary=f"更新商机项目: {project.name}",
                     detail={"changes": changes} if changes else None)

    # Auto-activity & notification for win/lost status change
    if new_status and new_status in ("won", "lost"):
        try:
            from app.common.auto_activity import record_activity
            label = "赢单" if new_status == "won" else "丢单"
            await record_activity(db, tenant_id, "project", project.id, "system",
                                  f"商机已{label}", None,
                                  user["sub"], user.get("real_name") or user.get("username"))
        except Exception as e:
            logger.warning("Auto-activity record for project win/lost failed: %s", e)
        try:
            if project.owner_id and project.owner_id != user["sub"]:
                from app.common.auto_notify import notify_project_won_lost
                await notify_project_won_lost(db, tenant_id, project.name, new_status,
                                               project.owner_id, user.get("real_name") or user.get("username"), project.id)
        except Exception as e:
            logger.warning("Auto-notify project owner for win/lost failed: %s", e)

    return project


async def delete_project(db: AsyncSession, tenant_id: str, project_id: str, user: dict):
    project = await get_project(db, tenant_id, project_id)
    project_name = project.name

    # Soft delete
    project.is_deleted = True
    await db.commit()

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="delete", resource_type="project", resource_id=project_id,
                     summary=f"删除商机项目: {project_name}")


async def _check_pending_approvals(db: AsyncSession, tenant_id: str, project_id: str) -> list[dict]:
    """Check for pending/rejected approval flows on project's quotes and contracts."""
    from app.domains.approval.models import ApprovalFlow
    from app.domains.quote.models import Quote, QuoteVersion
    from app.domains.contract.models import Contract, ContractVersion

    blocked = []

    # Get quote version IDs for this project
    quote_ids = (await db.execute(
        select(Quote.id).where(Quote.tenant_id == tenant_id, Quote.project_id == project_id)
    )).scalars().all()
    if quote_ids:
        qv_ids = (await db.execute(
            select(QuoteVersion.id).where(QuoteVersion.tenant_id == tenant_id, QuoteVersion.quote_id.in_(quote_ids))
        )).scalars().all()
        if qv_ids:
            pending_flows = (await db.execute(
                select(ApprovalFlow).where(
                    ApprovalFlow.tenant_id == tenant_id,
                    ApprovalFlow.biz_type == "quote_version",
                    ApprovalFlow.biz_id.in_(qv_ids),
                    ApprovalFlow.status.in_(["pending", "rejected"]),
                )
            )).scalars().all()
            for f in pending_flows:
                blocked.append({"type": "quote", "flow_id": f.id, "title": f.title, "status": f.status})

    # Get contract version IDs for this project
    contract_ids = (await db.execute(
        select(Contract.id).where(Contract.tenant_id == tenant_id, Contract.project_id == project_id)
    )).scalars().all()
    if contract_ids:
        cv_ids = (await db.execute(
            select(ContractVersion.id).where(ContractVersion.tenant_id == tenant_id, ContractVersion.contract_id.in_(contract_ids))
        )).scalars().all()
        if cv_ids:
            pending_flows = (await db.execute(
                select(ApprovalFlow).where(
                    ApprovalFlow.tenant_id == tenant_id,
                    ApprovalFlow.biz_type == "contract_version",
                    ApprovalFlow.biz_id.in_(cv_ids),
                    ApprovalFlow.status.in_(["pending", "rejected"]),
                )
            )).scalars().all()
            for f in pending_flows:
                blocked.append({"type": "contract", "flow_id": f.id, "title": f.title, "status": f.status})

    return blocked


async def advance_stage(db: AsyncSession, tenant_id: str, project_id: str, to_stage: str, note: str | None, user: dict, force: bool = False) -> OpportunityProject:
    project = await get_project(db, tenant_id, project_id)
    from_stage = project.stage_code

    if to_stage not in STAGE_ORDER:
        raise BusinessException(code=BUSINESS_ERROR, message=f"无效的阶段: {to_stage}")
    from_idx = STAGE_ORDER.index(from_stage)
    to_idx = STAGE_ORDER.index(to_stage)
    if to_idx <= from_idx:
        raise BusinessException(code=BUSINESS_ERROR, message=f"只能向前推进阶段，当前 {from_stage}，目标 {to_stage}")

    # Check allowed transitions from DB config (if configured)
    if not force:
        allowed = await _load_allowed_transitions_from_db(db, tenant_id, from_stage)
        if allowed is not None and to_stage not in allowed:
            raise BusinessException(
                code=BUSINESS_ERROR,
                message=f"当前阶段 {from_stage} 不允许直接推进到 {to_stage}，允许的目标阶段: {', '.join(allowed)}",
            )

    # Gate check (skip if force=True)
    if not force:
        failed = await check_gate_rules(db, tenant_id, project, to_stage)
        if failed:
            raise BusinessException(code=42201, message="gate_check_failed", detail={"pass": False, "failed_rules": failed})

        # Approval check — block if pending/rejected approvals exist
        blocked_approvals = await _check_pending_approvals(db, tenant_id, project_id)
        if blocked_approvals:
            pending = [a for a in blocked_approvals if a["status"] == "pending"]
            rejected = [a for a in blocked_approvals if a["status"] == "rejected"]
            parts = []
            if pending:
                parts.append(f"{len(pending)} 个审批待处理")
            if rejected:
                parts.append(f"{len(rejected)} 个审批已驳回")
            raise BusinessException(
                code=42202,
                message=f"存在未完成的审批流程（{'，'.join(parts)}），请先处理后再推进阶段。",
                detail={"blocked_approvals": blocked_approvals},
            )

    project.stage_code = to_stage
    history = ProjectStageHistory(
        id=generate_uuid(), tenant_id=tenant_id,
        project_id=project_id, from_stage=from_stage, to_stage=to_stage,
        changed_by_id=user["sub"], changed_by_name=user.get("real_name") or user.get("username"),
        note=note,
    )
    db.add(history)
    await db.commit()
    await db.refresh(project)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="advance_stage", resource_type="project", resource_id=project_id,
                     summary=f"推进阶段: {from_stage} → {to_stage}")

    # Auto-notify project owner
    try:
        from app.common.auto_notify import notify_stage_advance
        if project.owner_id and project.owner_id != user["sub"]:
            await notify_stage_advance(db, tenant_id, project.name, from_stage, to_stage,
                                       project.owner_id, user.get("real_name") or user.get("username"))
    except Exception as e:
        logger.warning("Auto-notify stage advance failed: %s", e)

    # Auto-activity record
    try:
        from app.common.auto_activity import record_activity
        await record_activity(db, tenant_id, "project", project_id, "stage_change",
                               f"阶段推进: {from_stage} → {to_stage}", note,
                               user["sub"], user.get("real_name") or user.get("username"))
    except Exception as e:
        logger.warning("Auto-activity record for stage advance failed: %s", e)

    return project


async def rollback_stage(db: AsyncSession, tenant_id: str, project_id: str, to_stage: str, note: str | None, user: dict) -> OpportunityProject:
    project = await get_project(db, tenant_id, project_id)
    from_stage = project.stage_code

    if to_stage not in STAGE_ORDER:
        raise BusinessException(code=BUSINESS_ERROR, message=f"无效的阶段: {to_stage}")
    from_idx = STAGE_ORDER.index(from_stage)
    to_idx = STAGE_ORDER.index(to_stage)
    if to_idx >= from_idx:
        raise BusinessException(code=BUSINESS_ERROR, message=f"只能回退阶段，当前 {from_stage}，目标 {to_stage}")

    project.stage_code = to_stage
    history = ProjectStageHistory(
        id=generate_uuid(), tenant_id=tenant_id,
        project_id=project_id, from_stage=from_stage, to_stage=to_stage,
        changed_by_id=user["sub"], changed_by_name=user.get("real_name") or user.get("username"),
        note=note,
    )
    db.add(history)
    await db.commit()
    await db.refresh(project)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="rollback_stage", resource_type="project", resource_id=project_id,
                     summary=f"回退阶段: {from_stage} → {to_stage}")
    return project


async def calculate_health_score(db: AsyncSession, tenant_id: str, project_id: str) -> dict:
    """Calculate project health score (0-100) based on multiple dimensions."""
    project = await get_project(db, tenant_id, project_id)

    dimensions = {}
    reasons = []
    stage_idx = STAGE_ORDER.index(project.stage_code)

    # 1. Stall days (max 20 pts)
    days_since_update = (datetime.now(timezone.utc) - project.updated_at.replace(tzinfo=timezone.utc)).days if project.updated_at else 0
    if days_since_update <= 3:
        dimensions["stall"] = {"score": 20, "max": 20, "label": "活跃度", "detail": f"最近更新 {days_since_update} 天前"}
    elif days_since_update <= 7:
        dimensions["stall"] = {"score": 16, "max": 20, "label": "活跃度", "detail": f"{days_since_update} 天前更新"}
    elif days_since_update <= 14:
        dimensions["stall"] = {"score": 10, "max": 20, "label": "活跃度", "detail": f"停滞 {days_since_update} 天"}
        reasons.append(f"商机已停滞 {days_since_update} 天")
    elif days_since_update <= 30:
        dimensions["stall"] = {"score": 4, "max": 20, "label": "活跃度", "detail": f"停滞 {days_since_update} 天"}
        reasons.append(f"商机已停滞 {days_since_update} 天，建议尽快跟进")
    else:
        dimensions["stall"] = {"score": 0, "max": 20, "label": "活跃度", "detail": f"停滞 {days_since_update} 天"}
        reasons.append(f"商机已停滞 {days_since_update} 天，风险极高")

    # 2. Stage coverage — customer + requirements (max 15 pts)
    coverage_score = 0
    if project.customer_id:
        coverage_score += 7
    else:
        reasons.append("未关联客户")
    reqs = project.key_requirements_json
    has_reqs = (reqs and isinstance(reqs, (dict, list)) and len(reqs) > 0)
    if has_reqs:
        coverage_score += 8
    elif stage_idx >= 2:
        reasons.append("关键需求信息为空")
    else:
        coverage_score += 4  # early stage ok
    dimensions["coverage"] = {"score": coverage_score, "max": 15, "label": "阶段覆盖",
                               "detail": f"客户{'✓' if project.customer_id else '✗'} 需求{'✓' if has_reqs else '✗'}"}

    # 3. Quote versions (max 15 pts)
    from app.domains.quote.models import Quote, QuoteVersion
    quote_count = (await db.execute(
        select(func.count(Quote.id)).where(Quote.tenant_id == tenant_id, Quote.project_id == project_id)
    )).scalar() or 0
    if quote_count > 0:
        # Bonus for multiple versions
        total_versions = (await db.execute(
            select(func.count(QuoteVersion.id)).where(
                QuoteVersion.tenant_id == tenant_id,
                QuoteVersion.quote_id.in_(
                    select(Quote.id).where(Quote.tenant_id == tenant_id, Quote.project_id == project_id)
                ),
            )
        )).scalar() or 0
        q_score = 12 if total_versions == 1 else 15
        dimensions["quote"] = {"score": q_score, "max": 15, "label": "报价版本",
                                "detail": f"{quote_count} 份报价, {total_versions} 个版本"}
    else:
        q_score = 10 if stage_idx < 3 else 0
        dimensions["quote"] = {"score": q_score, "max": 15, "label": "报价版本",
                                "detail": "暂无报价"}
        if stage_idx >= 3:
            reasons.append("尚未创建报价")

    # 4. Close date risk (max 15 pts)
    if project.close_date_expect:
        close_str = str(project.close_date_expect)
        try:
            close_date = datetime.strptime(close_str[:10], "%Y-%m-%d")
            days_to_close = (close_date - datetime.now()).days
            if days_to_close > 30:
                dimensions["close_date"] = {"score": 15, "max": 15, "label": "成交节奏", "detail": f"距成交 {days_to_close} 天"}
            elif days_to_close > 7:
                dimensions["close_date"] = {"score": 10, "max": 15, "label": "成交节奏", "detail": f"距成交 {days_to_close} 天"}
            elif days_to_close > 0:
                dimensions["close_date"] = {"score": 5, "max": 15, "label": "成交节奏", "detail": f"仅剩 {days_to_close} 天"}
                reasons.append(f"距预期成交仅 {days_to_close} 天")
            else:
                dimensions["close_date"] = {"score": 0, "max": 15, "label": "成交节奏", "detail": f"已超期 {abs(days_to_close)} 天"}
                reasons.append(f"已超过预期成交日期 {abs(days_to_close)} 天")
        except (ValueError, TypeError):
            dimensions["close_date"] = {"score": 8, "max": 15, "label": "成交节奏", "detail": "日期格式异常"}
    else:
        dimensions["close_date"] = {"score": 5, "max": 15, "label": "成交节奏", "detail": "未设置预期成交日"}

    # 5. Payment risk (max 15 pts) — only relevant for S5+ stages
    if stage_idx >= 4:
        from app.domains.payment.models import PaymentPlan, PaymentRecord
        plan_total = (await db.execute(
            select(func.coalesce(func.sum(PaymentPlan.amount), 0)).where(
                PaymentPlan.tenant_id == tenant_id, PaymentPlan.project_id == project_id
            )
        )).scalar() or 0
        received_total = (await db.execute(
            select(func.coalesce(func.sum(PaymentRecord.amount), 0)).where(
                PaymentRecord.tenant_id == tenant_id, PaymentRecord.project_id == project_id
            )
        )).scalar() or 0
        plan_total = float(plan_total)
        received_total = float(received_total)
        if plan_total > 0:
            collection_rate = received_total / plan_total
            if collection_rate >= 0.8:
                dimensions["payment"] = {"score": 15, "max": 15, "label": "回款风险", "detail": f"回款率 {collection_rate:.0%}"}
            elif collection_rate >= 0.5:
                dimensions["payment"] = {"score": 10, "max": 15, "label": "回款风险", "detail": f"回款率 {collection_rate:.0%}"}
            elif collection_rate >= 0.2:
                dimensions["payment"] = {"score": 5, "max": 15, "label": "回款风险", "detail": f"回款率 {collection_rate:.0%}"}
                reasons.append(f"回款率仅 {collection_rate:.0%}")
            else:
                dimensions["payment"] = {"score": 2, "max": 15, "label": "回款风险", "detail": f"回款率 {collection_rate:.0%}"}
                reasons.append(f"回款率极低 ({collection_rate:.0%})")
        else:
            dimensions["payment"] = {"score": 8, "max": 15, "label": "回款风险", "detail": "暂无回款计划"}
    else:
        dimensions["payment"] = {"score": 15, "max": 15, "label": "回款风险", "detail": "尚未进入回款阶段"}

    # 6. Delivery reliability (max 10 pts) — only relevant for S5+ stages
    if stage_idx >= 4:
        from app.domains.delivery.models import DeliveryMilestone
        milestones = (await db.execute(
            select(DeliveryMilestone).where(
                DeliveryMilestone.tenant_id == tenant_id, DeliveryMilestone.project_id == project_id
            )
        )).scalars().all()
        if milestones:
            overdue = sum(1 for m in milestones if m.plan_date and m.actual_date and str(m.actual_date) > str(m.plan_date))
            if overdue == 0:
                dimensions["delivery"] = {"score": 10, "max": 10, "label": "交期可信度", "detail": f"{len(milestones)} 个里程碑, 无延期"}
            elif overdue <= len(milestones) * 0.3:
                dimensions["delivery"] = {"score": 7, "max": 10, "label": "交期可信度", "detail": f"{overdue}/{len(milestones)} 延期"}
            else:
                dimensions["delivery"] = {"score": 3, "max": 10, "label": "交期可信度", "detail": f"{overdue}/{len(milestones)} 延期"}
                reasons.append(f"交付里程碑 {overdue}/{len(milestones)} 延期")
        else:
            dimensions["delivery"] = {"score": 5, "max": 10, "label": "交期可信度", "detail": "暂无里程碑"}
    else:
        dimensions["delivery"] = {"score": 10, "max": 10, "label": "交期可信度", "detail": "尚未进入交付阶段"}

    # 7. Risk level (max 10 pts)
    risk = project.risk_level
    if risk == "L":
        dimensions["risk"] = {"score": 10, "max": 10, "label": "风险等级", "detail": "低风险"}
    elif risk == "M":
        dimensions["risk"] = {"score": 7, "max": 10, "label": "风险等级", "detail": "中风险"}
    elif risk == "H":
        dimensions["risk"] = {"score": 2, "max": 10, "label": "风险等级", "detail": "高风险"}
        reasons.append("项目风险等级为高")
    else:
        dimensions["risk"] = {"score": 7, "max": 10, "label": "风险等级", "detail": "未评估"}

    total = sum(d["score"] for d in dimensions.values())
    max_total = sum(d["max"] for d in dimensions.values())

    # Health level
    pct = total / max_total if max_total > 0 else 0
    if pct >= 0.8:
        level = "healthy"
    elif pct >= 0.6:
        level = "attention"
    elif pct >= 0.4:
        level = "warning"
    else:
        level = "critical"

    return {
        "project_id": project_id,
        "score": total,
        "max_score": max_total,
        "level": level,
        "dimensions": dimensions,
        "risks": reasons,
        "stall_days": days_since_update,
    }


async def list_stage_history(db: AsyncSession, tenant_id: str, project_id: str):
    result = await db.execute(
        select(ProjectStageHistory).where(
            ProjectStageHistory.tenant_id == tenant_id,
            ProjectStageHistory.project_id == project_id,
        ).order_by(ProjectStageHistory.created_at.desc())
    )
    return result.scalars().all()
