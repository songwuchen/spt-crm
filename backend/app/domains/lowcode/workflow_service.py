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


async def _published_version(db, tenant_id, def_id) -> WfProcessDefinitionVersion | None:
    return (await db.execute(select(WfProcessDefinitionVersion).where(
        WfProcessDefinitionVersion.tenant_id == tenant_id,
        WfProcessDefinitionVersion.process_definition_id == def_id,
        WfProcessDefinitionVersion.status == "published",
    ).order_by(WfProcessDefinitionVersion.version_number.desc()).limit(1))).scalar_one_or_none()


async def save_design(db, tenant_id, def_id, data: ws.WfSaveDesign, user_id) -> WfProcessDefinitionVersion:
    await get_definition(db, tenant_id, def_id)
    latest = await _latest_version(db, tenant_id, def_id)
    if latest and latest.status == "draft":
        latest.node_definitions = data.node_definitions
        latest.route_definitions = data.route_definitions
        latest.approver_rules = data.approver_rules
        await db.commit()
        await db.refresh(latest)
        return latest
    v = WfProcessDefinitionVersion(
        id=generate_uuid(), tenant_id=tenant_id, process_definition_id=def_id,
        version_number=(latest.version_number + 1) if latest else 1,
        node_definitions=data.node_definitions, route_definitions=data.route_definitions,
        approver_rules=data.approver_rules, status="draft",
    )
    db.add(v)
    await db.commit()
    await db.refresh(v)
    return v


async def publish(db, tenant_id, def_id, user_id) -> WfProcessDefinitionVersion:
    d = await get_definition(db, tenant_id, def_id)
    latest = await _latest_version(db, tenant_id, def_id)
    if not latest or latest.status != "draft":
        raise BusinessException(code=BUSINESS_ERROR, message="没有可发布的草稿版本")
    # 基本校验: 必须有 start 与 end，且至少有一个审批节点（避免 start→end 空流程免审）
    types = {n.get("type") for n in (latest.node_definitions or [])}
    if "start" not in types or "end" not in types:
        raise BusinessException(code=BUSINESS_ERROR, message="流程必须包含开始与结束节点")
    if "approval" not in types:
        raise BusinessException(code=BUSINESS_ERROR, message="流程至少包含一个审批节点")
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
    return await _latest_version(db, tenant_id, def_id)


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
    engine = WorkflowEngine(db, tenant_id)
    # 注意: 引擎内部会 commit;此处不额外 commit(调用方 create_instance 已在 flush 后)
    return await engine.submit(
        d.id, version, user, form_instance_id=form_instance.id,
        form_data=form_data, title=form_instance.title,
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
        "biz_type": "lead",
        "code": "SYS_LEAD_REVIEW",
        "name": "线索审核",
        "approver_rule": {"type": "specified_role", "value": "lead_intel", "exclude_initiator": True},
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
]

DRAWING_FORM_FLOW_DESC = (
    "对齐简道云通用流程拓扑（具名审批人/角色在 CRM 无对应用户时 empty_strategy=auto_approve；"
    "详见 docs/product/_jdy_drawing_forms.md）"
)


def _drawing_flow_graph(form_code: str) -> tuple[list[dict], list[dict]] | None:
    try:
        from app.domains.lowcode._drawing_jdy_generated import DRAWING_JDY
    except Exception:
        return None
    pack = DRAWING_JDY.get(form_code)
    if not pack:
        return None
    nodes = pack.get("flow_nodes") or []
    routes = pack.get("flow_routes") or []
    if not nodes:
        return None
    return nodes, routes


