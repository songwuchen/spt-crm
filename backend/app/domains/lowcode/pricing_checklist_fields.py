# -*- coding: utf-8 -*-
"""核价清单传递：关联表单选择（简道云 linkfield）+ 选中后带出。"""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.models import User
from app.domains.lowcode.models import FormInstance, FormTemplate
from app.domains.organization.models import Department

# 流程名称 → 选择字段。source 为 CRM builtin code。
PRICING_CHECKLIST_LINKS: dict[str, dict[str, Any]] = {
    "link_install": {
        "form_code": "install_drawing_notice",
        "label": "选择安装图设计通知数据",
        "placeholder": "从安装图设计通知中选择",
        "dests": [
            "install_serial_no", "install_design_card_no", "install_order_person",
            "install_applicant", "install_department",
            "summary_serial_no", "design_card_no", "contract_no",
            "order_person", "applicant", "business_dept",
        ],
    },
    "link_requisition": {
        "form_code": "drawing_requisition",
        "label": "选择合同图纸(资料)领用申请数据",
        "placeholder": "从合同图纸领用中选择",
        "dests": [
            "req_serial_no", "req_contract_no", "req_applicant",
            "req_order_person", "req_department",
            "summary_serial_no", "design_card_no", "contract_no",
            "order_person", "applicant", "business_dept",
        ],
    },
    "link_cs_drawing": {
        "form_code": "cs_drawing_request",
        "label": "选择客服领图数据",
        "placeholder": "从客服领图中选择",
        "dests": [
            "cs_serial_no", "cs_contract_no", "cs_order_person",
            "cs_applicant", "cs_department",
            "summary_serial_no", "design_card_no", "contract_no",
            "order_person", "applicant", "business_dept",
        ],
    },
    "link_coop_card": {
        "form_code": "research_coop_card",
        "label": "选择中央研究院协同卡数据",
        "placeholder": "从中央研究院协同卡中选择",
        "dests": [
            "coop_serial_no", "coop_contract_no", "coop_order_person",
            "coop_applicant", "coop_order_dept",
            "summary_serial_no", "design_card_no", "contract_no",
            "order_person", "applicant", "business_dept",
        ],
    },
}

# 合同外购件提前安排等：link_prod_card → 生产卡/补充流程
CONTRACT_OUTSOURCE_PROD_CARD_LINK = "link_prod_card"
CONTRACT_OUTSOURCE_PROD_CARD_DESTS = (
    "prod_card_serial", "contract_no", "design_assign", "office",
)

PICKABLE_FORM_CODES = {
    spec["form_code"] for spec in PRICING_CHECKLIST_LINKS.values()
} | {"prod_card_supplement"}
# 草稿、已撤回不可选；已提交/审批中/已通过可选。
PICKABLE_EXCLUDED_STATUSES = ("draft", "withdrawn")
# 生产卡补充：列表可见的草稿也应可被外购件等流程关联，仅排除已撤回。
PROD_CARD_SUPPLEMENT_PICKABLE_EXCLUDED_STATUSES = ("withdrawn",)


def pickable_excluded_statuses(form_code: str) -> tuple[str, ...]:
    if form_code == "prod_card_supplement":
        return PROD_CARD_SUPPLEMENT_PICKABLE_EXCLUDED_STATUSES
    return PICKABLE_EXCLUDED_STATUSES

# 弹窗列表列，对齐简道云 linkFields。
# 生产卡「项目号选择251128」弹窗列，对齐简道云 linkFields（非核价清单 link_install）。
PROD_CARD_INSTALL_PICK_COLUMNS: list[tuple[str, str]] = [
    ("project_no_print", "项目号（打印模板显示）"),
    ("customer_name", "现场"),
    ("sales_person", "业务员"),
    ("matter", "事项"),
]

