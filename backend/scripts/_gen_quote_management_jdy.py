# -*- coding: utf-8 -*-
"""Generate CRM builtin 报价管理 from JDY 核价管理流程 dumps.

Sources:
  docs/product/_jdy_quote_management_{fields,workflows_raw}.json
Output:
  backend/app/domains/lowcode/_quote_management_generated.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _gen_drawing_jdy import (  # noqa: E402
    apply_pickable_scope,
    build_flow,
    label_of,
    load_widget_limits_from_edit_raw,
    map_type,
    options_of,
)

OUT = Path(r"g:\ruolin-a\spt-crm\docs\product")
GEN = Path(
    r"g:\ruolin-a\spt-crm\backend\app\domains\lowcode\_quote_management_generated.py"
)

SOFT_NOISE_KEYS = (
    "辅助", "已取消", "打印模板", "筛选用", "公式的", "主键", "离职",
    "按日统计", "周几", "当日回款", "目标数",
)
HARD_DROP_KEYS = ("取消", "停用", "不用显示", "22/11/28", "230320", "221209", "240311")
SYS_IDS = {"creator", "createTime", "updateTime", "appId", "entryId", "_id"}
SKIP_TYPES = {
    "separator", "button", "pagebreak", "hint", "flowstate",
    "aggregation", "linkquery", "formula",
}

TITLE_SLUG = {
    "流程编号": "serial_no",
    "部门": "department",
    "业务员": "sales_person",
    "参考合同号": "ref_contract_no",
    "客户名称": "customer_name",
    "下卡合同号": "card_contract_no",
    "客户类别": "customer_category",
    "价格类型": "price_type",
    "价格明细": "price_lines",
    "产品名称": "product_name",
    "规格型号": "spec_model",
    "单位": "unit",
    "数量": "qty",
    "是否转采购": "need_purchase",
    "采购": "purchaser",
    "询价单附件": "inquiry_attachments",
    "成本价附件": "cost_attachments",
    "询价图片": "inquiry_images",
    "特别提醒": "special_reminder",
    "成本价": "cost_price",
}

FORM = {
    "key": "quote_management",
    "title": "报价管理",
    "entry": "5e6c740e6d74970006a67190",
    "route": "/quotes",
    "fields_file": "_jdy_quote_management_fields.json",
    "wf_file": "_jdy_quote_management_workflows_raw.json",
    "md_file": "_jdy_quote_management_forms.md",
}


def is_hard_drop(label: str, name: str) -> bool:
    if name in SYS_IDS:
        return True
    lab = label or ""
    if not lab or lab.startswith("_"):
        return True
    return any(k in lab for k in HARD_DROP_KEYS)


def is_soft_noise(label: str) -> bool:
    return any(k in (label or "") for k in SOFT_NOISE_KEYS)


def should_keep_field(label: str, name: str) -> bool:
    if is_hard_drop(label, name):
        return False
    if is_soft_noise(label):
        return False
    return True


def _slug_for(label: str, used: set[str]) -> str:
    base = TITLE_SLUG.get(label)
    if not base:
        base = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "_", label).strip("_").lower()
        base = re.sub(r"[^a-zA-Z0-9_]+", "_", base).strip("_").lower() or "field"
        if base[0].isdigit():
            base = "f_" + base
    slug = base
    i = 2
    while slug in used:
        slug = f"{base}_{i}"
        i += 1
    used.add(slug)
    return slug


def sub_columns(f: dict, used: set[str]) -> list[dict]:
    cols = f.get("widgets") or []
    if not cols:
        cols = [
            x for x in (f.get("items") or [])
            if isinstance(x, dict) and x.get("type") and x.get("type") not in SKIP_TYPES
        ]
    out = []
    for c in cols:
        lab = label_of(c) or c.get("name") or "col"
        name = c.get("name") or ""
        if not should_keep_field(lab, name):
            continue
        typ0 = (c.get("type") or "").lower()
        if typ0 in SKIP_TYPES:
            continue
        typ = map_type(typ0)
        if typ0 == "linkfield":
            typ = "text"
        if typ == "detail_table":
            continue
        opts = options_of(c)
        if typ == "select" and not opts:
            typ = "text"
        fd = {"id": _slug_for(lab, used), "type": typ, "label": lab}
        if opts and typ in ("select", "radio", "checkbox"):
            fd["options"] = opts
        if name:
            fd["jdy_widget"] = name
        out.append(fd)
    return out


def build_fields(raw: dict, widget_limits: dict[str, dict] | None = None) -> list[dict]:
    data = raw.get("data", raw)
    fields = data.get("fields") if isinstance(data, dict) else data
    used: set[str] = set()
    out = []
    limits = widget_limits or {}
    for f in fields or []:
        if not isinstance(f, dict):
            continue
        typ0 = (f.get("type") or "").lower()
        lab = label_of(f)
        name = f.get("name") or ""
        if typ0 in SKIP_TYPES:
            continue
        if not lab or not should_keep_field(lab, name):
            continue
        slug = _slug_for(lab, used)
        # 流程编号：JDY 开放字段仅为 text；业务单号形如 HJ…，CRM 用 auto_number
        if slug == "serial_no" or lab == "流程编号":
            fd = {
                "id": "serial_no",
                "type": "auto_number",
                "label": "流程编号",
                "props": {
                    "serial_rules": [
                        {"type": "text", "value": "HJ"},
                        {"type": "date", "format": "yyyyMMdd"},
                        {
                            "type": "counter",
                            "digits": 3,
                            "fixed": True,
                            "reset_period": "daily",
                            "initial_value": 1,
                        },
                    ],
                },
                "available_on_create": True,
                "fill_stage": "initiator",
            }
            if name:
                fd["jdy_widget"] = name
            out.append(fd)
            continue
        typ = map_type(typ0)
        if typ0 == "linkfield":
            typ = "text"
        opts = options_of(f)
        if typ == "select" and not opts:
            typ = "text"
        # CRM：客户从客户管理选择，不手填（简道云原为 combo）
        if slug == "customer_name" or lab == "客户名称":
            typ = "customer"
            opts = []
        fd: dict = {"id": slug, "type": typ, "label": lab}
        if typ == "customer":
            fd["description"] = "从客户管理中选择。"
        if f.get("required"):
            fd["required"] = True
        if opts and typ in ("select", "radio", "checkbox"):
            fd["options"] = opts
        if typ == "detail_table":
            cols = sub_columns(f, used)
            if cols:
                fd["detail_table_columns"] = cols
            else:
                continue
        if name:
            fd["jdy_widget"] = name
        if typ in ("person", "person_multi"):
            apply_pickable_scope(fd, limit=limits.get(name), jdy_field=f)
            # 采购：简道云 limit.departs=计划采购部 → quote_purchasers
            if slug == "purchaser" and not (fd.get("props") or {}).get("pickable_scope"):
                props = dict(fd.get("props") or {})
                props["pickable_scope"] = {"scope_code": "quote_purchasers"}
                fd["props"] = props
        out.append(fd)
    return out


def unwrap_wf(raw: dict) -> dict:
    if isinstance(raw, dict) and "workflow_config" in raw:
        return raw
    if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
        return raw["data"]
    return raw


def build_rules(fields: list[dict]) -> list[dict]:
    """是否转采购=是 时显示采购人选人。"""
    ids = {f["id"] for f in fields}
    if "need_purchase" not in ids or "purchaser" not in ids:
        return []
    return [
        {
            "id": "vis_purchaser_when_need",
            "type": "visibility",
            "target_field_id": "purchaser",
            "condition": {"field": "need_purchase", "operator": "eq", "value": "是"},
            "action": {"visible": True},
        },
    ]


# 客户类别 / 价格类型：创建不填，部门审批时可填（非必填）
_APPROVER_FILL_FIELDS = ("customer_category", "price_type")


def apply_finance_need_purchase_editable(nodes: list[dict], notes: list[str]) -> None:
    """财务核价节点：「是否转采购」可填非必填（客户要求）。"""
    for n in nodes:
        if not isinstance(n, dict) or n.get("name") != "财务核价":
            continue
        perms = list(n.get("field_perms") or [])
        found = False
        for p in perms:
            if isinstance(p, dict) and p.get("field") == "need_purchase":
                p["access"] = "editable"
                found = True
                break
        if not found:
            perms.append({"field": "need_purchase", "access": "editable"})
        n["field_perms"] = perms
        notes.append("财务核价：是否转采购 → editable（非必填）")
        break


def apply_dept_approver_fill_fields(nodes: list[dict], notes: list[str]) -> None:
    """部门审批：客户类别 / 价格类型 → editable（创建阶段隐藏，非必填）。"""
    touched = 0
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
        for fid in _APPROVER_FILL_FIELDS:
            if fid in by_field:
                by_field[fid]["access"] = "editable"
            else:
                perms.append({"field": fid, "access": "editable"})
                by_field[fid] = perms[-1]
        n["field_perms"] = perms
        touched += 1
    if touched:
        notes.append(
            f"部门审批×{touched}：客户类别/价格类型 → editable（创建不填，非必填）"
        )


def apply_notify_initiator(nodes: list[dict], notes: list[str]) -> None:
    """原「通知尚高华」改为通知发起人（谁发起通知谁）。"""
    for n in nodes:
        if not isinstance(n, dict):
            continue
        if n.get("id") != "n7" and n.get("name") != "通知尚高华":
            continue
        n["name"] = "通知发起人"
        n["type"] = n.get("type") or "approval"
        n["approver_rule"] = {"type": "creator"}
        # 清掉 build_flow 里残留的「具名用户尚高华」备注
        notes[:] = [x for x in notes if "通知尚高华" not in x]
        notes.append("通知尚高华 → 通知发起人（approver_rule=creator）")
        break


def gen_one() -> dict:
    fields_raw = json.loads((OUT / FORM["fields_file"]).read_text(encoding="utf-8"))
    wf_raw = unwrap_wf(json.loads((OUT / FORM["wf_file"]).read_text(encoding="utf-8")))
    widget_limits = load_widget_limits_from_edit_raw(
        OUT / "_jdy_quote_management_edit_raw.json"
    )
    fields = build_fields(fields_raw, widget_limits)
    force_req = {
        "department", "sales_person", "customer_name",
    }
    for fd in fields:
        if fd["id"] in force_req:
            fd["required"] = True
            fd.setdefault("available_on_create", True)
            fd.setdefault("fill_stage", "initiator")

    rules = build_rules(fields)
    nodes, routes, notes = build_flow(wf_raw, fields, FORM["title"])
    # build_flow 内 optAuth 会把发起可写字段标成 initiator；客户类别/价格类型改回审批填写
    for fd in fields:
        if fd["id"] in _APPROVER_FILL_FIELDS:
            fd["available_on_create"] = False
            fd["fill_stage"] = "approver"
            fd["required"] = False
    apply_finance_need_purchase_editable(nodes, notes)
    apply_dept_approver_fill_fields(nodes, notes)
    apply_notify_initiator(nodes, notes)
    # 与 workflow_service.apply_quote_named_role_approvers 一致（charger_rule 已映射；此处兜底）
    try:
        from app.domains.lowcode.workflow_service import (
            apply_quote_named_role_approvers,
            apply_quote_finance_dept_notify_parallel,
            apply_quote_purchase_inquiry_parallel,
        )
        if apply_quote_named_role_approvers(nodes):
            notes.append("报价角色审批：王玲玲/段荣凯→指定用户，冶金→可选范围 quote_metallurgy")
        if apply_quote_purchase_inquiry_parallel(nodes, routes):
            notes.append("财务核价→采购：并行（不与部门通知互斥）；采购→财务核价可重入")
        if apply_quote_finance_dept_notify_parallel(nodes, routes):
            notes.append("财务核价→部门通知：多条件并行（通知发起人与热能等可同时命中）")
    except Exception as ex:  # pragma: no cover
        notes.append(f"报价角色/转采购补丁跳过: {ex}")
    notes.append("客户类别/价格类型：创建隐藏，部门审批可填（非必填）")

    pack = {
        "name": FORM["title"],
        "field_definitions": fields,
        "rule_definitions": rules,
        "flow_nodes": nodes,
        "flow_routes": routes,
        "notes": notes,
    }

    n_req = sum(1 for f in fields if f.get("required"))
    md = [
        f"# {FORM['title']} — CRM 字段对照（简道云核价管理流程）",
        "",
        f"> 简道云 app=`5e6c73fefc53170006bd4e9c` entry=`{FORM['entry']}`",
        "",
        f"- **builtin key**: `{FORM['key']}`",
        f"- **路由**: `{FORM['route']}`",
        f"- **字段数（去噪后）**: {len(fields)}",
        f"- **必填字段**: {n_req}",
        f"- **流程节点数（CRM）**: {len(nodes)} / 连线 {len(routes)}",
        f"- **流水号**: `HJ` + yyyyMMdd + 三位日序",
        "",
        "| slug | 标签 | type | 必填 | jdy_widget |",
        "|------|------|------|------|------------|",
    ]
    for fd in fields:
        md.append(
            f"| {fd['id']} | {fd['label']} | {fd['type']} | "
            f"{'是' if fd.get('required') else ''} | `{fd.get('jdy_widget', '')}` |"
        )
        for col in fd.get("detail_table_columns") or []:
            md.append(
                f"| └ {col['id']} | {col['label']} | {col['type']} | "
                f"{'是' if col.get('required') else ''} | `{col.get('jdy_widget', '')}` |"
            )
    md += ["", "### 流程降级备注", ""]
    for n in notes:
        md.append(f"- {n}")
    md.append("")
    (OUT / FORM["md_file"]).write_text("\n".join(md) + "\n", encoding="utf-8")

    print(
        f"{FORM['key']}: fields={len(fields)} required={n_req} "
        f"nodes={len(nodes)} routes={len(routes)} rules={len(rules)}"
    )
    return {FORM["key"]: pack}


def main():
    result = gen_one()
    GEN.write_text(
        "# -*- coding: utf-8 -*\n"
        "\"\"\"Auto-generated from docs/product/_jdy_quote_management_* dumps. "
        "Do not edit by hand.\"\"\"\n"
        "from __future__ import annotations\n"
        "import json\n\n"
        f"QUOTE_MANAGEMENT_JDY = json.loads(r'''{json.dumps(result, ensure_ascii=False)}''')\n",
        encoding="utf-8",
    )
    print("wrote", GEN)


if __name__ == "__main__":
    main()
