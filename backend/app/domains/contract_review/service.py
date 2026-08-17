"""合同评审 service。"""
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND, VALIDATION_ERROR
from app.common.code_generator import generate_code
from app.domains.audit.service import log_action
from app.domains.contract_review.models import ContractReview
from app.domains.contract_review.schemas import ContractReviewCreate, ContractReviewUpdate

ALLOWED_STATUS = {"draft", "submitted", "approved", "rejected"}


async def _hydrate_display_names(
    db: AsyncSession, tenant_id: str, rows: list[ContractReview],
) -> None:
    """业务员/区域经理/部门仅存了 id 时，补齐 *_name 供列表与详情展示（不落库）。"""
    if not rows:
        return
    user_ids: set[str] = set()
    dept_ids: set[str] = set()
    for r in rows:
        if r.owner_id and not (r.owner_name or "").strip():
            user_ids.add(r.owner_id)
        if r.region_manager_id and not (r.region_manager_name or "").strip():
            user_ids.add(r.region_manager_id)
        if r.department_id and not (r.department_name or "").strip():
            dept_ids.add(r.department_id)
    users: dict[str, str] = {}
    depts: dict[str, str] = {}
    if user_ids:
        from app.domains.auth.models import User
        for u in (await db.execute(
            select(User).where(User.tenant_id == tenant_id, User.id.in_(user_ids))
        )).scalars().all():
            users[u.id] = (u.real_name or u.username or "").strip()
    if dept_ids:
        from app.domains.organization.models import Department
        for d in (await db.execute(
            select(Department).where(
                Department.tenant_id == tenant_id, Department.id.in_(dept_ids),
            )
        )).scalars().all():
            depts[d.id] = (d.name or "").strip()
    for r in rows:
        if r.owner_id and not (r.owner_name or "").strip():
            r.owner_name = users.get(r.owner_id) or r.owner_name
        if r.region_manager_id and not (r.region_manager_name or "").strip():
            r.region_manager_name = users.get(r.region_manager_id) or r.region_manager_name
        if r.department_id and not (r.department_name or "").strip():
            r.department_name = depts.get(r.department_id) or r.department_name