PICK_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "install_drawing_notice": [
        ("serial_no", "流水号"),
        ("design_card_no", "新设计卡号"),
        ("order_person", "订货人"),
        ("applicant", "申请人"),
        ("department", "部门"),
    ],
    "drawing_requisition": [
        ("serial_no", "流水号"),
        ("contract_no", "合同号"),
        ("order_person", "订货人"),
        ("applicant", "申请人"),
        ("department", "部门"),
    ],
    "cs_drawing_request": [
        ("serial_no", "流水号"),
        ("contract_no", "合同号"),
        ("order_person", "订货人"),
        ("applicant", "申请人"),
        ("department", "部门"),
    ],
    "research_coop_card": [
        ("serial_no", "流水号"),
        ("order_dept", "订货部门"),
        ("applicant", "申请人"),
        ("drawing_no", "图纸编号"),
        ("order_person", "订货人"),
    ],
    "prod_card_supplement": [
        ("serial_no", "1.2.8生产卡/补充流程编号"),
        ("drawing_no", "图纸编号（筛选用）"),
        ("design_assign", "设计指派"),
        ("office", "科室"),
    ],
}

# 简道云 linkDataMaps 目标字段 enable=false；核价清单汇总行是公式字段 enable=false。
_LINK_DEST_READONLY = {
    "install_serial_no", "install_design_card_no", "install_order_person",
    "install_applicant", "install_department",
    "req_serial_no", "req_contract_no", "req_applicant",
    "req_order_person", "req_department",
    "cs_serial_no", "cs_contract_no", "cs_order_person",
    "cs_applicant", "cs_department",
    "coop_serial_no", "coop_contract_no", "coop_order_person",
    "coop_applicant", "coop_order_dept",
    "summary_serial_no", "design_card_no", "contract_no",
    "order_person", "applicant", "business_dept",
}


def apply_pricing_checklist_fields(field_defs: list[dict[str, Any]]) -> None:
    """把四条「选择××数据」从文本改为关联表单选择，并让带出字段只读。"""
    if not isinstance(field_defs, list):
        return
    for fd in field_defs:
        if not isinstance(fd, dict):
            continue
        fid = fd.get("id")
        spec = PRICING_CHECKLIST_LINKS.get(str(fid or ""))
        if spec:
            fd["type"] = "select_data"
            fd["label"] = spec["label"]
            fd["placeholder"] = spec["placeholder"]
            fd["description"] = spec["placeholder"]
            fd["available_on_create"] = True
            fd["fill_stage"] = "initiator"
            fd["required"] = True
            props = dict(fd.get("props") or {})
            props["source_form_code"] = spec["form_code"]
            props["link_fill"] = "pricing_checklist"
            fd["props"] = props
            continue
        if fid in _LINK_DEST_READONLY:
            fd["form_editable"] = False
            props = dict(fd.get("props") or {})
            props["read_only"] = True
            fd["props"] = props
            fd["description"] = fd.get("description") or "由所选关联单据自动带出，不可手改。"
            continue
        if fid == "pricing_qty":
            fd["default_value"] = 1
            props = dict(fd.get("props") or {})
            props.setdefault("min", 1)
            fd["props"] = props
            continue
        if fid in ("designer", "office", "process_name"):
            # 简道云 allowBlank=false：设计员 / 科室 / 流程名称提交必填
            fd["required"] = True
            if fid == "process_name":
                continue
        if fid == "apply_datetime":
            # 对齐简道云：datetime + value=today → 新增时默认当前时间
            fd["type"] = "datetime"
            fd["label"] = fd.get("label") or "日期时间"
            props = dict(fd.get("props") or {})
            props["default_today"] = True
            props.pop("date_only", None)
            props["show_time"] = True
            fd["props"] = props


def _as_id(val: Any) -> str | None:
    if val is None or val == "":
        return None
    if isinstance(val, list):
        return _as_id(val[0] if val else None)
    if isinstance(val, dict):
        rid = val.get("id") or val.get("value")
        return str(rid) if rid not in (None, "") else None
    s = str(val).strip()
    return s or None


def _as_text(val: Any, name_map: dict[str, str] | None = None) -> str:
    if val is None or val == "":
        return ""
    if isinstance(val, list):
        return _as_text(val[0], name_map) if val else ""
    if isinstance(val, dict):
        name = val.get("name") or val.get("label") or val.get("real_name")
        if name:
            return str(name)
        rid = _as_id(val)
        if rid and name_map:
            return name_map.get(rid, "")
        return str(rid or "")
    s = str(val).strip()
    if name_map and s in name_map:
        return name_map[s]
    return s


def _collect_ref_ids(*vals: Any) -> list[str]:
    out: list[str] = []
    for v in vals:
        if isinstance(v, list):
            for item in v:
                rid = _as_id(item)
                if rid:
                    out.append(rid)
            continue
        rid = _as_id(v)
        if rid:
            out.append(rid)
    return out


