"""提交后锁编辑：审批中/已通过单据不可改内容，驳回（或撤回回草稿）后可再编辑。

权威边界在各业务 update_*；审批人字段写回走 wf act / field_updates，不经本闸门。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.error_codes import VALIDATION_ERROR
from app.common.exceptions import BusinessException

# 可整单编辑的业务状态（对齐 wf_biz_writeback 写回值）
EDITABLE_STATUSES: dict[str, frozenset[str]] = {
    "contract_version": frozenset({"draft", "rejected"}),
    "contract_review": frozenset({"draft", "rejected"}),
    "tech_agreement_review": frozenset({"draft", "rejected"}),
    "quote_version": frozenset({"draft", "rejected"}),
    # 方案提交态为 reviewing（REGISTRY 的 submitted 较少用）
    "solution": frozenset({"draft", "rejected"}),
    "change_request": frozenset({"draft", "rejected"}),
    # 工单日常态可改；仅审批中 submitted（及 running 流程）锁定；通过后 processing 可继续处理
    "service_ticket": frozenset({
        "draft", "rejected", "open", "assigned", "in_progress", "resolved", "closed", "processing",
    }),
    "form_instance": frozenset({"draft", "rejected"}),
    "order": frozenset({"draft"}),
    # 线索：仅 draft（及无 running 的 pending，见 assert_lead_editable）；收录后不可改
    "lead": frozenset({"draft"}),
    "customer": frozenset({"draft"}),
}

_LOCK_MSG = "审批中或已提交的单据不可编辑，驳回后可由发起人修改再提交"


async def has_running_process(
    db: AsyncSession, tenant_id: str, biz_type: str, biz_id: str | None,
) -> bool:
    if not biz_id:
        return False
    from app.domains.lowcode.workflow_models import WfProcessInstance

    row = (await db.execute(
        select(WfProcessInstance.id).where(
            WfProcessInstance.tenant_id == tenant_id,
            WfProcessInstance.biz_type == biz_type,
            WfProcessInstance.biz_id == biz_id,
            WfProcessInstance.status == "running",
        ).limit(1)
    )).scalar_one_or_none()
    return row is not None


def is_status_editable(biz_type: str, status: str | None) -> bool:
    allowed = EDITABLE_STATUSES.get(biz_type)
    if allowed is None:
        return True
    return (status or "draft") in allowed


async def assert_biz_editable(
    db: AsyncSession,
    tenant_id: str,
    biz_type: str,
    biz_id: str | None,
    status: str | None,
    *,
    message: str | None = None,
) -> None:
    """有 running 流程或 status 不在可编辑集合 → 拒绝。"""
    if await has_running_process(db, tenant_id, biz_type, biz_id):
        raise BusinessException(code=VALIDATION_ERROR, message=message or _LOCK_MSG)
    if not is_status_editable(biz_type, status):
        raise BusinessException(code=VALIDATION_ERROR, message=message or _LOCK_MSG)


async def assert_lead_editable(
    db: AsyncSession, tenant_id: str, lead_id: str, review_status: str | None,
) -> None:
    """线索内容锁：running 必锁；仅 draft / 无 running 的 pending 可整单编辑。

    - rejected：情报驳回终态，不可再改
    - approved（收录）/ attacked：流程已结束，申报与跟进内容不可再改
      （转化/废弃/改派等运维字段由 update_lead 单独豁免，不经本闸）
    """
    running = await has_running_process(db, tenant_id, "lead", lead_id)
    if running:
        raise BusinessException(code=VALIDATION_ERROR, message=_LOCK_MSG)
    rs = review_status or "approved"
    if rs == "draft":
        return
    if rs == "pending":
        # 无 running：撤回后回写 pending，允许修改再提交
        return
    if rs == "rejected":
        raise BusinessException(
            code=VALIDATION_ERROR,
            message="线索已被驳回，项目不可再报备，不可继续编辑或跟进",
        )
    if rs == "attacked":
        raise BusinessException(
            code=VALIDATION_ERROR,
            message="袭击状态的线索不可编辑申报信息",
        )
    if rs == "approved":
        raise BusinessException(
            code=VALIDATION_ERROR,
            message="线索已收录，不可再编辑；如需变更请走重激活或转化流程",
        )
    raise BusinessException(code=VALIDATION_ERROR, message=_LOCK_MSG)


async def assert_customer_editable(
    db: AsyncSession, tenant_id: str, customer_id: str, review_status: str | None,
) -> None:
    """客户：running 必锁；draft 可整单编辑；pending 仅无 running（撤回后）可编辑。

    rejected 为驳回终态；approved 可继续维护主数据（变更再审另议）。
    """
    running = await has_running_process(db, tenant_id, "customer", customer_id)
    if running:
        raise BusinessException(code=VALIDATION_ERROR, message=_LOCK_MSG)
    rs = review_status or "approved"
    if rs in ("draft", "pending", "approved"):
        return
    if rs == "rejected":
        raise BusinessException(
            code=VALIDATION_ERROR,
            message="客户信息已被驳回，不可继续编辑或重新提交",
        )


async def assert_contract_record_editable(
    db: AsyncSession, tenant_id: str, contract, *, version=None,
) -> None:
    """合同主表编辑：签署/终止不可改；否则看当前版本 status + contract_version 流程。"""
    st = getattr(contract, "status", None) or "draft"
    if st in ("signed", "terminated"):
        raise BusinessException(
            code=VALIDATION_ERROR,
            message="已签署或已终止的合同不可编辑",
        )
    ver = version
    if ver is None:
        from app.domains.contract.models import ContractVersion

        ver = (await db.execute(
            select(ContractVersion).where(
                ContractVersion.tenant_id == tenant_id,
                ContractVersion.contract_id == contract.id,
                ContractVersion.version_no == contract.current_version_no,
            )
        )).scalar_one_or_none()
    ver_status = getattr(ver, "status", None) if ver else "draft"
    ver_id = getattr(ver, "id", None) if ver else None
    await assert_biz_editable(db, tenant_id, "contract_version", ver_id, ver_status)


async def assert_form_instance_editable(
    db: AsyncSession, tenant_id: str, inst_id: str, status: str | None,
) -> None:
    """表单实例：status 闸门 + biz/form_instance_id 任一 running 流程。"""
    await assert_biz_editable(
        db, tenant_id, "form_instance", inst_id, status,
        message="审批中或已提交的表单不可编辑，驳回后可由发起人修改再提交",
    )
    from app.domains.lowcode.workflow_models import WfProcessInstance

    running = (await db.execute(
        select(WfProcessInstance.id).where(
            WfProcessInstance.tenant_id == tenant_id,
            WfProcessInstance.form_instance_id == inst_id,
            WfProcessInstance.status == "running",
        ).limit(1)
    )).scalar_one_or_none()
    if running:
        raise BusinessException(
            code=VALIDATION_ERROR,
            message="审批中或已提交的表单不可编辑，驳回后可由发起人修改再提交",
        )


async def assert_content_update_allowed(
    db: AsyncSession,
    tenant_id: str,
    biz_type: str,
    biz_id: str,
    current_status: str | None,
    payload: dict,
    *,
    status_key: str = "status",
) -> None:
    """版本类 update：改内容必须可编辑；仅 status→submitted 时也要求当前可编辑。"""
    content = {k: v for k, v in payload.items() if k != status_key}
    if content:
        await assert_biz_editable(db, tenant_id, biz_type, biz_id, current_status)
        return
    if status_key in payload:
        new_st = payload[status_key]
        if new_st != current_status:
            # 提交审批：当前须可编辑
            await assert_biz_editable(db, tenant_id, biz_type, biz_id, current_status)
