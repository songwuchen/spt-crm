# -*- coding: utf-8 -*-
"""从 drawing_requisition + install_drawing_notice 合成独立表单 scheme_management。

产出: backend/app/domains/lowcode/_scheme_management_generated.py
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.domains.lowcode._drawing_jdy_generated import DRAWING_JDY  # noqa: E402

OUT = ROOT / "app" / "domains" / "lowcode" / "_scheme_management_generated.py"

SCHEME_TYPE = {
    "id": "scheme_type",
    "type": "radio",
    "label": "方案类型",
    "required": True,
    "options": [
        {"label": "有合同号 · 简易领图", "value": "requisition"},
        {"label": "无合同号 · 前期/投标方案", "value": "install"},
    ],
    "description": "有合同号走领用字段与审批；无合同号走安装图/投标方案字段与审批。",
}

# 可选关联商机（存商机 id）；与安装图侧的文本字段 project_no 无关
RELATED_PROJECT = {
    "id": "related_project",
    "type": "project",
    "label": "关联商机",
    "required": False,
    "description": "可选。关联一条商机，便于从方案回溯项目。",
}

# 关联客户（与合同登记一致）：存客户 id；公司名称由回填得到
RELATED_CUSTOMER = {
    "id": "related_customer",
    "type": "customer",
    "label": "关联客户",
    "required": False,
    "description": "从客户管理中选择；可不选商机只选客户。",
    "available_on_create": True,
    "fill_stage": "initiator",
}


# 方案管理不需要：订货人/设计人文本桩、是否解密、项目号/是否新项目/业务员
DROP_FIELD_IDS = frozenset({
    "order_person_text",
    "designer_text",
    "need_decrypt",
    "need_decrypt_note",
    "project_no",
    "is_new_project",
    "sales_person",
})


def _and_scheme(scheme: str, cond: dict | None) -> dict:
    scheme_cond = {"field": "scheme_type", "operator": "eq", "value": scheme}
    if not cond:
        return scheme_cond
    # __always 占位：仅保留 scheme_type
    if isinstance(cond, dict) and cond.get("field") == "__always":
        return scheme_cond
    return {"rel": "and", "cond": [scheme_cond, cond]}


def _wrap_rule(rule: dict, scheme: str, prefix: str) -> dict:
    r = copy.deepcopy(rule)
    r["id"] = f"{prefix}{r.get('id', 'rule')}"
    r["condition"] = _and_scheme(scheme, r.get("condition") if isinstance(r.get("condition"), dict) else None)
    return r


def _merge_field(a: dict, b: dict) -> dict:
    out = copy.deepcopy(a)
    if b.get("required"):
        out["required"] = True
    if not out.get("options") and b.get("options"):
        out["options"] = copy.deepcopy(b["options"])
    if not out.get("detail_table_columns") and b.get("detail_table_columns"):
        out["detail_table_columns"] = copy.deepcopy(b["detail_table_columns"])
    if not out.get("description") and b.get("description"):
        out["description"] = b["description"]
    # 类型冲突时保留 a（领用侧）
    return out


def _prefix_flow(nodes: list, routes: list, prefix: str, scheme: str) -> tuple[list, list]:
    id_map: dict[str, str] = {}
    for n in nodes:
        oid = n["id"]
        id_map[oid] = oid if oid in ("start", "end") else f"{prefix}{oid}"

    new_nodes = []
    for n in nodes:
        if n["id"] in ("start", "end"):
            continue
        nn = copy.deepcopy(n)
        nn["id"] = id_map[n["id"]]
        new_nodes.append(nn)

    new_routes = []
    for i, r in enumerate(routes):
        nr = copy.deepcopy(r)
        nr["id"] = f"{prefix}{r.get('id') or f'r_{i}'}"
        nr["source"] = id_map[r["source"]]
        nr["target"] = id_map[r["target"]]
        if r["source"] == "start":
            raw = r.get("condition") if isinstance(r.get("condition"), dict) else None
            nr["condition"] = _and_scheme(scheme, raw)
        new_routes.append(nr)
    return new_nodes, new_routes


def build() -> dict:
    req = DRAWING_JDY["drawing_requisition"]
    ins = DRAWING_JDY["install_drawing_notice"]

    req_fields = {f["id"]: f for f in req["field_definitions"]}
    ins_fields = {f["id"]: f for f in ins["field_definitions"]}
    shared = set(req_fields) & set(ins_fields)
    req_only = set(req_fields) - shared
    ins_only = set(ins_fields) - shared

    fields: list[dict] = [
        copy.deepcopy(SCHEME_TYPE),
        copy.deepcopy(RELATED_PROJECT),
        copy.deepcopy(RELATED_CUSTOMER),
    ]
    # 共享字段：领用顺序优先，再补安装图独有顺序里未出现的共享项（已在 shared 一次加入）
    seen: set[str] = set()
    for f in req["field_definitions"]:
        fid = f["id"]
        if fid in shared and fid not in seen:
            fields.append(_merge_field(f, ins_fields[fid]))
            seen.add(fid)
    for f in ins["field_definitions"]:
        fid = f["id"]
        if fid in shared and fid not in seen:
            fields.append(_merge_field(ins_fields[fid], req_fields[fid]))
            seen.add(fid)

    for f in req["field_definitions"]:
        if f["id"] in req_only:
            fields.append(copy.deepcopy(f))
    for f in ins["field_definitions"]:
        if f["id"] in ins_only:
            fields.append(copy.deepcopy(f))

    rules: list[dict] = []
    # 独有字段：按类型显隐
    for fid in sorted(req_only):
        rules.append({
            "id": f"sm_vis_req_only_{fid}",
            "type": "visibility",
            "target_field_id": fid,
            "condition": {"field": "scheme_type", "operator": "eq", "value": "requisition"},
            "action": {"visible": True},
        })
    for fid in sorted(ins_only):
        if fid == "apply_or_change":
            # 申请事由/修改事项：始终展示，不按 scheme_type 显隐
            continue
        rules.append({
            "id": f"sm_vis_ins_only_{fid}",
            "type": "visibility",
            "target_field_id": fid,
            "condition": {"field": "scheme_type", "operator": "eq", "value": "install"},
            "action": {"visible": True},
        })

    # 原规则外包 scheme_type；同 target 多条 visibility 后写会覆盖，
    # 对共享字段的 visibility 合并为 OR。
    def collect_vis(side_rules: list, scheme: str, prefix: str) -> tuple[dict[str, list], list[dict]]:
        by_target: dict[str, list] = {}
        other: list[dict] = []
        for rule in side_rules:
            wrapped = _wrap_rule(rule, scheme, prefix)
            if wrapped.get("type") == "visibility":
                tid = wrapped.get("target_field_id")
                tids = list(wrapped.get("target_field_ids") or ([tid] if tid else []))
                for t in tids:
                    by_target.setdefault(t, []).append(wrapped)
            else:
                other.append(wrapped)
        return by_target, other

    req_vis, req_other = collect_vis(req.get("rule_definitions") or [], "requisition", "sm_req_")
    ins_vis, ins_other = collect_vis(ins.get("rule_definitions") or [], "install", "sm_ins_")

    rules.extend(req_other)
    rules.extend(ins_other)

    all_vis_targets = set(req_vis) | set(ins_vis)
    for tid in sorted(all_vis_targets):
        if tid == "apply_or_change":
            continue
        parts = []
        for w in req_vis.get(tid, []):
            parts.append(w["condition"])
        for w in ins_vis.get(tid, []):
            parts.append(w["condition"])
        if len(parts) == 1:
            rules.append({
                "id": f"sm_vis_merged_{tid}",
                "type": "visibility",
                "target_field_id": tid,
                "condition": parts[0],
                "action": {"visible": True},
            })
        else:
            rules.append({
                "id": f"sm_vis_merged_{tid}",
                "type": "visibility",
                "target_field_id": tid,
                "condition": {"rel": "or", "cond": parts},
                "action": {"visible": True},
            })

    # 流程：start 按 scheme_type 分叉
    req_nodes, req_routes = _prefix_flow(
        req.get("flow_nodes") or [], req.get("flow_routes") or [], "req_", "requisition",
    )
    ins_nodes, ins_routes = _prefix_flow(
        ins.get("flow_nodes") or [], ins.get("flow_routes") or [], "ins_", "install",
    )
    flow_nodes = [
        {"id": "start", "type": "start", "name": "发起"},
        *req_nodes,
        *ins_nodes,
        {"id": "end", "type": "end", "name": "结束"},
    ]
    flow_routes = [*req_routes, *ins_routes]

    # 申请人默认当前用户；合同号改为引用合同管理；去掉订货人文本 / 是否解密等
    for f in fields:
        if f.get("id") == "applicant":
            props = dict(f.get("props") or {})
            props["default_current_user"] = True
            f["props"] = props
        if f.get("id") == "contract_no":
            f["type"] = "contract"
            f["label"] = "合同号"
            f["description"] = "从合同管理中选择合同。"
            f.pop("options", None)
        if f.get("id") == "offices_multi":
            f["type"] = "department_multi"
        if f.get("id") == "customer_name":
            # 公司名称：文本回填，不作为客户选择器
            f["type"] = "text"
            f["label"] = "公司名称"
            f["description"] = "由关联商机 / 关联客户自动回填。"
            f["props"] = {**(f.get("props") or {}), "read_only": True}
            f.pop("options", None)
        if f.get("id") == "apply_or_change":
            f["type"] = "textarea"
            f["label"] = "申请事由/修改事项(如表述不完，请填至备注)"
            f["description"] = ""
            f["available_on_create"] = True
            f["fill_stage"] = "initiator"
    fields = [f for f in fields if f.get("id") not in DROP_FIELD_IDS]

    def _cond_refs_drop(cond: dict | None) -> bool:
        if not isinstance(cond, dict):
            return False
        if cond.get("field") in DROP_FIELD_IDS:
            return True
        return any(_cond_refs_drop(c) for c in (cond.get("cond") or []) if isinstance(c, dict))

    def _rule_keep(rule: dict) -> bool:
        tids = set(rule.get("target_field_ids") or [])
        if rule.get("target_field_id"):
            tids.add(rule["target_field_id"])
        if tids & DROP_FIELD_IDS:
            return False
        if _cond_refs_drop(rule.get("condition") if isinstance(rule.get("condition"), dict) else None):
            return False
        return True

    cleaned_rules = [r for r in rules if _rule_keep(r)]
    # 申请事由/修改事项：始终显示（不限方案类型 / 是否小萌）
    rules = [
        r for r in cleaned_rules
        if not (
            r.get("type") == "visibility"
            and (
                r.get("target_field_id") == "apply_or_change"
                or "apply_or_change" in (r.get("target_field_ids") or [])
            )
        )
    ]

    return {
        "name": "方案管理",
        "field_definitions": fields,
        "rule_definitions": rules,
        "flow_nodes": flow_nodes,
        "flow_routes": flow_routes,
        "notes": [
            "合成自 drawing_requisition + install_drawing_notice；独立 code=scheme_management。",
            "scheme_type=requisition|install 分流字段与审批。",
            "related_project / related_customer 可选；公司名称文本由二者回填。",
            "下图类型含 出方案图 / 出测绘图 / 修改方案 / 领图。",
            "申请人默认当前用户；合同号 type=contract 引用合同管理；"
            "不含 order_person_text / designer_text / need_decrypt / project_no / is_new_project / sales_person。",
        ],
    }


def main() -> None:
    pack = build()
    body = json.dumps({"scheme_management": pack}, ensure_ascii=False)
    text = (
        "# -*- coding: utf-8 -*-\n"
        '"""Auto-generated by scripts/_gen_scheme_management.py. Do not edit by hand."""\n'
        "from __future__ import annotations\n"
        "import json\n\n"
        f"SCHEME_MANAGEMENT_JDY = json.loads(r'''{body}''')\n"
    )
    OUT.write_text(text, encoding="utf-8")
    sm = pack
    print(
        f"wrote {OUT}\n"
        f"  fields={len(sm['field_definitions'])} rules={len(sm['rule_definitions'])} "
        f"nodes={len(sm['flow_nodes'])} routes={len(sm['flow_routes'])}"
    )


if __name__ == "__main__":
    main()