def _is_uuid(val: str) -> bool:
    s = (val or "").strip()
    return len(s) == 36 and s.count("-") == 4


async def _lookup_contract_ids_for_pick_keyword(
    db: AsyncSession,
    tenant_id: str,
    keyword: str,
) -> list[str]:
    """生产卡选单：图纸号/合同号关键词反查 contracts.id（form_data 仅存合同引用）。"""
    from app.domains.contract.models import Contract

    kw = (keyword or "").strip()
    if not kw:
        return []
    like = f"%{kw}%"
    rows = (await db.execute(
        select(Contract.id).where(
            Contract.tenant_id == tenant_id,
            or_(
                Contract.drawing_no.ilike(like),
                Contract.contract_no.ilike(like),
                Contract.peer_contract_no.ilike(like),
                Contract.serial_no.ilike(like),
                Contract.registration_json["serial_no"].as_string().ilike(like),
            ),
        ).limit(200)
    )).scalars().all()
    return [str(x) for x in rows]


def _prod_card_form_contract_ref_conds(
    contract_ids: list[str],
    contract_ref_texts: list[str] | None = None,
):
    """form_data 中 drawing_no_query / contract_no_select 命中合同 id 或流水号/合同号/图纸号。"""
    parts = []
    for cid in contract_ids:
        for key in ("drawing_no_query", "contract_no_select"):
            col = FormInstance.form_data[key]
            parts.append(col.astext == cid)
            parts.append(col["id"].astext == cid)
    for txt in contract_ref_texts or []:
        s = str(txt or "").strip()
        if not s:
            continue
        for key in ("drawing_no_query", "contract_no_select"):
            col = FormInstance.form_data[key]
            parts.append(col.astext == s)
            parts.append(col["id"].astext == s)
    return or_(*parts) if parts else None


async def _lookup_contract_ref_texts_for_ids(
    db: AsyncSession,
    tenant_id: str,
    contract_ids: list[str],
) -> list[str]:
    """合同 id → 流水号/合同号/图纸号，用于生产卡选单反查 drawing_no_query 存流水号的场景。"""
    from app.domains.contract.models import Contract

    ids = [x for x in contract_ids if x]
    if not ids:
        return []
    rows = (await db.execute(
        select(
            Contract.serial_no, Contract.contract_no, Contract.drawing_no,
            Contract.registration_json,
        ).where(
            Contract.tenant_id == tenant_id,
            Contract.id.in_(ids),
        )
    )).all()
    out: list[str] = []
    seen: set[str] = set()
    for serial, cno, dno, reg in rows:
        for val in (serial, cno, dno):
            s = str(val or "").strip()
            if s and s not in seen:
                seen.add(s)
                out.append(s)
        if isinstance(reg, dict):
            rs = str(reg.get("serial_no") or "").strip()
            if rs and rs not in seen:
                seen.add(rs)
                out.append(rs)
    return out


async def prod_card_supplement_list_keyword_clause(
    db: AsyncSession,
    tenant_id: str,
    keyword: str,
):
    """生产卡列表 keyword：反查关联合同图纸号/流水号（form_data 仅存合同引用）。"""
    parts = await _prod_card_supplement_pick_keyword_conds(db, tenant_id, keyword)
    return or_(*parts) if parts else None


async def _prod_card_supplement_pick_keyword_conds(
    db: AsyncSession,
    tenant_id: str,
    keyword: str,
) -> list:
    kw = (keyword or "").strip()
    if not kw:
        return []
    like = f"%{kw}%"
    kw_conds = [
        FormInstance.title.ilike(like),
        FormInstance.business_no.ilike(like),
        cast(FormInstance.form_data, String).ilike(like),
    ]
    cids = await _lookup_contract_ids_for_pick_keyword(db, tenant_id, kw)
    ref_texts = await _lookup_contract_ref_texts_for_ids(db, tenant_id, cids)
    ref_conds = _prod_card_form_contract_ref_conds(cids, ref_texts)
    if ref_conds is not None:
        kw_conds.append(ref_conds)
    for key in ("no_drawing_no", "yes_drawing_no", "yes_contract_no"):
        kw_conds.append(FormInstance.form_data[key].astext.ilike(like))
    return kw_conds


