# -*- coding: utf-8 -*-
"""Generate CRM builtin 售前服务通知 from JDY dumps.

Sources:
  docs/product/_jdy_presale_service_notice_{fields,workflows_raw,edit_raw}.json
Output:
  backend/app/domains/lowcode/_presale_service_notice_generated.py
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
    label_of,
    load_widget_limits_from_edit_raw,
    map_condition,
    map_type,
    options_of,
    or_merge,
    widget_slug_map,
)

OUT = Path(__file__).resolve().parents[2] / "docs" / "product"
GEN = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "domains"
    / "lowcode"
    / "_presale_service_notice_generated.py"
)

SOFT_NOISE_KEYS = ("辅助", "已取消", "打印模板", "筛选用", "公式的", "主键", "离职")
HARD_DROP_KEYS = ("取消", "停用", "不用显示", "迁移提醒")
HARD_DROP_LABELS = frozenset({"迁移提醒", "人员查看"})
SYS_IDS = {"creator", "createTime", "updateTime", "appId", "entryId", "_id"}
SKIP_TYPES = {
    "separator", "button", "pagebreak", "hint", "flowstate",
    "aggregation", "linkquery", "formula",
}

TITLE_SLUG = {
    "流程编号": "serial_no",
    "申请人": "applicant",
    "所属部门": "department",
    "是否智能化": "is_smart",
    "是否需要金微星去现场": "need_jwx_onsite",
    "项目状态": "project_status",
    "智能化项目状态": "smart_project_status",
    "附件": "attachments",
    "希望派遣人员": "desired_staff",
    "合同号": "contract_no",
    "服务地点": "service_location",
    "服务时间": "service_time",
    "预计天数": "estimated_days",
    "联系人/联系电话": "contact_phone",
    "有无图纸及前期技术": "drawing_tech_status",
    "服务内容": "service_content",
    "工作日程计划": "work_schedule",
    "日期时间": "schedule_datetime",
    "工作日程": "schedule_item",
    "备注": "remark",
    "人员协调": "staff_coordination",
    "产品名称": "product_name",
    "规格型号": "spec_model",
    "测绘人": "surveyor",
    "测绘数据": "survey_data",
    "名称": "item_name",
    "数量": "qty",
    "单位": "unit",
    "单重": "unit_weight",
    "是否需要新疆威猛人员": "need_xjwm_staff",
    "新疆威猛人员": "xjwm_staff",
    "其他说明": "other_notes",
}

FORM = {
    "key": "presale_service_notice",
    "title": "售前服务通知",
    "entry": "5e79b7e9b587cc0006b632d7",
    "route": "/presale-service-notices",
    "fields_file": "_jdy_presale_service_notice_fields.json",
    "wf_file": "_jdy_presale_service_notice_workflows_raw.json",
    "edit_file": "_jdy_presale_service_notice_edit_raw.json",
    "md_file": "_jdy_presale_service_notice_forms.md",
}

# 审批节点填写，创建阶段不填
_APPROVER_FILL = frozenset({
    "staff_coordination",
    "product_name",
    "spec_model",
    "surveyor",
    "survey_data",
    "xjwm_staff",
})

# 创建必填（简道云 allowBlank=false，不含审批字段）
_CREATE_REQUIRED = frozenset({
    "applicant",
    "department",
    "is_smart",
    "need_jwx_onsite",
    "service_location",
    "service_time",
    "estimated_days",
    "contact_phone",
    "need_xjwm_staff",
})


def is_hard_drop(label: str, name: str) -> bool:
    if name in SYS_IDS:
        return True
    lab = (label or "").strip()
    if not lab or lab.startswith("_"):
        return True
    if lab in HARD_DROP_LABELS:
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
        if slug == "serial_no" or lab == "流程编号":
            fd = {
                "id": "serial_no",
                "type": "auto_number",
                "label": "流程编号",
                "props": {
                    "serial_rules": [
                        {"type": "text", "value": "24.13-"},
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
        if typ0 == "combo" and lab == "合同号":
            typ = "contract"
        if typ0 == "linkfield":
            typ = "text"
        opts = options_of(f)
        if typ == "select" and not opts:
            typ = "text"
        fd: dict = {"id": slug, "type": typ, "label": lab}
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
        if slug == "applicant":
            fd.setdefault("props", {})["default_current_user"] = True
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


def load_presale_linkage() -> dict:
    path = OUT / FORM["edit_file"]
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    content = raw.get("data") or raw.get("content") or raw
    attr = content.get("attr") or {}
    link = attr.get("linkage") or content.get("linkage") or {}
    if link.get("fieldShowRules"):
        return link
    # presale edit_raw: fieldShowRules on content root
    fsr = content.get("fieldShowRules") or []
    return {"fieldShowRules": fsr, "subformFieldShowRules": content.get("subformFieldShowRules") or []}


def build_presale_rules(fields: list[dict], linkage: dict) -> list[dict]:
    """Convert JDY filter/fields fieldShowRules → CRM visibility (+ conditional required)."""
    widget_slug = widget_slug_map(fields)
    by_target: dict[str, list[dict]] = {}

    for rule in linkage.get("fieldShowRules") or []:
        filt = rule.get("filter") or {}
        cond = map_condition(filt, widget_slug)
        if not cond:
            continue
        for wid in rule.get("fields") or rule.get("show_fields") or []:
            if isinstance(wid, dict):
                wid = wid.get("widget") or wid.get("name")
            slug = widget_slug.get(wid) if wid else None
            if not slug:
                continue
            by_target.setdefault(slug, []).append(cond)

    rules: list[dict] = []
    for slug, conds in by_target.items():
        uniq: list[dict] = []
        seen: set[str] = set()
        for c in conds:
            key = json.dumps(c, sort_keys=True, ensure_ascii=False)
            if key in seen:
                continue
            seen.add(key)
            uniq.append(c)
        merged = or_merge(uniq)
        rules.append({
            "id": f"psn_vis_{slug}",
            "type": "visibility",
            "target_field_id": slug,
            "condition": merged,
            "action": {"visible": True},
        })
        # 简道云 allowBlank=false 且由联动控制显示的字段 → 显示时必填
        if slug in (
            "contract_no",
            "desired_staff",
            "smart_project_status",
            "project_status",
            "xjwm_staff",
        ):
            rules.append({
                "id": f"psn_req_{slug}",
                "type": "required",
                "target_field_id": slug,
                "condition": merged,
                "action": {"required": True},
            })
    return rules


def apply_conditional_initiator_required(fields: list[dict]) -> None:
    """互斥的项目/智能化状态：创建时按 is_smart 分支必填。"""
    ids = {f["id"] for f in fields}
    for fd in fields:
        if fd["id"] == "project_status" and "project_status" in ids:
            fd["required"] = False
        if fd["id"] == "smart_project_status" and "smart_project_status" in ids:
            fd["required"] = False
        if fd["id"] == "desired_staff":
            fd["required"] = False
        if fd["id"] == "contract_no":
            fd["required"] = False
        if fd["id"] == "xjwm_staff":
            fd["required"] = False


def patch_presale_cc_nodes(nodes: list[dict]) -> None:
    """抄送：简道云仅 creator，CRM 额外抄送表单「申请人」。"""
    want = {
        "type": "mixed",
        "value": [
            {"type": "creator"},
            {"type": "form_field_person", "value": "applicant"},
        ],
    }
    for n in nodes:
        if n.get("type") == "cc":
            n["approver_rule"] = want


def gen_one() -> dict:
    fields_raw = json.loads((OUT / FORM["fields_file"]).read_text(encoding="utf-8"))
    wf_raw = unwrap_wf(json.loads((OUT / FORM["wf_file"]).read_text(encoding="utf-8")))
    widget_limits = load_widget_limits_from_edit_raw(OUT / FORM["edit_file"])
    fields = build_fields(fields_raw, widget_limits)
    apply_conditional_initiator_required(fields)
    from app.domains.lowcode.presale_service_notice_fields import apply_presale_service_notice_fields
    apply_presale_service_notice_fields(fields)
    linkage = load_presale_linkage()
    rules = build_presale_rules(fields, linkage)
    nodes, routes, notes = build_flow(wf_raw, fields, FORM["title"])
    patch_presale_cc_nodes(nodes)
    notes.insert(0, "对齐简道云销售中心「售前服务通知流程」；流水号 24.13-+yyyyMMdd+四位日序。")
    notes.append("抄送节点：发起人本人 + 表单申请人（组合去重）。")

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
        f"# {FORM['title']} — CRM 字段对照（简道云售前服务通知流程）",
        "",
        f"> 简道云 app=`5de0b3e85600ec0006f420f2` entry=`{FORM['entry']}`",
        "",
        f"- **builtin key**: `{FORM['key']}`",
        f"- **路由**: `{FORM['route']}`",
        f"- **字段数（去噪后）**: {len(fields)}",
        f"- **静态必填**: {n_req}",
        f"- **流程节点数（CRM）**: {len(nodes)} / 连线 {len(routes)}",
        f"- **联动规则**: {len(rules)}",
        f"- **流水号**: `24.13-` + yyyyMMdd + 四位日序",
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


def main() -> None:
    result = gen_one()
    GEN.write_text(
        "# -*- coding: utf-8 -*\n"
        "\"\"\"Auto-generated from docs/product/_jdy_presale_service_notice_* dumps. "
        "Do not edit by hand.\"\"\"\n"
        "from __future__ import annotations\n"
        "import json\n\n"
        f"PRESALE_SERVICE_NOTICE_JDY = json.loads(r'''{json.dumps(result, ensure_ascii=False)}''')\n",
        encoding="utf-8",
    )
    print("wrote", GEN)


if __name__ == "__main__":
    main()
