"""扩展平台 — 审批流程引擎服务(定义生命周期 + 运行时查询 + 表单绑定触发)。"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
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
    await get_definition(db, tenant_id, def_id)
    from app.domains.lowcode.jdy_id_remap import sanitize_route_ids_for_tenant
    routes, _ = await sanitize_route_ids_for_tenant(db, tenant_id, data.route_definitions or [])
    draft = await _draft_version(db, tenant_id, def_id)
    if draft:
        draft.node_definitions = data.node_definitions
        draft.route_definitions = routes
        draft.approver_rules = data.approver_rules
        await db.commit()
        await db.refresh(draft)
        return draft
    latest = await _latest_version(db, tenant_id, def_id)
    v = WfProcessDefinitionVersion(
        id=generate_uuid(), tenant_id=tenant_id, process_definition_id=def_id,
        version_number=(latest.version_number + 1) if latest else 1,
        node_definitions=data.node_definitions, route_definitions=routes,
        approver_rules=data.approver_rules, status="draft",
    )
    db.add(v)
    await db.commit()
    await db.refresh(v)
    return v


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
    if not title:
        from app.domains.lowcode.service import derive_form_instance_title
        from app.domains.lowcode.models import FormTemplate
        tpl = await db.get(FormTemplate, template_id)
        title = derive_form_instance_title(
            (tpl.name if tpl else None) or d.name,
            form_data,
            getattr(form_instance, "field_definitions", None),
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
# 系统兜底流程排在最后，租户自建流程(sort_order 默认 0)优先命中
_SYSTEM_DEFAULT_SORT = 9999

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
        "approver_rule": {"type": "specified_role", "value": "lead_intel", "exclude_initiator": True},
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
            "type": "specified_role", "value": "service_manager", "exclude_initiator": True,
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
    pack = packs.get(form_code)
    if not pack:
        return None
    import copy
    nodes = copy.deepcopy(pack.get("flow_nodes") or [])
    routes = copy.deepcopy(pack.get("flow_routes") or [])
    if not nodes:
        return None
    if form_code == "install_drawing_notice":
        from app.domains.lowcode.biz_score import apply_biz_score_flow_nodes
        apply_biz_score_flow_nodes(nodes)
    if form_code == "scheme_management":
        from app.domains.lowcode.biz_score import (
            apply_chief_gm_flow_nodes, strip_biz_score_flow_nodes,
        )
        strip_biz_score_flow_nodes(nodes)
        apply_chief_gm_flow_nodes(nodes)
    return nodes, routes


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


def _flow_is_jdy_payment(nodes: list | None) -> bool:
    """已对齐简道云收款登记：按部门分支的多路内勤处理。"""
    names = {n.get("name") for n in (nodes or [])}
    return "内勤处理" in names and "采购" in names and len(nodes or []) >= 15


def _flow_is_jdy_quote(nodes: list | None) -> bool:
    """已对齐简道云核价管理流程：财务核价 + 部门审批分支。"""
    names = {n.get("name") for n in (nodes or [])}
    return "财务核价" in names and "部门审批" in names and len(nodes or []) >= 15


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
    if form_code == "pricing_checklist_hjqd":
        return _flow_is_jdy_pricing_checklist(nodes)
    if form_code == "research_coop_card":
        return _flow_is_jdy_research_coop_card(nodes)
    if form_code and form_code.startswith("cs_"):
        return _flow_is_jdy_customer_service(nodes)
    return False


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
    """旧生成器把叶子抄送接到 end，或入抄送边未标 always —— 需再升级。"""
    cc_ids = {n.get("id") for n in (nodes or []) if n.get("type") == "cc" and n.get("id")}
    if not cc_ids:
        return False
    for r in routes or []:
        if not isinstance(r, dict):
            continue
        if r.get("target") == "end" and r.get("source") in cc_ids:
            return True
        if r.get("target") in cc_ids and not r.get("always"):
            return True
    return False


def _source_is_jdy_parallel_fork(outs: list) -> bool:
    """显式标了 fork=parallel 的同源分叉（工艺包装串行优先不走此标记）。"""
    return any(isinstance(o, dict) and o.get("fork") == "parallel" for o in outs)


def _flow_missing_exclusive_groups(routes: list | None) -> bool:
    """同源多出边未标 exclusive_group 时，画布像一条直线、引擎也可能不按 if/else 选路。

    标了 ``fork=parallel`` 的分叉故意不设互斥组，跳过。
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
        if len(outs) < 2:
            continue
        if _source_is_jdy_parallel_fork(outs):
            continue
        if any(not o.get("exclusive_group") for o in outs):
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
    await ensure_all_form_defaults(db, tenant_id)


