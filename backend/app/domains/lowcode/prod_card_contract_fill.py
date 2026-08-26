# -*- coding: utf-8 -*-
"""生产卡选合同后的字段带出（对齐简道云 linkDataMaps）。"""
from __future__ import annotations

from typing import Any


# 合同明细列 → 生产卡明细列
_LINE_COL_MAP = {
    "product_type": "product_type_2",
    "name": "product_name_3",
    "spec": "spec_model_3",
    "unit": "unit_3",
    "qty": "qty_3",
    "elec_ctrl": "electric_control",
    "standard": "tech_params_line",
    "line_remark": "field_3",
}


def _as_rows(key_clauses: Any) -> list[dict]:
    if isinstance(key_clauses, list):
        return [r for r in key_clauses if isinstance(r, dict)]
    if isinstance(key_clauses, dict):
        for k in ("rows", "items", "line_items", "data"):
            v = key_clauses.get(k)
            if isinstance(v, list):
                return [r for r in v if isinstance(r, dict)]
        # 有时整表就是 {0: {...}, 1: {...}}
        vals = list(key_clauses.values())
        if vals and all(isinstance(x, dict) for x in vals):
            return [x for x in vals if isinstance(x, dict)]
    return []


def map_contract_lines_to_prod_card(key_clauses: Any) -> list[dict]:
    out: list[dict] = []
    for row in _as_rows(key_clauses):
        mapped: dict[str, Any] = {}
        for src, dst in _LINE_COL_MAP.items():
            if src in row and row[src] not in (None, ""):
                mapped[dst] = row[src]
        if mapped:
            out.append(mapped)
    return out


def _fmt_delivery_date(raw: Any) -> str:
    if raw is None or raw == "":
        return ""
    return str(raw).strip()[:10]


def build_prod_card_fill_from_contract(
    *,
    contract_no: str | None,
    drawing_no: str | None,
    assignee_id: str | None,
    assignee_name: str | None,
    customer_name: str | None,
    delivery_date: str | None = None,
    registration_json: dict | None,
    key_clauses_json: Any,
    mode: str,
) -> dict[str, Any]:
    """mode: drawing_no_query | contract_no_select"""
    reg = registration_json if isinstance(registration_json, dict) else {}
    lines = map_contract_lines_to_prod_card(key_clauses_json)
    sales = assignee_id or None
    # 客户名：主数据优先；否则合同登记里的单位/客户名称
    unit = (customer_name or "").strip()
    if not unit:
        for key in ("customer_name", "company_name", "单位名称", "客户名称"):
            raw = reg.get(key)
            if raw is not None and str(raw).strip():
                unit = str(raw).strip()
                break
    delivery = _fmt_delivery_date(delivery_date) or _fmt_delivery_date(reg.get("delivery_date"))
    has_intel = str(reg.get("has_intelligence") or reg.get("has_smart") or "").strip()
    is_export = str(reg.get("is_export") or "").strip()

    if mode == "contract_no_select":
        # 简道云「合同号选择1」linkDataMaps：仅合同号 / 业务员 / 单位名称 / 评审流水号
        return {
            "yes_contract_no": contract_no or "",
            "yes_sales_person": sales,
            "yes_customer_name": unit,
            "contract_tech_review_sn": reg.get("review_sn") or "",
        }

    # drawing_no_query（非补充）：对齐简道云 linkfield 同区展示的关键信息
    return {
        "no_drawing_no": drawing_no or "",
        "no_sales_person": sales,
        "yes_customer_name": unit,
        "contract_delivery_date": delivery,
        "prod_card_line_items": lines,
        "tech_params": reg.get("tech_requirements") or "",
        "packaging_req": reg.get("packaging") or "",
        "remark_prod_card": reg.get("remark") or "",
        "paint_req": reg.get("paint_req") or "",
        "special_reminder": reg.get("special_note") or "",
        "no_warranty_period": reg.get("warranty_period") or "",
        "project_name": reg.get("project_name") or "",
        "has_intelligence": has_intel,
        "is_export_equipment": is_export,
        "contract_tech_review_sn": reg.get("review_sn") or "",
    }


def prod_card_fill_clear_keys(mode: str) -> list[str]:
    if mode == "contract_no_select":
        return [
            "yes_contract_no", "yes_sales_person", "yes_customer_name", "contract_tech_review_sn",
            "region_manager",
        ]
    return [
        "no_drawing_no", "no_sales_person", "yes_customer_name", "prod_card_line_items",
        "tech_params", "packaging_req", "remark_prod_card", "paint_req",
        "special_reminder", "no_warranty_period", "project_name",
        "contract_delivery_date", "has_intelligence", "is_export_equipment",
        "contract_tech_review_sn", "region_manager",
    ]


# 选合同带出字段：只作实时引用展示，不落库（合同变更后详情/审批同步变化）
PROD_CARD_CONTRACT_LIVE_KEYS: frozenset[str] = frozenset(
    prod_card_fill_clear_keys("drawing_no_query")
    + prod_card_fill_clear_keys("contract_no_select")
)


def strip_prod_card_contract_snapshot(form_data: dict | None) -> dict:
    """持久化前剔除选合同带出快照，只保留 drawing_no_query / contract_no_select 引用。"""
    data = dict(form_data or {})
    for k in PROD_CARD_CONTRACT_LIVE_KEYS:
        data.pop(k, None)
    return data


