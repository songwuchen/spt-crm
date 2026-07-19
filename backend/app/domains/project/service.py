import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND, BUSINESS_ERROR
from app.domains.project.models import OpportunityProject, ProjectStageHistory, ProjectMember
from app.domains.project.schemas import ProjectCreate, ProjectUpdate, ProjectMemberAdd, ProjectMemberUpdate
from app.domains.audit.service import log_action
from app.common.code_generator import generate_code

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
            # 兼容 dict（旧版单条需求）与 list（新版多条需求明细）：空则不通过
            if not val or (isinstance(val, (dict, list)) and len(val) == 0):
                passed = False

        elif check_type == "has_related":
            entity = rule["entity"]
            # Optional status filter — lets a tenant require e.g. a *signed* contract
            # (configure in StageDefinition.gate_rules_json), not just any contract.
            want_status = rule.get("status")
            count = 0
            if entity == "solution":
                from app.domains.solution.models import Solution
                q = select(func.count(Solution.id)).where(Solution.tenant_id == tenant_id, Solution.project_id == project.id)
                if want_status:
                    q = q.where(Solution.status == want_status)
                count = (await db.execute(q)).scalar() or 0
            elif entity == "quote":
                from app.domains.quote.models import Quote
                q = select(func.count(Quote.id)).where(Quote.tenant_id == tenant_id, Quote.project_id == project.id)
                if want_status:
                    q = q.where(Quote.status == want_status)
                count = (await db.execute(q)).scalar() or 0
            elif entity == "contract":
                from app.domains.contract.models import Contract
                q = select(func.count(Contract.id)).where(Contract.tenant_id == tenant_id, Contract.project_id == project.id)
                if want_status:
                    q = q.where(Contract.status == want_status)
                count = (await db.execute(q)).scalar() or 0
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



