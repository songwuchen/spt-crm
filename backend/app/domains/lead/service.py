import logging
from datetime import datetime, timedelta

from sqlalchemy import select, func, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND, LEAD_ALREADY_QUALIFIED, LEAD_ALREADY_DISCARDED
from app.common.code_generator import generate_code
from app.domains.lead.models import Lead, LeadProduct
from app.domains.lead.schemas import LeadCreate, LeadUpdate
from app.domains.customer.models import Customer, Contact
from app.domains.audit.service import log_action

logger = logging.getLogger("spt_crm.lead")



def _derived_region(lead: Lead) -> str | None:
    """Concat province/city/district into a single display string."""
    parts = [p for p in (lead.province, lead.city, lead.district) if p]
    return "".join(parts) if parts else None


def _compute_score(lead: Lead) -> int:
    """Basic rule-based scoring per requirements: source, industry, demand, budget, contact."""
    score = 0
    if lead.company_name:
        score += 15
    if lead.contact_phone or lead.contact_email:
        score += 15
    if lead.contact_name:
        score += 10
    if lead.industry:
        score += 10
    if lead.region:
        score += 5
    if lead.source:
        score += 10
    if lead.demand_summary:
        score += 15
    if lead.budget_range:
        score += 10
    # Extra: multiple contact methods
    if lead.contact_phone and lead.contact_email:
        score += 10
    return min(score, 100)