def resolve_prod_card_contract_pick(form_data: dict | None) -> tuple[str | None, str]:
    """返回 (contract_id, mode)。补充=是优先合同号选择，否则图纸号查询。"""
    fd = form_data if isinstance(form_data, dict) else {}
    is_supp = str(fd.get("is_supplement") or "").strip()
    yes_id = str(fd.get("contract_no_select") or "").strip() or None
    no_id = str(fd.get("drawing_no_query") or "").strip() or None
    if is_supp == "是" and yes_id:
        return yes_id, "contract_no_select"
    if no_id:
        return no_id, "drawing_no_query"
    if yes_id:
        return yes_id, "contract_no_select"
    return None, "drawing_no_query"


async def load_prod_card_fill_for_contract(
    db,
    tenant_id: str,
    contract_id: str,
    mode: str,
    user: dict | None = None,
) -> dict[str, Any]:
    """按合同当前版本实时组装带出字段（与 pickable API 同源）。"""
    from sqlalchemy import select
    from app.domains.contract.models import Contract, ContractVersion

    if mode not in ("drawing_no_query", "contract_no_select"):
        mode = "drawing_no_query"
    c = (
        await db.execute(
            select(Contract).where(Contract.id == contract_id, Contract.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not c:
        return {}
    ver = (
        await db.execute(
            select(ContractVersion).where(
                ContractVersion.tenant_id == tenant_id,
                ContractVersion.contract_id == contract_id,
                ContractVersion.version_no == c.current_version_no,
            )
        )
    ).scalar_one_or_none()
    if not ver:
        ver = (
            await db.execute(
                select(ContractVersion).where(
                    ContractVersion.tenant_id == tenant_id,
                    ContractVersion.contract_id == contract_id,
                ).order_by(ContractVersion.version_no.desc()).limit(1)
            )
        ).scalar_one_or_none()

    customer_name = None
    cust_id = c.customer_id
    if not cust_id and c.project_id:
        from app.domains.project.models import OpportunityProject
        cust_id = (
            await db.execute(
                select(OpportunityProject.customer_id).where(
                    OpportunityProject.id == c.project_id,
                    OpportunityProject.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
    if cust_id:
        from app.domains.customer.models import Customer
        cu = (
            await db.execute(
                select(Customer).where(Customer.id == cust_id, Customer.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if cu:
            customer_name = cu.name
        else:
            from app.common.list_enrich import customer_names_map
            customer_name = (await customer_names_map(db, tenant_id, [cust_id])).get(cust_id)

    fill = build_prod_card_fill_from_contract(
        contract_no=c.contract_no,
        drawing_no=c.drawing_no,
        assignee_id=c.assignee_id,
        assignee_name=c.assignee_name,
        customer_name=customer_name,
        delivery_date=str(c.delivery_date) if c.delivery_date else None,
        registration_json=c.registration_json if isinstance(c.registration_json, dict) else {},
        key_clauses_json=ver.key_clauses_json if ver else None,
        mode=mode,
    )
    return await enrich_prod_card_fill_with_region_manager(db, tenant_id, fill, user)


async def overlay_prod_card_contract_live(
    db,
    tenant_id: str,
    form_data: dict | None,
    user: dict | None = None,
) -> dict:
    """读时叠加热合同引用；无选合同时清空带出键，避免残留快照。"""
    data = dict(form_data or {})
    cid, mode = resolve_prod_card_contract_pick(data)
    live: dict[str, Any] = {}
    if cid:
        live = await load_prod_card_fill_for_contract(db, tenant_id, cid, mode, user)
    # 技术协议评审流水号：有选评审时以评审为准（也可后续改成实时）
    tar_id = str(data.get("select_contract_tech_review") or "").strip()
    if tar_id:
        from sqlalchemy import select
        from app.domains.tech_agreement_review.models import TechAgreementReview
        row = (
            await db.execute(
                select(TechAgreementReview.review_code).where(
                    TechAgreementReview.id == tar_id,
                    TechAgreementReview.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if row:
            live = {**live, **build_prod_card_fill_from_tar(review_code=str(row))}
    for k in PROD_CARD_CONTRACT_LIVE_KEYS:
        if k in live:
            data[k] = live[k]
        else:
            data.pop(k, None)
    return data


# CRM 生产卡流水号：固定「SCK」+ 5 位递增、不重置
PROD_CARD_SERIAL_PREFIX = "SCK"
PROD_CARD_SERIAL_NO_RULES: list[dict[str, Any]] = [
    {"type": "text", "value": PROD_CARD_SERIAL_PREFIX},
    {
        "type": "counter",
        "digits": 5,
        "fixed": True,
        "reset_period": "none",
        "initial_value": 1,
    },
]


def ensure_prod_card_serial_no_field(defs: list) -> None:
    """确保生产卡有流程编号 auto_number；无则插到字段列表最前。"""
    serial = None
    for f in defs:
        if isinstance(f, dict) and f.get("id") == "serial_no":
            serial = f
            break
    if serial is None:
        serial = {
            "id": "serial_no",
            "type": "auto_number",
            "label": "流程编号",
            "jdy_widget": "_widget_1617693684982",
        }
        defs.insert(0, serial)
    serial["type"] = "auto_number"
    serial["label"] = serial.get("label") or "流程编号"
    serial["form_editable"] = False
    serial["available_on_create"] = True
    serial["fill_stage"] = "initiator"
    serial["required"] = False
    props = dict(serial.get("props") or {})
    props["serial_rules"] = [dict(r) for r in PROD_CARD_SERIAL_NO_RULES]
    serial["props"] = props
    serial["description"] = (
        f"系统流水号：{PROD_CARD_SERIAL_PREFIX} + 5 位递增序号（不自动重置）。"
    )
    if not serial.get("jdy_widget"):
        serial["jdy_widget"] = "_widget_1617693684982"


# 选合同后自动带出、发起页不可手改的字段
_CONTRACT_PICK_READONLY_IDS = frozenset({
    "no_sales_person",
    "yes_sales_person",
    "no_drawing_no",
    "yes_contract_no",
    "yes_customer_name",
    "region_manager",
    "tech_params",
    "packaging_req",
    "remark_prod_card",
    "paint_req",
    "special_reminder",
    "no_warranty_period",
    "project_name",
    "prod_card_line_items",
    "contract_delivery_date",
    "has_intelligence",
    "is_export_equipment",
})

# 简道云 linkDataMaps：否=图纸编号查询（整块合同信息）；是=合同号选择（仅 4 项）
_PC_DRAWING_ONLY_FILL_FIELDS: tuple[str, ...] = (
    "no_drawing_no",
    "no_sales_person",
    "contract_delivery_date",
    "project_name",
    "packaging_req",
    "prod_card_line_items",
    "paint_req",
    "has_intelligence",
    "is_export_equipment",
    "no_warranty_period",
    "special_reminder",
    "tech_params",
    "remark_prod_card",
)
_PC_YES_ONLY_FILL_FIELDS: tuple[str, ...] = (
    "yes_contract_no",
    "yes_sales_person",
)
_PC_SHARED_CONTRACT_FILL_FIELDS: tuple[str, ...] = (
    "yes_customer_name",
    "region_manager",
)
_PC_DRAWING_CONTRACT_FILL_FIELDS: tuple[str, ...] = (
    *_PC_DRAWING_ONLY_FILL_FIELDS,
    *_PC_SHARED_CONTRACT_FILL_FIELDS,
)
_PC_YES_CONTRACT_FILL_FIELDS: tuple[str, ...] = (
    *_PC_YES_ONLY_FILL_FIELDS,
    *_PC_SHARED_CONTRACT_FILL_FIELDS,
)
# 简道云 linkfield 展示字段在 JDY 里 available_on_create=false；CRM 发起页选合同后需同区展示
_PROD_CARD_CONTRACT_FILL_ON_CREATE_IDS: frozenset[str] = frozenset({
    *_PC_DRAWING_ONLY_FILL_FIELDS,
    *_PC_YES_ONLY_FILL_FIELDS,
    *_PC_SHARED_CONTRACT_FILL_FIELDS,
    "contract_tech_review_sn",
})


def ensure_prod_card_contract_fill_on_create(defs: list) -> None:
    """选合同带出字段在发起页可见（只读），对齐简道云选完合同后同区展示。"""
    for f in defs:
        if not isinstance(f, dict):
            continue
        fid = f.get("id")
        if fid not in _PROD_CARD_CONTRACT_FILL_ON_CREATE_IDS:
            continue
        f["available_on_create"] = True
        f["fill_stage"] = "initiator"
        f["form_editable"] = False
_PC_CONTRACT_FILL_VIS_RULE_IDS = frozenset(
    [f"crm_vis_pc_contract_fill_{fid}" for fid in _PC_DRAWING_CONTRACT_FILL_FIELDS]
    + [f"crm_vis_pc_yes_contract_fill_{fid}" for fid in _PC_YES_CONTRACT_FILL_FIELDS]
    + ["crm_vis_pc_contract_fill_shared_yes_customer_name", "crm_vis_pc_contract_fill_shared_region_manager"]
)
_PC_CONTRACT_DISPLAY_FIELD_DEFS: tuple[dict[str, Any], ...] = (
    {"id": "contract_delivery_date", "type": "text", "label": "合同交货期"},
    {"id": "has_intelligence", "type": "text", "label": "是否含智能化"},
    {"id": "is_export_equipment", "type": "text", "label": "设备是否出口"},
)


def ensure_prod_card_contract_display_fields(defs: list) -> None:
    """补齐简道云 linkfield 同区展示字段（合同交货期 / 智能化 / 出口）。"""
    by_id = {f.get("id") for f in defs if isinstance(f, dict)}
    anchor = next(
        (i for i, f in enumerate(defs) if isinstance(f, dict) and f.get("id") == "no_drawing_no"),
        next((i for i, f in enumerate(defs) if isinstance(f, dict) and f.get("id") == "drawing_no_query"), len(defs)),
    )
    offset = 0
    for extra in _PC_CONTRACT_DISPLAY_FIELD_DEFS:
        if extra["id"] in by_id:
            continue
        defs.insert(anchor + 1 + offset, {
            **extra,
            "available_on_create": True,
            "fill_stage": "initiator",
        })
        offset += 1


def apply_prod_card_contract_pick_fields(defs: list) -> None:
    """把图纸编号查询/合同号选择改为 contract 类型，并挂部门过滤 + 带出模式。

    同时默认「是否为补充」=否：显隐规则在未选时会把两个选合同字段都藏掉，
    新建打开时必须能立刻看到合同下拉。
    提交人 / 所在部门默认当前用户与当前部门。
    「确认协议 / 设计指派填写」仅审批节点可见（对齐简道云，不在发起页展示）。
    补齐流程编号（SCK + 五位不重置；生成器曾跳过 sn 类型）。
    """
    ensure_prod_card_serial_no_field(defs)
    ensure_prod_card_contract_display_fields(defs)
    for f in defs:
        if not isinstance(f, dict):
            continue
        fid = f.get("id")
        if fid == "is_supplement":
            # 未选时两边合同字段均隐藏；默认否 → 显示「图纸编号查询」合同选择
            f["default_value"] = "否"
        elif fid == "submitter":
            props = dict(f.get("props") or {})
            props["default_current_user"] = True
            f["props"] = props
        elif fid == "department":
            props = dict(f.get("props") or {})
            props["default_current_dept"] = True
            f["props"] = props
        elif fid == "drawing_no_query":
            f["type"] = "contract"
            f["label"] = "选择合同"
            f["description"] = "从合同管理选择（对齐简道云图纸编号查询）；按所在部门过滤；选中后实时引用合同单位/图纸号/明细等（合同变更后同步）。"
            props = dict(f.get("props") or {})
            props["filter_by_department_field"] = "department"
            props["contract_fill"] = "drawing_no_query"
            f["props"] = props
        elif fid == "contract_no_select":
            f["type"] = "contract"
            f["label"] = "选择合同（合同号）"
            f["description"] = "从合同管理选择；按所在部门过滤；选中后实时引用合同号/单位名称/业务员（合同变更后同步）。"
            props = dict(f.get("props") or {})
            props["filter_by_department_field"] = "department"
            props["contract_fill"] = "contract_no_select"
            f["props"] = props
        elif fid == "yes_customer_name":
            f["label"] = "单位名称"
            f["form_editable"] = False
            props = dict(f.get("props") or {})
            props.pop("readonly", None)
            f["props"] = props
            f["description"] = f.get("description") or "实时引用所选合同，不可手改。"
        elif fid == "yes_contract_no":
            f["form_editable"] = False
            f["description"] = f.get("description") or "实时引用所选合同，不可手改。"
        elif fid == "yes_sales_person":
            f["label"] = f.get("label") or "（是）业务人员"
            f["form_editable"] = False
            f["description"] = "实时引用所选合同业务员；如有不符请及时反馈。"
        elif fid == "no_drawing_no":
            f["label"] = "图纸编号"
            f["form_editable"] = False
            f["description"] = f.get("description") or "实时引用所选合同，不可手改。"
        elif fid == "no_sales_person":
            f["label"] = "业务人员"
            f["form_editable"] = False
            f["description"] = "实时引用所选合同业务员；如有不符请及时反馈。"
        elif fid in _CONTRACT_PICK_READONLY_IDS:
            f["description"] = f.get("description") or "实时引用所选合同，不可手改。"
        elif fid == "select_contract_tech_review":
            # 简道云 linkfield → 技术协议评审；选中后带出流水号（linkDataMaps）
            f["type"] = "tech_agreement_review"
            f["label"] = "选择合同技术协议评审"
            f["description"] = (
                "从技术协议评审中选择（申请人=提交人或业务部门=所在部门）；"
                "选中后自动带出流水号。"
            )
            props = dict(f.get("props") or {})
            props["filter_by_submitter_field"] = "submitter"
            props["filter_by_department_field"] = "department"
            props["tar_fill"] = "prod_card_sn"
            f["props"] = props
        elif fid == "contract_tech_review_sn":
            props = dict(f.get("props") or {})
            props["readonly"] = True
            f["props"] = props
            f["description"] = f.get("description") or "实时引用所选合同/技术协议评审，不可手改。"
        elif fid == "field" and "合并含补充" in str(f.get("label") or ""):
            # 简道云：text + rely 联动回填，用户仍可手改（非 formula 只读）
            f["type"] = "text"
            f["form_editable"] = True
            f["props"] = {
                **dict(f.get("props") or {}),
                "suggest_formula": "IF($is_supplement#=='是','补充',$order_type#)",
            }
            f["description"] = (
                f.get("description")
                or "默认随「是否补充/下单类型」联动；可手动修改。"
            )
        elif fid == "order_datetime":
            props = dict(f.get("props") or {})
            props.setdefault("show_time", False)
            props.setdefault("date_only", True)
            props["default_today_on_approve"] = True
            f["props"] = props

    apply_prod_card_std_room_detail_defaults(defs)
    apply_prod_card_prune_std_room_columns(defs)
    apply_prod_card_approver_only_fields(defs)
    apply_prod_card_legacy_hidden_fields(defs)
    apply_prod_card_detail_quick_fill_flags(defs)
    ensure_prod_card_contract_fill_on_create(defs)
    apply_prod_card_install_pick_fields(defs)


# 圈选区：仅审批可填（创建页隐藏）；字段级必填下沉到节点 field_perms
# 业务员确认：是否同意按协议/方案执行
_PROD_CARD_SALES_CONFIRM_PERMS: dict[str, str] = {
    "confirm_agreement": "required",
}
# 研管办安排：设计指派填写（对齐简道云 安排设计1 optAuth）
# 注：f_0414「室主任0414」在简道云全流程 optAuth 均未出现（legacy 子表），不在任何节点填写。
_PROD_CARD_DESIGN_ASSIGN_PERMS: dict[str, str] = {
    "f_251128": "required",
    "has_install_project": "required",
    "install_project_no": "readonly",
    "design_assignees": "required",
}
# 表单保留但简道云流程已废弃：全程隐藏（创建/审批/详情均不展示）
PROD_CARD_LEGACY_HIDDEN_FIELDS: frozenset[str] = frozenset({"f_0414"})
# 安排设计节点：发起人已填，本节点不再展示/编辑（不沿用简道云 optAuth 的可编辑项）
PROD_CARD_DESIGN_INITIATOR_ONLY_FIELDS: frozenset[str] = frozenset({
    "need_dispatch",
    "has_contract_tech_review",
    "select_contract_tech_review",
    "contract_tech_review_sn",
})
_PROD_CARD_APPROVER_ONLY: dict[str, str] = {
    **_PROD_CARD_SALES_CONFIRM_PERMS,
    **_PROD_CARD_DESIGN_ASSIGN_PERMS,
}


PROD_CARD_DETAIL_QUICK_FILL_FIELDS: frozenset[str] = frozenset({"std_room_fill"})


PROD_CARD_DROPPED_DETAIL_COLUMNS: dict[str, frozenset[str]] = {
    "std_room_fill": frozenset({"theoretical_weight"}),
    "elec_workshop_fill": frozenset({"theoretical_weight_2"}),
}


def apply_prod_card_prune_std_room_columns(defs: list) -> None:
    """生产卡明细子表：移除业务废弃列（标准化室/电气车间「理论重量」）。"""
    for f in defs:
        if not isinstance(f, dict):
            continue
        drop = PROD_CARD_DROPPED_DETAIL_COLUMNS.get(f.get("id") or "")
        if not drop:
            continue
        cols = f.get("detail_table_columns") or []
        f["detail_table_columns"] = [
            c for c in cols
            if isinstance(c, dict) and c.get("id") not in drop
        ]


def apply_prod_card_std_room_detail_defaults(defs: list) -> None:
    """标准化室子表：填写物料代码时间默认当前时刻（对齐简道云 value=today）。"""
    for f in defs:
        if not isinstance(f, dict) or f.get("id") != "std_room_fill":
            continue
        for col in f.get("detail_table_columns") or []:
            if not isinstance(col, dict) or col.get("id") != "material_code_time":
                continue
            props = dict(col.get("props") or {})
            props["default_today"] = True
            col["props"] = props


def apply_prod_card_detail_quick_fill_flags(defs: list) -> None:
    """对齐简道云 subform quick_fill：明细子表显示「快速填报」入口。"""
    for f in defs:
        if not isinstance(f, dict) or f.get("id") not in PROD_CARD_DETAIL_QUICK_FILL_FIELDS:
            continue
        props = dict(f.get("props") or {})
        props["quick_fill"] = True
        f["props"] = props


def apply_prod_card_legacy_hidden_fields(defs: list) -> None:
    """简道云 optAuth 未挂出的 legacy 字段：CRM 全程隐藏。"""
    for f in defs:
        if not isinstance(f, dict) or f.get("id") not in PROD_CARD_LEGACY_HIDDEN_FIELDS:
            continue
        f["available_on_create"] = False
        f["required"] = False
        f.pop("fill_stage", None)
        props = dict(f.get("props") or {})
        props["hidden"] = True
        f["props"] = props


def filter_prod_card_legacy_field_perms(perms: list | None) -> list:
    """待办/审批：去掉已废弃字段（在途流程节点可能仍挂着旧 field_perms）。"""
    out: list = []
    for p in perms or []:
        if not isinstance(p, dict):
            continue
        if p.get("field") in PROD_CARD_LEGACY_HIDDEN_FIELDS:
            continue
        out.append(p)
    return out


def apply_prod_card_prune_legacy_field_perms(nodes: list | None) -> bool:
    """发布/升级流程：从各节点 field_perms 剔除废弃字段。"""
    if not nodes:
        return False
    changed = False
    for n in nodes:
        if not isinstance(n, dict):
            continue
        perms = list(n.get("field_perms") or [])
        pruned = filter_prod_card_legacy_field_perms(perms)
        if len(pruned) != len(perms):
            n["field_perms"] = pruned
            changed = True
    return changed


def apply_prod_card_approver_only_fields(defs: list) -> None:
    """确认协议 / 设计指派填写：仅审批可填，创建页隐藏；字段级必填下沉到节点 perms。"""
    for f in defs:
        if not isinstance(f, dict):
            continue
        fid = f.get("id")
        if fid not in _PROD_CARD_APPROVER_ONLY:
            continue
        f["available_on_create"] = False
        f["fill_stage"] = "approver"
        # 发起不再校验；审批节点 field_perms 再要求
        f["required"] = False


def _merge_node_field_perms(node: dict, want: dict[str, str]) -> bool:
    """把 want 合并进 node.field_perms；required 优先。返回是否有改动。"""
    perms = list(node.get("field_perms") or [])
    by_field = {
        str(p.get("field")): p
        for p in perms
        if isinstance(p, dict) and p.get("field")
    }
    changed = False
    for fid, access in want.items():
        cur = by_field.get(fid)
        if not cur:
            perms.append({"field": fid, "access": access})
            changed = True
        elif access == "required" and cur.get("access") != "required":
            cur["access"] = "required"
            changed = True
    if changed:
        node["field_perms"] = perms
    return changed


def _force_node_field_access(node: dict, field_id: str, access: str) -> bool:
    """写入/覆盖节点 field_perms（含 editable → readonly）。"""
    perms = list(node.get("field_perms") or [])
    for p in perms:
        if isinstance(p, dict) and p.get("field") == field_id:
            if p.get("access") == access:
                return False
            p["access"] = access
            node["field_perms"] = perms
            return True
    perms.append({"field": field_id, "access": access})
    node["field_perms"] = perms
    return True


def apply_prod_card_sales_confirm_field_perms(nodes: list | None) -> bool:
    """业务员确认：可填「请确认是否同意按本协议约定、方案执行」（必填）。"""
    if not nodes:
        return False
    changed = False
    for n in nodes:
        if not isinstance(n, dict):
            continue
        if str(n.get("name") or "") != "业务员确认":
            continue
        if n.get("type") != "approval":
            continue
        if _merge_node_field_perms(n, _PROD_CARD_SALES_CONFIRM_PERMS):
            changed = True
    return changed


def _route_cond_is_region_manager_not_empty(cond) -> bool:
    if not isinstance(cond, dict):
        return False
    if cond.get("field") == "region_manager" and cond.get("operator") == "is_not_empty":
        return True
    for c in cond.get("cond") or []:
        if isinstance(c, dict) and _route_cond_is_region_manager_not_empty(c):
            return True
    return False


def apply_prod_card_sales_before_region(
    nodes: list | None, routes: list | None,
) -> bool:
    """生产卡：先业务员确认，再按区域经理/组长是否为空分支（对齐简道云画布 V43）。

    错误拓扑（data-hub 旧缓存 + 误补节点）：
      发起 --区域不为空--> 区域经理/组长 → 部门审批
      发起 --else--> 业务员确认 → 部门审批

    正确拓扑：
      发起 --else--> 业务员确认
      业务员确认 --区域不为空--> 区域经理/组长 → 部门审批
      业务员确认 --else--> 部门审批
    """
    if not isinstance(routes, list) or not nodes:
        return False
    by_name: dict[str, str] = {}
    start_ids: set[str] = set()
    for n in nodes:
        if not isinstance(n, dict) or not n.get("id"):
            continue
        nid = str(n["id"])
        name = str(n.get("name") or "")
        if n.get("type") == "start" or name == "生产卡发起":
            start_ids.add(nid)
        if name and name not in by_name:
            by_name[name] = nid
    sales_id = by_name.get("业务员确认")
    region_id = by_name.get("区域经理/组长")
    dept_id = by_name.get("部门审批")
    if not sales_id or not region_id or not dept_id or not start_ids:
        return False

    excl = f"ex_{sales_id}"
    changed = False
    has_sales_to_dept = False
    has_sales_to_region = False

    for r in routes:
        if not isinstance(r, dict) or r.get("always"):
            continue
        src = str(r.get("source") or "")
        tgt = str(r.get("target") or "")
        cond = r.get("condition")

        # 发起→区域经理（区域不为空）→ 改挂业务员确认
        if (
            src in start_ids
            and tgt == region_id
            and _route_cond_is_region_manager_not_empty(cond)
        ):
            r["source"] = sales_id
            r["exclusive_group"] = excl
            r.pop("fork", None)
            changed = True
            has_sales_to_region = True
            continue

        if src == sales_id and tgt == region_id:
            has_sales_to_region = True
            if r.get("exclusive_group") != excl:
                r["exclusive_group"] = excl
                changed = True
            if r.get("fork") == "parallel":
                r.pop("fork", None)
                changed = True
            continue

        if src == sales_id and tgt == dept_id:
            has_sales_to_dept = True
            if r.get("exclusive_group") != excl:
                r["exclusive_group"] = excl
                changed = True
            if r.get("fork") == "parallel":
                r.pop("fork", None)
                changed = True
            continue

        # 发起仍直达部门审批（旧 else）→ 改到业务员确认
        if src in start_ids and tgt == dept_id and not cond:
            r["target"] = sales_id
            changed = True

    if not has_sales_to_region:
        routes.append({
            "id": "r_sales_to_region",
            "source": sales_id,
            "target": region_id,
            "condition": {
                "field": "region_manager",
                "operator": "is_not_empty",
                "value": None,
            },
            "exclusive_group": excl,
        })
        changed = True

    if not has_sales_to_dept:
        routes.append({
            "id": "r_sales_to_dept",
            "source": sales_id,
            "target": dept_id,
            "exclusive_group": excl,
        })
        changed = True

    # 互斥组内：有条件的区域边排在 else 前，避免 else 抢先
    sales_outs = [
        r for r in routes
        if isinstance(r, dict)
        and not r.get("always")
        and str(r.get("source") or "") == sales_id
    ]
    if len(sales_outs) >= 2:
        def _rank(r: dict) -> tuple:
            if str(r.get("target") or "") == region_id:
                return (0, 0)
            if r.get("condition"):
                return (1, 0)
            return (2, 0)

        ordered = sorted(sales_outs, key=_rank)
        if [id(r) for r in ordered] != [id(r) for r in sales_outs]:
            new_routes: list = []
            replaced = False
            for r in routes:
                if not isinstance(r, dict):
                    new_routes.append(r)
                    continue
                if r.get("always") or str(r.get("source") or "") != sales_id:
                    new_routes.append(r)
                    continue
                if not replaced:
                    new_routes.extend(ordered)
                    replaced = True
            routes[:] = new_routes
            changed = True

    return changed


def _prune_node_field_perms(node: dict, drop_fields: frozenset[str]) -> bool:
    """从节点 field_perms 移除指定字段（发起人阶段已填，审批节点不再挂出）。"""
    perms = list(node.get("field_perms") or [])
    pruned = [
        p for p in perms
        if not (isinstance(p, dict) and p.get("field") in drop_fields)
    ]
    if len(pruned) == len(perms):
        return False
    node["field_perms"] = pruned
    return True


def apply_prod_card_design_assign_field_perms(nodes: list | None) -> bool:
    """安排设计节点：设计指派可写；派人/技术协议评审由发起人填写，本节点不编辑。"""
    if not nodes:
        return False
    changed = False
    for n in nodes:
        if not isinstance(n, dict):
            continue
        name = str(n.get("name") or "")
        if "安排设计" not in name or n.get("type") != "approval":
            continue
        if _prune_node_field_perms(n, PROD_CARD_DESIGN_INITIATOR_ONLY_FIELDS):
            changed = True
        if _merge_node_field_perms(n, _PROD_CARD_DESIGN_ASSIGN_PERMS):
            changed = True
        # 协议确认已归业务员确认，从安排设计节点去掉避免重复必填
        perms = list(n.get("field_perms") or [])
        pruned = [
            p for p in perms
            if not (
                isinstance(p, dict)
                and p.get("field") in ("confirm_agreement", *PROD_CARD_LEGACY_HIDDEN_FIELDS)
            )
        ]
        if len(pruned) != len(perms):
            n["field_perms"] = pruned
            changed = True
    changed = apply_prod_card_prune_legacy_field_perms(nodes) or changed
    return changed


def build_prod_card_fill_from_tar(*, review_code: str | None) -> dict[str, Any]:
    """生产卡选技术协议评审后的带出（对齐简道云 linkDataMaps：仅流水号）。"""
    return {"contract_tech_review_sn": (review_code or "").strip()}


def prod_card_tar_fill_clear_keys() -> list[str]:
    return ["contract_tech_review_sn"]


async def enrich_prod_card_fill_with_region_manager(
    db,
    tenant_id: str,
    fill: dict[str, Any],
    user: dict | None = None,
) -> dict[str, Any]:
    """选合同带出业务员后，按对照表补区域经理/组长。"""
    sp = fill.get("no_sales_person") or fill.get("yes_sales_person")
    if not sp:
        return fill
    from app.domains.lowcode.salesperson_region import resolve_region_manager

    rm = await resolve_region_manager(db, tenant_id, str(sp), user)
    rm_id = rm.get("region_manager_id")
    if not rm_id:
        return fill
    out = dict(fill)
    out["region_manager"] = rm_id
    return out


# 「生产卡通知单上的内容」：仅「是否为补充=否」时展示（补充单不填生产卡正文）
_PROD_CARD_NOTICE_FIELDS: tuple[str, ...] = (
    "prod_card_line_items",
    "packaging_req",
    "project_name",
    "paint_req",
    "tech_params",
    "no_warranty_period",
    "special_reminder",
    "remark_prod_card",
    "special_reminder_multi",
)
_PROD_CARD_NOTICE_RULE_IDS = frozenset(
    f"crm_vis_prod_notice_{fid}" for fid in _PROD_CARD_NOTICE_FIELDS
)
_PROD_CARD_NOTICE_WHEN_NOT_SUPPLEMENT = {
    "field": "is_supplement",
    "operator": "in",
    "value": ["否"],
}


def apply_prod_card_contract_fill_visibility(
    rules: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """选合同后同区展示（对齐简道云）：否=整块合同信息；是=合同号/业务员/单位名称。"""
    strip_ids = set(_PC_CONTRACT_FILL_VIS_RULE_IDS)
    # 去掉简道云旧规则，避免「是/否」与「已选合同」条件冲突
    for fid in _PC_DRAWING_ONLY_FILL_FIELDS:
        strip_ids.add(f"jdy_vis_{fid}")
        strip_ids.add(f"crm_vis_prod_notice_{fid}")
    for fid in _PC_YES_ONLY_FILL_FIELDS + _PC_SHARED_CONTRACT_FILL_FIELDS:
        strip_ids.add(f"jdy_vis_{fid}")
    for prefix in ("jdy_vis_yes_contract_no", "jdy_vis_yes_sales_person", "jdy_vis_yes_customer_name"):
        strip_ids.add(prefix)
    out: list[dict[str, Any]] = [
        r for r in (rules or [])
        if isinstance(r, dict) and r.get("id") not in strip_ids
    ]
    when_drawing_picked = {
        "rel": "and",
        "cond": [
            {"field": "is_supplement", "operator": "in", "value": ["否"]},
            {"field": "drawing_no_query", "operator": "is_not_empty"},
        ],
    }
    when_yes_contract_picked = {
        "rel": "and",
        "cond": [
            {"field": "is_supplement", "operator": "in", "value": ["是"]},
            {"field": "contract_no_select", "operator": "is_not_empty"},
        ],
    }
    when_either_contract_picked = {
        "rel": "or",
        "cond": [dict(when_drawing_picked), dict(when_yes_contract_picked)],
    }
    for fid in _PC_DRAWING_ONLY_FILL_FIELDS:
        out.append({
            "id": f"crm_vis_pc_contract_fill_{fid}",
            "type": "visibility",
            "target_field_id": fid,
            "condition": dict(when_drawing_picked),
            "action": {"visible": True},
            "enabled": True,
        })
    for fid in _PC_YES_ONLY_FILL_FIELDS:
        out.append({
            "id": f"crm_vis_pc_yes_contract_fill_{fid}",
            "type": "visibility",
            "target_field_id": fid,
            "condition": dict(when_yes_contract_picked),
            "action": {"visible": True},
            "enabled": True,
        })
    for fid, rid in (
        ("yes_customer_name", "crm_vis_pc_contract_fill_shared_yes_customer_name"),
        ("region_manager", "crm_vis_pc_contract_fill_shared_region_manager"),
    ):
        out.append({
            "id": rid,
            "type": "visibility",
            "target_field_id": fid,
            "condition": dict(when_either_contract_picked),
            "action": {"visible": True},
            "enabled": True,
        })
    return out


PROD_CARD_INSTALL_LINK_FIELD = "prod_card_install"
_PROD_CARD_INSTALL_DETAIL_ID = "f_251128"
_PROD_CARD_INSTALL_COL_ID = "field_2"
_PROD_CARD_INSTALL_COL_SALES = "field_3"
_PROD_CARD_INSTALL_COL_SITE = "field_4"
_PROD_CARD_INSTALL_COL_PRINT = "field_5"
_PROD_CARD_INSTALL_COL_MATTER = "field_6"


def _install_pick_as_id(val: Any) -> str | None:
    if val is None or val == "":
        return None
    if isinstance(val, list):
        return _install_pick_as_id(val[0] if val else None)
    if isinstance(val, dict):
        rid = val.get("id") or val.get("value")
        return str(rid).strip() if rid not in (None, "") else None
    s = str(val).strip()
    return s or None


def _resolve_install_project_no(
    data: dict,
    *,
    business_no: str | None,
    project_codes: dict[str, str] | None = None,
) -> str:
    """安装图项目号：优先打印项目号/流水号（AZ…），对齐简道云 linkDataMaps。"""
    pn = str(data.get("project_no_print") or "").strip()
    if pn:
        return pn
    pn = str(data.get("serial_no") or "").strip()
    if pn:
        return pn
    pn = (business_no or "").strip()
    if pn:
        return pn
    pid = _install_pick_as_id(data.get("project_no"))
    if pid and project_codes and pid in project_codes:
        return project_codes[pid]
    pn = str(data.get("matter") or "").strip()
    if pn:
        return pn
    return str(data.get("design_card_no") or "").strip()


def build_prod_card_install_fill(
    *,
    business_no: str | None,
    form_data: dict | None,
    project_codes: dict[str, str] | None = None,
    user_names: dict[str, str] | None = None,
) -> dict[str, Any]:
    """生产卡明细「选择数据」→ 安装图设计通知；带出安装图项目号与明细展示列。"""
    data = form_data if isinstance(form_data, dict) else {}
    names = user_names if isinstance(user_names, dict) else {}
    pn = _resolve_install_project_no(data, business_no=business_no, project_codes=project_codes)
    sales = data.get("sales_person")
    sales_text = ""
    if isinstance(sales, dict):
        sales_text = str(sales.get("name") or sales.get("label") or "").strip()
    if not sales_text and sales is not None:
        sid = _install_pick_as_id(sales)
        if sid and sid in names:
            sales_text = names[sid]
        elif sales not in (None, ""):
            sales_text = str(sales).strip()
    site = str(data.get("customer_name") or "").strip()
    matter = str(data.get("matter") or "").strip()
    return {
        "install_project_no": pn,
        _PROD_CARD_INSTALL_COL_PRINT: pn,
        _PROD_CARD_INSTALL_COL_SALES: sales_text,
        _PROD_CARD_INSTALL_COL_SITE: site,
        _PROD_CARD_INSTALL_COL_MATTER: matter,
    }


def prod_card_install_fill_clear_keys() -> list[str]:
    return ["install_project_no"]


def apply_prod_card_install_pick_fields(defs: list) -> None:
    """项目号选择251128 → 选择数据：关联安装图设计通知实例。"""
    _display_cols = (
        (_PROD_CARD_INSTALL_COL_PRINT, "项目号（打印模板显示）", "_widget_1764289051545"),
        (_PROD_CARD_INSTALL_COL_SALES, "业务员", None),
        (_PROD_CARD_INSTALL_COL_SITE, "现场", None),
        (_PROD_CARD_INSTALL_COL_MATTER, "事项", None),
    )
    for f in defs:
        if not isinstance(f, dict) or f.get("id") != _PROD_CARD_INSTALL_DETAIL_ID:
            continue
        cols = [c for c in (f.get("detail_table_columns") or []) if isinstance(c, dict)]
        col_by_id = {c["id"]: c for c in cols if c.get("id")}
        pick = col_by_id.get(_PROD_CARD_INSTALL_COL_ID)
        if not isinstance(pick, dict):
            pick = {"id": _PROD_CARD_INSTALL_COL_ID, "type": "text", "label": "选择数据"}
            cols.insert(0, pick)
        pick["type"] = "select_data"
        pick["label"] = pick.get("label") or "选择数据"
        pick["description"] = (
            pick.get("description")
            or "从安装图设计通知中选择；选中后自动带出安装图项目号。"
        )
        props = dict(pick.get("props") or {})
        props["source_form_code"] = "install_drawing_notice"
        props["link_fill"] = "prod_card_install"
        props["link_field"] = PROD_CARD_INSTALL_LINK_FIELD
        pick["props"] = props
        for cid, label, jdy_widget in _display_cols:
            col = col_by_id.get(cid)
            if not isinstance(col, dict):
                col = {"id": cid, "type": "text", "label": label}
                cols.append(col)
            col["type"] = "text"
            col["label"] = label
            col["form_editable"] = False
            if jdy_widget:
                col["jdy_widget"] = jdy_widget
        f["detail_table_columns"] = cols
        break
    for f in defs:
        if isinstance(f, dict) and f.get("id") == "install_project_no":
            f["form_editable"] = False
            f["description"] = (
                f.get("description")
                or "由项目号选择中的安装图设计通知自动带出，不可手改。"
            )


def apply_prod_card_supplement_rules(rules: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """合并「是否为补充=否 → 显示生产卡通知单内容」+ 设计单分派联动显隐。

    设计单分派（对齐简道云 fieldShowRules）：
    - 总部单 / 共同 → 显示并必填「设计指派」
    - 新乡单 / 郑州单 / 共同 / 包装单 → 显示并必填「转新乡、工艺包装」
    - 总部单不需要「转新乡、工艺包装」
    """
    out: list[dict[str, Any]] = [
        r for r in (rules or [])
        if isinstance(r, dict) and r.get("id") not in _PROD_CARD_NOTICE_RULE_IDS
    ]
    for fid in _PROD_CARD_NOTICE_FIELDS:
        out.append({
            "id": f"crm_vis_prod_notice_{fid}",
            "type": "visibility",
            "target_field_id": fid,
            "condition": dict(_PROD_CARD_NOTICE_WHEN_NOT_SUPPLEMENT),
            "action": {"visible": True},
            "enabled": True,
        })
    out = apply_prod_card_contract_fill_visibility(out)
    from app.domains.lowcode.cs_drawing_request_fields import apply_cs_drawing_request_rules
    return apply_cs_drawing_request_rules(out)
