# -*- coding: utf-8 -*-
"""核价清单传递：关联表单选择（简道云 linkfield）+ 选中后带出。"""
from __future__ import annotations

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
) -> tuple[str | None, str]:
    """从生产卡 form_data 解析合同 id 与展示用图纸/合同号（对齐简道云公式字段）。"""
    from app.domains.lowcode.prod_card_contract_fill import resolve_prod_card_contract_pick

    cid, _mode = resolve_prod_card_contract_pick(data)
    if cid and contract_names and cid in contract_names:
        return cid, contract_names[cid]
    text = (
        _as_text(data.get("no_drawing_no"))
        or _as_text(data.get("yes_contract_no"))
        or _contract_label(data.get("drawing_no_query"), contract_names)
        or _contract_label(data.get("contract_no_select"), contract_names)
    )
    return cid, text


def build_contract_outsource_prod_card_fill(
    *,
    business_no: str | None,
    form_data: dict | None,
    user_names: dict[str, str] | None = None,
    dept_names: dict[str, str] | None = None,
    contract_names: dict[str, str] | None = None,
) -> dict[str, Any]:
    """合同外购件等：选中生产卡/补充流程后带出字段（对齐简道云 linkDataMaps）。"""
    data = form_data if isinstance(form_data, dict) else {}
    serial = _as_text(data.get("serial_no")) or (business_no or "")
    contract_id, _drawing_label = _resolve_prod_card_contract_for_outsource(
        data, contract_names=contract_names,
    )
    design = data.get("design_assignees")
    if design in (None, "", []):
        design = data.get("design_assign")
    offices = data.get("offices")
    if offices in (None, "", []):
        offices = data.get("office")
    fill: dict[str, Any] = {
        "prod_card_serial": serial,
        "design_assign": design,
        "office": offices,
    }
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
        conds.append(FormInstance.status.notin_(list(PICKABLE_EXCLUDED_STATUSES)))
        kw = (keyword or "").strip()
        if kw:
            like = f"%{kw}%"
            conds.append(or_(
                FormInstance.title.ilike(like),
                FormInstance.business_no.ilike(like),
                cast(FormInstance.form_data, String).ilike(like),
            ))
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
        for raw in (data.get("contract_no"), data.get("drawing_no")):
            rid = _as_id(raw)
            if rid and _is_uuid(rid):
                contract_ids.append(rid)
        if form_code == "prod_card_supplement":
            from app.domains.lowcode.prod_card_contract_fill import resolve_prod_card_contract_pick
            pcid, _ = resolve_prod_card_contract_pick(data)
            if pcid and _is_uuid(pcid):
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
    if contract_ids:
        from app.domains.contract.models import Contract
        crows = (await db.execute(
            select(Contract.id, Contract.contract_no, Contract.drawing_no).where(
                Contract.tenant_id == tenant_id,
                Contract.id.in_(list(dict.fromkeys(contract_ids))),
            )
        )).all()
        for cid, no, draw in crows:
            label = (draw or "").strip() or (no or "").strip()
            if label:
                contract_names[str(cid)] = label

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
            )
        out.append(item)
    return {"items": out, "total": total, "page": page, "page_size": page_size, "columns": columns}
