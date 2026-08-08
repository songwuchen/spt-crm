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


# 方案管理不需要：订货人/设计人文本桩、前期沟通设计员文本、是否解密、项目号/是否新项目/业务员、
# 「修改方案 / 非出方案图物料特性」明细、是否上交图纸（下图类型选项仍保留）
DROP_FIELD_IDS = frozenset({
    "order_person_text",
    "designer_text",
    "pre_designer_text",  # 保留选人 pre_designers，去掉文本桩
    "need_decrypt",
    "need_decrypt_note",
    "project_no",
    "is_new_project",
    "sales_person",
    "change_scheme",
    "non_scheme_material",
    "need_submit_drawing",
    # 业务打分三项及派生字段：方案管理不再使用
    "score_attitude",
    "score_progress",
    "score_skill",
    "score_total",
    "score_date",
})

# 业务上只需选到「日」的字段（简道云多为 datetime，CRM 统一为 date）
DATE_ONLY_FIELD_IDS = frozenset({
    "apply_datetime",
    "order_date",
    "card_date",
    "require_draw_date",
})

# 这些字段只用「scheme_type 显隐」，不套简道云原条件（否则后写规则会盖掉类型显隐）
# 前期沟通设计人员：选人始终随「无合同号」显示，不按「是否小萌」再藏
SKIP_JDY_VIS_FIELD_IDS = frozenset({
    "pre_designers",
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
    # 原规则外包 scheme_type；同 target 多条 visibility 后写会覆盖，
    # 对共享字段的 visibility 合并为 OR。
    # 独有字段：若已有简道云显隐，只保留合并后的条件，不再加「仅 scheme_type」宽规则
    # （否则审批页 last-wins / 或双规则会把下图类型明细等一直打开）。
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
    for skip_id in SKIP_JDY_VIS_FIELD_IDS:
        req_vis.pop(skip_id, None)
        ins_vis.pop(skip_id, None)

    # 独有字段：按类型显隐（无 JDY 条件时）
    for fid in sorted(req_only):
        if fid in req_vis:
            continue
        if fid == "need_gm_approval":
            # 审批节点填写：有/无合同号总工都要用，不按 scheme_type 隐藏
            continue
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
        if fid in ins_vis:
            continue
        rules.append({
            "id": f"sm_vis_ins_only_{fid}",
            "type": "visibility",
            "target_field_id": fid,
            "condition": {"field": "scheme_type", "operator": "eq", "value": "install"},
            "action": {"visible": True},
        })

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

    # 独有字段的静态 required 改为「随 scheme_type 的条件必填」：
    # 避免显隐规则未生效时，对侧（如无合同号）仍被「附件/图片名称」拦住。
    def _rule_targets(rule: dict) -> set[str]:
        tids = set(rule.get("target_field_ids") or [])
        if rule.get("target_field_id"):
            tids.add(rule["target_field_id"])
        return tids

    required_ruled: set[str] = set()
    for r in rules:
        if r.get("type") == "required":
            required_ruled |= _rule_targets(r)

    by_id = {f["id"]: f for f in fields}
    # 这些字段只做类型显隐，不自动抬成条件必填（业务上常选填；避免「规则只有显示、提交却拦必填」）
    OPTIONAL_EXCLUSIVE = {
        "attachment_name", "attachment_names", "attachments", "attachments_no_image", "images",
        "remark",  # 备注：表单上未设必填，勿因安装图源 required 抬成条件必填
    }
    for fid in sorted(req_only):
        f = by_id.get(fid)
        if not f or not f.get("required"):
            continue
        f["required"] = False
        if fid in OPTIONAL_EXCLUSIVE or fid in required_ruled:
            continue
        rules.append({
            "id": f"sm_req_req_only_{fid}",
            "type": "required",
            "target_field_id": fid,
            "condition": {"field": "scheme_type", "operator": "eq", "value": "requisition"},
            "action": {"required": True},
        })
        required_ruled.add(fid)
    for fid in sorted(ins_only):
        if fid == "apply_or_change":
            continue
        f = by_id.get(fid)
        if not f or not f.get("required"):
            continue
        f["required"] = False
        if fid in OPTIONAL_EXCLUSIVE or fid in required_ruled:
            continue
        rules.append({
            "id": f"sm_req_ins_only_{fid}",
            "type": "required",
            "target_field_id": fid,
            "condition": {"field": "scheme_type", "operator": "eq", "value": "install"},
            "action": {"required": True},
        })
        required_ruled.add(fid)

    # 去掉附件类字段上残留的条件必填（含简道云带过来的）
    def _drop_attach_required(rule: dict) -> bool:
        if rule.get("type") != "required":
            return True
        tids = set(rule.get("target_field_ids") or [])
        if rule.get("target_field_id"):
            tids.add(rule["target_field_id"])
        return not (tids & OPTIONAL_EXCLUSIVE)

    rules = [r for r in rules if _drop_attach_required(r)]
    for fid in OPTIONAL_EXCLUSIVE:
        if fid in by_id:
            by_id[fid]["required"] = False

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
    for f in fields:
        # 对齐 JDY usergroup：转新乡、工艺包装须多选
        if f.get("id") == "transfer_packaging_users":
            f["type"] = "person_multi"
        # 下图类型=出方案图 时三张明细默认带 1 行空行，方便直接填
        if f.get("id") in ("scheme_detail", "install_env", "scheme_material"):
            f["props"] = {**(f.get("props") or {}), "ensure_min_rows": 1}
        # 日期字段：只选日期，不要时分
        if f.get("id") in DATE_ONLY_FIELD_IDS and f.get("type") in ("date", "datetime", None):
            f["type"] = "date"
            props = dict(f.get("props") or {})
            props["show_time"] = False
            props["date_only"] = True
            f["props"] = props

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
    # 是否需要总经理审批：有/无合同号总工审批都要用，去掉仅 requisition 显隐
    rules = [
        r for r in cleaned_rules
        if not (
            r.get("type") == "visibility"
            and (
                r.get("target_field_id") == "apply_or_change"
                or "apply_or_change" in (r.get("target_field_ids") or [])
                or r.get("target_field_id") == "need_gm_approval"
                or "need_gm_approval" in (r.get("target_field_ids") or [])
            )
        )
    ]

    # 物料特性子表：显隐条件改绑用户实际填写的单选 need_screening_eff_star
    # （简道云触发器是文本桩 need_screening_eff，CRM 界面只露出 _star 单选）
    def _rewrite_screening_trigger(node: dict | list | None) -> None:
        if isinstance(node, list):
            for x in node:
                _rewrite_screening_trigger(x if isinstance(x, (dict, list)) else None)
            return
        if not isinstance(node, dict):
            return
        if node.get("field") == "need_screening_eff":
            node["field"] = "need_screening_eff_star"
        if node.get("field") == "need_screening_eff_2":
            # non_scheme 已删；保留无害
            pass
        for x in node.get("cond") or []:
            if isinstance(x, dict):
                _rewrite_screening_trigger(x)

    for r in rules:
        if isinstance(r, dict) and isinstance(r.get("condition"), dict):
            _rewrite_screening_trigger(r["condition"])

    # 粒度组成：随「筛分效率是否有要求=是」显示（简道云出方案图表未列，业务要求与其它后续字段一致）
    screening_yes = {
        "rel": "and",
        "cond": [
            {"field": "scheme_type", "operator": "eq", "value": "install"},
            {"field": "need_screening_eff_star", "operator": "eq", "value": "是"},
        ],
    }
    if not any(
        isinstance(r, dict)
        and r.get("type") == "visibility"
        and r.get("target_field_id") == "particle_composition"
        for r in rules
    ):
        rules.append({
            "id": "sm_vis_particle_composition_screening",
            "type": "visibility",
            "target_field_id": "particle_composition",
            "condition": screening_yes,
            "action": {"visible": True},
        })

    # 物料特性：条件展示列去掉静态 required，改走条件必填（避免选「否」仍被拦）
    for f in fields:
        if f.get("id") != "scheme_material":
            continue
        for col in f.get("detail_table_columns") or []:
            if col.get("id") in (
                "particle_dist_star", "screening_eff_star", "moisture_star",
                "particle_dist", "screening_eff", "moisture", "particle_composition",
            ):
                col["required"] = False

    # 总工审批：有/无合同号均必填「是否需要总经理审批」
    for n in flow_nodes:
        if not isinstance(n, dict) or n.get("type") != "approval":
            continue
        if n.get("name") != "总工审批":
            continue
        perms = [
            p for p in (n.get("field_perms") or [])
            if isinstance(p, dict) and p.get("field")
        ]
        by_f = {str(p["field"]): str(p.get("access") or "editable") for p in perms}
        by_f["need_gm_approval"] = "required"
        n["field_perms"] = [{"field": k, "access": v} for k, v in by_f.items()]

    # 方案管理不再使用业务打分字段：从审批节点 field_perms 剥离
    score_drop = {
        "score_attitude", "score_progress", "score_skill", "score_total", "score_date",
    }
    for n in flow_nodes:
        if not isinstance(n, dict):
            continue
        perms = n.get("field_perms") or []
        if not perms:
            continue
        n["field_perms"] = [
            p for p in perms
            if isinstance(p, dict) and p.get("field") not in score_drop
        ]

    # 无合同号总工：need_gm=是 → 总经理审批 → 设计指派；保留小萌→周经理；抄送仅在不需总经理审批时
    _patch_install_need_gm_flow(flow_nodes, flow_routes)

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
            "下图类型含 出方案图 / 出测绘图 / 修改方案 / 领图（选项保留）。",
            "不含 change_scheme / non_scheme_material 明细表。",
            "不含业务打分：score_attitude / score_progress / score_skill / score_total / score_date。",
            "总工审批（有/无合同号）必填 need_gm_approval；无合同号按 need_gm 走总经理审批。",
            "申请人默认当前用户；合同号 type=contract 引用合同管理；"
            "不含 order_person_text / designer_text / need_decrypt / project_no / is_new_project / sales_person。",
        ],
    }


