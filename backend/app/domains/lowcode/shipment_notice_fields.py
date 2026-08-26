"""发货通知：字段运行时补丁（与生成器 / ensure 共用）。"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

# 选合同后写入的字段（清空合同时一并清）
SHIPMENT_FILL_CLEAR = [
    "consignee_unit",
    "contract_no_text",
    "department",
    "sales_person",
    "dept_contract_no",
    "need_install",
    "counterparty_contract_no",
    "accept_method",
    "accept_docs",
    "contract_amount",
    "ship_lines",
    "ship_amount",
    "prior_shipped_amount",
    "shipped_amount_incl",
    "unshipped_amount",
]

# 单据编号：24.1- + yyyyMMdd + 四位日序（CRM 约定，见 builtin 说明）
SHIPMENT_SERIAL_PREFIX = "24.1-"
SHIPMENT_SERIAL_NO_RULES: list[dict[str, Any]] = [
    {"type": "text", "value": SHIPMENT_SERIAL_PREFIX},
    {"type": "date", "format": "yyyyMMdd"},
    {
        "type": "counter",
        "digits": 4,
        "fixed": True,
        "reset_period": "daily",
        "initial_value": 1,
    },
]

# 合同明细列 → 发货明细列（对齐简道云 subLink）
_LINE_COL_MAP = {
    "name": "goods_name",
    "product_name": "goods_name",
    "spec": "spec_model",
    "spec_model": "spec_model",
    "unit": "unit",
    "qty": "qty",
    "amount": "contract_line_amount",
    "line_amount": "contract_line_amount",
}


def _as_rows(key_clauses: Any) -> list[dict]:
    if isinstance(key_clauses, list):
        return [r for r in key_clauses if isinstance(r, dict)]
    if isinstance(key_clauses, dict):
        for k in ("rows", "items", "line_items", "data"):
            v = key_clauses.get(k)
            if isinstance(v, list):
                return [r for r in v if isinstance(r, dict)]
        vals = list(key_clauses.values())
        if vals and all(isinstance(x, dict) for x in vals):
            return [x for x in vals if isinstance(x, dict)]
    return []


def _to_number(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(Decimal(str(v)))
    except (InvalidOperation, ValueError, TypeError):
        return None


def map_contract_lines_to_shipment(
    key_clauses: Any,
    *,
    drawing_no: str | None = None,
    contract_no: str | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    line_contract_no = (drawing_no or "").strip() or (contract_no or "").strip()
    for row in _as_rows(key_clauses):
        mapped: dict[str, Any] = {}
        for src, dst in _LINE_COL_MAP.items():
            if src in row and row[src] not in (None, "") and dst not in mapped:
                val = row[src]
                if dst in ("qty", "contract_line_amount", "line_amount"):
                    mapped[dst] = _to_number(val)
                else:
                    mapped[dst] = val
        qty = _to_number(mapped.get("qty"))
        amount = _to_number(mapped.get("contract_line_amount"))
        if amount is None and qty is not None:
            price = _to_number(row.get("price") or row.get("unit_price"))
            if price is not None:
                amount = round(qty * price, 2)
                mapped["contract_line_amount"] = amount
        if amount is not None:
            mapped["line_amount"] = amount
        if row.get("line_remark") not in (None, ""):
            mapped["line_remark"] = row.get("line_remark")
        if line_contract_no:
            mapped["line_contract_no"] = line_contract_no
        if mapped:
            out.append(mapped)
    return out


def _sum_line_amounts(lines: list[dict[str, Any]]) -> float | None:
    total = 0.0
    has = False
    for row in lines:
        amt = _to_number(row.get("line_amount"))
        if amt is None:
            continue
        total += amt
        has = True
    return round(total, 2) if has else None


def build_shipment_fill_from_contract(
    *,
    contract_no: str | None,
    drawing_no: str | None,
    peer_contract_no: str | None,
    assignee_id: str | None,
    department_id: str | None,
    customer_name: str | None,
    amount_total: Any = None,
    registration_json: dict | None,
    key_clauses_json: Any = None,
    prior_shipped_amount: Any = None,
) -> dict[str, Any]:
    """对齐简道云发货通知「合同号选择」linkDataMaps + 发货明细 subLink。

    金额三件套（是否售后=否时显示）对齐简道云：
    - 合同金额 ← 合同总金额（关联查询等价：选合同时带出）
    - 累计已发货（含本次）← MAPX(同合同历史发货金额) + 本次发货金额
    - 未发货 ← 合同金额 − 累计已发货
    """
    reg = registration_json if isinstance(registration_json, dict) else {}
    lines = map_contract_lines_to_shipment(
        key_clauses_json, drawing_no=drawing_no, contract_no=contract_no,
    )
    ship_amount = _sum_line_amounts(lines)
    prior = _to_number(prior_shipped_amount) or 0.0
    contract_amount = _to_number(amount_total)
    shipped_incl = None
    if ship_amount is not None or prior:
        shipped_incl = round(prior + (ship_amount or 0.0), 2)
    unshipped = None
    if contract_amount is not None and shipped_incl is not None:
        unshipped = round(contract_amount - shipped_incl, 2)
    return {
        "consignee_unit": customer_name or "",
        "contract_no_text": drawing_no or "",
        "department": department_id or None,
        "sales_person": assignee_id or None,
        "dept_contract_no": contract_no or "",
        "need_install": reg.get("need_install") or "",
        "counterparty_contract_no": peer_contract_no or "",
        "accept_method": reg.get("accept_method") or "",
        "accept_docs": reg.get("accept_materials") or reg.get("accept_docs") or "",
        "contract_amount": contract_amount,
        "ship_lines": lines,
        "ship_amount": ship_amount,
        # 历史已发（不含本次），供公式：累计=历史+本次
        "prior_shipped_amount": round(prior, 2),
        "shipped_amount_incl": shipped_incl,
        "unshipped_amount": unshipped,
    }


async def sum_prior_ship_amount_for_contract(
    db,
    tenant_id: str,
    *,
    contract_id: str,
    contract_no: str | None = None,
    drawing_no: str | None = None,
    exclude_instance_id: str | None = None,
    limit: int = 200,
) -> float:
    """对齐简道云 MAPX：同合同号其它发货通知的发货金额合计（不含本单）。"""
    from sqlalchemy import or_, select

    from app.domains.lowcode.models import FormInstance, FormTemplate

    tpl = (
        await db.execute(
            select(FormTemplate.id).where(
                FormTemplate.tenant_id == tenant_id,
                FormTemplate.code == "shipment_notice",
                FormTemplate.is_deleted.is_(False),  # noqa: E712
            ).limit(1)
        )
    ).scalar_one_or_none()
    if not tpl:
        return 0.0

    conds = [
        FormInstance.form_data.op("->>")("contract_no") == contract_id,
    ]
    dn = (drawing_no or "").strip()
    if dn:
        conds.append(FormInstance.form_data.op("->>")("contract_no_text") == dn)
    cn = (contract_no or "").strip()
    if cn:
        conds.append(FormInstance.form_data.op("->>")("dept_contract_no") == cn)

    q = (
        select(FormInstance)
        .where(
            FormInstance.tenant_id == tenant_id,
            FormInstance.template_id == tpl,
            FormInstance.is_deleted.is_(False),  # noqa: E712
            or_(*conds),
        )
        .order_by(FormInstance.created_at.desc())
        .limit(max(1, min(int(limit or 200), 500)))
    )
    if exclude_instance_id:
        q = q.where(FormInstance.id != exclude_instance_id)

    rows = (await db.execute(q)).scalars().all()
    total = 0.0
    seen: set[str] = set()
    for fi in rows:
        if fi.id in seen:
            continue
        seen.add(fi.id)
        data = fi.form_data if isinstance(fi.form_data, dict) else {}
        amt = _to_number(data.get("ship_amount"))
        if amt is None:
            # 无汇总时回退明细金额
            lines = data.get("ship_lines")
            if isinstance(lines, list):
                sub = _sum_line_amounts([r for r in lines if isinstance(r, dict)])
                amt = sub
        if amt is not None:
            total += amt
    return round(total, 2)


def apply_shipment_notice_fields(fields: list[dict]) -> None:
    """业务日期只选到日；合同号选择走合同控件并带出关联字段；加固单据编号流水规则。"""
    has_prior = False
    for fd in fields:
        if not isinstance(fd, dict):
            continue
        if fd.get("id") == "prior_shipped_amount":
            has_prior = True
        if fd.get("id") == "serial_no":
            fd["type"] = "auto_number"
            fd["label"] = fd.get("label") or "单据编号"
            fd["form_editable"] = False
            fd["available_on_create"] = True
            fd["fill_stage"] = "initiator"
            props = dict(fd.get("props") or {})
            props["serial_rules"] = [dict(r) for r in SHIPMENT_SERIAL_NO_RULES]
            fd["props"] = props
            fd["description"] = (
                f"系统单据编号：{SHIPMENT_SERIAL_PREFIX} + yyyyMMdd + 四位日序。"
            )
        if fd.get("id") in ("biz_datetime", "require_arrive_time"):
            fd["type"] = "date"
            props = dict(fd.get("props") or {})
            props["show_time"] = False
            props["date_only"] = True
            fd["props"] = props
        if fd.get("id") == "contract_no":
            fd["type"] = "contract"
            fd["label"] = "合同号选择"
            fd["description"] = "从合同管理中选择；选中后带出对方合同号、收货单位、部门、业务员及发货明细。"
            props = dict(fd.get("props") or {})
            props["contract_fill"] = "shipment_notice"
            fd["props"] = props
        if fd.get("id") == "ship_lines":
            fd["description"] = (fd.get("description") or "") or "选择合同号后从合同登记明细自动带出，可在本单增删改。"
        if fd.get("id") == "ship_amount":
            # 对齐简道云：SUM(发货明细.金额)
            fd["type"] = "formula"
            fd["label"] = fd.get("label") or "发货金额"
            fd["required"] = False
            fd["available_on_create"] = True
            fd["fill_stage"] = "initiator"
            fd["form_editable"] = False
            fd["description"] = "由发货明细「金额」自动汇总，不可编辑。"
            fd["props"] = {"formula": "SUM($ship_lines.line_amount#)"}
        if fd.get("id") == "contract_amount":
            fd["form_editable"] = False
            fd["description"] = (fd.get("description") or "") or "选自合同总金额；是否售后=否时显示。"
        if fd.get("id") == "shipped_amount_incl":
            # 对齐简道云：MAPX(历史发货金额) + 本次发货金额；可手改覆盖
            fd["type"] = "formula"
            fd["label"] = fd.get("label") or "累计已发货（含本次）"
            fd["required"] = False
            fd["available_on_create"] = True
            fd["fill_stage"] = "initiator"
            fd["form_editable"] = True
            fd["description"] = "同合同历史发货金额合计 + 本次发货金额；可手改。"
            props = dict(fd.get("props") or {})
            props["formula"] = "$prior_shipped_amount#+$ship_amount#"
            props["formula_editable"] = True
            fd["props"] = props
        if fd.get("id") == "unshipped_amount":
            # 对齐简道云：合同金额 − 累计已发货；可手改覆盖
            fd["type"] = "formula"
            fd["label"] = fd.get("label") or "未发货"
            fd["required"] = False
            fd["available_on_create"] = True
            fd["fill_stage"] = "initiator"
            fd["form_editable"] = True
            fd["description"] = "合同金额 − 累计已发货（含本次）；可手改。"
            props = dict(fd.get("props") or {})
            props["formula"] = "$contract_amount#-$shipped_amount_incl#"
            props["formula_editable"] = True
            fd["props"] = props
        if fd.get("id") == "prior_shipped_amount":
            fd["type"] = "number"
            fd["label"] = fd.get("label") or "历史已发货金额"
            fd["required"] = False
            fd["available_on_create"] = True
            fd["fill_stage"] = "initiator"
            fd["form_editable"] = False
            fd["description"] = "系统内部：同合同其它发货通知的发货金额合计（不含本单）。"
            props = dict(fd.get("props") or {})
            props["hidden"] = True
            fd["props"] = props

    if not has_prior:
        fields.append({
            "id": "prior_shipped_amount",
            "type": "number",
            "label": "历史已发货金额",
            "required": False,
            "available_on_create": True,
            "fill_stage": "initiator",
            "form_editable": False,
            "props": {"hidden": True},
            "description": "系统内部：同合同其它发货通知的发货金额合计（不含本单）。",
        })


# 简道云：开具提货单后「生产领料」与「仓库判定」并行（非互斥）
_SHIPMENT_PICK_PARALLEL_TARGETS = frozenset({"n9", "n10"})


def patch_shipment_notice_parallel_routes(routes: list[dict]) -> bool:
    """去掉开具提货单→生产领料/仓库判定的互斥组，对齐简道云并行分叉。"""
    changed = False
    for r in routes or []:
        if not isinstance(r, dict):
            continue
        if r.get("source") != "n3" or r.get("target") not in _SHIPMENT_PICK_PARALLEL_TARGETS:
            continue
        if r.pop("exclusive_group", None):
            changed = True
        r.pop("fork", None)
    return changed


def shipment_parallel_fork_broken(routes: list | None) -> bool:
    """旧版流程把 n3→n9/n10 标成互斥，需升级。"""
    for r in routes or []:
        if not isinstance(r, dict):
            continue
        if r.get("source") == "n3" and r.get("target") in _SHIPMENT_PICK_PARALLEL_TARGETS:
            if r.get("exclusive_group"):
                return True
    return False


_SHIPMENT_SALES_ACCEPT_NODE_NAMES = frozenset({
    "通知业务员4",
    "通知业务员1（1分钟自动提交）",
    "通知业务员2（1分钟自动提交）",
    "通知业务员3（1分钟自动提交）",
})
_SHIPMENT_SALES_ACCEPT_CONTEXT_READONLY = ("accept_method", "accept_docs")


def _merge_node_field_perm(node: dict, field: str, access: str) -> bool:
    perms = list(node.get("field_perms") or [])
    for p in perms:
        if isinstance(p, dict) and p.get("field") == field:
            if access == "required" and p.get("access") != "required":
                p["access"] = "required"
                node["field_perms"] = perms
                return True
            return False
    perms.append({"field": field, "access": access})
    node["field_perms"] = perms
    return True


def apply_shipment_notice_sales_accept_field_perms(nodes: list[dict]) -> bool:
    """通知业务员节点：展示验收方式/资料（只读）+ 可上传验收单附件（对齐简道云 optAuth）。"""
    changed = False
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        if str(n.get("name") or "") not in _SHIPMENT_SALES_ACCEPT_NODE_NAMES:
            continue
        for fid in _SHIPMENT_SALES_ACCEPT_CONTEXT_READONLY:
            if _merge_node_field_perm(n, fid, "readonly"):
                changed = True
        # 通知业务员4：验收单附件可编辑；显隐/必填由表单规则 sn_req_accept_attachments 控制
        if str(n.get("name") or "") == "通知业务员4":
            if _merge_node_field_perm(n, "accept_attachments", "editable"):
                changed = True
    return changed


def shipment_sales_accept_perms_ok(nodes: list | None) -> bool:
    for n in nodes or []:
        if not isinstance(n, dict) or n.get("name") != "通知业务员4":
            continue
        by_field = {
            p.get("field"): p.get("access")
            for p in (n.get("field_perms") or [])
            if isinstance(p, dict) and p.get("field")
        }
        return (
            by_field.get("accept_attachments") == "editable"
            and by_field.get("accept_method") == "readonly"
            and by_field.get("accept_docs") == "readonly"
        )
    return False