def _flow_is_jdy_drawing(nodes: list | None) -> bool:
    """已对齐简道云图纸流：含总工/图纸领取等关键节点名。"""
    names = {n.get("name") for n in (nodes or [])}
    return "总工审批" in names and ("图纸领取" in names or "设计指派安排" in names)


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
            # 对齐简道云 optAuth=3：财务可改合同类型、验收方式
            field_perms=_fp(
                ("contract_type", "editable"),
                ("accept_method", "editable"),
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


def _default_flow_graph(
    name: str, approver_rule: dict, multi_mode: str, empty_strategy: str,
    *, with_owner_cc: bool = False,
) -> tuple[list[dict], list[dict]]:
    """系统兜底流程节点图。with_owner_cc=True 时在审批后抄送「表单人员字段=owner_id」。"""
    nodes: list[dict] = [
        {"id": "start", "type": "start", "name": "发起"},
        {"id": "approval_1", "type": "approval", "name": name,
         "approver_rule": approver_rule, "multi_mode": multi_mode,
         "empty_strategy": empty_strategy},
    ]
    routes: list[dict] = [
        {"id": "r_start", "source": "start", "target": "approval_1"},
    ]
    if with_owner_cc:
        nodes.append({
            "id": "cc_owner", "type": "cc", "name": "通知业务员确认转化",
            "approver_rule": {"type": "form_field_person", "value": "owner_id"},
        })
        nodes.append({"id": "end", "type": "end", "name": "结束"})
        routes.append({"id": "r_cc", "source": "approval_1", "target": "cc_owner"})
        routes.append({"id": "r_end", "source": "cc_owner", "target": "end"})
    else:
        nodes.append({"id": "end", "type": "end", "name": "结束"})
        routes.append({"id": "r_end", "source": "approval_1", "target": "end"})
    return nodes, routes


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
    """系统兜底图纸表单流：单节点等升级为简道云对齐拓扑。"""
    if not form_code:
        return
    if d.category and d.category != SYSTEM_DEFAULT_CATEGORY:
        return
    if d.code not in ("SYS_DRAWING_REQUISITION", "SYS_INSTALL_DRAWING_NOTICE"):
        return
    graph = _drawing_flow_graph(form_code)
    if not graph:
        return
    version = await _published_version(db, tenant_id, d.id)
    if not version:
        return
    if _flow_is_jdy_drawing(version.node_definitions):
        return
    new_nodes, new_routes = graph
    if form_code == "drawing_requisition":
        d.name = "合同图纸（资料）领用申请"
    elif form_code == "install_drawing_notice":
        d.name = "安装图设计通知"
    await _publish_system_default_upgrade(
        db, tenant_id, d, version, new_nodes, new_routes,
        DRAWING_FORM_FLOW_DESC, f"简道云图纸流({form_code})",
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
    for n in nodes or []:
        if n.get("type") != "cc":
            continue
        rule = n.get("approver_rule") or (n.get("config") or {}).get("approver_rule") or {}
        if rule.get("type") == "form_field_person" and rule.get("value") == "owner_id":
            return True
        if n.get("id") == "cc_owner":
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
            fin_fields = {p.get("field") for p in fps if isinstance(p, dict)}
            finance_fp_ok = {"contract_type", "accept_method"} <= fin_fields
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
    d.description = description
    # 同步展示名（若仍是旧系统名）
    if d.biz_type == "contract_version" and (not d.name or "法务" in (d.name or "") or "签署前" in (d.name or "")):
        d.name = "合同登记审批（运营）"
    if d.biz_type == "contract_review" and (not d.name or d.name == "合同评审审批"):
        d.name = "合同评审会签"
    await db.commit()
    logger.info(
        "已升级系统兜底流程 %s(tenant=%s) → v%s：%s",
        d.code, tenant_id, next_ver, log_tag,
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


async def _upgrade_default_owner_cc_if_needed(
    db, tenant_id: str, d: WfProcessDefinition, name: str,
    approver_rule: dict, multi_mode: str, empty_strategy: str,
) -> None:
    """系统兜底线索流补齐「审批通过 → 抄送负责人」。

    - 仍是 start→审批→结束：发布含抄送节点的新版本
    - 已有唯一抄送但指向发起人(creator)等占位规则：改为表单人员字段 owner_id
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
                if not nn.get("name") or nn.get("name") in ("抄送", "CC"):
                    nn["name"] = "通知业务员确认转化"
                nn["approver_rule"] = {"type": "form_field_person", "value": "owner_id"}
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
    out = []
    for c in ccs:
        inst = insts.get(c.process_instance_id)
        biz_ref_id = None
        if inst:
            if inst.biz_type == "contract_version" and inst.biz_id:
                biz_ref_id = cv_map.get(inst.biz_id)
            elif inst.biz_type == "contract_review":
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
            "initiator_id": inst.initiator_id if inst else None,
            "initiator_name": name_map.get(inst.initiator_id) if inst and inst.initiator_id else None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return out, total


async def _enrich_instances(db, rows: list[WfProcessInstance]) -> list[dict]:
    """列表补充：合同 biz_ref_id、进行中当前节点名。"""
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
    out = []
    for i in rows:
        d = _inst_dict(i)
        if i.biz_type == "contract_version" and i.biz_id:
            d["biz_ref_id"] = cv_map.get(i.biz_id)
        elif i.biz_type == "contract_review":
            d["biz_ref_id"] = i.biz_id
        else:
            d["biz_ref_id"] = None
        d["current_node_name"] = current_node.get(i.id)
        out.append(d)
    return out


async def _enrich_tasks(db, tasks: list[WfTaskInstance], viewer_id: str | None = None) -> list[dict]:
    # 若含代办任务，批量解析委托人姓名用于「代 XX 审批」标注
    principal_ids = {t.assignee_id for t in tasks if viewer_id and t.assignee_id != viewer_id}
    insts = {}
    for t in tasks:
        if t.process_instance_id not in insts:
            insts[t.process_instance_id] = await db.get(WfProcessInstance, t.process_instance_id)
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
    if node_ids:
        ni_rows = (await db.execute(
            select(WfNodeInstance.id, WfNodeInstance.node_name).where(WfNodeInstance.id.in_(node_ids))
        )).all()
        node_name_map = {r[0]: (r[1] or "审批") for r in ni_rows}

    out = []
    for t in tasks:
        inst = insts.get(t.process_instance_id)
        on_behalf = viewer_id is not None and t.assignee_id != viewer_id
        biz_ref_id = None
        if inst:
            if inst.biz_type == "contract_version" and inst.biz_id:
                biz_ref_id = cv_contract_map.get(inst.biz_id)
            elif inst.biz_type == "contract_review":
                biz_ref_id = inst.biz_id
        out.append({
            "task_id": t.id, "status": t.status, "opinion": t.opinion,
            "process_instance_id": t.process_instance_id,
            "title": inst.title if inst else None,
            "business_no": inst.business_no if inst else None,
            "initiator_id": inst.initiator_id if inst else None,
            "initiator_name": name_map.get(inst.initiator_id) if inst else None,
            "process_status": inst.status if inst else None,
            "node_name": node_name_map.get(t.node_instance_id) if t.node_instance_id else None,
            # 承载的业务单据：调用方据此把待办关联回业务详情页(如线索详情页的内联审批卡)
            "biz_type": inst.biz_type if inst else None,
            "biz_id": inst.biz_id if inst else None,
            "biz_ref_id": biz_ref_id,
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


async def _build_flow_steps(db, nodes: list, tasks: list, logs: list) -> list[dict]:
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
    name_map: dict[str, str] = {}
    if uid_set:
        rows = (await db.execute(
            select(User.id, User.real_name, User.username).where(User.id.in_(uid_set))
        )).all()
        name_map = {r[0]: (r[1] or r[2] or r[0]) for r in rows}

    status_text = {
        "running": "处理中", "completed": "已完成", "cancelled": "已取消",
        "pending": "待处理",
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
        if n.status == "running" and not actor_name and assignees:
            pending_names = [a["name"] for a in assignees if a["status"] == "pending"]
            actor_name = "、".join(pending_names) if pending_names else "、".join(a["name"] for a in assignees)
            action = action or "pending"
        end_at = n.completed_at or (getattr(lg, "created_at", None) if lg else None)
        out.append({
            "node_instance_id": n.id,
            "node_def_id": n.node_def_id,
            "node_name": n.node_name,
            "node_type": n.node_type,
            "status": n.status,
            "status_text": status_text.get(n.status, n.status),
            "assignees": assignees,
            "handler_name": actor_name,
            "action": action,
            "opinion": opinion,
            "started_at": n.started_at.isoformat() if n.started_at else None,
            "completed_at": n.completed_at.isoformat() if n.completed_at else None,
            "duration": _fmt_duration(n.started_at, end_at),
            "is_current": n.status == "running",
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
        {"id": n.get("id"), "name": n.get("name") or "审批"}
        for n in (version.node_definitions if version else []) if n.get("type") == "approval"
    ]
    # 业务单据审批（线索/报价等）没有 form_instance：把业务关键字段塞进 biz_detail，
    # 供审批中心抽屉展示；否则审批人只能看到「无关联表单」。
    biz_detail: dict = {}
    biz_ref_id = None
    if inst.biz_type and inst.biz_id:
        try:
            from app.domains.approval.service import _resolve_biz_detail
            biz_detail = await _resolve_biz_detail(db, tenant_id, inst.biz_type, inst.biz_id) or {}
        except Exception:
            biz_detail = {}
        if inst.biz_type == "contract_review":
            biz_ref_id = inst.biz_id
        elif inst.biz_type == "contract_version":
            try:
                from app.domains.contract.models import ContractVersion
                ver = await db.get(ContractVersion, inst.biz_id)
                if ver:
                    biz_ref_id = ver.contract_id
            except Exception:
                biz_ref_id = None

    current_task = await _resolve_current_task_for_viewer(
        db, tenant_id, inst, version, list(tasks), viewer_id, task_id=task_id,
    )
    nodes = (await db.execute(select(WfNodeInstance).where(
        WfNodeInstance.process_instance_id == instance_id,
    ))).scalars().all()
    flow_steps = await _build_flow_steps(db, list(nodes), list(tasks), list(logs))
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
        "approval_nodes": approval_nodes,
        "biz_detail": biz_detail,
        "biz_ref_id": biz_ref_id,
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
    """
    if not viewer_id or inst.status != "running":
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
    nodes = {n.get("id"): n for n in (version.node_definitions if version else [])}
    node = nodes.get(node_def_id or "") or {}
    field_perms = parse_field_perms(node)
    field_ids = [p["field"] for p in field_perms]
    catalog = {f["id"]: f for f in get_catalog(inst.biz_type or "")}
    field_meta = []
    for fid in field_ids:
        meta = catalog.get(fid) or {"id": fid, "label": fid, "type": "text"}
        item = {
            "id": fid,
            "label": meta.get("label") or fid,
            "type": meta.get("type") or "text",
        }
        if meta.get("options"):
            item["options"] = meta["options"]
        field_meta.append(item)
    field_values = await load_field_values(
        db, tenant_id, inst.biz_type, inst.biz_id, inst.form_instance_id, field_ids,
    )
    return {
        "task_id": pending.id,
        "node_id": node_def_id,
        "node_name": node.get("name") or "审批",
        "field_perms": field_perms,
        "opinion_required": bool(node.get("opinion_required")),
        "field_meta": field_meta,
        "field_values": field_values,
    }