async def ensure_all_form_defaults(db, tenant_id: str) -> None:
    """幂等：安装图纸等内置表单（若尚未安装），并补齐绑定表单的默认审批流。"""
    from app.domains.lowcode.service import ensure_builtin_form
    for spec in FORM_DEFAULT_SPECS:
        try:
            await ensure_builtin_form(db, tenant_id, spec["form_code"], {"sub": None})
        except Exception as e:
            logger.warning("ensure form flow %s failed: %s", spec.get("code"), e)


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
    "finance_dir": ["02362556584221", "0433406811775721"],  # 李晋、张光（会签）
    "production": "01210720669288",           # 周世孔
    "procurement": "02352513566524",          # 杨霜
    "qc": "0236420233847",                    # 张国运
    "export": "01000533004677",               # 王玲玲
    "legal_sup": "492105073721398323",        # 史守义（法务主管）
    # 抄送具名
    "cc_install": ["080160552326376700", "02364307332960", "232040221426613133"],  # 杜珍珍/韩利民/杜金波
    "cc_related": ["02364249424532", "023656363429294971", "02362556584221"],  # 李惠萍/王梦颖/李晋
    "cc_lili": "02364313303546",              # 李莉
    "cc_xunhan": "01670210101135172",         # 许曼（简道云迅焊）
}