async def list_leads(
    db: AsyncSession, tenant_id: str, page_no: int = 1, page_size: int = 20,
    keyword: str | None = None, status: str | None = None, owner_id: str | None = None,
    customer_type: str | None = None, category: str | None = None,
    country_type: str | None = None, province: str | None = None,
    department_id: str | None = None, industry: str | None = None,
    company_name: str | None = None,
    start_date=None, end_date=None, date_field: str | None = None,
    current_user: dict | None = None,
    adv_filter: str | None = None, sort_by: str | None = None, sort_order: str | None = None,
):
    base = select(Lead).where(Lead.tenant_id == tenant_id, Lead.is_deleted == False)
    if keyword:
        base = base.where(Lead.title.ilike(f"%{keyword}%") | Lead.company_name.ilike(f"%{keyword}%") | Lead.lead_code.ilike(f"%{keyword}%"))
    if company_name:
        base = base.where(Lead.company_name.ilike(f"%{company_name}%"))
    # 日期区间可按「创建时间」(默认，DateTime) 或「业务日期」(biz_date，Date) 筛选。
    if date_field == "biz_date":
        if start_date:
            base = base.where(Lead.biz_date >= start_date)
        if end_date:
            base = base.where(Lead.biz_date <= end_date)
    else:
        if start_date:
            base = base.where(Lead.created_at >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            base = base.where(Lead.created_at < datetime.combine(end_date + timedelta(days=1), datetime.min.time()))
    if status:
        base = base.where(Lead.status == status)
    if isinstance(owner_id, (list, tuple, set)):
        base = base.where(Lead.owner_id.in_(list(owner_id)))  # [] -> 无可见数据
    elif owner_id:
        base = base.where(Lead.owner_id == owner_id)
    if customer_type:
        base = base.where(Lead.customer_type == customer_type)
    if category:
        base = base.where(Lead.category == category)
    if country_type:
        base = base.where(Lead.country_type == country_type)
    if province:
        base = base.where(Lead.province == province)
    if department_id:
        base = base.where(Lead.department_id == department_id)
    if industry:
        base = base.where(Lead.industry == industry)

    # 高级筛选（多字段/多条件，含自定义扩展字段）
    from app.common.search import (
        entity_search_context, filter_clause_from_schema_or_400, resolve_sort_from_schema,
    )
    search_schema = await entity_search_context("lead", db, tenant_id)
    clause = filter_clause_from_schema_or_400(search_schema, adv_filter, {"user_id": (current_user or {}).get("sub")})
    if clause is not None:
        base = base.where(clause)

    # 数据范围过滤（非管理员仅见 负责人/创建人/共享给本人 的线索）
    if current_user:
        from app.common.data_scope import apply_data_scope
        base = await apply_data_scope(base, db, tenant_id, current_user, Lead, "lead")

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar()
    order = resolve_sort_from_schema(search_schema, sort_by, sort_order, Lead.created_at.desc())
    items = (await db.execute(
        base.order_by(order).offset((page_no - 1) * page_size).limit(page_size)
    )).scalars().all()
    return items, total


async def list_lead_products(db: AsyncSession, tenant_id: str, lead_id: str):
    """取某条线索的产品明细，按 sort_order 排序。"""
    return (await db.execute(
        select(LeadProduct).where(
            LeadProduct.tenant_id == tenant_id, LeadProduct.lead_id == lead_id)
        .order_by(LeadProduct.sort_order, LeadProduct.created_at)
    )).scalars().all()


async def _replace_lead_products(db: AsyncSession, tenant_id: str, lead_id: str, products) -> None:
    """用给定明细整体替换线索产品明细。products 为 LeadProductIn 列表。"""
    await db.execute(sql_delete(LeadProduct).where(
        LeadProduct.tenant_id == tenant_id, LeadProduct.lead_id == lead_id))
    for i, p in enumerate(products or []):
        # 整行为空则跳过
        if not (p.product_name or p.product_spec or p.quantity is not None or p.remark):
            continue
        db.add(LeadProduct(
            id=generate_uuid(), tenant_id=tenant_id, lead_id=lead_id,
            product_name=p.product_name, product_spec=p.product_spec,
            quantity=p.quantity, remark=p.remark, sort_order=i,
        ))


async def get_lead(db: AsyncSession, tenant_id: str, lead_id: str) -> Lead:
    lead = (await db.execute(
        select(Lead).where(Lead.id == lead_id, Lead.tenant_id == tenant_id, Lead.is_deleted == False)
    )).scalar_one_or_none()
    if not lead:
        raise BusinessException(code=NOT_FOUND, message="线索不存在")
    return lead




# 线索审核的系统兜底流程（租户未在设计器里画流程时自动创建并发布）
LEAD_DEFAULT_FLOW_CODE = "SYS_LEAD_REVIEW"


async def submit_lead_review(db: AsyncSession, tenant_id: str, lead: Lead, user: dict):
    """把线索提交审核（走扩展平台可视化工作流引擎）。

    审批人解析优先级：
      ① 租户在「扩展平台→流程设计」为 biz_type=lead 发布的可视化流程；
      ② 系统兜底默认流程 —— 审批人 = lead_intel(信息情报部内勤)角色的活跃成员，
         或签(任一通过)，并排除提交人本人。

    兜底流程用引擎自己的规则语言(specified_role)表达原先硬编码的内勤兜底，因此运行时
    不需要任何线索特判；「解析不出审批人就免审通过」也交给引擎的 empty_strategy=auto_approve
    承担（并会通知发起人，不再是静默放行），避免线索卡在 pending 无法转化。

    返回创建的 WfProcessInstance；连流程都起不来时返回 None（调用方按免审处理）。
    """
    from app.domains.lowcode.workflow_service import ensure_default_definition, start_for_biz

    title = f"线索审核: {(lead.lead_code + ' ') if lead.lead_code else ''}{lead.title}"
    # 先直接起流程：稳态下租户已有可用流程，这样每条线索只花 start_for_biz 自己的那次查询，
    # 不必在写路径上再多跑一次「兜底流程是否存在」的探测(Excel 批量导入会放大这个开销)。
    inst = await start_for_biz(db, tenant_id, "lead", lead.id, user, title=title)
    if inst is not None:
        return inst
    # 起不来 → 说明还没有可用的已发布流程，补建/恢复系统兜底流程后重试一次
    await ensure_default_definition(
        db, tenant_id, biz_type="lead", code=LEAD_DEFAULT_FLOW_CODE, name="线索审核",
        # 刻意按角色而非按 lead:review 权限解析，避免把管理员(拥有全部权限)也拉进审核人池
        approver_rule={"type": "specified_role", "value": "lead_intel", "exclude_initiator": True},
        multi_mode="or_sign", empty_strategy="auto_approve",
    )
    return await start_for_biz(db, tenant_id, "lead", lead.id, user, title=title)


async def create_lead(db: AsyncSession, tenant_id: str, data: LeadCreate, user: dict,
                      auto_review: bool | None = None) -> Lead:
    payload = data.model_dump()
    products = data.products  # 产品明细单独处理，不能 setattr 到模型
    payload.pop("products", None)
    # 字段级权限：丢弃用户对不可编辑/隐藏扩展字段的写入
    from app.domains.lowcode.field_permission import (
        enforce_native_field_policy, sanitize_entity_write, validate_entity_custom_fields,
    )
    payload["custom_fields_json"] = await sanitize_entity_write(
        db, tenant_id, "lead", payload.get("custom_fields_json"), None, user.get("roles"))
    await validate_entity_custom_fields(
        db, tenant_id, "lead", payload["custom_fields_json"], user.get("roles"))
    # 原生字段的租户策略（必填/条件显隐/只读/字段级权限）同样在后端强制
    payload = await enforce_native_field_policy(db, tenant_id, "lead", payload, None, user.get("roles"))
    # If user picked an owner in the form, look up that user's name; otherwise fall back to creator.
    chosen_owner_id = payload.pop("owner_id", None)
    if chosen_owner_id:
        from app.domains.auth.models import User as AuthUser
        owner = (await db.execute(select(AuthUser).where(AuthUser.id == chosen_owner_id, AuthUser.tenant_id == tenant_id))).scalar_one_or_none()
        owner_id = chosen_owner_id
        owner_name = (owner.real_name or owner.username) if owner else None
    else:
        owner_id = user["sub"]
        owner_name = user.get("real_name") or user.get("username")

    lead = Lead(
        id=generate_uuid(), tenant_id=tenant_id,
        lead_code=await generate_code(db, tenant_id, "lead"),
        owner_id=owner_id, owner_name=owner_name,
        created_by_id=user["sub"],
        created_by_name=user.get("real_name") or user.get("username"),
        **payload,
    )
    lead.score = _compute_score(lead)
    db.add(lead)
    if products is not None:
        await _replace_lead_products(db, tenant_id, lead.id, products)
    from app.domains.outbox.service import emit_event
    await emit_event(db, tenant_id, "crm.lead.created", "lead", lead.id, {
        "lead_id": lead.id, "lead_code": lead.lead_code, "title": lead.title,
        "company_name": lead.company_name, "source": lead.source,
    })
    await db.commit()
    await db.refresh(lead)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="lead", resource_id=lead.id,
                     summary=f"创建线索: {lead.title}")

    # 审核门禁：任何人（含管理员）在系统内新建/导入线索都需内勤审核。
    # 仅显式传 auto_review=False 的入口（如公开表单 webhook）免审。
    if auto_review is None:
        needs_review = True
    else:
        needs_review = not auto_review
    if needs_review:
        lead.review_status = "pending"
        await db.commit()
        try:
            inst = await submit_lead_review(db, tenant_id, lead, user)
        except Exception as e:
            logger.warning("Lead review submit failed for %s: %s", lead.id, e)
            # 失败可能来自 DB 错误，此时 session 已进入 needs-rollback；
            # 不回滚就继续用它提交会抛 PendingRollbackError，线索已落库却返回 500。
            await db.rollback()
            inst = None
        await _apply_review_flow(db, tenant_id, lead, inst, user)
        await db.refresh(lead)
    return lead


