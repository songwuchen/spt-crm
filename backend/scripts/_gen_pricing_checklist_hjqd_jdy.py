# -*- coding: utf-8 -*-
"""Generate CRM builtin 核价清单传递 from JDY 核价清单传递流程HJQD dumps.

Sources:
  docs/product/_jdy_pricing_checklist_hjqd_{fields,workflows_raw,edit_raw}.json
Output:
  backend/app/domains/lowcode/_pricing_checklist_hjqd_generated.py
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
    r"g:\ruolin-a\spt-crm\backend\app\domains\lowcode\_pricing_checklist_hjqd_generated.py"
)

SYS_IDS = {"creator", "createTime", "updateTime", "appId", "entryId", "_id"}
SKIP_TYPES = {
    "separator", "button", "pagebreak", "hint", "flowstate",
    "aggregation", "linkquery", "formula",
}

# 显式 slug，避免「流水号」等多处同名冲突
TITLE_SLUG = {
    "流水号": "serial_no",  # sn 主流水；文本「流水号」另处理
    "流程名称*": "process_name",
    "流程名称": "process_name",
    "选择安装图设计通知数据": "link_install",
    "流水号-安装图设计通知": "install_serial_no",
    "新设计卡号-安装图设计通知": "install_design_card_no",
    "订货人（文本）-安装图设计通知": "install_order_person",
    "申请人-安装图设计通知": "install_applicant",
    "部门-安装图设计通知": "install_department",
    "选择合同图纸(资料)领用申请数据": "link_requisition",
    "流水号-合同图纸(资料)领用申请": "req_serial_no",
    "合同号-合同图纸(资料)领用申请": "req_contract_no",
    "申请人-合同图纸(资料)领用申请": "req_applicant",
    "订货人（文本）-合同图纸(资料)领用申请": "req_order_person",
    "部门-合同图纸(资料)领用申请": "req_department",
    "选择客服领图数据": "link_cs_drawing",
    "流水号-客服领图": "cs_serial_no",
    "合同号-客服领图": "cs_contract_no",
    "订货人（文本）-客服领图": "cs_order_person",
    "申请人-客服领图": "cs_applicant",
    "部门-客服领图": "cs_department",
    "选择中央研究院协同卡数据": "link_coop_card",
    "流水号-中央研究院协同卡": "coop_serial_no",
    "合同号-中央研究院协同卡": "coop_contract_no",
    "订货人（文本）-中央研究院协同卡": "coop_order_person",
    "申请人-中央研究院协同卡": "coop_applicant",
    "订货部门-中央研究院协同卡": "coop_order_dept",
    "对应设计卡号": "design_card_no",
    "合同号": "contract_no",
    "订货人": "order_person",
    "申请人": "applicant",
    "业务部门": "business_dept",
    "设计员": "designer",
    "科室": "office",
    "日期时间": "apply_datetime",
    "核价单数量": "pricing_qty",
    "图片": "images",
    "附件": "attachments",
    "备注": "remark",
    "核价清单是否有问题0909": "has_issue",
    "问题类型和具体问题明细0909": "issue_details",
    "问题类型": "issue_type",
    "具体问题": "issue_detail",
}

FORM = {
    "key": "pricing_checklist_hjqd",
    "title": "核价清单传递",
    "entry": "667638539c1f73c42e4bcbff",
    "fields_file": "_jdy_pricing_checklist_hjqd_fields.json",
    "wf_file": "_jdy_pricing_checklist_hjqd_workflows_raw.json",
    "edit_file": "_jdy_pricing_checklist_hjqd_edit_raw.json",
}

# 流程名称切换时显示的关联块
VIS_GROUPS = {
    "安装图设计通知": [
        "link_install", "install_serial_no", "install_design_card_no",
        "install_order_person", "install_applicant", "install_department",
    ],
    "合同图纸（资料）领用申请": [
        "link_requisition", "req_serial_no", "req_contract_no",
        "req_applicant", "req_order_person", "req_department",
    ],
    "客服领图": [
        "link_cs_drawing", "cs_serial_no", "cs_contract_no",
        "cs_order_person", "cs_applicant", "cs_department",
    ],
    "中央研究院协同卡": [
        "link_coop_card", "coop_serial_no", "coop_contract_no",
        "coop_order_person", "coop_applicant", "coop_order_dept",
    ],
}

_APPROVER_FILL = {"has_issue", "issue_details"}


def should_keep_field(label: str, name: str, typ0: str) -> bool:
    if name in SYS_IDS:
        return True
    if typ0 in SKIP_TYPES:
        return False
    lab = label or ""
    if not lab or lab.startswith("_"):
        return False
    return True


def _slug_for(label: str, typ0: str, used: set[str], name: str) -> str:
    # 主流水号：type=sn；汇总文本「流水号」→ summary_serial_no
    if label == "流水号" and typ0 != "sn" and "serial_no" in used:
        base = "summary_serial_no"
    else:
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
        typ0 = (c.get("type") or "").lower()
        if not should_keep_field(lab, name, typ0):
            continue
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
        fd = {"id": _slug_for(lab, typ0, used, name), "type": typ, "label": lab}
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
        if name in SYS_IDS:
            continue
        if typ0 in SKIP_TYPES:
            continue
        if not lab or not should_keep_field(lab, name, typ0):
            continue

        # 主流水号：JDY type=sn → HJQD-yyyyMMdd + 5 位不重置
        if typ0 == "sn":
            fd = {
                "id": "serial_no",
                "type": "auto_number",
                "label": "流水号",
                "props": {
                    "serial_rules": [
                        {"type": "text", "value": "HJQD-"},
                        {"type": "date", "format": "yyyyMMdd"},
                        {
                            "type": "counter",
                            "digits": 5,
                            "fixed": True,
                            "reset_period": "none",
                            "initial_value": 1,
                        },
                    ],
                },
                "available_on_create": True,
                "fill_stage": "initiator",
            }
            used.add("serial_no")
            if name:
                fd["jdy_widget"] = name
            out.append(fd)
            continue

        slug = _slug_for(lab, typ0, used, name)
        typ = map_type(typ0)
        if typ0 in ("sn",):
            typ = "text"
        if typ0 == "linkfield":
            typ = "text"
        if typ0 == "image":
            typ = "file"
        if typ0 == "upload":
            typ = "file"
        opts = options_of(f)
        if typ == "select" and not opts:
            typ = "text"
        fd: dict = {"id": slug, "type": typ, "label": lab.rstrip("*")}
        if f.get("required") or lab.endswith("*"):
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
        if slug in _APPROVER_FILL:
            fd["available_on_create"] = False
            fd["fill_stage"] = "approver"
        else:
            fd.setdefault("available_on_create", True)
            fd.setdefault("fill_stage", "initiator")
        out.append(fd)
    return out


def unwrap_wf(raw: dict) -> dict:
    if isinstance(raw, dict) and "workflow_config" in raw:
        return raw
    if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
        return raw["data"]
    return raw


def build_rules(fields: list[dict]) -> list[dict]:
    ids = {f["id"] for f in fields}
    rules: list[dict] = []
    for process_val, targets in VIS_GROUPS.items():
        present = [t for t in targets if t in ids]
        if not present:
            continue
        rules.append({
            "id": f"vis_process_{abs(hash(process_val)) % 10_000_000}",
            "type": "visibility",
            "target_field_ids": present,
            "condition": {"field": "process_name", "operator": "eq", "value": process_val},
            "action": {"visible": True},
        })
    if "has_issue" in ids and "issue_details" in ids:
        rules.append({
            "id": "vis_issue_details_when_yes",
            "type": "visibility",
            "target_field_id": "issue_details",
            "condition": {"field": "has_issue", "operator": "eq", "value": "是"},
            "action": {"visible": True},
        })
    return rules


def apply_finance_issue_editable(nodes: list[dict], notes: list[str]) -> None:
    """财务节点：核价清单是否有问题 / 问题明细可填。"""
    for n in nodes:
        if not isinstance(n, dict) or n.get("name") != "财务":
            continue
        perms = list(n.get("field_perms") or [])
        by_field = {
            p.get("field"): p for p in perms
            if isinstance(p, dict) and p.get("field")
        }
        for fid in ("has_issue", "issue_details"):
            if fid in by_field:
                by_field[fid]["access"] = "editable"
            else:
                perms.append({"field": fid, "access": "editable"})
        n["field_perms"] = perms
        notes.append("财务：has_issue / issue_details → editable")
        break


def gen_one() -> dict:
    fields_raw = json.loads((OUT / FORM["fields_file"]).read_text(encoding="utf-8"))
    wf_raw = unwrap_wf(json.loads((OUT / FORM["wf_file"]).read_text(encoding="utf-8")))
    widget_limits = load_widget_limits_from_edit_raw(OUT / FORM["edit_file"])
    fields = build_fields(fields_raw, widget_limits)

    # 流程名称必填
    for fd in fields:
        if fd["id"] == "process_name":
            fd["required"] = True
            fd["label"] = "流程名称"

    rules = build_rules(fields)
    nodes, routes, notes = build_flow(wf_raw, fields, FORM["title"])
    apply_finance_issue_editable(nodes, notes)

    # 确保审批填写字段标记不被 optAuth 覆盖回 initiator
    for fd in fields:
        if fd["id"] in _APPROVER_FILL:
            fd["available_on_create"] = False
            fd["fill_stage"] = "approver"

    pack = {
        FORM["key"]: {
            "name": FORM["title"],
            "field_definitions": fields,
            "rule_definitions": rules,
            "flow_nodes": nodes,
            "flow_routes": routes,
            "notes": notes,
            "jdy": {
                "app": "584658417562f37a227fa805",
                "entry": FORM["entry"],
                "menu": "中央研究院 / 研究院统计 / 核价清单 / 核价清单传递流程HJQD",
            },
        }
    }
    return pack


def main() -> None:
    pack = gen_one()
    one = pack[FORM["key"]]
    GEN.write_text(
        "# -*- coding: utf-8 -*-\n"
        '"""Auto-generated from docs/product/_jdy_pricing_checklist_hjqd_* dumps. Do not edit by hand."""\n'
        "from __future__ import annotations\n"
        "import json\n\n"
        f"PRICING_CHECKLIST_HJQD_JDY = json.loads(r'''{json.dumps(pack, ensure_ascii=False)}''')\n",
        encoding="utf-8",
    )
    print(
        f"wrote {GEN.name} fields={len(one['field_definitions'])} "
        f"rules={len(one['rule_definitions'])} "
        f"nodes={len(one['flow_nodes'])} routes={len(one['flow_routes'])}"
    )
    for n in one["notes"][:12]:
        print(" note:", n)


if __name__ == "__main__":
    main()
