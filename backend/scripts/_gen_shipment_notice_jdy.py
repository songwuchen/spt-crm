# -*- coding: utf-8 -*-
"""Generate CRM builtin 发货通知 from JDY dumps.

Sources:
  docs/product/_jdy_shipment_notice_{fields,workflows_raw}.json
Output:
  backend/app/domains/lowcode/_shipment_notice_generated.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _gen_drawing_jdy import (  # noqa: E402
    apply_pickable_scope,
    build_flow,
    build_rule_definitions,
    label_of,
    load_widget_limits_from_edit_raw,
    map_type,
    options_of,
    widget_slug_map,
)

OUT = Path(__file__).resolve().parents[2] / "docs" / "product"
GEN = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "domains"
    / "lowcode"
    / "_shipment_notice_generated.py"
)

SOFT_NOISE_KEYS = ("辅助", "已取消", "打印模板", "筛选用", "公式的", "主键", "离职")
HARD_DROP_KEYS = ("取消", "停用", "不用显示", "迁移提醒")
HARD_DROP_LABELS = frozenset({"迁移提醒", "人员查看", "离职人员数据", "限制战略规划部辅助"})
SYS_IDS = {"creator", "createTime", "updateTime", "appId", "entryId", "_id"}
SKIP_TYPES = {
    "separator", "button", "pagebreak", "hint", "flowstate",
    "aggregation", "linkquery", "formula",
}

TITLE_SLUG = {
    "单据编号": "serial_no",
    "日期时间": "biz_datetime",
    "发货类型": "ship_type",
    "采购员（多选）": "purchasers",
    "发货状态": "ship_status",
    "是否售后": "is_after_sales",
    "采购员": "purchaser",
    "合同号选择": "contract_no",
    "是否需要安装": "need_install",
    "对方合同号": "counterparty_contract_no",
    "合同金额": "contract_amount",
    "累计已发货（含本次）": "shipped_amount_incl",
    "未发货": "unshipped_amount",
    "合同号241012": "contract_no_text",
    "部门合同号": "dept_contract_no",
    "出门证编号": "exit_pass_no",
    "部门": "department",
    "业务员": "sales_person",
    "业务员电话": "sales_phone",
    "收货单位": "consignee_unit",
    "收货人及电话": "consignee_contact",
    "要求到货时间": "require_arrive_time",
    "多地址卸货": "multi_unload",
    "地址": "address",
    "第二地址": "address_2",
    "运费承担方": "freight_payer",
    "节假日是否收货": "holiday_receive",
    "是否过磅": "need_weigh",
    "是否补发": "is_reship",
    "是否要拉回货": "need_return_goods",
    "回货内容": "return_goods_content",
    "车型有无限制": "truck_limit",
    "是否可以带其它货进": "allow_other_goods",
    "付款方式": "payment_method",
    "是否为销售出库": "is_sales_outbound",
    "仓库经办人": "warehouse_handler",
    "移交仓库人员处理": "warehouse_transfer",
    "发货明细": "ship_lines",
    "货物名称": "goods_name",
    "规格型号": "spec_model",
    "公司型号": "company_model",
    "单位": "unit",
    "数量": "qty",
    "理论重量": "theory_weight",
    "金额": "line_amount",
    "*合同额": "contract_line_amount",
    "备注": "line_remark",
    "销售出库单据单号": "outbound_doc_no",
    "合同号": "line_contract_no",
    "验收方式": "accept_method",
    "验收所需资料": "accept_docs",
    "验收单附件": "accept_attachments",
    "发货金额": "ship_amount",
    "注意事项": "notes",
    "附件": "attachments",
    "图片": "images",
    "回执单图片": "receipt_images",
    "回执单附件": "receipt_files",
    "是否是先包装": "pack_first",
    "财务查款填写": "finance_check_note",
}

FORM = {
    "key": "shipment_notice",
    "title": "发货通知",
    "entry": "5de5f57eb980d700062f33d6",
    "route": "/shipment-notices",
    "fields_file": "_jdy_shipment_notice_fields.json",
    "wf_file": "_jdy_shipment_notice_workflows_raw.json",
    "edit_file": "_jdy_shipment_notice_edit_raw.json",
    "md_file": "_jdy_shipment_notice_forms.md",
}

# 发起节点 optAuth 未授权：审批阶段填写
_APPROVER_FILL = frozenset({
    "purchaser",
    "need_install",
    "dept_contract_no",
    "exit_pass_no",
    "is_sales_outbound",
    "warehouse_handler",
    "warehouse_transfer",
    "accept_method",
    "accept_docs",
    "accept_attachments",
    "receipt_images",
    "pack_first",
    "finance_check_note",
})

_CREATE_REQUIRED = frozenset({
    "ship_type",
    "ship_status",
    "is_after_sales",
    "department",
    "sales_person",
    "consignee_unit",
    "consignee_contact",
    "require_arrive_time",
    "freight_payer",
})

# 简道云「物流审批」角色 → CRM logistics_approval
_LOGISTICS_USERS = [
    "0236433705597",       # 孔令山
    "02362440128774",      # 李娜
    "575448583538947351",  # 马瑞草
    "196558292138209137",  # 韩文祯
    "221707676324076528",  # 张冠杰
]


def _norm_label(label: str) -> str:
    return (label or "").replace("*", "").strip()


def is_hard_drop(label: str, name: str) -> bool:
    if name in SYS_IDS:
        return True
    lab = _norm_label(label)
    if not lab or lab.startswith("_"):
        return True
    if lab in HARD_DROP_LABELS or (label or "").strip() in HARD_DROP_LABELS:
        return True
    return any(k in lab for k in HARD_DROP_KEYS)


def is_soft_noise(label: str) -> bool:
    return any(k in _norm_label(label) for k in SOFT_NOISE_KEYS)


def should_keep_field(label: str, name: str) -> bool:
    if is_hard_drop(label, name):
        return False
    if is_soft_noise(label):
        return False
    return True


def _slug_for(label: str, used: set[str]) -> str:
    lab = _norm_label(label)
    base = TITLE_SLUG.get(label) or TITLE_SLUG.get(lab)
    if not base:
        base = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "_", lab).strip("_").lower()
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
        opts = options_of(c)
        if typ == "select" and not opts:
            typ = "text"
        fd = {"id": _slug_for(lab, used), "type": typ, "label": _norm_label(lab) or lab}
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
        display = _norm_label(lab) or lab
        if slug == "serial_no" or display == "单据编号":
            fd = {
                "id": "serial_no",
                "type": "auto_number",
                "label": "单据编号",
                "props": {
                    "serial_rules": [
                        {"type": "text", "value": "24.1-"},
                        {"type": "date", "format": "yyyyMMdd"},
                        {
                            "type": "counter",
                            "digits": 4,
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
        if typ0 in ("linkfield", "combo") and display == "合同号选择":
            typ = "contract"
        if typ0 == "linkfield" and typ != "contract":
            typ = "text"
        opts = options_of(f)
        if typ == "select" and not opts:
            typ = "text"
        fd: dict = {"id": slug, "type": typ, "label": display}
        if typ == "contract":
            fd["description"] = "从合同管理中选择。"
        if slug in _CREATE_REQUIRED:
            fd["required"] = True
            fd["available_on_create"] = True
            fd["fill_stage"] = "initiator"
        elif slug in _APPROVER_FILL:
            fd["available_on_create"] = False
            fd["fill_stage"] = "approver"
            fd["required"] = False
        else:
            fd.setdefault("available_on_create", True)
            fd.setdefault("fill_stage", "initiator")
        if slug == "sales_person":
            fd.setdefault("props", {})["default_current_user"] = True
        if slug == "department":
            fd.setdefault("props", {})["default_current_dept"] = True
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
        out.append(fd)
    return out


def unwrap_wf(raw: dict) -> dict:
    if isinstance(raw, dict) and "workflow_config" in raw:
        return raw
    if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
        return raw["data"]
    return raw


def load_linkage() -> dict:
    path = OUT / FORM["edit_file"]
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    content = raw.get("data") or raw.get("content") or raw
    attr = content.get("attr") or {}
    link = attr.get("linkage") or content.get("linkage") or {}
    fsr = link.get("fieldShowRules") or content.get("fieldShowRules") or []
    ssr = link.get("subformFieldShowRules") or content.get("subformFieldShowRules") or []
    return {"fieldShowRules": fsr, "subformFieldShowRules": ssr}


# 简道云显示后需填：采购直发采购员、第二地址、回货、出门证、仓库经办、验收附件
_CONDITIONAL_REQUIRED = frozenset({
    "purchasers",
    "purchaser",
    "address_2",
    "return_goods_content",
    "exit_pass_no",
    "warehouse_handler",
    "accept_attachments",
})


def add_conditional_required(rules: list[dict]) -> list[dict]:
    extra: list[dict] = []
    have = {(r.get("type"), r.get("target_field_id")) for r in rules}
    for r in rules:
        if r.get("type") != "visibility":
            continue
        slug = r.get("target_field_id")
        if slug not in _CONDITIONAL_REQUIRED:
            continue
        key = ("required", slug)
        if key in have:
            continue
        extra.append({
            "id": f"sn_req_{slug}",
            "type": "required",
            "target_field_id": slug,
            "condition": r.get("condition"),
            "action": {"required": True},
        })
        have.add(key)
    return rules + extra


def patch_shipment_approvers(nodes: list[dict]) -> None:
    """物流审批：CRM 角色 logistics_approval（或签）。"""
    want = {
        "type": "specified_role",
        "value": "logistics_approval",
        "exclude_initiator": True,
        "jdy_role_hint": "物流审批",
    }
    for n in nodes:
        if n.get("name") == "物流审批":
            n["approver_rule"] = want
            n["multi_mode"] = "or_sign"


def gen_one() -> dict:
    fields_raw = json.loads((OUT / FORM["fields_file"]).read_text(encoding="utf-8"))
    wf_raw = unwrap_wf(json.loads((OUT / FORM["wf_file"]).read_text(encoding="utf-8")))
    widget_limits = {}
    edit_path = OUT / FORM["edit_file"]
    if edit_path.exists():
        widget_limits = load_widget_limits_from_edit_raw(edit_path)
    fields = build_fields(fields_raw, widget_limits)
    from app.domains.lowcode.shipment_notice_fields import apply_shipment_notice_fields
    apply_shipment_notice_fields(fields)
    linkage = load_linkage()
    rules = add_conditional_required(build_rule_definitions(linkage, fields))
    vis_n = sum(1 for r in rules if r.get("type") == "visibility")
    nodes, routes, notes = build_flow(wf_raw, fields, FORM["title"])
    from app.domains.lowcode.shipment_notice_fields import (
        apply_shipment_notice_sales_accept_field_perms,
        patch_shipment_notice_parallel_routes,
    )
    patch_shipment_approvers(nodes)
    if patch_shipment_notice_parallel_routes(routes):
        notes.append("开具提货单→生产领料/仓库判定改为并行（去掉误标互斥组 ex_n3）。")
    if apply_shipment_notice_sales_accept_field_perms(nodes):
        notes.append("通知业务员4：验收方式/资料只读展示，验收单附件可上传。")
    notes.insert(0, "对齐简道云销售中心「CRM-发货通知流程」；单据编号 24.1-+yyyyMMdd+四位日序。")
    notes.insert(1, f"简道云 fieldShowRules {len(linkage.get('fieldShowRules') or [])} 条 → CRM 显隐 {vis_n} 条（含显示后必填）。")
    notes.append("物流审批：CRM 角色 logistics_approval（孔令山/李娜/马瑞草/韩文祯/张冠杰，或签）。")

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
        f"# {FORM['title']} — CRM 字段对照（简道云 CRM-发货通知流程）",
        "",
        f"> 简道云 app=`5de0b3e85600ec0006f420f2` entry=`{FORM['entry']}`",
        "",
        f"- **builtin key**: `{FORM['key']}`",
        f"- **路由**: `{FORM['route']}`",
        f"- **字段数（去噪后）**: {len(fields)}",
        f"- **静态必填**: {n_req}",
        f"- **流程节点数（CRM）**: {len(nodes)} / 连线 {len(routes)}",
        f"- **联动规则**: {len(rules)}",
        f"- **流水号**: `24.1-` + yyyyMMdd + 四位日序",
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
    md += ["", "### 字段联动（显隐）", ""]
    for r in rules:
        if r.get("type") != "visibility":
            continue
        md.append(f"- `{r.get('target_field_id')}` ← `{json.dumps(r.get('condition'), ensure_ascii=False)}`")
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


def main() -> None:
    result = gen_one()
    GEN.write_text(
        "# -*- coding: utf-8 -*\n"
        "\"\"\"Auto-generated from docs/product/_jdy_shipment_notice_* dumps. "
        "Do not edit by hand.\"\"\"\n"
        "from __future__ import annotations\n"
        "import json\n\n"
        f"SHIPMENT_NOTICE_JDY = json.loads(r'''{json.dumps(result, ensure_ascii=False)}''')\n",
        encoding="utf-8",
    )
    print("wrote", GEN)


if __name__ == "__main__":
    main()