async def _apply_review_flow(db: AsyncSession, tenant_id: str, lead: Lead, inst, user: dict) -> None:
    """把审核流程的发起结果落到线索上。

    流程若在发起过程中就已结束（无审批人自动通过 / 空审批人终止），引擎已用 SQL 回写了
    review_status，必须先 refresh 同步回 ORM，再写 review_flow_id，否则这里的 commit
    会把内存里过期的 pending 覆盖回去。
    """
    if inst is None:
        # 连流程都起不来（流程被删且恢复失败、或引擎异常）→ 仍按免审放行，避免线索
        # 永远卡在待审无法转化；但必须通知提交人，否则审核门禁被跳过了却无人知情。
        lead.review_status = "approved"
        await db.commit()
        from app.domains.lowcode import wf_notify
        await wf_notify.notify_review_flow_unavailable(
            tenant_id, "lead", lead.id, user.get("sub"), lead.title or "线索",
        )
        return
    if inst.status != "running":
        await db.refresh(lead)
    lead.review_flow_id = inst.id
    await db.commit()


async def update_lead(db: AsyncSession, tenant_id: str, lead_id: str, data: LeadUpdate, user: dict) -> Lead:
    lead = await get_lead(db, tenant_id, lead_id)
    payload = data.model_dump(exclude_unset=True)
    products_given = "products" in payload
    payload.pop("products", None)  # 产品明细单独处理
    # 字段级权限：不可编辑扩展字段保留原值，忽略用户改动
    from app.domains.lowcode.field_permission import (
        enforce_native_field_policy, sanitize_entity_write, validate_entity_custom_fields,
    )
    if "custom_fields_json" in payload:
        payload["custom_fields_json"] = await sanitize_entity_write(
            db, tenant_id, "lead", payload["custom_fields_json"], lead.custom_fields_json, user.get("roles"))
        await validate_entity_custom_fields(
            db, tenant_id, "lead", payload["custom_fields_json"], user.get("roles"))
    # 原生字段策略：必填只校验本次提交携带的字段，避免批量改派/废弃被历史数据卡住
    payload = await enforce_native_field_policy(
        db, tenant_id, "lead", payload, lead, user.get("roles"), required_scope="payload")
    # 审核门禁：未通过审核的线索不可经编辑直接置为「已转化」(移动端转化走 update)
    if payload.get("status") == "qualified" and getattr(lead, "review_status", "approved") != "approved":
        from app.common.error_codes import VALIDATION_ERROR
        raise BusinessException(code=VALIDATION_ERROR, message="线索尚未通过审核，无法转化")
    # When owner changes, refresh owner_name to match
    reassigned_to = None
    if "owner_id" in payload and payload["owner_id"] and payload["owner_id"] != lead.owner_id:
        from app.domains.auth.models import User as AuthUser
        new_owner = (await db.execute(select(AuthUser).where(AuthUser.id == payload["owner_id"], AuthUser.tenant_id == tenant_id))).scalar_one_or_none()
        if new_owner:
            lead.owner_name = new_owner.real_name or new_owner.username
        reassigned_to = payload["owner_id"]
    for field, val in payload.items():
        setattr(lead, field, val)
    lead.score = _compute_score(lead)
    if products_given:
        await _replace_lead_products(db, tenant_id, lead.id, data.products or [])
    await db.commit()
    await db.refresh(lead)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="update", resource_type="lead", resource_id=lead.id,
                     summary=f"更新线索: {lead.title}")
    # 线索改派给他人 → 通知新负责人有线索待跟进
    if reassigned_to and reassigned_to != user["sub"]:
        try:
            from app.common.auto_notify import notify_lead_assigned
            await notify_lead_assigned(db, tenant_id, lead.title or lead.company_name or "线索",
                                       reassigned_to, user.get("real_name") or user.get("username"), lead.id)
        except Exception:
            pass
    return lead