async def list_projects(
    db: AsyncSession, tenant_id: str, page_no: int = 1, page_size: int = 20,
    keyword: str | None = None, stage_code: str | None = None,
    customer_id: str | None = None, status: str | None = None,
    owner_id: str | None = None, current_user: dict | None = None,
    adv_filter: str | None = None, sort_by: str | None = None, sort_order: str | None = None,
    filter_user_id: str | None = None,
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

    # 高级筛选（多字段/多条件，含自定义扩展字段）
    from app.common.search import (
        entity_search_context, filter_clause_from_schema_or_400, resolve_sort_from_schema,
    )
    search_schema = await entity_search_context("project", db, tenant_id)
    clause = filter_clause_from_schema_or_400(search_schema, adv_filter, {"user_id": filter_user_id})
    if clause is not None:
        base = base.where(clause)

    # Apply data scope (non-admin only sees owned/shared records)
    if current_user:
        from app.common.data_scope import apply_data_scope
        base = await apply_data_scope(base, db, tenant_id, current_user, OpportunityProject, "project")

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar()
    order = resolve_sort_from_schema(search_schema, sort_by, sort_order, OpportunityProject.created_at.desc())
    items = (await db.execute(
        base.order_by(order).offset((page_no - 1) * page_size).limit(page_size)
    )).scalars().all()
    return items, total


async def get_project(db: AsyncSession, tenant_id: str, project_id: str,
                      user: dict | None = None) -> OpportunityProject:
    """按 id 取商机。传入 user 时校验数据范围（列表能查到的，按 id 才读得到）。

    user=None 表示系统内部调用（审批引擎、提醒、跨域统计等），不做范围校验。
    """
    p = (await db.execute(
        select(OpportunityProject).where(OpportunityProject.id == project_id, OpportunityProject.tenant_id == tenant_id, OpportunityProject.is_deleted == False)
    )).scalar_one_or_none()
    if not p:
        raise BusinessException(code=NOT_FOUND, message="商机项目不存在")
    from app.common.data_scope import assert_in_scope
    await assert_in_scope(db, tenant_id, user, p, "project", label="该商机")
    return p


async def create_project(db: AsyncSession, tenant_id: str, data: ProjectCreate, user: dict) -> OpportunityProject:
    actor_name = user.get("real_name") or user.get("username")
    payload = data.model_dump()
    # 字段级权限：丢弃用户对不可编辑/隐藏扩展字段的写入
    from app.domains.lowcode.field_permission import (
        enforce_native_field_policy, sanitize_entity_write, validate_entity_custom_fields,
    )
    payload["custom_fields_json"] = await sanitize_entity_write(
        db, tenant_id, "project", payload.get("custom_fields_json"), None, user.get("roles"))
    await validate_entity_custom_fields(
        db, tenant_id, "project", payload["custom_fields_json"], user.get("roles"))
    # 原生字段策略：读取侧已按角色隐藏/脱敏，写入侧必须对称拦截
    payload = await enforce_native_field_policy(db, tenant_id, "project", payload, None, user.get("roles"))
    # 创建时负责人默认 = 录入人（之后可由主管经 transfer_owner 转移）；
    # 若显式指定 owner_id（如批量导入按姓名指派），则查该用户名回填 owner_name
    chosen_owner_id = payload.pop("owner_id", None)
    if chosen_owner_id:
        from app.domains.auth.models import User as AuthUser
        owner = (await db.execute(
            select(AuthUser).where(AuthUser.id == chosen_owner_id, AuthUser.tenant_id == tenant_id)
        )).scalar_one_or_none()
        owner_id = chosen_owner_id
        owner_name = (owner.real_name or owner.username) if owner else actor_name
    else:
        owner_id, owner_name = user["sub"], actor_name
    project = OpportunityProject(
        id=generate_uuid(), tenant_id=tenant_id,
        project_code=await generate_code(db, tenant_id, "project"),
        owner_id=owner_id, owner_name=owner_name,
        created_by_id=user["sub"], created_by_name=actor_name,
        **payload,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="project", resource_id=project.id,
                     summary=f"创建商机项目: {project.name}")
    return project


async def update_project(db: AsyncSession, tenant_id: str, project_id: str, data: ProjectUpdate, user: dict) -> OpportunityProject:
    project = await get_project(db, tenant_id, project_id, user)
    update_data = data.model_dump(exclude_unset=True)
    # 字段级权限：不可编辑扩展字段保留原值，忽略用户改动
    from app.domains.lowcode.field_permission import (
        enforce_native_field_policy, sanitize_entity_write, validate_entity_custom_fields,
    )
    if "custom_fields_json" in update_data:
        update_data["custom_fields_json"] = await sanitize_entity_write(
            db, tenant_id, "project", update_data["custom_fields_json"], project.custom_fields_json, user.get("roles"))
        await validate_entity_custom_fields(
            db, tenant_id, "project", update_data["custom_fields_json"], user.get("roles"))
    update_data = await enforce_native_field_policy(
        db, tenant_id, "project", update_data, project, user.get("roles"), required_scope="payload")

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

    if new_status and new_status in ("won", "lost"):
        from app.domains.outbox.service import emit_event
        await emit_event(db, tenant_id, f"crm.project.{new_status}", "project", project.id, {
            "project_id": project.id, "project_code": project.project_code, "name": project.name,
            "status": new_status,
            "amount_expect": float(project.amount_expect) if project.amount_expect else None,
        })
    # 结单商机数：赢单/丢单后重算所属客户的冗余计数
    if new_status and new_status in ("won", "lost") and project.customer_id:
        try:
            from app.domains.customer.service import refresh_won_deal_count
            await refresh_won_deal_count(db, tenant_id, project.customer_id)
        except Exception as e:
            logger.warning("refresh won_deal_count failed: %s", e)
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


async def transfer_owner(db: AsyncSession, tenant_id: str, project_id: str,
                         new_owner_id: str, note: str | None, user: dict) -> OpportunityProject:
    """转移商机负责人。受 project:transfer 权限保护（路由层校验）。

    与普通编辑分离：改负责人会改变该商机在数据范围(data_scope)下对其他人的可见性，
    并把后续赢单/丢单/回款等通知导向新负责人，故单独鉴权 + 审计 + 通知新负责人。
    录入人(created_by)不受影响，始终保留。"""
    project = await get_project(db, tenant_id, project_id, user)

    from app.domains.auth.models import User as AuthUser
    new_owner = (await db.execute(
        select(AuthUser).where(AuthUser.id == new_owner_id, AuthUser.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not new_owner:
        raise BusinessException(code=BUSINESS_ERROR, message="新负责人不存在")

    old_owner_id = project.owner_id
    old_owner_name = project.owner_name
    if new_owner_id == old_owner_id:
        return project  # 负责人未变，幂等返回

    project.owner_id = new_owner_id
    project.owner_name = new_owner.real_name or new_owner.username
    await db.commit()
    await db.refresh(project)

    actor_name = user.get("real_name") or user.get("username")
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=actor_name,
                     action="transfer", resource_type="project", resource_id=project.id,
                     summary=f"转移负责人: {old_owner_name or '-'} → {project.owner_name}",
                     detail={"changes": {"owner_id": {"old": old_owner_id, "new": new_owner_id}},
                             "note": note})

    # 通知新负责人（自己转给自己不通知）
    if new_owner_id != user["sub"]:
        try:
            from app.common.auto_notify import notify_project_assigned
            await notify_project_assigned(db, tenant_id, project.name, new_owner_id, actor_name, project.id)
        except Exception as e:
            logger.warning("Auto-notify new project owner on transfer failed: %s", e)

    return project


async def delete_project(db: AsyncSession, tenant_id: str, project_id: str, user: dict):
    project = await get_project(db, tenant_id, project_id, user)
    project_name = project.name

    # Cascade: soft-delete related payment data
    from sqlalchemy import update as sql_update, delete as sql_delete
    from app.domains.payment.models import Invoice, PaymentPlan, PaymentRecord
    await db.execute(
        sql_update(Invoice).where(Invoice.tenant_id == tenant_id, Invoice.project_id == project_id)
        .values(status="void")
    )
    await db.execute(
        sql_update(PaymentPlan).where(PaymentPlan.tenant_id == tenant_id, PaymentPlan.project_id == project_id)
        .values(status="cancelled")
    )
    # PaymentRecord has no status column — delete directly
    await db.execute(
        sql_delete(PaymentRecord).where(PaymentRecord.tenant_id == tenant_id, PaymentRecord.project_id == project_id)
    )

    # Cascade: cancel pending approval flows on this project's quotes/contracts
    try:
        from app.domains.approval.models import ApprovalFlow, ApprovalTask
        from app.domains.quote.models import Quote, QuoteVersion
        from app.domains.contract.models import Contract, ContractVersion

        quote_ids = (await db.execute(
            select(Quote.id).where(Quote.tenant_id == tenant_id, Quote.project_id == project_id)
        )).scalars().all()
        contract_ids = (await db.execute(
            select(Contract.id).where(Contract.tenant_id == tenant_id, Contract.project_id == project_id)
        )).scalars().all()

        biz_ids = []
        if quote_ids:
            qv_ids = (await db.execute(
                select(QuoteVersion.id).where(QuoteVersion.tenant_id == tenant_id, QuoteVersion.quote_id.in_(quote_ids))
            )).scalars().all()
            biz_ids.extend(qv_ids)
        if contract_ids:
            cv_ids = (await db.execute(
                select(ContractVersion.id).where(ContractVersion.tenant_id == tenant_id, ContractVersion.contract_id.in_(contract_ids))
            )).scalars().all()
            biz_ids.extend(cv_ids)

        if biz_ids:
            await db.execute(
                sql_update(ApprovalFlow).where(
                    ApprovalFlow.tenant_id == tenant_id,
                    ApprovalFlow.biz_id.in_(biz_ids),
                    ApprovalFlow.status == "pending",
                ).values(status="withdrawn")
            )
            # Cancel pending tasks for those flows
            pending_flow_ids = (await db.execute(
                select(ApprovalFlow.id).where(
                    ApprovalFlow.tenant_id == tenant_id,
                    ApprovalFlow.biz_id.in_(biz_ids),
                )
            )).scalars().all()
            if pending_flow_ids:
                await db.execute(
                    sql_update(ApprovalTask).where(
                        ApprovalTask.tenant_id == tenant_id,
                        ApprovalTask.flow_id.in_(pending_flow_ids),
                        ApprovalTask.status.in_(["pending", "waiting"]),
                    ).values(status="cancelled")
                )
    except Exception as e:
        logger.warning("Cascade cancel approvals on project delete failed: %s", e)

    # Soft delete the project itself
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
    project = await get_project(db, tenant_id, project_id, user)
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
            missing_names = [r["name"] for r in failed]
            summary = f"Gate 校验未通过，缺少: {', '.join(missing_names)}"
            raise BusinessException(code=42201, message=summary, detail={"pass": False, "failed_rules": failed})

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
    from app.domains.outbox.service import emit_event
    await emit_event(db, tenant_id, "crm.project.stage_advanced", "project", project_id, {
        "project_id": project_id, "project_code": project.project_code,
        "from_stage": from_stage, "to_stage": to_stage,
    })
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
    project = await get_project(db, tenant_id, project_id, user)
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


async def calculate_health_score(db: AsyncSession, tenant_id: str, project_id: str,
                                 user: dict | None = None) -> dict:
    """Calculate project health score (0-100) based on multiple dimensions."""
    project = await get_project(db, tenant_id, project_id, user)

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


async def list_stage_history(db: AsyncSession, tenant_id: str, project_id: str,
                             user: dict | None = None):
    # 子资源按 project_id 直查会绕过数据范围：先确认父商机对当前用户可见
    await get_project(db, tenant_id, project_id, user)
    result = await db.execute(
        select(ProjectStageHistory).where(
            ProjectStageHistory.tenant_id == tenant_id,
            ProjectStageHistory.project_id == project_id,
        ).order_by(ProjectStageHistory.created_at.desc())
    )
    return result.scalars().all()


# ==================== Project Members (多部门/多人协作) ====================

async def list_members(db: AsyncSession, tenant_id: str, project_id: str,
                       user: dict | None = None):
    # 同上：成员名单也只对能看见该商机的人开放
    await get_project(db, tenant_id, project_id, user)
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.tenant_id == tenant_id,
            ProjectMember.project_id == project_id,
        ).order_by(ProjectMember.created_at)
    )
    return result.scalars().all()


async def add_member(db: AsyncSession, tenant_id: str, project_id: str, data: ProjectMemberAdd, user: dict) -> ProjectMember:
    # 404 if project missing（并校验数据范围：看不见的商机不能往里加人）
    await get_project(db, tenant_id, project_id, user)

    # De-dupe / upsert: one row per (project, user)
    existing = (await db.execute(
        select(ProjectMember).where(
            ProjectMember.tenant_id == tenant_id,
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == data.user_id,
        )
    )).scalar_one_or_none()

    if existing:
        for field in ("user_name", "member_role", "department_id", "department_name", "permission"):
            val = getattr(data, field, None)
            if val is not None:
                setattr(existing, field, val)
        await db.commit()
        await db.refresh(existing)
        member = existing
        action = "update_member"
    else:
        member = ProjectMember(
            id=generate_uuid(), tenant_id=tenant_id,
            project_id=project_id,
            user_id=data.user_id, user_name=data.user_name,
            member_role=data.member_role,
            department_id=data.department_id, department_name=data.department_name,
            permission=data.permission or "view",
            added_by_id=user["sub"], added_by_name=user.get("real_name") or user.get("username"),
        )
        db.add(member)
        await db.commit()
        await db.refresh(member)
        action = "add_member"

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action=action, resource_type="project", resource_id=project_id,
                     summary=f"商机成员: {member.user_name or member.user_id}")
    return member