async def _resolve_names_into_dump(
    db: AsyncSession, tenant_id: str, dump: dict,
) -> None:
    """创建/更新时：有 id 无 name 则查库写入，避免再次落成「只存 UUID」。"""
    from app.domains.auth.models import User
    from app.domains.organization.models import Department

    async def user_label(uid: str | None) -> str | None:
        if not uid:
            return None
        u = (await db.execute(
            select(User).where(User.id == uid, User.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not u:
            return None
        return (u.real_name or u.username or "").strip() or None

    if dump.get("owner_id") and not (dump.get("owner_name") or "").strip():
        dump["owner_name"] = await user_label(dump.get("owner_id"))
    if dump.get("region_manager_id") and not (dump.get("region_manager_name") or "").strip():
        dump["region_manager_name"] = await user_label(dump.get("region_manager_id"))
    if dump.get("department_id") and not (dump.get("department_name") or "").strip():
        did = dump.get("department_id")
        d = (await db.execute(
            select(Department).where(Department.id == did, Department.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if d:
            dump["department_name"] = (d.name or "").strip() or None


async def list_reviews(
    db: AsyncSession,
    tenant_id: str,
    page_no: int = 1,
    page_size: int = 20,
    status: str | None = None,
    review_type: str | None = None,
    keyword: str | None = None,
    current_user: dict | None = None,
    filter: str | None = None,
    sort_by: str | None = None,
    sort_order: str | None = None,
):
    from app.common.search import (
        entity_search_context, filter_clause_from_schema_or_400, resolve_sort_from_schema,
    )

    base = select(ContractReview).where(ContractReview.tenant_id == tenant_id)
    if status:
        base = base.where(ContractReview.status == status)
    if review_type:
        base = base.where(ContractReview.review_type == review_type)
    if keyword:
        kw = f"%{keyword}%"
        base = base.where(or_(
            ContractReview.review_code.ilike(kw),
            ContractReview.company_name.ilike(kw),
            ContractReview.project_title.ilike(kw),
            ContractReview.owner_name.ilike(kw),
        ))

    search_schema = await entity_search_context("contract_review", db, tenant_id)
    clause = filter_clause_from_schema_or_400(
        search_schema, filter, {"user_id": (current_user or {}).get("sub")},
    )
    if clause is not None:
        base = base.where(clause)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    order = resolve_sort_from_schema(
        search_schema, sort_by, sort_order, ContractReview.created_at.desc(),
    )
    items = list((await db.execute(
        base.order_by(order)
        .offset((page_no - 1) * page_size).limit(page_size)
    )).scalars().all())
    await _hydrate_display_names(db, tenant_id, items)
    return items, total


async def get_review(db: AsyncSession, tenant_id: str, rid: str) -> ContractReview:
    row = (await db.execute(
        select(ContractReview).where(ContractReview.id == rid, ContractReview.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not row:
        raise BusinessException(code=NOT_FOUND, message="合同评审不存在")
    await _hydrate_display_names(db, tenant_id, [row])
    return row


async def create_review(
    db: AsyncSession, tenant_id: str, data: ContractReviewCreate, user: dict,
) -> ContractReview:
    dump = data.model_dump(exclude_unset=True)
    status = dump.get("status") or "draft"
    if status not in ALLOWED_STATUS:
        raise BusinessException(code=VALIDATION_ERROR, message="无效状态")
    dump["status"] = status
    await _resolve_names_into_dump(db, tenant_id, dump)
    code = await generate_code(db, tenant_id, "contract_review")
    row = ContractReview(
        id=generate_uuid(),
        tenant_id=tenant_id,
        review_code=code,
        created_by_id=user["sub"],
        created_by_name=user.get("real_name") or user.get("username"),
        **dump,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    await log_action(
        db, tenant_id=tenant_id, user_id=user["sub"],
        user_name=user.get("real_name") or user.get("username"),
        action="create", resource_type="contract_review", resource_id=row.id,
        summary=f"创建合同评审: {row.review_code}",
    )
    return row


async def update_review(
    db: AsyncSession, tenant_id: str, rid: str, data: ContractReviewUpdate, user: dict,
) -> ContractReview:
    row = await get_review(db, tenant_id, rid)
    dump = data.model_dump(exclude_unset=True)
    if "status" in dump and dump["status"] not in ALLOWED_STATUS:
        raise BusinessException(code=VALIDATION_ERROR, message="无效状态")
    from app.domains.lowcode.edit_lock import assert_content_update_allowed
    await assert_content_update_allowed(
        db, tenant_id, "contract_review", row.id, row.status, dump)
    await _resolve_names_into_dump(db, tenant_id, dump)
    for field, val in dump.items():
        setattr(row, field, val)
    await db.commit()
    await db.refresh(row)
    await log_action(
        db, tenant_id=tenant_id, user_id=user["sub"],
        user_name=user.get("real_name") or user.get("username"),
        action="update", resource_type="contract_review", resource_id=row.id,
        summary=f"更新合同评审: {row.review_code}",
    )
    return row


async def delete_review(db: AsyncSession, tenant_id: str, rid: str, user: dict):
    row = await get_review(db, tenant_id, rid)
    if row.status != "draft":
        raise BusinessException(
            code=VALIDATION_ERROR,
            message=f"当前状态「{row.status}」不可删除（仅草稿可删除）",
        )
    code = row.review_code
    await db.delete(row)
    await db.commit()
    await log_action(
        db, tenant_id=tenant_id, user_id=user["sub"],
        user_name=user.get("real_name") or user.get("username"),
        action="delete", resource_type="contract_review", resource_id=rid,
        summary=f"删除合同评审: {code}",
    )


CONTRACT_REVIEW_DEFAULT_FLOW_CODE = "SYS_CONTRACT_REVIEW_APPROVAL"


async def submit_for_approval(
    db: AsyncSession, tenant_id: str, rid: str, user: dict,
) -> ContractReview:
    """提交合同评审审批：ensure 默认流程 + start_for_biz，状态 → submitted。"""
    row = await get_review(db, tenant_id, rid)
    if row.status not in ("draft", "rejected"):
        raise BusinessException(
            code=VALIDATION_ERROR,
            message=f"当前状态「{row.status}」不可提交审批（仅草稿/已驳回可提交）",
        )

    from app.domains.lowcode.workflow_service import ensure_default_definition, start_for_biz

    await ensure_default_definition(
        db, tenant_id,
        biz_type="contract_review",
        code=CONTRACT_REVIEW_DEFAULT_FLOW_CODE,
        name="合同评审会签",
        # 系统兜底图在 workflow_service._contract_review_flow_graph（简道云会签主干）
        approver_rule={"type": "specified_role", "value": "sales_manager", "exclude_initiator": True},
        multi_mode="or_sign",
        empty_strategy="auto_approve",
    )

    row.status = "submitted"
    await db.flush()

    title = f"合同评审: {row.review_code} {row.company_name or row.project_title or ''}".strip()
    pinst = await start_for_biz(db, tenant_id, "contract_review", row.id, user, title=title)
    if not pinst:
        raise BusinessException(
            code=VALIDATION_ERROR,
            message="未找到已发布的合同评审流程，请先在扩展平台→流程管理中发布并绑定 contract_review",
        )

    await db.commit()
    await db.refresh(row)
    await log_action(
        db, tenant_id=tenant_id, user_id=user["sub"],
        user_name=user.get("real_name") or user.get("username"),
        action="submit", resource_type="contract_review", resource_id=row.id,
        summary=f"提交合同评审审批: {row.review_code}",
    )
    await _hydrate_display_names(db, tenant_id, [row])
    return row