def _patch_install_need_gm_flow(flow_nodes: list, flow_routes: list) -> None:
    """无合同号：总工按 need_gm_approval 分支到总经理审批。"""
    req_gm = next((n for n in flow_nodes if isinstance(n, dict) and n.get("id") == "req_n18"), None)
    if not any(isinstance(n, dict) and n.get("id") == "ins_n_gm" for n in flow_nodes):
        gm_rule = copy.deepcopy((req_gm or {}).get("approver_rule")) or {
            "type": "specified_user",
            "value": "02336214315748",
        }
        flow_nodes.append({
            "id": "ins_n_gm",
            "type": "approval",
            "name": "总经理审批",
            "approver_rule": gm_rule,
            "multi_mode": (req_gm or {}).get("multi_mode") or "or_sign",
            "empty_strategy": (req_gm or {}).get("empty_strategy") or "auto_approve",
            "field_perms": [],
        })

    kept = [r for r in flow_routes if not (isinstance(r, dict) and r.get("source") == "ins_n7")]
    kept.extend([
        {
            "id": "ins_r_n7_gm",
            "source": "ins_n7",
            "target": "ins_n_gm",
            "exclusive_group": "ex_n7",
            "condition": {"field": "need_gm_approval", "operator": "eq", "value": "是"},
        },
        {
            "id": "ins_r_n7_zhou",
            "source": "ins_n7",
            "target": "ins_n9",
            "exclusive_group": "ex_n7",
            "condition": {"field": "is_xiaomeng", "operator": "eq", "value": "是"},
        },
        {
            "id": "ins_r_n7_design",
            "source": "ins_n7",
            "target": "ins_n5",
            "exclusive_group": "ex_n7",
            # else：不需总经理且非小萌
        },
        {
            "id": "ins_r_n7_cc_gm",
            "source": "ins_n7",
            "target": "ins_n12",
            "always": True,
            "condition": {"field": "need_gm_approval", "operator": "eq", "value": "否"},
        },
    ])
    # 总经理审批后进入设计指派
    if not any(
        isinstance(r, dict) and r.get("source") == "ins_n_gm" and r.get("target") == "ins_n5"
        for r in kept
    ):
        kept.append({
            "id": "ins_r_gm_design",
            "source": "ins_n_gm",
            "target": "ins_n5",
            "condition": None,
        })
    flow_routes[:] = kept


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