def apply_contract_row_to_lookup_maps(
    name_map: dict[str, str],
    id_by_ref: dict[str, str],
    *,
    contract_id: str,
    serial_no: str | None = None,
    contract_no: str | None = None,
    drawing_no: str | None = None,
) -> None:
    """合同主数据 → 选单展示名 + 流水号/合同号/图纸号 → UUID 反查表。"""
    cid = str(contract_id)
    label = (drawing_no or "").strip() or (contract_no or "").strip()
    id_by_ref[cid] = cid
    if label:
        name_map[cid] = label
    for ref in (serial_no, contract_no, drawing_no):
        s = str(ref or "").strip()
        if not s:
            continue
        id_by_ref[s] = cid
        if label:
            name_map[s] = label


def _contract_label(val: Any, contract_names: dict[str, str] | None = None) -> str:
    rid = _as_id(val)
    if rid and contract_names and rid in contract_names:
        return contract_names[rid]
    raw = _as_text(val)
    if raw and _is_uuid(raw):
        return ""
    return raw


def build_pricing_checklist_fill(
    link_field: str,
    *,
    business_no: str | None,
    form_data: dict | None,
    user_names: dict[str, str],
    dept_names: dict[str, str],
    contract_names: dict[str, str] | None = None,
) -> dict[str, Any]:
    """选中关联单后写入核价清单字段（对齐简道云 linkDataMaps + 公式汇总）。"""
    data = form_data if isinstance(form_data, dict) else {}
    serial = _as_text(data.get("serial_no")) or (business_no or "")
    applicant_id = _as_id(data.get("applicant"))
    dept_id = _as_id(data.get("department") or data.get("order_dept"))
    applicant_name = _as_text(data.get("applicant"), user_names)
    dept_name = _as_text(data.get("department") or data.get("order_dept"), dept_names)
    order_text = (
        _as_text(data.get("order_person_text"))
        or _as_text(data.get("order_person"), user_names)
        or _as_text(data.get("customer_name"))
    )
    contract_no = (
        _contract_label(data.get("contract_no"), contract_names)
        or _contract_label(data.get("drawing_no"), contract_names)
        or _as_text(data.get("drawing_no"))
    )
    design_card = _as_text(data.get("design_card_no"))

    if link_field == "link_install":
        return {
            "install_serial_no": serial,
            "install_design_card_no": design_card,
            "install_order_person": order_text,
            "install_applicant": applicant_id,
            "install_department": dept_id,
            "summary_serial_no": serial,
            "design_card_no": design_card,
            "contract_no": "无",
            "order_person": order_text,
            "applicant": applicant_name,
            "business_dept": dept_name,
        }
    if link_field == "link_requisition":
        return {
            "req_serial_no": serial,
            "req_contract_no": contract_no,
            "req_applicant": applicant_id,
            "req_order_person": order_text,
            "req_department": dept_id,
            "summary_serial_no": serial,
            "design_card_no": "无",
            "contract_no": contract_no,
            "order_person": order_text,
            "applicant": applicant_name,
            "business_dept": dept_name,
        }
    if link_field == "link_cs_drawing":
        return {
            "cs_serial_no": serial,
            "cs_contract_no": contract_no,
            "cs_order_person": order_text,
            "cs_applicant": applicant_id,
            "cs_department": dept_id,
            "summary_serial_no": serial,
            "design_card_no": "无",
            "contract_no": contract_no,
            "order_person": order_text,
            "applicant": applicant_name,
            "business_dept": dept_name,
        }
    if link_field == "link_coop_card":
        order_id = _as_id(data.get("order_person"))
        return {
            "coop_serial_no": serial,
            "coop_contract_no": contract_no,
            "coop_order_person": order_id,
            "coop_applicant": applicant_id,
            "coop_order_dept": dept_id,
            "summary_serial_no": serial,
            "design_card_no": "无",
            "contract_no": contract_no,
            "order_person": _as_text(data.get("order_person"), user_names),
            "applicant": applicant_name,
            "business_dept": dept_name,
        }
    return {}


