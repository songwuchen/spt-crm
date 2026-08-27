"""扩展平台 — 审批流程引擎服务(定义生命周期 + 运行时查询 + 表单绑定触发)。"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import cast, func, or_, select, text, String, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND, DUPLICATE_ENTRY, BUSINESS_ERROR
from app.database import generate_uuid
from app.domains.lowcode import workflow_schemas as ws
from app.domains.lowcode.workflow_models import (
    WfProcessDefinition, WfProcessDefinitionVersion, WfProcessInstance,
    WfNodeInstance, WfTaskInstance, WfTaskActionLog, WfProcessComment, WfProcessCc,
)
from app.domains.lowcode.workflow_engine import WorkflowEngine


logger = logging.getLogger("spt_crm.lowcode.workflow")


def _now() -> datetime:
    return datetime.now(timezone.utc)


STARTED_FLOW_DELETE_MSG = "该单据已发起流程，不可删除。如需作废请撤回或走流程驳回。"


async def has_started_process(
    db,
    tenant_id: str,
    *,
    form_instance_id: str | None = None,
    biz_type: str | None = None,
    biz_id: str | None = None,
) -> bool:
    """是否已有流程实例（任意状态）。发起后即视为已走流程。"""
    conds = [WfProcessInstance.tenant_id == tenant_id]
    if form_instance_id:
        inst = (await db.execute(
            select(WfProcessInstance.id).where(
                *conds, WfProcessInstance.form_instance_id == form_instance_id,
            ).limit(1)
        )).scalar_one_or_none()
        if inst:
            return True
    if biz_type and biz_id:
        inst = (await db.execute(
            select(WfProcessInstance.id).where(
                *conds,
                WfProcessInstance.biz_type == biz_type,
                WfProcessInstance.biz_id == biz_id,
            ).limit(1)
        )).scalar_one_or_none()
        if inst:
            return True
    return False


async def assert_no_started_process(
    db,
    tenant_id: str,
    *,
    form_instance_id: str | None = None,
    biz_type: str | None = None,
    biz_id: str | None = None,
) -> None:
    """流程一旦发起，禁止直接删除关联单据。"""
    if await has_started_process(
        db, tenant_id, form_instance_id=form_instance_id, biz_type=biz_type, biz_id=biz_id,
    ):
        raise BusinessException(code=BUSINESS_ERROR, message=STARTED_FLOW_DELETE_MSG)


# ==================== 流程定义 ====================

async def create_definition(db: AsyncSession, tenant_id: str, data: ws.WfDefinitionCreate, user: dict) -> WfProcessDefinition:
    has_form = bool(data.form_template_id)
    has_biz = bool(data.biz_type)
    if has_form and has_biz:
        raise BusinessException(code=BUSINESS_ERROR, message="绑定表单与业务类型只能二选一")
    if not has_form and not has_biz:
        raise BusinessException(code=BUSINESS_ERROR, message="请绑定表单或业务类型之一")
    code = data.code or f"WF_{generate_uuid()[:8].upper()}"
    exists = (await db.execute(select(WfProcessDefinition).where(
        WfProcessDefinition.tenant_id == tenant_id, WfProcessDefinition.code == code,
        WfProcessDefinition.is_deleted == False,  # noqa: E712
    ))).scalar_one_or_none()
    if exists:
        raise BusinessException(code=DUPLICATE_ENTRY, message=f"流程编码 {code} 已存在")
    d = WfProcessDefinition(
        id=generate_uuid(), tenant_id=tenant_id, name=data.name, code=code,
        description=data.description, category=data.category, icon=data.icon,
        form_template_id=data.form_template_id, biz_type=data.biz_type,
        status="draft", current_version=0, created_by=user.get("sub"),
    )
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return d


async def get_definition(db: AsyncSession, tenant_id: str, def_id: str) -> WfProcessDefinition:
    d = (await db.execute(select(WfProcessDefinition).where(
        WfProcessDefinition.id == def_id, WfProcessDefinition.tenant_id == tenant_id,
        WfProcessDefinition.is_deleted == False,  # noqa: E712
    ))).scalar_one_or_none()
    if not d:
        raise BusinessException(code=NOT_FOUND, message="流程定义不存在")
    return d


async def list_definitions(db, tenant_id, page_no, page_size, name=None):
    # 打开流程管理即幂等补齐系统默认流（合同/线索 + 图纸等表单绑定流）
    try:
        await ensure_all_biz_defaults(db, tenant_id)
    except Exception as e:
        logger.warning("ensure_all_biz_defaults on list failed: %s", e)
        await db.rollback()
    conds = [WfProcessDefinition.tenant_id == tenant_id, WfProcessDefinition.is_deleted == False]  # noqa: E712
    if name:
        conds.append(WfProcessDefinition.name.ilike(f"%{name}%"))
    total = (await db.execute(select(func.count()).select_from(WfProcessDefinition).where(*conds))).scalar_one()
    rows = (await db.execute(select(WfProcessDefinition).where(*conds)
            .order_by(WfProcessDefinition.created_at.desc())
            .offset((page_no - 1) * page_size).limit(page_size))).scalars().all()
    return list(rows), total


async def update_definition(db, tenant_id, def_id, data: ws.WfDefinitionUpdate) -> WfProcessDefinition:
    d = await get_definition(db, tenant_id, def_id)
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(d, k, v)
    await db.commit()
    await db.refresh(d)
    return d


async def delete_definition(db, tenant_id, def_id) -> None:
    d = await get_definition(db, tenant_id, def_id)
    d.is_deleted = True
    await db.commit()


async def _latest_version(db, tenant_id, def_id) -> WfProcessDefinitionVersion | None:
    return (await db.execute(select(WfProcessDefinitionVersion).where(
        WfProcessDefinitionVersion.tenant_id == tenant_id,
        WfProcessDefinitionVersion.process_definition_id == def_id,
    ).order_by(WfProcessDefinitionVersion.version_number.desc()).limit(1))).scalar_one_or_none()


async def _draft_version(db, tenant_id, def_id) -> WfProcessDefinitionVersion | None:
    return (await db.execute(select(WfProcessDefinitionVersion).where(
        WfProcessDefinitionVersion.tenant_id == tenant_id,
        WfProcessDefinitionVersion.process_definition_id == def_id,
        WfProcessDefinitionVersion.status == "draft",
    ).order_by(WfProcessDefinitionVersion.version_number.desc()).limit(1))).scalar_one_or_none()


async def _published_version(db, tenant_id, def_id) -> WfProcessDefinitionVersion | None:
    return (await db.execute(select(WfProcessDefinitionVersion).where(
        WfProcessDefinitionVersion.tenant_id == tenant_id,
        WfProcessDefinitionVersion.process_definition_id == def_id,
        WfProcessDefinitionVersion.status == "published",
    ).order_by(WfProcessDefinitionVersion.version_number.desc()).limit(1))).scalar_one_or_none()


async def save_design(db, tenant_id, def_id, data: ws.WfSaveDesign, user_id) -> WfProcessDefinitionVersion:
    d = await get_definition(db, tenant_id, def_id)
    from app.domains.lowcode.jdy_id_remap import sanitize_route_ids_for_tenant
    routes, _ = await sanitize_route_ids_for_tenant(
        db, tenant_id, data.route_definitions or [],
        preserve_routes_without_exclusive=True,
    )
    draft = await _draft_version(db, tenant_id, def_id)
    if draft:
        draft.node_definitions = data.node_definitions
        draft.route_definitions = routes
        draft.approver_rules = data.approver_rules
    else:
        latest = await _latest_version(db, tenant_id, def_id)
        draft = WfProcessDefinitionVersion(
            id=generate_uuid(), tenant_id=tenant_id, process_definition_id=def_id,
            version_number=(latest.version_number + 1) if latest else 1,
            node_definitions=data.node_definitions, route_definitions=routes,
            approver_rules=data.approver_rules, status="draft",
        )
        db.add(draft)
    # 设计器手动保存即视为租户编排，避免 ensure 时系统对齐整图覆盖
    if d.category == SYSTEM_DEFAULT_CATEGORY or d.code in {
        s["code"] for s in FORM_DEFAULT_SPECS
    }:
        d.category = USER_DESIGNED_CATEGORY
    await db.commit()
    await db.refresh(draft)
    return draft


async def publish(db, tenant_id, def_id, user_id) -> WfProcessDefinitionVersion:
    d = await get_definition(db, tenant_id, def_id)
    latest = await _draft_version(db, tenant_id, def_id)
    if not latest:
        raise BusinessException(code=BUSINESS_ERROR, message="没有可发布的草稿版本")
    # 基本校验: 必须有 start 与 end，且至少有一个审批节点（避免 start→end 空流程免审）
    types = {n.get("type") for n in (latest.node_definitions or [])}
    if "start" not in types or "end" not in types:
        raise BusinessException(code=BUSINESS_ERROR, message="流程必须包含开始与结束节点")
    if "approval" not in types:
        raise BusinessException(code=BUSINESS_ERROR, message="流程至少包含一个审批节点")
    # 发布前再清一次：CRM 不存在的部门/简道云残留人员 id 会在设计器显示乱码
    from app.domains.lowcode.jdy_id_remap import sanitize_route_ids_for_tenant
    cleaned, _ = await sanitize_route_ids_for_tenant(
        db, tenant_id, latest.route_definitions,
    )
    latest.route_definitions = cleaned
    old = await _published_version(db, tenant_id, def_id)
    if old:
        old.status = "deprecated"
    latest.status = "published"
    latest.published_at = _now()
    latest.published_by = user_id
    d.status = "published"
    d.current_version = latest.version_number
    # 设计器手动发布：标记为用户编排，避免 ensure/对齐逻辑整图覆盖
    if d.category == SYSTEM_DEFAULT_CATEGORY or d.code in {
        s["code"] for s in FORM_DEFAULT_SPECS
    }:
        d.category = USER_DESIGNED_CATEGORY
    await db.commit()
    await db.refresh(latest)
    return latest


async def get_design(db, tenant_id, def_id) -> WfProcessDefinitionVersion | None:
    """返回可编辑设计：优先活跃草稿，否则已发布；系统表单流先对齐简道云并清旧草稿。"""
    d = await get_definition(db, tenant_id, def_id)
    form_code = None
    if d.code in (
        "SYS_DRAWING_REQUISITION",
        "SYS_INSTALL_DRAWING_NOTICE",
        "SYS_SCHEME_MANAGEMENT",
        "SYS_PROD_CARD_SUPPLEMENT",
        "SYS_INVOICE_APPLICATION",
        "SYS_PAYMENT_REGISTRATION",
    ):
        form_code = next(
            (s["form_code"] for s in FORM_DEFAULT_SPECS if s["code"] == d.code),
            None,
        )
        if form_code:
            await _upgrade_drawing_form_flow_if_needed(db, tenant_id, d, form_code)
            await _discard_stale_system_draft_if_needed(db, tenant_id, d, form_code)
    draft = await _draft_version(db, tenant_id, def_id)
    if draft:
        return draft
    return await _published_version(db, tenant_id, def_id)


async def _discard_stale_system_draft_if_needed(
    db, tenant_id: str, d: WfProcessDefinition, form_code: str,
) -> None:
    """系统流已对齐简道云后，若仍有未对齐的草稿盖在上面，废弃草稿以免设计器读旧图。"""
    if d.category and d.category != SYSTEM_DEFAULT_CATEGORY:
        return
    latest = await _draft_version(db, tenant_id, d.id)
    if not latest:
        return
    published = await _published_version(db, tenant_id, d.id)
    if not published:
        return
    if not _flow_is_jdy_form_graph(form_code, published.node_definitions):
        return
    # 草稿已是对齐拓扑则保留（用户可能在调布局/审批人）
    if _flow_is_jdy_form_graph(form_code, latest.node_definitions):
        if not (
            form_code == "invoice_application"
            and _flow_missing_invoice_sales_cc(
                latest.node_definitions, latest.route_definitions,
            )
        ) and not (
            form_code in _CS_SALES_CC_FORM_CODES
            and _flow_missing_cs_sales_cc_on_start(
                latest.node_definitions, latest.route_definitions,
            )
        ):
            return
    latest.status = "deprecated"
    await db.commit()
    logger.info(
        "已废弃盖住系统流的旧草稿 %s v%s(tenant=%s)",
        d.code, latest.version_number, tenant_id,
    )


async def get_versions(db, tenant_id, def_id):
    rows = (await db.execute(select(WfProcessDefinitionVersion).where(
        WfProcessDefinitionVersion.tenant_id == tenant_id,
        WfProcessDefinitionVersion.process_definition_id == def_id,
    ).order_by(WfProcessDefinitionVersion.version_number.desc()))).scalars().all()
    return list(rows)


# ==================== 表单绑定触发 ====================

async def maybe_start_for_form(db, tenant_id, template_id, form_instance, user, form_data) -> WfProcessInstance | None:
    """表单提交后: 若该表单绑定了已发布流程,则起流程并返回;否则返回 None(表单按普通提交)。"""
    d = (await db.execute(select(WfProcessDefinition).where(
        WfProcessDefinition.tenant_id == tenant_id,
        WfProcessDefinition.form_template_id == template_id,
        WfProcessDefinition.status == "published",
        WfProcessDefinition.is_deleted == False,  # noqa: E712
    ).limit(1))).scalar_one_or_none()
    if not d:
        return None
    version = await _published_version(db, tenant_id, d.id)
    if not version:
        return None

    title = (getattr(form_instance, "title", None) or "").strip() or None
    from app.domains.lowcode.service import (
        _should_use_composite_title,
        derive_form_instance_title_resolved,
        is_weak_form_title,
    )
    from app.domains.lowcode.models import FormTemplate
    tpl = await db.get(FormTemplate, template_id)
    tpl_name = (tpl.name if tpl else None) or d.name
    field_defs = getattr(form_instance, "field_definitions", None)
    if (
        not title
        or is_weak_form_title(title, tpl_name)
        or _should_use_composite_title(tpl_name, form_data or {}, field_defs)
    ):
        title = await derive_form_instance_title_resolved(
            db, tenant_id, tpl_name, form_data, field_defs,
        )
        form_instance.title = title
        await db.flush()

    engine = WorkflowEngine(db, tenant_id)
    # 注意: 引擎内部会 commit;此处不额外 commit(调用方 create_instance 已在 flush 后)
    return await engine.submit(
        d.id, version, user, form_instance_id=form_instance.id,
        form_data=form_data, title=title,
    )


SYSTEM_DEFAULT_CATEGORY = "system_default"
USER_DESIGNED_CATEGORY = "user_designed"
# 系统兜底流程排在最后，租户自建流程(sort_order 默认 0)优先命中
_SYSTEM_DEFAULT_SORT = 9999

# 线索情报审批默认指定人员（钉钉 username，与 resolver / 简道云 chargers 一致）
_LEAD_INTEL_APPROVER_USERNAMES = ["060832423223953982", "0615176412841441"]  # 崔艳丽、杨光


def _lead_intel_approver_rule() -> dict:
    return {
        "type": "specified_user",
        "value": list(_LEAD_INTEL_APPROVER_USERNAMES),
        "exclude_initiator": True,
    }


# 打开「流程管理」/租户开通时幂等补齐；业务提交路径仍保留 ensure 作双保险。
BIZ_DEFAULT_SPECS: list[dict] = [
    {
        "biz_type": "contract_version",
        "code": "SYS_CONTRACT_VERSION_APPROVAL",
        "name": "合同登记审批（运营）",
        "approver_rule": {"type": "specified_role", "value": "finance_manager", "exclude_initiator": True},
        "multi_mode": "or_sign",
        "empty_strategy": "auto_approve",
    },
    {
        "biz_type": "contract_review",
        "code": "SYS_CONTRACT_REVIEW_APPROVAL",
        "name": "合同评审会签",
        "approver_rule": {"type": "specified_role", "value": "sales_manager", "exclude_initiator": True},
        "multi_mode": "or_sign",
        "empty_strategy": "auto_approve",
    },
    {
        "biz_type": "tech_agreement_review",
        "code": "SYS_TECH_AGREEMENT_REVIEW",
        "name": "技术协议评审审批",
        "approver_rule": {"type": "specified_role", "value": "sales_manager", "exclude_initiator": True},
        "multi_mode": "or_sign",
        "empty_strategy": "auto_approve",
    },
    {
        "biz_type": "lead",
        "code": "SYS_LEAD_REVIEW",
        "name": "信息情报部审批",
        "approver_rule": _lead_intel_approver_rule(),
        "multi_mode": "or_sign",
        "empty_strategy": "auto_approve",
    },
    {
        "biz_type": "lead_reactivation",
        "code": "SYS_LEAD_REACTIVATION_REVIEW",
        "name": "180天项目激活审批",
        "approver_rule": _lead_intel_approver_rule(),
        "multi_mode": "or_sign",
        "empty_strategy": "auto_approve",
    },
    {
        "biz_type": "customer",
        "code": "SYS_CUSTOMER_INFO",
        "name": "客户信息审批",
        "approver_rule": {
            "type": "specified_user",
            "value": "03303022525221387032",  # 刘金花（财务，默认兜底单节点用不到完整图）
            "exclude_initiator": True,
        },
        "multi_mode": "or_sign",
        "empty_strategy": "auto_approve",
    },
]


# 自定义表单（内置模块）默认审批流：绑定 form_template_id，表单提交走 maybe_start_for_form。
FORM_DEFAULT_SPECS: list[dict] = [
    {
        "form_code": "drawing_requisition",
        "code": "SYS_DRAWING_REQUISITION",
        "name": "合同图纸（资料）领用申请",
        "approver_rule": {
            "type": "specified_role", "value": "sales_manager", "exclude_initiator": True,
        },
        "multi_mode": "or_sign",
        "empty_strategy": "auto_approve",
    },
    {
        "form_code": "install_drawing_notice",
        "code": "SYS_INSTALL_DRAWING_NOTICE",
        "name": "安装图设计通知",
        "approver_rule": {
            "type": "specified_role", "value": "sales_manager", "exclude_initiator": True,
        },
        "multi_mode": "or_sign",
        "empty_strategy": "auto_approve",
    },
    {
        "form_code": "scheme_management",
        "code": "SYS_SCHEME_MANAGEMENT",
        "name": "方案管理",
        "approver_rule": {
            "type": "specified_role", "value": "sales_manager", "exclude_initiator": True,
        },
        "multi_mode": "or_sign",
        "empty_strategy": "auto_approve",
    },
    {
        "form_code": "shipment_notice",
        "code": "SYS_SHIPMENT_NOTICE",
        "name": "发货通知",
        "approver_rule": {
            "type": "specified_role", "value": "sales_manager", "exclude_initiator": True,
        },
        "multi_mode": "or_sign",
        "empty_strategy": "auto_approve",
    },
    {
        "form_code": "xunhan_contract_review",
        "code": "SYS_XUNHAN_CONTRACT_REVIEW",
        "name": "迅焊公司合同评审",
        "approver_rule": {
            "type": "specified_role", "value": "sales_manager", "exclude_initiator": True,
        },
        "multi_mode": "or_sign",
        "empty_strategy": "auto_approve",
    },
    {
        "form_code": "presale_service_notice",
        "code": "SYS_PRESALE_SERVICE_NOTICE",
        "name": "售前服务通知",
        "approver_rule": {
            "type": "specified_role", "value": "sales_manager", "exclude_initiator": True,
        },
        "multi_mode": "or_sign",
        "empty_strategy": "auto_approve",
    },
    {
        "form_code": "prod_card_supplement",
        "code": "SYS_PROD_CARD_SUPPLEMENT",
        "name": "生产卡/补充流程",
        "approver_rule": {
            "type": "specified_role", "value": "sales_manager", "exclude_initiator": True,
        },
        "multi_mode": "or_sign",
        "empty_strategy": "auto_approve",
    },
    {
        "form_code": "invoice_application",
        "code": "SYS_INVOICE_APPLICATION",
        "name": "开票申请",
        "approver_rule": {
            "type": "specified_role", "value": "finance_manager", "exclude_initiator": True,
        },
        "multi_mode": "or_sign",
        "empty_strategy": "auto_approve",
    },
    {
        "form_code": "payment_registration",
        "code": "SYS_PAYMENT_REGISTRATION",
        "name": "收款登记",
        "approver_rule": {
            "type": "specified_role", "value": "finance_manager", "exclude_initiator": True,
        },
        "multi_mode": "or_sign",
        "empty_strategy": "auto_approve",
    },
    {
        "form_code": "quote_management",
        "code": "SYS_QUOTE_MANAGEMENT",
        "name": "报价管理",
        "approver_rule": {
            "type": "specified_role", "value": "sales_manager", "exclude_initiator": True,
        },
        "multi_mode": "or_sign",
        "empty_strategy": "auto_approve",
    },
    {
        "form_code": "pricing_checklist_hjqd",
        "code": "SYS_PRICING_CHECKLIST_HJQD",
        "name": "核价清单传递",
        "approver_rule": {
            "type": "specified_role", "value": "finance_manager", "exclude_initiator": True,
        },
        "multi_mode": "or_sign",
        "empty_strategy": "auto_approve",
    },
    {
        "form_code": "research_coop_card",
        "code": "SYS_RESEARCH_COOP_CARD",
        "name": "中央研究院协同卡",
        "approver_rule": {
            "type": "specified_role", "value": "sales_manager", "exclude_initiator": True,
        },
        "multi_mode": "or_sign",
        "empty_strategy": "auto_approve",
    },
    {
        "form_code": "tech_agreement_feedback",
        "code": "SYS_TECH_AGREEMENT_FEEDBACK",
        "name": "技术协议反馈单",
        "approver_rule": {
            "type": "specified_role", "value": "sales_manager", "exclude_initiator": True,
        },
        "multi_mode": "or_sign",
        "empty_strategy": "auto_approve",
    },
    {
        "form_code": "contract_outsource_early",
        "code": "SYS_CONTRACT_OUTSOURCE_EARLY",
        "name": "合同外购件提前安排流程",
        "approver_rule": {
            "type": "specified_role", "value": "sales_manager", "exclude_initiator": True,
        },
        "multi_mode": "or_sign",
        "empty_strategy": "auto_approve",
    },
    {
        "form_code": "biz_bonus_transfer",
        "code": "SYS_BIZ_BONUS_TRANSFER",
        "name": "业务奖金流转单",
        "approver_rule": {
            "type": "dept_head", "exclude_initiator": True,
        },
        "multi_mode": "or_sign",
        "empty_strategy": "auto_approve",
    },
    {
        "form_code": "biz_bonus_biz_initiate",
        "code": "SYS_BIZ_BONUS_BIZ_INITIATE",
        "name": "业务奖金流转—业务发起",
        "approver_rule": {
            "type": "dept_head", "exclude_initiator": True,
        },
        "multi_mode": "or_sign",
        "empty_strategy": "auto_approve",
    },
    {
        "form_code": "commission_database",
        "code": "SYS_COMMISSION_DATABASE",
        "name": "提成数据库",
        "approver_rule": {
            "type": "specified_role", "value": "finance_manager", "exclude_initiator": True,
        },
        "multi_mode": "or_sign",
        "empty_strategy": "auto_approve",
    },
    {
        "form_code": "cs_service_request",
        "code": "SYS_CS_SERVICE_REQUEST",
        "name": "客户服务申请及反馈",
        "approver_rule": {
            "type": "specified_role", "value": "service_manager", "exclude_initiator": True,
        },
        "multi_mode": "or_sign",
        "empty_strategy": "auto_approve",
    },
    {
        "form_code": "cs_product_replace",
        "code": "SYS_CS_PRODUCT_REPLACE",
        "name": "售出产品更换（补发）",
        "approver_rule": {
            "type": "specified_role", "value": "service_manager", "exclude_initiator": True,
        },
        "multi_mode": "or_sign",
        "empty_strategy": "auto_approve",
    },
    {
        "form_code": "cs_product_return",
        "code": "SYS_CS_PRODUCT_RETURN",
        "name": "售出产品/工具退回",
        "approver_rule": {
            "type": "specified_user",
            "value": [
                "0236446249514",
                "181359282120075679",
                "113236314224043072",
                "01364955133227249077",
            ],
            "exclude_initiator": True,
        },
        "multi_mode": "or_sign",
        "empty_strategy": "auto_approve",
    },
    {
        "form_code": "cs_loan_slip",
        "code": "SYS_CS_LOAN_SLIP",
        "name": "客服借据",
        "approver_rule": {
            "type": "specified_role", "value": "service_manager", "exclude_initiator": True,
        },
        "multi_mode": "or_sign",
        "empty_strategy": "auto_approve",
    },
    {
        "form_code": "cs_drawing_request",
        "code": "SYS_CS_DRAWING_REQUEST",
        "name": "客服领图",
        "approver_rule": {
            "type": "specified_role", "value": "service_manager", "exclude_initiator": True,
        },
        "multi_mode": "or_sign",
        "empty_strategy": "auto_approve",
    },
    {
        "form_code": "cs_service_delay",
        "code": "SYS_CS_SERVICE_DELAY",
        "name": "客户服务延期申请",
        "approver_rule": {
            "type": "specified_role", "value": "service_manager", "exclude_initiator": True,
        },
        "multi_mode": "or_sign",
        "empty_strategy": "auto_approve",
    },
    {
        "form_code": "cs_correspondence",
        "code": "SYS_CS_CORRESPONDENCE",
        "name": "客服往来函件",
        "approver_rule": {
            "type": "specified_role", "value": "service_manager", "exclude_initiator": True,
        },
        "multi_mode": "or_sign",
        "empty_strategy": "auto_approve",
    },
]

DRAWING_FORM_FLOW_DESC = (
    "对齐简道云表单流程拓扑（图纸/方案/生产卡/开票/收款/售后客服；具名审批人/角色在 CRM 无对应用户时 "
    "empty_strategy=auto_approve；详见 docs/product/_jdy_*_forms.md）"
)


def _drawing_flow_graph(form_code: str) -> tuple[list[dict], list[dict]] | None:
    packs: dict = {}
    try:
        from app.domains.lowcode._drawing_jdy_generated import DRAWING_JDY
        packs.update(DRAWING_JDY)
    except Exception:
        pass
    try:
        from app.domains.lowcode._scheme_management_generated import SCHEME_MANAGEMENT_JDY
        packs.update(SCHEME_MANAGEMENT_JDY)
    except Exception:
        pass
    try:
        from app.domains.lowcode._prod_card_jdy_generated import PROD_CARD_JDY
        packs.update(PROD_CARD_JDY)
    except Exception:
        pass
    try:
        from app.domains.lowcode._invoice_payment_jdy_generated import INVOICE_PAYMENT_JDY
        packs.update(INVOICE_PAYMENT_JDY)
    except Exception:
        pass
    try:
        from app.domains.lowcode._quote_management_generated import QUOTE_MANAGEMENT_JDY
        packs.update(QUOTE_MANAGEMENT_JDY)
    except Exception:
        pass
    try:
        from app.domains.lowcode._pricing_checklist_hjqd_generated import PRICING_CHECKLIST_HJQD_JDY
        packs.update(PRICING_CHECKLIST_HJQD_JDY)
    except Exception:
        pass
    try:
        from app.domains.lowcode._research_coop_card_generated import RESEARCH_COOP_CARD_JDY
        packs.update(RESEARCH_COOP_CARD_JDY)
    except Exception:
        pass
    try:
        from app.domains.lowcode._customer_service_jdy_generated import CUSTOMER_SERVICE_JDY
        packs.update(CUSTOMER_SERVICE_JDY)
    except Exception:
        pass
    try:
        from app.domains.lowcode._presale_service_notice_generated import PRESALE_SERVICE_NOTICE_JDY
        packs.update(PRESALE_SERVICE_NOTICE_JDY)
    except Exception:
        pass
    try:
        from app.domains.lowcode._shipment_notice_generated import SHIPMENT_NOTICE_JDY
        packs.update(SHIPMENT_NOTICE_JDY)
    except Exception:
        pass
    try:
        from app.domains.lowcode._xunhan_contract_review_generated import XUNHAN_CONTRACT_REVIEW_JDY
        packs.update(XUNHAN_CONTRACT_REVIEW_JDY)
    except Exception:
        pass
    try:
        from app.domains.lowcode._tech_feedback_outsource_generated import TECH_FEEDBACK_OUTSOURCE_JDY
        packs.update(TECH_FEEDBACK_OUTSOURCE_JDY)
    except Exception:
        pass
    try:
        from app.domains.lowcode._bonus_jdy_generated import BONUS_JDY
        packs.update(BONUS_JDY)
    except Exception:
        pass
    pack = packs.get(form_code)
    if not pack:
        return None
    import copy
    nodes = copy.deepcopy(pack.get("flow_nodes") or [])
    routes = copy.deepcopy(pack.get("flow_routes") or [])
    if not nodes:
        return None
    if form_code == "install_drawing_notice":
        from app.domains.lowcode.biz_score import strip_biz_score_flow_nodes
        strip_biz_score_flow_nodes(nodes, extra_fields=frozenset({"remark"}))
    if form_code == "scheme_management":
        from app.domains.lowcode.biz_score import (
            apply_chief_gm_flow_nodes, strip_biz_score_flow_nodes,
        )
        strip_biz_score_flow_nodes(nodes)
        apply_chief_gm_flow_nodes(nodes)
    if form_code in ("install_drawing_notice", "scheme_management", "drawing_requisition"):
        apply_drawing_pre_chief_opinion_required(nodes)
        from app.domains.lowcode.wf_node_actions import apply_drawing_print_node_actions
        apply_drawing_print_node_actions(nodes)
    if form_code == "cs_drawing_request":
        apply_cs_drawing_approvers(nodes)
        from app.domains.lowcode.wf_node_actions import apply_drawing_print_node_actions
        apply_drawing_print_node_actions(nodes)
    if form_code == "invoice_application":
        apply_invoice_sales_cc(nodes, routes)
    if form_code in _CS_SALES_CC_FORM_CODES:
        apply_cs_sales_cc_on_start(nodes, routes)
    if form_code == "tech_agreement_feedback":
        apply_tech_agreement_feedback_flow(nodes, routes)
    if form_code == "cs_product_return":
        apply_cs_product_return_approvers(nodes)
        apply_cs_product_return_logistics_field_perms(nodes)
        apply_cs_product_return_n20_countersign_routes(routes)
    if form_code == "cs_product_replace":
        apply_cs_product_replace_approvers(nodes)
    if form_code == "shipment_notice":
        from app.domains.lowcode.shipment_notice_fields import (
            patch_shipment_notice_parallel_routes,
        )
        apply_shipment_notice_approvers(nodes)
        patch_shipment_notice_parallel_routes(routes)
    if form_code == "prod_card_supplement":
        from app.domains.lowcode.prod_card_contract_fill import (
            apply_prod_card_design_assign_field_perms,
            apply_prod_card_prune_legacy_field_perms,
            apply_prod_card_sales_before_region,
            apply_prod_card_sales_confirm_field_perms,
        )
        apply_prod_card_sales_confirm_field_perms(nodes)
        apply_prod_card_design_assign_field_perms(nodes)
        apply_prod_card_prune_legacy_field_perms(nodes)
        apply_prod_card_sales_before_region(nodes, routes)
        apply_prod_card_notify_production_cc(nodes)
        apply_prod_card_finance_branch_parallel(nodes, routes)
        apply_prod_card_xiaomeng_yangshuang_cc(nodes, routes)
        fix_packaging_fork_serial_priority(nodes, routes)
        from app.domains.lowcode.wf_node_actions import apply_prod_card_material_code_node_actions
        apply_prod_card_material_code_node_actions(nodes)
    if form_code == "xunhan_contract_review":
        apply_xunhan_contract_review_approvers(nodes)
        patch_xunhan_contract_review_feedback_routes(routes)
    if form_code == "payment_registration":
        apply_payment_registration_cc_dept_head(nodes)
    return nodes, routes


# 安装图/方案/领用：部门审批→市场支持→总工须填意见（同意等），「已完成」不能代替同意
_DRAWING_OPINION_REQUIRED_NODES = ("部门审批", "市场支持中心", "总工审批")


def apply_drawing_pre_chief_opinion_required(nodes: list | None) -> bool:
    """就地为部门/市场支持/总工挂 opinion_required。"""
    changed = False
    for n in nodes or []:
        if not isinstance(n, dict) or n.get("type") != "approval":
            continue
        if n.get("name") not in _DRAWING_OPINION_REQUIRED_NODES:
            continue
        if not n.get("opinion_required"):
            n["opinion_required"] = True
            changed = True
    return changed


def _flow_missing_drawing_pre_chief_opinion(nodes: list | None) -> bool:
    """部门/市场支持/总工任一缺少 opinion_required → 需升级。"""
    want = set(_DRAWING_OPINION_REQUIRED_NODES)
    for n in nodes or []:
        if not isinstance(n, dict) or n.get("type") != "approval":
            continue
        if n.get("name") not in want:
            continue
        if not n.get("opinion_required"):
            return True
    return False


def _flow_is_jdy_drawing(nodes: list | None) -> bool:
    """已对齐简道云图纸流：含总工/图纸领取等关键节点名。"""
    names = {n.get("name") for n in (nodes or [])}
    return "总工审批" in names and ("图纸领取" in names or "设计指派安排" in names)


def _flow_has_node_field_perms(nodes: list | None) -> bool:
    return any(
        isinstance(n, dict) and n.get("type") == "approval" and n.get("field_perms")
        for n in (nodes or [])
    )


def _flow_field_perms_sig(nodes: list | None) -> str:
    """审批节点 field_perms 指纹（含 required/editable），用于检测简道云校验变更。"""
    import json
    items: list[tuple[str, str, str]] = []
    for n in nodes or []:
        if not isinstance(n, dict) or n.get("type") != "approval":
            continue
        nid = str(n.get("id") or "")
        for p in n.get("field_perms") or []:
            if not isinstance(p, dict):
                continue
            items.append((nid, str(p.get("field") or ""), str(p.get("access") or "")))
    return json.dumps(sorted(items), ensure_ascii=False)


def _flow_missing_biz_score_perms(nodes: list | None) -> bool:
    """方案/安装图「业务打分」未挂三项分数 → 需升级系统兜底流。"""
    from app.domains.lowcode.biz_score import flow_missing_biz_score_perms
    return flow_missing_biz_score_perms(nodes)


def _flow_has_install_score_perms(nodes: list | None) -> bool:
    from app.domains.lowcode.biz_score import flow_has_install_score_perms
    return flow_has_install_score_perms(nodes)


def _flow_missing_chief_gm_perm(nodes: list | None) -> bool:
    """方案管理「总工审批」未挂 need_gm_approval 必填 → 需升级。"""
    from app.domains.lowcode.biz_score import flow_missing_chief_gm_perm
    return flow_missing_chief_gm_perm(nodes)


def _flow_missing_install_gm_branch(nodes: list | None, routes: list | None) -> bool:
    """方案管理无合同号总工未按 need_gm 走总经理审批 → 需升级。"""
    from app.domains.lowcode.biz_score import flow_missing_install_gm_branch
    return flow_missing_install_gm_branch(nodes, routes)


def _flow_is_jdy_prod_card(nodes: list | None) -> bool:
    """已对齐简道云生产卡/补充（含 V43「业务员确认」；非旧「财务报价」简图）。"""
    names = {n.get("name") for n in (nodes or [])}
    if "财务报价" in names:
        return False
    return (
        "业务员确认" in names
        and "财务核价" in names
        and "法务审核" in names
        and "区域经理/组长" in names
        and len(nodes or []) >= 20
    )


def _flow_is_jdy_invoice(nodes: list | None) -> bool:
    """已对齐简道云开票申请：开票 → 发起人接收。"""
    names = {n.get("name") for n in (nodes or [])}
    return "开票" in names and "发起人接收" in names


# 开票申请：抄送业务员（提交知悉 / 发起人接收后再通知可下载）
_INVOICE_CC_SALES_SUBMIT = "cc_sales_submit"
_INVOICE_CC_SALES_DONE = "cc_sales_done"
_INVOICE_CC_SALES_SUBMIT_NAME = "已提交开票申请"
_INVOICE_CC_SALES_DONE_NAME = "发票已开具可下载"
_INVOICE_INITIATOR_RECV_NAME = "发起人接收"
_INVOICE_APPROVE_NAME = "开票"

# 客服三类表单：发起旁路抄送表单「业务员」
_CS_SALES_CC_ON_START = "cc_sales_on_start"
_CS_SALES_CC_ON_START_NAME = "抄送业务员"
_CS_SALES_CC_FORM_CODES = frozenset({
    "cs_service_request",
    "cs_product_replace",
    "cs_product_return",
})

# 技术协议反馈单：发起旁路抄送业务员；业务员反馈后旁路抄送申请人
_TECH_FB_CC_SALES = "cc_salesperson"
_TECH_FB_CC_APPLICANT = "cc_applicant"
_TECH_FB_CC_SALES_NAME = "抄送业务员"
_TECH_FB_CC_APPLICANT_NAME = "抄送申请人"


def _invoice_node_id(nodes: list | None, name: str) -> str | None:
    for n in nodes or []:
        if isinstance(n, dict) and n.get("name") == name and n.get("id"):
            return str(n["id"])
    return None


def _flow_missing_invoice_sales_cc(nodes: list | None, routes: list | None = None) -> bool:
    """缺少业务员抄送，或「可下载」仍挂在开票旁路（应在发起人接收之后）→ 需升级。"""
    by_id = {n.get("id"): n for n in (nodes or []) if isinstance(n, dict) and n.get("id")}
    for nid, want_name in (
        (_INVOICE_CC_SALES_SUBMIT, _INVOICE_CC_SALES_SUBMIT_NAME),
        (_INVOICE_CC_SALES_DONE, _INVOICE_CC_SALES_DONE_NAME),
    ):
        n = by_id.get(nid)
        if not n or n.get("type") != "cc":
            return True
        rule = n.get("approver_rule") or {}
        if rule.get("type") != "form_field_person" or rule.get("value") != "sales_person":
            return True
        if n.get("name") != want_name:
            return True
    initiator = _invoice_node_id(nodes, _INVOICE_INITIATOR_RECV_NAME)
    invoice_id = _invoice_node_id(nodes, _INVOICE_APPROVE_NAME)
    if not initiator:
        return True
    pairs = {
        (r.get("source"), r.get("target"))
        for r in (routes or [])
        if isinstance(r, dict)
    }
    if ("start", _INVOICE_CC_SALES_SUBMIT) not in pairs:
        return True
    if (initiator, _INVOICE_CC_SALES_DONE) not in pairs:
        return True
    if (_INVOICE_CC_SALES_DONE, "end") not in pairs:
        return True
    if invoice_id and (invoice_id, _INVOICE_CC_SALES_DONE) in pairs:
        return True
    return False


def apply_invoice_sales_cc(nodes: list[dict], routes: list[dict]) -> bool:
    """就地补：提交旁路抄送业务员；发起人接收完成后再抄送「发票已开具可下载」并到结束。"""
    if not isinstance(nodes, list) or not isinstance(routes, list):
        return False
    changed = False
    by_id = {n.get("id"): n for n in nodes if isinstance(n, dict) and n.get("id")}

    def _upsert_cc(nid: str, name: str) -> None:
        nonlocal changed
        want = _cc_node(nid, name, {"type": "form_field_person", "value": "sales_person"})
        cur = by_id.get(nid)
        if not cur:
            nodes.append(want)
            by_id[nid] = want
            changed = True
            return
        if cur.get("type") != "cc" or cur.get("name") != name:
            cur["type"] = "cc"
            cur["name"] = name
            changed = True
        rule = cur.get("approver_rule") or {}
        if rule.get("type") != "form_field_person" or rule.get("value") != "sales_person":
            cur["approver_rule"] = {"type": "form_field_person", "value": "sales_person"}
            changed = True

    _upsert_cc(_INVOICE_CC_SALES_SUBMIT, _INVOICE_CC_SALES_SUBMIT_NAME)
    _upsert_cc(_INVOICE_CC_SALES_DONE, _INVOICE_CC_SALES_DONE_NAME)

    initiator = _invoice_node_id(nodes, _INVOICE_INITIATOR_RECV_NAME)
    invoice_id = _invoice_node_id(nodes, _INVOICE_APPROVE_NAME)
    if not initiator:
        return changed

    def _ensure_always(rid: str, source: str, target: str) -> None:
        nonlocal changed
        for r in routes:
            if not isinstance(r, dict):
                continue
            if r.get("source") == source and r.get("target") == target:
                if not r.get("always"):
                    r["always"] = True
                    changed = True
                return
        routes.append({"id": rid, "source": source, "target": target, "always": True})
        changed = True

    _ensure_always("r_start_cc_sales_submit", "start", _INVOICE_CC_SALES_SUBMIT)

    has_init_to_done = False
    has_done_to_end = False
    for r in routes:
        if not isinstance(r, dict):
            continue
        src, tgt = r.get("source"), r.get("target")
        if tgt == _INVOICE_CC_SALES_DONE:
            if invoice_id and src == invoice_id:
                r["source"] = initiator
                r.pop("always", None)
                r.pop("exclusive_group", None)
                changed = True
                src = initiator
            if src == initiator:
                if r.get("always"):
                    r.pop("always", None)
                    changed = True
                if r.get("exclusive_group"):
                    r.pop("exclusive_group", None)
                    changed = True
                has_init_to_done = True
        if src == _INVOICE_CC_SALES_DONE and tgt == "end":
            has_done_to_end = True
        if src == initiator and tgt == "end":
            r["source"] = _INVOICE_CC_SALES_DONE
            r.pop("exclusive_group", None)
            changed = True
            has_done_to_end = True

    if not has_init_to_done:
        routes.append({
            "id": "r_n4_cc_sales_done",
            "source": initiator,
            "target": _INVOICE_CC_SALES_DONE,
        })
        changed = True
    if not has_done_to_end:
        routes.append({
            "id": "r_cc_sales_done_end",
            "source": _INVOICE_CC_SALES_DONE,
            "target": "end",
        })
        changed = True
    return changed


def _flow_missing_cs_sales_cc_on_start(
    nodes: list | None, routes: list | None = None,
) -> bool:
    """客服类表单：缺少发起旁路抄送业务员。"""
    if not isinstance(nodes, list):
        return True
    by_id = {n.get("id"): n for n in nodes if isinstance(n, dict) and n.get("id")}
    n = by_id.get(_CS_SALES_CC_ON_START)
    if not n or n.get("type") != "cc":
        return True
    rule = n.get("approver_rule") or {}
    if rule.get("type") != "form_field_person" or rule.get("value") != "sales_person":
        return True
    if n.get("name") != _CS_SALES_CC_ON_START_NAME:
        return True
    for r in routes or []:
        if not isinstance(r, dict):
            continue
        if (
            r.get("source") == "start"
            and r.get("target") == _CS_SALES_CC_ON_START
            and r.get("always")
        ):
            return False
    return True


def apply_cs_sales_cc_on_start(nodes: list[dict], routes: list[dict]) -> bool:
    """客服三类表单：发起后立即旁路抄送表单「业务员」字段对应人员。"""
    if not isinstance(nodes, list) or not isinstance(routes, list):
        return False
    if not _flow_missing_cs_sales_cc_on_start(nodes, routes):
        return False
    changed = False
    by_id = {n.get("id"): n for n in nodes if isinstance(n, dict) and n.get("id")}
    want = _cc_node(
        _CS_SALES_CC_ON_START,
        _CS_SALES_CC_ON_START_NAME,
        {"type": "form_field_person", "value": "sales_person"},
    )
    cur = by_id.get(_CS_SALES_CC_ON_START)
    if not cur:
        nodes.append(want)
        by_id[_CS_SALES_CC_ON_START] = want
        changed = True
    else:
        if cur.get("type") != "cc" or cur.get("name") != _CS_SALES_CC_ON_START_NAME:
            cur["type"] = "cc"
            cur["name"] = _CS_SALES_CC_ON_START_NAME
            changed = True
        rule = cur.get("approver_rule") or {}
        if rule.get("type") != "form_field_person" or rule.get("value") != "sales_person":
            cur["approver_rule"] = {"type": "form_field_person", "value": "sales_person"}
            changed = True
    has_start_route = False
    for r in routes:
        if not isinstance(r, dict):
            continue
        if r.get("source") == "start" and r.get("target") == _CS_SALES_CC_ON_START:
            has_start_route = True
            if not r.get("always"):
                r["always"] = True
                changed = True
    if not has_start_route:
        routes.append({
            "id": "r_start_cc_sales_on_start",
            "source": "start",
            "target": _CS_SALES_CC_ON_START,
            "always": True,
        })
        changed = True
    return changed


def _tech_fb_cc_applicant_rule() -> dict:
    return {
        "type": "mixed",
        "value": [
            {"type": "creator"},
            {"type": "form_field_person", "value": "applicant"},
        ],
    }


def _tech_fb_cc_notify1_rule() -> dict:
    return {
        "type": "mixed",
        "value": [
            {"type": "form_field_person", "value": "order_person"},
            {"type": "form_field_person", "value": "applicant"},
        ],
    }


def build_tech_agreement_feedback_flow() -> tuple[list[dict], list[dict]]:
    """技术协议反馈单：对齐简道云流程设计（中央研究院；workflow API 未取到时按实单拓扑）。"""
    fb_fields = ["business_feedback", "feedback_suggestion"]
    nodes: list[dict] = [
        {"id": "start", "type": "start", "name": "发起"},
        _cc_node(
            _TECH_FB_CC_SALES, _TECH_FB_CC_SALES_NAME,
            {"type": "form_field_person", "value": "salesperson"},
        ),
        {
            "id": "n_design_review", "type": "approval", "name": "设计审核",
            "approver_rule": {"type": "form_field_person", "value": "design_reviewer"},
            "multi_mode": "or_sign", "empty_strategy": "auto_approve",
        },
        {
            "id": "n_chief_opinion", "type": "approval", "name": "总工意见",
            "approver_rule": {
                "type": "specified_user", "value": "02364335378133",
                "exclude_initiator": True, "jdy_role_hint": "总工意见",
            },
            "multi_mode": "or_sign", "empty_strategy": "auto_approve",
        },
        {
            "id": "n_clerk_arrange", "type": "approval", "name": "内勤安排",
            "approver_rule": {"type": "form_field_person", "value": "dept_clerk"},
            "multi_mode": "or_sign", "empty_strategy": "auto_approve",
        },
        {
            "id": "n_clerk_verify", "type": "approval", "name": "内勤核查",
            "approver_rule": {"type": "form_field_person", "value": "dept_clerk"},
            "multi_mode": "or_sign", "empty_strategy": "auto_approve",
        },
        {
            "id": "n_sales", "type": "approval", "name": "业务员",
            "approver_rule": {"type": "form_field_person", "value": "salesperson"},
            "multi_mode": "or_sign", "empty_strategy": "auto_approve",
            "field_perms": [{"field": f, "access": "editable"} for f in fb_fields],
        },
        {
            "id": "n_finance", "type": "approval", "name": "财务核算",
            "approver_rule": {
                "type": "specified_user", "value": "0433406811775721",
                "exclude_initiator": True, "jdy_role_hint": "财务核算",
            },
            "multi_mode": "or_sign", "empty_strategy": "auto_approve",
        },
        {
            "id": "n_dept_opinion", "type": "approval", "name": "部门意见",
            "approver_rule": {"type": "dept_head", "exclude_initiator": True},
            "multi_mode": "or_sign", "empty_strategy": "auto_approve",
        },
        {
            "id": "n_gm", "type": "approval", "name": "总经理审批",
            "approver_rule": {
                "type": "specified_user", "value": "02336214315748",
                "exclude_initiator": True, "jdy_role_hint": "总经理审批",
            },
            "multi_mode": "or_sign", "empty_strategy": "auto_approve",
        },
        _cc_node("cc_notify_dist", "通知分发", {
            "type": "specified_role", "value": "procurement",
            "exclude_initiator": True, "jdy_role_hint": "通知采购",
        }),
        _cc_node("cc_notify1", "通知1", _tech_fb_cc_notify1_rule()),
        _cc_node(
            "cc_notify2", "通知2",
            {"type": "form_field_person_multi", "value": "transfer_rd_centers"},
        ),
        _cc_node(
            _TECH_FB_CC_APPLICANT, _TECH_FB_CC_APPLICANT_NAME,
            _tech_fb_cc_applicant_rule(),
        ),
        {"id": "end", "type": "end", "name": "结束"},
    ]
    routes: list[dict] = [
        {"id": "r_start_cc_sales", "source": "start", "target": _TECH_FB_CC_SALES, "always": True},
        {"id": "r_start_design", "source": "start", "target": "n_design_review"},
        {"id": "r_design_chief", "source": "n_design_review", "target": "n_chief_opinion"},
        {"id": "r_chief_arrange", "source": "n_chief_opinion", "target": "n_clerk_arrange", "always": True},
        {"id": "r_chief_verify", "source": "n_chief_opinion", "target": "n_clerk_verify", "always": True},
        {"id": "r_arrange_verify", "source": "n_clerk_arrange", "target": "n_clerk_verify"},
        {
            "id": "r_verify_finance_empty", "source": "n_clerk_verify", "target": "n_finance",
            "exclusive_group": "ex_sales",
            "condition": {"field": "salesperson", "operator": "is_empty"},
        },
        {
            "id": "r_verify_sales", "source": "n_clerk_verify", "target": "n_sales",
            "exclusive_group": "ex_sales",
            "condition": {"field": "salesperson", "operator": "is_not_empty"},
        },
        {"id": "r_sales_finance", "source": "n_sales", "target": "n_finance"},
        {"id": "r_sales_cc_app", "source": "n_sales", "target": _TECH_FB_CC_APPLICANT, "always": True},
        {"id": "r_finance_dept", "source": "n_finance", "target": "n_dept_opinion"},
        {"id": "r_dept_gm", "source": "n_dept_opinion", "target": "n_gm"},
        {"id": "r_gm_end", "source": "n_gm", "target": "end"},
        {
            "id": "r_gm_notify_dist", "source": "n_gm", "target": "cc_notify_dist",
            "always": True,
            "condition": {"field": "notify_purchase", "operator": "eq", "value": "需要"},
        },
        {"id": "r_gm_notify1", "source": "n_gm", "target": "cc_notify1", "always": True},
        {
            "id": "r_notify1_notify2", "source": "cc_notify1", "target": "cc_notify2",
            "always": True,
            "condition": {"field": "transfer_rd_centers", "operator": "is_not_empty"},
        },
    ]
    return nodes, routes


def _flow_is_jdy_tech_agreement_feedback(
    nodes: list | None, routes: list | None = None,
) -> bool:
    """已对齐简道云技术协议反馈单完整拓扑。"""
    if not isinstance(nodes, list):
        return False
    names = {n.get("name") for n in nodes if isinstance(n, dict)}
    by_id = {n.get("id"): n for n in nodes if isinstance(n, dict) and n.get("id")}
    cc = by_id.get(_TECH_FB_CC_SALES) or {}
    rule = cc.get("approver_rule") or {}
    need_names = (
        "设计审核", "总工意见", "内勤核查", "财务核算", "部门意见", "总经理审批",
    )
    if not all(n in names for n in need_names):
        return False
    if cc.get("type") != "cc":
        return False
    if rule.get("type") != "form_field_person" or rule.get("value") != "salesperson":
        return False
    if by_id.get("n_chief_opinion", {}).get("type") != "approval":
        return False
    if routes is None:
        return len(nodes) >= 14
    pairs = {
        (r.get("source"), r.get("target"))
        for r in (routes or []) if isinstance(r, dict)
    }
    if ("start", _TECH_FB_CC_SALES) not in pairs:
        return False
    if ("n_clerk_verify", "n_finance") not in pairs and ("n_sales", "n_finance") not in pairs:
        return False
    if ("n_gm", "end") not in pairs:
        return False
    for r in routes or []:
        if not isinstance(r, dict):
            continue
        src, tgt = r.get("source"), r.get("target")
        if src in (_TECH_FB_CC_SALES, _TECH_FB_CC_APPLICANT, "cc_notify_dist", "cc_notify1", "cc_notify2") and tgt == "end":
            return False
    return len(nodes) >= 14


def _flow_missing_tech_agreement_feedback_flow(
    nodes: list | None, routes: list | None = None,
) -> bool:
    """技术协议反馈单：未对齐简道云完整拓扑。"""
    return not _flow_is_jdy_tech_agreement_feedback(nodes, routes)


def apply_tech_agreement_feedback_flow(nodes: list[dict], routes: list[dict]) -> bool:
    """技术协议反馈单：旧拓扑/兜底图 → 简道云对齐完整流程。"""
    if not isinstance(nodes, list) or not isinstance(routes, list):
        return False
    if _flow_is_jdy_tech_agreement_feedback(nodes, routes):
        return False
    built_nodes, built_routes = build_tech_agreement_feedback_flow()
    nodes[:] = built_nodes
    routes[:] = built_routes
    return True


def _flow_is_jdy_payment(nodes: list | None) -> bool:
    """已对齐简道云收款登记：按部门分支的多路内勤处理。"""
    names = {n.get("name") for n in (nodes or [])}
    return "内勤处理" in names and "采购" in names and len(nodes or []) >= 15


_PAYMENT_CC_NODE_IDS = frozenset({"n24", "n25", "n27"})
# 简道云 ccUsers.deptManager.deptWidgets → 表单「部门」字段负责人
_PAYMENT_CC_DEPT_HEAD = {
    "type": "form_field_dept",
    "value": "department",
    "exclude_initiator": True,
}
# 简道云 ccUsers.widgets → 表单「业务人员」
_PAYMENT_CC_SALES_PERSON = {
    "type": "form_field_person",
    "value": "sales_person",
}
# 曾误对齐为 userWidgets/业务人员部门负责人，升级时移除
_PAYMENT_CC_WRONG_PERSON_DEPT_HEAD = {
    "type": "form_field_person_dept_head",
    "value": "sales_person",
}


def _approver_rule_has_sub_type(rule: dict | None, sub_type: str) -> bool:
    rule = rule or {}
    if rule.get("type") == sub_type:
        return True
    if rule.get("type") != "mixed":
        return False
    return any(
        isinstance(sub, dict) and sub.get("type") == sub_type
        for sub in (rule.get("value") or [])
    )


def _approver_rule_has_sub(rule: dict | None, want: dict) -> bool:
    """mixed 或单条规则是否已含指定子规则（type + value）。"""
    rule = rule or {}
    if rule.get("type") == want.get("type") and _approver_rule_value_equal(
        rule.get("value"), want.get("value"),
    ):
        return True
    if rule.get("type") != "mixed":
        return False
    for sub in rule.get("value") or []:
        if not isinstance(sub, dict):
            continue
        if sub.get("type") == want.get("type") and _approver_rule_value_equal(
            sub.get("value"), want.get("value"),
        ):
            return True
    return False


def _ensure_mixed_sub(rule: dict | None, sub: dict) -> tuple[dict, bool]:
    """在主抄送规则上叠加子规则（保留原有指定人员等）。"""
    rule = rule or {"type": "specified_user", "value": []}
    if _approver_rule_has_sub(rule, sub):
        return rule, False
    if rule.get("type") == "mixed":
        value = [dict(x) for x in rule.get("value") or [] if isinstance(x, dict)]
        value.append(dict(sub))
        return {"type": "mixed", "value": value}, True
    return {"type": "mixed", "value": [dict(rule), dict(sub)]}, True


def _remove_mixed_sub(rule: dict | None, sub_type: str) -> tuple[dict, bool]:
    """从 mixed 规则中移除指定 type 的子规则（单条则降级为唯一子规则）。"""
    rule = rule or {}
    if rule.get("type") != "mixed":
        if rule.get("type") == sub_type:
            return {"type": "specified_user", "value": []}, True
        return rule, False
    value = [dict(x) for x in rule.get("value") or [] if isinstance(x, dict)]
    new_value = [x for x in value if x.get("type") != sub_type]
    if len(new_value) == len(value):
        return rule, False
    if len(new_value) == 1:
        return new_value[0], True
    if not new_value:
        return {"type": "specified_user", "value": []}, True
    return {"type": "mixed", "value": new_value}, True


def _flow_payment_cc_needs_dept_head(nodes: list | None) -> bool:
    """收款登记抄送缺少部门负责人或表单业务人员。"""
    for n in nodes or []:
        if not isinstance(n, dict) or n.get("type") != "cc":
            continue
        nid = str(n.get("id") or "")
        if nid not in _PAYMENT_CC_NODE_IDS:
            continue
        rule = n.get("approver_rule") or {}
        if not _approver_rule_has_sub(rule, _PAYMENT_CC_DEPT_HEAD):
            return True
        if not _approver_rule_has_sub(rule, _PAYMENT_CC_SALES_PERSON):
            return True
        if _approver_rule_has_sub_type(rule, "dept_head"):
            return True
        if _approver_rule_has_sub(rule, _PAYMENT_CC_WRONG_PERSON_DEPT_HEAD):
            return True
    return False


def apply_payment_registration_cc_dept_head(nodes: list[dict] | None) -> bool:
    """收款登记：抄送叠加表单部门负责人 + 业务人员（n24/n25/n27）。"""
    if not nodes:
        return False
    changed = False
    for n in nodes:
        if not isinstance(n, dict) or n.get("type") != "cc":
            continue
        nid = str(n.get("id") or "")
        if nid not in _PAYMENT_CC_NODE_IDS:
            continue
        rule = n.get("approver_rule") or {}
        for strip_type in ("dept_head", "form_field_person_dept_head"):
            rule, stripped = _remove_mixed_sub(rule, strip_type)
            if stripped:
                changed = True
        n["approver_rule"] = rule
        for sub in (_PAYMENT_CC_DEPT_HEAD, _PAYMENT_CC_SALES_PERSON):
            new_rule, did = _ensure_mixed_sub(n.get("approver_rule"), sub)
            if did:
                n["approver_rule"] = new_rule
                changed = True
    return changed


def _flow_is_jdy_quote(nodes: list | None) -> bool:
    """已对齐简道云核价管理流程：财务核价 + 部门审批分支。"""
    names = {n.get("name") for n in (nodes or [])}
    return "财务核价" in names and "部门审批" in names and len(nodes or []) >= 15


def _flow_is_jdy_presale_service_notice(nodes: list | None) -> bool:
    """已对齐简道云售前服务通知：总工审批 + 人员协调 + 新疆威猛分支。"""
    names = {n.get("name") for n in (nodes or [])}
    return "总工审批" in names and "人员协调" in names and len(nodes or []) >= 10


def _flow_is_jdy_shipment_notice(nodes: list | None) -> bool:
    """已对齐简道云发货通知：物流审批 + 财务查款 + 开具提货单。"""
    names = {n.get("name") for n in (nodes or [])}
    return "物流审批" in names and "财务查款" in names and "开具提货单" in names and len(nodes or []) >= 15


_SHIPMENT_LOGISTICS_APPROVER = {
    "type": "specified_role",
    "value": "logistics_approval",
    "exclude_initiator": True,
    "jdy_role_hint": "物流审批",
}
_SHIPMENT_WAREHOUSE_ROLE = {
    "type": "specified_role",
    "value": "ship_sales_outbound",
    "exclude_initiator": True,
    "jdy_role_hint": "24.1发货通知流程-销售出库",
}
_SHIPMENT_GATE_ROLE = {
    "type": "specified_role",
    "value": "gate_guard",
    "exclude_initiator": True,
    "jdy_role_hint": "240706门岗保卫组",
}
_SHIPMENT_APPROVER_BY_ID: dict[str, dict] = {
    "n1": _SHIPMENT_LOGISTICS_APPROVER,
    "n8": _SHIPMENT_WAREHOUSE_ROLE,
    "n10": _SHIPMENT_WAREHOUSE_ROLE,
    "n27": _SHIPMENT_GATE_ROLE,
}
_SHIPMENT_APPROVER_BY_NAME: dict[str, dict] = {
    "物流审批": _SHIPMENT_LOGISTICS_APPROVER,
    "仓库": _SHIPMENT_WAREHOUSE_ROLE,
    "仓库判定": _SHIPMENT_WAREHOUSE_ROLE,
    "抄送门岗": _SHIPMENT_GATE_ROLE,
}


def apply_shipment_notice_approvers(nodes: list[dict]) -> bool:
    """发货通知：物流→logistics_approval；仓库/仓库判定→ship_sales_outbound；抄送门岗→gate_guard。"""
    from app.domains.lowcode.shipment_notice_fields import (
        apply_shipment_notice_sales_accept_field_perms,
    )
    changed = False
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        want = _SHIPMENT_APPROVER_BY_ID.get(str(n.get("id") or ""))
        if not want:
            want = _SHIPMENT_APPROVER_BY_NAME.get(str(n.get("name") or "").strip())
        if not want:
            continue
        cur = n.get("approver_rule") or {}
        if _approver_rule_matches(cur, want):
            continue
        n["approver_rule"] = dict(want)
        if want is _SHIPMENT_LOGISTICS_APPROVER:
            n["multi_mode"] = "or_sign"
        changed = True
    if apply_shipment_notice_sales_accept_field_perms(nodes):
        changed = True
    return changed


def _flow_shipment_logistics_needs_fix(nodes: list | None) -> bool:
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        want = _SHIPMENT_APPROVER_BY_ID.get(str(n.get("id") or ""))
        if not want:
            want = _SHIPMENT_APPROVER_BY_NAME.get(str(n.get("name") or "").strip())
        if not want:
            continue
        if not _approver_rule_matches(n.get("approver_rule") or {}, want):
            return True
    return False


def _flow_shipment_parallel_fork_broken(routes: list | None) -> bool:
    """发货通知：n3→生产领料/仓库判定误标互斥组 ex_n3（应对齐简道云并行）。"""
    from app.domains.lowcode.shipment_notice_fields import shipment_parallel_fork_broken
    return shipment_parallel_fork_broken(routes)


def _flow_has_quote_need_purchase_required(nodes: list | None) -> bool:
    """报价管理：财务核价仍把「是否转采购」标成 required（应改为可填非必填）。"""
    for n in nodes or []:
        if not isinstance(n, dict) or n.get("name") != "财务核价":
            continue
        for p in n.get("field_perms") or []:
            if isinstance(p, dict) and p.get("field") == "need_purchase":
                return p.get("access") == "required"
        return False
    return False


def apply_quote_finance_need_purchase_optional(nodes: list[dict]) -> bool:
    """就地改：财务核价.need_purchase required → editable。"""
    changed = False
    for n in nodes or []:
        if not isinstance(n, dict) or n.get("name") != "财务核价":
            continue
        perms = list(n.get("field_perms") or [])
        found = False
        for p in perms:
            if isinstance(p, dict) and p.get("field") == "need_purchase":
                if p.get("access") == "required":
                    p["access"] = "editable"
                    changed = True
                found = True
                break
        if not found:
            perms.append({"field": "need_purchase", "access": "editable"})
            changed = True
        n["field_perms"] = perms
        break
    return changed


_QUOTE_DEPT_APPROVER_FIELDS = ("customer_category", "price_type")


def _flow_has_quote_dept_approver_required(nodes: list | None) -> bool:
    """任一「部门审批」仍将客户类别/价格类型标为 required。"""
    for n in nodes or []:
        if not isinstance(n, dict) or n.get("type") != "approval":
            continue
        if n.get("name") != "部门审批":
            continue
        for p in (n.get("field_perms") or []):
            if (
                isinstance(p, dict)
                and p.get("field") in _QUOTE_DEPT_APPROVER_FIELDS
                and p.get("access") == "required"
            ):
                return True
    return False


def apply_quote_dept_approver_optional(nodes: list[dict]) -> bool:
    """就地改：部门审批.customer_category/price_type → editable（非必填）。"""
    changed = False
    for n in nodes:
        if not isinstance(n, dict) or n.get("type") != "approval":
            continue
        if n.get("name") != "部门审批":
            continue
        perms = list(n.get("field_perms") or [])
        by_field = {
            p.get("field"): p for p in perms
            if isinstance(p, dict) and p.get("field")
        }
        for fid in _QUOTE_DEPT_APPROVER_FIELDS:
            if fid in by_field:
                if by_field[fid].get("access") != "editable":
                    by_field[fid]["access"] = "editable"
                    changed = True
            else:
                perms.append({"field": fid, "access": "editable"})
                changed = True
        n["field_perms"] = perms
    return changed


def _flow_missing_quote_notify_initiator(nodes: list | None) -> bool:
    """报价管理仍存在「通知尚高华」或 n7 未指向发起人。"""
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        if n.get("name") == "通知尚高华":
            return True
        if n.get("id") == "n7":
            rule = n.get("approver_rule") or {}
            if n.get("name") != "通知发起人" or rule.get("type") != "creator":
                return True
    return False


def apply_quote_notify_initiator(nodes: list[dict]) -> bool:
    """就地改：通知尚高华 → 通知发起人（creator）。"""
    changed = False
    for n in nodes:
        if not isinstance(n, dict):
            continue
        if n.get("id") != "n7" and n.get("name") != "通知尚高华":
            continue
        if n.get("name") != "通知发起人":
            n["name"] = "通知发起人"
            changed = True
        rule = n.get("approver_rule") or {}
        if rule.get("type") != "creator":
            n["approver_rule"] = {"type": "creator"}
            changed = True
        break
    return changed


# 报价：简道云一人角色 / 冶金专属角色 → 具名用户或可选范围（勿用空的 sales_manager）
_QUOTE_ROLE_APPROVER_BY_ID: dict[str, dict] = {
    "n10": {  # 王玲玲审批
        "type": "specified_user", "value": "01000533004677",
        "exclude_initiator": True, "jdy_role_hint": "王玲玲",
    },
    "n11": {  # 经理审批 ← 热能利用-段荣凯
        "type": "specified_user", "value": "02364714147257",
        "exclude_initiator": True, "jdy_role_hint": "热能利用-段荣凯",
    },
    "n12": {  # 热能
        "type": "specified_user", "value": "02364714147257",
        "exclude_initiator": True, "jdy_role_hint": "热能利用-段荣凯",
    },
    "n14": {  # 冶金装备销售事业部
        "type": "pickable_scope", "value": "quote_metallurgy",
        "exclude_initiator": True, "jdy_role_hint": "27.7核价管理流程-冶金",
    },
}


def _flow_quote_needs_named_role_approvers(nodes: list | None) -> bool:
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        want = _QUOTE_ROLE_APPROVER_BY_ID.get(str(n.get("id") or ""))
        if not want:
            continue
        rule = n.get("approver_rule") or {}
        if rule.get("type") != want.get("type") or rule.get("value") != want.get("value"):
            return True
    return False


def apply_quote_named_role_approvers(nodes: list[dict]) -> bool:
    """就地改：报价角色审批对齐合同式具名用户 / 可选范围。"""
    changed = False
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        want = _QUOTE_ROLE_APPROVER_BY_ID.get(str(n.get("id") or ""))
        if not want:
            continue
        cur = n.get("approver_rule") or {}
        if cur.get("type") == want["type"] and cur.get("value") == want["value"]:
            continue
        n["approver_rule"] = dict(want)
        changed = True
    return changed


_CS_REPLACE_CS_USERS = {
    "type": "specified_role",
    "value": "cs_office",
    "exclude_initiator": True,
    "jdy_role_hint": "7.1.2售出产品更换（补发）流程-客服补登",
}
_CS_REPLACE_BIZ_MGR = {
    "type": "form_field_person_dept_head",
    "value": "sales_person",
    "exclude_initiator": True,
}
_CS_REPLACE_CHIEF = {
    "type": "specified_user",
    "value": "02364335378133",
    "exclude_initiator": True,
    "jdy_role_hint": "7.1.1售后服务申请及反馈-总工审批",
}
_CS_REPLACE_CEO = {
    "type": "specified_user",
    "value": "02336214315748",
    "exclude_initiator": True,
    "jdy_role_hint": "总经理",
}
_CS_REPLACE_WANG = {
    "type": "specified_user",
    "value": "01000533004677",
    "exclude_initiator": True,
    "jdy_role_hint": "7.1.1售后服务申请及反馈-王玲玲",
}
_CS_REPLACE_DUAN = {
    "type": "specified_user",
    "value": "02364714147257",
    "exclude_initiator": True,
    "jdy_role_hint": "热能利用-段荣凯",
}
_CS_REPLACE_FINANCE = {
    "type": "specified_user",
    "value": "0433406811775721",
    "exclude_initiator": True,
    "jdy_role_hint": "7.1.2售出产品更换（补发）流程-财务开票抄送",
}


def _approver_rule_value_equal(a: object, b: object) -> bool:
    if isinstance(a, list) and isinstance(b, list):
        return sorted(str(x) for x in a) == sorted(str(x) for x in b)
    return a == b


def _approver_rule_matches(have: dict, want: dict) -> bool:
    return (
        have.get("type") == want.get("type")
        and _approver_rule_value_equal(have.get("value"), want.get("value"))
    )


def _flow_cs_product_replace_needs_approver_fix(nodes: list | None) -> bool:
    want_by_id = {
        "n1": _CS_REPLACE_BIZ_MGR,
        "n4": _CS_REPLACE_CS_USERS,
        "n6": _CS_REPLACE_CHIEF,
        "n8": _CS_REPLACE_CEO,
        "n9": _CS_REPLACE_CS_USERS,
        "n12": _CS_REPLACE_WANG,
        "n16": _CS_REPLACE_CS_USERS,
        "n17": _CS_REPLACE_DUAN,
        "n18": _CS_REPLACE_FINANCE,
    }
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        want = want_by_id.get(str(n.get("id") or ""))
        if not want:
            continue
        rule = n.get("approver_rule") or {}
        if not _approver_rule_matches(rule, want):
            return True
    return _cs_product_replace_field_12_needs_required(nodes)


def apply_cs_product_replace_approvers(nodes: list[dict]) -> bool:
    """售出产品更换：客服节点→cs_office；业务经理=业务员部门负责人。"""
    want_by_id = {
        "n1": _CS_REPLACE_BIZ_MGR,
        "n4": _CS_REPLACE_CS_USERS,
        "n6": _CS_REPLACE_CHIEF,
        "n8": _CS_REPLACE_CEO,
        "n9": _CS_REPLACE_CS_USERS,
        "n12": _CS_REPLACE_WANG,
        "n16": _CS_REPLACE_CS_USERS,
        "n17": _CS_REPLACE_DUAN,
        "n18": _CS_REPLACE_FINANCE,
    }
    changed = False
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        want = want_by_id.get(str(n.get("id") or ""))
        if want:
            cur = n.get("approver_rule") or {}
            if not _approver_rule_matches(cur, want):
                n["approver_rule"] = dict(want)
                changed = True
        # 客服补登：换货明细须填故障分类 → field_12 标 required（明细审批列仅 required 时校验）
        nid = str(n.get("id") or "")
        name = (n.get("name") or "").strip()
        if nid == "n9" or name == "客服补登":
            perms = n.get("field_perms")
            if isinstance(perms, list):
                new_perms: list = []
                touched = False
                for p in perms:
                    if isinstance(p, dict) and p.get("field") == "field_12" and p.get("access") != "required":
                        new_perms.append({**p, "access": "required"})
                        touched = True
                    else:
                        new_perms.append(p)
                if touched:
                    n["field_perms"] = new_perms
                    changed = True
    return changed


def _cs_product_replace_field_12_needs_required(nodes: list | None) -> bool:
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        if str(n.get("id") or "") != "n9" and (n.get("name") or "").strip() != "客服补登":
            continue
        for p in n.get("field_perms") or []:
            if isinstance(p, dict) and p.get("field") == "field_12" and p.get("access") != "required":
                return True
    return False


def apply_cs_product_return_logistics_field_perms(nodes: list[dict]) -> bool:
    """物流中心：不把退回明细放进本节点可填区（避免误强制「仓库判定」）；只填物流情况。"""
    changed = False
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        nid = str(n.get("id") or "")
        name = (n.get("name") or "").strip()
        if nid != "n17" and "物流" not in name:
            continue
        perms = n.get("field_perms")
        if not isinstance(perms, list):
            continue
        new_perms = [
            p for p in perms
            if not (isinstance(p, dict) and p.get("field") == "field_7")
        ]
        if len(new_perms) != len(perms):
            n["field_perms"] = new_perms
            changed = True
    return changed


def _flow_cs_product_return_needs_logistics_field_fix(nodes: list | None) -> bool:
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        nid = str(n.get("id") or "")
        name = (n.get("name") or "").strip()
        if nid != "n17" and "物流" not in name:
            continue
        for p in n.get("field_perms") or []:
            if isinstance(p, dict) and p.get("field") == "field_7":
                return True
    return False


# 简道云「客户服务申请及反馈」客服落实 ← 角色 230902客服内勤（CRM: cs_office）
_CS_SERVICE_CS_OFFICE_ROLE = {
    "type": "specified_role",
    "value": "cs_office",
    "exclude_initiator": True,
    "jdy_role_hint": "230902客服内勤",
}
# 简道云「客户服务申请及反馈」客服安排1 ← 角色 服务申请及反馈-客服安排（CRM: cs_arrange）
_CS_SERVICE_CS_ARRANGE_ROLE = {
    "type": "specified_role",
    "value": "cs_arrange",
    "exclude_initiator": True,
    "jdy_role_hint": "服务申请及反馈-客服安排",
}
_CS_SERVICE_CHIEF = {
    "type": "specified_user",
    "value": "02364335378133",  # 曹修国
    "exclude_initiator": True,
    "jdy_role_hint": "7.1.1售后服务申请及反馈-总工审批",
}
_CS_SERVICE_CEO = {
    "type": "specified_user",
    "value": "02336214315748",  # 王思民
    "exclude_initiator": True,
    "jdy_role_hint": "总经理",
}
_CS_SERVICE_CS_LEADER_FIELD = {
    "type": "form_field_person",
    "value": "field_37",  # 客服组长（客服落实节点填写）
}
# 按节点 id / 名称 纠正审批人（勿用空 sales_manager / 勿写死指定人员）
_CS_SERVICE_APPROVER_BY_ID: dict[str, dict] = {
    "n2": _CS_SERVICE_CS_OFFICE_ROLE,  # 客服落实
    "n4": _CS_SERVICE_CHIEF,  # 总工审批
    "n5": _CS_SERVICE_CEO,  # 总经理
    "n6__1": _CS_SERVICE_CS_ARRANGE_ROLE,  # 客服安排1
    "n21": _CS_SERVICE_CEO,
    "n24": _CS_SERVICE_CS_LEADER_FIELD,  # 客服组长
}
_CS_SERVICE_APPROVER_BY_NAME: dict[str, dict] = {
    "客服落实": _CS_SERVICE_CS_OFFICE_ROLE,
    "客服安排1": _CS_SERVICE_CS_ARRANGE_ROLE,
    "总工审批": _CS_SERVICE_CHIEF,
    "客服组长": _CS_SERVICE_CS_LEADER_FIELD,
}


def _flow_cs_service_request_needs_approver_fix(nodes: list[dict] | None) -> bool:
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        want = _CS_SERVICE_APPROVER_BY_ID.get(str(n.get("id") or ""))
        if not want:
            want = _CS_SERVICE_APPROVER_BY_NAME.get(str(n.get("name") or "").strip())
        if not want:
            continue
        if not _approver_rule_matches(n.get("approver_rule") or {}, want):
            return True
    return False


def apply_cs_service_request_approvers(nodes: list[dict]) -> bool:
    """客户服务申请及反馈：客服落实→cs_office；客服安排1→cs_arrange。"""
    changed = False
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        want = _CS_SERVICE_APPROVER_BY_ID.get(str(n.get("id") or ""))
        if not want:
            want = _CS_SERVICE_APPROVER_BY_NAME.get(str(n.get("name") or "").strip())
        if not want:
            continue
        cur = n.get("approver_rule") or {}
        if _approver_rule_matches(cur, want):
            continue
        n["approver_rule"] = dict(want)
        changed = True
    return changed


_CS_DELAY_FEEDBACK_ROLE = {
    "type": "specified_role",
    "value": "cs_office",
    "exclude_initiator": True,
    "jdy_role_hint": "7.5客户服务延期申请-客服反馈",
}
_CS_DELAY_APPROVE_ROLE = {
    "type": "specified_role",
    "value": "cs_delay_approve",
    "exclude_initiator": True,
    "jdy_role_hint": "7.5客户服务延期申请-客服审批",
}
_CS_DELAY_APPROVER_BY_ID: dict[str, dict] = {
    "n3": _CS_DELAY_FEEDBACK_ROLE,
    "n4": _CS_DELAY_APPROVE_ROLE,
    "n7": _CS_DELAY_FEEDBACK_ROLE,
}
_CS_DELAY_APPROVER_BY_NAME: dict[str, dict] = {
    "客服反馈": _CS_DELAY_FEEDBACK_ROLE,
    "客服审批": _CS_DELAY_APPROVE_ROLE,
    "客服备案": _CS_DELAY_FEEDBACK_ROLE,
}


def _flow_cs_service_delay_needs_approver_fix(nodes: list | None) -> bool:
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        want = _CS_DELAY_APPROVER_BY_ID.get(str(n.get("id") or ""))
        if not want:
            want = _CS_DELAY_APPROVER_BY_NAME.get(str(n.get("name") or "").strip())
        if not want:
            continue
        if not _approver_rule_matches(n.get("approver_rule") or {}, want):
            return True
    return False


def apply_cs_service_delay_approvers(nodes: list[dict]) -> bool:
    """客户服务延期申请：客服反馈/备案→cs_office；客服审批→cs_delay_approve。"""
    changed = False
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        want = _CS_DELAY_APPROVER_BY_ID.get(str(n.get("id") or ""))
        if not want:
            want = _CS_DELAY_APPROVER_BY_NAME.get(str(n.get("name") or "").strip())
        if not want:
            continue
        cur = n.get("approver_rule") or {}
        if _approver_rule_matches(cur, want):
            continue
        n["approver_rule"] = dict(want)
        changed = True
    return changed


_CS_CORRESPONDENCE_OFFICE_ROLE = {
    "type": "specified_role",
    "value": "cs_office",
    "exclude_initiator": True,
    "jdy_role_hint": "230902客服内勤",
}
_CS_CORRESPONDENCE_APPROVER_BY_ID: dict[str, dict] = {
    "n3": _CS_CORRESPONDENCE_OFFICE_ROLE,  # 内勤办理
}
_CS_CORRESPONDENCE_APPROVER_BY_NAME: dict[str, dict] = {
    "内勤办理": _CS_CORRESPONDENCE_OFFICE_ROLE,
}


def _flow_cs_correspondence_needs_approver_fix(nodes: list | None) -> bool:
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        want = _CS_CORRESPONDENCE_APPROVER_BY_ID.get(str(n.get("id") or ""))
        if not want:
            want = _CS_CORRESPONDENCE_APPROVER_BY_NAME.get(str(n.get("name") or "").strip())
        if not want:
            continue
        if not _approver_rule_matches(n.get("approver_rule") or {}, want):
            return True
    return False


def apply_cs_correspondence_approvers(nodes: list[dict]) -> bool:
    """客服往来函件：内勤办理→cs_office。"""
    changed = False
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        want = _CS_CORRESPONDENCE_APPROVER_BY_ID.get(str(n.get("id") or ""))
        if not want:
            want = _CS_CORRESPONDENCE_APPROVER_BY_NAME.get(str(n.get("name") or "").strip())
        if not want:
            continue
        cur = n.get("approver_rule") or {}
        if _approver_rule_matches(cur, want):
            continue
        n["approver_rule"] = dict(want)
        changed = True
    return changed


_XUNHAN_LEGAL_ROLE = {
    "type": "specified_role",
    "value": "legal",
    "exclude_initiator": True,
    "jdy_role_hint": "24.2.3合同/项目评审-法务审批多人",
}
_XUNHAN_APPROVER_BY_ID: dict[str, dict] = {
    "n3": _XUNHAN_LEGAL_ROLE,
}
_XUNHAN_APPROVER_BY_NAME: dict[str, dict] = {
    "法务审批": _XUNHAN_LEGAL_ROLE,
}


def _flow_xunhan_contract_review_needs_approver_fix(nodes: list | None) -> bool:
    if _legal_sup_approver_needs_fix(nodes):
        return True
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        want = _XUNHAN_APPROVER_BY_ID.get(str(n.get("id") or ""))
        if not want:
            want = _XUNHAN_APPROVER_BY_NAME.get(str(n.get("name") or "").strip())
        if not want:
            continue
        if not _approver_rule_matches(n.get("approver_rule") or {}, want):
            return True
    return False


def apply_xunhan_contract_review_approvers(nodes: list[dict]) -> bool:
    """迅焊公司合同评审：法务审批→legal；法务主管→袁文俊。"""
    changed = False
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        want = _XUNHAN_APPROVER_BY_ID.get(str(n.get("id") or ""))
        if not want:
            want = _XUNHAN_APPROVER_BY_NAME.get(str(n.get("name") or "").strip())
        if not want:
            continue
        cur = n.get("approver_rule") or {}
        if _approver_rule_matches(cur, want):
            continue
        n["approver_rule"] = dict(want)
        changed = True
    if apply_legal_sup_named_approver(nodes):
        changed = True
    return changed


_XUNHAN_FEEDBACK_REENTER_EDGES: tuple[tuple[str, str], ...] = (
    ("n12", "n1__2"),      # 信息反馈 → 业务部门2
    ("n1__2", "n28__1"),   # 业务部门2 → 设计审批1（反馈回路）
    ("n28__1", "n5"),      # 设计审批1 → 总经理（第二轮）
    ("n5", "n6"),          # 总经理 → 财务意见（第二轮）
    ("n6", "n12"),         # 财务意见 → 信息反馈（多轮反馈）
)


def patch_xunhan_contract_review_feedback_routes(routes: list[dict]) -> bool:
    """反馈回路/第二轮主干：已完成节点须 reenter，否则 skip_reactivate 卡死。"""
    changed = False
    want = set(_XUNHAN_FEEDBACK_REENTER_EDGES)
    for r in routes or []:
        if not isinstance(r, dict):
            continue
        edge = (str(r.get("source") or ""), str(r.get("target") or ""))
        if edge in want and not r.get("reenter"):
            r["reenter"] = True
            changed = True
    return changed


def _flow_xunhan_feedback_routes_need_fix(routes: list | None) -> bool:
    want = set(_XUNHAN_FEEDBACK_REENTER_EDGES)
    got = {
        (str(r.get("source") or ""), str(r.get("target") or ""))
        for r in (routes or [])
        if isinstance(r, dict) and r.get("reenter")
    }
    return bool(want - got)


# 通知生产：简道云启用抄送（吕英萍、雷贤、吴超）
_PROD_NOTIFY_CC_USERNAMES: list[str] = [
    "02364437547295",  # 吕英萍
    "02362247571234189",  # 雷贤
    "1739424832704465",  # 吴超
]
_PROD_NOTIFY_CC_RULE: dict = {
    "type": "specified_user",
    "value": list(_PROD_NOTIFY_CC_USERNAMES),
}


def _cc_rule_matches(cur: dict | None, want: dict) -> bool:
    if not isinstance(cur, dict):
        return False
    if cur.get("type") != want.get("type"):
        return False
    cv = cur.get("value")
    wv = want.get("value")
    if isinstance(wv, list):
        if not isinstance(cv, list):
            return False
        return sorted(str(x) for x in cv) == sorted(str(x) for x in wv)
    return cv == wv


def _flow_prod_card_notify_cc_needs_fix(nodes: list | None) -> bool:
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        if str(n.get("name") or "") != "通知生产":
            continue
        if n.get("type") != "approval":
            continue
        if not _cc_rule_matches(n.get("cc_rule"), _PROD_NOTIFY_CC_RULE):
            return True
    return False


def apply_prod_card_notify_production_cc(nodes: list[dict] | None) -> bool:
    """生产卡「通知生产」启用抄送：吕英萍、雷贤、吴超（对齐简道云）。"""
    if not nodes:
        return False
    changed = False
    for n in nodes:
        if not isinstance(n, dict):
            continue
        if str(n.get("name") or "") != "通知生产":
            continue
        if n.get("type") != "approval":
            continue
        if _cc_rule_matches(n.get("cc_rule"), _PROD_NOTIFY_CC_RULE):
            continue
        n["cc_rule"] = dict(_PROD_NOTIFY_CC_RULE)
        changed = True
    return changed


_PROD_MATERIAL_ROLE = {
    "type": "specified_role",
    "value": "prod_material_code",
    "exclude_initiator": True,
    "jdy_role_hint": "1.2.8生产卡/补充流程-物料编码",
}
_PROD_LEGAL_ROLE = {
    "type": "specified_role",
    "value": "legal",
    "exclude_initiator": True,
    "jdy_role_hint": "法务办理",
}
_PROD_ELEC_WORKSHOP_ROLE = {
    "type": "specified_role",
    "value": "prod_elec_workshop",
    "exclude_initiator": True,
    "jdy_role_hint": "1.2.8生产卡/补充流程-电气车间",
}
_PROD_CARD_APPROVER_BY_ID: dict[str, dict] = {
    "n5": _PROD_MATERIAL_ROLE,
    "n10": _PROD_ELEC_WORKSHOP_ROLE,
    "n45": _PROD_LEGAL_ROLE,
}
_PROD_CARD_APPROVER_BY_NAME: dict[str, dict] = {
    "物料编码": _PROD_MATERIAL_ROLE,
    "电气编码": _PROD_ELEC_WORKSHOP_ROLE,
    "法务审核": _PROD_LEGAL_ROLE,
}


def _flow_prod_card_supplement_needs_approver_fix(nodes: list | None) -> bool:
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        want = _PROD_CARD_APPROVER_BY_ID.get(str(n.get("id") or ""))
        if not want:
            want = _PROD_CARD_APPROVER_BY_NAME.get(str(n.get("name") or "").strip())
        if not want:
            continue
        if not _approver_rule_matches(n.get("approver_rule") or {}, want):
            return True
    return False


def apply_prod_card_supplement_approvers(nodes: list[dict]) -> bool:
    """生产卡补充：物料编码→prod_material_code；电气编码→prod_elec_workshop；法务审核→legal。"""
    changed = False
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        want = _PROD_CARD_APPROVER_BY_ID.get(str(n.get("id") or ""))
        if not want:
            want = _PROD_CARD_APPROVER_BY_NAME.get(str(n.get("name") or "").strip())
        if not want:
            continue
        cur = n.get("approver_rule") or {}
        if _approver_rule_matches(cur, want):
            continue
        n["approver_rule"] = dict(want)
        changed = True
    return changed


def _prod_card_nodes_named(nodes: list | None, name: str) -> set[str]:
    return {
        str(n["id"])
        for n in (nodes or [])
        if isinstance(n, dict) and n.get("id") and n.get("name") == name
    }


def apply_prod_card_finance_branch_parallel(
    nodes: list | None, routes: list | None,
) -> bool:
    """财务核价后：安排设计/通知生产/产线设计等可同时命中，对齐简道云并行分支。

    流程生成器对同源多出边一律标 ``exclusive_group``，导致「是否需研究院出图=是」
    且「不是机器人」时只走通知生产、跳过安排设计1。
    """
    finance_ids = _prod_card_nodes_named(nodes, "财务核价")
    if not finance_ids:
        return False
    changed = False
    for r in routes or []:
        if not isinstance(r, dict) or r.get("always"):
            continue
        if str(r.get("source") or "") not in finance_ids:
            continue
        if not r.get("condition"):
            continue
        if r.get("exclusive_group") or r.get("fork") != "parallel":
            r.pop("exclusive_group", None)
            r["fork"] = "parallel"
            changed = True
    return changed


def _flow_prod_card_finance_not_parallel(
    nodes: list | None, routes: list | None,
) -> bool:
    """财务核价出边仍在互斥组 → 设计分支会被通知生产吞掉。"""
    finance_ids = _prod_card_nodes_named(nodes, "财务核价")
    if not finance_ids:
        return False
    for r in routes or []:
        if not isinstance(r, dict) or r.get("always"):
            continue
        if str(r.get("source") or "") not in finance_ids:
            continue
        if r.get("condition"):
            if r.get("exclusive_group") or r.get("fork") != "parallel":
                return True
        elif r.get("exclusive_group"):
            return True
    return False


# 小萌工厂：杨霜审批 → 抄送小萌工厂（宋华强/任成双/段晓彤）∥ 结束（不加转电气车间）
_PROD_XIAOMENG_APPROVER: dict = {
    "type": "specified_user",
    "value": "02352513566524",  # 杨霜
}
_PROD_XIAOMENG_CC_RULE: dict = {
    "type": "specified_user",
    "value": [
        "246945356423206519",  # 宋华强
        "286311260320230135",  # 任成双
        "422237032327334118",  # 段晓彤
    ],
}
_PROD_XIAOMENG_CC_NODE_ID = "n_cc_xiaomeng_factory"
_PROD_XIAOMENG_CC_NODE_NAME = "抄送小萌工厂"


def _prod_card_xiaomeng_node(nodes: list | None) -> dict | None:
    for n in nodes or []:
        if isinstance(n, dict) and n.get("name") == "小萌工厂" and n.get("type") == "approval":
            return n
    return None


def _flow_prod_card_xiaomeng_needs_fix(
    nodes: list | None, routes: list | None,
) -> bool:
    xm = _prod_card_xiaomeng_node(nodes)
    if not xm:
        return False
    if not _approver_rule_matches(xm.get("approver_rule") or {}, _PROD_XIAOMENG_APPROVER):
        return True
    if xm.get("cc_rule"):
        return True
    by_id = {n.get("id"): n for n in (nodes or []) if isinstance(n, dict) and n.get("id")}
    cc = by_id.get(_PROD_XIAOMENG_CC_NODE_ID)
    if not cc or cc.get("type") != "cc" or cc.get("name") != _PROD_XIAOMENG_CC_NODE_NAME:
        return True
    if not _approver_rule_matches(cc.get("approver_rule") or {}, _PROD_XIAOMENG_CC_RULE):
        return True
    xm_id = str(xm.get("id") or "")
    pairs = {
        (str(r.get("source") or ""), str(r.get("target") or ""))
        for r in (routes or [])
        if isinstance(r, dict)
    }
    if (xm_id, "end") not in pairs:
        return True
    if (xm_id, _PROD_XIAOMENG_CC_NODE_ID) not in pairs:
        return True
    return False


def apply_prod_card_xiaomeng_yangshuang_cc(
    nodes: list | None, routes: list | None,
) -> bool:
    """生产卡「小萌工厂」：杨霜审批；审完并行抄送三人与结束（无转电气车间）。"""
    if not isinstance(nodes, list) or not isinstance(routes, list):
        return False
    xm = _prod_card_xiaomeng_node(nodes)
    if not xm:
        return False
    changed = False
    xm_id = str(xm.get("id") or "")
    if not xm_id:
        return False

    if not _approver_rule_matches(xm.get("approver_rule") or {}, _PROD_XIAOMENG_APPROVER):
        xm["approver_rule"] = dict(_PROD_XIAOMENG_APPROVER)
        changed = True
    if xm.get("multi_mode"):
        xm.pop("multi_mode", None)
        changed = True
    if xm.get("cc_rule"):
        xm.pop("cc_rule", None)
        changed = True

    by_id = {n.get("id"): n for n in nodes if isinstance(n, dict) and n.get("id")}
    want_cc = _cc_node(
        _PROD_XIAOMENG_CC_NODE_ID, _PROD_XIAOMENG_CC_NODE_NAME, dict(_PROD_XIAOMENG_CC_RULE),
    )
    cur_cc = by_id.get(_PROD_XIAOMENG_CC_NODE_ID)
    if not cur_cc:
        nodes.append(want_cc)
        changed = True
    else:
        if cur_cc.get("type") != "cc" or cur_cc.get("name") != _PROD_XIAOMENG_CC_NODE_NAME:
            cur_cc["type"] = "cc"
            cur_cc["name"] = _PROD_XIAOMENG_CC_NODE_NAME
            changed = True
        if not _approver_rule_matches(cur_cc.get("approver_rule") or {}, _PROD_XIAOMENG_CC_RULE):
            cur_cc["approver_rule"] = dict(_PROD_XIAOMENG_CC_RULE)
            changed = True

    def _ensure_out(rid: str, target: str, *, use_always_flag: bool) -> None:
        nonlocal changed
        for r in routes:
            if not isinstance(r, dict):
                continue
            if str(r.get("source") or "") != xm_id or str(r.get("target") or "") != target:
                continue
            if r.get("exclusive_group"):
                r.pop("exclusive_group", None)
                changed = True
            if use_always_flag:
                if not r.get("always"):
                    r["always"] = True
                    changed = True
                if r.get("condition") and not _route_is_always_parallel(r):
                    r.pop("condition", None)
                    changed = True
            else:
                # 结束：保留/写成恒真并行（与生成器 __always 一致）
                if not _route_is_always_parallel(r):
                    r.pop("always", None)
                    r["condition"] = {"field": "__always", "operator": "is_empty"}
                    changed = True
                if r.get("exclusive_group"):
                    r.pop("exclusive_group", None)
                    changed = True
            return
        if use_always_flag:
            routes.append({"id": rid, "source": xm_id, "target": target, "always": True})
        else:
            routes.append({
                "id": rid, "source": xm_id, "target": target,
                "condition": {"field": "__always", "operator": "is_empty"},
            })
        changed = True

    _ensure_out("r_xiaomeng_end", "end", use_always_flag=False)
    _ensure_out(f"r_xiaomeng_{_PROD_XIAOMENG_CC_NODE_ID}", _PROD_XIAOMENG_CC_NODE_ID, use_always_flag=True)
    return changed


_CS_RETURN_CS_USERS = {
    "type": "specified_role",
    "value": "cs_office",
    "exclude_initiator": True,
    "jdy_role_hint": "230902客服内勤",
}


def _cs_return_user(username: str) -> dict:
    return {"type": "specified_user", "value": username, "exclude_initiator": True}


def _cs_return_field(field_id: str) -> dict:
    return {"type": "form_field_person", "value": field_id}


# 简道云 flowId → CRM 审批人（不用角色；具名用户 / 表单人员字段）
_CS_RETURN_APPROVER_BY_ID: dict[str, dict] = {
    "n2": _cs_return_user("02366368263850"),  # 仓库接收1 司丹丹
    "n3": _CS_RETURN_CS_USERS,  # 客服办理/会签
    "n4": _cs_return_user("191811255038139135"),  # 质检 韩小超
    "n5": _cs_return_user("03303022525221387032"),  # 财务判定 刘金花
    "n9": _cs_return_user("191811255038139135"),  # 质检二次鉴定 韩小超
    "n12": _cs_return_user("02366368263850"),  # 仓库接收2 司丹丹
    "n15": _cs_return_user("03303022525221387032"),  # 财务备案 刘金花
    "n17": {  # 物流中心 马瑞草 / 李娜
        "type": "specified_user",
        "value": ["575448583538947351", "02362440128774"],
        "exclude_initiator": True,
    },
    "n19": _cs_return_field("field_22"),  # 分发仓管员2 ← 分发仓库人员
    "n20": _CS_RETURN_CS_USERS,  # 客服办理/会签
    "n21": _cs_return_user("191811255038139135"),  # 质检鉴定 韩小超
    "n23": _cs_return_user("02364437547295"),  # 生产 吕英萍
    "n24": _cs_return_user("054351591124488512"),  # 采购 张蒙蒙
    "n25": _cs_return_field("field_19"),  # 分发质检
    "n26": _cs_return_field("field_20"),  # 分发生产
    "n27": _cs_return_field("field_21"),  # 分发采购
    "n28": _cs_return_field("field_22"),  # 分发仓管员1 ← 分发仓库人员
    "n29": _cs_return_field("field_27"),  # 相关业务员 ← 转相关人员
    "n31": _cs_return_field("field"),  # 再发起 ← 提交人
    "n32": _cs_return_user("1135263833366065"),  # 采购 苏金泓
}


def _cs_return_want_for_node(node: dict) -> dict | None:
    nid = str(node.get("id") or "")
    if nid in _CS_RETURN_APPROVER_BY_ID:
        return _CS_RETURN_APPROVER_BY_ID[nid]
    for key in sorted(_CS_RETURN_APPROVER_BY_ID, key=len, reverse=True):
        if nid.startswith(key + "__"):
            return _CS_RETURN_APPROVER_BY_ID[key]
    return None


def _flow_cs_product_return_needs_approver_fix(nodes: list | None) -> bool:
    for n in nodes or []:
        if not isinstance(n, dict) or n.get("type") not in ("approval", "cc"):
            continue
        rule = n.get("approver_rule") or {}
        want = _cs_return_want_for_node(n)
        if want:
            if not _approver_rule_matches(rule, want):
                return True
            continue
        # 未映射节点若仍是空角色/可选范围，需要升级
        if rule.get("type") in ("specified_role", "pickable_scope"):
            return True
    return False


def apply_cs_product_return_approvers(nodes: list[dict]) -> bool:
    """售出产品/工具退回：客服节点→cs_office；分发/转交走表单人员字段。"""
    changed = False
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        want = _cs_return_want_for_node(n)
        if not want:
            continue
        cur = n.get("approver_rule") or {}
        if _approver_rule_matches(cur, want):
            continue
        n["approver_rule"] = dict(want)
        changed = True
    return changed


# 客服办理(n20) 后「会签人员」分流：简道云条件写的是部门 id，CRM 字段是人员多选。
# 路由同时认 username + 原部门 id；多人并行（去掉互斥组）。
_CS_RETURN_N20_PERSON_BRANCHES: tuple[tuple[str, str, str, str], ...] = (
    # route_id, target, username, jdy_dept_id
    ("r_5", "n4", "191811255038139135", "5b18a7b8258e41557b07f6e2"),  # 质检 韩小超
    ("r_21", "n23", "02364437547295", "56ca5bacf83c32e4699dd192"),  # 生产 吕英萍
    ("r_22", "n24", "054351591124488512", "619af35c8fb9780008059d3d"),  # 采购 张蒙蒙
    ("r_29", "n32", "1135263833366065", "645af34b67c48d0008d855ff"),  # 采购 苏金泓
)
_CS_RETURN_REPAIR_TYPE = "退回及维修再发货"


def _cs_return_n20_person_cond(username: str, dept_id: str) -> dict:
    return {
        "rel": "and",
        "cond": [
            {"field": "field_3", "operator": "in", "value": [_CS_RETURN_REPAIR_TYPE]},
            {
                "field": "field_18",
                "operator": "in",
                "value": [username, dept_id],
            },
        ],
    }


def _flow_cs_product_return_needs_n20_route_fix(routes: list | None) -> bool:
    """n20 出边仍按简道云部门 id 互斥 → 需升级为会签人员并行。"""
    want_by_id = {rid: (tgt, user, dept) for rid, tgt, user, dept in _CS_RETURN_N20_PERSON_BRANCHES}
    found = 0
    for r in routes or []:
        if not isinstance(r, dict) or r.get("source") != "n20":
            continue
        rid = str(r.get("id") or "")
        if rid not in want_by_id:
            # 兼容无 id 时按 target 认
            tgt = str(r.get("target") or "")
            hit = next((x for x in _CS_RETURN_N20_PERSON_BRANCHES if x[1] == tgt), None)
            if not hit:
                continue
            rid, tgt, user, dept = hit
        else:
            tgt, user, dept = want_by_id[rid]
        if r.get("exclusive_group") or r.get("fork") != "parallel":
            return True
        cond = r.get("condition") or {}
        blob = str(cond)
        if user not in blob:
            return True
        found += 1
    return found < len(_CS_RETURN_N20_PERSON_BRANCHES)


def apply_cs_product_return_n20_countersign_routes(routes: list | None) -> bool:
    """客服办理后：会签人员(field_18) 命中则并行进质检/生产/采购。"""
    if not routes:
        return False
    changed = False
    by_target = {tgt: (rid, user, dept) for rid, tgt, user, dept in _CS_RETURN_N20_PERSON_BRANCHES}
    for r in routes:
        if not isinstance(r, dict) or r.get("source") != "n20":
            continue
        tgt = str(r.get("target") or "")
        if tgt not in by_target:
            continue
        rid, user, dept = by_target[tgt]
        want_cond = _cs_return_n20_person_cond(user, dept)
        already_ok = (
            r.get("fork") == "parallel"
            and not r.get("exclusive_group")
            and user in str(r.get("condition") or "")
            and dept in str(r.get("condition") or "")
        )
        if already_ok:
            continue
        r["condition"] = want_cond
        r["fork"] = "parallel"
        r.pop("exclusive_group", None)
        if not r.get("id"):
            r["id"] = rid
        changed = True
    return changed


# 客服领图「部门指派-研管办」：简道云角色仅郑志颖一人 → 直接指定用户
_CS_DRAWING_YGB_APPROVER = {
    "type": "specified_user",
    "value": "013807685436426800",  # 郑志颖
    "exclude_initiator": True,
    "jdy_role_hint": "27.3图纸领用申请-研究院安排",
}

# 部门指派节点填写项（对齐图纸领用「研究院安排」）
_CS_DRAWING_ASSIGN_PERMS = [
    {"field": "design_dispatch", "access": "required"},
    {"field": "transfer_packaging_users", "access": "required"},
    {"field": "design_assignees", "access": "required"},
    {"field": "offices", "access": "required"},
    {"field": "order_date", "access": "required"},
]


def _cs_drawing_is_assign_node(n: dict) -> bool:
    nid = n.get("id")
    name = (n.get("name") or "").strip()
    if nid in ("n5", "n18"):
        return True
    # 简道云/现网命名可能是「部门指派-研管办 / 何伟 / 孙伟」等
    return name.startswith("部门指派")


def _field_perms_equal(have: object, want: list[dict]) -> bool:
    if not isinstance(have, list) or len(have) != len(want):
        return False
    for a, b in zip(have, want):
        if not isinstance(a, dict):
            return False
        if a.get("field") != b.get("field") or a.get("access") != b.get("access"):
            return False
    return True


def _flow_cs_drawing_needs_approver_fix(nodes: list | None) -> bool:
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        if n.get("name") != "部门指派-研管办" and n.get("id") != "n5":
            continue
        rule = n.get("approver_rule") or {}
        if not _approver_rule_matches(rule, _CS_DRAWING_YGB_APPROVER):
            return True
    return False


def _flow_cs_drawing_needs_assign_perms(nodes: list | None) -> bool:
    """何伟指派节点缺本节点填写项，或研管办 perms 被改坏时需升级。"""
    for n in nodes or []:
        if not isinstance(n, dict) or not _cs_drawing_is_assign_node(n):
            continue
        if not _field_perms_equal(n.get("field_perms"), _CS_DRAWING_ASSIGN_PERMS):
            return True
    return False


def apply_cs_drawing_approvers(nodes: list[dict]) -> bool:
    """客服领图：研管办→郑志颖；部门指派节点填写项对齐图纸领用。"""
    changed = False
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        if n.get("name") == "部门指派-研管办" or n.get("id") == "n5":
            cur = n.get("approver_rule") or {}
            if not _approver_rule_matches(cur, _CS_DRAWING_YGB_APPROVER):
                n["approver_rule"] = dict(_CS_DRAWING_YGB_APPROVER)
                changed = True
        if _cs_drawing_is_assign_node(n):
            if not _field_perms_equal(n.get("field_perms"), _CS_DRAWING_ASSIGN_PERMS):
                n["field_perms"] = [dict(p) for p in _CS_DRAWING_ASSIGN_PERMS]
                changed = True
    return changed


_PRESALE_CHIEF_APPROVER = {
    "type": "specified_user",
    "value": "02364335378133",  # 曹修国（简道云 24.2.3合同/项目评审-设计-曹修国）
    "exclude_initiator": True,
    "jdy_role_hint": "24.2.3合同/项目评审-设计-曹修国",
}


def _flow_presale_chief_needs_specified_user(nodes: list | None) -> bool:
    for n in nodes or []:
        if not isinstance(n, dict) or n.get("name") != "总工审批":
            continue
        rule = n.get("approver_rule") or {}
        if (
            rule.get("type") != _PRESALE_CHIEF_APPROVER["type"]
            or rule.get("value") != _PRESALE_CHIEF_APPROVER["value"]
        ):
            return True
    return False


def apply_presale_chief_specified_user(nodes: list[dict]) -> bool:
    """售前服务通知：总工审批 → 曹修国（勿用 sales_manager 空批）。"""
    changed = False
    for n in nodes or []:
        if not isinstance(n, dict) or n.get("name") != "总工审批":
            continue
        cur = n.get("approver_rule") or {}
        if (
            cur.get("type") == _PRESALE_CHIEF_APPROVER["type"]
            and cur.get("value") == _PRESALE_CHIEF_APPROVER["value"]
        ):
            continue
        n["approver_rule"] = dict(_PRESALE_CHIEF_APPROVER)
        changed = True
    return changed


def _presale_chief_staff_coordination_required(perms: list | None) -> bool:
    for p in perms or []:
        if isinstance(p, dict) and p.get("field") == "staff_coordination":
            return p.get("access") == "required"
    return False


def _flow_presale_chief_needs_staff_coordination_required(nodes: list | None) -> bool:
    for n in nodes or []:
        if isinstance(n, dict) and n.get("name") == "总工审批":
            return not _presale_chief_staff_coordination_required(n.get("field_perms"))
    return False


def apply_presale_chief_staff_coordination_required(nodes: list[dict]) -> bool:
    """总工审批须先指定「人员协调」，否则下一节点 form_field_person 空审自动通过。"""
    changed = False
    for n in nodes or []:
        if not isinstance(n, dict) or n.get("name") != "总工审批":
            continue
        perms: list[dict] = []
        for p in n.get("field_perms") or []:
            if not isinstance(p, dict):
                continue
            rec = dict(p)
            if rec.get("field") == "staff_coordination":
                rec["access"] = "required"
            perms.append(rec)
        if not _presale_chief_staff_coordination_required(perms):
            seen = {p.get("field") for p in perms if isinstance(p, dict)}
            if "staff_coordination" not in seen:
                perms.append({"field": "staff_coordination", "access": "required"})
            else:
                for p in perms:
                    if p.get("field") == "staff_coordination":
                        p["access"] = "required"
        if _presale_chief_staff_coordination_required(n.get("field_perms")):
            continue
        n["field_perms"] = perms
        changed = True
    return changed


_PRESALE_CC_RULE = {
    "type": "mixed",
    "value": [
        {"type": "creator"},
        {"type": "form_field_person", "value": "applicant"},
    ],
}


def _presale_cc_rule_ok(rule: dict | None) -> bool:
    rule = rule or {}
    if rule.get("type") != "mixed":
        return False
    has_creator = False
    has_applicant = False
    for sub in rule.get("value") or []:
        if not isinstance(sub, dict):
            continue
        if sub.get("type") == "creator":
            has_creator = True
        if sub.get("type") == "form_field_person" and sub.get("value") == "applicant":
            has_applicant = True
    return has_creator and has_applicant


def _flow_presale_cc_needs_applicant(nodes: list | None) -> bool:
    """抄送节点应同时通知发起人本人与表单「申请人」。"""
    for n in nodes or []:
        if isinstance(n, dict) and n.get("type") == "cc":
            if not _presale_cc_rule_ok(n.get("approver_rule")):
                return True
    return False


def apply_presale_cc_initiator_and_applicant(nodes: list[dict]) -> bool:
    """售前服务通知：抄送 → 发起人 + 申请人（组合去重）。"""
    changed = False
    for n in nodes or []:
        if not isinstance(n, dict) or n.get("type") != "cc":
            continue
        if _presale_cc_rule_ok(n.get("approver_rule")):
            continue
        n["approver_rule"] = {
            "type": "mixed",
            "value": [dict(x) for x in _PRESALE_CC_RULE["value"]],
        }
        changed = True
    return changed


def _quote_nodes_named(nodes: list | None, name: str) -> set[str]:
    return {
        str(n["id"])
        for n in (nodes or [])
        if isinstance(n, dict) and n.get("id") and n.get("name") == name
    }


def apply_quote_purchase_inquiry_parallel(
    nodes: list | None, routes: list | None,
) -> bool:
    """财务核价后「是否转采购=是」并行进采购，不与部门通知互斥。

    简道云里采购条件字段独立于部门 if/else；采购完成后无条件回到财务核价，
    须标 ``reenter`` 否则引擎会 skip_reactivate 已完成的财务核价。
    """
    purchase_ids = _quote_nodes_named(nodes, "采购")
    finance_ids = _quote_nodes_named(nodes, "财务核价")
    if not purchase_ids:
        return False
    changed = False
    for r in routes or []:
        if not isinstance(r, dict):
            continue
        tgt = str(r.get("target") or "")
        src = str(r.get("source") or "")
        if tgt in purchase_ids:
            if r.get("exclusive_group") or r.get("fork") != "parallel":
                r.pop("exclusive_group", None)
                r["fork"] = "parallel"
                changed = True
        if src in purchase_ids and tgt in finance_ids:
            if not r.get("reenter"):
                r["reenter"] = True
                changed = True
    return changed


def _flow_quote_purchase_not_parallel(nodes: list | None, routes: list | None) -> bool:
    """采购边仍在部门互斥组内，或采购回财务核价未标重入。"""
    purchase_ids = _quote_nodes_named(nodes, "采购")
    finance_ids = _quote_nodes_named(nodes, "财务核价")
    if not purchase_ids:
        return False
    for r in routes or []:
        if not isinstance(r, dict):
            continue
        tgt = str(r.get("target") or "")
        src = str(r.get("source") or "")
        if tgt in purchase_ids:
            if r.get("exclusive_group") or r.get("fork") != "parallel":
                return True
        if src in purchase_ids and tgt in finance_ids and not r.get("reenter"):
            return True
    return False


def _quote_finance_out_count(nodes: list | None, routes: list | None) -> int:
    finance_ids = _quote_nodes_named(nodes, "财务核价")
    if not finance_ids:
        return 0
    return sum(
        1 for r in (routes or [])
        if isinstance(r, dict)
        and str(r.get("source") or "") in finance_ids
        and not r.get("always")
    )


def _flow_quote_finance_outs_incomplete(
    nodes: list | None, routes: list | None,
    new_nodes: list | None, new_routes: list | None,
) -> bool:
    """财务核价出边比生成图少（部门条件边曾被 sanitize 整段删掉）→ 须整图重发。"""
    have = _quote_finance_out_count(nodes, routes)
    want = _quote_finance_out_count(new_nodes, new_routes)
    return want > 0 and have < want


def _quote_and_need_purchase_ne_yes(cond: dict | None) -> dict:
    """部门条件 ∧ 是否转采购≠是（转采购时不走通知发起人，对齐简道云实单）。"""
    gate = {"field": "need_purchase", "operator": "ne", "value": "是"}
    if not cond:
        return gate
    if (
        isinstance(cond, dict)
        and cond.get("field") == "need_purchase"
        and cond.get("operator") == "ne"
        and str(cond.get("value")) == "是"
    ):
        return cond
    nodes = cond.get("cond") if isinstance(cond, dict) else None
    if isinstance(nodes, list) and nodes:
        if any(
            isinstance(n, dict)
            and n.get("field") == "need_purchase"
            and n.get("operator") == "ne"
            and str(n.get("value")) == "是"
            for n in nodes
        ):
            return cond
        return {"rel": "and", "cond": [*nodes, gate]}
    if isinstance(cond, dict) and cond.get("field"):
        return {"rel": "and", "cond": [cond, gate]}
    return {"rel": "and", "cond": [gate]}


def apply_quote_notify_initiator_after_no_purchase(
    nodes: list | None, routes: list | None,
) -> bool:
    """通知发起人：仅当「是否转采购≠是」才进入。

    简道云实单（冶金矿山）：第一次转采购=是 → 采购+通知矿山，不走通知尚高华/发起人；
    第二次改为否 → 才走通知发起人+矿山。导出条件里没有该门闩，按实单补上。
    """
    finance_ids = _quote_nodes_named(nodes, "财务核价")
    initiator_ids = _quote_nodes_named(nodes, "通知发起人") | _quote_nodes_named(
        nodes, "通知尚高华",
    )
    if not finance_ids or not initiator_ids:
        return False
    changed = False
    for r in routes or []:
        if not isinstance(r, dict) or r.get("always"):
            continue
        if str(r.get("source") or "") not in finance_ids:
            continue
        if str(r.get("target") or "") not in initiator_ids:
            continue
        new_cond = _quote_and_need_purchase_ne_yes(
            r.get("condition") if isinstance(r.get("condition"), dict) else None,
        )
        if r.get("condition") != new_cond:
            r["condition"] = new_cond
            changed = True
    return changed


def _flow_quote_notify_initiator_missing_purchase_gate(
    nodes: list | None, routes: list | None,
) -> bool:
    finance_ids = _quote_nodes_named(nodes, "财务核价")
    initiator_ids = _quote_nodes_named(nodes, "通知发起人") | _quote_nodes_named(
        nodes, "通知尚高华",
    )
    if not finance_ids or not initiator_ids:
        return False
    for r in routes or []:
        if not isinstance(r, dict) or r.get("always"):
            continue
        if str(r.get("source") or "") not in finance_ids:
            continue
        if str(r.get("target") or "") not in initiator_ids:
            continue
        want = _quote_and_need_purchase_ne_yes(
            r.get("condition") if isinstance(r.get("condition"), dict) else None,
        )
        if r.get("condition") != want:
            return True
    return False


def apply_quote_finance_dept_notify_parallel(
    nodes: list | None, routes: list | None,
) -> bool:
    """财务核价后部门通知边：多条件可同时命中，不能进互斥组。

    简道云同源出边是「条件为真则进入」，不是严格 if/else。通知发起人条件
    含新疆/冶金/矿山，同时又有子集边「热能→段荣凯」「冶金事业部」「矿山销售」；
    若标 ``exclusive_group``，先命中超集边后子集永远走不到。
    有条件的部门边标 ``fork=parallel``；无条件 else（通知销售经理）仅作
    全未命中时的兜底，且不进互斥组。

    采购回路回到财务核价后须再次激活部门通知：财务→部门/else 审批边标
    ``reenter``，否则引擎 skip_reactivate 已完成节点，第二次核价只剩抄送就结束。
    """
    finance_ids = _quote_nodes_named(nodes, "财务核价")
    purchase_ids = _quote_nodes_named(nodes, "采购")
    if not finance_ids:
        return False
    by_id = {
        str(n["id"]): n
        for n in (nodes or [])
        if isinstance(n, dict) and n.get("id")
    }
    changed = False
    for r in routes or []:
        if not isinstance(r, dict) or r.get("always"):
            continue
        src = str(r.get("source") or "")
        if src not in finance_ids:
            continue
        tgt = str(r.get("target") or "")
        if tgt in purchase_ids:
            continue
        tgt_node = by_id.get(tgt) or {}
        # 采购回路二次财务核价后，部门/else 审批须可重入
        if tgt_node.get("type") == "approval" and not r.get("reenter"):
            r["reenter"] = True
            changed = True
        if r.get("condition"):
            if r.get("exclusive_group") or r.get("fork") != "parallel":
                r.pop("exclusive_group", None)
                r["fork"] = "parallel"
                changed = True
            continue
        # else：通知销售经理等无条件兜底，禁止进互斥组
        name = tgt_node.get("name") or ""
        if name == "通知销售经理" or not r.get("condition"):
            if r.get("exclusive_group"):
                r.pop("exclusive_group", None)
                changed = True
    return changed


def _flow_quote_finance_dept_not_parallel(
    nodes: list | None, routes: list | None,
) -> bool:
    """财务核价→部门通知仍在互斥组，或二次核价后部门边未标重入。"""
    finance_ids = _quote_nodes_named(nodes, "财务核价")
    purchase_ids = _quote_nodes_named(nodes, "采购")
    if not finance_ids:
        return False
    by_id = {
        str(n["id"]): n
        for n in (nodes or [])
        if isinstance(n, dict) and n.get("id")
    }
    for r in routes or []:
        if not isinstance(r, dict) or r.get("always"):
            continue
        if str(r.get("source") or "") not in finance_ids:
            continue
        tgt = str(r.get("target") or "")
        if tgt in purchase_ids:
            continue
        tgt_node = by_id.get(tgt) or {}
        if tgt_node.get("type") == "approval" and not r.get("reenter"):
            return True
        if r.get("condition"):
            if r.get("exclusive_group") or r.get("fork") != "parallel":
                return True
        elif r.get("exclusive_group"):
            return True
    return False


def apply_cs_service_request_start_region_first(
    nodes: list | None, routes: list | None,
) -> bool:
    """客服类表单：有区域经理时先审区域，再进业务经理（串行绕行，非并行）。

    对齐简道云「条件流程」示例（数量>10→小组长→内务；否则直达内务）及实单日志：
    业务经理 ``startAt`` = 区域经理 ``finishAt``。配置上发起→业务经理与发起→区域
    条件可能重叠，但运行按互斥优先走区域；区域审完经区域→业务经理汇合。

    做法：发起出边保持/恢复互斥组，去掉误标的 ``fork=parallel``，并把
    「区域经理或组长」排到互斥组最前，避免业务经理直达边抢先吞掉区域。
    """
    if not isinstance(routes, list):
        return False
    start_ids = {
        str(n["id"])
        for n in (nodes or [])
        if isinstance(n, dict) and n.get("id") and n.get("type") == "start"
    }
    if not start_ids:
        return False
    name_by_id = {
        str(n["id"]): str(n.get("name") or "")
        for n in (nodes or [])
        if isinstance(n, dict) and n.get("id")
    }
    region_ids = {
        nid for nid, nm in name_by_id.items() if nm == "区域经理或组长"
    }
    if not region_ids:
        return False

    changed = False
    start_outs: list[dict] = []
    for r in routes:
        if not isinstance(r, dict) or r.get("always"):
            continue
        if str(r.get("source") or "") not in start_ids:
            continue
        start_outs.append(r)
        if r.get("fork") == "parallel":
            r.pop("fork", None)
            changed = True
        if r.get("exclusive_group") != "ex_start":
            r["exclusive_group"] = "ex_start"
            changed = True

    if len(start_outs) < 2:
        return changed

    def _rank(r: dict) -> tuple:
        tgt = str(r.get("target") or "")
        if tgt in region_ids:
            return (0, 0)
        if r.get("condition"):
            return (1, 0)
        return (2, 0)

    ordered = sorted(start_outs, key=_rank)
    need_reorder = [str(r.get("target")) for r in ordered] != [
        str(r.get("target")) for r in start_outs
    ]
    if need_reorder:
        new_routes: list = []
        replaced = False
        for r in routes:
            if not isinstance(r, dict):
                new_routes.append(r)
                continue
            if r.get("always") or str(r.get("source") or "") not in start_ids:
                new_routes.append(r)
                continue
            if not replaced:
                new_routes.extend(ordered)
                replaced = True
        routes[:] = new_routes
        changed = True

    return changed


# 兼容旧名：语义已改为区域优先串行，不再并行
apply_cs_service_request_start_parallel = apply_cs_service_request_start_region_first
apply_cs_product_replace_start_parallel = apply_cs_service_request_start_region_first
apply_cs_product_replace_start_region_first = apply_cs_service_request_start_region_first


def _flow_cs_service_start_not_region_first(
    nodes: list | None, routes: list | None,
) -> bool:
    """True = 需要升级：发起仍并行，或互斥组内区域未排在业务经理之前。"""
    start_ids = {
        str(n["id"])
        for n in (nodes or [])
        if isinstance(n, dict) and n.get("id") and n.get("type") == "start"
    }
    if not start_ids:
        return False
    region_ids = {
        str(n["id"])
        for n in (nodes or [])
        if isinstance(n, dict) and n.get("id") and n.get("name") == "区域经理或组长"
    }
    if not region_ids:
        return False
    start_outs = [
        r for r in (routes or [])
        if isinstance(r, dict) and not r.get("always")
        and str(r.get("source") or "") in start_ids
    ]
    if len(start_outs) < 2:
        return False
    if any(r.get("fork") == "parallel" for r in start_outs):
        return True
    if any(not r.get("exclusive_group") for r in start_outs):
        return True
    biz_ids = {
        str(n["id"])
        for n in (nodes or [])
        if isinstance(n, dict) and n.get("id")
        and str(n.get("name") or "").startswith("业务经理")
    }
    region_pos = next(
        (i for i, r in enumerate(start_outs) if str(r.get("target") or "") in region_ids),
        None,
    )
    biz_pos = next(
        (i for i, r in enumerate(start_outs) if str(r.get("target") or "") in biz_ids),
        None,
    )
    if region_pos is not None and biz_pos is not None and region_pos > biz_pos:
        return True
    return False


_flow_cs_service_start_not_parallel = _flow_cs_service_start_not_region_first
_flow_cs_product_replace_start_not_parallel = _flow_cs_service_start_not_region_first
_flow_cs_product_replace_start_not_region_first = _flow_cs_service_start_not_region_first


def _flow_is_jdy_form_graph(form_code: str | None, nodes: list | None) -> bool:
    if form_code in ("drawing_requisition", "install_drawing_notice", "scheme_management"):
        return _flow_is_jdy_drawing(nodes)
    if form_code == "prod_card_supplement":
        return _flow_is_jdy_prod_card(nodes)
    if form_code == "invoice_application":
        return _flow_is_jdy_invoice(nodes)
    if form_code == "payment_registration":
        return _flow_is_jdy_payment(nodes)
    if form_code == "quote_management":
        return _flow_is_jdy_quote(nodes)
    if form_code == "presale_service_notice":
        return _flow_is_jdy_presale_service_notice(nodes)
    if form_code == "shipment_notice":
        return _flow_is_jdy_shipment_notice(nodes)
    if form_code == "pricing_checklist_hjqd":
        return _flow_is_jdy_pricing_checklist(nodes)
    if form_code == "research_coop_card":
        return _flow_is_jdy_research_coop_card(nodes)
    if form_code == "tech_agreement_feedback":
        return _flow_is_jdy_tech_agreement_feedback(nodes)
    if form_code == "contract_outsource_early":
        return _flow_is_jdy_contract_outsource_early(nodes)
    if form_code == "xunhan_contract_review":
        return _flow_is_jdy_xunhan_contract_review(nodes)
    if form_code and form_code.startswith("cs_"):
        return _flow_is_jdy_customer_service(nodes)
    return False


def _flow_is_jdy_xunhan_contract_review(nodes: list | None) -> bool:
    """已对齐简道云迅焊合同评审：含法务审批等多节点（非单节点兜底）。"""
    ids = {str(n.get("id") or "") for n in (nodes or []) if isinstance(n, dict)}
    return "n3" in ids and len(nodes or []) >= 10


def _flow_is_jdy_customer_service(nodes: list | None) -> bool:
    """已对齐简道云客户服务部流程：多审批节点（非单节点兜底）。"""
    nodes = nodes or []
    types = {n.get("type") for n in nodes if isinstance(n, dict)}
    return "approval" in types and len(nodes) >= 5


def _flow_is_jdy_pricing_checklist(nodes: list | None) -> bool:
    """已对齐简道云核价清单传递：含「财务」+ 抄送申请人。"""
    names = {n.get("name") for n in (nodes or [])}
    types = {n.get("type") for n in (nodes or [])}
    return "财务" in names and "cc" in types and len(nodes or []) >= 5


def _flow_is_jdy_research_coop_card(nodes: list | None) -> bool:
    """已对齐简道云中央研究院协同卡：含「设计安排」+ 抄送申请人。"""
    names = {n.get("name") for n in (nodes or [])}
    types = {n.get("type") for n in (nodes or [])}
    return "设计安排" in names and "cc" in types and len(nodes or []) >= 6


def _flow_is_jdy_contract_outsource_early(nodes: list | None) -> bool:
    """已对齐简道云合同外购件提前安排（或 CRM 兜底拓扑）：设计指派 + 采购安排。"""
    names = {n.get("name") for n in (nodes or [])}
    types = {n.get("type") for n in (nodes or [])}
    return "设计指派" in names and "采购安排" in names and "approval" in types and len(nodes or []) >= 5


def _flow_has_legacy_department_leader(nodes: list | None) -> bool:
    """旧生成器把部门主管写成 department_leader，需升级为 dept_head。"""
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        rule = n.get("approver_rule") or {}
        if isinstance(rule, dict) and rule.get("type") == "department_leader":
            return True
    return False


def _flow_needs_pickable_scope_approver_upgrade(
    current_nodes: list | None, new_nodes: list | None,
) -> bool:
    """生成图已改为 pickable_scope（如客服领图「部门指派-研管办」），现网仍为角色降级时需重发。"""
    cur_by_id = {
        n.get("id"): n
        for n in (current_nodes or [])
        if isinstance(n, dict) and n.get("id")
    }
    for nn in new_nodes or []:
        if not isinstance(nn, dict):
            continue
        want = nn.get("approver_rule") or {}
        if not isinstance(want, dict) or want.get("type") != "pickable_scope":
            continue
        cur = cur_by_id.get(nn.get("id")) or {}
        have = cur.get("approver_rule") or {}
        if not isinstance(have, dict):
            return True
        if have.get("type") != "pickable_scope" or have.get("value") != want.get("value"):
            return True
    return False


def _drawing_flow_has_cc_end_bug(nodes: list | None, routes: list | None) -> bool:
    """旧生成器把叶子抄送接到 end，或入抄送边未标 always —— 需再升级。

    开票「发票已开具可下载」例外：发起人接收之后串到该抄送再结束，入边不必 always。
    """
    cc_ids = {n.get("id") for n in (nodes or []) if n.get("type") == "cc" and n.get("id")}
    if not cc_ids:
        return False
    for r in routes or []:
        if not isinstance(r, dict):
            continue
        src, tgt = r.get("source"), r.get("target")
        if tgt == _INVOICE_CC_SALES_DONE or src == _INVOICE_CC_SALES_DONE:
            continue
        if tgt == "end" and src in cc_ids:
            return True
        if tgt in cc_ids and not r.get("always"):
            return True
    return False


def _route_is_always_parallel(route: dict | None) -> bool:
    """简道云 cond=[] → ``__always is_empty``：无条件并行后继，不得进互斥组。

    与 ``always: true``（抄送旁路）同类：与其它 if/else 并行，不抢占。
    """
    if not isinstance(route, dict):
        return False
    if route.get("always"):
        return True
    cond = route.get("condition")
    return (
        isinstance(cond, dict)
        and cond.get("field") == "__always"
        and cond.get("operator") == "is_empty"
    )


def _route_has_branch_condition(route: dict | None) -> bool:
    """连线是否有可参与 if/else 分支判断的条件（__always / always 旁路不算）。"""
    if not isinstance(route, dict):
        return False
    if route.get("always") or _route_is_always_parallel(route):
        return False
    return bool(route.get("condition"))


def _flow_src_is_unconditional_parallel_fork(outs: list) -> bool:
    """同源多条均无条件出边 = 简道云并行分叉（如发货通知开具提货单→生产领料/仓库判定）。"""
    serial = _serial_exclusive_outs(outs)
    return len(serial) >= 2 and all(not _route_has_branch_condition(o) for o in serial)


def _serial_exclusive_outs(outs: list) -> list:
    """互斥组只覆盖非 parallel / 非恒真并行出边。转采购、总工→总经理等并行边不参与 if/else。"""
    return [
        o for o in outs
        if isinstance(o, dict)
        and o.get("fork") != "parallel"
        and not _route_is_always_parallel(o)
    ]


def fix_always_parallel_exclusive_groups(routes: list | None) -> bool:
    """把误打进 exclusive_group 的恒真并行边拆出来（否则总工会只走总经理、跳过财务核算）。"""
    changed = False
    for r in routes or []:
        if not isinstance(r, dict):
            continue
        if _route_is_always_parallel(r) and r.get("exclusive_group"):
            r.pop("exclusive_group", None)
            changed = True
    return changed


def _flow_always_parallel_in_exclusive_group(routes: list | None) -> bool:
    return any(
        isinstance(r, dict) and _route_is_always_parallel(r) and r.get("exclusive_group")
        for r in (routes or [])
    )


def _flow_missing_exclusive_groups(routes: list | None) -> bool:
    """同源多出边未标 exclusive_group 时，画布像一条直线、引擎也可能不按 if/else 选路。

    标了 ``fork=parallel`` 的边不参与互斥；其余串行出边仍须成组。
    """
    by_src: dict[str, list] = {}
    for r in routes or []:
        if not isinstance(r, dict) or r.get("always"):
            continue
        src = str(r.get("source") or "")
        if not src:
            continue
        by_src.setdefault(src, []).append(r)
    for outs in by_src.values():
        serial = _serial_exclusive_outs(outs)
        if len(serial) < 2:
            continue
        if _flow_src_is_unconditional_parallel_fork(outs):
            continue
        if any(not o.get("exclusive_group") for o in serial):
            return True
    return False


def _flow_exclusive_group_multi_blank(routes: list | None) -> bool:
    """互斥组内出现 ≥2 条无条件边（条件被清成 null 后的假 else）。

    报价等串行流会因此把「部门审批」与下游「财务核价」同时激活，须整图重发。
    """
    blanks: dict[str, int] = {}
    for r in routes or []:
        if not isinstance(r, dict) or r.get("always"):
            continue
        gid = r.get("exclusive_group")
        if not gid:
            continue
        if not r.get("condition"):
            blanks[str(gid)] = blanks.get(str(gid), 0) + 1
    return any(n > 1 for n in blanks.values())


def fix_packaging_fork_serial_priority(
    nodes: list | None, routes: list | None,
) -> bool:
    """工艺包装分叉改为互斥且包装优先（对齐简道云实单，非并行）。

    有「转新乡、工艺包装」人选 → 先「工艺包装」，再经包装节点出边进第二「研究院安排」；
    无包装人选、设计单分派命中 → 直达第二研究院安排；否则 else。
    """
    by_id = {
        n["id"]: n for n in (nodes or [])
        if isinstance(n, dict) and n.get("id")
    }
    pack_sources: set[str] = set()
    for r in routes or []:
        if not isinstance(r, dict):
            continue
        t = by_id.get(r.get("target") or "")
        if t and t.get("name") == "工艺包装":
            pack_sources.add(str(r.get("source") or ""))
    if not pack_sources:
        return False

    changed = False
    name_by_id = {i: (n.get("name") or "") for i, n in by_id.items()}
    for src in pack_sources:
        outs = [
            r for r in (routes or [])
            if isinstance(r, dict) and not r.get("always") and str(r.get("source") or "") == src
        ]
        if len(outs) < 2:
            continue
        gid = f"ex_{src}"
        for r in outs:
            if r.get("fork") is not None:
                r.pop("fork", None)
                changed = True
            if r.get("exclusive_group") != gid:
                r["exclusive_group"] = gid
                changed = True
        outs_sorted = sorted(outs, key=lambda r: (
            0 if name_by_id.get(r.get("target") or "") == "工艺包装" else
            1 if r.get("condition") else 2
        ))
        if outs != outs_sorted:
            new_routes: list = []
            replaced = False
            for r in routes or []:
                if not isinstance(r, dict):
                    new_routes.append(r)
                    continue
                if r.get("always") or str(r.get("source") or "") != src:
                    new_routes.append(r)
                    continue
                if not replaced:
                    new_routes.extend(outs_sorted)
                    replaced = True
            routes[:] = new_routes  # type: ignore[index]
            changed = True
    return changed


async def ensure_all_biz_defaults(db, tenant_id: str) -> None:
    """幂等：为租户补齐合同版本/合同评审/线索等系统默认审批流。"""
    for spec in BIZ_DEFAULT_SPECS:
        try:
            await ensure_default_definition(
                db, tenant_id,
                biz_type=spec["biz_type"],
                code=spec["code"],
                name=spec["name"],
                approver_rule=spec["approver_rule"],
                multi_mode=spec.get("multi_mode", "or_sign"),
                empty_strategy=spec.get("empty_strategy", "auto_approve"),
            )
        except Exception as e:
            logger.warning("ensure default flow %s failed: %s", spec.get("code"), e)
            await db.rollback()
    await ensure_all_form_defaults(db, tenant_id)


async def ensure_all_form_defaults(db, tenant_id: str) -> None:
    """幂等：安装图纸等内置表单（若尚未安装），并补齐绑定表单的默认审批流。"""
    from app.domains.lowcode.service import ensure_builtin_form
    for spec in FORM_DEFAULT_SPECS:
        try:
            await ensure_builtin_form(db, tenant_id, spec["form_code"], {"sub": None})
        except Exception as e:
            logger.warning("ensure form flow %s failed: %s", spec.get("code"), e)
            await db.rollback()
    # 租户自建线索流（如 WF_*）也补齐情报审 field_perms，否则审批页无「新/老、收录/袭击」
    try:
        lead_defs = (await db.execute(select(WfProcessDefinition).where(
            WfProcessDefinition.tenant_id == tenant_id,
            WfProcessDefinition.biz_type == "lead",
            WfProcessDefinition.is_deleted == False,  # noqa: E712
            WfProcessDefinition.status == "published",
        ))).scalars().all()
        for d in lead_defs:
            try:
                await _upgrade_lead_intel_field_perms_if_needed(db, tenant_id, d)
            except Exception as e:
                logger.warning("upgrade lead intel field perms %s failed: %s", d.code, e)
                await db.rollback()
            try:
                await _upgrade_lead_owner_confirm_if_missing(db, tenant_id, d)
            except Exception as e:
                logger.warning("upgrade lead owner confirm %s failed: %s", d.code, e)
                await db.rollback()
    except Exception as e:
        logger.warning("ensure lead intel field perms failed: %s", e)
        await db.rollback()


# 引擎在「有条件边命中时会忽略无条件 else」：与条件边并存的必经边需挂恒真条件。
_ALWAYS_TRUE_COND = {"field": "__always", "operator": "is_empty"}


def _fp(*items: tuple[str, str]) -> list[dict]:
    """field_perms 快捷构造：('legal_risk','required'), ..."""
    return [{"field": f, "access": a} for f, a in items]


def _role_approval_node(
    nid: str, name: str, role: str, *,
    field_perms: list[dict] | None = None,
    opinion_required: bool = False,
    multi_mode: str = "or_sign",
) -> dict:
    node: dict = {
        "id": nid, "type": "approval", "name": name,
        "approver_rule": {
            "type": "specified_role", "value": role, "exclude_initiator": True,
        },
        "multi_mode": multi_mode, "empty_strategy": "auto_approve",
    }
    if field_perms:
        node["field_perms"] = field_perms
    if opinion_required:
        node["opinion_required"] = True
    return node


def _user_approval_node(
    nid: str, name: str, usernames: list[str] | str, *,
    field_perms: list[dict] | None = None,
    opinion_required: bool = False,
    multi_mode: str = "or_sign",
    empty_strategy: str = "auto_approve",
) -> dict:
    """指定人员审批（对齐简道云 chargers.users；value 用 CRM username）。"""
    names = [usernames] if isinstance(usernames, str) else list(usernames)
    value: str | list[str] = names[0] if len(names) == 1 else names
    node: dict = {
        "id": nid, "type": "approval", "name": name,
        "approver_rule": {
            "type": "specified_user", "value": value, "exclude_initiator": True,
        },
        "multi_mode": multi_mode, "empty_strategy": empty_strategy,
    }
    if field_perms:
        node["field_perms"] = field_perms
    if opinion_required:
        node["opinion_required"] = True
    return node


def _field_person_approval_node(
    nid: str, name: str, field: str, *,
    field_perms: list[dict] | None = None,
    multi_mode: str = "or_sign",
    empty_strategy: str = "auto_approve",
) -> dict:
    """表单人员字段审批（对齐简道云 chargers.widgets）。"""
    node: dict = {
        "id": nid, "type": "approval", "name": name,
        "approver_rule": {
            "type": "form_field_person", "value": field, "exclude_initiator": True,
        },
        "multi_mode": multi_mode, "empty_strategy": empty_strategy,
    }
    if field_perms:
        node["field_perms"] = field_perms
    return node


def _creator_approval_node(
    nid: str, name: str, *,
    field_perms: list[dict] | None = None,
    multi_mode: str = "or_sign",
    empty_strategy: str = "auto_approve",
) -> dict:
    """发起人审批（对齐简道云 chargers.creator）。"""
    node: dict = {
        "id": nid, "type": "approval", "name": name,
        "approver_rule": {"type": "creator"},
        "multi_mode": multi_mode, "empty_strategy": empty_strategy,
    }
    if field_perms:
        node["field_perms"] = field_perms
    return node


def _cc_node(nid: str, name: str, approver_rule: dict) -> dict:
    """抄送节点（旁路通知，不阻塞主链；出边可为空）。"""
    return {
        "id": nid, "type": "cc", "name": name,
        "approver_rule": approver_rule,
    }


def _and_cond(*parts: dict) -> dict:
    return {"rel": "and", "cond": list(parts)}


CUSTOMER_INFO_DEFAULT_DESC = (
    "系统默认（对齐简道云客户信息）："
    "外贸=是 → 外贸客户审批(王玲玲)；"
    "信息分发=是 → 信息分发(业务员) → 跟进确认 → 财务审批(刘金花)；"
    "否则 → 财务审批。可在流程管理中继续改。"
)


def _customer_info_flow_graph() -> tuple[list[dict], list[dict]]:
    """客户信息默认图：互斥三分支（外贸 / 信息分发串行 / 默认财务）。"""
    u_fin = _JDY_REG_USER["finance_maint"]  # 刘金花
    u_export = _JDY_REVIEW_USER["export"]  # 王玲玲
    foreign_yes = {"field": "is_foreign_trade", "operator": "in", "value": [True, "是"]}
    dist_yes = {"field": "need_info_distribute", "operator": "in", "value": [True, "是"]}
    nodes: list[dict] = [
        {"id": "start", "type": "start", "name": "发起"},
        _user_approval_node("approval_foreign", "外贸客户审批", u_export),
        _field_person_approval_node("approval_distribute", "信息分发-客户", "owner_id"),
        _field_person_approval_node("approval_follow", "跟进确认", "owner_id"),
        _user_approval_node("approval_finance", "财务审批", u_fin),
        {"id": "end", "type": "end", "name": "结束"},
    ]
    # exclusive_group：同组按顺序互斥，命中第一条；else 边放最后且无条件
    g = "g_customer_start"
    routes: list[dict] = [
        {
            "id": "r_start_foreign", "source": "start", "target": "approval_foreign",
            "exclusive_group": g, "condition": _and_cond(foreign_yes),
        },
        {
            "id": "r_start_dist", "source": "start", "target": "approval_distribute",
            "exclusive_group": g, "condition": _and_cond(dist_yes),
        },
        {
            "id": "r_start_finance", "source": "start", "target": "approval_finance",
            "exclusive_group": g,
        },
        {"id": "r_foreign_end", "source": "approval_foreign", "target": "end"},
        {"id": "r_dist_follow", "source": "approval_distribute", "target": "approval_follow"},
        {"id": "r_follow_finance", "source": "approval_follow", "target": "approval_finance"},
        {"id": "r_finance_end", "source": "approval_finance", "target": "end"},
    ]
    return nodes, routes


# 简道云合同登记 chargers → CRM username（按 real_name 匹配本地用户）
_JDY_REG_USER = {
    "finance": "442558535226341870",          # 李焱焱
    "production": "02374913228906",           # 薛非霞
    "procurement": "02352513566524",          # 杨霜
    "warehouse": ["01346931076927160185", "0654354430671114"],  # 段亚非、侯静
    "qc": "0236420233847",                    # 张国运
    "finance_maint": "03303022525221387032",  # 刘金花（财务维护，标准交付/旋振筛共用）
    "prod_office": "02425350081942",          # 杜意敏（生产办/旋振筛）
    "purch_dept": "286057106726080520",       # 杨丽丽（采购部，挂生产办后）
    "purch_xzs": "1135263833366065",          # 苏金泓（采购员/旋振筛）
    "qc_xzs": "02362247571234189",            # 雷贤（质检员/旋振筛）
    "wh_xzs": "26140402631151393",            # 贾真（仓库人员/旋振筛）
}

# 简道云合同评审 chargers → CRM username
_JDY_REVIEW_USER = {
    "intel": "023656363429294971",            # 王梦茹/王梦颖
    "gm": "02336214315748",                   # 王思民
    "finance_opinion": "0433406811775721",    # 张光
    "design": "02364335378133",               # 曹修国
    "finance_dir": "0433406811775721",  # 张光（业务确认无需李晋）
    "production": "01210720669288",           # 周世孔
    "procurement": "02352513566524",          # 杨霜
    "qc": "0236420233847",                    # 张国运
    "export": "01000533004677",               # 王玲玲
    # 简道云角色「24.2.3合同/项目评审-法务审批多人」；CRM legal 角色成员解析
    "legal": ["543355140326074979", "4723152427763414", "256932256424153873"],  # 杜习慧、孔雪、张孟杰
    "legal_sup": "02364840011125",            # 袁文俊（法务主管）
    # 抄送具名
    "cc_install": ["080160552326376700", "02364307332960", "232040221426613133"],  # 杜珍珍/韩利民/杜金波
    "cc_related": ["02364249424532", "023656363429294971", "02362556584221"],  # 李惠萍/王梦颖/李晋
    "cc_lili": "02364313303546",              # 李莉
    "cc_xunhan": "01670210101135172",         # 许曼（简道云迅焊）
}

_LEGAL_SUP_NODE_IDS = frozenset({"approval_legal_sup", "n29"})
_LEGAL_SUP_NODE_NAMES = frozenset({"法务主管审批"})


def _legal_sup_want_username(want: str | None = None) -> str:
    if want:
        return want
    v = _JDY_REVIEW_USER["legal_sup"]
    return v[0] if isinstance(v, list) else v


def _legal_sup_user_rule(want: str | None = None) -> dict:
    return {
        "type": "specified_user",
        "value": _legal_sup_want_username(want),
        "exclude_initiator": True,
    }


def _is_legal_sup_node(n: dict) -> bool:
    return (
        str(n.get("id") or "") in _LEGAL_SUP_NODE_IDS
        or str(n.get("name") or "").strip() in _LEGAL_SUP_NODE_NAMES
    )


def _legal_sup_approver_needs_fix(
    nodes: list | None, want: str | None = None,
) -> bool:
    want_rule = _legal_sup_user_rule(want)
    for n in nodes or []:
        if not isinstance(n, dict) or not _is_legal_sup_node(n):
            continue
        if not _approver_rule_matches(n.get("approver_rule") or {}, want_rule):
            return True
    return False


def apply_legal_sup_named_approver(
    nodes: list[dict], *, username: str | None = None,
) -> bool:
    """合同评审/迅焊等：法务主管审批→袁文俊（具名用户）。"""
    want_rule = _legal_sup_user_rule(username)
    changed = False
    for n in nodes or []:
        if not isinstance(n, dict) or not _is_legal_sup_node(n):
            continue
        if _approver_rule_matches(n.get("approver_rule") or {}, want_rule):
            continue
        n["approver_rule"] = dict(want_rule)
        n.setdefault("empty_strategy", "auto_approve")
        changed = True
    return changed


# 简道云「合同技术协议评审」chargers / 抄送 → CRM username
_JDY_TAR_USER = {
    # 历史「市场支持中心」节点审批人（已从默认拓扑移除；保留映射供对照）
    "market_support": "023641581817",         # 王亚飞
    "chief": "02364335378133",                # 曹修国（总工审批）
    # 审批反馈后抄送相关人（简道云 ccUsers.users；另含业务员字段）
    "cc_related": [
        "02364335378133",  # 曹修国
        "02365310056917",  # 王东明
        "02365625057413",  # 周彦立
        "02365312411349",  # 李兴玉
        "0236562418583",   # 樊磊
        "01142154504565",  # 刘松潮
        "02374448122197",  # 王鹏飞（z老）
        "02380224638593",  # 李巧丽
        "02374836394830",  # 韦利星
        "0237444753532",   # 吕芹
        "02365310124408",  # 丰芊
        "04055912043654",  # 常文飞
        "02383653146747",  # 吕宗源
        "02396211202298",  # 许杰
        "02380332036601",  # 李振
    ],
}

CONTRACT_VERSION_DEFAULT_DESC = (
    "系统默认（对齐简道云合同登记）：审批人按简道云具名配置；"
    "财务后按标准交付/方式并行产采仓质，再接采购员/质检员/财务维护；"
    "旋振筛并行生产办/采购员/质检员/仓库人员，生产办后再接采购部与财务维护；最后汇聚结束。"
    "可在设计器改条件与审批人。"
)

CONTRACT_REVIEW_DEFAULT_DESC = (
    "系统默认（对齐简道云合同评审）：发起旁路抄送业务员/安装组；"
    "可选区域经理 → 业务部门 → 情报/法务→法务主管/设计/财务总监/出口会签 → "
    "总经理 → 财务意见；不反馈时产采质+发起人直达结束，需反馈时走信息反馈回路再入总经理；"
    "财务意见旁路抄送相关人/李莉/迅焊。国际营销部门用业务部门名称包含「国际」近似匹配。"
    "可在设计器改条件与审批人。"
)


def _contract_version_flow_graph() -> tuple[list[dict], list[dict]]:
    """合同版本默认图：对齐简道云「合同登记」完整运营拓扑与具名审批人。

    简道云主干（CRM 用 merge 汇聚替代多父结束，避免并行未完就结束）：
    - 财务 → 产/采/仓/质（标准交付+方式）→ 采后采购员、质后质检员、仓后财务维护
    - 财务 → 生产办/采购员/质检员/仓库人员（旋振筛=是）→ 生产办后再接采购部+财务维护
    - 财务 → 结束（标准交付=否 AND 旋振筛=否）
    """
    u = _JDY_REG_USER
    nodes: list[dict] = [
        {"id": "start", "type": "start", "name": "发起"},
        _user_approval_node(
            "approval_finance", "财务审核", u["finance"],
            # 对齐简道云 optAuth=3：财务填写合同类型、验收相关字段
            field_perms=_fp(
                ("contract_type", "required"),
                ("accept_method", "required"),
                ("accept_materials", "editable"),
                ("accept_date", "editable"),
            ),
        ),
        # —— 标准交付分支 ——
        _user_approval_node("approval_production", "生产", u["production"]),
        _user_approval_node(
            "approval_procurement", "采购", u["procurement"],
            field_perms=_fp(("purchasers", "required")),
        ),
        _field_person_approval_node("approval_purchaser", "采购员", "purchasers"),
        _user_approval_node(
            "approval_warehouse", "仓库", u["warehouse"],
            field_perms=_fp(("fill_code", "editable")),
        ),
        _user_approval_node("approval_finance_maint", "财务维护", u["finance_maint"]),
        _user_approval_node(
            "approval_qc", "质检", u["qc"],
            field_perms=_fp(("inspectors", "required")),
        ),
        _field_person_approval_node("approval_inspector", "质检员", "inspectors"),
        # —— 旋振筛分支 ——
        _user_approval_node(
            "approval_prod_office", "生产办", u["prod_office"],
            field_perms=_fp(("fill_code", "editable")),
        ),
        _user_approval_node("approval_purch_dept", "采购部", u["purch_dept"]),
        _user_approval_node(
            "approval_finance_maint_xzs", "财务维护（旋振筛）", u["finance_maint"],
        ),
        _user_approval_node("approval_purch_xzs", "采购员（旋振筛）", u["purch_xzs"]),
        _user_approval_node("approval_qc_xzs", "质检员（旋振筛）", u["qc_xzs"]),
        _user_approval_node(
            "approval_wh_xzs", "仓库人员", u["wh_xzs"],
            field_perms=_fp(("fill_code", "editable")),
        ),
        {"id": "merge_ops", "type": "merge", "name": "运营汇聚"},
        {"id": "end", "type": "end", "name": "结束"},
    ]
    # 各并行叶节点汇入 merge（条件未激活的边由引擎 early-complete 跳过）
    leaf_to_merge = [
        "approval_production",
        "approval_purchaser",
        "approval_finance_maint",
        "approval_inspector",
        "approval_purch_dept",
        "approval_finance_maint_xzs",
        "approval_purch_xzs",
        "approval_qc_xzs",
        "approval_wh_xzs",
    ]
    std_yes = {"field": "standard_delivery", "operator": "in", "value": ["是"]}
    std_no = {"field": "standard_delivery", "operator": "in", "value": ["否"]}
    rotary_yes = {"field": "is_rotary_sieve", "operator": "in", "value": ["是"]}
    rotary_no = {"field": "is_rotary_sieve", "operator": "in", "value": ["否"]}
    routes: list[dict] = [
        {"id": "r_start", "source": "start", "target": "approval_finance"},
        {
            "id": "r_fin_prod", "source": "approval_finance", "target": "approval_production",
            "condition": _and_cond(
                std_yes, {"field": "delivery_mode", "operator": "in", "value": ["YZO", "YZO和YZS"]},
            ),
        },
        {
            "id": "r_fin_purch", "source": "approval_finance", "target": "approval_procurement",
            "condition": _and_cond(
                std_yes, {"field": "delivery_mode", "operator": "in", "value": ["YZS", "YZO和YZS"]},
            ),
        },
        {
            "id": "r_fin_wh", "source": "approval_finance", "target": "approval_warehouse",
            "condition": _and_cond(
                std_yes, {"field": "delivery_mode", "operator": "in", "value": ["YZO", "YZS", "YZO和YZS"]},
            ),
        },
        {
            "id": "r_fin_qc", "source": "approval_finance", "target": "approval_qc",
            "condition": _and_cond(
                std_yes, {"field": "delivery_mode", "operator": "in", "value": ["YZO", "YZS", "YZO和YZS"]},
            ),
        },
        {
            "id": "r_fin_po", "source": "approval_finance", "target": "approval_prod_office",
            "condition": _and_cond(rotary_yes),
        },
        {
            "id": "r_fin_px", "source": "approval_finance", "target": "approval_purch_xzs",
            "condition": _and_cond(rotary_yes),
        },
        {
            "id": "r_fin_qx", "source": "approval_finance", "target": "approval_qc_xzs",
            "condition": _and_cond(rotary_yes),
        },
        {
            "id": "r_fin_wx", "source": "approval_finance", "target": "approval_wh_xzs",
            "condition": _and_cond(rotary_yes),
        },
        {
            "id": "r_fin_end", "source": "approval_finance", "target": "end",
            "condition": _and_cond(std_no, rotary_no),
        },
        # 标准交付二级：采购→采购员；质检→质检员；仓库→财务维护
        {"id": "r_purch_buyer", "source": "approval_procurement", "target": "approval_purchaser"},
        {"id": "r_qc_insp", "source": "approval_qc", "target": "approval_inspector"},
        {"id": "r_wh_fin", "source": "approval_warehouse", "target": "approval_finance_maint"},
        # 旋振筛：生产办 → 采购部 + 财务维护（并行）
        {"id": "r_po_dept", "source": "approval_prod_office", "target": "approval_purch_dept"},
        {"id": "r_po_fin", "source": "approval_prod_office", "target": "approval_finance_maint_xzs"},
        *[{"id": f"r_{i}_merge", "source": i, "target": "merge_ops"} for i in leaf_to_merge],
        {"id": "r_merge_end", "source": "merge_ops", "target": "end"},
    ]
    return nodes, routes


def _contract_review_flow_graph() -> tuple[list[dict], list[dict]]:
    """合同评审默认图：对齐简道云截图拓扑（会签 + 反馈 + 旁路抄送）。

    简道云主干：
    - 发起旁路：抄送业务员；负责安装 → 抄送金微星
    - 发起 →（合同评审且有区域经理）区域经理 → 业务部门；否则直接业务部门
    - 业务后并行：情报(项目评审) / 法务→法务主管(合同评审) / 设计 / 财务总监 /
      出口(出口=是 且部门名不含「国际」)
    - 汇聚 → 总经理 → 财务意见
    - 财务意见旁路：抄送相关人；部门含「国际」→ 抄送李莉；含「迅焊」→ 抄送迅焊
    - 财务意见后：不反馈+合同评审 → 产采质+发起人 → 结束；不反馈+项目评审 → 结束；
      需反馈 → 信息反馈 →（可选反馈区域经理）→ 反馈业务部门 → 设计审批1 → 再入总经理
    """
    u = _JDY_REVIEW_USER
    nodes: list[dict] = [
        {"id": "start", "type": "start", "name": "发起"},
        # —— 发起旁路抄送（always 边，不抢占 else）——
        _cc_node(
            "cc_owner", "抄送业务员",
            {"type": "form_field_person", "value": "owner_id"},
        ),
        _cc_node(
            "cc_install", "抄送金微星",
            {"type": "specified_user", "value": u["cc_install"]},
        ),
        _field_person_approval_node(
            "approval_region", "区域经理/组长", "region_manager_id",
            field_perms=_fp(("biz_risk", "required"), ("biz_risk_desc", "editable")),
        ),
        {
            "id": "approval_biz", "type": "approval", "name": "业务部门审批",
            "approver_rule": {"type": "dept_head", "exclude_initiator": True},
            "multi_mode": "or_sign", "empty_strategy": "auto_approve",
            "field_perms": _fp(("biz_risk", "required"), ("biz_risk_desc", "editable")),
        },
        _user_approval_node("approval_intel", "信息情报部审批", u["intel"]),
        _user_approval_node(
            "approval_legal", "法务审批", u["legal"],
            multi_mode="or_sign",
            field_perms=_fp(
                ("legal_risk", "required"), ("legal_risk_desc", "editable"),
                ("clause_opinion", "editable"),
            ),
        ),
        _user_approval_node(
            "approval_legal_sup", "法务主管审批", u["legal_sup"],
            field_perms=_fp(
                ("legal_risk", "required"), ("legal_risk_desc", "editable"),
                ("clause_opinion", "editable"),
            ),
        ),
        _user_approval_node(
            "approval_design", "设计审批", u["design"],
            field_perms=_fp(("tech_risk", "required"), ("tech_risk_desc", "editable")),
        ),
        _user_approval_node(
            "approval_finance_dir", "财务总监意见", u["finance_dir"],
            # 业务确认仅张光审批（或签）；简道云原为李晋+张光会签已按业务调整
            multi_mode="or_sign",
            # 简道云：财务/采购风险 + 账期/结论描述
            field_perms=_fp(
                ("finance_risk", "required"), ("finance_risk_desc", "editable"),
                ("purchase_risk", "required"), ("purchase_risk_desc", "editable"),
                ("payment_term", "required"), ("conclusion", "editable"),
            ),
        ),
        _user_approval_node(
            "approval_export", "出口审批", u["export"],
            field_perms=_fp(("export_risk", "required"), ("export_risk_desc", "editable")),
        ),
        {"id": "merge_review", "type": "merge", "name": "会签汇聚"},
        _user_approval_node(
            "approval_gm", "总经理审批", u["gm"], opinion_required=True,
        ),
        _user_approval_node(
            "approval_finance_opinion", "财务意见", u["finance_opinion"],
            # 简道云：是否反馈在此填写，决定后续反馈回路 / 产采质
            field_perms=_fp(("need_feedback", "required")),
        ),
        # —— 财务意见旁路抄送 ——
        _cc_node(
            "cc_related", "抄送相关人",
            {
                "type": "mixed",
                "value": [
                    {"type": "specified_user", "value": u["cc_related"]},
                    {"type": "creator"},
                    {"type": "form_field_person", "value": "owner_id"},
                ],
            },
        ),
        _cc_node(
            "cc_lili", "抄送李莉",
            {"type": "specified_user", "value": u["cc_lili"]},
        ),
        _cc_node(
            "cc_xunhan", "抄送迅焊",
            {"type": "specified_user", "value": u["cc_xunhan"]},
        ),
        # 财务意见后：产采质 + 发起人（不反馈时）→ 直达结束
        _user_approval_node("approval_production", "生产审批", u["production"]),
        _user_approval_node("approval_procurement", "采购审批", u["procurement"]),
        _user_approval_node("approval_qc", "质检审批", u["qc"]),
        _creator_approval_node(
            "approval_initiator", "发起人",
            # 简道云流程无签约字段可写；CRM 在发起人节点补填图纸号/意见执行/反馈成员
            field_perms=_fp(
                ("drawing_no", "editable"), ("opinion_exec", "editable"),
                ("feedback_members", "editable"),
            ),
        ),
        {"id": "merge_ops_post", "type": "merge", "name": "产采质汇聚"},
        # 反馈回路
        _creator_approval_node("approval_info_feedback", "信息反馈"),
        _field_person_approval_node(
            "approval_feedback_region", "反馈区域经理/组长", "region_manager_id",
            field_perms=_fp(("biz_risk", "required"), ("biz_risk_desc", "editable")),
        ),
        {
            "id": "approval_feedback_biz", "type": "approval", "name": "反馈业务部门",
            "approver_rule": {"type": "dept_head", "exclude_initiator": True},
            "multi_mode": "or_sign", "empty_strategy": "auto_approve",
            "field_perms": _fp(("biz_risk", "required"), ("biz_risk_desc", "editable")),
        },
        _user_approval_node("approval_design_fb", "设计审批1", u["design"]),
        {"id": "end", "type": "end", "name": "结束"},
    ]
    rt_contract = {"field": "review_type", "operator": "in", "value": ["合同评审"]}
    rt_project = {"field": "review_type", "operator": "in", "value": ["项目评审"]}
    export_yes = {"field": "is_export", "operator": "in", "value": ["是"]}
    # 简道云：业务部门 nin 国际营销范围 → CRM 用部门名不含「国际」近似
    not_intl = {"field": "department_name", "operator": "not_contains", "value": "国际"}
    intl_dept = {"field": "department_name", "operator": "contains", "value": "国际"}
    xunhan_dept = {"field": "department_name", "operator": "contains", "value": "迅焊"}
    feedback_no = {"field": "need_feedback", "operator": "in", "value": ["否"]}
    feedback_yes = {"field": "need_feedback", "operator": "in", "value": ["是"]}
    region_set = {"field": "region_manager_id", "operator": "is_not_empty"}
    install_yes = {"field": "need_install", "operator": "in", "value": ["负责安装"]}
    peer_to_merge = [
        ("approval_intel", _and_cond(rt_project)),
        ("approval_design", _ALWAYS_TRUE_COND),
        ("approval_finance_dir", _ALWAYS_TRUE_COND),
        ("approval_export", _and_cond(export_yes, not_intl)),
    ]
    post_fin_ops = [
        ("approval_production", _and_cond(rt_contract, feedback_no)),
        ("approval_procurement", _and_cond(rt_contract, feedback_no)),
        ("approval_qc", _and_cond(rt_contract, feedback_no)),
        ("approval_initiator", _and_cond(rt_contract, feedback_no)),
    ]
    routes: list[dict] = [
        # 发起旁路抄送（always，不抢占区域经理/业务 else）
        {"id": "r_start_cc_owner", "source": "start", "target": "cc_owner", "always": True},
        {
            "id": "r_start_cc_install", "source": "start", "target": "cc_install",
            "always": True, "condition": _and_cond(install_yes),
        },
        # 发起：有区域经理则先审，否则直接业务部门
        {
            "id": "r_start_region", "source": "start", "target": "approval_region",
            "condition": _and_cond(rt_contract, region_set),
        },
        {"id": "r_start_biz", "source": "start", "target": "approval_biz"},
        {"id": "r_region_biz", "source": "approval_region", "target": "approval_biz"},
        # 业务 → 会签分支（须 fork=parallel，否则「有条件边+一条无条件 merge」会被
        # 引擎当成 if/else，合同评审只走法务、设计/财务永不激活）
        {
            "id": "r_biz_legal", "source": "approval_biz", "target": "approval_legal",
            "condition": _and_cond(rt_contract), "fork": "parallel",
        },
        *[
            {
                "id": f"r_biz_{tid}", "source": "approval_biz", "target": tid,
                "condition": cond, "fork": "parallel",
            }
            for tid, cond in peer_to_merge
        ],
        # 法务 → 法务主管 → 汇聚
        {"id": "r_legal_sup", "source": "approval_legal", "target": "approval_legal_sup"},
        {"id": "r_legal_sup_merge", "source": "approval_legal_sup", "target": "merge_review"},
        *[{"id": f"r_{tid}_merge", "source": tid, "target": "merge_review"} for tid, _ in peer_to_merge],
        # 主干
        {"id": "r_merge_gm", "source": "merge_review", "target": "approval_gm"},
        # reenter：反馈回路设计审批1 再入总经理后，须能再次激活已完成的财务意见
        {
            "id": "r_gm_fin", "source": "approval_gm",
            "target": "approval_finance_opinion", "reenter": True,
        },
        # 财务意见旁路抄送
        {
            "id": "r_fin_cc_related", "source": "approval_finance_opinion",
            "target": "cc_related", "always": True,
        },
        {
            "id": "r_fin_cc_lili", "source": "approval_finance_opinion",
            "target": "cc_lili", "always": True, "condition": _and_cond(intl_dept),
        },
        {
            "id": "r_fin_cc_xunhan", "source": "approval_finance_opinion",
            "target": "cc_xunhan", "always": True, "condition": _and_cond(xunhan_dept),
        },
        # 财务意见后主分支（产采质+发起人须 fork=parallel；否则「多条件边+一条无条件
        # end 兜底」会被引擎自动当成 if/else，只激活第一条生产审批）
        *[
            {
                "id": f"r_fin_{tid}", "source": "approval_finance_opinion", "target": tid,
                "condition": cond, "fork": "parallel",
            }
            for tid, cond in post_fin_ops
        ],
        {
            "id": "r_fin_end_project", "source": "approval_finance_opinion", "target": "end",
            "condition": _and_cond(rt_project, feedback_no),
        },
        {
            "id": "r_fin_feedback", "source": "approval_finance_opinion",
            "target": "approval_info_feedback",
            "condition": _and_cond(feedback_yes),
        },
        # 反馈字段为空等兜底：直接结束，避免卡死
        {"id": "r_fin_end_fallback", "source": "approval_finance_opinion", "target": "end"},
        *[{"id": f"r_{tid}_post_merge", "source": tid, "target": "merge_ops_post"} for tid, _ in post_fin_ops],
        {"id": "r_post_end", "source": "merge_ops_post", "target": "end"},
        # 反馈回路
        {
            "id": "r_fb_region", "source": "approval_info_feedback",
            "target": "approval_feedback_region",
            "condition": _and_cond(rt_contract, region_set),
        },
        {"id": "r_fb_biz", "source": "approval_info_feedback", "target": "approval_feedback_biz"},
        {
            "id": "r_fb_region_biz", "source": "approval_feedback_region",
            "target": "approval_feedback_biz",
        },
        {
            "id": "r_fb_biz_design", "source": "approval_feedback_biz",
            "target": "approval_design_fb",
            "condition": _and_cond(feedback_yes),
        },
        # 反馈过程中若已改为不反馈，直接再入总经理（避免卡在反馈业务部门）
        # reenter：总经理首轮已完成，反馈回路须允许再次激活（对齐简道云）
        {
            "id": "r_fb_biz_gm", "source": "approval_feedback_biz",
            "target": "approval_gm", "reenter": True,
        },
        # 设计审批1 再入总经理
        {
            "id": "r_design_fb_gm", "source": "approval_design_fb",
            "target": "approval_gm", "reenter": True,
        },
    ]
    return nodes, routes


def _tech_agreement_flow_graph() -> tuple[list[dict], list[dict]]:
    """技术协议评审默认图：对齐简道云「合同技术协议评审 HTJSXY」主干（已去掉市场支持中心）。

    发起旁路抄送业务员；
    部门审批（业务部门主管）→ 总工（填设计审批）→
    设计审批1（填设计审批2）→ 设计审批2 → 业务反馈（业务员）→
    设计审批1.1 → 设计审批2.1 → 审批反馈（申请人/发起人）→
    旁路抄送相关人 → 结束。

    注：简道云导出里「业务反馈→设计审批1.1→2.1→审批反馈」为无条件边
    （界面画成旁路，实际每单都走）；CRM 按导出条件落地。
    「市场支持中心」节点已按业务要求移除。
    """
    u = _JDY_TAR_USER
    nodes: list[dict] = [
        {"id": "start", "type": "start", "name": "发起"},
        _cc_node(
            "cc_owner", "抄送业务员",
            {"type": "form_field_person", "value": "owner_id"},
        ),
        {
            "id": "approval_dept", "type": "approval", "name": "部门审批",
            "approver_rule": {"type": "dept_head", "exclude_initiator": True},
            "multi_mode": "or_sign", "empty_strategy": "auto_approve",
        },
        _user_approval_node(
            "approval_chief", "总工审批", u["chief"],
            field_perms=_fp(("design_approver_ids", "required")),
        ),
        _field_person_approval_node(
            "approval_design1", "设计审批1", "design_approver_ids",
            field_perms=_fp(("design_approver_2_ids", "required")),
        ),
        _field_person_approval_node(
            "approval_design2", "设计审批2", "design_approver_2_ids",
            field_perms=_fp(("has_objection", "editable")),
        ),
        _field_person_approval_node("approval_biz_fb", "业务反馈", "owner_id"),
        _field_person_approval_node(
            "approval_design1_1", "设计审批1.1", "design_approver_ids",
            field_perms=_fp(("design_approver_2_ids", "required")),
        ),
        _field_person_approval_node(
            "approval_design2_1", "设计审批2.1", "design_approver_2_ids",
        ),
        {
            "id": "approval_feedback", "type": "approval", "name": "审批反馈",
            "approver_rule": {
                "type": "mixed",
                "value": [
                    {"type": "creator"},
                    {"type": "form_field_person", "value": "applicant_id"},
                ],
            },
            "multi_mode": "or_sign", "empty_strategy": "auto_approve",
        },
        _cc_node(
            "cc_related", "抄送相关人",
            {
                "type": "mixed",
                "value": [
                    {"type": "specified_user", "value": u["cc_related"]},
                    {"type": "form_field_person", "value": "owner_id"},
                ],
            },
        ),
        {"id": "end", "type": "end", "name": "结束"},
    ]
    routes: list[dict] = [
        {"id": "r_start_cc_owner", "source": "start", "target": "cc_owner", "always": True},
        {"id": "r_start_dept", "source": "start", "target": "approval_dept"},
        {"id": "r_dept_chief", "source": "approval_dept", "target": "approval_chief"},
        {"id": "r_chief_d1", "source": "approval_chief", "target": "approval_design1"},
        {"id": "r_d1_d2", "source": "approval_design1", "target": "approval_design2"},
        {"id": "r_d2_biz", "source": "approval_design2", "target": "approval_biz_fb"},
        {"id": "r_biz_d11", "source": "approval_biz_fb", "target": "approval_design1_1"},
        {"id": "r_d11_d21", "source": "approval_design1_1", "target": "approval_design2_1"},
        {"id": "r_d21_fb", "source": "approval_design2_1", "target": "approval_feedback"},
        {
            "id": "r_fb_cc_related", "source": "approval_feedback",
            "target": "cc_related", "always": True,
        },
        {"id": "r_fb_end", "source": "approval_feedback", "target": "end"},
    ]
    return nodes, routes


TECH_AGREEMENT_DEFAULT_DESC = (
    "系统默认（对齐简道云合同技术协议评审）：发起抄送业务员；"
    "部门审批 → 总工填设计审批 → 设计审批1/2 → "
    "业务反馈 → 设计审批1.1/2.1 → 审批反馈；旁路抄送相关人后结束。"
    "已去掉「市场支持中心」节点。可在流程管理中继续改。"
)


# 线索第二节点：业务员确认是否转商机（审批，非抄送）
_LEAD_OWNER_CONFIRM_NODE_ID = "approval_owner_confirm"
_LEAD_OWNER_CONFIRM_LEGACY_IDS = frozenset({"cc_owner", "approval_owner_confirm"})
# 简道云「申报信息」对齐文案
_LEAD_JDY_START = "递呈信息"
_LEAD_JDY_APPROVAL = "信息情报部审批"
_LEAD_JDY_CC = "业务员确认是否转商机"
_LEAD_JDY_END = "流程结束"
_LEAD_LEGACY_START = {"发起", "开始", "start"}
_LEAD_LEGACY_APPROVAL = {"线索审核", "内勤审批", "审批"}
_LEAD_LEGACY_CC = {"通知业务员确认转化", "抄送", "CC", "抄送业务员"}
_LEAD_LEGACY_END = {"结束", "end"}


# 业务员确认节点人员字段：申报人=业务员；历史误绑过负责人 owner_id
_LEAD_CONFIRM_PERSON_FIELDS = frozenset({"reporter_id", "owner_id"})


def _is_lead_confirm_person_rule(rule: dict | None) -> bool:
    rule = rule or {}
    return (
        rule.get("type") == "form_field_person"
        and rule.get("value") in _LEAD_CONFIRM_PERSON_FIELDS
    )


def _is_lead_owner_confirm_node_dict(n: dict) -> bool:
    if n.get("id") in _LEAD_OWNER_CONFIRM_LEGACY_IDS:
        return True
    name = (n.get("name") or "").strip()
    if name in (_LEAD_JDY_CC, *_LEAD_LEGACY_CC) or "转商机" in name:
        return True
    rule = n.get("approver_rule") or {}
    return _is_lead_confirm_person_rule(rule) and ("转商机" in name or "确认转化" in name)


def _lead_intel_approver_already_cui_yang(rule: dict | None) -> bool:
    rule = rule or {}
    if rule.get("type") != "specified_user":
        return False
    vals = rule.get("value")
    if isinstance(vals, str):
        vals = [vals]
    want = set(_LEAD_INTEL_APPROVER_USERNAMES)
    got = {str(v).strip() for v in (vals or []) if str(v).strip()}
    return want <= got


def _lead_owner_confirm_node() -> dict:
    """情报通过后：申报人（业务员）审批确认是否转商机（非填表人/负责人）。"""
    return {
        "id": _LEAD_OWNER_CONFIRM_NODE_ID,
        "type": "approval",
        "name": "业务员确认是否转商机",
        "approver_rule": {"type": "form_field_person", "value": "reporter_id"},
        "multi_mode": "or_sign",
        # 无申报人时终止，避免再被 auto_approve 静默跳过
        "empty_strategy": "terminate",
    }


def _default_flow_graph(
    name: str, approver_rule: dict, multi_mode: str, empty_strategy: str,
    *, with_owner_cc: bool = False,
) -> tuple[list[dict], list[dict]]:
    """系统兜底流程节点图。

    with_owner_cc=True（线索）：对齐简道云「申报信息」
    递呈信息 → 信息情报部审批 → 业务员确认是否转商机(审批) → 流程结束
    """
    start_name = "递呈信息" if with_owner_cc else "发起"
    end_name = "流程结束" if with_owner_cc else "结束"
    approval_node: dict = {
        "id": "approval_1", "type": "approval", "name": name,
        "approver_rule": approver_rule, "multi_mode": multi_mode,
        "empty_strategy": empty_strategy,
    }
    # 线索：情报节点可填评估字段（对齐升级后引擎「本节点可填写字段」）
    if with_owner_cc:
        approval_node["field_perms"] = _fp(
            ("customer_newness", "required"),
            ("reject_reason", "editable"),
            ("assess_remark", "editable"),
        )
    nodes: list[dict] = [
        {"id": "start", "type": "start", "name": start_name},
        approval_node,
    ]
    routes: list[dict] = [
        {"id": "r_start", "source": "start", "target": "approval_1"},
    ]
    if with_owner_cc:
        confirm = _lead_owner_confirm_node()
        nodes.append(confirm)
        nodes.append({"id": "end", "type": "end", "name": end_name})
        routes.append({"id": "r_confirm", "source": "approval_1", "target": confirm["id"]})
        routes.append({"id": "r_end", "source": confirm["id"], "target": "end"})
    else:
        nodes.append({"id": "end", "type": "end", "name": end_name})
        routes.append({"id": "r_end", "source": "approval_1", "target": "end"})
    return nodes, routes


LEAD_REACTIVATION_DEFAULT_DESC = (
    "系统默认（对齐简道云 180天项目激活）："
    "触发即起流程；跳过申报人→内勤(填跟进)，否则业务员→进行中且需内勤→内勤(确认)"
    "→信息情报部审批→抄送申报人→结束。"
)

_LEAD_REACT_ENTRY_NODE_ID = "approval_intel"
_LEAD_REACT_SALES_NODE_ID = "approval_sales"
_LEAD_REACT_FILLER_SKIP_NODE_ID = "approval_filler_skip"
_LEAD_REACT_FILLER_NODE_ID = "approval_filler"
_LEAD_REACT_CC_NODE_ID = "cc_reporter"
_LEAD_REACT_INTEL_NODE_NAME = "信息情报部审批"

_REPORT_STATUS_OPTS = [
    {"value": "进行中", "label": "进行中"},
    {"value": "暂缓", "label": "暂缓"},
    {"value": "暂停", "label": "暂停"},
    {"value": "取消", "label": "取消"},
    {"value": "落标", "label": "落标"},
    {"value": "中标", "label": "中标"},
    {"value": "已签合同", "label": "已签合同"},
]

_LEAD_REACT_FOLLOW_FIELD_PERMS = _fp(
    ("project_recent", "editable"),
    ("follow_progress", "editable"),
    ("site_visit", "editable"),
    ("report_project_status", "required"),
)

# 简道云 flowId=3：业务员已填跟进，内勤仅确认转发（无可填字段）


def _node_field_access(nodes: list | None, nid: str, field: str) -> str | None:
    by_id = {n.get("id"): n for n in (nodes or []) if isinstance(n, dict)}
    node = by_id.get(nid) or {}
    for p in node.get("field_perms") or []:
        if isinstance(p, dict) and p.get("field") == field:
            return str(p.get("access") or "")
    return None


def _node_has_field_perms(nodes: list | None, nid: str) -> bool:
    by_id = {n.get("id"): n for n in (nodes or []) if isinstance(n, dict)}
    perms = (by_id.get(nid) or {}).get("field_perms") or []
    return bool(perms)


def _lead_reactivation_flow_graph(
    name: str, approver_rule: dict, multi_mode: str, empty_strategy: str,
) -> tuple[list[dict], list[dict]]:
    """180天项目激活：全链路 workflow（递呈→业务员/内勤×2→情报审→抄送）。"""
    progress = {"field": "report_project_status", "operator": "eq", "value": "进行中"}
    skip_reporter = {"field": "react_skip_reporter", "operator": "in", "value": [True, "true", 1]}
    need_filler = {"field": "react_need_filler", "operator": "in", "value": [True, "true", 1]}
    sales = _field_person_approval_node(
        _LEAD_REACT_SALES_NODE_ID, "业务员", "reporter_id",
        field_perms=_LEAD_REACT_FOLLOW_FIELD_PERMS,
    )
    # 简道云 flowId=5：跳过申报人时内勤代填跟进（同业务员字段权限）
    filler_skip = _field_person_approval_node(
        _LEAD_REACT_FILLER_SKIP_NODE_ID, "内勤", "created_by_id",
        field_perms=_LEAD_REACT_FOLLOW_FIELD_PERMS,
    )
    # 简道云 flowId=3：业务员后内勤只点通过，不填字段
    filler = _field_person_approval_node(
        _LEAD_REACT_FILLER_NODE_ID, "内勤", "created_by_id",
    )
    # 简道云 flowId=4：情报审通过后抄送申报人
    cc_reporter = _cc_node(
        _LEAD_REACT_CC_NODE_ID, "抄送申报人",
        {"type": "form_field_person", "value": "reporter_id"},
    )
    nodes: list[dict] = [
        {"id": "start", "type": "start", "name": "递呈信息"},
        sales,
        filler_skip,
        filler,
        {
            "id": _LEAD_REACT_ENTRY_NODE_ID, "type": "approval",
            "name": _LEAD_REACT_INTEL_NODE_NAME,
            "approver_rule": approver_rule, "multi_mode": multi_mode,
            "empty_strategy": empty_strategy,
            "field_perms": _LEAD_REACT_INTEL_FIELD_PERMS,
        },
        cc_reporter,
        {"id": "end", "type": "end", "name": "流程结束"},
    ]
    g_start = "g_react_start"
    g_sales = "g_react_sales"
    g_filler_skip = "g_react_filler_skip"
    g_filler = "g_react_filler"
    routes: list[dict] = [
        {
            "id": "r_start_skip_reporter", "source": "start",
            "target": _LEAD_REACT_FILLER_SKIP_NODE_ID,
            "exclusive_group": g_start, "condition": _and_cond(skip_reporter),
        },
        {
            "id": "r_start_sales", "source": "start", "target": _LEAD_REACT_SALES_NODE_ID,
            "exclusive_group": g_start,
        },
        {
            "id": "r_sales_filler", "source": _LEAD_REACT_SALES_NODE_ID,
            "target": _LEAD_REACT_FILLER_NODE_ID,
            "exclusive_group": g_sales, "condition": _and_cond(progress, need_filler),
        },
        {
            "id": "r_sales_intel", "source": _LEAD_REACT_SALES_NODE_ID,
            "target": _LEAD_REACT_ENTRY_NODE_ID,
            "exclusive_group": g_sales, "condition": _and_cond(progress),
        },
        {
            "id": "r_sales_end", "source": _LEAD_REACT_SALES_NODE_ID, "target": "end",
            "exclusive_group": g_sales,
        },
        {
            "id": "r_filler_skip_intel", "source": _LEAD_REACT_FILLER_SKIP_NODE_ID,
            "target": _LEAD_REACT_ENTRY_NODE_ID,
            "exclusive_group": g_filler_skip, "condition": _and_cond(progress),
        },
        {
            "id": "r_filler_skip_end", "source": _LEAD_REACT_FILLER_SKIP_NODE_ID, "target": "end",
            "exclusive_group": g_filler_skip,
        },
        {
            "id": "r_filler_intel", "source": _LEAD_REACT_FILLER_NODE_ID,
            "target": _LEAD_REACT_ENTRY_NODE_ID,
            "exclusive_group": g_filler, "condition": _and_cond(progress),
        },
        {
            "id": "r_filler_end", "source": _LEAD_REACT_FILLER_NODE_ID, "target": "end",
            "exclusive_group": g_filler,
        },
        {
            "id": "r_intel_cc", "source": _LEAD_REACT_ENTRY_NODE_ID,
            "target": _LEAD_REACT_CC_NODE_ID,
        },
        {"id": "r_cc_end", "source": _LEAD_REACT_CC_NODE_ID, "target": "end"},
    ]
    return nodes, routes


def _flow_is_jdy_lead_reactivation(nodes: list | None, routes: list | None = None) -> bool:
    """已是 workflow 全链路 180天激活图（双内勤 + 情报字段 + 抄送申报人）。"""
    ids = {n.get("id") for n in (nodes or [])}
    required = {
        _LEAD_REACT_SALES_NODE_ID, _LEAD_REACT_FILLER_SKIP_NODE_ID,
        _LEAD_REACT_FILLER_NODE_ID, _LEAD_REACT_ENTRY_NODE_ID, _LEAD_REACT_CC_NODE_ID,
    }
    if not required <= ids:
        return False
    if _node_field_access(nodes, _LEAD_REACT_SALES_NODE_ID, "report_project_status") != "required":
        return False
    if _node_field_access(nodes, _LEAD_REACT_FILLER_SKIP_NODE_ID, "report_project_status") != "required":
        return False
    if _node_has_field_perms(nodes, _LEAD_REACT_FILLER_NODE_ID):
        return False
    if _node_field_access(nodes, _LEAD_REACT_ENTRY_NODE_ID, "has_internal_conflict") != "editable":
        return False
    by_id = {n.get("id"): n for n in (nodes or []) if isinstance(n, dict)}
    intel = by_id.get(_LEAD_REACT_ENTRY_NODE_ID) or {}
    if (intel.get("name") or "").strip() != _LEAD_REACT_INTEL_NODE_NAME:
        return False
    skip_to_filler_skip = need_filler_route = has_sales_intel = has_intel_cc = False
    for r in routes or []:
        fields = _route_cond_fields(r)
        if (
            r.get("source") == "start"
            and r.get("target") == _LEAD_REACT_FILLER_SKIP_NODE_ID
            and "react_skip_reporter" in fields
        ):
            skip_to_filler_skip = True
        if (
            r.get("source") == _LEAD_REACT_SALES_NODE_ID
            and r.get("target") == _LEAD_REACT_FILLER_NODE_ID
            and "react_need_filler" in fields
        ):
            need_filler_route = True
        if (
            r.get("source") == _LEAD_REACT_SALES_NODE_ID
            and r.get("target") == _LEAD_REACT_ENTRY_NODE_ID
            and "report_project_status" in fields
        ):
            has_sales_intel = True
        if (
            r.get("source") == _LEAD_REACT_ENTRY_NODE_ID
            and r.get("target") == _LEAD_REACT_CC_NODE_ID
        ):
            has_intel_cc = True
    return skip_to_filler_skip and need_filler_route and has_sales_intel and has_intel_cc


_LEAD_INTEL_FIELD_PERMS = _fp(
    ("customer_newness", "required"),
    ("reject_reason", "editable"),
    ("assess_remark", "editable"),
)

# 简道云 180天激活情报审：新/老 + 内部冲突 + 最终状态(UI) + 回退原因 + 备注2
_LEAD_REACT_INTEL_FIELD_PERMS = _fp(
    ("customer_newness", "required"),
    ("has_internal_conflict", "editable"),
    ("conflict_note", "editable"),
    ("reject_reason", "editable"),
    ("assess_remark", "editable"),
)


async def _upgrade_lead_intel_field_perms_if_needed(
    db, tenant_id: str, d: WfProcessDefinition,
) -> None:
    """给线索情报审批节点补齐「本节点可填写字段」（不改审批人，尊重租户已配指定人）。

    字段顺序对齐简道云：新/老 → 回退原因 → 备注2 → 操作意见（最终状态由情报表单承担）。
    系统默认流与租户自建 lead 流均适用；跳过「业务员确认转商机」节点。
    """
    if d.biz_type != "lead":
        return
    version = await _published_version(db, tenant_id, d.id)
    if not version:
        return
    nodes = list(version.node_definitions or [])
    ap = None
    for n in nodes:
        if not isinstance(n, dict) or n.get("type") != "approval":
            continue
        nid = (n.get("id") or "").strip()
        name = (n.get("name") or "").strip()
        if nid in ("approval_owner_confirm", "cc_owner") or "转商机" in name or "确认转化" in name:
            continue
        ap = n
        break
    if not ap:
        return
    existing = {
        (p.get("field") or p.get("id")): p
        for p in (ap.get("field_perms") or [])
        if isinstance(p, dict)
    }
    want = {p["field"]: p["access"] for p in _LEAD_INTEL_FIELD_PERMS}
    want_order = [p["field"] for p in _LEAD_INTEL_FIELD_PERMS]
    cur_order = [
        (p.get("field") or p.get("id"))
        for p in (ap.get("field_perms") or [])
        if isinstance(p, dict) and (p.get("field") or p.get("id")) in want
    ]
    need_merge = not all(f in existing for f in want)
    need_reorder = cur_order != want_order
    if not need_merge and not need_reorder:
        return
    merged = dict(existing)
    for f, acc in want.items():
        if f not in merged:
            merged[f] = {"field": f, "access": acc}
        elif not merged[f].get("access"):
            merged[f] = {"field": f, "access": acc}
    ordered: list[dict] = []
    for f in want_order:
        if f in merged:
            ordered.append({"field": f, "access": merged[f].get("access") or want[f]})
    for f, p in merged.items():
        if f not in want:
            ordered.append(p)
    new_nodes: list[dict] = []
    for n in nodes:
        nn = dict(n)
        if nn.get("id") == ap.get("id") or (
            nn.get("type") == "approval" and nn.get("name") == ap.get("name")
        ):
            nn["field_perms"] = ordered
        new_nodes.append(nn)
    await _publish_system_default_upgrade(
        db, tenant_id, d, version, new_nodes, list(version.route_definitions or []),
        "系统默认流程（情报节点可填：新/老、回退原因、备注2、操作意见）",
        "线索情报节点field_perms",
    )


async def _upgrade_lead_intel_specified_users_if_needed(
    db, tenant_id: str, d: WfProcessDefinition,
) -> None:
    """线索情报节点：角色码 lead_intel → 指定崔艳丽、杨光（或签）。"""
    if d.code != "SYS_LEAD_REVIEW":
        return
    if d.category and d.category != SYSTEM_DEFAULT_CATEGORY:
        return
    version = await _published_version(db, tenant_id, d.id)
    if not version:
        return
    nodes = list(version.node_definitions or [])
    intel_ap: dict | None = None
    for n in nodes:
        if n.get("type") != "approval" or _is_lead_owner_confirm_node_dict(n):
            continue
        if "情报" in (n.get("name") or "") or n.get("id") == "approval_1":
            intel_ap = n
            break
    if intel_ap is None:
        for n in nodes:
            if n.get("type") == "approval" and not _is_lead_owner_confirm_node_dict(n):
                intel_ap = n
                break
    if intel_ap is None:
        return
    if _lead_intel_approver_already_cui_yang(intel_ap.get("approver_rule")):
        return
    new_rule = _lead_intel_approver_rule()
    new_nodes: list[dict] = []
    for n in nodes:
        nn = dict(n)
        if nn.get("id") == intel_ap.get("id"):
            nn["approver_rule"] = new_rule
            nn["multi_mode"] = nn.get("multi_mode") or "or_sign"
        new_nodes.append(nn)
    await _publish_system_default_upgrade(
        db, tenant_id, d, version, new_nodes, list(version.route_definitions or []),
        "系统默认流程（信息情报部审批：指定崔艳丽、杨光）",
        "线索情报节点指定人员",
    )


async def ensure_default_form_definition(
    db, tenant_id, form_template_id: str, code: str, name: str,
    approver_rule: dict | None = None,
    multi_mode: str = "or_sign",
    empty_strategy: str = "auto_approve",
) -> WfProcessDefinition | None:
    """为自定义表单幂等创建并发布默认审批流（绑定 form_template_id）。

    表单提交后由 maybe_start_for_form 命中；可在流程管理中继续编辑节点。
    图纸两表优先使用简道云对齐拓扑（DRAWING_JDY），否则回退单节点。
    """
    rule = approver_rule or {
        "type": "specified_role", "value": "sales_manager", "exclude_initiator": True,
    }
    form_code = next(
        (s["form_code"] for s in FORM_DEFAULT_SPECS if s["code"] == code),
        None,
    )
    jdy_graph = _drawing_flow_graph(form_code) if form_code else None
    if jdy_graph:
        nodes, routes = jdy_graph
        description = DRAWING_FORM_FLOW_DESC
        from app.domains.lowcode.jdy_id_remap import sanitize_route_ids_for_tenant
        routes, _ = await sanitize_route_ids_for_tenant(db, tenant_id, routes)
    else:
        nodes, routes = _default_flow_graph(name, rule, multi_mode, empty_strategy)
        description = "系统默认流程（表单提交后自动发起，可在流程管理中编辑）"

    existing = (await db.execute(select(WfProcessDefinition).where(
        WfProcessDefinition.tenant_id == tenant_id,
        WfProcessDefinition.form_template_id == form_template_id,
        WfProcessDefinition.status == "published",
        WfProcessDefinition.is_deleted == False,  # noqa: E712
    ).limit(1))).scalar_one_or_none()
    if existing:
        await _upgrade_drawing_form_flow_if_needed(db, tenant_id, existing, form_code)
        return existing

    mine = (await db.execute(select(WfProcessDefinition).where(
        WfProcessDefinition.tenant_id == tenant_id,
        WfProcessDefinition.code == code,
    ).limit(1))).scalar_one_or_none()
    if mine is not None:
        mine.form_template_id = form_template_id
        mine.biz_type = None
        mine.name = name
        mine.description = description
        mine.category = SYSTEM_DEFAULT_CATEGORY
        mine.sort_order = _SYSTEM_DEFAULT_SORT
        revived = await _revive_default_definition(db, tenant_id, mine, nodes, routes)
        if revived:
            await _upgrade_drawing_form_flow_if_needed(db, tenant_id, revived, form_code)
        return revived

    d = WfProcessDefinition(
        id=generate_uuid(), tenant_id=tenant_id, name=name, code=code,
        description=description,
        category=SYSTEM_DEFAULT_CATEGORY,
        form_template_id=form_template_id,
        biz_type=None,
        status="published", current_version=1, sort_order=_SYSTEM_DEFAULT_SORT,
    )
    db.add(d)
    v = WfProcessDefinitionVersion(
        id=generate_uuid(), tenant_id=tenant_id, process_definition_id=d.id,
        version_number=1, node_definitions=nodes, route_definitions=routes,
        approver_rules=[], status="published", published_at=_now(),
    )
    db.add(v)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raced = (await db.execute(select(WfProcessDefinition).where(
            WfProcessDefinition.tenant_id == tenant_id,
            WfProcessDefinition.code == code,
        ).limit(1))).scalar_one_or_none()
        if raced is not None:
            raced.form_template_id = form_template_id
            raced.biz_type = None
            raced.name = name
            raced.description = description
            raced.category = SYSTEM_DEFAULT_CATEGORY
            raced.sort_order = _SYSTEM_DEFAULT_SORT
            revived = await _revive_default_definition(db, tenant_id, raced, nodes, routes)
            if revived:
                await _upgrade_drawing_form_flow_if_needed(db, tenant_id, revived, form_code)
            return revived
        return None
    return d


async def _upgrade_drawing_form_flow_if_needed(
    db, tenant_id: str, d: WfProcessDefinition, form_code: str | None,
) -> None:
    """系统兜底表单流：单节点/旧简图升级为简道云对齐拓扑（图纸/方案/生产卡）。"""
    if not form_code:
        return
    if d.category and d.category != SYSTEM_DEFAULT_CATEGORY:
        return
    if d.code not in (
        "SYS_DRAWING_REQUISITION",
        "SYS_INSTALL_DRAWING_NOTICE",
        "SYS_SCHEME_MANAGEMENT",
        "SYS_PRESALE_SERVICE_NOTICE",
        "SYS_PROD_CARD_SUPPLEMENT",
        "SYS_INVOICE_APPLICATION",
        "SYS_PAYMENT_REGISTRATION",
        "SYS_QUOTE_MANAGEMENT",
        "SYS_PRICING_CHECKLIST_HJQD",
        "SYS_CS_SERVICE_REQUEST",
        "SYS_CS_PRODUCT_REPLACE",
        "SYS_CS_PRODUCT_RETURN",
        "SYS_CS_LOAN_SLIP",
        "SYS_CS_DRAWING_REQUEST",
        "SYS_CS_SERVICE_DELAY",
        "SYS_CS_CORRESPONDENCE",
        "SYS_SHIPMENT_NOTICE",
        "SYS_XUNHAN_CONTRACT_REVIEW",
        "SYS_TECH_AGREEMENT_FEEDBACK",
        "SYS_CONTRACT_OUTSOURCE_EARLY",
        "SYS_BIZ_BONUS_TRANSFER",
        "SYS_BIZ_BONUS_BIZ_INITIATE",
        "SYS_COMMISSION_DATABASE",
    ):
        return
    graph = _drawing_flow_graph(form_code)
    if not graph:
        return
    version = await _published_version(db, tenant_id, d.id)
    if not version:
        return
    new_nodes, new_routes = graph
    from app.domains.lowcode.jdy_id_remap import (
        routes_have_jdy_dept_ids, routes_have_jdy_person_ids,
        sanitize_route_ids_for_tenant,
    )
    need_id_remap = (
        routes_have_jdy_dept_ids(version.route_definitions)
        or routes_have_jdy_person_ids(version.route_definitions)
    )
    topology_ok = (
        _flow_is_jdy_form_graph(form_code, version.node_definitions)
        and not _drawing_flow_has_cc_end_bug(
            version.node_definitions, version.route_definitions,
        )
        and not _flow_has_legacy_department_leader(version.node_definitions)
        and not _flow_needs_pickable_scope_approver_upgrade(
            version.node_definitions, new_nodes,
        )
        and not (
            _flow_has_node_field_perms(new_nodes)
            and not _flow_has_node_field_perms(version.node_definitions)
        )
        and not (
            _flow_has_node_field_perms(new_nodes)
            and _flow_field_perms_sig(new_nodes)
            != _flow_field_perms_sig(version.node_definitions)
        )
        and not _flow_exclusive_group_multi_blank(version.route_definitions)
        and not (
            form_code == "shipment_notice"
            and _flow_shipment_parallel_fork_broken(version.route_definitions)
        )
        # 报价：财务核价部门出边被 sanitize 删光后节点仍在，须整图重发
        and not (
            form_code == "quote_management"
            and _flow_quote_finance_outs_incomplete(
                version.node_definitions, version.route_definitions,
                new_nodes, new_routes,
            )
        )
    )
    # 报价管理：财务核价「是否转采购」取消必填 → editable
    if (
        topology_ok
        and form_code == "quote_management"
        and _flow_has_quote_need_purchase_required(version.node_definitions)
    ):
        import copy
        patched = copy.deepcopy(version.node_definitions or [])
        apply_quote_finance_need_purchase_optional(patched)
        await _publish_system_default_upgrade(
            db, tenant_id, d, version,
            patched, version.route_definitions,
            DRAWING_FORM_FLOW_DESC, f"财务核价 need_purchase 取消必填({form_code})",
        )
        return
    # 报价管理：部门审批「客户类别/价格类型」取消必填 → editable
    if (
        topology_ok
        and form_code == "quote_management"
        and _flow_has_quote_dept_approver_required(version.node_definitions)
    ):
        import copy
        patched = copy.deepcopy(version.node_definitions or [])
        apply_quote_dept_approver_optional(patched)
        await _publish_system_default_upgrade(
            db, tenant_id, d, version,
            patched, version.route_definitions,
            DRAWING_FORM_FLOW_DESC, f"部门审批客户类别/价格类型取消必填({form_code})",
        )
        return
    # 报价管理：通知尚高华 → 通知发起人
    if (
        topology_ok
        and form_code == "quote_management"
        and _flow_missing_quote_notify_initiator(version.node_definitions)
    ):
        import copy
        patched = copy.deepcopy(version.node_definitions or [])
        apply_quote_notify_initiator(patched)
        await _publish_system_default_upgrade(
            db, tenant_id, d, version,
            patched, version.route_definitions,
            DRAWING_FORM_FLOW_DESC, f"通知尚高华改为通知发起人({form_code})",
        )
        return
    # 报价管理：王玲玲/段荣凯/冶金 从空 sales_manager 改为具名用户或可选范围
    if (
        topology_ok
        and form_code == "quote_management"
        and _flow_quote_needs_named_role_approvers(version.node_definitions)
    ):
        import copy
        patched = copy.deepcopy(version.node_definitions or [])
        apply_quote_named_role_approvers(patched)
        await _publish_system_default_upgrade(
            db, tenant_id, d, version,
            patched, version.route_definitions,
            DRAWING_FORM_FLOW_DESC, f"报价角色审批改为具名用户/可选范围({form_code})",
        )
        return
    # 售出产品更换：业务经理/客服会签 → 部门负责人 + cs_office
    # 不依赖 topology_ok
    if (
        form_code == "cs_product_replace"
        and _flow_cs_product_replace_needs_approver_fix(version.node_definitions)
    ):
        import copy
        from app.common.rbac_sync import ensure_cs_office_role_members
        await ensure_cs_office_role_members(db, tenant_id)
        patched = copy.deepcopy(version.node_definitions or [])
        apply_cs_product_replace_approvers(patched)
        await _publish_system_default_upgrade(
            db, tenant_id, d, version,
            patched, version.route_definitions,
            DRAWING_FORM_FLOW_DESC, f"售出产品更换客服节点/补登明细必填({form_code})",
        )
        return
    # 客户服务申请及反馈：客服落实→cs_office；客服安排1→cs_arrange
    # 不依赖 topology_ok：画布已手改/拓扑判定失败时也要把错误角色改回
    if (
        form_code == "cs_service_request"
        and _flow_cs_service_request_needs_approver_fix(version.node_definitions)
    ):
        import copy
        from app.common.rbac_sync import (
            ensure_cs_arrange_role_members,
            ensure_cs_office_role_members,
        )
        await ensure_cs_office_role_members(db, tenant_id)
        await ensure_cs_arrange_role_members(db, tenant_id)
        patched = copy.deepcopy(version.node_definitions or [])
        apply_cs_service_request_approvers(patched)
        await _publish_system_default_upgrade(
            db, tenant_id, d, version,
            patched, version.route_definitions,
            DRAWING_FORM_FLOW_DESC,
            f"客服落实/客服安排改为指定角色cs_office+cs_arrange({form_code})",
        )
        return
    # 售出产品/工具退回：客服办理 → cs_office；物流节点去掉误挂的明细可填；
    # 会签人员(field_18) 按人选并行分流（不再误用简道云部门 id 互斥）
    if form_code == "cs_product_return" and (
        _flow_cs_product_return_needs_approver_fix(version.node_definitions)
        or _flow_cs_product_return_needs_logistics_field_fix(version.node_definitions)
        or _flow_cs_product_return_needs_n20_route_fix(version.route_definitions)
    ):
        import copy
        from app.common.rbac_sync import ensure_cs_office_role_members
        await ensure_cs_office_role_members(db, tenant_id)
        patched = copy.deepcopy(version.node_definitions or [])
        patched_routes = copy.deepcopy(version.route_definitions or [])
        tags: list[str] = []
        if apply_cs_product_return_approvers(patched):
            tags.append("客服办理cs_office")
        if apply_cs_product_return_logistics_field_perms(patched):
            tags.append("物流节点字段")
        if apply_cs_product_return_n20_countersign_routes(patched_routes):
            tags.append("会签人员并行分流")
        if tags:
            await _publish_system_default_upgrade(
                db, tenant_id, d, version,
                patched, patched_routes,
                DRAWING_FORM_FLOW_DESC, f"售出产品退回修正({'+'.join(tags)})({form_code})",
            )
        return
    # 客户服务延期申请：客服反馈/备案→cs_office；客服审批→cs_delay_approve
    if (
        form_code == "cs_service_delay"
        and _flow_cs_service_delay_needs_approver_fix(version.node_definitions)
    ):
        import copy
        from app.common.rbac_sync import (
            ensure_cs_delay_approve_role_members,
            ensure_cs_office_role_members,
        )
        await ensure_cs_office_role_members(db, tenant_id)
        await ensure_cs_delay_approve_role_members(db, tenant_id)
        patched = copy.deepcopy(version.node_definitions or [])
        apply_cs_service_delay_approvers(patched)
        await _publish_system_default_upgrade(
            db, tenant_id, d, version,
            patched, version.route_definitions,
            DRAWING_FORM_FLOW_DESC, f"客服延期审批改为cs_office+cs_delay_approve({form_code})",
        )
        return
    # 客服往来函件：内勤办理 → cs_office
    if (
        form_code == "cs_correspondence"
        and _flow_cs_correspondence_needs_approver_fix(version.node_definitions)
    ):
        import copy
        from app.common.rbac_sync import ensure_cs_office_role_members
        await ensure_cs_office_role_members(db, tenant_id)
        patched = copy.deepcopy(version.node_definitions or [])
        apply_cs_correspondence_approvers(patched)
        await _publish_system_default_upgrade(
            db, tenant_id, d, version,
            patched, version.route_definitions,
            DRAWING_FORM_FLOW_DESC, f"往来函件内勤改为cs_office({form_code})",
        )
        return
    # 迅焊公司合同评审：法务审批 → legal；法务主管 → 袁文俊；信息反馈回路 reenter
    if form_code == "xunhan_contract_review" and (
        _flow_xunhan_contract_review_needs_approver_fix(version.node_definitions)
        or _flow_xunhan_feedback_routes_need_fix(version.route_definitions)
    ):
        import copy
        from app.common.rbac_sync import ensure_legal_role_members
        await ensure_legal_role_members(db, tenant_id)
        patched = copy.deepcopy(version.node_definitions or [])
        patched_routes = copy.deepcopy(version.route_definitions or [])
        apply_xunhan_contract_review_approvers(patched)
        patch_xunhan_contract_review_feedback_routes(patched_routes)
        await _publish_system_default_upgrade(
            db, tenant_id, d, version,
            patched, patched_routes,
            DRAWING_FORM_FLOW_DESC, f"迅焊法务+反馈回路+法务主管袁文俊({form_code})",
        )
        n_reassign = await _reassign_pending_legal_sup_tasks(db, tenant_id)
        if n_reassign:
            await db.commit()
        return
    # 生产卡补充：物料编码 / 法务审核
    if (
        form_code == "prod_card_supplement"
        and _flow_prod_card_supplement_needs_approver_fix(version.node_definitions)
    ):
        import copy
        from app.common.rbac_sync import (
            ensure_legal_role_members,
            ensure_prod_elec_workshop_role_members,
            ensure_prod_material_code_role_members,
        )
        await ensure_prod_material_code_role_members(db, tenant_id)
        await ensure_prod_elec_workshop_role_members(db, tenant_id)
        await ensure_legal_role_members(db, tenant_id)
        patched = copy.deepcopy(version.node_definitions or [])
        apply_prod_card_supplement_approvers(patched)
        await _publish_system_default_upgrade(
            db, tenant_id, d, version,
            patched, version.route_definitions,
            DRAWING_FORM_FLOW_DESC, f"生产卡物料编码/电气车间/法务改为角色({form_code})",
        )
        return
    # 生产卡：业务员确认可填协议确认；区域经理挂在业务员确认之后；通知生产抄送
    if form_code == "prod_card_supplement":
        import copy
        from app.domains.lowcode.prod_card_contract_fill import (
            apply_prod_card_design_assign_field_perms,
            apply_prod_card_prune_legacy_field_perms,
            apply_prod_card_sales_before_region,
            apply_prod_card_sales_confirm_field_perms,
        )
        patched = copy.deepcopy(version.node_definitions or [])
        patched_routes = copy.deepcopy(version.route_definitions or [])
        tags: list[str] = []
        if apply_prod_card_sales_confirm_field_perms(patched):
            tags.append("业务员确认可填协议确认")
        if apply_prod_card_design_assign_field_perms(patched):
            tags.append("安排设计剔除派人/技术协议评审+设计指派字段")
        if apply_prod_card_prune_legacy_field_perms(patched):
            tags.append("剔除废弃字段室主任0414")
        if apply_prod_card_sales_before_region(patched, patched_routes):
            tags.append("先业务员确认再区域经理")
        if apply_prod_card_notify_production_cc(patched):
            tags.append("通知生产抄送吕英萍雷贤吴超")
        if apply_prod_card_xiaomeng_yangshuang_cc(patched, patched_routes):
            tags.append("小萌工厂杨霜审批+抄送∥结束")
        from app.domains.lowcode.wf_node_actions import apply_prod_card_material_code_node_actions
        if apply_prod_card_material_code_node_actions(patched):
            tags.append("物料编码关闭转交")
        if tags:
            await _publish_system_default_upgrade(
                db, tenant_id, d, version,
                patched, patched_routes,
                DRAWING_FORM_FLOW_DESC, "+".join(tags),
            )
            return
    # 客服领图：研管办→郑志颖；部门指派节点填写项对齐图纸领用
    if (
        topology_ok
        and form_code == "cs_drawing_request"
        and (
            _flow_cs_drawing_needs_approver_fix(version.node_definitions)
            or _flow_cs_drawing_needs_assign_perms(version.node_definitions)
        )
    ):
        import copy
        patched = copy.deepcopy(version.node_definitions or [])
        apply_cs_drawing_approvers(patched)
        await _publish_system_default_upgrade(
            db, tenant_id, d, version,
            patched, version.route_definitions,
            DRAWING_FORM_FLOW_DESC, f"客服领图部门指派对齐图纸领用({form_code})",
        )
        return
    # 发货通知：并行分叉 + 业务员验收单 + 物流/门岗角色
    if form_code == "shipment_notice":
        from app.domains.lowcode.shipment_notice_fields import (
            patch_shipment_notice_parallel_routes,
            shipment_sales_accept_perms_ok,
        )
        need_nodes = (
            _flow_shipment_logistics_needs_fix(version.node_definitions)
            or not shipment_sales_accept_perms_ok(version.node_definitions)
        )
        need_routes = _flow_shipment_parallel_fork_broken(version.route_definitions)
        if need_nodes or need_routes:
            import copy
            from app.common.rbac_sync import (
                ensure_gate_guard_role_members,
                ensure_logistics_approval_role_members,
                ensure_ship_sales_outbound_role_members,
            )
            await ensure_logistics_approval_role_members(db, tenant_id)
            await ensure_ship_sales_outbound_role_members(db, tenant_id)
            await ensure_gate_guard_role_members(db, tenant_id)
            patched_nodes = copy.deepcopy(version.node_definitions or [])
            patched_routes = copy.deepcopy(version.route_definitions or [])
            apply_shipment_notice_approvers(patched_nodes)
            patch_shipment_notice_parallel_routes(patched_routes)
            reason = "发货通知开具提货单后生产领料与仓库判定并行"
            if need_nodes and need_routes:
                reason = "发货通知并行分叉与业务员验收单字段权限"
            elif need_nodes:
                reason = "发货通知业务员验收单字段权限与审批角色"
            await _publish_system_default_upgrade(
                db, tenant_id, d, version,
                patched_nodes, patched_routes,
                DRAWING_FORM_FLOW_DESC, f"{reason}({form_code})",
            )
            return
    # 售前服务通知：总工审批 sales_manager → 曹修国
    if (
        topology_ok
        and form_code == "presale_service_notice"
        and _flow_presale_chief_needs_specified_user(version.node_definitions)
    ):
        import copy
        patched = copy.deepcopy(version.node_definitions or [])
        apply_presale_chief_specified_user(patched)
        await _publish_system_default_upgrade(
            db, tenant_id, d, version,
            patched, version.route_definitions,
            DRAWING_FORM_FLOW_DESC, f"总工审批改为指定用户曹修国({form_code})",
        )
        return
    # 售前服务通知：抄送同时通知发起人 + 表单申请人
    if (
        topology_ok
        and form_code == "presale_service_notice"
        and _flow_presale_cc_needs_applicant(version.node_definitions)
    ):
        import copy
        patched = copy.deepcopy(version.node_definitions or [])
        apply_presale_cc_initiator_and_applicant(patched)
        await _publish_system_default_upgrade(
            db, tenant_id, d, version,
            patched, version.route_definitions,
            DRAWING_FORM_FLOW_DESC, f"抄送改为发起人+申请人({form_code})",
        )
        return
    # 售前服务通知：总工审批必填「人员协调」（下游节点审批人取自该字段）
    if (
        topology_ok
        and form_code == "presale_service_notice"
        and _flow_presale_chief_needs_staff_coordination_required(version.node_definitions)
    ):
        import copy
        patched = copy.deepcopy(version.node_definitions or [])
        apply_presale_chief_staff_coordination_required(patched)
        await _publish_system_default_upgrade(
            db, tenant_id, d, version,
            patched, version.route_definitions,
            DRAWING_FORM_FLOW_DESC, f"总工审批必填人员协调({form_code})",
        )
        return
    # 开票申请：提交旁路仍挂发起；「可下载」须在发起人接收之后（不依赖 topology_ok，
    # 否则 cc→end 会被旧 cc_end_bug 判成整图重发，把连线打回开票旁路）
    if (
        form_code == "invoice_application"
        and _flow_missing_invoice_sales_cc(
            version.node_definitions, version.route_definitions,
        )
    ):
        import copy
        patched_nodes = copy.deepcopy(version.node_definitions or [])
        patched_routes = copy.deepcopy(version.route_definitions or [])
        apply_invoice_sales_cc(patched_nodes, patched_routes)
        await _publish_system_default_upgrade(
            db, tenant_id, d, version,
            patched_nodes, patched_routes,
            DRAWING_FORM_FLOW_DESC, f"开票申请可下载改到发起人接收后({form_code})",
        )
        return
    # 收款登记：抄送叠加表单部门负责人 + 业务人员
    if (
        topology_ok
        and form_code == "payment_registration"
        and _flow_payment_cc_needs_dept_head(version.node_definitions)
    ):
        import copy
        patched = copy.deepcopy(version.node_definitions or [])
        apply_payment_registration_cc_dept_head(patched)
        await _publish_system_default_upgrade(
            db, tenant_id, d, version,
            patched, version.route_definitions,
            DRAWING_FORM_FLOW_DESC, f"抄送叠加部门负责人与业务人员({form_code})",
        )
        return
    if (
        form_code in _CS_SALES_CC_FORM_CODES
        and _flow_missing_cs_sales_cc_on_start(
            version.node_definitions, version.route_definitions,
        )
    ):
        import copy
        patched_nodes = copy.deepcopy(version.node_definitions or [])
        patched_routes = copy.deepcopy(version.route_definitions or [])
        apply_cs_sales_cc_on_start(patched_nodes, patched_routes)
        await _publish_system_default_upgrade(
            db, tenant_id, d, version,
            patched_nodes, patched_routes,
            DRAWING_FORM_FLOW_DESC, f"发起旁路抄送业务员({form_code})",
        )
        return
    # 安装图设计通知：剥离业务打分（及打分备注）节点可填权限
    if topology_ok and form_code == "install_drawing_notice":
        from app.domains.lowcode.biz_score import (
            flow_has_install_score_perms, strip_biz_score_flow_nodes,
        )
        if flow_has_install_score_perms(version.node_definitions):
            import copy
            patched = copy.deepcopy(version.node_definitions or [])
            strip_biz_score_flow_nodes(patched, extra_fields=frozenset({"remark"}))
            await _publish_system_default_upgrade(
                db, tenant_id, d, version,
                patched, version.route_definitions,
                DRAWING_FORM_FLOW_DESC, f"安装图设计通知去掉业务打分字段权限({form_code})",
            )
            return
    # 方案管理：剥离业务打分三项（及总分/日期）节点可填权限
    if topology_ok and form_code == "scheme_management":
        from app.domains.lowcode.biz_score import (
            flow_has_biz_score_perms, strip_biz_score_flow_nodes,
        )
        if flow_has_biz_score_perms(version.node_definitions):
            import copy
            patched = copy.deepcopy(version.node_definitions or [])
            strip_biz_score_flow_nodes(patched)
            await _publish_system_default_upgrade(
                db, tenant_id, d, version,
                patched, version.route_definitions,
                DRAWING_FORM_FLOW_DESC, f"方案管理去掉业务打分字段权限({form_code})",
            )
            return
    # 安装图/方案/领用：部门审批·市场支持·总工 意见必填
    if (
        topology_ok
        and form_code in ("install_drawing_notice", "scheme_management", "drawing_requisition")
        and _flow_missing_drawing_pre_chief_opinion(version.node_definitions)
    ):
        import copy
        patched = copy.deepcopy(version.node_definitions or [])
        apply_drawing_pre_chief_opinion_required(patched)
        await _publish_system_default_upgrade(
            db, tenant_id, d, version,
            patched, version.route_definitions,
            DRAWING_FORM_FLOW_DESC, f"部门/市场支持/总工意见必填({form_code})",
        )
        return
    # 仅缺总工「是否需要总经理审批」：就地补 field_perms，避免整图覆盖已 remap 的审批人
    if (
        topology_ok
        and form_code == "scheme_management"
        and _flow_missing_chief_gm_perm(version.node_definitions)
    ):
        import copy
        from app.domains.lowcode.biz_score import apply_chief_gm_flow_nodes
        patched = copy.deepcopy(version.node_definitions or [])
        apply_chief_gm_flow_nodes(patched)
        await _publish_system_default_upgrade(
            db, tenant_id, d, version,
            patched, version.route_definitions,
            DRAWING_FORM_FLOW_DESC, f"总工审批补 need_gm_approval({form_code})",
        )
        return
    # 仅缺无合同号 need_gm→总经理审批 分支：就地补节点/路由
    if (
        topology_ok
        and form_code == "scheme_management"
        and _flow_missing_install_gm_branch(version.node_definitions, version.route_definitions)
    ):
        import copy
        from app.domains.lowcode.biz_score import apply_install_gm_branch
        patched_nodes = copy.deepcopy(version.node_definitions or [])
        patched_routes = copy.deepcopy(version.route_definitions or [])
        apply_install_gm_branch(patched_nodes, patched_routes)
        await _publish_system_default_upgrade(
            db, tenant_id, d, version,
            patched_nodes, patched_routes,
            DRAWING_FORM_FLOW_DESC, f"无合同号总工按 need_gm 走总经理审批({form_code})",
        )
        return
    # 工艺包装分叉：互斥 + 包装优先（对齐简道云实单；纠正曾误标的 parallel）
    if topology_ok and form_code in (
        "drawing_requisition", "install_drawing_notice", "scheme_management",
        "prod_card_supplement",
    ):
        import copy
        patched_routes = copy.deepcopy(version.route_definitions or [])
        if fix_packaging_fork_serial_priority(
            version.node_definitions, patched_routes,
        ):
            await _publish_system_default_upgrade(
                db, tenant_id, d, version,
                version.node_definitions, patched_routes,
                DRAWING_FORM_FLOW_DESC, f"工艺包装分叉改为互斥优先({form_code})",
            )
            return
    # 报价：转采购与部门通知并行；二次核价可重入；同源互斥组只覆盖非 parallel 出边
    if topology_ok:
        import copy
        patched_routes = copy.deepcopy(version.route_definitions or [])
        publish_nodes = version.node_definitions
        tags: list[str] = []
        if form_code == "quote_management" and apply_quote_purchase_inquiry_parallel(
            version.node_definitions, patched_routes,
        ):
            tags.append("转采购并行询价")
        if form_code == "quote_management" and apply_quote_finance_dept_notify_parallel(
            version.node_definitions, patched_routes,
        ):
            tags.append("财务核价部门通知并行可重入")
        if form_code == "quote_management" and apply_quote_notify_initiator_after_no_purchase(
            version.node_definitions, patched_routes,
        ):
            tags.append("通知发起人须转采购≠是")
        if form_code == "prod_card_supplement":
            from app.domains.lowcode.prod_card_contract_fill import (
                apply_prod_card_sales_before_region,
            )
            if apply_prod_card_sales_before_region(
                version.node_definitions, patched_routes,
            ):
                tags.append("先业务员确认再区域经理")
            patched_nodes = copy.deepcopy(version.node_definitions or [])
            if apply_prod_card_notify_production_cc(patched_nodes):
                tags.append("通知生产抄送吕英萍雷贤吴超")
                publish_nodes = patched_nodes
            if apply_prod_card_xiaomeng_yangshuang_cc(patched_nodes, patched_routes):
                tags.append("小萌工厂杨霜审批+抄送∥结束")
                publish_nodes = patched_nodes
            from app.domains.lowcode.wf_node_actions import apply_prod_card_material_code_node_actions
            if apply_prod_card_material_code_node_actions(patched_nodes):
                tags.append("物料编码关闭转交")
                publish_nodes = patched_nodes
            if fix_packaging_fork_serial_priority(publish_nodes, patched_routes):
                tags.append("工艺包装分叉互斥优先")
        if form_code == "prod_card_supplement" and apply_prod_card_finance_branch_parallel(
            version.node_definitions, patched_routes,
        ):
            tags.append("财务核价后设计/生产分支并行")
        if form_code in ("cs_service_request", "cs_product_replace") and (
            apply_cs_service_request_start_region_first(
                version.node_definitions, patched_routes,
            )
        ):
            tags.append("发起节点区域经理优先串行（对齐简道云实单）")
        if fix_always_parallel_exclusive_groups(patched_routes):
            tags.append(f"恒真并行边退出互斥组({form_code})")
        if _flow_missing_exclusive_groups(patched_routes):
            by_src: dict[str, list] = {}
            for r in patched_routes:
                if not isinstance(r, dict) or r.get("always") or _route_is_always_parallel(r):
                    continue
                src = str(r.get("source") or "")
                if src:
                    by_src.setdefault(src, []).append(r)
            for src, outs in by_src.items():
                serial = _serial_exclusive_outs(outs)
                if len(serial) < 2:
                    continue
                if _flow_src_is_unconditional_parallel_fork(outs):
                    continue
                gid = f"ex_{src}"
                for r in serial:
                    r["exclusive_group"] = gid
            tags.append(f"补同源互斥组({form_code})")
        if tags:
            await _publish_system_default_upgrade(
                db, tenant_id, d, version,
                publish_nodes, patched_routes,
                DRAWING_FORM_FLOW_DESC, "+".join(tags),
            )
            if form_code == "quote_management":
                await _finish_quote_purchase_runtime_fix(db, tenant_id)
            return
        if form_code == "quote_management":
            await _finish_quote_purchase_runtime_fix(db, tenant_id)
    aligned = topology_ok and not _flow_missing_exclusive_groups(version.route_definitions)
    if aligned and not need_id_remap:
        # 拓扑已对齐且无 JDY MongoId：仍清掉 CRM 不存在的部门条件（未知部门）
        cleaned, stats = await sanitize_route_ids_for_tenant(
            db, tenant_id, version.route_definitions,
        )
        touched = (
            (stats.get("dept_clean") or {}).get("values_removed", 0)
            + (stats.get("person_clean") or {}).get("values_removed", 0)
            + (stats.get("dept_clean") or {}).get("routes_dropped", 0)
            + (stats.get("person_clean") or {}).get("routes_dropped", 0)
            + (stats.get("dept_remap") or {}).get("replaced", 0)
            + (stats.get("person_remap") or {}).get("replaced", 0)
        )
        if touched > 0:
            await _publish_system_default_upgrade(
                db, tenant_id, d, version,
                version.node_definitions, cleaned,
                DRAWING_FORM_FLOW_DESC, f"清除未知部门/人员条件({form_code})",
            )
        return
    # 拓扑已对齐、仅条件仍是简道云 MongoId：只改 routes，不覆盖画布节点
    if aligned and need_id_remap:
        cleaned, stats = await sanitize_route_ids_for_tenant(
            db, tenant_id, version.route_definitions,
        )
        touched = (
            (stats.get("dept_clean") or {}).get("values_removed", 0)
            + (stats.get("person_clean") or {}).get("values_removed", 0)
            + (stats.get("dept_clean") or {}).get("routes_dropped", 0)
            + (stats.get("person_clean") or {}).get("routes_dropped", 0)
            + (stats.get("dept_remap") or {}).get("replaced", 0)
            + (stats.get("person_remap") or {}).get("replaced", 0)
        )
        if touched <= 0:
            return
        await _publish_system_default_upgrade(
            db, tenant_id, d, version,
            version.node_definitions, cleaned,
            DRAWING_FORM_FLOW_DESC, f"简道云部门/人员ID→CRM({form_code})",
        )
        return
    # 生成图里仍是 JDY MongoId，发布前换成 CRM UUID，并去掉无法映射的残留
    new_routes, _ = await sanitize_route_ids_for_tenant(db, tenant_id, new_routes)
    if form_code == "drawing_requisition":
        d.name = "合同图纸（资料）领用申请"
    elif form_code == "install_drawing_notice":
        d.name = "安装图设计通知"
    elif form_code == "scheme_management":
        d.name = "方案管理"
    elif form_code == "prod_card_supplement":
        d.name = "生产卡/补充流程"
    elif form_code == "invoice_application":
        d.name = "开票申请"
    elif form_code == "payment_registration":
        d.name = "收款登记"
    elif form_code == "quote_management":
        d.name = "报价管理"
    elif form_code == "pricing_checklist_hjqd":
        d.name = "核价清单传递"
    elif form_code == "research_coop_card":
        d.name = "中央研究院协同卡"
    elif form_code == "tech_agreement_feedback":
        d.name = "技术协议反馈单"
    elif form_code == "contract_outsource_early":
        d.name = "合同外购件提前安排流程"
    elif form_code == "biz_bonus_transfer":
        d.name = "业务奖金流转单"
    elif form_code == "biz_bonus_biz_initiate":
        d.name = "业务奖金流转—业务发起"
    elif form_code == "commission_database":
        d.name = "提成数据库"
    elif form_code == "cs_service_request":
        d.name = "客户服务申请及反馈"
    elif form_code == "cs_product_replace":
        d.name = "售出产品更换（补发）"
    elif form_code == "cs_product_return":
        d.name = "售出产品/工具退回"
    elif form_code == "cs_loan_slip":
        d.name = "客服借据"
    elif form_code == "cs_drawing_request":
        d.name = "客服领图"
    elif form_code == "cs_service_delay":
        d.name = "客户服务延期申请"
    elif form_code == "cs_correspondence":
        d.name = "客服往来函件"
    elif form_code == "shipment_notice":
        d.name = "发货通知"
    elif form_code == "xunhan_contract_review":
        d.name = "迅焊公司合同评审"
    await _publish_system_default_upgrade(
        db, tenant_id, d, version, new_nodes, new_routes,
        DRAWING_FORM_FLOW_DESC, f"简道云表单流({form_code})",
    )


async def ensure_default_definition(
    db, tenant_id, biz_type: str, code: str, name: str,
    approver_rule: dict, multi_mode: str = "or_sign",
    empty_strategy: str = "auto_approve",
) -> WfProcessDefinition | None:
    """为某 biz_type 兜底创建并发布一条「默认流程」。

    - 线索：start → 内勤审批 → 抄送负责人 → end
    - 合同版本：对齐简道云登记运营流（财务 → 条件并行运营部门）
    - 合同评审：对齐简道云会签主干
    - 其它：start → 审批 → end

    已存在任何已发布的同 biz_type 流程时：系统兜底流可按规则升级；租户自建优先命中。
    """
    with_owner_cc = biz_type == "lead"
    # 线索系统兜底流：无论当前命中的是哪条 lead 流程，都尝试给 SYS_LEAD_REVIEW 补抄送节点
    if with_owner_cc:
        sys_def = (await db.execute(select(WfProcessDefinition).where(
            WfProcessDefinition.tenant_id == tenant_id,
            WfProcessDefinition.code == code,
            WfProcessDefinition.is_deleted == False,  # noqa: E712
        ).limit(1))).scalar_one_or_none()
        if sys_def and sys_def.status == "published":
            await _upgrade_default_owner_cc_if_needed(
                db, tenant_id, sys_def, name, approver_rule, multi_mode, empty_strategy,
            )
            await _upgrade_lead_jdy_labels_if_needed(
                db, tenant_id, sys_def, name, approver_rule, multi_mode, empty_strategy,
            )
            await _upgrade_lead_intel_field_perms_if_needed(db, tenant_id, sys_def)
            await _upgrade_lead_intel_specified_users_if_needed(db, tenant_id, sys_def)
            await _upgrade_lead_owner_confirm_to_approval_if_needed(db, tenant_id, sys_def)
            await _upgrade_lead_confirm_reporter_if_needed(db, tenant_id, sys_def)

    if biz_type == "contract_version":
        sys_def = (await db.execute(select(WfProcessDefinition).where(
            WfProcessDefinition.tenant_id == tenant_id,
            WfProcessDefinition.code == code,
            WfProcessDefinition.is_deleted == False,  # noqa: E712
        ).limit(1))).scalar_one_or_none()
        if sys_def and sys_def.status == "published":
            await _upgrade_contract_version_jdy_reg_if_needed(db, tenant_id, sys_def)

    if biz_type == "contract_review":
        sys_def = (await db.execute(select(WfProcessDefinition).where(
            WfProcessDefinition.tenant_id == tenant_id,
            WfProcessDefinition.code == code,
            WfProcessDefinition.is_deleted == False,  # noqa: E712
        ).limit(1))).scalar_one_or_none()
        if sys_def and sys_def.status == "published":
            await _upgrade_contract_review_jdy_if_needed(db, tenant_id, sys_def)

    if biz_type == "tech_agreement_review":
        sys_def = (await db.execute(select(WfProcessDefinition).where(
            WfProcessDefinition.tenant_id == tenant_id,
            WfProcessDefinition.code == code,
            WfProcessDefinition.is_deleted == False,  # noqa: E712
        ).limit(1))).scalar_one_or_none()
        if sys_def and sys_def.status == "published":
            await _upgrade_tech_agreement_jdy_if_needed(db, tenant_id, sys_def)

    if biz_type == "lead_reactivation":
        sys_def = (await db.execute(select(WfProcessDefinition).where(
            WfProcessDefinition.tenant_id == tenant_id,
            WfProcessDefinition.code == code,
            WfProcessDefinition.is_deleted == False,  # noqa: E712
        ).limit(1))).scalar_one_or_none()
        if sys_def and sys_def.status == "published":
            await _upgrade_lead_reactivation_label_if_needed(db, tenant_id, sys_def)
            await _upgrade_lead_reactivation_jdy_graph_if_needed(db, tenant_id, sys_def)

    existing = (await db.execute(select(WfProcessDefinition).where(
        WfProcessDefinition.tenant_id == tenant_id,
        WfProcessDefinition.biz_type == biz_type,
        WfProcessDefinition.status == "published",
        WfProcessDefinition.is_deleted == False,  # noqa: E712
    ).limit(1))).scalar_one_or_none()
    if existing:
        return existing

    if biz_type == "contract_version":
        nodes, routes = _contract_version_flow_graph()
        description = CONTRACT_VERSION_DEFAULT_DESC
    elif biz_type == "contract_review":
        nodes, routes = _contract_review_flow_graph()
        description = CONTRACT_REVIEW_DEFAULT_DESC
    elif biz_type == "tech_agreement_review":
        nodes, routes = _tech_agreement_flow_graph()
        description = TECH_AGREEMENT_DEFAULT_DESC
    elif biz_type == "customer":
        nodes, routes = _customer_info_flow_graph()
        description = CUSTOMER_INFO_DEFAULT_DESC
    elif biz_type == "lead_reactivation":
        nodes, routes = _lead_reactivation_flow_graph(
            name, approver_rule, multi_mode, empty_strategy,
        )
        description = LEAD_REACTIVATION_DEFAULT_DESC
    else:
        nodes, routes = _default_flow_graph(
            name, approver_rule, multi_mode, empty_strategy, with_owner_cc=with_owner_cc,
        )
        description = "系统默认流程（未配置可视化流程时兜底使用，可直接编辑）"

    # 同 code 的兜底流程可能已存在但被软删/取消发布 —— 唯一索引 (tenant_id, code)
    # 不区分软删，直接插入会撞唯一键，所以先查后复活。
    mine = (await db.execute(select(WfProcessDefinition).where(
        WfProcessDefinition.tenant_id == tenant_id,
        WfProcessDefinition.code == code,
    ).limit(1))).scalar_one_or_none()
    if mine is not None:
        revived = await _revive_default_definition(db, tenant_id, mine, nodes, routes)
        if biz_type == "contract_version" and revived:
            await _upgrade_contract_version_jdy_reg_if_needed(db, tenant_id, revived)
        if biz_type == "contract_review" and revived:
            await _upgrade_contract_review_jdy_if_needed(db, tenant_id, revived)
        if biz_type == "tech_agreement_review" and revived:
            await _upgrade_tech_agreement_jdy_if_needed(db, tenant_id, revived)
        return revived

    d = WfProcessDefinition(
        id=generate_uuid(), tenant_id=tenant_id, name=name, code=code,
        description=description,
        category=SYSTEM_DEFAULT_CATEGORY, biz_type=biz_type,
        status="published", current_version=1, sort_order=_SYSTEM_DEFAULT_SORT,
    )
    db.add(d)
    v = WfProcessDefinitionVersion(
        id=generate_uuid(), tenant_id=tenant_id, process_definition_id=d.id,
        version_number=1, node_definitions=nodes, route_definitions=routes,
        approver_rules=[], status="published", published_at=_now(),
    )
    db.add(v)
    try:
        await db.commit()
    except IntegrityError:
        # 并发下另一个请求已建好同 code 的定义，回滚后复活/取回（避免拿到软删不可用行）
        await db.rollback()
        raced = (await db.execute(select(WfProcessDefinition).where(
            WfProcessDefinition.tenant_id == tenant_id,
            WfProcessDefinition.code == code,
        ).limit(1))).scalar_one_or_none()
        if raced is not None:
            revived = await _revive_default_definition(db, tenant_id, raced, nodes, routes)
            if biz_type == "contract_version" and revived:
                await _upgrade_contract_version_jdy_reg_if_needed(db, tenant_id, revived)
            if biz_type == "contract_review" and revived:
                await _upgrade_contract_review_jdy_if_needed(db, tenant_id, revived)
            return revived
        return None
    return d


def _flow_has_owner_cc(nodes: list | None) -> bool:
    """是否已有「业务员确认是否转商机」节点（历史抄送或现行审批均可）。"""
    for n in nodes or []:
        nid = n.get("id")
        name = (n.get("name") or "").strip()
        rule = n.get("approver_rule") or (n.get("config") or {}).get("approver_rule") or {}
        is_confirm_rule = _is_lead_confirm_person_rule(rule)
        if nid in _LEAD_OWNER_CONFIRM_LEGACY_IDS:
            return True
        if name in (_LEAD_JDY_CC, "通知业务员确认转化") and (
            n.get("type") in ("cc", "approval") or is_confirm_rule
        ):
            return True
        if n.get("type") == "cc" and is_confirm_rule:
            return True
        if n.get("type") == "approval" and is_confirm_rule and (
            "转商机" in name or "确认转化" in name
        ):
            return True
    return False


def _flow_owner_confirm_is_approval(nodes: list | None) -> bool:
    """业务员确认节点是否已是审批（而非秒完的抄送）。"""
    for n in nodes or []:
        if n.get("type") != "approval":
            continue
        nid = n.get("id")
        name = (n.get("name") or "").strip()
        rule = n.get("approver_rule") or (n.get("config") or {}).get("approver_rule") or {}
        is_confirm_rule = _is_lead_confirm_person_rule(rule)
        if nid in _LEAD_OWNER_CONFIRM_LEGACY_IDS and (
            is_confirm_rule or not rule
        ):
            return True
        if is_confirm_rule and ("转商机" in name or name == _LEAD_JDY_CC):
            return True
    return False


def _flow_confirm_uses_reporter(nodes: list | None) -> bool:
    """确认节点是否已绑申报人 reporter_id。"""
    for n in nodes or []:
        if n.get("type") != "approval":
            continue
        nid = n.get("id")
        name = (n.get("name") or "").strip()
        rule = n.get("approver_rule") or (n.get("config") or {}).get("approver_rule") or {}
        if rule.get("type") != "form_field_person" or rule.get("value") != "reporter_id":
            continue
        if nid in _LEAD_OWNER_CONFIRM_LEGACY_IDS or "转商机" in name or name == _LEAD_JDY_CC:
            return True
    return False


def _route_cond_fields(route: dict) -> set[str]:
    cond = route.get("condition") or {}
    return {c.get("field") for c in (cond.get("cond") or []) if isinstance(c, dict) and c.get("field")}


def _flow_is_jdy_contract_reg(nodes: list | None, routes: list | None = None) -> bool:
    """已是登记完整运营图（含二级节点）、optAuth/具名审批人齐全，且财务→结束双条件。"""
    ids = {n.get("id") for n in (nodes or [])}
    if "merge_ops" not in ids:
        return False
    # 简道云二级：采购员/质检员/财务维护/采购部
    if not {"approval_purchaser", "approval_inspector", "approval_finance_maint", "approval_purch_dept"} <= ids:
        return False
    purch_ok = wh_ok = named_finance = finance_fp_ok = False
    for n in nodes or []:
        fps = n.get("field_perms") or []
        if n.get("id") == "approval_procurement":
            purch_ok = any(
                p.get("field") == "purchasers" and p.get("access") == "required" for p in fps
            )
        if n.get("id") == "approval_warehouse":
            wh_ok = any(p.get("field") == "fill_code" for p in fps)
        if n.get("id") == "approval_finance":
            rule = n.get("approver_rule") or {}
            named_finance = rule.get("type") == "specified_user"
            fin_fields = {
                (p.get("field"), p.get("access"))
                for p in fps if isinstance(p, dict)
            }
            # 合同类型/验收方式：财务审核必填（审批字段，创建不填）
            finance_fp_ok = (
                ("contract_type", "required") in fin_fields
                and ("accept_method", "required") in fin_fields
            )
    fin_end_dual = False
    for r in routes or []:
        if r.get("source") == "approval_finance" and r.get("target") == "end":
            fields = _route_cond_fields(r)
            fin_end_dual = "standard_delivery" in fields and "is_rotary_sieve" in fields
    return purch_ok and wh_ok and named_finance and finance_fp_ok and fin_end_dual


def _flow_is_jdy_contract_review(nodes: list | None, routes: list | None = None) -> bool:
    """已是完整会签图：旁路抄送/法务主管/区域经理/反馈回路齐全。"""
    ids = {n.get("id") for n in (nodes or [])}
    if "merge_review" not in ids:
        return False
    required = {
        "approval_legal_sup", "approval_region", "approval_info_feedback",
        "approval_design_fb", "approval_initiator",
        "cc_owner", "cc_install", "cc_related", "cc_lili", "cc_xunhan",
    }
    if not required <= ids:
        return False
    legal_ok = named_gm = named_legal_sup = False
    for n in nodes or []:
        if n.get("id") == "approval_legal" and n.get("field_perms"):
            legal_ok = True
        if n.get("id") == "approval_gm":
            rule = n.get("approver_rule") or {}
            named_gm = rule.get("type") == "specified_user"
        if n.get("id") == "approval_legal_sup":
            rule = n.get("approver_rule") or {}
            named_legal_sup = rule.get("type") == "specified_user"
    post_fin_ops = has_feedback_route = has_design_fb_reentry = has_start_cc = False
    export_not_intl = False
    for r in routes or []:
        if r.get("source") == "start" and r.get("target") == "cc_owner" and r.get("always"):
            has_start_cc = True
        if r.get("source") == "approval_finance_opinion" and r.get("target") == "approval_production":
            fields = _route_cond_fields(r)
            post_fin_ops = "review_type" in fields and "need_feedback" in fields
        if r.get("source") == "approval_finance_opinion" and r.get("target") == "approval_info_feedback":
            has_feedback_route = True
        if r.get("source") == "approval_design_fb" and r.get("target") == "approval_gm":
            has_design_fb_reentry = True
        if r.get("source") == "approval_biz" and r.get("target") == "approval_export":
            fields = _route_cond_fields(r)
            export_not_intl = "is_export" in fields and "department_name" in fields
    return (
        legal_ok and named_gm and named_legal_sup
        and post_fin_ops and has_feedback_route and has_design_fb_reentry
        and has_start_cc and export_not_intl
        and _contract_review_parallel_countersign_aligned(routes)
        and _contract_review_post_finance_parallel_aligned(routes)
    )


def _contract_review_parallel_countersign_aligned(routes: list | None) -> bool:
    """业务后会签边须标 fork=parallel，且不能有无条件 biz→merge（否则被当成 if/else）。"""
    has_legal_fork = False
    for r in routes or []:
        if not isinstance(r, dict) or r.get("source") != "approval_biz":
            continue
        tgt = r.get("target")
        if tgt == "merge_review" and not r.get("condition") and not r.get("always"):
            return False
        if tgt == "approval_legal" and r.get("fork") == "parallel":
            has_legal_fork = True
    return has_legal_fork


def _contract_review_post_finance_parallel_aligned(routes: list | None) -> bool:
    """财务意见→产采质+发起人须标 fork=parallel，避免与 end 兜底被当成 if/else。"""
    need = {
        "approval_production", "approval_procurement",
        "approval_qc", "approval_initiator",
    }
    found: set[str] = set()
    for r in routes or []:
        if not isinstance(r, dict) or r.get("source") != "approval_finance_opinion":
            continue
        tgt = r.get("target")
        if tgt in need and r.get("fork") == "parallel":
            found.add(str(tgt))
    return found == need


def _contract_review_feedback_reenter_aligned(routes: list | None) -> bool:
    """反馈回路再入总经理/财务意见的边须标 reenter，否则 skip_reactivate 直接结束。"""
    need = {
        ("approval_design_fb", "approval_gm"),
        ("approval_feedback_biz", "approval_gm"),
        ("approval_gm", "approval_finance_opinion"),
    }
    found: set[tuple[str, str]] = set()
    for r in routes or []:
        if not isinstance(r, dict):
            continue
        if not (r.get("reenter") or r.get("allow_reenter")):
            continue
        key = (str(r.get("source") or ""), str(r.get("target") or ""))
        if key in need:
            found.add(key)
    return found == need


def apply_contract_review_feedback_reenter(routes: list | None) -> bool:
    """给反馈回路再入总经理/财务意见的边打 reenter（对齐简道云二次审批）。"""
    want = {
        ("approval_design_fb", "approval_gm"),
        ("approval_feedback_biz", "approval_gm"),
        ("approval_gm", "approval_finance_opinion"),
    }
    changed = False
    for r in routes or []:
        if not isinstance(r, dict):
            continue
        key = (str(r.get("source") or ""), str(r.get("target") or ""))
        if key not in want:
            continue
        if not (r.get("reenter") or r.get("allow_reenter")):
            r["reenter"] = True
            changed = True
    return changed


async def _publish_system_default_upgrade(
    db, tenant_id: str, d: WfProcessDefinition,
    version: WfProcessDefinitionVersion,
    new_nodes: list[dict], new_routes: list[dict],
    description: str, log_tag: str,
) -> None:
    # 版本号取全部版本(含草稿)最大值+1，避免与未发布草稿撞号
    latest_any = await _latest_version(db, tenant_id, d.id)
    base_ver = max(
        version.version_number or 0,
        (latest_any.version_number if latest_any else 0) or 0,
    )
    next_ver = base_ver + 1
    # 废弃草稿：设计器 get_design 读最新版本，旧草稿会盖住刚升级的 published
    drafts = (await db.execute(select(WfProcessDefinitionVersion).where(
        WfProcessDefinitionVersion.tenant_id == tenant_id,
        WfProcessDefinitionVersion.process_definition_id == d.id,
        WfProcessDefinitionVersion.status == "draft",
    ))).scalars().all()
    for draft in drafts:
        draft.status = "deprecated"
    nv = WfProcessDefinitionVersion(
        id=generate_uuid(), tenant_id=tenant_id, process_definition_id=d.id,
        version_number=next_ver, node_definitions=new_nodes, route_definitions=new_routes,
        approver_rules=[], status="published", published_at=_now(),
    )
    db.add(nv)
    version.status = "deprecated"
    d.current_version = next_ver
    d.status = "published"
    d.is_deleted = False
    d.description = description
    # 同步展示名（若仍是旧系统名）
    if d.biz_type == "contract_version" and (not d.name or "法务" in (d.name or "") or "签署前" in (d.name or "")):
        d.name = "合同登记审批（运营）"
    if d.biz_type == "contract_review" and (not d.name or d.name == "合同评审审批"):
        d.name = "合同评审会签"
    if d.biz_type == "lead_reactivation" and d.name == "信息情报部审批":
        d.name = "180天项目激活审批"
    await db.commit()
    logger.info(
        "已升级系统兜底流程 %s(tenant=%s) → v%s：%s（废弃草稿 %s 条）",
        d.code, tenant_id, next_ver, log_tag, len(drafts),
    )


async def _upgrade_lead_reactivation_label_if_needed(
    db, tenant_id: str, d: WfProcessDefinition,
) -> None:
    """180天激活兜底流：流程管理里与「申报信息」情报审区分展示名。"""
    if d.code != "SYS_LEAD_REACTIVATION_REVIEW":
        return
    if d.category and d.category != SYSTEM_DEFAULT_CATEGORY:
        return
    target = "180天项目激活审批"
    changed = False
    if (d.name or "").strip() in ("信息情报部审批", ""):
        d.name = target
        changed = True
    if not d.description or LEAD_REACTIVATION_DEFAULT_DESC not in (d.description or ""):
        d.description = LEAD_REACTIVATION_DEFAULT_DESC
        changed = True
    if changed:
        await db.commit()


async def _upgrade_lead_reactivation_jdy_graph_if_needed(
    db, tenant_id: str, d: WfProcessDefinition,
) -> None:
    """旧三节点兜底图 → 简道云 180天激活完整拓扑。"""
    if d.code != "SYS_LEAD_REACTIVATION_REVIEW":
        return
    if d.category and d.category != SYSTEM_DEFAULT_CATEGORY:
        return
    version = await _published_version(db, tenant_id, d.id)
    if not version:
        return
    if _flow_is_jdy_lead_reactivation(version.node_definitions, version.route_definitions):
        return
    intel_rule = _lead_intel_approver_rule()
    new_nodes, new_routes = _lead_reactivation_flow_graph(
        d.name or "180天项目激活审批",
        intel_rule, "or_sign", "auto_approve",
    )
    await _publish_system_default_upgrade(
        db, tenant_id, d, version, new_nodes, new_routes,
        LEAD_REACTIVATION_DEFAULT_DESC, "简道云180天激活流(双内勤/情报审/抄送申报人)",
    )


async def _upgrade_contract_version_jdy_reg_if_needed(
    db, tenant_id: str, d: WfProcessDefinition,
) -> None:
    """系统兜底合同版本流：旧图（单节点/法务+财务等）升级为简道云登记运营图。"""
    if d.category and d.category != SYSTEM_DEFAULT_CATEGORY:
        return
    if d.biz_type != "contract_version":
        return
    version = await _published_version(db, tenant_id, d.id)
    if not version:
        return
    if _flow_is_jdy_contract_reg(version.node_definitions, version.route_definitions):
        return

    new_nodes, new_routes = _contract_version_flow_graph()
    await _publish_system_default_upgrade(
        db, tenant_id, d, version, new_nodes, new_routes,
        CONTRACT_VERSION_DEFAULT_DESC, "简道云登记运营流(完整二级节点)",
    )


def _contract_review_risk_perms_aligned(nodes: list | None) -> bool:
    """风险/结论/签约字段可写节点是否对齐简道云。"""
    by_id = {
        n.get("id"): n for n in (nodes or [])
        if isinstance(n, dict) and n.get("id")
    }

    def fields_of(nid: str) -> set[str]:
        n = by_id.get(nid) or {}
        return {
            str(p.get("field"))
            for p in (n.get("field_perms") or [])
            if isinstance(p, dict) and p.get("field")
        }

    fin_dir = fields_of("approval_finance_dir")
    if "finance_risk" not in fin_dir or "purchase_risk" not in fin_dir:
        return False
    if "payment_term" not in fin_dir or "conclusion" not in fin_dir:
        return False
    if "purchase_risk" in fields_of("approval_procurement"):
        return False
    if "finance_risk" in fields_of("approval_finance_opinion"):
        return False
    if "need_feedback" not in fields_of("approval_finance_opinion"):
        return False
    if "need_feedback" in fields_of("approval_info_feedback"):
        return False
    if "legal_risk" not in fields_of("approval_legal_sup"):
        return False
    if "biz_risk" not in fields_of("approval_region"):
        return False
    initiator = fields_of("approval_initiator")
    if "drawing_no" not in initiator or "opinion_exec" not in initiator:
        return False
    return True


def _contract_review_legal_sup_user_aligned(
    nodes: list | None, want: str | None = None,
) -> bool:
    """法务主管审批人是否为当前配置的具名用户。"""
    want_rule = _legal_sup_user_rule(want)
    for n in nodes or []:
        if not isinstance(n, dict) or n.get("id") != "approval_legal_sup":
            continue
        return _approver_rule_matches(n.get("approver_rule") or {}, want_rule)
    return False


def _contract_review_legal_users_aligned(
    nodes: list | None, want: list[str] | str | None = None,
) -> bool:
    """法务审批是否已改为具名用户（勿用空的 specified_role=legal）。"""
    want = want if want is not None else _JDY_REVIEW_USER["legal"]
    want_list = [want] if isinstance(want, str) else list(want)
    for n in nodes or []:
        if not isinstance(n, dict) or n.get("id") != "approval_legal":
            continue
        rule = n.get("approver_rule") or {}
        if rule.get("type") != "specified_user":
            return False
        v = rule.get("value")
        got = [v] if isinstance(v, str) else list(v or [])
        return got == want_list
    return False


def _contract_review_finance_dir_aligned(
    nodes: list | None, want: list[str] | str | None = None,
) -> bool:
    """财务总监意见：业务确认仅张光（或签），勿保留李晋会签。"""
    want = want if want is not None else _JDY_REVIEW_USER["finance_dir"]
    want_list = [want] if isinstance(want, str) else list(want)
    for n in nodes or []:
        if not isinstance(n, dict) or n.get("id") != "approval_finance_dir":
            continue
        rule = n.get("approver_rule") or {}
        if rule.get("type") != "specified_user":
            return False
        v = rule.get("value")
        got = [v] if isinstance(v, str) else list(v or [])
        mode = n.get("multi_mode") or "or_sign"
        if mode == "and_sign":
            mode = "countersign"
        # 单人应或签；多人会签也不再符合当前业务
        if got != want_list:
            return False
        if len(want_list) == 1 and mode == "countersign":
            return False
        return True
    return False


def apply_contract_review_named_legal_approvers(nodes: list[dict]) -> bool:
    """就地改：法务审批 specified_role=legal → 法务部具名用户（或签）。"""
    want = _JDY_REVIEW_USER["legal"]
    want_list = [want] if isinstance(want, str) else list(want)
    want_rule = {
        "type": "specified_user",
        "value": want_list[0] if len(want_list) == 1 else want_list,
        "exclude_initiator": True,
    }
    changed = False
    for n in nodes or []:
        if not isinstance(n, dict) or n.get("id") != "approval_legal":
            continue
        cur = n.get("approver_rule") or {}
        if cur.get("type") == want_rule["type"] and cur.get("value") == want_rule["value"]:
            return False
        n["approver_rule"] = dict(want_rule)
        n.setdefault("multi_mode", "or_sign")
        n.setdefault("empty_strategy", "auto_approve")
        changed = True
        break
    return changed


async def _resolve_legal_sup_user(db, tenant_id: str) -> tuple[str | None, str | None]:
    """解析租户内法务主管 (user_id, username)；优先配置 username，否则按姓名「袁文俊」。"""
    from app.domains.auth.models import User

    want = _JDY_REVIEW_USER["legal_sup"]
    if isinstance(want, list):
        want = want[0]
    row = (await db.execute(
        select(User.id, User.username).where(
            User.tenant_id == tenant_id,
            User.username == want,
        ).limit(1)
    )).first()
    if row:
        return row[0], row[1]
    row = (await db.execute(
        select(User.id, User.username).where(
            User.tenant_id == tenant_id,
            User.real_name == "袁文俊",
        ).limit(1)
    )).first()
    if row:
        return row[0], row[1]
    return None, None


async def _reassign_pending_legal_sup_tasks(db, tenant_id: str) -> int:
    """在途「法务主管审批」待办改派到当前 legal_sup 用户。"""
    uid, want_username = await _resolve_legal_sup_user(db, tenant_id)
    if not uid:
        logger.warning(
            "法务主管改派跳过：租户 %s 未找到 username=%s / 姓名袁文俊",
            tenant_id, _JDY_REVIEW_USER["legal_sup"],
        )
        return 0

    rows = (await db.execute(text("""
        SELECT t.id AS task_id, t.assignee_id, pi.business_no
        FROM wf_task_instance t
        JOIN wf_node_instance ni ON ni.id = t.node_instance_id
        JOIN wf_process_instance pi ON pi.id = t.process_instance_id
        WHERE pi.tenant_id = :tid
          AND pi.status = 'running'
          AND t.status IN ('pending', 'waiting')
          AND ni.node_def_id IN ('approval_legal_sup', 'n29')
          AND t.assignee_id IS DISTINCT FROM :uid
    """), {"tid": tenant_id, "uid": uid})).mappings().all()
    for r in rows:
        await db.execute(text("""
            UPDATE wf_task_instance
            SET assignee_id = :uid, dingtalk_todo_id = NULL, version = version + 1
            WHERE id = :tid
        """), {"uid": uid, "tid": r["task_id"]})
        logger.info(
            "法务主管待办改派 %s: %s → %s(%s)",
            r["business_no"] or r["task_id"], r["assignee_id"], uid, want_username,
        )
    return len(rows)


async def _repair_contract_review_skipped_legal(
    db, tenant_id: str,
) -> tuple[int, "WorkflowEngine | None"]:
    """修复因空角色 legal 被 auto_approve 直接跳到法务主管的单据。

    覆盖：在途卡在法务主管、以及被主管提前驳回正在「修改并重新提交」的单。
    撤回主管/修订待办，补建法务会签，并补激活被 if/else 误吞的设计/财务总监。
    """
    from app.domains.auth.models import User
    from app.domains.lowcode.approver_resolver import ApprovalContext
    from app.domains.lowcode.wf_biz_writeback import writeback

    want_legal = _JDY_REVIEW_USER["legal"]
    want_list = [want_legal] if isinstance(want_legal, str) else list(want_legal)
    legal_uids = list((await db.execute(
        select(User.id).where(
            User.tenant_id == tenant_id,
            User.username.in_(want_list),
            User.is_active == True,  # noqa: E712
        )
    )).scalars().all())
    if not legal_uids:
        logger.warning("补建法务待办跳过：租户 %s 无具名法务用户 %s", tenant_id, want_list)
        return 0, None

    # 从未建过法务节点，且已经到过法务主管（在途或被提前驳回）
    rows = (await db.execute(text("""
        SELECT pi.id AS pid
        FROM wf_process_instance pi
        WHERE pi.tenant_id = :tid
          AND pi.biz_type = 'contract_review'
          AND pi.status IN ('running', 'rejected')
          AND EXISTS (
            SELECT 1 FROM wf_node_instance ni
            WHERE ni.process_instance_id = pi.id
              AND ni.node_def_id = 'approval_legal_sup'
              AND ni.status IN ('running', 'rejected')
          )
          AND NOT EXISTS (
            SELECT 1 FROM wf_node_instance ni2
            WHERE ni2.process_instance_id = pi.id
              AND ni2.node_def_id = 'approval_legal'
          )
    """), {"tid": tenant_id})).mappings().all()

    if not rows:
        return 0, None

    engine = WorkflowEngine(db, tenant_id)
    fixed = 0
    for r in rows:
        pid = r["pid"]
        inst = await db.get(WfProcessInstance, pid)
        if not inst:
            continue

        await engine._cancel_initiator_revise_todos(pid)

        pending_sup = (await db.execute(select(WfTaskInstance.id).where(
            WfTaskInstance.process_instance_id == pid,
            WfTaskInstance.status.in_(["pending", "waiting"]),
            WfTaskInstance.node_instance_id.in_(
                select(WfNodeInstance.id).where(
                    WfNodeInstance.process_instance_id == pid,
                    WfNodeInstance.node_def_id == "approval_legal_sup",
                )
            ),
        ))).scalars().all()
        if pending_sup:
            await db.execute(text("""
                UPDATE wf_task_instance t
                SET status = 'cancelled', action_at = NOW(), version = version + 1
                FROM wf_node_instance ni
                WHERE t.node_instance_id = ni.id
                  AND ni.process_instance_id = :pid
                  AND ni.node_def_id = 'approval_legal_sup'
                  AND t.status IN ('pending', 'waiting')
            """), {"pid": pid})
            engine._queue("todos_done", [str(x) for x in pending_sup])

        await db.execute(text("""
            UPDATE wf_node_instance
            SET status = 'cancelled', completed_at = NOW(),
                config = COALESCE(config, '{}'::jsonb) || '{"repaired":"rewind_to_legal"}'::jsonb
            WHERE process_instance_id = :pid
              AND node_def_id = 'approval_legal_sup'
              AND status IN ('running', 'rejected')
        """), {"pid": pid})

        if inst.status != "running":
            inst.status = "running"
            inst.completed_at = None
            if inst.biz_id:
                await writeback(db, tenant_id, "contract_review", inst.biz_id, "submitted")

        version = await _published_version(db, tenant_id, inst.process_definition_id)
        if version:
            inst.process_version_id = version.id

        ni = WfNodeInstance(
            id=generate_uuid(), tenant_id=tenant_id, process_instance_id=pid,
            node_def_id="approval_legal", node_type="approval", node_name="法务审批",
            status="running", config={"mode": "or_sign", "repaired": True},
            started_at=_now(),
        )
        db.add(ni)
        await db.flush()
        fresh_tasks: list[str] = []
        for idx, uid in enumerate(legal_uids):
            tid = generate_uuid()
            db.add(WfTaskInstance(
                id=tid, tenant_id=tenant_id, process_instance_id=pid,
                node_instance_id=ni.id, assignee_id=uid, status="pending", task_order=idx,
            ))
            fresh_tasks.append(tid)
        engine._queue("tasks_created", fresh_tasks, inst)
        # 不挂到法务节点、不写处理人，避免流程动态把「系统修复」当成当前审批人
        engine._log(
            pid, None, None, {"sub": "system"}, "repair",
            "空角色法务已跳过，补建法务审批待办（孔雪/张孟杰）并拉回会签主干",
        )
        await db.flush()

        if version:
            ctx = ApprovalContext(
                initiator_id=inst.initiator_id or "",
                form_data=await engine._form_data(inst),
                nominated=dict(inst.nominated_approvers or {}),
            )
            nodes_by = {n.get("id"): n for n in (version.node_definitions or []) if isinstance(n, dict)}
            for nid in ("approval_design", "approval_finance_dir"):
                exists = (await db.execute(select(WfNodeInstance.id).where(
                    WfNodeInstance.process_instance_id == pid,
                    WfNodeInstance.node_def_id == nid,
                ).limit(1))).scalar_one_or_none()
                if exists:
                    continue
                node = nodes_by.get(nid)
                if not node:
                    continue
                approvers = await engine._resolve_approvers(version, node, ctx)
                if not approvers:
                    logger.warning("合同评审补激活跳过 %s：无审批人 process=%s", nid, pid)
                    continue
                await engine._activate_node(inst, version, node, ctx)
        fixed += 1
        logger.info("合同评审补建法务审批 process=%s", pid)
    return fixed, engine


async def _finish_contract_review_runtime_fix(db, tenant_id: str) -> None:
    """升级定义后：改派在途法务主管 + 跳过法务拉回 + 财务总监去掉李晋待办。"""
    n_repair, eng = await _repair_contract_review_skipped_legal(db, tenant_id)
    n_reassign = await _reassign_pending_legal_sup_tasks(db, tenant_id)
    n_fin, eng2 = await _repair_contract_review_finance_dir_drop_lijin(db, tenant_id)
    eng = eng or eng2
    if n_repair or n_reassign or n_fin:
        await db.commit()
        if eng:
            await eng.flush_notifications(wait=True)


async def _repair_contract_review_finance_dir_drop_lijin(
    db, tenant_id: str,
) -> tuple[int, "WorkflowEngine | None"]:
    """在途「财务总监意见」：取消非张光待办；张光已通过则完成节点并推进。"""
    from app.domains.auth.models import User
    from app.domains.lowcode.approver_resolver import ApprovalContext

    want = _JDY_REVIEW_USER["finance_dir"]
    want_username = want[0] if isinstance(want, list) else want
    zhang = (await db.execute(
        select(User.id).where(User.tenant_id == tenant_id, User.username == want_username)
    )).scalar_one_or_none()
    if not zhang:
        logger.warning("合同评审财务总监修复跳过：未找到用户 %s", want_username)
        return 0, None

    rows = (await db.execute(text("""
        SELECT ni.id AS ni_id, ni.process_instance_id AS pid
        FROM wf_node_instance ni
        JOIN wf_process_instance pi ON pi.id = ni.process_instance_id
        WHERE pi.tenant_id = :tid
          AND pi.biz_type = 'contract_review'
          AND pi.status = 'running'
          AND ni.node_def_id = 'approval_finance_dir'
          AND ni.status = 'running'
    """), {"tid": tenant_id})).mappings().all()
    if not rows:
        return 0, None

    engine = WorkflowEngine(db, tenant_id)
    fixed = 0
    for r in rows:
        ni = await db.get(WfNodeInstance, r["ni_id"])
        inst = await db.get(WfProcessInstance, r["pid"])
        if not ni or not inst:
            continue
        tasks = (await db.execute(
            select(WfTaskInstance).where(WfTaskInstance.node_instance_id == ni.id)
        )).scalars().all()
        cancelled_ids: list[str] = []
        for t in tasks:
            if t.status in ("pending", "waiting") and t.assignee_id != zhang:
                t.status = "cancelled"
                cancelled_ids.append(t.id)
        if cancelled_ids:
            engine._queue("todos_done", cancelled_ids)

        cfg = dict(ni.config or {})
        if cfg.get("mode") in ("and_sign", "countersign"):
            cfg["mode"] = "or_sign"
            ni.config = cfg
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(ni, "config")

        tasks = (await db.execute(
            select(WfTaskInstance).where(WfTaskInstance.node_instance_id == ni.id)
        )).scalars().all()
        has_pending = any(t.status in ("pending", "waiting") for t in tasks)
        has_approved = any(
            t.status == "approved" and t.assignee_id == zhang for t in tasks
        )
        # 张光已通过且无其它待办 → 完成节点并推进（等同或签完成）
        if has_approved and not has_pending and ni.status == "running":
            version = await _published_version(db, tenant_id, inst.process_definition_id)
            if not version:
                continue
            ni.status = "completed"
            ni.completed_at = _now()
            await db.flush()
            form_data = await engine._form_data(inst)
            if not form_data and inst.biz_type == "contract_review" and inst.biz_id:
                from app.domains.contract_review.models import ContractReview
                cr = await db.get(ContractReview, inst.biz_id)
                if cr:
                    form_data = {
                        "review_type": cr.review_type,
                        "is_export": cr.is_export,
                        "department_name": cr.department_name,
                        "region_manager_id": cr.region_manager_id,
                        "need_install": cr.need_install,
                    }
            ctx = ApprovalContext(
                initiator_id=inst.initiator_id or "",
                form_data=form_data or {},
                nominated=dict(inst.nominated_approvers or {}),
            )
            await engine._advance(inst, version, ni.node_def_id, ctx)
            fixed += 1
            logger.info("合同评审财务总监去李晋并推进 process=%s", inst.id)
        elif cancelled_ids:
            fixed += 1
            logger.info("合同评审财务总监取消非张光待办 process=%s n=%s", inst.id, len(cancelled_ids))
    return fixed, engine if fixed else None


def _form_need_purchase_yes(data: dict | None) -> bool:
    raw = (data or {}).get("need_purchase")
    vals = raw if isinstance(raw, list) else [raw]
    return any(str(v).strip() == "是" for v in vals if v is not None)


async def _repair_quote_skipped_purchase(
    db, tenant_id: str,
) -> tuple[int, "WorkflowEngine | None"]:
    """财务核价已选转采购，但互斥组吞掉采购节点：补建采购待办。"""
    from app.domains.lowcode.approver_resolver import ApprovalContext
    from app.domains.lowcode.models import FormInstance

    rows = (await db.execute(text("""
        SELECT pi.id AS pid
        FROM wf_process_instance pi
        JOIN wf_process_definition d ON d.id = pi.process_definition_id
        WHERE pi.tenant_id = :tid
          AND d.code = 'SYS_QUOTE_MANAGEMENT'
          AND pi.status IN ('running', 'completed')
          AND pi.form_instance_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM wf_node_instance ni
            WHERE ni.process_instance_id = pi.id
              AND ni.node_name = '采购'
          )
          AND EXISTS (
            SELECT 1 FROM wf_node_instance ni2
            WHERE ni2.process_instance_id = pi.id
              AND ni2.node_name = '财务核价'
              AND ni2.status = 'completed'
          )
    """), {"tid": tenant_id})).mappings().all()
    if not rows:
        return 0, None

    engine = WorkflowEngine(db, tenant_id)
    fixed = 0
    for r in rows:
        pid = r["pid"]
        inst = await db.get(WfProcessInstance, pid)
        if not inst or not inst.form_instance_id:
            continue
        fi = await db.get(FormInstance, inst.form_instance_id)
        if not fi or not _form_need_purchase_yes(fi.form_data):
            continue
        purchaser = (fi.form_data or {}).get("purchaser")
        if purchaser in (None, "", [], {}):
            continue

        version = await _published_version(db, tenant_id, inst.process_definition_id)
        if not version:
            continue
        purchase = next(
            (
                n for n in (version.node_definitions or [])
                if isinstance(n, dict) and n.get("name") == "采购"
            ),
            None,
        )
        if not purchase:
            continue

        inst.process_version_id = version.id
        if inst.status != "running":
            inst.status = "running"
            inst.completed_at = None
        fi.status = "running"
        await db.flush()

        ctx = ApprovalContext(
            initiator_id=inst.initiator_id or "",
            form_data=dict(fi.form_data or {}),
            nominated=dict(inst.nominated_approvers or {}) or {},
        )
        await engine._activate_approval(inst, version, purchase, ctx)
        engine._log(
            inst.id, None, None, {"sub": "system"}, "repair",
            "补建采购询价（财务核价已选择转采购）",
        )
        fixed += 1
        logger.info("报价补建采购询价 process=%s serial=%s", pid, fi.business_no)
    return fixed, engine if fixed else None


async def _finish_quote_purchase_runtime_fix(db, tenant_id: str) -> None:
    """升级定义后：给已跳过采购节点的报价补建待办。"""
    n_repair, eng = await _repair_quote_skipped_purchase(db, tenant_id)
    if n_repair:
        await db.commit()
        if eng:
            await eng.flush_notifications(wait=True)


async def _upgrade_contract_review_jdy_if_needed(
    db, tenant_id: str, d: WfProcessDefinition,
) -> None:
    """系统兜底合同评审流：单节点等升级为简道云会签主干；已对齐拓扑则补风险字段权限/法务主管。"""
    if d.category and d.category != SYSTEM_DEFAULT_CATEGORY:
        return
    if d.biz_type != "contract_review":
        return
    version = await _published_version(db, tenant_id, d.id)
    if not version:
        return
    new_nodes, new_routes = _contract_review_flow_graph()
    _, local_legal_sup = await _resolve_legal_sup_user(db, tenant_id)
    legal_sup_want = local_legal_sup or (
        _JDY_REVIEW_USER["legal_sup"][0]
        if isinstance(_JDY_REVIEW_USER["legal_sup"], list)
        else _JDY_REVIEW_USER["legal_sup"]
    )
    if not _flow_is_jdy_contract_review(version.node_definitions, version.route_definitions):
        # 全量拓扑替换前，把法务主管改成租户可解析的 username
        import copy
        new_nodes = copy.deepcopy(new_nodes)
        for n in new_nodes:
            if isinstance(n, dict) and n.get("id") == "approval_legal_sup":
                rule = dict(n.get("approver_rule") or {})
                rule["value"] = legal_sup_want
                n["approver_rule"] = rule
        await _publish_system_default_upgrade(
            db, tenant_id, d, version, new_nodes, new_routes,
            CONTRACT_REVIEW_DEFAULT_DESC, "简道云评审会签流(旁路抄送/反馈回路)",
        )
        await _finish_contract_review_runtime_fix(db, tenant_id)
        return

    need_fp = not _contract_review_risk_perms_aligned(version.node_definitions)
    need_legal_sup = not _contract_review_legal_sup_user_aligned(
        version.node_definitions, legal_sup_want,
    )
    need_legal = not _contract_review_legal_users_aligned(version.node_definitions)
    need_fin_dir = not _contract_review_finance_dir_aligned(version.node_definitions)
    need_fb_reenter = not _contract_review_feedback_reenter_aligned(
        version.route_definitions,
    )
    if (
        not need_fp and not need_legal_sup and not need_legal
        and not need_fin_dir and not need_fb_reenter
    ):
        await _finish_contract_review_runtime_fix(db, tenant_id)
        return

    import copy
    want_by_id = {
        n.get("id"): n
        for n in new_nodes
        if isinstance(n, dict) and n.get("id") and n.get("type") == "approval"
    }
    patched = copy.deepcopy(version.node_definitions or [])
    patched_routes = copy.deepcopy(version.route_definitions or [])
    changed = False
    tags: list[str] = []
    if need_fb_reenter and apply_contract_review_feedback_reenter(patched_routes):
        changed = True
        tags.append("反馈回路reenter")
    for n in patched:
        if not isinstance(n, dict) or n.get("type") != "approval":
            continue
        nid = n.get("id")
        want_node = want_by_id.get(nid)
        if not want_node:
            continue
        if need_fp:
            cur = list(n.get("field_perms") or [])
            want = list(want_node.get("field_perms") or [])
            if _flow_field_perms_sig([{"id": nid, "type": "approval", "field_perms": cur}]) != \
                    _flow_field_perms_sig([{"id": nid, "type": "approval", "field_perms": want}]):
                if want:
                    n["field_perms"] = want
                elif "field_perms" in n:
                    del n["field_perms"]
                changed = True
        if need_legal_sup and nid == "approval_legal_sup":
            want_rule = copy.deepcopy(want_node.get("approver_rule") or {})
            want_rule["value"] = legal_sup_want
            if n.get("approver_rule") != want_rule:
                n["approver_rule"] = want_rule
                changed = True
        if need_legal and nid == "approval_legal":
            want_rule = copy.deepcopy(want_node.get("approver_rule") or {})
            if n.get("approver_rule") != want_rule:
                n["approver_rule"] = want_rule
                n.setdefault("multi_mode", want_node.get("multi_mode") or "or_sign")
                changed = True
        if need_fin_dir and nid == "approval_finance_dir":
            want_rule = copy.deepcopy(want_node.get("approver_rule") or {})
            want_mode = want_node.get("multi_mode") or "or_sign"
            if n.get("approver_rule") != want_rule or (n.get("multi_mode") or "or_sign") != want_mode:
                n["approver_rule"] = want_rule
                n["multi_mode"] = want_mode
                changed = True
    if need_fp and changed:
        tags.append("风险字段审批可写")
    if need_legal_sup and changed:
        tags.append("法务主管→袁文俊")
    if need_legal and changed:
        tags.append("法务审批→具名")
    if need_fin_dir and changed:
        tags.append("财务总监→仅张光")
    if changed:
        await _publish_system_default_upgrade(
            db, tenant_id, d, version, patched, patched_routes,
            CONTRACT_REVIEW_DEFAULT_DESC,
            "合同评审" + "+".join(tags) if tags else "合同评审局部对齐",
        )
    await _finish_contract_review_runtime_fix(db, tenant_id)


def _flow_is_tech_agreement_jdy(nodes: list | None) -> bool:
    """是否已是当前技术协议系统默认拓扑（无市场支持中心；含业务反馈 / 1.1·2.1）。"""
    names = {
        n.get("name") for n in (nodes or [])
        if isinstance(n, dict) and n.get("type") in ("approval", "cc")
    }
    # 仍含「市场支持中心」→ 需升级移除
    if "市场支持中心" in names:
        return False
    required = {
        "抄送业务员", "部门审批", "总工审批",
        "设计审批1", "设计审批2", "业务反馈",
        "设计审批1.1", "设计审批2.1", "审批反馈", "抄送相关人",
    }
    if not required.issubset(names):
        return False
    # 旧精简版也有总工+设计审批字段权限，必须靠节点名区分
    for n in nodes or []:
        if not isinstance(n, dict) or n.get("type") != "approval":
            continue
        if n.get("name") != "总工审批":
            continue
        for p in n.get("field_perms") or []:
            if isinstance(p, dict) and p.get("field") == "design_approver_ids":
                return True
    return False


async def _upgrade_tech_agreement_jdy_if_needed(
    db, tenant_id: str, d: WfProcessDefinition,
) -> None:
    """系统兜底技术协议流：精简版/含市场支持中心 → 当前默认拓扑。"""
    if d.category and d.category != SYSTEM_DEFAULT_CATEGORY:
        return
    if d.biz_type != "tech_agreement_review":
        return
    version = await _published_version(db, tenant_id, d.id)
    if not version:
        return
    if _flow_is_tech_agreement_jdy(version.node_definitions):
        return
    new_nodes, new_routes = _tech_agreement_flow_graph()
    await _publish_system_default_upgrade(
        db, tenant_id, d, version, new_nodes, new_routes,
        TECH_AGREEMENT_DEFAULT_DESC, "技术协议评审去掉市场支持中心",
    )


async def _upgrade_default_owner_cc_if_needed(
    db, tenant_id: str, d: WfProcessDefinition, name: str,
    approver_rule: dict, multi_mode: str, empty_strategy: str,
) -> None:
    """系统兜底线索流补齐「审批通过 → 抄送负责人」。

    - 仍是 start→审批→结束：发布含抄送节点的新版本
    - 已有唯一抄送但指向发起人(creator)等占位规则：改为表单人员字段 reporter_id（申报人）
    - 租户已自配其它抄送/复杂拓扑：不改动
    """
    if d.category and d.category != SYSTEM_DEFAULT_CATEGORY:
        return
    version = await _published_version(db, tenant_id, d.id)
    if not version:
        return
    if _flow_has_owner_cc(version.node_definitions):
        return

    nodes = list(version.node_definitions or [])
    routes = list(version.route_definitions or [])
    types = {n.get("type") for n in nodes}
    approvals = [n for n in nodes if n.get("type") == "approval"]
    ccs = [n for n in nodes if n.get("type") == "cc"]

    new_nodes: list[dict] | None = None
    new_routes: list[dict] | None = None

    if types <= {"start", "approval", "end"} and len(approvals) == 1:
        new_nodes, new_routes = _default_flow_graph(
            name, approver_rule, multi_mode, empty_strategy, with_owner_cc=True,
        )
        old_ap = approvals[0]
        for n in new_nodes:
            if n.get("id") == "approval_1":
                for k in ("approver_rule", "multi_mode", "empty_strategy", "name", "timeout"):
                    if old_ap.get(k) is not None:
                        n[k] = old_ap[k]
                break
    elif types <= {"start", "approval", "end", "cc"} and len(approvals) == 1 and len(ccs) == 1:
        cc = ccs[0]
        rule = dict(cc.get("approver_rule") or (cc.get("config") or {}).get("approver_rule") or {})
        # 仅纠正明显是占位/误配的抄送（发起人、空指定人），不动指定角色/指定人员等明确配置
        if rule.get("type") not in (None, "", "creator"):
            if not (rule.get("type") == "specified_user" and not rule.get("value")):
                return
        new_nodes = []
        for n in nodes:
            if n.get("id") == cc.get("id"):
                nn = dict(n)
                if not nn.get("name") or nn.get("name") in (
                    "抄送", "CC", "通知业务员确认转化",
                ):
                    nn["name"] = "业务员确认是否转商机"
                nn["approver_rule"] = {"type": "form_field_person", "value": "reporter_id"}
                new_nodes.append(nn)
            else:
                new_nodes.append(n)
        new_routes = routes
    else:
        return

    next_ver = (version.version_number or 0) + 1
    nv = WfProcessDefinitionVersion(
        id=generate_uuid(), tenant_id=tenant_id, process_definition_id=d.id,
        version_number=next_ver, node_definitions=new_nodes, route_definitions=new_routes,
        approver_rules=[], status="published", published_at=_now(),
    )
    db.add(nv)
    version.status = "deprecated"
    d.current_version = next_ver
    d.status = "published"
    d.is_deleted = False
    await db.commit()
    logger.info(
        "已升级系统兜底流程 %s(tenant=%s) → v%s：审批通过后抄送负责人",
        d.code, tenant_id, next_ver,
    )


async def _upgrade_lead_owner_confirm_to_approval_if_needed(
    db, tenant_id: str, d: WfProcessDefinition,
) -> None:
    """把线索流里「业务员确认是否转商机」从抄送升级为审批节点。

    仅改系统兜底简单拓扑；已是审批则跳过。
    """
    if d.category and d.category != SYSTEM_DEFAULT_CATEGORY:
        return
    if d.code != "SYS_LEAD_REVIEW":
        return
    version = await _published_version(db, tenant_id, d.id)
    if not version:
        return
    if _flow_owner_confirm_is_approval(version.node_definitions):
        return

    nodes = list(version.node_definitions or [])
    routes = list(version.route_definitions or [])
    types = {n.get("type") for n in nodes}
    approvals = [n for n in nodes if n.get("type") == "approval"]
    ccs = [n for n in nodes if n.get("type") == "cc"]

    # 仅处理：唯一情报审批 + 一条负责人抄送（或尚无第二节点）
    if not (types <= {"start", "approval", "end", "cc"} and len(approvals) == 1):
        return
    if len(ccs) > 1:
        return

    confirm = _lead_owner_confirm_node()
    if len(ccs) == 1:
        cc = ccs[0]
        rule = dict(cc.get("approver_rule") or (cc.get("config") or {}).get("approver_rule") or {})
        name = (cc.get("name") or "").strip()
        is_ownerish = (
            cc.get("id") in _LEAD_OWNER_CONFIRM_LEGACY_IDS
            or name in (_LEAD_JDY_CC, *_LEAD_LEGACY_CC)
            or (rule.get("type") == "form_field_person" and rule.get("value") in (None, "", "owner_id", "reporter_id"))
            or rule.get("type") in (None, "", "creator")
        )
        if not is_ownerish:
            return
        old_id = cc.get("id")
        new_nodes = []
        for n in nodes:
            if n.get("id") == old_id:
                new_nodes.append(confirm)
            else:
                new_nodes.append(n)
        new_routes = []
        for r in routes:
            rr = dict(r)
            if rr.get("source") == old_id:
                rr["source"] = confirm["id"]
            if rr.get("target") == old_id:
                rr["target"] = confirm["id"]
            new_routes.append(rr)
    elif len(ccs) == 0 and types <= {"start", "approval", "end"}:
        # 无确认节点：整图换成带审批确认的默认图，保留情报节点配置
        name = approvals[0].get("name") or _LEAD_JDY_APPROVAL
        rule = approvals[0].get("approver_rule") or _lead_intel_approver_rule()
        mode = approvals[0].get("multi_mode") or "or_sign"
        empty = approvals[0].get("empty_strategy") or "auto_approve"
        new_nodes, new_routes = _default_flow_graph(
            name, rule, mode, empty, with_owner_cc=True,
        )
        old_ap = approvals[0]
        for n in new_nodes:
            if n.get("id") == "approval_1" or (
                n.get("type") == "approval" and n.get("id") != confirm["id"]
            ):
                for k in ("approver_rule", "multi_mode", "empty_strategy", "timeout", "field_perms", "name"):
                    if old_ap.get(k) is not None:
                        n[k] = old_ap[k]
                break
    else:
        return

    await _publish_system_default_upgrade(
        db, tenant_id, d, version, new_nodes, new_routes,
        "系统默认流程（业务员确认是否转商机：抄送→审批）",
        "线索业务员确认改审批",
    )


async def _upgrade_lead_owner_confirm_if_missing(
    db, tenant_id: str, d: WfProcessDefinition,
) -> None:
    """租户自建/系统 lead 流：唯一情报审后直接结束 → 插入「业务员确认是否转商机」。

    对齐简道云：情报收录后由申报人（业务员）确认是否转商机，而非流程直接结束。
    """
    if d.biz_type != "lead":
        return
    version = await _published_version(db, tenant_id, d.id)
    if not version:
        return
    nodes = list(version.node_definitions or [])
    routes = list(version.route_definitions or [])
    if _flow_has_owner_cc(nodes):
        return
    intel_nodes = [
        n for n in nodes
        if isinstance(n, dict) and n.get("type") == "approval" and not _is_lead_owner_confirm_node_dict(n)
    ]
    if len(intel_nodes) != 1:
        return
    intel_id = intel_nodes[0].get("id")
    if not intel_id:
        return
    confirm = _lead_owner_confirm_node()
    new_nodes = [n for n in nodes if n.get("id") != confirm["id"]]
    new_nodes.append(confirm)
    new_routes: list[dict] = []
    patched = False
    for r in routes:
        rr = dict(r)
        if rr.get("source") == intel_id and rr.get("target") == "end":
            rr["target"] = confirm["id"]
            patched = True
        new_routes.append(rr)
    if not patched:
        return
    new_routes.append({
        "id": f"r_{confirm['id']}_end",
        "source": confirm["id"],
        "target": "end",
    })
    desc = (d.description or "").strip()
    if "转商机" not in desc:
        desc = (desc + "；" if desc else "") + "情报审后业务员确认是否转商机"
    await _publish_system_default_upgrade(
        db, tenant_id, d, version, new_nodes, new_routes,
        desc,
        "线索流补齐业务员确认转商机节点",
    )


async def _upgrade_lead_confirm_reporter_if_needed(
    db, tenant_id: str, d: WfProcessDefinition,
) -> None:
    """业务员确认节点审批人：负责人 owner_id → 申报人 reporter_id。

    业务含义：申报人是业务员，由其确认是否转商机；填表人/负责人不一定是业务员。
    例外：申报人在跳过名单（如张贺）时，引擎激活节点会改派填表人 created_by_id。
    """
    if d.category and d.category != SYSTEM_DEFAULT_CATEGORY:
        return
    if d.code != "SYS_LEAD_REVIEW":
        return
    version = await _published_version(db, tenant_id, d.id)
    if not version:
        return
    if _flow_confirm_uses_reporter(version.node_definitions):
        return

    nodes = list(version.node_definitions or [])
    changed = False
    new_nodes: list[dict] = []
    for n in nodes:
        nn = dict(n)
        nid = nn.get("id")
        name = (nn.get("name") or "").strip()
        rule = dict(nn.get("approver_rule") or (nn.get("config") or {}).get("approver_rule") or {})
        is_confirm = (
            nid in _LEAD_OWNER_CONFIRM_LEGACY_IDS
            or name in (_LEAD_JDY_CC, "通知业务员确认转化")
            or (
                nn.get("type") in ("approval", "cc")
                and _is_lead_confirm_person_rule(rule)
                and ("转商机" in name or "确认转化" in name)
            )
        )
        if is_confirm and rule.get("type") == "form_field_person" and rule.get("value") != "reporter_id":
            nn["approver_rule"] = {**rule, "type": "form_field_person", "value": "reporter_id"}
            changed = True
        elif is_confirm and rule.get("type") in (None, "", "creator"):
            nn["approver_rule"] = {"type": "form_field_person", "value": "reporter_id"}
            changed = True
        new_nodes.append(nn)

    if not changed:
        return

    await _publish_system_default_upgrade(
        db, tenant_id, d, version, new_nodes, list(version.route_definitions or []),
        "系统默认流程（业务员确认：审批人=申报人）",
        "线索业务员确认绑申报人",
    )


# 简道云「申报信息」对齐文案（常量已上移至 _default_flow_graph 旁）


async def _upgrade_lead_jdy_labels_if_needed(
    db, tenant_id: str, d: WfProcessDefinition, name: str,
    approver_rule: dict, multi_mode: str, empty_strategy: str,
) -> None:
    """系统兜底线索流节点文案对齐简道云「申报信息」。

    仅处理简单拓扑（唯一审批 + 可选一条 owner 抄送）；租户自配复杂流不改。
    """
    if d.category and d.category != SYSTEM_DEFAULT_CATEGORY:
        return
    if d.code != "SYS_LEAD_REVIEW":
        return
    version = await _published_version(db, tenant_id, d.id)
    if not version:
        return

    nodes = list(version.node_definitions or [])
    routes = list(version.route_definitions or [])
    types = {n.get("type") for n in nodes}
    approvals = [n for n in nodes if n.get("type") == "approval"]
    ccs = [n for n in nodes if n.get("type") == "cc"]

    if not (types <= {"start", "approval", "end", "cc"} and len(approvals) == 1):
        return
    if len(ccs) > 1:
        return
    if len(ccs) == 1:
        cc = ccs[0]
        rule = dict(cc.get("approver_rule") or (cc.get("config") or {}).get("approver_rule") or {})
        # 非申报人/负责人字段抄送则视为租户定制，不改文案以免误导
        if rule.get("type") == "form_field_person" and rule.get("value") not in (
            None, "", "owner_id", "reporter_id",
        ):
            return
        if rule.get("type") not in (None, "", "creator", "form_field_person"):
            if not (rule.get("type") == "specified_user" and not rule.get("value")):
                return

    target_approval_name = name or _LEAD_JDY_APPROVAL
    changed = False
    new_nodes: list[dict] = []
    for n in nodes:
        nn = dict(n)
        ntype = nn.get("type")
        cur = (nn.get("name") or "").strip()
        if ntype == "start" and cur in _LEAD_LEGACY_START:
            nn["name"] = _LEAD_JDY_START
            changed = True
        elif ntype == "end" and cur in _LEAD_LEGACY_END:
            nn["name"] = _LEAD_JDY_END
            changed = True
        elif ntype == "approval" and (
            cur in _LEAD_LEGACY_APPROVAL or cur != target_approval_name
        ):
            # 仅当仍是旧系统名或与目标不一致时改；租户若改成其它自定义名则保留
            if cur in _LEAD_LEGACY_APPROVAL or cur in ("", "审批节点"):
                nn["name"] = target_approval_name
                changed = True
        elif ntype == "cc" and (cur in _LEAD_LEGACY_CC or not cur):
            nn["name"] = _LEAD_JDY_CC
            nn["approver_rule"] = {"type": "form_field_person", "value": "reporter_id"}
            changed = True
        new_nodes.append(nn)

    # 定义显示名
    if (d.name or "") in _LEAD_LEGACY_APPROVAL or d.name in ("线索审核",):
        d.name = target_approval_name
        changed = True

    if not changed:
        return

    # 若尚无 owner 抄送且拓扑仍是 start→审批→结束，一并补上（与 owner_cc 升级互补）
    if len(ccs) == 0 and types <= {"start", "approval", "end"}:
        new_nodes, routes = _default_flow_graph(
            target_approval_name, approver_rule, multi_mode, empty_strategy, with_owner_cc=True,
        )
        old_ap = approvals[0]
        for n in new_nodes:
            if n.get("id") == "approval_1" or n.get("type") == "approval":
                for k in ("approver_rule", "multi_mode", "empty_strategy", "timeout"):
                    if old_ap.get(k) is not None:
                        n[k] = old_ap[k]
                n["name"] = target_approval_name
                break

    await _publish_system_default_upgrade(
        db, tenant_id, d, version, new_nodes, routes,
        "系统默认流程（对齐简道云「申报信息」：递呈信息→信息情报部审批→业务员确认是否转商机）",
        "简道云申报信息(线索文案)",
    )


async def _revive_default_definition(
    db, tenant_id: str, d: WfProcessDefinition, nodes: list, routes: list,
) -> WfProcessDefinition:
    """把被软删/取消发布的系统兜底流程恢复为可用状态，必要时补一个已发布版本。"""
    logger.warning(
        "系统兜底流程 %s(biz_type=%s, tenant=%s) 处于不可用状态(is_deleted=%s, status=%s)，"
        "已自动恢复并重新发布，以免该业务的审核被静默跳过。",
        d.code, d.biz_type, tenant_id, d.is_deleted, d.status,
    )
    d.is_deleted = False
    d.status = "published"
    version = await _published_version(db, tenant_id, d.id)
    if version is None:
        latest = await _latest_version(db, tenant_id, d.id)
        version = WfProcessDefinitionVersion(
            id=generate_uuid(), tenant_id=tenant_id, process_definition_id=d.id,
            version_number=(latest.version_number + 1) if latest else 1,
            node_definitions=nodes, route_definitions=routes,
            approver_rules=[], status="published", published_at=_now(),
        )
        db.add(version)
    d.current_version = version.version_number
    await db.commit()
    return d


async def start_for_biz(
    db, tenant_id, biz_type, biz_id, user, title=None, form_data=None,
    entry_node_id: str | None = None,
) -> WfProcessInstance | None:
    """既有业务单据(报价/合同/订单/线索...)提交审批: 若该 biz_type 绑定了已发布流程,
    起新引擎流程并承载 (biz_type, biz_id);完成/驳回后由引擎回写业务表状态(wf_biz_writeback)。
    与旧 approval 引擎并存,按 biz_type 灰度切换。未绑定流程则返回 None(走原有逻辑)。"""
    # 同一 biz_type 可能同时存在租户自建流程与系统兜底流程；按 sort_order/created_at
    # 排序保证命中是确定的，且租户自建(sort_order=0)优先于系统兜底(sort_order=9999)。
    d = (await db.execute(select(WfProcessDefinition).where(
        WfProcessDefinition.tenant_id == tenant_id,
        WfProcessDefinition.biz_type == biz_type,
        WfProcessDefinition.status == "published",
        WfProcessDefinition.is_deleted == False,  # noqa: E712
    ).order_by(
        WfProcessDefinition.sort_order.asc(), WfProcessDefinition.created_at.asc()
    ).limit(1))).scalar_one_or_none()
    if not d:
        return None
    # 防重: 同一业务单据已有进行中的流程时不再重复发起(对齐旧引擎 submit_approval 的
    # 「该对象已有进行中的审批流」保护),避免重复提交产生并发重复审批。返回已存在实例。
    existing = (await db.execute(select(WfProcessInstance).where(
        WfProcessInstance.tenant_id == tenant_id,
        WfProcessInstance.biz_type == biz_type,
        WfProcessInstance.biz_id == biz_id,
        WfProcessInstance.status == "running",
    ).limit(1))).scalar_one_or_none()
    if existing:
        return existing
    version = await _published_version(db, tenant_id, d.id)
    if not version:
        return None
    # 业务流没有表单：载入业务实体字段(金额/优先级/来源...)作为条件上下文，
    # 让连线条件能按业务字段分支(与业务字段目录、旧审批 _build_policy_context 一致)。
    ctx = form_data
    if ctx is None:
        try:
            from app.domains.approval.service import _build_policy_context
            ctx = await _build_policy_context(db, tenant_id, biz_type, biz_id)
        except Exception:
            ctx = {}
    return await WorkflowEngine(db, tenant_id).submit(
        d.id, version, user, biz_type=biz_type, biz_id=biz_id, title=title,
        form_data=ctx or {}, entry_node_id=entry_node_id,
    )


# ==================== 运行时查询 ====================

async def can_access_contract_via_workflow(
    db,
    tenant_id: str,
    user_id: str | None,
    *,
    contract_id: str | None = None,
    version_id: str | None = None,
) -> bool:
    """审批相关人可只读合同登记信息（对齐简道云：有待办即可看单据，不必有 contract:view）。

    覆盖：发起人 / 任务处理人(含已办) / 抄送人 / 当前待办的有效代理人。
    """
    if not user_id or (not contract_id and not version_id):
        return False
    from app.domains.contract.models import ContractVersion

    version_ids: set[str] = set()
    if version_id:
        version_ids.add(version_id)
    if contract_id:
        rows = (await db.execute(
            select(ContractVersion.id).where(
                ContractVersion.tenant_id == tenant_id,
                ContractVersion.contract_id == contract_id,
            )
        )).all()
        version_ids.update(r[0] for r in rows)
    if not version_ids:
        return False

    insts = (await db.execute(
        select(WfProcessInstance).where(
            WfProcessInstance.tenant_id == tenant_id,
            WfProcessInstance.biz_type == "contract_version",
            WfProcessInstance.biz_id.in_(version_ids),
        )
    )).scalars().all()
    return await _user_participates_in_instances(db, tenant_id, user_id, list(insts))


async def _user_participates_in_instances(
    db, tenant_id: str, user_id: str, insts: list,
) -> bool:
    """发起人 / 任务处理人(含已办) / 抄送人 / 当前待办的有效代理人。"""
    if not insts:
        return False
    if any(i.initiator_id == user_id for i in insts):
        return True

    inst_ids = [i.id for i in insts]
    has_task = (await db.execute(
        select(WfTaskInstance.id).where(
            WfTaskInstance.process_instance_id.in_(inst_ids),
            WfTaskInstance.assignee_id == user_id,
        ).limit(1)
    )).scalar_one_or_none()
    if has_task:
        return True

    has_cc = (await db.execute(
        select(WfProcessCc.id).where(
            WfProcessCc.process_instance_id.in_(inst_ids),
            WfProcessCc.user_id == user_id,
        ).limit(1)
    )).scalar_one_or_none()
    if has_cc:
        return True

    from datetime import datetime, timezone
    from app.domains.organization.models import UserAgent
    pending_assignees = list({
        a for a in (await db.execute(
            select(WfTaskInstance.assignee_id).where(
                WfTaskInstance.process_instance_id.in_(inst_ids),
                WfTaskInstance.status == "pending",
            )
        )).scalars().all() if a
    })
    if pending_assignees:
        now = datetime.now(timezone.utc)
        agent_ok = (await db.execute(
            select(UserAgent.id).where(
                UserAgent.tenant_id == tenant_id,
                UserAgent.agent_id == user_id,
                UserAgent.user_id.in_(pending_assignees),
                UserAgent.status == "active",
                UserAgent.start_time <= now,
                UserAgent.end_time >= now,
            ).limit(1)
        )).scalar_one_or_none()
        if agent_ok:
            return True
    return False


async def can_access_biz_via_workflow(
    db,
    tenant_id: str,
    user_id: str | None,
    *,
    biz_type: str | None,
    biz_id: str | None,
) -> bool:
    """审批相关人可只读业务单据附件（有待办即可看，不必有业务 view / attachment:download）。"""
    if not user_id or not biz_type or not biz_id:
        return False
    insts = (await db.execute(
        select(WfProcessInstance).where(
            WfProcessInstance.tenant_id == tenant_id,
            WfProcessInstance.biz_type == biz_type,
            WfProcessInstance.biz_id == biz_id,
        )
    )).scalars().all()
    return await _user_participates_in_instances(db, tenant_id, user_id, list(insts))


async def can_access_form_via_workflow(
    db,
    tenant_id: str,
    user_id: str | None,
    form_instance_id: str | None,
) -> bool:
    """审批相关人可只读表单数据（对齐合同：有待办即可看单据，不必有 form_data:view）。

    覆盖：发起人 / 任务处理人(含已办) / 抄送人 / 当前待办的有效代理人。
    """
    if not user_id or not form_instance_id:
        return False
    insts = (await db.execute(
        select(WfProcessInstance).where(
            WfProcessInstance.tenant_id == tenant_id,
            WfProcessInstance.form_instance_id == form_instance_id,
        )
    )).scalars().all()
    return await _user_participates_in_instances(db, tenant_id, user_id, list(insts))


def _workflow_participated_process_ids_subquery(user_id: str):
    """用户作为发起人/任务处理人/抄送人参与过的流程实例 id（子查询）。"""
    return select(WfProcessInstance.id).where(
        or_(
            WfProcessInstance.initiator_id == user_id,
            WfProcessInstance.id.in_(
                select(WfTaskInstance.process_instance_id).where(
                    WfTaskInstance.assignee_id == user_id,
                )
            ),
            WfProcessInstance.id.in_(
                select(WfProcessCc.process_instance_id).where(
                    WfProcessCc.user_id == user_id,
                )
            ),
        )
    )


def form_instance_workflow_participant_clause(user_id: str, tenant_id: str):
    """关联子句：FormInstance 行因用户参与其流程而可见（用于列表 OR 旁路）。"""
    from sqlalchemy import exists
    from app.domains.lowcode.models import FormInstance

    pi = WfProcessInstance
    fi_match = pi.form_instance_id == FormInstance.id
    base = and_(pi.tenant_id == tenant_id, fi_match)
    return or_(
        exists(select(1).where(base, pi.initiator_id == user_id)),
        exists(
            select(1)
            .select_from(WfTaskInstance)
            .where(
                WfTaskInstance.process_instance_id == pi.id,
                base,
                WfTaskInstance.assignee_id == user_id,
            )
        ),
        exists(
            select(1)
            .select_from(WfProcessCc)
            .where(
                WfProcessCc.process_instance_id == pi.id,
                base,
                WfProcessCc.user_id == user_id,
            )
        ),
    )


async def user_participates_in_form_template_workflow(
    db,
    tenant_id: str,
    user_id: str | None,
    template_id: str,
) -> bool:
    """用户是否在该表单模板任一实例的流程中出现过（发起/待办/已办/抄送）。"""
    if not user_id or not template_id:
        return False
    from app.domains.lowcode.models import FormInstance

    participated = _workflow_participated_process_ids_subquery(user_id)
    hit = (await db.execute(
        select(FormInstance.id).where(
            FormInstance.tenant_id == tenant_id,
            FormInstance.template_id == template_id,
            FormInstance.is_deleted.is_(False),  # noqa: E712
            FormInstance.id.in_(
                select(WfProcessInstance.form_instance_id).where(
                    WfProcessInstance.tenant_id == tenant_id,
                    WfProcessInstance.form_instance_id.isnot(None),
                    WfProcessInstance.id.in_(participated),
                )
            ),
        ).limit(1)
    )).scalar_one_or_none()
    return hit is not None


async def form_template_codes_user_participates(
    db,
    tenant_id: str,
    user_id: str | None,
) -> list[str]:
    """用户参与过流程的表单模板 code 列表（用于侧栏菜单）。"""
    if not user_id:
        return []
    from app.domains.lowcode.models import FormInstance, FormTemplate

    participated = _workflow_participated_process_ids_subquery(user_id)
    form_ids = select(WfProcessInstance.form_instance_id).where(
        WfProcessInstance.tenant_id == tenant_id,
        WfProcessInstance.form_instance_id.isnot(None),
        WfProcessInstance.id.in_(participated),
    )
    codes = list((await db.execute(
        select(FormTemplate.code).distinct()
        .join(FormInstance, FormInstance.template_id == FormTemplate.id)
        .where(
            FormInstance.tenant_id == tenant_id,
            FormInstance.is_deleted.is_(False),  # noqa: E712
            FormInstance.id.in_(form_ids),
        )
    )).scalars().all())
    return codes


def _live_form_process_clause(tenant_id: str):
    """排除关联表单已软删的流程：单据删了，待办/我发起的/抄送不应再出现。"""
    from app.domains.lowcode.models import FormInstance
    deleted_forms = select(FormInstance.id).where(
        FormInstance.tenant_id == tenant_id,
        FormInstance.is_deleted.is_(True),  # noqa: E712
    )
    return or_(
        WfProcessInstance.form_instance_id.is_(None),
        ~WfProcessInstance.form_instance_id.in_(deleted_forms),
    )


async def abort_processes_for_deleted_form(
    db, tenant_id: str, form_instance_id: str, user: dict | None = None,
) -> int:
    """表单已删时作废仍挂着的流程实例。"""
    if not form_instance_id:
        return 0
    rows = (await db.execute(
        select(WfProcessInstance).where(
            WfProcessInstance.tenant_id == tenant_id,
            WfProcessInstance.form_instance_id == form_instance_id,
            WfProcessInstance.status.in_(["running", "draft"]),
        )
    )).scalars().all()
    n = 0
    engine = WorkflowEngine(db, tenant_id)
    for inst in rows:
        if await engine.abort_deleted_form(inst.id, user):
            n += 1
    return n


@dataclass
class WfListFilters:
    """审批中心列表筛选（待办/已办/我发起/抄送）。"""
    keyword: str | None = None
    process_definition_id: str | None = None
    form_code: str | None = None
    node_name: str | None = None
    initiator_id: str | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    # JSON: {match,rules:[{field,op,value}]} — 与表单数据列表 filters 同格式
    form_filters: str | None = None

    def active(self) -> bool:
        return any([
            self.keyword and self.keyword.strip(),
            self.process_definition_id,
            self.form_code,
            self.node_name,
            self.initiator_id,
            self.created_from,
            self.created_to,
            self.form_filters and self.form_filters.strip(),
        ])


async def _form_field_filter_instance_clause(db, tenant_id: str, filters: WfListFilters):
    """表单字段筛选 → form_instance_id 子查询条件。"""
    if not filters.form_filters or not filters.form_filters.strip():
        return None
    from app.domains.lowcode.models import FormInstance
    from app.domains.lowcode.service import (
        _form_data_filter_clause,
        _instance_list_filter_bundle,
        _normalize_instance_filters,
    )
    template_id = None
    if filters.process_definition_id:
        template_id = (await db.execute(
            select(WfProcessDefinition.form_template_id).where(
                WfProcessDefinition.tenant_id == tenant_id,
                WfProcessDefinition.id == filters.process_definition_id,
            )
        )).scalar_one_or_none()
    match, rules = _normalize_instance_filters(filters.form_filters)
    if not rules:
        return None
    fi_conds = [
        FormInstance.tenant_id == tenant_id,
        FormInstance.is_deleted == False,  # noqa: E712
    ]
    if template_id:
        fi_conds.append(FormInstance.template_id == template_id)
        bundle = await _instance_list_filter_bundle(db, tenant_id, template_id, filters.form_filters)
        if bundle:
            fi_conds.append(bundle[0])
    else:
        clauses = [_form_data_filter_clause(r) for r in rules]
        combined = or_(*clauses) if match == "any" else and_(*clauses)
        fi_conds.append(combined)
    fi_sq = select(FormInstance.id).where(*fi_conds)
    return WfProcessInstance.form_instance_id.in_(fi_sq)


def _instance_filter_clauses(tenant_id: str, filters: WfListFilters) -> list:
    clauses = []
    if filters.keyword and filters.keyword.strip():
        kw = f"%{filters.keyword.strip()}%"
        def_sq = select(WfProcessDefinition.id).where(
            WfProcessDefinition.tenant_id == tenant_id,
            WfProcessDefinition.name.ilike(kw),
        )
        from app.domains.lowcode.models import FormInstance
        fi_kw_sq = select(FormInstance.id).where(
            FormInstance.tenant_id == tenant_id,
            FormInstance.is_deleted == False,  # noqa: E712
            cast(FormInstance.form_data, String).ilike(kw),
        )
        clauses.append(or_(
            WfProcessInstance.title.ilike(kw),
            WfProcessInstance.business_no.ilike(kw),
            WfProcessInstance.process_definition_id.in_(def_sq),
            WfProcessInstance.form_instance_id.in_(fi_kw_sq),
        ))
    if filters.process_definition_id:
        clauses.append(WfProcessInstance.process_definition_id == filters.process_definition_id)
    if filters.form_code:
        from app.domains.lowcode.models import FormInstance, FormTemplate
        tpl_sq = select(FormTemplate.id).where(
            FormTemplate.tenant_id == tenant_id,
            FormTemplate.code == filters.form_code,
        )
        fi_sq = select(FormInstance.id).where(
            FormInstance.tenant_id == tenant_id,
            FormInstance.template_id.in_(tpl_sq),
            FormInstance.is_deleted == False,  # noqa: E712
        )
        clauses.append(WfProcessInstance.form_instance_id.in_(fi_sq))
    if filters.initiator_id:
        clauses.append(WfProcessInstance.initiator_id == filters.initiator_id)
    if filters.created_from:
        clauses.append(WfProcessInstance.created_at >= filters.created_from)
    if filters.created_to:
        clauses.append(WfProcessInstance.created_at <= filters.created_to)
    return clauses


async def _live_filtered_instance_subquery(db, tenant_id: str, filters: WfListFilters | None = None):
    q = select(WfProcessInstance.id).where(
        WfProcessInstance.tenant_id == tenant_id,
        _live_form_process_clause(tenant_id),
    )
    if filters and filters.active():
        q = q.where(*_instance_filter_clauses(tenant_id, filters))
        form_clause = await _form_field_filter_instance_clause(db, tenant_id, filters)
        if form_clause is not None:
            q = q.where(form_clause)
    return q


def _running_node_name_instance_subquery(tenant_id: str, node_name: str):
    return select(WfNodeInstance.process_instance_id).where(
        WfNodeInstance.tenant_id == tenant_id,
        WfNodeInstance.status == "running",
        WfNodeInstance.node_type == "approval",
        WfNodeInstance.node_name == node_name,
    )


def _task_node_name_clause(tenant_id: str, node_name: str):
    node_sq = select(WfNodeInstance.id).where(
        WfNodeInstance.tenant_id == tenant_id,
        WfNodeInstance.node_name == node_name,
    )
    return WfTaskInstance.node_instance_id.in_(node_sq)


async def list_filter_options(db, tenant_id: str, process_definition_id: str | None = None) -> dict:
    """审批中心筛选项：已发布流程 + 常见节点名；指定流程时返回可筛字段。"""
    from app.domains.lowcode.models import FormTemplate
    from app.domains.lowcode.service import get_published_version
    def_rows = (await db.execute(
        select(
            WfProcessDefinition.id,
            WfProcessDefinition.name,
            WfProcessDefinition.form_template_id,
        ).where(
            WfProcessDefinition.tenant_id == tenant_id,
            WfProcessDefinition.is_deleted == False,  # noqa: E712
            WfProcessDefinition.status == "published",
        ).order_by(WfProcessDefinition.sort_order, WfProcessDefinition.name)
    )).all()
    tpl_ids = {r[2] for r in def_rows if r[2]}
    tpl_code_map: dict[str, str] = {}
    if tpl_ids:
        tpl_code_map = {
            r[0]: r[1] for r in (await db.execute(
                select(FormTemplate.id, FormTemplate.code).where(FormTemplate.id.in_(tpl_ids))
            )).all()
        }
    processes = [
        {"id": r[0], "name": r[1], "form_code": tpl_code_map.get(r[2])}
        for r in def_rows
    ]
    node_names = list((await db.execute(
        select(WfNodeInstance.node_name).where(
            WfNodeInstance.tenant_id == tenant_id,
            WfNodeInstance.node_name.isnot(None),
            WfNodeInstance.node_name != "",
        ).distinct().order_by(WfNodeInstance.node_name).limit(300)
    )).scalars().all())
    fields: list[dict] = []
    if process_definition_id:
        tpl_id = (await db.execute(
            select(WfProcessDefinition.form_template_id).where(
                WfProcessDefinition.tenant_id == tenant_id,
                WfProcessDefinition.id == process_definition_id,
            )
        )).scalar_one_or_none()
        if tpl_id:
            ver = await get_published_version(db, tenant_id, tpl_id)
            from app.domains.lowcode.service import expand_filterable_form_fields
            fields = expand_filterable_form_fields(
                (ver.field_definitions if ver else []) or [],
            )
    return {"processes": processes, "node_names": node_names, "fields": fields}


async def list_todo(
    db, tenant_id, user_id, page_no, page_size,
    biz_type=None, biz_id=None, filters: WfListFilters | None = None,
):
    """我的待办。biz_type/biz_id 可选，用于业务详情页精确查「这单是否轮到我审」——
    否则调用方只能拉一页待办再在前端过滤，待办多时会漏掉。"""
    # 待办 = 本人被指派 + 本人作为「有效代理人」代办的委托人任务
    principals = await active_principals(db, tenant_id, user_id)
    assignees = [user_id, *principals]
    conds = [WfTaskInstance.tenant_id == tenant_id, WfTaskInstance.assignee_id.in_(assignees),
             WfTaskInstance.status == "pending"]
    inst_q = await _live_filtered_instance_subquery(db, tenant_id, filters)
    if biz_type:
        inst_q = inst_q.where(WfProcessInstance.biz_type == biz_type)
    if biz_id:
        inst_q = inst_q.where(WfProcessInstance.biz_id == biz_id)
    conds.append(WfTaskInstance.process_instance_id.in_(inst_q))
    if filters and filters.node_name:
        conds.append(_task_node_name_clause(tenant_id, filters.node_name))
    total = (await db.execute(select(func.count()).select_from(WfTaskInstance).where(*conds))).scalar_one()
    tasks = (await db.execute(select(WfTaskInstance).where(*conds)
             .order_by(WfTaskInstance.created_at.desc())
             .offset((page_no - 1) * page_size).limit(page_size))).scalars().all()
    return await _enrich_tasks(db, list(tasks), viewer_id=user_id), total


async def list_done(db, tenant_id, user_id, page_no, page_size, filters: WfListFilters | None = None):
    inst_q = await _live_filtered_instance_subquery(db, tenant_id, filters)
    conds = [WfTaskInstance.tenant_id == tenant_id, WfTaskInstance.assignee_id == user_id,
             WfTaskInstance.status.in_(["approved", "rejected", "transferred", "returned"]),
             WfTaskInstance.process_instance_id.in_(inst_q)]
    if filters and filters.node_name:
        conds.append(_task_node_name_clause(tenant_id, filters.node_name))
    total = (await db.execute(select(func.count()).select_from(WfTaskInstance).where(*conds))).scalar_one()
    tasks = (await db.execute(select(WfTaskInstance).where(*conds)
             .order_by(WfTaskInstance.action_at.desc())
             .offset((page_no - 1) * page_size).limit(page_size))).scalars().all()
    return await _enrich_tasks(db, list(tasks)), total


async def list_initiated(db, tenant_id, user_id, page_no, page_size, filters: WfListFilters | None = None):
    conds = [
        WfProcessInstance.tenant_id == tenant_id,
        WfProcessInstance.initiator_id == user_id,
        _live_form_process_clause(tenant_id),
    ]
    if filters and filters.active():
        conds.extend(_instance_filter_clauses(tenant_id, filters))
    if filters and filters.node_name:
        conds.append(WfProcessInstance.id.in_(
            _running_node_name_instance_subquery(tenant_id, filters.node_name)
        ))
    total = (await db.execute(select(func.count()).select_from(WfProcessInstance).where(*conds))).scalar_one()
    rows = (await db.execute(select(WfProcessInstance).where(*conds)
            .order_by(WfProcessInstance.created_at.desc())
            .offset((page_no - 1) * page_size).limit(page_size))).scalars().all()
    return await _enrich_instances(db, list(rows)), total


async def list_cc(db, tenant_id, user_id, page_no, page_size, filters: WfListFilters | None = None):
    """抄送给我的流程。"""
    inst_q = await _live_filtered_instance_subquery(db, tenant_id, filters)
    if filters and filters.node_name:
        inst_q = inst_q.where(
            WfProcessInstance.id.in_(_running_node_name_instance_subquery(tenant_id, filters.node_name))
        )
    conds = [
        WfProcessCc.tenant_id == tenant_id,
        WfProcessCc.user_id == user_id,
        WfProcessCc.process_instance_id.in_(inst_q),
    ]
    total = (await db.execute(select(func.count()).select_from(WfProcessCc).where(*conds))).scalar_one()
    ccs = (await db.execute(select(WfProcessCc).where(*conds)
           .order_by(WfProcessCc.created_at.desc())
           .offset((page_no - 1) * page_size).limit(page_size))).scalars().all()
    if not ccs:
        return [], total
    inst_ids = {c.process_instance_id for c in ccs}
    insts = {
        i.id: i for i in (await db.execute(
            select(WfProcessInstance).where(WfProcessInstance.id.in_(inst_ids))
        )).scalars().all()
    }
    cv_ids = {
        i.biz_id for i in insts.values()
        if i and i.biz_type == "contract_version" and i.biz_id
    }
    cv_map: dict[str, str] = {}
    if cv_ids:
        from app.domains.contract.models import ContractVersion
        cv_map = {
            r[0]: r[1] for r in (await db.execute(
                select(ContractVersion.id, ContractVersion.contract_id).where(ContractVersion.id.in_(cv_ids))
            )).all()
        }
    from app.domains.auth.models import User
    initiator_ids = {i.initiator_id for i in insts.values() if i and i.initiator_id}
    name_map: dict[str, str] = {}
    if initiator_ids:
        name_map = {
            r[0]: (r[1] or r[2]) for r in (await db.execute(
                select(User.id, User.real_name, User.username).where(User.id.in_(initiator_ids))
            )).all()
        }
    def_ids = {i.process_definition_id for i in insts.values() if i and i.process_definition_id}
    def_name_map: dict[str, str] = {}
    if def_ids:
        def_name_map = {
            r[0]: r[1] for r in (await db.execute(
                select(WfProcessDefinition.id, WfProcessDefinition.name).where(
                    WfProcessDefinition.id.in_(def_ids)
                )
            )).all()
        }
    await _heal_weak_form_titles(db, insts, def_name_map)
    out = []
    for c in ccs:
        inst = insts.get(c.process_instance_id)
        biz_ref_id = None
        process_name = None
        if inst:
            process_name = def_name_map.get(inst.process_definition_id)
            if inst.biz_type == "contract_version" and inst.biz_id:
                biz_ref_id = cv_map.get(inst.biz_id)
            elif inst.biz_type == "contract_review":
                biz_ref_id = inst.biz_id
            elif inst.biz_type == "tech_agreement_review":
                biz_ref_id = inst.biz_id
        out.append({
            "cc_id": c.id,
            "is_read": bool(c.is_read),
            "process_instance_id": c.process_instance_id,
            "title": inst.title if inst else None,
            "business_no": inst.business_no if inst else None,
            "status": inst.status if inst else None,
            "biz_type": inst.biz_type if inst else None,
            "biz_id": inst.biz_id if inst else None,
            "biz_ref_id": biz_ref_id,
            "process_name": process_name,
            "initiator_id": inst.initiator_id if inst else None,
            "initiator_name": name_map.get(inst.initiator_id) if inst and inst.initiator_id else None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return out, total


async def _heal_weak_form_titles(
    db,
    instances: list[WfProcessInstance] | dict[str, WfProcessInstance],
    def_name_map: dict[str, str] | None = None,
) -> None:
    """列表页：把仅有「报价管理」等模板名的弱标题按表单字段补成「单号 · 客户 · 业务员」。"""
    from app.domains.lowcode.models import FormInstance, FormTemplate
    from app.domains.lowcode.service import (
        derive_form_instance_title_resolved,
        is_weak_form_title,
    )

    inst_iter = instances.values() if isinstance(instances, dict) else instances
    def_name_map = def_name_map or {}
    candidates: list[WfProcessInstance] = []
    for inst in inst_iter:
        if not inst or not inst.form_instance_id:
            continue
        pname = def_name_map.get(inst.process_definition_id)
        if is_weak_form_title(inst.title, pname):
            candidates.append(inst)
    if not candidates:
        return

    fi_ids = {i.form_instance_id for i in candidates if i.form_instance_id}
    fi_map: dict[str, FormInstance] = {}
    if fi_ids:
        rows = (await db.execute(
            select(FormInstance).where(FormInstance.id.in_(fi_ids))
        )).scalars().all()
        fi_map = {f.id: f for f in rows}

    tpl_ids = {f.template_id for f in fi_map.values() if f.template_id}
    tpl_name_map: dict[str, str] = {}
    if tpl_ids:
        tpl_name_map = {
            r[0]: r[1]
            for r in (await db.execute(
                select(FormTemplate.id, FormTemplate.name).where(FormTemplate.id.in_(tpl_ids))
            )).all()
        }

    dirty = False
    for inst in candidates:
        fi = fi_map.get(inst.form_instance_id or "")
        if not fi:
            continue
        tpl_name = (
            tpl_name_map.get(fi.template_id)
            or def_name_map.get(inst.process_definition_id)
            or "表单申请"
        )
        try:
            healed = await derive_form_instance_title_resolved(
                db,
                inst.tenant_id,
                tpl_name,
                fi.form_data if isinstance(fi.form_data, dict) else {},
                fi.field_definitions,
            )
        except Exception:
            continue
        if not healed or healed == (inst.title or "").strip():
            continue
        inst.title = healed
        if is_weak_form_title(fi.title, tpl_name):
            fi.title = healed
        dirty = True

    if dirty:
        try:
            await db.commit()
        except Exception:
            await db.rollback()


_FORM_WF_ACTIVE_STATUSES = frozenset({"running", "returned", "rejected", "withdrawn"})


async def heal_form_instance_status_from_process(db, tenant_id: str) -> int:
    """重提/激活后表单仍标 submitted 但流程进行中 → 回写 running（及 returned/rejected/withdrawn）。"""
    from app.domains.lowcode.models import FormInstance
    from sqlalchemy import text
    rows = (await db.execute(text("""
        UPDATE lc_form_instance fi
        SET status = src.wf_status,
            process_instance_id = COALESCE(fi.process_instance_id, src.pid)
        FROM (
            SELECT DISTINCT ON (pi.form_instance_id)
                   pi.form_instance_id AS fid,
                   pi.id AS pid,
                   pi.status AS wf_status
            FROM wf_process_instance pi
            WHERE pi.tenant_id = :tid
              AND pi.form_instance_id IS NOT NULL
              AND pi.status IN ('running', 'returned', 'rejected', 'withdrawn')
            ORDER BY pi.form_instance_id,
                     pi.started_at DESC NULLS LAST,
                     pi.created_at DESC
        ) src
        WHERE fi.id = src.fid
          AND fi.tenant_id = :tid
          AND fi.is_deleted = false
          AND fi.status = 'submitted'
          AND (
            fi.process_instance_id IS NULL
            OR fi.process_instance_id = src.pid
          )
        RETURNING fi.id
    """), {"tid": tenant_id})).scalars().all()
    if rows:
        await db.commit()
    return len(rows)


async def current_node_names_for_form_instances(
    db, tenant_id: str, form_instance_ids: list[str],
) -> dict[str, str]:
    """表单列表：form_instance_id → 当前流程节点名（进行中的审批/修订节点）。"""
    if not form_instance_ids:
        return {}
    insts = (await db.execute(
        select(WfProcessInstance).where(
            WfProcessInstance.tenant_id == tenant_id,
            WfProcessInstance.form_instance_id.in_(form_instance_ids),
            WfProcessInstance.status.in_(_FORM_WF_ACTIVE_STATUSES),
        ).order_by(
            WfProcessInstance.started_at.desc().nulls_last(),
            WfProcessInstance.created_at.desc(),
        )
    )).scalars().all()
    pi_by_fi: dict[str, str] = {}
    for inst in insts:
        fid = inst.form_instance_id
        if fid and fid not in pi_by_fi:
            pi_by_fi[fid] = inst.id
    if not pi_by_fi:
        return {}
    pid_names = await _running_node_names_by_process_ids(db, list(pi_by_fi.values()))
    return {
        fid: pid_names[pid]
        for fid, pid in pi_by_fi.items()
        if pid in pid_names
    }


async def _running_node_names_by_process_ids(
    db, process_ids: list[str],
) -> dict[str, str]:
    """process_instance_id → 当前 running 节点名（并行审批用顿号连接）。"""
    if not process_ids:
        return {}
    ni_rows = (await db.execute(
        select(
            WfNodeInstance.process_instance_id,
            WfNodeInstance.node_name,
            WfNodeInstance.node_type,
        ).where(
            WfNodeInstance.process_instance_id.in_(process_ids),
            WfNodeInstance.status == "running",
            WfNodeInstance.node_type.in_(("approval", "revise")),
        ).order_by(WfNodeInstance.started_at.asc().nulls_last())
    )).all()
    from collections import defaultdict
    names_by_pid: dict[str, list[str]] = defaultdict(list)
    revise_by_pid: dict[str, str] = {}
    for pid, name, ntype in ni_rows:
        if ntype == "revise":
            revise_by_pid[pid] = (name or "").strip() or "修改并重新提交"
            continue
        label = (name or "").strip()
        if label and label not in names_by_pid[pid]:
            names_by_pid[pid].append(label)
    out: dict[str, str] = {}
    for pid in process_ids:
        if names_by_pid.get(pid):
            out[pid] = "、".join(names_by_pid[pid])
        elif pid in revise_by_pid:
            out[pid] = revise_by_pid[pid]
    return out


async def _enrich_instances(db, rows: list[WfProcessInstance]) -> list[dict]:
    """列表补充：合同 biz_ref_id、进行中当前节点名、流程定义名（表单流无 biz_type 时作类型兜底）。"""
    if not rows:
        return []
    cv_ids = {i.biz_id for i in rows if i.biz_type == "contract_version" and i.biz_id}
    cv_map: dict[str, str] = {}
    if cv_ids:
        from app.domains.contract.models import ContractVersion
        cv_map = {
            r[0]: r[1] for r in (await db.execute(
                select(ContractVersion.id, ContractVersion.contract_id).where(ContractVersion.id.in_(cv_ids))
            )).all()
        }
    running_ids = [i.id for i in rows if i.status == "running"]
    current_node: dict[str, str] = {}
    if running_ids:
        current_node = await _running_node_names_by_process_ids(db, running_ids)
    def_ids = {i.process_definition_id for i in rows if i.process_definition_id}
    def_name_map: dict[str, str] = {}
    if def_ids:
        def_name_map = {
            r[0]: r[1] for r in (await db.execute(
                select(WfProcessDefinition.id, WfProcessDefinition.name).where(
                    WfProcessDefinition.id.in_(def_ids)
                )
            )).all()
        }
    await _heal_weak_form_titles(db, rows, def_name_map)
    fi_ids = {i.form_instance_id for i in rows if i.form_instance_id}
    form_code_map = await _form_codes_by_instance_ids(db, fi_ids)
    out = []
    for i in rows:
        d = _inst_dict(i, form_code=form_code_map.get(i.form_instance_id or ""))
        if i.biz_type == "contract_version" and i.biz_id:
            d["biz_ref_id"] = cv_map.get(i.biz_id)
        elif i.biz_type == "contract_review":
            d["biz_ref_id"] = i.biz_id
        elif i.biz_type == "tech_agreement_review":
            d["biz_ref_id"] = i.biz_id
        else:
            d["biz_ref_id"] = None
        d["current_node_name"] = current_node.get(i.id)
        d["process_name"] = def_name_map.get(i.process_definition_id)
        out.append(d)
    return out


async def _enrich_tasks(db, tasks: list[WfTaskInstance], viewer_id: str | None = None) -> list[dict]:
    # 若含代办任务，批量解析委托人姓名用于「代 XX 审批」标注
    principal_ids = {t.assignee_id for t in tasks if viewer_id and t.assignee_id != viewer_id}
    inst_ids = {t.process_instance_id for t in tasks if t.process_instance_id}
    insts: dict[str, WfProcessInstance] = {}
    if inst_ids:
        rows = (await db.execute(
            select(WfProcessInstance).where(WfProcessInstance.id.in_(inst_ids))
        )).scalars().all()
        insts = {i.id: i for i in rows}
    # 发起人姓名: 列表要显示「XX 发起」，与待办的代理人姓名一起批量解析，避免逐条查询
    wanted = set(principal_ids) | {i.initiator_id for i in insts.values() if i and i.initiator_id}
    name_map: dict[str, str] = {}
    if wanted:
        from app.domains.auth.models import User
        rows = (await db.execute(select(User.id, User.real_name, User.username)
                .where(User.id.in_(wanted)))).all()
        name_map = {r[0]: (r[1] or r[2]) for r in rows}
    # 合同版本审批：biz_id 是 version_id，列表「查看单据」需要 contract_id
    cv_ids = {
        i.biz_id for i in insts.values()
        if i and i.biz_type == "contract_version" and i.biz_id
    }
    cv_contract_map: dict[str, str] = {}
    if cv_ids:
        from app.domains.contract.models import ContractVersion
        cv_rows = (await db.execute(
            select(ContractVersion.id, ContractVersion.contract_id).where(ContractVersion.id.in_(cv_ids))
        )).all()
        cv_contract_map = {r[0]: r[1] for r in cv_rows}
    # 节点名：列表展示「待审：财务审核」
    node_ids = {t.node_instance_id for t in tasks if t.node_instance_id}
    node_name_map: dict[str, str] = {}
    node_type_map: dict[str, str] = {}
    if node_ids:
        ni_rows = (await db.execute(
            select(WfNodeInstance.id, WfNodeInstance.node_name, WfNodeInstance.node_type).where(
                WfNodeInstance.id.in_(node_ids)
            )
        )).all()
        node_name_map = {r[0]: (r[1] or "审批") for r in ni_rows}
        node_type_map = {r[0]: (r[2] or "") for r in ni_rows}

    # 流程定义名：表单绑定流常无 biz_type，用流程名作类型/标题兜底
    def_ids = {i.process_definition_id for i in insts.values() if i and i.process_definition_id}
    def_name_map: dict[str, str] = {}
    if def_ids:
        def_name_map = {
            r[0]: r[1] for r in (await db.execute(
                select(WfProcessDefinition.id, WfProcessDefinition.name).where(
                    WfProcessDefinition.id.in_(def_ids)
                )
            )).all()
        }

    # 报价等弱标题（仅模板名）按表单字段补齐单号/客户/业务员；空标题仍用流程名 / 单号兜底
    await _heal_weak_form_titles(db, insts, def_name_map)
    fi_ids = {i.form_instance_id for i in insts.values() if i and i.form_instance_id}
    form_code_map = await _form_codes_by_instance_ids(db, fi_ids)
    out = []
    for t in tasks:
        inst = insts.get(t.process_instance_id)
        on_behalf = viewer_id is not None and t.assignee_id != viewer_id
        biz_ref_id = None
        process_name = None
        title = None
        if inst:
            process_name = def_name_map.get(inst.process_definition_id)
            title = (inst.title or "").strip() or None
            if not title:
                title = process_name or (inst.business_no or None)
            if inst.biz_type == "contract_version" and inst.biz_id:
                biz_ref_id = cv_contract_map.get(inst.biz_id)
            elif inst.biz_type == "contract_review":
                biz_ref_id = inst.biz_id
            elif inst.biz_type == "tech_agreement_review":
                biz_ref_id = inst.biz_id
        out.append({
            "task_id": t.id, "status": t.status, "opinion": t.opinion,
            "process_instance_id": t.process_instance_id,
            "title": title,
            "process_name": process_name,
            "business_no": inst.business_no if inst else None,
            "initiator_id": inst.initiator_id if inst else None,
            "initiator_name": name_map.get(inst.initiator_id) if inst else None,
            "process_status": inst.status if inst else None,
            "node_name": node_name_map.get(t.node_instance_id) if t.node_instance_id else None,
            "node_type": node_type_map.get(t.node_instance_id) if t.node_instance_id else None,
            "task_kind": (
                "revise"
                if (t.node_instance_id and node_type_map.get(t.node_instance_id) == "revise")
                else "approve"
            ),
            # 承载的业务单据：调用方据此把待办关联回业务详情页(如线索详情页的内联审批卡)
            "biz_type": inst.biz_type if inst else None,
            "biz_id": inst.biz_id if inst else None,
            "biz_ref_id": biz_ref_id,
            "form_instance_id": inst.form_instance_id if inst else None,
            "form_code": form_code_map.get(inst.form_instance_id or "") if inst else None,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "action_at": t.action_at.isoformat() if t.action_at else None,
            # 代理审批：非本人被指派的待办 = 代办，标注委托人
            "on_behalf_of": on_behalf,
            "delegator_id": t.assignee_id if on_behalf else None,
            "delegator_name": name_map.get(t.assignee_id) if on_behalf else None,
        })
    return out


# ==================== 代理审批(委托) ====================

async def active_principals(db, tenant_id, agent_id) -> list[str]:
    """返回当前时刻 agent_id 作为有效代理人所代理的委托人 user_id 列表。"""
    from app.domains.organization.models import UserAgent
    now = _now()
    rows = (await db.execute(select(UserAgent.user_id).where(
        UserAgent.tenant_id == tenant_id, UserAgent.agent_id == agent_id,
        UserAgent.status == "active", UserAgent.start_time <= now, UserAgent.end_time >= now,
    ))).scalars().all()
    return list(rows)


async def is_active_agent(db, tenant_id, principal_id: str, agent_id: str) -> bool:
    """agent_id 当前是否为 principal_id 的有效代理人。"""
    from app.domains.organization.models import UserAgent
    now = _now()
    r = (await db.execute(select(UserAgent.id).where(
        UserAgent.tenant_id == tenant_id, UserAgent.user_id == principal_id,
        UserAgent.agent_id == agent_id, UserAgent.status == "active",
        UserAgent.start_time <= now, UserAgent.end_time >= now,
    ).limit(1))).scalar_one_or_none()
    return r is not None


async def create_agent(db, tenant_id, principal_id: str, agent_id: str, start_time, end_time, note=None):
    """设置代理：principal_id 在 [start,end] 期间由 agent_id 代为审批。"""
    from app.domains.organization.models import UserAgent
    if principal_id == agent_id:
        raise BusinessException(code=BUSINESS_ERROR, message="不能设置自己为代理人")
    if end_time <= start_time:
        raise BusinessException(code=BUSINESS_ERROR, message="结束时间需晚于开始时间")
    ua = UserAgent(id=generate_uuid(), tenant_id=tenant_id, user_id=principal_id, agent_id=agent_id,
                   start_time=start_time, end_time=end_time, status="active", note=note)
    db.add(ua)
    await db.commit()
    await db.refresh(ua)
    return ua


async def list_agents(db, tenant_id, principal_id: str) -> list[dict]:
    """列出「我(principal_id)设置的代理」。"""
    from app.domains.organization.models import UserAgent
    from app.domains.auth.models import User
    rows = (await db.execute(select(UserAgent).where(
        UserAgent.tenant_id == tenant_id, UserAgent.user_id == principal_id,
    ).order_by(UserAgent.created_at.desc()))).scalars().all()
    agent_ids = {r.agent_id for r in rows}
    name_map: dict[str, str] = {}
    if agent_ids:
        urows = (await db.execute(select(User.id, User.real_name, User.username)
                 .where(User.id.in_(agent_ids)))).all()
        name_map = {u[0]: (u[1] or u[2]) for u in urows}
    now = _now()
    return [{
        "id": r.id, "agent_id": r.agent_id, "agent_name": name_map.get(r.agent_id),
        "start_time": r.start_time.isoformat() if r.start_time else None,
        "end_time": r.end_time.isoformat() if r.end_time else None,
        "status": r.status, "note": r.note,
        "active_now": r.status == "active" and (r.start_time <= now <= r.end_time),
    } for r in rows]


async def delete_agent(db, tenant_id, agent_row_id: str, principal_id: str) -> None:
    """撤销代理（仅委托人本人可撤销自己设置的代理）。"""
    from app.domains.organization.models import UserAgent
    ua = await db.get(UserAgent, agent_row_id)
    if ua and ua.tenant_id == tenant_id and ua.user_id == principal_id:
        await db.delete(ua)
        await db.commit()


async def _form_codes_by_instance_ids(db, fi_ids: set[str]) -> dict[str, str]:
    """form_instance_id → template code，供前端跳转原单据模块页。"""
    if not fi_ids:
        return {}
    from app.domains.lowcode.models import FormInstance, FormTemplate
    rows = (await db.execute(
        select(FormInstance.id, FormTemplate.code).join(
            FormTemplate, FormTemplate.id == FormInstance.template_id,
        ).where(FormInstance.id.in_(fi_ids))
    )).all()
    return {str(r[0]): str(r[1]) for r in rows if r[0] and r[1]}


def _inst_dict(i: WfProcessInstance, *, form_code: str | None = None) -> dict:
    return {
        "id": i.id, "title": i.title, "business_no": i.business_no, "status": i.status,
        "initiator_id": i.initiator_id, "form_instance_id": i.form_instance_id,
        "biz_type": i.biz_type, "biz_id": i.biz_id,
        "form_code": form_code,
        "started_at": i.started_at.isoformat() if i.started_at else None,
        "completed_at": i.completed_at.isoformat() if i.completed_at else None,
        "created_at": i.created_at.isoformat() if i.created_at else None,
        "updated_at": i.updated_at.isoformat() if getattr(i, "updated_at", None) else None,
    }


def _fmt_duration(start, end) -> str | None:
    if not start or not end:
        return None
    sec = max(0, int((end - start).total_seconds()))
    if sec < 60:
        return f"{sec}秒"
    if sec < 3600:
        return f"{sec // 60}分{sec % 60}秒"
    if sec < 86400:
        h, m = divmod(sec // 60, 60)
        return f"{h}小时{m}分"
    d, rem = divmod(sec, 86400)
    h = rem // 3600
    return f"{d}天{h}小时"


async def _build_flow_steps(
    db, nodes: list, tasks: list, logs: list, process_status: str | None = None,
) -> list[dict]:
    """按节点实例构造「流程动态」(对齐简道云右侧时间线)。

    简道云：同一节点可有多条日志 —— 转交人一条（finishAction=transfer），
    接收人待办另见 runningNodes。此处同样拆成多条 step。
    """
    from app.domains.auth.models import User

    nodes_sorted = sorted(
        nodes,
        key=lambda n: n.started_at or n.created_at or _now(),
        reverse=True,
    )
    by_node: dict[str, list] = {}
    for t in tasks:
        by_node.setdefault(t.node_instance_id, []).append(t)
    logs_by_node: dict[str, list] = {}
    for l in logs:
        if l.node_instance_id:
            logs_by_node.setdefault(l.node_instance_id, []).append(l)

    uid_set: set[str] = set()
    for t in tasks:
        if t.assignee_id:
            uid_set.add(t.assignee_id)
    for l in logs:
        if l.actor_id:
            uid_set.add(l.actor_id)

    cc_node_ids = [n.id for n in nodes_sorted]
    cc_by_node: dict[str, list[str]] = {}
    if cc_node_ids:
        cc_rows = (await db.execute(
            select(WfProcessCc.node_instance_id, WfProcessCc.user_id).where(
                WfProcessCc.node_instance_id.in_(cc_node_ids),
            )
        )).all()
        for nid, uid in cc_rows:
            if not nid or not uid:
                continue
            cc_by_node.setdefault(nid, []).append(uid)
            uid_set.add(uid)

    name_map: dict[str, str] = {}
    if uid_set:
        rows = (await db.execute(
            select(User.id, User.real_name, User.username).where(User.id.in_(uid_set))
        )).all()
        name_map = {r[0]: (r[1] or r[2] or r[0]) for r in rows}

    status_text = {
        "running": "处理中", "completed": "已完成", "cancelled": "已取消",
        "pending": "待处理", "rejected": "已驳回", "returned": "已退回",
    }
    # 会进入时间线的操作（对齐简道云 finishAction）；评论不单独占节点卡片
    _LOG_ACTIONS = frozenset({
        "approve", "reject", "transfer", "auto_transfer", "auto_approve",
        "auto_reject", "return", "withdraw", "cc",
    })

    def _iso(dt) -> str | None:
        return dt.isoformat() if dt else None

    def _step(
        *,
        step_key: str,
        n,
        status: str,
        handler_name: str | None,
        action: str | None,
        opinion: str | None,
        assignees: list,
        started_at,
        completed_at,
        is_current: bool,
        status_text_override: str | None = None,
    ) -> dict:
        end_at = completed_at if status != "running" else _now()
        return {
            "step_key": step_key,
            "node_instance_id": n.id,
            "node_def_id": n.node_def_id,
            "node_name": n.node_name,
            "node_type": n.node_type,
            "status": status,
            "status_text": status_text_override or status_text.get(status, status),
            "assignees": assignees,
            "handler_name": handler_name,
            "action": action,
            "opinion": opinion,
            "started_at": _iso(started_at),
            "completed_at": _iso(completed_at) if status != "running" else None,
            "duration": _fmt_duration(started_at, end_at),
            "is_current": is_current,
        }

    out: list[dict] = []
    for n in nodes_sorted:
        if n.node_type in ("parallel", "merge"):
            continue

        nt = by_node.get(n.id) or []
        assignees: list[dict] = []
        seen: set[str] = set()
        for t in nt:
            if t.assignee_id and t.assignee_id not in seen:
                seen.add(t.assignee_id)
                assignees.append({
                    "id": t.assignee_id,
                    "name": name_map.get(t.assignee_id, t.assignee_id),
                    "status": t.status,
                })

        node_logs = sorted(
            logs_by_node.get(n.id) or [],
            key=lambda x: x.created_at or x.updated_at or _now(),
        )
        actionable = [l for l in node_logs if getattr(l, "action", None) in _LOG_ACTIONS]
        last_lg = actionable[-1] if actionable else None
        last_action = getattr(last_lg, "action", None) if last_lg else None
        is_revise_node = n.node_type == "revise" or n.node_def_id == "__initiator_revise__"

        cfg = n.config if isinstance(getattr(n, "config", None), dict) else {}

        # 抄送：一条卡片即可
        if n.node_type == "cc":
            cc_uids = cc_by_node.get(n.id) or []
            uniq: list[str] = []
            for uid in cc_uids:
                if uid not in uniq:
                    uniq.append(uid)
            cc_assignees = [
                {"id": uid, "name": name_map.get(uid, uid), "status": "completed"}
                for uid in uniq
            ]
            out.append(_step(
                step_key=f"{n.id}:cc",
                n=n,
                status="completed",
                handler_name="系统",
                action="cc",
                opinion=None,
                assignees=cc_assignees,
                started_at=n.started_at,
                completed_at=n.completed_at or n.started_at,
                is_current=False,
            ))
            continue

        # 审批节点启用抄送：单独一条「系统·抄送」卡片（对齐简道云）；有名单后不再用空日志卡
        approval_cc_uids = cc_by_node.get(n.id) or []
        has_approval_cc_card = False
        if approval_cc_uids and n.node_type == "approval":
            uniq_cc: list[str] = []
            for uid in approval_cc_uids:
                if uid not in uniq_cc:
                    uniq_cc.append(uid)
            out.append(_step(
                step_key=f"{n.id}:approval_cc",
                n=n,
                status="completed",
                handler_name="系统",
                action="cc",
                opinion=None,
                assignees=[
                    {"id": uid, "name": name_map.get(uid, uid), "status": "completed"}
                    for uid in uniq_cc
                ],
                started_at=n.started_at,
                completed_at=n.started_at,
                is_current=False,
            ))
            has_approval_cc_card = True

        # 历史兼容：节点仍 running 但已驳回/撤回/流程结束（修订节点除外，仍显示待修改）
        force_status = None
        if n.status == "running" and not is_revise_node:
            if last_action in ("reject", "auto_reject") or process_status == "rejected":
                force_status = "rejected"
            elif process_status == "withdrawn":
                force_status = "cancelled"
            elif process_status == "completed":
                force_status = "cancelled"

        # 自动通过（无日志时靠 config）
        if cfg.get("auto_approve") and not actionable:
            out.append(_step(
                step_key=f"{n.id}:auto",
                n=n,
                status="completed",
                handler_name="系统",
                action="auto_approve",
                opinion=f"节点「{n.node_name}」无审批人，自动通过",
                assignees=assignees,
                started_at=n.started_at,
                completed_at=n.completed_at or n.started_at,
                is_current=False,
            ))
            continue

        # 每条操作日志 → 一条动态（转交人单独成卡，对齐简道云）
        prev_at = n.started_at
        for lg in actionable:
            act = lg.action
            # 审批节点抄送已有名单卡时，跳过空的 action=cc 日志，避免双卡
            if act == "cc" and has_approval_cc_card:
                continue
            st = "rejected" if act in ("reject", "auto_reject") else "completed"
            if force_status == "rejected" and act in ("reject", "auto_reject"):
                st = "rejected"
            actor = lg.actor_name or (name_map.get(lg.actor_id) if lg.actor_id else None)
            op = lg.opinion
            if act == "auto_approve":
                actor = actor or "系统"
                if not op:
                    op = f"节点「{n.node_name}」无审批人，自动通过"
            # 仅有日志、无 wf_process_cc 时：仍展示抄送卡（无名单）
            if act == "cc":
                actor = actor or "系统"
            done_at = lg.created_at
            step = _step(
                step_key=f"{n.id}:log:{getattr(lg, 'id', id(lg))}",
                n=n,
                status=st,
                handler_name=actor,
                action=act,
                opinion=op,
                assignees=assignees if act != "cc" else [],
                started_at=prev_at,
                completed_at=done_at,
                is_current=False,
            )
            # 转交卡片标签对齐简道云观感：已转交
            if act in ("transfer", "auto_transfer"):
                step["status_text"] = "已转交"
                step["node_name"] = f"{n.node_name} · 转交"
            elif act == "return":
                step["status_text"] = "已退回"
            out.append(step)
            prev_at = done_at

        # 仍在处理中：当前待办人单独一条（转交后显示接收人）
        if n.status == "running" and not force_status:
            _task_st = {
                "pending": "待处理", "waiting": "排队中", "approved": "已通过",
                "rejected": "已驳回", "cancelled": "已取消",
            }
            active = [a for a in assignees if a.get("status") != "cancelled"]
            pending = [a for a in active if a["status"] == "pending"]
            waiting = [a for a in active if a["status"] == "waiting"]
            if len(active) > 1:
                handler = "、".join(
                    f"{a['name']}({_task_st.get(a['status'], a['status'])})"
                    for a in active
                )
            else:
                names = [a["name"] for a in (pending or waiting or active)]
                handler = "、".join(names) if names else None
            # 转交后待办起点用转交时间，对齐简道云 runningNodes.startAt
            cur_start = prev_at or n.started_at
            out.append(_step(
                step_key=f"{n.id}:current",
                n=n,
                status="running",
                handler_name=handler,
                action="pending",
                opinion=None,
                assignees=assignees,
                started_at=cur_start,
                completed_at=None,
                is_current=True,
                status_text_override="待修改" if is_revise_node else None,
            ))
        elif not actionable and force_status:
            # 无日志的僵死节点
            out.append(_step(
                step_key=f"{n.id}:force",
                n=n,
                status=force_status,
                handler_name=getattr(last_lg, "actor_name", None) if last_lg else None,
                action=last_action,
                opinion=getattr(last_lg, "opinion", None) if last_lg else None,
                assignees=assignees,
                started_at=n.started_at,
                completed_at=n.completed_at or (getattr(last_lg, "created_at", None) if last_lg else None),
                is_current=False,
            ))
        elif not actionable and n.status == "completed":
            # 无日志已完成：用任务汇总兜底
            handler = None
            if assignees:
                handler = "、".join(a["name"] for a in assignees)
            out.append(_step(
                step_key=f"{n.id}:done",
                n=n,
                status="completed",
                handler_name=handler,
                action="approve",
                opinion=None,
                assignees=assignees,
                started_at=n.started_at,
                completed_at=n.completed_at,
                is_current=False,
            ))

    # 最新在前（同节点：当前处理中 > 最近操作）
    def _sort_key(s: dict):
        raw = s.get("completed_at") or s.get("started_at") or ""
        # 处理中置顶于同节点其它卡片：加一点权重
        boost = 1 if s.get("is_current") else 0
        return (raw, boost)

    out.sort(key=_sort_key, reverse=True)
    return out


async def find_latest_instance_by_biz(
    db, tenant_id: str, biz_type: str, biz_id: str,
    viewer_id: str | None = None,
) -> dict | None:
    """业务详情页按 (biz_type, biz_id) 取最新流程实例详情（含审批记录）。无则 None。"""
    if not biz_type or not biz_id:
        return None
    inst = (await db.execute(
        select(WfProcessInstance).where(
            WfProcessInstance.tenant_id == tenant_id,
            WfProcessInstance.biz_type == biz_type,
            WfProcessInstance.biz_id == biz_id,
        ).order_by(WfProcessInstance.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    if not inst:
        return None
    return await get_instance_detail(db, tenant_id, inst.id, viewer_id=viewer_id)


async def find_latest_instance_by_form_instance(
    db, tenant_id: str, form_instance_id: str,
    viewer_id: str | None = None,
) -> dict | None:
    """表单详情页：按 form_instance_id 取最新流程实例（兼容未回写 process_instance_id 的旧数据）。"""
    if not form_instance_id:
        return None
    from sqlalchemy import case
    active_first = case(
        (WfProcessInstance.status.in_(("running", "returned", "rejected", "withdrawn")), 0),
        else_=1,
    )
    inst = (await db.execute(
        select(WfProcessInstance).where(
            WfProcessInstance.tenant_id == tenant_id,
            WfProcessInstance.form_instance_id == form_instance_id,
        ).order_by(
            active_first,
            WfProcessInstance.started_at.desc().nulls_last(),
            WfProcessInstance.created_at.desc(),
        ).limit(1)
    )).scalar_one_or_none()
    if not inst:
        return None
    return await get_instance_detail(db, tenant_id, inst.id, viewer_id=viewer_id)


def list_activate_nodes(version: WfProcessDefinitionVersion | None) -> list[dict]:
    """可激活节点：开始 + 全部审批（对齐简道云激活流程下拉）。"""
    if not version:
        return []
    out: list[dict] = []
    for n in version.node_definitions or []:
        if not isinstance(n, dict) or not n.get("id"):
            continue
        ntype = n.get("type")
        if ntype == "start":
            out.append({
                "id": n["id"],
                "name": n.get("name") or "开始",
                "type": "start",
            })
        elif ntype == "approval":
            out.append({
                "id": n["id"],
                "name": n.get("name") or "审批",
                "type": "approval",
            })
    return out


async def get_activate_nodes(db, tenant_id: str, instance_id: str) -> list[dict]:
    inst = (await db.execute(select(WfProcessInstance).where(
        WfProcessInstance.id == instance_id, WfProcessInstance.tenant_id == tenant_id,
    ))).scalar_one_or_none()
    if not inst:
        raise BusinessException(code=NOT_FOUND, message="流程实例不存在")
    version = await db.get(WfProcessDefinitionVersion, inst.process_version_id)
    # 优先已发布最新版
    pub = (await db.execute(select(WfProcessDefinitionVersion).where(
        WfProcessDefinitionVersion.tenant_id == tenant_id,
        WfProcessDefinitionVersion.process_definition_id == inst.process_definition_id,
        WfProcessDefinitionVersion.status == "published",
    ).order_by(WfProcessDefinitionVersion.version_number.desc()).limit(1))).scalar_one_or_none()
    return list_activate_nodes(pub or version)


async def get_instance_detail(
    db, tenant_id, instance_id, viewer_id: str | None = None,
    task_id: str | None = None,
) -> dict:
    inst = (await db.execute(select(WfProcessInstance).where(
        WfProcessInstance.id == instance_id, WfProcessInstance.tenant_id == tenant_id,
    ))).scalar_one_or_none()
    if not inst:
        raise BusinessException(code=NOT_FOUND, message="流程实例不存在")
    logs = (await db.execute(select(WfTaskActionLog).where(
        WfTaskActionLog.process_instance_id == instance_id,
    ).order_by(WfTaskActionLog.created_at.asc()))).scalars().all()
    tasks = (await db.execute(select(WfTaskInstance).where(
        WfTaskInstance.process_instance_id == instance_id,
    ))).scalars().all()
    comments = (await db.execute(select(WfProcessComment).where(
        WfProcessComment.process_instance_id == instance_id,
    ).order_by(WfProcessComment.created_at.asc()))).scalars().all()
    version = await db.get(WfProcessDefinitionVersion, inst.process_version_id)
    approval_nodes = [
        {"id": "__initiator__", "name": "退回发起人（修改后重提）"},
        *[
            {"id": n.get("id"), "name": n.get("name") or "审批"}
            for n in (version.node_definitions if version else []) if n.get("type") == "approval"
        ],
    ]
    activate_nodes = list_activate_nodes(version)
    can_activate = inst.status in ("completed", "rejected", "withdrawn") and bool(activate_nodes)
    # 业务单据审批（线索/报价等）没有 form_instance：把业务关键字段塞进 biz_detail，
    # 供审批中心抽屉展示；否则审批人只能看到「无关联表单」。
    biz_detail: dict = {}
    biz_ref_id = None
    process_name = None
    try:
        dfn = await db.get(WfProcessDefinition, inst.process_definition_id)
        process_name = dfn.name if dfn else None
    except Exception:
        process_name = None

    # 表单流历史数据可能没写 title / 仅有模板名：从关联表单补齐展示（并回写）
    from app.domains.lowcode.service import (
        derive_form_instance_title_resolved,
        is_weak_form_title,
    )
    if is_weak_form_title(inst.title, process_name) or (
        inst.form_instance_id and is_weak_form_title(inst.title)
    ):
        healed = None
        if inst.form_instance_id:
            try:
                from app.domains.lowcode.models import FormInstance, FormTemplate
                fi = await db.get(FormInstance, inst.form_instance_id)
                if fi:
                    tpl = await db.get(FormTemplate, fi.template_id) if fi.template_id else None
                    tpl_name = (tpl.name if tpl else None) or process_name
                    # 仅模板名也视为弱标题，强制按表单字段重算
                    if is_weak_form_title(inst.title, tpl_name) or is_weak_form_title(inst.title, process_name):
                        healed = await derive_form_instance_title_resolved(
                            db, tenant_id, tpl_name,
                            fi.form_data if isinstance(fi.form_data, dict) else {},
                            fi.field_definitions,
                        )
                        if healed and is_weak_form_title(fi.title, tpl_name):
                            fi.title = healed
            except Exception:
                healed = None
        if not healed:
            healed = process_name
        if healed and healed != (inst.title or "").strip():
            inst.title = healed
            try:
                await db.commit()
                await db.refresh(inst)
            except Exception:
                await db.rollback()

    if inst.biz_type and inst.biz_id:
        try:
            from app.domains.approval.service import _resolve_biz_detail
            biz_detail = await _resolve_biz_detail(db, tenant_id, inst.biz_type, inst.biz_id) or {}
        except Exception:
            biz_detail = {}
        if inst.biz_type == "contract_review":
            biz_ref_id = inst.biz_id
        elif inst.biz_type == "tech_agreement_review":
            biz_ref_id = inst.biz_id
        elif inst.biz_type == "contract_version":
            try:
                from app.domains.contract.models import ContractVersion
                ver = await db.get(ContractVersion, inst.biz_id)
                if ver:
                    biz_ref_id = ver.contract_id
            except Exception:
                biz_ref_id = None

    # 表单绑定流：把字段定义+数据嵌进详情，审批人不必再调 form_data:view
    form_fields: list = []
    form_data: dict = {}
    form_rules: list = []
    form_code: str | None = None
    if inst.form_instance_id:
        try:
            from app.domains.lowcode.models import FormInstance, FormTemplateVersion
            from app.domains.lowcode.service import get_published_version
            fi = await db.get(FormInstance, inst.form_instance_id)
            if fi and not getattr(fi, "is_deleted", False):
                form_fields = list(fi.field_definitions or [])
                form_data = dict(fi.form_data or {}) if isinstance(fi.form_data, dict) else {}
                form_tpl_code: str | None = None
                try:
                    from app.domains.lowcode.models import FormTemplate
                    from app.domains.lowcode.prod_card_contract_fill import (
                        overlay_prod_card_contract_live,
                    )
                    tpl = await db.get(FormTemplate, fi.template_id)
                    form_tpl_code = tpl.code if tpl else None
                    form_code = form_tpl_code
                    if tpl and tpl.code == "prod_card_supplement":
                        form_data = await overlay_prod_card_contract_live(
                            db, tenant_id, form_data,
                        )
                except Exception:
                    pass
                ver = await db.get(FormTemplateVersion, fi.template_version_id) if fi.template_version_id else None
                if ver:
                    if not form_fields:
                        form_fields = list(ver.field_definitions or [])
                    form_rules = list(ver.rule_definitions or [])
                # 实例快照 type/props 可能落后：用当前已发布模板覆盖（如科室改多选）
                try:
                    pub = await get_published_version(db, tenant_id, fi.template_id)
                except Exception:
                    pub = None
                if pub and pub.field_definitions:
                    pub_by_id = {
                        fd["id"]: fd for fd in (pub.field_definitions or [])
                        if isinstance(fd, dict) and fd.get("id")
                    }
                    if not form_fields:
                        form_fields = list(pub.field_definitions)
                    else:
                        merged_ff: list = []
                        for fd in form_fields:
                            if not isinstance(fd, dict) or not fd.get("id"):
                                continue
                            pfd = pub_by_id.get(fd["id"])
                            if not isinstance(pfd, dict):
                                merged_ff.append(fd)
                                continue
                            m = dict(fd)
                            if pfd.get("type"):
                                m["type"] = pfd["type"]
                            if pfd.get("label"):
                                m["label"] = pfd["label"]
                            pub_props = pfd.get("props") if isinstance(pfd.get("props"), dict) else {}
                            if pub_props:
                                props = dict(m.get("props") or {})
                                if pub_props.get("pickable_scope"):
                                    props["pickable_scope"] = pub_props["pickable_scope"]
                                m["props"] = props
                            merged_ff.append(m)
                        form_fields = merged_ff
                    if pub.rule_definitions:
                        form_rules = list(pub.rule_definitions)
                # 生产卡：叠设计单分派显隐（总部单不要求转新乡），避免已发布规则未同步时仍必填
                if form_tpl_code == "prod_card_supplement":
                    try:
                        from app.domains.lowcode.prod_card_contract_fill import (
                            apply_prod_card_detail_quick_fill_flags,
                            apply_prod_card_install_pick_fields,
                            apply_prod_card_legacy_hidden_fields,
                            apply_prod_card_prune_std_room_columns,
                            apply_prod_card_supplement_rules,
                        )
                        apply_prod_card_install_pick_fields(form_fields)
                        apply_prod_card_prune_std_room_columns(form_fields)
                        apply_prod_card_detail_quick_fill_flags(form_fields)
                        apply_prod_card_legacy_hidden_fields(form_fields)
                        form_rules = apply_prod_card_supplement_rules(form_rules)
                    except Exception:
                        pass
                if form_tpl_code == "payment_registration":
                    try:
                        from app.domains.lowcode.payment_registration_fields import (
                            apply_payment_registration_fields,
                        )
                        apply_payment_registration_fields(form_fields)
                    except Exception:
                        pass
                if form_tpl_code == "shipment_notice":
                    try:
                        from app.domains.lowcode.shipment_notice_fields import (
                            apply_shipment_notice_fields,
                        )
                        apply_shipment_notice_fields(form_fields)
                    except Exception:
                        pass
                if form_tpl_code == "quote_management":
                    try:
                        from app.domains.auth.service import get_user_roles
                        from app.domains.lowcode.field_permission import filter_read
                        from app.domains.lowcode.quote_management_fields import prepare_quote_field_defs
                        form_fields = prepare_quote_field_defs(form_fields)
                        viewer_roles: list[str] = []
                        if viewer_id:
                            viewer_roles = await get_user_roles(db, viewer_id, tenant_id)
                        is_creator = bool(
                            viewer_id and (
                                viewer_id == getattr(fi, "created_by", None)
                                or viewer_id == getattr(fi, "initiator_id", None)
                                or viewer_id == inst.initiator_id
                            )
                        )
                        form_fields, form_data = filter_read(
                            form_fields, form_data, viewer_roles, is_creator=is_creator,
                        )
                    except Exception:
                        pass
        except Exception:
            form_fields, form_data, form_rules = [], {}, []

    current_task = await _resolve_current_task_for_viewer(
        db, tenant_id, inst, version, list(tasks), viewer_id, task_id=task_id,
    )
    nodes = (await db.execute(select(WfNodeInstance).where(
        WfNodeInstance.process_instance_id == instance_id,
    ))).scalars().all()
    flow_steps = await _build_flow_steps(
        db, list(nodes), list(tasks), list(logs), process_status=inst.status,
    )
    # 补一条「发起」动态（对齐简道云流程发起节点）
    initiator_name = None
    if inst.started_at:
        from app.domains.auth.models import User
        if inst.initiator_id:
            u = (await db.execute(
                select(User.real_name, User.username).where(User.id == inst.initiator_id)
            )).first()
            if u:
                initiator_name = u[0] or u[1]
        flow_steps.append({
            "node_instance_id": f"start:{inst.id}",
            "node_def_id": "start",
            "node_name": "流程发起",
            "node_type": "start",
            "status": "completed",
            "status_text": "已完成",
            "assignees": [],
            "handler_name": initiator_name,
            "action": "submit",
            "opinion": None,
            "started_at": inst.started_at.isoformat(),
            "completed_at": inst.started_at.isoformat(),
            "duration": "1秒",
            "is_current": False,
        })
    elif inst.initiator_id:
        from app.domains.auth.models import User
        u = (await db.execute(
            select(User.real_name, User.username).where(User.id == inst.initiator_id)
        )).first()
        if u:
            initiator_name = u[0] or u[1]

    # 轨迹补充节点名
    ni_name = {n.id: n.node_name for n in nodes}
    return {
        **_inst_dict(inst, form_code=form_code),
        "initiator_name": initiator_name,
        "process_name": process_name,
        "approval_nodes": approval_nodes,
        "activate_nodes": activate_nodes,
        "can_activate": can_activate,
        "biz_detail": biz_detail,
        "biz_ref_id": biz_ref_id,
        "form_fields": form_fields,
        "form_data": form_data,
        "form_rules": form_rules,
        "current_task": current_task,
        "flow_steps": flow_steps,
        "timeline": [{
            "action": l.action, "actor_id": l.actor_id, "actor_name": l.actor_name,
            "opinion": l.opinion, "at": l.created_at.isoformat() if l.created_at else None,
            "node_name": ni_name.get(l.node_instance_id) if l.node_instance_id else None,
        } for l in logs],
        "tasks": [{
            "id": t.id, "assignee_id": t.assignee_id, "status": t.status,
            "opinion": t.opinion, "task_order": t.task_order,
            "node_instance_id": t.node_instance_id,
        } for t in tasks],
        "comments": [{
            "user_id": c.user_id, "user_name": c.user_name, "content": c.content,
            "at": c.created_at.isoformat() if c.created_at else None,
        } for c in comments],
    }


async def _resolve_current_task_for_viewer(
    db, tenant_id: str, inst: WfProcessInstance,
    version: WfProcessDefinitionVersion | None,
    tasks: list, viewer_id: str | None,
    task_id: str | None = None,
) -> dict | None:
    """若 viewer 对本实例有 pending 待办，返回节点可填字段配置与当前值。

    并行会签时同一人可能有多条待办：传入 task_id 时优先解析该任务，避免填错节点字段。
    撤回/驳回后的发起人修订待办（node_type=revise）同样返回，供编辑后重新提交。
    """
    if not viewer_id:
        return None
    allow_revise = inst.status in ("withdrawn", "rejected", "returned")
    if inst.status != "running" and not allow_revise:
        return None
    assignees = [viewer_id]
    try:
        principals = await active_principals(db, tenant_id, viewer_id)
        assignees = [viewer_id, *principals]
    except Exception:
        pass
    pending = None
    if task_id:
        pending = next(
            (t for t in tasks
             if t.id == task_id and t.status == "pending" and t.assignee_id in assignees),
            None,
        )
    if not pending:
        pending = next(
            (t for t in tasks if t.status == "pending" and t.assignee_id in assignees),
            None,
        )
    if not pending:
        return None
    from app.domains.lowcode.wf_field_writeback import load_field_values, parse_field_perms
    from app.domains.lowcode.wf_node_actions import parse_node_actions
    from app.domains.lowcode.biz_field_catalog import get_catalog

    node_inst = await db.get(WfNodeInstance, pending.node_instance_id)
    node_def_id = node_inst.node_def_id if node_inst else None
    node_type = (node_inst.node_type if node_inst else None) or ""
    is_revise = node_type == "revise" or node_def_id == "__initiator_revise__"
    if allow_revise and not is_revise:
        return None

    nodes = {n.get("id"): n for n in (version.node_definitions if version else [])}
    node = nodes.get(node_def_id or "") or {}
    if is_revise:
        node = {"name": (node_inst.node_name if node_inst else None) or "修改并重新提交"}
        field_perms: list = []
    else:
        field_perms = parse_field_perms(node)
        try:
            latest_pub = await _published_version(db, tenant_id, inst.process_definition_id)
            if latest_pub and (not version or latest_pub.id != version.id):
                by_id = {
                    n.get("id"): n for n in (latest_pub.node_definitions or [])
                    if isinstance(n, dict) and n.get("id")
                }
                by_name = {
                    n.get("name"): n for n in (latest_pub.node_definitions or [])
                    if isinstance(n, dict) and n.get("name")
                }
                latest_node = by_id.get(node_def_id or "") or by_name.get(node.get("name") or "")
                if latest_node:
                    # 在途单冻结旧版 field_perms 时，以最新发布版本节点可填区为准
                    # （否则物流等节点仍会带上已下线的明细可填/误强制列）
                    field_perms = parse_field_perms(latest_node)
        except Exception:
            pass
    from app.domains.lowcode.prod_card_contract_fill import (
        PROD_CARD_LEGACY_HIDDEN_FIELDS,
        filter_prod_card_legacy_field_perms,
    )
    field_perms = filter_prod_card_legacy_field_perms(field_perms)

    field_ids = [p["field"] for p in field_perms]
    catalog = {f["id"]: f for f in get_catalog(inst.biz_type or "")}
    published_by_id: dict = {}
    form_tpl_code: str | None = None
    is_prod_card = inst.biz_type == "prod_card_supplement"
    if inst.form_instance_id:
        from app.domains.lowcode.models import FormInstance, FormTemplate
        fi = await db.get(FormInstance, inst.form_instance_id)
        form_defs = []
        if fi and fi.tenant_id == tenant_id:
            tpl = await db.get(FormTemplate, fi.template_id)
            form_tpl_code = tpl.code if tpl else None
            form_defs = list(fi.field_definitions or [])
            from app.domains.lowcode.service import get_published_version
            try:
                ver = await get_published_version(db, tenant_id, fi.template_id)
                pub_defs = list((ver.field_definitions if ver else None) or [])
                published_by_id = {
                    fd["id"]: fd for fd in pub_defs
                    if isinstance(fd, dict) and fd.get("id")
                }
                if not form_defs:
                    form_defs = pub_defs
            except Exception:
                published_by_id = {}
        for fd in form_defs:
            if isinstance(fd, dict) and fd.get("id") and fd["id"] not in catalog:
                catalog[fd["id"]] = fd
        is_prod_card = (
            form_tpl_code == "prod_card_supplement"
            or inst.biz_type == "prod_card_supplement"
        )
        if is_prod_card:
            from app.domains.lowcode.prod_card_contract_fill import (
                apply_prod_card_detail_quick_fill_flags,
                apply_prod_card_legacy_hidden_fields,
                apply_prod_card_prune_std_room_columns,
            )
            patched_defs = list(catalog.values())
            apply_prod_card_prune_std_room_columns(patched_defs)
            apply_prod_card_detail_quick_fill_flags(patched_defs)
            apply_prod_card_legacy_hidden_fields(patched_defs)
            catalog = {fd["id"]: fd for fd in patched_defs if isinstance(fd, dict) and fd.get("id")}
        # 修订待办：整单可编辑，返回全部表单字段
        if is_revise and form_defs:
            field_ids = [fd["id"] for fd in form_defs if isinstance(fd, dict) and fd.get("id")]
            field_perms = [{"field": fid, "access": "editable"} for fid in field_ids]
            field_perms = filter_prod_card_legacy_field_perms(field_perms)
            field_ids = [p["field"] for p in field_perms]

    field_meta = []
    for fid in field_ids:
        if fid in PROD_CARD_LEGACY_HIDDEN_FIELDS:
            continue
        meta = dict(catalog.get(fid) or {"id": fid, "label": fid, "type": "text"})
        pub = published_by_id.get(fid)
        if isinstance(pub, dict):
            if pub.get("type"):
                meta["type"] = pub["type"]
            if pub.get("detail_table_columns"):
                meta["detail_table_columns"] = pub["detail_table_columns"]
            pub_props = pub.get("props") if isinstance(pub.get("props"), dict) else {}
            if pub_props.get("pickable_scope"):
                props = dict(meta.get("props") or {})
                props["pickable_scope"] = pub_props["pickable_scope"]
                meta["props"] = props
        if is_prod_card and fid == "f_251128":
            from app.domains.lowcode.prod_card_contract_fill import apply_prod_card_install_pick_fields
            patched = [dict(meta)]
            apply_prod_card_install_pick_fields(patched)
            if patched and patched[0].get("detail_table_columns"):
                meta["detail_table_columns"] = patched[0]["detail_table_columns"]
        if fid in ("design_assignees",):
            props = dict(meta.get("props") or {})
            scope = props.get("pickable_scope")
            if isinstance(scope, dict) and scope.get("filter_by_fields"):
                props["pickable_scope"] = {
                    k: v for k, v in scope.items() if k != "filter_by_fields"
                }
                meta["props"] = props
        item = {
            "id": fid,
            "label": meta.get("label") or fid,
            "type": meta.get("type") or "text",
        }
        if meta.get("options"):
            item["options"] = meta["options"]
        if meta.get("detail_table_columns"):
            item["detail_table_columns"] = meta["detail_table_columns"]
        if isinstance(meta.get("props"), dict) and meta["props"]:
            item["props"] = meta["props"]
        field_meta.append(item)

    if is_prod_card and field_meta:
        from app.domains.lowcode.prod_card_contract_fill import apply_prod_card_prune_std_room_columns
        apply_prod_card_prune_std_room_columns(field_meta)

    value_ids = list(field_ids)
    for item in field_meta:
        scope = (item.get("props") or {}).get("pickable_scope") if isinstance(item.get("props"), dict) else None
        if isinstance(scope, dict):
            for dep in scope.get("filter_by_fields") or []:
                if dep and dep not in value_ids:
                    value_ids.append(str(dep))
    field_values = await load_field_values(
        db, tenant_id, inst.biz_type, inst.biz_id, inst.form_instance_id, value_ids,
    )
    return {
        "task_id": pending.id,
        "node_id": node_def_id,
        "node_name": (node_inst.node_name if is_revise and node_inst else None)
            or node.get("name") or "审批",
        "node_type": node_type or ("revise" if is_revise else None),
        "task_kind": "revise" if is_revise else "approve",
        "field_perms": field_perms,
        "opinion_required": False if is_revise else bool(node.get("opinion_required")),
        "node_actions": parse_node_actions(
            node if not is_revise else None,
            biz_type=inst.biz_type,
            form_code=form_tpl_code,
        ),
        "field_meta": field_meta,
        "field_values": field_values,
    }
