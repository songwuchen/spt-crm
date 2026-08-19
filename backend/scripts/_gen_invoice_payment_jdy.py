# -*- coding: utf-8 -*-
"""Generate CRM builtin fields + flow from JDY 开票申请 / 收款登记 dumps.

Sources:
  docs/product/_jdy_invoice_application_{fields,workflows_raw}.json
  docs/product/_jdy_payment_registration_{fields,workflows_raw}.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _gen_drawing_jdy import (  # noqa: E402
    build_flow,
    label_of,
    map_type,
    options_of,
)
from _gen_prod_card_jdy import (  # noqa: E402
    collect_linkage_sets,
    normalize_linkage_pack,
)

OUT = Path(r"g:\ruolin-a\spt-crm\docs\product")
GEN = Path(
    r"g:\ruolin-a\spt-crm\backend\app\domains\lowcode\_invoice_payment_jdy_generated.py"
)

SOFT_NOISE_KEYS = (
    "辅助", "已取消", "打印模板", "筛选用", "公式的", "主键", "离职",
    "按日统计", "周几", "当日回款", "目标数",
)
HARD_DROP_KEYS = ("取消", "停用", "不用显示", "22/11/28", "230320", "合同明细（变动）")
SYS_IDS = {"creator", "createTime", "updateTime", "appId", "entryId", "_id"}
SKIP_TYPES = {
    "separator", "button", "pagebreak", "hint", "flowstate",
    "aggregation", "linkquery", "formula",
}

FORMS = [
    {
        "key": "invoice_application",
        "title": "开票申请",
        "entry": "5dd34ddf26aecf000655a354",
        "route": "/invoice-applications",
        "fields_file": "_jdy_invoice_application_fields.json",
        "wf_file": "_jdy_invoice_application_workflows_raw.json",
        "md_file": "_jdy_invoice_application_forms.md",
    },
    {
        "key": "payment_registration",
        "title": "收款登记",
        "entry": "5d63721786b06824f3fcc07f",
        "route": "/payment-registrations",
        "fields_file": "_jdy_payment_registration_fields.json",
        "wf_file": "_jdy_payment_registration_workflows_raw.json",
        "md_file": "_jdy_payment_registration_forms.md",
    },
]

TITLE_SLUG = {
    # 开票申请
    "流水号": "serial_no",
    "申请日期": "apply_date",
    "所在部门": "department",
    "选择图纸编号": "drawing_no_select",
    "图纸编号": "drawing_no",
    "单位名称": "customer_name",
    "部门合同号240222增": "dept_contract_no",
    "客户编号": "customer_no",
    "业务员": "sales_person",
    "合同数据": "contract_data",
    "合同明细（新增）": "contract_lines_new",
    "合同明细（变动）": "contract_lines_change",
    "总价合计": "total_amount",
    "总价合计（调整后）*": "total_amount_adjusted",
    "客户编码": "customer_code",
    "开票时间": "invoice_datetime",
    "开票特殊要求": "invoice_special_req",
    "发票号码": "invoice_no",
    "备注": "remark",
    "接收发票邮箱地址": "invoice_email",
    "附件": "attachments",
    "图片": "images",
    "产品名称": "product_name",
    "规格型号": "spec_model",
    "单位": "unit",
    "数量": "qty",
    "单价": "unit_price",
    "合计": "line_amount",
    "产品名称1": "product_name_chg",
    "规格型号1": "spec_model_chg",
    "单位1": "unit_chg",
    "数量1": "qty_chg",
    "单价1": "unit_price_chg",
    "合计1": "line_amount_chg",
    # 收款登记
    "收款号": "payment_no",
    "来款日期": "payment_date",
    "部门": "department",
    "来款明细": "payment_details",
    "来款形式": "payment_method",
    "金额": "amount",
    "承兑号": "acceptance_no",
    "出票银行": "issuing_bank",
    "到期日": "due_date",
    "来款合计": "payment_total",
    "业务人员": "sales_person",
    "款项分配": "payment_allocation",
    "合同号240222添加": "contract_no",
    "款项性质": "payment_nature",
    "分配金额": "alloc_amount",
    "分配金额合计": "alloc_total",
    "贴息手续": "discount_docs",
    "罚款手续": "penalty_docs",
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


def should_keep_field(
    label: str, name: str, required_widgets: set[str], rule_widgets: set[str],
) -> bool:
    if is_hard_drop(label, name):
        return False
    if name in required_widgets or name in rule_widgets:
        return True
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


def sub_columns(
    f: dict, used: set[str], required_widgets: set[str], rule_widgets: set[str],
) -> list[dict]:
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
        if not should_keep_field(lab, name, required_widgets, rule_widgets):
            continue
        typ0 = (c.get("type") or "").lower()
        if typ0 in SKIP_TYPES:
            continue
        typ = map_type(typ0)
        if typ0 == "linkfield":
            typ = "text"
        if typ0 == "sn":
            typ = "text"
        if typ == "detail_table":
            continue
        opts = options_of(c)
        if typ == "select" and not opts:
            typ = "text"
        fd = {"id": _slug_for(lab, used), "type": typ, "label": lab}
        if name in required_widgets:
            fd["required"] = True
        if opts and typ in ("select", "radio", "checkbox"):
            fd["options"] = opts
        if name:
            fd["jdy_widget"] = name
        out.append(fd)
    return out


def build_fields(raw: dict, required_widgets: set[str], rule_widgets: set[str]) -> list[dict]:
    data = raw.get("data", raw)
    fields = data.get("fields") if isinstance(data, dict) else data
    used: set[str] = set()
    out = []
    for f in fields or []:
        if not isinstance(f, dict):
            continue
        typ0 = (f.get("type") or "").lower()
        lab = label_of(f)
        name = f.get("name") or ""
        if typ0 in SKIP_TYPES:
            continue
        if not lab or not should_keep_field(lab, name, required_widgets, rule_widgets):
            continue
        slug = _slug_for(lab, used)
        if typ0 == "sn":
            typ = "auto_number"
        else:
            typ = map_type(typ0)
        if typ0 == "linkfield":
            typ = "text"
        opts = options_of(f)
        # 无选项的 combo（单位名称等靠关联带出）降为手填文本
        if typ == "select" and not opts:
            typ = "text"
        fd: dict = {"id": slug, "type": typ, "label": lab}
        if name in required_widgets or f.get("required"):
            fd["required"] = True
        if opts and typ in ("select", "radio", "checkbox"):
            fd["options"] = opts
        if typ == "detail_table":
            cols = sub_columns(f, used, required_widgets, rule_widgets)
            if cols:
                fd["detail_table_columns"] = cols
            else:
                continue
        if name:
            fd["jdy_widget"] = name
        out.append(fd)
    return out


def _cond_summary(cond: dict) -> str:
    if not cond:
        return ""
    if "cond" in cond and isinstance(cond.get("cond"), list):
        parts = [
            _cond_summary(c) if isinstance(c, dict) and "cond" in c
            else f"{c.get('field')} {c.get('operator')} {c.get('value')!r}"
            for c in cond["cond"] if isinstance(c, dict)
        ]
        return f"({(cond.get('rel') or 'and').upper()} " + "; ".join(parts) + ")"
    return f"{cond.get('field')} {cond.get('operator')} {cond.get('value')!r}"


def unwrap_wf(raw: dict) -> dict:
    if isinstance(raw, dict) and "workflow_config" in raw:
        return raw
    if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
        return raw["data"]
    return raw


def gen_one(spec: dict) -> dict:
    fields_raw = json.loads((OUT / spec["fields_file"]).read_text(encoding="utf-8"))
    wf_raw = unwrap_wf(json.loads((OUT / spec["wf_file"]).read_text(encoding="utf-8")))
    linkage: dict = {}
    link_path = OUT / f"_jdy_{spec['key']}_linkages.json"
    if link_path.exists():
        linkage = normalize_linkage_pack(
            json.loads(link_path.read_text(encoding="utf-8"))
        )
    required_widgets, rule_widgets, _ = collect_linkage_sets(linkage)
    fields = build_fields(fields_raw, required_widgets, rule_widgets)
    # 无 edit linkages：首批关键字段标必填（发起人可填）
    if not required_widgets:
        force_req = {
            "invoice_application": {
                "drawing_no", "customer_name", "department", "sales_person", "apply_date",
            },
            "payment_registration": {
                "payment_date", "customer_name", "department", "payment_details",
            },
        }.get(spec["key"], set())
        for fd in fields:
            if fd["id"] in force_req:
                fd["required"] = True

    nodes, routes, notes = build_flow(wf_raw, fields, spec["title"])

    pack = {
        "name": spec["title"],
        "field_definitions": fields,
        "rule_definitions": [],
        "flow_nodes": nodes,
        "flow_routes": routes,
        "notes": notes,
    }

    n_req = sum(1 for f in fields if f.get("required"))
    n_req_cols = sum(
        1 for f in fields for c in (f.get("detail_table_columns") or []) if c.get("required")
    )
    md = [
        f"# {spec['title']} — CRM 字段对照",
        "",
        f"> 简道云 app=`56ca77ce1efc301d279b8a4d` entry=`{spec['entry']}`",
        "",
        f"- **builtin key**: `{spec['key']}`",
        f"- **路由**: `{spec['route']}`",
        f"- **字段数（去噪后）**: {len(fields)}",
        f"- **必填字段**: {n_req}" + (f"（含子表列 {n_req_cols}）" if n_req_cols else ""),
        f"- **流程节点数（CRM）**: {len(nodes)} / 连线 {len(routes)}",
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
    (OUT / spec["md_file"]).write_text("\n".join(md) + "\n", encoding="utf-8")

    print(
        f"{spec['key']}: fields={len(fields)} required={n_req} "
        f"nodes={len(nodes)} routes={len(routes)}"
    )
    return {spec["key"]: pack}


def main():
    result: dict = {}
    for spec in FORMS:
        result.update(gen_one(spec))

    GEN.write_text(
        "# -*- coding: utf-8 -*\n"
        "\"\"\"Auto-generated from docs/product/_jdy_invoice_application_* "
        "and _jdy_payment_registration_* dumps. Do not edit by hand.\"\"\"\n"
        "from __future__ import annotations\n"
        "import json\n\n"
        f"INVOICE_PAYMENT_JDY = json.loads(r'''{json.dumps(result, ensure_ascii=False)}''')\n",
        encoding="utf-8",
    )
    print("wrote", GEN)


if __name__ == "__main__":
    main()