async def qualify_lead(db: AsyncSession, tenant_id: str, lead_id: str, user: dict,
                       create_opportunity: bool = False) -> dict:
    """Convert a lead into a customer. Optionally also spin up an opportunity (商机)
    carrying the lead's demand/budget context, so sales doesn't re-key it."""
    lead = await get_lead(db, tenant_id, lead_id)
    if lead.status == "qualified":
        raise BusinessException(code=LEAD_ALREADY_QUALIFIED, message="线索已转化")
    if lead.status == "discarded":
        raise BusinessException(code=LEAD_ALREADY_DISCARDED, message="线索已废弃，无法转化")
    if getattr(lead, "review_status", "approved") != "approved":
        from app.common.error_codes import VALIDATION_ERROR
        raise BusinessException(code=VALIDATION_ERROR, message="线索尚未通过审核，无法转化")

    # Create customer from lead — carry over geographic fields so sales keeps context on conversion
    customer = Customer(
        id=generate_uuid(), tenant_id=tenant_id,
        name=lead.company_name or lead.title,
        industry=lead.industry,
        region=_derived_region(lead) or lead.region,
        source=lead.source, owner_id=lead.owner_id, owner_name=lead.owner_name,
    )
    db.add(customer)

    # Carry the lead's contact person over to the new customer so sales keeps
    # the person (and their phone/email) after conversion — otherwise the
    # converted customer has no contacts. (issue #90)
    contact_name = (lead.contact_name or "").strip()
    contact_phone = (lead.contact_phone or "").strip()
    contact_email = (lead.contact_email or "").strip()
    if contact_name or contact_phone or contact_email:
        db.add(Contact(
            id=generate_uuid(), tenant_id=tenant_id,
            customer_id=customer.id,
            name=contact_name or contact_phone or contact_email,
            mobile=contact_phone or None,
            email=contact_email or None,
            is_primary=True,
        ))

    lead.status = "qualified"
    lead.converted_customer_id = customer.id

    # Optionally create an opportunity from the lead, carrying demand/budget context.
    project = None
    if create_opportunity:
        from app.domains.project.models import OpportunityProject
        from app.common.code_generator import generate_code
        remark_parts = []
        if lead.budget_range:
            remark_parts.append(f"预算: {lead.budget_range}")
        if lead.remark:
            remark_parts.append(lead.remark)
        project = OpportunityProject(
            id=generate_uuid(), tenant_id=tenant_id,
            project_code=await generate_code(db, tenant_id, "project"),
            name=lead.title or lead.company_name or "新商机",
            customer_id=customer.id, stage_code="S1",
            # 直接同步线索与商机重复的字段，避免转化后重复录入 (issue #94)
            biz_date=lead.biz_date,
            owner_id=lead.owner_id, owner_name=lead.owner_name,
            created_by_id=user.get("sub"),
            created_by_name=user.get("real_name") or user.get("username"),
            key_requirements_json={"summary": lead.demand_summary} if lead.demand_summary else None,
            remark="\n".join(remark_parts) or None,
        )
        db.add(project)

        # 同步线索的产品信息子表到商机需求，避免转化后重复录入 (issue #94 / #84)
        lead_products = await list_lead_products(db, tenant_id, lead.id)
        if lead_products:
            product_lines = [{
                "product_name": p.product_name,
                "product_spec": p.product_spec,
                "quantity": float(p.quantity) if p.quantity is not None else None,
                "remark": p.remark,
            } for p in lead_products]
            kr = project.key_requirements_json or {}
            kr["products"] = product_lines
            project.key_requirements_json = kr

    await db.commit()
    await db.refresh(lead)
    await db.refresh(customer)
    if project is not None:
        await db.refresh(project)

    summary = f"转化线索: {lead.title} -> 客户: {customer.name}"
    if project is not None:
        summary += f" + 商机: {project.project_code}"
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="qualify", resource_type="lead", resource_id=lead.id,
                     summary=summary)

    # Auto-activity: record lead qualification on lead timeline
    try:
        from app.common.auto_activity import record_activity
        act_msg = f"线索转化为客户: {customer.name}" + (f"，并创建商机 {project.project_code}" if project is not None else "")
        await record_activity(db, tenant_id, "lead", lead.id, "system",
                              act_msg, None,
                              user["sub"], user.get("real_name") or user.get("username"))
    except Exception as e:
        logger.warning("Auto-activity record for lead qualification failed: %s", e)

    result = {"lead_id": lead.id, "customer_id": customer.id, "customer_name": customer.name}
    if project is not None:
        result["project_id"] = project.id
        result["project_code"] = project.project_code
    return result