def _resolve_prod_card_contract_for_outsource(
    data: dict,
    *,
    contract_names: dict[str, str] | None = None,
    contract_id_by_ref: dict[str, str] | None = None,
) -> tuple[str | None, str]:
    """从生产卡 form_data 解析合同 id 与展示用图纸/合同号（对齐简道云公式字段）。"""
    from app.domains.lowcode.prod_card_contract_fill import resolve_prod_card_contract_pick

    ref, _mode = resolve_prod_card_contract_pick(data)
    resolved_id = None
    if ref and contract_id_by_ref:
        resolved_id = contract_id_by_ref.get(ref)
    if not resolved_id and ref and _is_uuid(ref):
        resolved_id = ref
    contract_id = resolved_id or ref
    names = contract_names or {}
    for key in (ref, resolved_id, contract_id):
        if key and key in names:
            return contract_id, names[key]
    text = (
        _as_text(data.get("no_drawing_no"))
        or _as_text(data.get("yes_contract_no"))
        or ""
    )
    if not text and ref and ref in names:
        text = names[ref]
    if not text:
        text = (
            _contract_label(data.get("drawing_no_query"), contract_names)
            or _contract_label(data.get("contract_no_select"), contract_names)
        )
    return contract_id, text


def split_prod_card_office_tokens(raw: Any) -> list[str]:
    """生产卡 offices：UUID 列表或简道云文本「设计二室, 电气组」。"""
    if raw in (None, "", []):
        return []
    if isinstance(raw, list):
        out: list[str] = []
        for item in raw:
            rid = _as_id(item)
            if rid:
                out.append(rid)
                continue
            text = _as_text(item).strip()
            if text:
                out.extend(split_prod_card_office_tokens(text))
        return out
    text = str(raw).strip()
    if not text:
        return []
    if _is_uuid(text):
        return [text]
    return [part.strip() for part in re.split(r"[,，、;；]", text) if part.strip()]


def resolve_prod_card_office_for_fill(
    offices_raw: Any,
    *,
    dept_ids_by_name: dict[str, str] | None = None,
) -> list[str] | None:
    """科室 department_multi：名称 → 部门 UUID 数组。"""
    tokens = split_prod_card_office_tokens(offices_raw)
    if not tokens:
        return None
    name_map = dept_ids_by_name or {}
    out: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        dept_id = token if _is_uuid(token) else name_map.get(token)
        if dept_id and dept_id not in seen:
            seen.add(dept_id)
            out.append(dept_id)
    return out or None


def resolve_design_office_department_id(
    dept_rows: list[tuple[str, str]],
) -> str | None:
    """设计员所属科室：优先名称含「设计」且含「室/科」，否则取第一个编制部门。"""
    for did, name in dept_rows:
        n = (name or "").strip()
        if "设计" in n and ("室" in n or "科" in n):
            return did
    return dept_rows[0][0] if dept_rows else None


async def lookup_user_design_office_department_id(
    db: AsyncSession,
    tenant_id: str,
    user_id: str,
) -> str | None:
    """按用户 id 解析其设计科室（核价清单：选设计员带出科室）。"""
    from app.domains.organization.models import UserDepartment

    uid = str(user_id or "").strip()
    if not uid:
        return None
    rows = (
        await db.execute(
            select(Department.id, Department.name)
            .join(UserDepartment, UserDepartment.department_id == Department.id)
            .where(
                UserDepartment.tenant_id == tenant_id,
                UserDepartment.user_id == uid,
                Department.tenant_id == tenant_id,
            )
            .order_by(Department.name)
        )
    ).all()
    pairs = [(str(did), str(name or "")) for did, name in rows if did]
    return resolve_design_office_department_id(pairs)


async def lookup_department_ids_by_names(
    db: AsyncSession,
    tenant_id: str,
    names: list[str],
) -> dict[str, str]:
    """部门名称 → UUID（外购件选生产卡带出科室）。"""
    clean = [n.strip() for n in names if n and n.strip() and not _is_uuid(n.strip())]
    if not clean:
        return {}
    rows = (await db.execute(
        select(Department.id, Department.name).where(
            Department.tenant_id == tenant_id,
            Department.name.in_(list(dict.fromkeys(clean))),
        )
    )).all()
    return {str(name): str(did) for did, name in rows}


