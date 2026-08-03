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


async def list_reviews(
    db: AsyncSession,
    tenant_id: str,
    page_no: int = 1,
    page_size: int = 20,
    status: str | None = None,
    review_type: str | None = None,
    keyword: str | None = None,
    current_user: dict | None = None,
):
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

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    items = (await db.execute(
        base.order_by(ContractReview.created_at.desc())
        .offset((page_no - 1) * page_size).limit(page_size)
    )).scalars().all()
    return items, total


async def get_review(db: AsyncSession, tenant_id: str, rid: str) -> ContractReview:
    row = (await db.execute(
        select(ContractReview).where(ContractReview.id == rid, ContractReview.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not row:
        raise BusinessException(code=NOT_FOUND, message="合同评审不存在")
    return row


async def create_review(
    db: AsyncSession, tenant_id: str, data: ContractReviewCreate, user: dict,
) -> ContractReview:
    dump = data.model_dump(exclude_unset=True)
    status = dump.get("status") or "draft"
    if status not in ALLOWED_STATUS:
        raise BusinessException(code=VALIDATION_ERROR, message="无效状态")
    dump["status"] = status
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
    if pinst is None:
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
    return row