async def update_member(db: AsyncSession, tenant_id: str, project_id: str, member_id: str, data: ProjectMemberUpdate, user: dict) -> ProjectMember:
    await get_project(db, tenant_id, project_id, user)  # 数据范围校验
    member = (await db.execute(
        select(ProjectMember).where(
            ProjectMember.id == member_id,
            ProjectMember.tenant_id == tenant_id,
            ProjectMember.project_id == project_id,
        )
    )).scalar_one_or_none()
    if not member:
        raise BusinessException(code=NOT_FOUND, message="成员不存在")
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(member, field, val)
    await db.commit()
    await db.refresh(member)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="update_member", resource_type="project", resource_id=project_id,
                     summary=f"更新商机成员: {member.user_name or member.user_id}")
    return member


async def remove_member(db: AsyncSession, tenant_id: str, project_id: str, member_id: str, user: dict):
    await get_project(db, tenant_id, project_id, user)  # 数据范围校验
    member = (await db.execute(
        select(ProjectMember).where(
            ProjectMember.id == member_id,
            ProjectMember.tenant_id == tenant_id,
            ProjectMember.project_id == project_id,
        )
    )).scalar_one_or_none()
    if not member:
        raise BusinessException(code=NOT_FOUND, message="成员不存在")
    member_name = member.user_name or member.user_id
    await db.delete(member)
    await db.commit()

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="remove_member", resource_type="project", resource_id=project_id,
                     summary=f"移除商机成员: {member_name}")