def build_contract_outsource_prod_card_fill(
    *,
    business_no: str | None,
    form_data: dict | None,
    user_names: dict[str, str] | None = None,
    dept_names: dict[str, str] | None = None,
    contract_names: dict[str, str] | None = None,
    contract_id_by_ref: dict[str, str] | None = None,
    dept_ids_by_name: dict[str, str] | None = None,
) -> dict[str, Any]:
    """合同外购件等：选中生产卡/补充流程后带出字段（对齐简道云 linkDataMaps）。"""
    data = form_data if isinstance(form_data, dict) else {}
    serial = _as_text(data.get("serial_no")) or (business_no or "")
    contract_id, _drawing_label = _resolve_prod_card_contract_for_outsource(
        data,
        contract_names=contract_names,
        contract_id_by_ref=contract_id_by_ref,
    )
    design = data.get("design_assignees")
    if design in (None, "", []):
        design = data.get("design_assign")
    offices = data.get("offices")
    if offices in (None, "", []):
        offices = data.get("office")
    office_ids = resolve_prod_card_office_for_fill(
        offices, dept_ids_by_name=dept_ids_by_name,
    )
    fill: dict[str, Any] = {
        "prod_card_serial": serial,
        "design_assign": design,
    }
    if office_ids:
        fill["office"] = office_ids
    if contract_id:
        fill["contract_no"] = contract_id
    return fill


def instance_pick_label(inst: FormInstance) -> str:
    data = inst.form_data if isinstance(inst.form_data, dict) else {}
    serial = _as_text(data.get("serial_no")) or (inst.business_no or "")
    extra = (
        _as_text(data.get("design_card_no"))
        or _as_text(data.get("contract_no"))
        or _as_text(data.get("drawing_no"))
        or _as_text(data.get("customer_name"))
        or (inst.title or "")
    )
    if serial and extra and extra != serial:
        return f"{serial} · {extra}"
    return serial or extra or inst.id


def pick_column_defs(form_code: str, link_field: str | None = None) -> list[dict[str, str]]:
    if link_field == "prod_card_install":
        cols = PROD_CARD_INSTALL_PICK_COLUMNS
    elif form_code == "prod_card_supplement" and link_field == CONTRACT_OUTSOURCE_PROD_CARD_LINK:
        cols = PICK_COLUMNS.get("prod_card_supplement", [])
    else:
        cols = PICK_COLUMNS.get(form_code, [])
    return [{"key": k, "title": t} for k, t in cols]


def _pick_cell(
    key: str,
    *,
    business_no: str | None,
    form_data: dict,
    user_names: dict[str, str],
    dept_names: dict[str, str],
    contract_names: dict[str, str] | None = None,
) -> str:
    data = form_data
    if key == "serial_no":
        return _as_text(data.get("serial_no")) or (business_no or "")
    if key == "project_no_print":
        return (
            _as_text(data.get("project_no_print"))
            or _as_text(data.get("serial_no"))
            or (business_no or "")
        )
    if key == "sales_person":
        return _as_text(data.get("sales_person"), user_names)
    if key == "customer_name":
        return _as_text(data.get("customer_name"))
    if key == "matter":
        return _as_text(data.get("matter"))
    if key in ("department", "order_dept"):
        return _as_text(data.get(key) or data.get("department") or data.get("order_dept"), dept_names)
    if key == "order_person":
        return (
            _as_text(data.get("order_person_text"))
            or _as_text(data.get("order_person"), user_names)
            or _as_text(data.get("customer_name"))
        )
    if key == "applicant":
        return _as_text(data.get("applicant"), user_names)
    if key == "design_card_no":
        return _as_text(data.get("design_card_no"))
    if key == "drawing_no":
        _cid, label = _resolve_prod_card_contract_for_outsource(
            data, contract_names=contract_names,
        )
        if label:
            return label
        return (
            _contract_label(data.get("drawing_no"), contract_names)
            or _as_text(data.get("drawing_no"))
        )
    if key == "contract_no":
        return (
            _contract_label(data.get(key), contract_names)
            or _contract_label(data.get("drawing_no"), contract_names)
            or _as_text(data.get("drawing_no"))
        )
    if key == "design_assign":
        val = data.get("design_assignees") or data.get("design_assign")
        if isinstance(val, list):
            parts = [_as_text(v, user_names) for v in val]
            return "、".join(p for p in parts if p)
        return _as_text(val, user_names)
    if key == "office":
        val = data.get("offices") or data.get("office")
        if isinstance(val, list):
            parts = [_as_text(v, dept_names) for v in val]
            return "、".join(p for p in parts if p)
        return _as_text(val, dept_names)
    return _as_text(data.get(key), user_names) or _as_text(data.get(key), dept_names)