async def delete_lead(db: AsyncSession, tenant_id: str, lead_id: str, user: dict):
    lead = await get_lead(db, tenant_id, lead_id)
    lead_title = lead.title

    if lead.status == "qualified":
        from app.common.error_codes import VALIDATION_ERROR
        raise BusinessException(code=VALIDATION_ERROR, message="已转化的线索不可删除")

    # Soft delete
    lead.is_deleted = True
    await db.commit()

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="delete", resource_type="lead", resource_id=lead_id,
                     summary=f"删除线索: {lead_title}")


async def discard_lead(db: AsyncSession, tenant_id: str, lead_id: str, user: dict) -> Lead:
    lead = await get_lead(db, tenant_id, lead_id)
    if lead.status == "qualified":
        raise BusinessException(code=LEAD_ALREADY_QUALIFIED, message="线索已转化，无法废弃")
    if lead.status == "discarded":
        raise BusinessException(code=LEAD_ALREADY_DISCARDED, message="线索已废弃")

    lead.status = "discarded"
    await db.commit()
    await db.refresh(lead)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="discard", resource_type="lead", resource_id=lead.id,
                     summary=f"废弃线索: {lead.title}")

    # Auto-activity: record lead discard
    try:
        from app.common.auto_activity import record_activity
        await record_activity(db, tenant_id, "lead", lead.id, "system",
                              "线索已废弃", None,
                              user["sub"], user.get("real_name") or user.get("username"))
    except Exception as e:
        logger.warning("Auto-activity record for lead discard failed: %s", e)

    return lead


async def resubmit_lead_review(db: AsyncSession, tenant_id: str, lead_id: str, user: dict) -> Lead:
    """被驳回的线索修改后重新提交内勤审核。"""
    from app.common.error_codes import VALIDATION_ERROR
    lead = await get_lead(db, tenant_id, lead_id)
    if lead.review_status != "rejected":
        raise BusinessException(code=VALIDATION_ERROR, message="仅被驳回的线索可重新提交审核")

    lead.review_status = "pending"
    lead.reject_reason = None
    await db.commit()
    try:
        inst = await submit_lead_review(db, tenant_id, lead, user)
    except Exception as e:
        logger.warning("Lead review resubmit failed for %s: %s", lead.id, e)
        await db.rollback()
        inst = None
    await _apply_review_flow(db, tenant_id, lead, inst, user)
    await db.refresh(lead)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="submit_review", resource_type="lead", resource_id=lead.id,
                     summary=f"重新提交线索审核: {lead.title}")
    return lead