# 简道云「合同技术协议评审」chargers / 抄送 → CRM username
_JDY_TAR_USER = {
    "market_support": "023641581817",         # 李巧芳（市场支持中心）
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
        _field_person_approval_node("approval_region", "区域经理/组长", "region_manager_id"),
        {
            "id": "approval_biz", "type": "approval", "name": "业务部门审批",
            "approver_rule": {"type": "dept_head", "exclude_initiator": True},
            "multi_mode": "or_sign", "empty_strategy": "auto_approve",
            "field_perms": _fp(("biz_risk", "required"), ("biz_risk_desc", "editable")),
        },
        _user_approval_node("approval_intel", "信息情报部审批", u["intel"]),
        _role_approval_node(
            "approval_legal", "法务审批", "legal",
            field_perms=_fp(
                ("legal_risk", "required"), ("legal_risk_desc", "editable"),
                ("clause_opinion", "editable"),
            ),
        ),
        _user_approval_node("approval_legal_sup", "法务主管审批", u["legal_sup"]),
        _user_approval_node(
            "approval_design", "设计审批", u["design"],
            field_perms=_fp(("tech_risk", "required"), ("tech_risk_desc", "editable")),
        ),
        _user_approval_node(
            "approval_finance_dir", "财务总监意见", u["finance_dir"],
            multi_mode="and_sign",
            field_perms=_fp(("finance_risk", "required"), ("finance_risk_desc", "editable")),
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
            field_perms=_fp(("finance_risk", "required"), ("finance_risk_desc", "editable")),
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
        _user_approval_node(
            "approval_procurement", "采购审批", u["procurement"],
            field_perms=_fp(("purchase_risk", "required"), ("purchase_risk_desc", "editable")),
        ),
        _user_approval_node("approval_qc", "质检审批", u["qc"]),
        _creator_approval_node("approval_initiator", "发起人"),
        {"id": "merge_ops_post", "type": "merge", "name": "产采质汇聚"},
        # 反馈回路
        _creator_approval_node(
            "approval_info_feedback", "信息反馈",
            field_perms=_fp(("need_feedback", "editable")),
        ),
        _field_person_approval_node(
            "approval_feedback_region", "反馈区域经理/组长", "region_manager_id",
        ),
        {
            "id": "approval_feedback_biz", "type": "approval", "name": "反馈业务部门",
            "approver_rule": {"type": "dept_head", "exclude_initiator": True},
            "multi_mode": "or_sign", "empty_strategy": "auto_approve",
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
        # 业务 → 会签分支
        {
            "id": "r_biz_legal", "source": "approval_biz", "target": "approval_legal",
            "condition": _and_cond(rt_contract),
        },
        *[
            {"id": f"r_biz_{tid}", "source": "approval_biz", "target": tid, "condition": cond}
            for tid, cond in peer_to_merge
        ],
        {"id": "r_biz_merge", "source": "approval_biz", "target": "merge_review"},
        # 法务 → 法务主管 → 汇聚
        {"id": "r_legal_sup", "source": "approval_legal", "target": "approval_legal_sup"},
        {"id": "r_legal_sup_merge", "source": "approval_legal_sup", "target": "merge_review"},
        *[{"id": f"r_{tid}_merge", "source": tid, "target": "merge_review"} for tid, _ in peer_to_merge],
        # 主干
        {"id": "r_merge_gm", "source": "merge_review", "target": "approval_gm"},
        {"id": "r_gm_fin", "source": "approval_gm", "target": "approval_finance_opinion"},
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
        # 财务意见后主分支
        *[
            {"id": f"r_fin_{tid}", "source": "approval_finance_opinion", "target": tid, "condition": cond}
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
        {"id": "r_fb_biz_gm", "source": "approval_feedback_biz", "target": "approval_gm"},
        # 设计审批1 再入总经理
        {"id": "r_design_fb_gm", "source": "approval_design_fb", "target": "approval_gm"},
    ]
    return nodes, routes


def _tech_agreement_flow_graph() -> tuple[list[dict], list[dict]]:
    """技术协议评审默认图：对齐简道云「合同技术协议评审 HTJSXY」全拓扑。

    发起旁路抄送业务员；
    部门审批（业务部门主管）→ 市场支持中心 → 总工（填设计审批）→
    设计审批1（填设计审批2）→ 设计审批2 → 业务反馈（业务员）→
    设计审批1.1 → 设计审批2.1 → 审批反馈（申请人/发起人）→
    旁路抄送相关人 → 结束。

    注：简道云导出里「业务反馈→设计审批1.1→2.1→审批反馈」为无条件边
    （界面画成旁路，实际每单都走）；CRM 按导出条件落地。
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
        _user_approval_node("approval_market", "市场支持中心", u["market_support"]),
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
        {"id": "r_dept_market", "source": "approval_dept", "target": "approval_market"},
        {"id": "r_market_chief", "source": "approval_market", "target": "approval_chief"},
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
    "部门审批 → 市场支持中心 → 总工填设计审批 → 设计审批1/2 → "
    "业务反馈 → 设计审批1.1/2.1 → 审批反馈；旁路抄送相关人后结束。"
    "可在流程管理中继续改。"
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


_LEAD_INTEL_FIELD_PERMS = _fp(
    ("customer_newness", "required"),
    ("reject_reason", "editable"),
    ("assess_remark", "editable"),
)


async def _upgrade_lead_intel_field_perms_if_needed(
    db, tenant_id: str, d: WfProcessDefinition,
) -> None:
    """给线索情报审批节点补齐「本节点可填写字段」（不改审批人，尊重租户已配指定人）。

    字段顺序对齐简道云：新/老 → 回退原因 → 备注2 → 操作意见（最终状态由情报表单承担）。
    """
    if d.code != "SYS_LEAD_REVIEW":
        return
    if d.category and d.category != SYSTEM_DEFAULT_CATEGORY:
        return
    version = await _published_version(db, tenant_id, d.id)
    if not version:
        return
    nodes = list(version.node_definitions or [])
    approvals = [n for n in nodes if isinstance(n, dict) and n.get("type") == "approval"]
    if len(approvals) != 1:
        return
    ap = approvals[0]
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
        and not (
            form_code == "install_drawing_notice"
            and _flow_missing_biz_score_perms(version.node_definitions)
        )
        # 条件被清成 null 后互斥组多 else：节点拓扑仍「对齐」，但连线已坏，须整图重发
        and not _flow_exclusive_group_multi_blank(version.route_definitions)
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
    # 仅缺互斥组：在现有 CRM 条件上补 exclusive_group，避免用生成图覆盖已 remap 的部门/人员
    if topology_ok and _flow_missing_exclusive_groups(version.route_definitions):
        patched = [dict(r) if isinstance(r, dict) else r for r in (version.route_definitions or [])]
        by_src: dict[str, list] = {}
        for r in patched:
            if not isinstance(r, dict) or r.get("always"):
                continue
            src = str(r.get("source") or "")
            if src:
                by_src.setdefault(src, []).append(r)
        for src, outs in by_src.items():
            if len(outs) < 2:
                continue
            if _source_is_jdy_parallel_fork(outs):
                continue
            gid = f"ex_{src}"
            for r in outs:
                r["exclusive_group"] = gid
        await _publish_system_default_upgrade(
            db, tenant_id, d, version,
            version.node_definitions, patched,
            DRAWING_FORM_FLOW_DESC, f"补同源互斥组({form_code})",
        )
        return
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
    )


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
    await db.commit()
    logger.info(
        "已升级系统兜底流程 %s(tenant=%s) → v%s：%s（废弃草稿 %s 条）",
        d.code, tenant_id, next_ver, log_tag, len(drafts),
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


async def _upgrade_contract_review_jdy_if_needed(
    db, tenant_id: str, d: WfProcessDefinition,
) -> None:
    """系统兜底合同评审流：单节点等升级为简道云会签主干。"""
    if d.category and d.category != SYSTEM_DEFAULT_CATEGORY:
        return
    if d.biz_type != "contract_review":
        return
    version = await _published_version(db, tenant_id, d.id)
    if not version:
        return
    if _flow_is_jdy_contract_review(version.node_definitions, version.route_definitions):
        return

    new_nodes, new_routes = _contract_review_flow_graph()
    await _publish_system_default_upgrade(
        db, tenant_id, d, version, new_nodes, new_routes,
        CONTRACT_REVIEW_DEFAULT_DESC, "简道云评审会签流(旁路抄送/反馈回路)",
    )


def _flow_is_tech_agreement_jdy(nodes: list | None) -> bool:
    """是否已是简道云技术协议全拓扑（含市场支持 / 业务反馈 / 1.1·2.1）。"""
    names = {
        n.get("name") for n in (nodes or [])
        if isinstance(n, dict) and n.get("type") in ("approval", "cc")
    }
    required = {
        "抄送业务员", "部门审批", "市场支持中心", "总工审批",
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
    """系统兜底技术协议流：精简版/单节点升级为简道云全拓扑。"""
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
        TECH_AGREEMENT_DEFAULT_DESC, "简道云技术协议评审(全拓扑)",
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
        rule = approvals[0].get("approver_rule") or {"type": "specified_role", "value": "lead_intel"}
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
        d.id, version, user, biz_type=biz_type, biz_id=biz_id, title=title, form_data=ctx or {},
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


async def list_todo(db, tenant_id, user_id, page_no, page_size, biz_type=None, biz_id=None):
    """我的待办。biz_type/biz_id 可选，用于业务详情页精确查「这单是否轮到我审」——
    否则调用方只能拉一页待办再在前端过滤，待办多时会漏掉。"""
    # 待办 = 本人被指派 + 本人作为「有效代理人」代办的委托人任务
    principals = await active_principals(db, tenant_id, user_id)
    assignees = [user_id, *principals]
    conds = [WfTaskInstance.tenant_id == tenant_id, WfTaskInstance.assignee_id.in_(assignees),
             WfTaskInstance.status == "pending"]
    if biz_type or biz_id:
        inst_q = select(WfProcessInstance.id).where(WfProcessInstance.tenant_id == tenant_id)
        if biz_type:
            inst_q = inst_q.where(WfProcessInstance.biz_type == biz_type)
        if biz_id:
            inst_q = inst_q.where(WfProcessInstance.biz_id == biz_id)
        conds.append(WfTaskInstance.process_instance_id.in_(inst_q))
    total = (await db.execute(select(func.count()).select_from(WfTaskInstance).where(*conds))).scalar_one()
    tasks = (await db.execute(select(WfTaskInstance).where(*conds)
             .order_by(WfTaskInstance.created_at.desc())
             .offset((page_no - 1) * page_size).limit(page_size))).scalars().all()
    return await _enrich_tasks(db, list(tasks), viewer_id=user_id), total


async def list_done(db, tenant_id, user_id, page_no, page_size):
    conds = [WfTaskInstance.tenant_id == tenant_id, WfTaskInstance.assignee_id == user_id,
             WfTaskInstance.status.in_(["approved", "rejected", "transferred", "returned"])]
    total = (await db.execute(select(func.count()).select_from(WfTaskInstance).where(*conds))).scalar_one()
    tasks = (await db.execute(select(WfTaskInstance).where(*conds)
             .order_by(WfTaskInstance.action_at.desc())
             .offset((page_no - 1) * page_size).limit(page_size))).scalars().all()
    return await _enrich_tasks(db, list(tasks)), total


async def list_initiated(db, tenant_id, user_id, page_no, page_size):
    conds = [WfProcessInstance.tenant_id == tenant_id, WfProcessInstance.initiator_id == user_id]
    total = (await db.execute(select(func.count()).select_from(WfProcessInstance).where(*conds))).scalar_one()
    rows = (await db.execute(select(WfProcessInstance).where(*conds)
            .order_by(WfProcessInstance.created_at.desc())
            .offset((page_no - 1) * page_size).limit(page_size))).scalars().all()
    return await _enrich_instances(db, list(rows)), total


async def list_cc(db, tenant_id, user_id, page_no, page_size):
    """抄送给我的流程。"""
    conds = [WfProcessCc.tenant_id == tenant_id, WfProcessCc.user_id == user_id]
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
        ni_rows = (await db.execute(
            select(WfNodeInstance.process_instance_id, WfNodeInstance.node_name).where(
                WfNodeInstance.process_instance_id.in_(running_ids),
                WfNodeInstance.status == "running",
                WfNodeInstance.node_type == "approval",
            )
        )).all()
        for pid, name in ni_rows:
            if pid not in current_node and name:
                current_node[pid] = name
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
    out = []
    for i in rows:
        d = _inst_dict(i)
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

    # 列表路径不再为补标题去读 FormInstance（含大 JSON）；空标题用流程名 / 单号兜底
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


def _inst_dict(i: WfProcessInstance) -> dict:
    return {
        "id": i.id, "title": i.title, "business_no": i.business_no, "status": i.status,
        "initiator_id": i.initiator_id, "form_instance_id": i.form_instance_id,
        "biz_type": i.biz_type, "biz_id": i.biz_id,
        "started_at": i.started_at.isoformat() if i.started_at else None,
        "completed_at": i.completed_at.isoformat() if i.completed_at else None,
        "created_at": i.created_at.isoformat() if i.created_at else None,
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
    """按节点实例构造「流程动态」(对齐简道云右侧时间线)。"""
    from app.domains.auth.models import User

    # 最新在前
    nodes_sorted = sorted(
        nodes,
        key=lambda n: n.started_at or n.created_at or _now(),
        reverse=True,
    )
    by_node: dict[str, list] = {}
    for t in tasks:
        by_node.setdefault(t.node_instance_id, []).append(t)
    last_log: dict[str, object] = {}
    for l in logs:
        if l.node_instance_id:
            last_log[l.node_instance_id] = l

    uid_set: set[str] = set()
    for t in tasks:
        if t.assignee_id:
            uid_set.add(t.assignee_id)
    for l in logs:
        if l.actor_id:
            uid_set.add(l.actor_id)

    # 抄送节点：从 wf_process_cc 取被抄送人（无审批任务，原先流程动态看不到人）
    cc_node_ids = [n.id for n in nodes_sorted if getattr(n, "node_type", None) == "cc"]
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
        "pending": "待处理", "rejected": "已驳回",
    }
    out = []
    for n in nodes_sorted:
        if n.node_type in ("parallel", "merge"):
            continue
        nt = by_node.get(n.id) or []
        assignees = []
        seen: set[str] = set()
        for t in nt:
            if t.assignee_id and t.assignee_id not in seen:
                seen.add(t.assignee_id)
                assignees.append({
                    "id": t.assignee_id,
                    "name": name_map.get(t.assignee_id, t.assignee_id),
                    "status": t.status,
                })
        lg = last_log.get(n.id)
        action = getattr(lg, "action", None) if lg else None
        actor_name = getattr(lg, "actor_name", None) if lg else None
        opinion = getattr(lg, "opinion", None) if lg else None
        # 历史数据兼容：旧版驳回未关闭节点，仍为 running，但操作已是驳回 / 流程已结束
        display_status = n.status
        if display_status == "running":
            if action in ("reject", "auto_reject") or process_status == "rejected":
                display_status = "rejected"
            elif process_status == "withdrawn":
                display_status = "cancelled"
            elif process_status == "completed":
                # 旁路抄送误触 end 等历史数据：流程已结束但节点未关
                display_status = "cancelled"
        if display_status == "running" and not actor_name and assignees:
            pending_names = [a["name"] for a in assignees if a["status"] == "pending"]
            actor_name = "、".join(pending_names) if pending_names else "、".join(a["name"] for a in assignees)
            action = action or "pending"
        # 抄送节点：被抄送人放 assignees，供「查看抄送详情」；处理人显示为系统
        if n.node_type == "cc":
            cc_uids = cc_by_node.get(n.id) or []
            uniq: list[str] = []
            for uid in cc_uids:
                if uid not in uniq:
                    uniq.append(uid)
            if uniq:
                assignees = [
                    {"id": uid, "name": name_map.get(uid, uid), "status": "completed"}
                    for uid in uniq
                ]
            actor_name = actor_name or "系统"
            action = action or "cc"
        end_at = n.completed_at or (getattr(lg, "created_at", None) if lg else None)
        out.append({
            "node_instance_id": n.id,
            "node_def_id": n.node_def_id,
            "node_name": n.node_name,
            "node_type": n.node_type,
            "status": display_status,
            "status_text": status_text.get(display_status, display_status),
            "assignees": assignees,
            "handler_name": actor_name,
            "action": action,
            "opinion": opinion,
            "started_at": n.started_at.isoformat() if n.started_at else None,
            "completed_at": n.completed_at.isoformat() if n.completed_at else None,
            "duration": _fmt_duration(n.started_at, end_at),
            "is_current": display_status == "running",
        })
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
    inst = (await db.execute(
        select(WfProcessInstance).where(
            WfProcessInstance.tenant_id == tenant_id,
            WfProcessInstance.form_instance_id == form_instance_id,
        ).order_by(WfProcessInstance.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    if not inst:
        return None
    return await get_instance_detail(db, tenant_id, inst.id, viewer_id=viewer_id)


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

    # 表单流历史数据可能没写 title：从关联表单/流程名补齐展示（并回写）
    if not (inst.title or "").strip():
        healed = None
        if inst.form_instance_id:
            try:
                from app.domains.lowcode.models import FormInstance, FormTemplate
                from app.domains.lowcode.service import derive_form_instance_title
                fi = await db.get(FormInstance, inst.form_instance_id)
                if fi:
                    tpl = await db.get(FormTemplate, fi.template_id) if fi.template_id else None
                    healed = derive_form_instance_title(
                        (tpl.name if tpl else None) or process_name,
                        fi.form_data if isinstance(fi.form_data, dict) else {},
                        fi.field_definitions,
                    )
                    if healed and not (fi.title or "").strip():
                        fi.title = healed
            except Exception:
                healed = None
        if not healed:
            healed = process_name
        if healed:
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
    if inst.form_instance_id:
        try:
            from app.domains.lowcode.models import FormInstance, FormTemplateVersion
            from app.domains.lowcode.service import get_published_version
            fi = await db.get(FormInstance, inst.form_instance_id)
            if fi and not getattr(fi, "is_deleted", False):
                form_fields = list(fi.field_definitions or [])
                form_data = dict(fi.form_data or {}) if isinstance(fi.form_data, dict) else {}
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
    if inst.started_at:
        from app.domains.auth.models import User
        iname = None
        if inst.initiator_id:
            u = (await db.execute(
                select(User.real_name, User.username).where(User.id == inst.initiator_id)
            )).first()
            if u:
                iname = u[0] or u[1]
        flow_steps.append({
            "node_instance_id": f"start:{inst.id}",
            "node_def_id": "start",
            "node_name": "流程发起",
            "node_type": "start",
            "status": "completed",
            "status_text": "已完成",
            "assignees": [],
            "handler_name": iname,
            "action": "submit",
            "opinion": None,
            "started_at": inst.started_at.isoformat(),
            "completed_at": inst.started_at.isoformat(),
            "duration": "1秒",
            "is_current": False,
        })

    # 轨迹补充节点名
    ni_name = {n.id: n.node_name for n in nodes}
    return {
        **_inst_dict(inst),
        "process_name": process_name,
        "approval_nodes": approval_nodes,
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
    allow_revise = inst.status in ("withdrawn", "rejected")
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
                    latest_req = {
                        p["field"] for p in parse_field_perms(latest_node)
                        if p.get("access") == "required"
                    }
                    if latest_req:
                        field_perms = [
                            {**p, "access": "required"} if p.get("field") in latest_req else p
                            for p in field_perms
                        ]
        except Exception:
            pass

    field_ids = [p["field"] for p in field_perms]
    catalog = {f["id"]: f for f in get_catalog(inst.biz_type or "")}
    published_by_id: dict = {}
    if inst.form_instance_id:
        from app.domains.lowcode.models import FormInstance
        fi = await db.get(FormInstance, inst.form_instance_id)
        form_defs = []
        if fi and fi.tenant_id == tenant_id:
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
        # 修订待办：整单可编辑，返回全部表单字段
        if is_revise and form_defs:
            field_ids = [fd["id"] for fd in form_defs if isinstance(fd, dict) and fd.get("id")]
            field_perms = [{"field": fid, "access": "editable"} for fid in field_ids]

    field_meta = []
    for fid in field_ids:
        meta = dict(catalog.get(fid) or {"id": fid, "label": fid, "type": "text"})
        pub = published_by_id.get(fid)
        if isinstance(pub, dict):
            if pub.get("type"):
                meta["type"] = pub["type"]
            pub_props = pub.get("props") if isinstance(pub.get("props"), dict) else {}
            if pub_props.get("pickable_scope"):
                props = dict(meta.get("props") or {})
                props["pickable_scope"] = pub_props["pickable_scope"]
                meta["props"] = props
        if fid in ("design_assignees", "designer"):
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
        "field_meta": field_meta,
        "field_values": field_values,
    }