async def list_pickable_form_instances(
    db: AsyncSession,
    tenant_id: str,
    *,
    form_code: str,
    link_field: str | None = None,
    keyword: str | None = None,
    ids: list[str] | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """登录即可选关联表单实例（不要求 form_data:view）。"""
    columns = pick_column_defs(form_code, link_field)
    empty = {"items": [], "total": 0, "page": page, "page_size": page_size, "columns": columns}
    if form_code not in PICKABLE_FORM_CODES:
        return empty
    tpl = (await db.execute(
        select(FormTemplate).where(
            FormTemplate.tenant_id == tenant_id,
            FormTemplate.code == form_code,
            FormTemplate.is_deleted == False,  # noqa: E712
        ).limit(1)
    )).scalar_one_or_none()
    if not tpl:
        return empty

    conds = [
        FormInstance.tenant_id == tenant_id,
        FormInstance.template_id == tpl.id,
        FormInstance.is_deleted == False,  # noqa: E712
    ]
    id_list = [x for x in (ids or []) if x]
    if id_list:
        conds.append(FormInstance.id.in_(id_list))
        total = len(id_list)
        page, page_size = 1, max(len(id_list), 1)
    else:
        conds.append(FormInstance.status.notin_(list(pickable_excluded_statuses(form_code))))
        kw = (keyword or "").strip()
        if kw:
            if form_code == "prod_card_supplement":
                kw_conds = await _prod_card_supplement_pick_keyword_conds(db, tenant_id, kw)
            else:
                like = f"%{kw}%"
                kw_conds = [
                    FormInstance.title.ilike(like),
                    FormInstance.business_no.ilike(like),
                    cast(FormInstance.form_data, String).ilike(like),
                ]
            conds.append(or_(*kw_conds))
        total = int((await db.execute(
            select(func.count()).select_from(FormInstance).where(*conds)
        )).scalar_one() or 0)
        page = max(1, int(page or 1))
        page_size = max(1, min(int(page_size or 20), 50))

    q = (
        select(FormInstance).where(*conds)
        .order_by(FormInstance.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = list((await db.execute(q)).scalars().all())
    user_ids: list[str] = []
    dept_ids: list[str] = []
    contract_ids: list[str] = []
    prod_card_contract_refs: list[str] = []
    prod_card_office_names: list[str] = []
    project_ids: list[str] = []
    for inst in rows:
        data = inst.form_data if isinstance(inst.form_data, dict) else {}
        user_ids.extend(_collect_ref_ids(
            data.get("applicant"), data.get("order_person"),
        ))
        if link_field == "prod_card_install":
            user_ids.extend(_collect_ref_ids(data.get("sales_person")))
        if form_code == "prod_card_supplement":
            user_ids.extend(_collect_ref_ids(
                data.get("design_assignees"), data.get("design_assign"),
            ))
        dept_ids.extend(_collect_ref_ids(
            data.get("department"), data.get("order_dept"),
        ))
        if form_code == "prod_card_supplement":
            dept_ids.extend(_collect_ref_ids(data.get("offices"), data.get("office")))
            prod_card_office_names.extend(
                token for token in split_prod_card_office_tokens(
                    data.get("offices") or data.get("office"),
                )
                if token and not _is_uuid(token)
            )
        for raw in (data.get("contract_no"), data.get("drawing_no")):
            rid = _as_id(raw)
            if rid and _is_uuid(rid):
                contract_ids.append(rid)
        if form_code == "prod_card_supplement":
            from app.domains.lowcode.prod_card_contract_fill import resolve_prod_card_contract_pick
            pcid, _ = resolve_prod_card_contract_pick(data)
            if pcid:
                prod_card_contract_refs.append(pcid)
                if _is_uuid(pcid):
                    contract_ids.append(pcid)
        if link_field == "prod_card_install":
            pid = _as_id(data.get("project_no"))
            if pid and _is_uuid(pid):
                project_ids.append(pid)

    user_names: dict[str, str] = {}
    if user_ids:
        urows = (await db.execute(
            select(User.id, User.real_name, User.username).where(
                User.tenant_id == tenant_id, User.id.in_(list(dict.fromkeys(user_ids))),
            )
        )).all()
        for uid, real_name, username in urows:
            user_names[str(uid)] = (real_name or username or "").strip() or str(uid)

    dept_names: dict[str, str] = {}
    if dept_ids:
        drows = (await db.execute(
            select(Department.id, Department.name).where(
                Department.tenant_id == tenant_id,
                Department.id.in_(list(dict.fromkeys(dept_ids))),
            )
        )).all()
        for did, name in drows:
            dept_names[str(did)] = (name or "").strip() or str(did)

    contract_names: dict[str, str] = {}
    contract_id_by_ref: dict[str, str] = {}
    dept_ids_by_name: dict[str, str] = {}
    if form_code == "prod_card_supplement" and prod_card_office_names:
        dept_ids_by_name = await lookup_department_ids_by_names(
            db, tenant_id, prod_card_office_names,
        )
    if form_code == "prod_card_supplement" and prod_card_contract_refs:
        from app.domains.lowcode.prod_card_contract_fill import resolve_contract_id_for_fill
        for ref in prod_card_contract_refs:
            if ref and not _is_uuid(ref):
                resolved = await resolve_contract_id_for_fill(db, tenant_id, ref)
                if resolved:
                    contract_ids.append(resolved)
    if contract_ids:
        from app.domains.contract.models import Contract
        crows = (await db.execute(
            select(
                Contract.id, Contract.serial_no, Contract.contract_no, Contract.drawing_no,
            ).where(
                Contract.tenant_id == tenant_id,
                Contract.id.in_(list(dict.fromkeys(contract_ids))),
            )
        )).all()
        for cid, serial, no, draw in crows:
            apply_contract_row_to_lookup_maps(
                contract_names,
                contract_id_by_ref,
                contract_id=str(cid),
                serial_no=serial,
                contract_no=no,
                drawing_no=draw,
            )

    project_codes: dict[str, str] = {}
    if project_ids:
        from app.domains.project.models import OpportunityProject
        prows = (await db.execute(
            select(OpportunityProject.id, OpportunityProject.project_code, OpportunityProject.name).where(
                OpportunityProject.tenant_id == tenant_id,
                OpportunityProject.id.in_(list(dict.fromkeys(project_ids))),
            )
        )).all()
        for pid, code, name in prows:
            label = (code or "").strip() or (name or "").strip()
            if label:
                project_codes[str(pid)] = label

    out: list[dict[str, Any]] = []
    col_keys = [c["key"] for c in columns]
    for inst in rows:
        data = inst.form_data if isinstance(inst.form_data, dict) else {}
        cols = {
            k: _pick_cell(
                k, business_no=inst.business_no, form_data=data,
                user_names=user_names, dept_names=dept_names,
                contract_names=contract_names,
            )
            for k in col_keys
        }
        item: dict[str, Any] = {
            "id": inst.id,
            "label": instance_pick_label(inst),
            "business_no": inst.business_no,
            "cols": cols,
        }
        if link_field == "prod_card_install":
            from app.domains.lowcode.prod_card_contract_fill import build_prod_card_install_fill
            item["fill"] = build_prod_card_install_fill(
                business_no=inst.business_no,
                form_data=data,
                project_codes=project_codes,
                user_names=user_names,
            )
        elif link_field and link_field in PRICING_CHECKLIST_LINKS:
            item["fill"] = build_pricing_checklist_fill(
                link_field,
                business_no=inst.business_no,
                form_data=data,
                user_names=user_names,
                dept_names=dept_names,
                contract_names=contract_names,
            )
        elif link_field == CONTRACT_OUTSOURCE_PROD_CARD_LINK:
            item["fill"] = build_contract_outsource_prod_card_fill(
                business_no=inst.business_no,
                form_data=data,
                user_names=user_names,
                dept_names=dept_names,
                contract_names=contract_names,
                contract_id_by_ref=contract_id_by_ref,
                dept_ids_by_name=dept_ids_by_name,
            )
        out.append(item)
    return {"items": out, "total": total, "page": page, "page_size": page_size, "columns": columns}
