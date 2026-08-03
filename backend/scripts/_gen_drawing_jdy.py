"""Generate CRM builtin fields + flow graphs from pulled JDY drawing dumps."""
from __future__ import annotations

import json
import re
from pathlib import Path

OUT = Path(r"g:\ruolin-a\spt-crm\docs\product")
GEN = Path(r"g:\ruolin-a\spt-crm\backend\app\domains\lowcode\_drawing_jdy_generated.py")

NOISE_KEYS = (
    "取消", "停用", "辅助", "已取消", "不用显示", "打印模板", "同一天", "补位",
    "count辅助", "240829", "240912", "240416", "0816", "260601", "20230112",
    "22/11/28", "230320",
)
SYS_IDS = {"creator", "createTime", "updateTime", "appId", "entryId", "_id"}
SKIP_TYPES = {"separator", "button", "pagebreak", "hint", "flowstate", "sn", "aggregation"}

TITLE_SLUG = {
    "日期时间": "apply_datetime",
    "部门": "department",
    "申请人": "applicant",
    "是否涉及企标图纸": "involve_std_drawing",
    "订货人": "order_person",
    "订货人（文本）": "order_person_text",
    "合同号": "contract_no",
    "申请事由": "apply_reason",
    "设计人": "designer",
    "设计人(文本)": "designer_text",
    "产品型号": "product_model",
    "图纸传递途径": "transfer_channel",
    "是否解密": "need_decrypt",
    "是否解密*": "need_decrypt_note",
    "图纸类型": "drawing_type",
    "附件/图片名称": "attachment_name",
    "附件": "attachments",
    "图片": "images",
    "设计单分派": "design_dispatch",
    "转新乡、工艺包装": "transfer_packaging_users",
    "设计指派": "design_assignees",
    "科室": "offices",
    "下单日期": "order_date",
    "是否需要总经理审批": "need_gm_approval",
    "项目号辅助": "project_no_aux",
    "项目号（打印模板显示）": "project_no_print",
    "是否为新项目0816": "is_new_project",
    "项目号选择": "project_no",
    "业务员": "sales_person",
    "公司名称": "customer_name",
    "事项": "matter",
    "部门编号": "dept_code",
    "是否小萌方案": "is_xiaomeng",
    "新设计卡号": "design_card_no",
    "下图类型": "drawing_issue_type",
    "图纸类型（可多选）": "drawing_types",
    "领图目的": "pickup_purpose",
    "申请事由/修改事项": "apply_or_change",
    "*申请事由": "apply_reason_star",
    "下卡日期": "card_date",
    "前期沟通设计人员": "pre_designers",
    "要求交图时间": "require_draw_date",
    "安装位置": "install_position",
    "设备基础图纸": "foundation_drawing",
    "安装方式": "install_method",
    "注意": "attention",
    "附件名称": "attachment_names",
    "是否上交图纸": "need_submit_drawing",
    "科室多选": "offices_multi",
    "转孙伟、刘万涛": "transfer_sw_lwt",
    "附件（不能放图片）": "attachments_no_image",
    "出方案图填写明细": "scheme_detail",
    "安装环境和现场条件": "install_env",
    "修改方案": "change_scheme",
    "出方案图填写明细-物料特性": "scheme_material",
    "非出方案图填写明细-物料特性": "non_scheme_material",
    "前期沟通的设计员（文本）": "pre_designer_text",
    "态度分数": "score_attitude",
    "进度、准确性分数": "score_progress",
    "专业技能分数": "score_skill",
    "备注": "remark",
    "总分": "score_total",
    "打分日期": "score_date",
}


def label_of(f: dict) -> str:
    return (f.get("title") or f.get("text") or f.get("label") or "").strip()


def is_noise(label: str, name: str) -> bool:
    if name in SYS_IDS:
        return True
    lab = label or ""
    if any(k in lab for k in NOISE_KEYS):
        return True
    # 纯系统/空标签
    if not lab or lab.startswith("_"):
        return True
    return False


def map_type(t: str) -> str:
    t = (t or "").lower()
    return {
        "text": "text", "textarea": "textarea", "number": "number",
        "datetime": "datetime", "date": "date",
        "radiogroup": "radio", "radio": "radio",
        "checkboxgroup": "checkbox", "checkbox": "checkbox", "combocheck": "checkbox",
        "combo": "select", "select": "select",
        "user": "person", "usergroup": "person",
        "dept": "department", "department": "department", "deptgroup": "department",
        "upload": "file", "image": "file", "file": "file",
        "subform": "detail_table", "switch": "switch",
    }.get(t, "text")


def options_of(f: dict) -> list[dict]:
    items = f.get("items") or []
    out = []
    for it in items:
        if isinstance(it, dict):
            if it.get("type") and it.get("name"):
                continue  # nested widget
            v = it.get("text") or it.get("value") or it.get("label")
            if v is not None and str(v).strip() != "":
                s = str(v)
                out.append({"label": s, "value": s})
        elif it is not None:
            s = str(it)
            out.append({"label": s, "value": s})
    return out


def slug_for(label: str, used: set[str]) -> str:
    base = TITLE_SLUG.get(label)
    if not base:
        base = re.sub(r"[^a-zA-Z0-9]+", "_", label).strip("_").lower() or "field"
        if base[0].isdigit():
            base = "f_" + base
    slug = base
    i = 2
    while slug in used:
        slug = f"{base}_{i}"
        i += 1
    used.add(slug)
    return slug


def sub_columns(f: dict) -> list[dict]:
    cols = f.get("widgets") or []
    if not cols:
        cols = [x for x in (f.get("items") or []) if isinstance(x, dict) and x.get("type") and x.get("type") not in SKIP_TYPES]
    used: set[str] = set()
    out = []
    for c in cols:
        lab = label_of(c) or c.get("name") or "col"
        if is_noise(lab, c.get("name") or ""):
            continue
        typ = map_type(c.get("type") or "")
        if typ == "detail_table":
            continue
        fd = {"id": slug_for(lab, used), "type": typ, "label": lab}
        opts = options_of(c)
        if opts and typ in ("select", "radio", "checkbox"):
            fd["options"] = opts
        if c.get("name"):
            fd["jdy_widget"] = c["name"]
        out.append(fd)
    return out


def build_fields(raw: dict) -> list[dict]:
    data = raw.get("data", raw)
    fields = data.get("fields") if isinstance(data, dict) else data
    used: set[str] = set()
    out = []
    for f in fields or []:
        if not isinstance(f, dict):
            continue
        typ0 = (f.get("type") or "").lower()
        if typ0 in SKIP_TYPES:
            continue
        lab = label_of(f)
        name = f.get("name") or ""
        if not lab or is_noise(lab, name):
            continue
        slug = slug_for(lab, used)
        typ = map_type(typ0)
        fd: dict = {"id": slug, "type": typ, "label": lab}
        if f.get("required"):
            fd["required"] = True
        opts = options_of(f)
        if opts and typ in ("select", "radio", "checkbox"):
            fd["options"] = opts
        if typ == "detail_table":
            cols = sub_columns(f)
            if cols:
                fd["detail_table_columns"] = cols
        if name:
            fd["jdy_widget"] = name
        out.append(fd)
    return out


def charger_rule(chargers: dict | None, widget_slug: dict[str, str]) -> dict:
    c = chargers or {}
    if c.get("creator"):
        return {"type": "creator"}
    users = c.get("users") or []
    if users:
        names = [u.get("username") for u in users if isinstance(u, dict) and u.get("username")]
        if names:
            return {"type": "specified_user", "value": names[0] if len(names) == 1 else names}
    widgets = c.get("widgets") or []
    if widgets:
        w = widgets[0]
        slug = widget_slug.get(w, w)
        return {"type": "form_field_person", "value": slug}
    dm = c.get("deptManager") or {}
    if dm.get("deptWidgets") or dm.get("creator") or dm.get("charger"):
        return {"type": "department_leader"}
    roles = c.get("roles") or []
    if roles and isinstance(roles[0], dict) and roles[0].get("name"):
        # CRM 无同名角色时会空批 → auto_approve
        return {"type": "specified_role", "value": "sales_manager", "exclude_initiator": True,
                "jdy_role_hint": roles[0].get("name")}
    return {"type": "specified_role", "value": "sales_manager", "exclude_initiator": True}


def map_condition(cond_obj: dict | None, widget_slug: dict[str, str]) -> dict | None:
    """JDY condition value like {rel, cond:[{field, method, value, type}], isElse} → CRM route condition."""
    if not cond_obj or not isinstance(cond_obj, dict):
        return None
    if cond_obj.get("isElse"):
        return None  # else = no condition on that exclusive edge; engine uses unconditional
    conds = cond_obj.get("cond") or []
    if not conds:
        return {"field": "__always", "operator": "is_empty"}  # always true if empty cond list with isElse false?
    mapped = []
    for c in conds:
        if not isinstance(c, dict):
            continue
        field = c.get("field")
        if not field:
            continue
        slug = widget_slug.get(field, field)
        method = c.get("method") or "eq"
        op = {"eq": "eq", "ne": "ne", "in": "in", "nin": "not_in", "empty": "is_empty", "not_empty": "is_not_empty"}.get(method, "eq")
        val = c.get("value")
        if isinstance(val, list) and len(val) == 1 and op == "eq":
            val = val[0]
        mapped.append({"field": slug, "operator": op, "value": val})
    if not mapped:
        return None
    if len(mapped) == 1 and (cond_obj.get("rel") or "and") == "and":
        return mapped[0]
    return {"rel": cond_obj.get("rel") or "and", "cond": mapped}


def build_flow(wf_raw: dict, fields: list[dict], title: str) -> tuple[list, list, list[str]]:
    """Build nodes/routes from JDY workflow_config. Returns notes about degradations."""
    notes: list[str] = []
    wf = (wf_raw.get("workflow_config") or {}) if isinstance(wf_raw, dict) else {}
    flows = wf.get("flows") or []
    widget_slug = {f["jdy_widget"]: f["id"] for f in fields if f.get("jdy_widget")}

    # index by flowId
    by_id = {}
    for f in flows:
        if isinstance(f, dict) and "flowId" in f:
            by_id[f["flowId"]] = f

    nodes: list[dict] = [{"id": "start", "type": "start", "name": "发起"}]
    routes: list[dict] = []
    node_id_map: dict[int, str] = {}  # flowId -> crm node id

    def nid(fid, name, typ):
        safe = re.sub(r"[^a-zA-Z0-9_]+", "_", f"n{fid}_{name}")[:48].strip("_") or f"n{fid}"
        node_id_map[fid] = safe
        return safe

    # create nodes (skip end -1 and start 0 as special)
    for f in flows:
        if not isinstance(f, dict):
            continue
        fid = f.get("flowId")
        if fid in (-1, 0):
            continue
        name = f.get("name") or f"节点{fid}"
        jdy_type = f.get("type") or "flow"
        crm_id = nid(fid, name, jdy_type)
        if jdy_type == "cc":
            rule = charger_rule(
                # cc uses ccUsers
                {**({} if not isinstance(f.get("ccUsers"), dict) else {
                    "users": f["ccUsers"].get("users") or [],
                    "widgets": f["ccUsers"].get("widgets") or [],
                    "creator": f["ccUsers"].get("creator"),
                    "roles": f["ccUsers"].get("roles") or [],
                    "deptManager": f["ccUsers"].get("deptManager") or {},
                })},
                widget_slug,
            )
            nodes.append({"id": crm_id, "type": "cc", "name": name, "approver_rule": rule})
            if rule.get("type") == "specified_user":
                notes.append(f"CC「{name}」绑定具名用户 {rule.get('value')}，CRM 无对应用户时 empty→auto_approve 不适用 CC，可能跳过")
        else:
            rule = charger_rule(f.get("chargers") if isinstance(f.get("chargers"), dict) else {}, widget_slug)
            nodes.append({
                "id": crm_id, "type": "approval", "name": name,
                "approver_rule": rule, "multi_mode": "or_sign",
                "empty_strategy": "auto_approve",
            })
            if rule.get("jdy_role_hint"):
                notes.append(f"审批「{name}」JDY 角色「{rule['jdy_role_hint']}」降级为 sales_manager")
            if rule.get("type") == "specified_user":
                notes.append(f"审批「{name}」具名用户 {rule.get('value')}，无匹配用户时 auto_approve")

    nodes.append({"id": "end", "type": "end", "name": "结束"})

    # Build adjacency from each node's condition map: condition keys are source flowIds
    # In JDY, node.condition = { sourceFlowId: condObj } means "this node is reached from sourceFlowId when cond"
    incoming: dict[int, list[tuple[int, dict | None]]] = {}  # target -> [(source, cond)]
    for f in flows:
        if not isinstance(f, dict):
            continue
        tid = f.get("flowId")
        cond_map = f.get("condition") or {}
        if not isinstance(cond_map, dict):
            continue
        for src_s, cobj in cond_map.items():
            try:
                sid = int(src_s)
            except (TypeError, ValueError):
                continue
            incoming.setdefault(tid, []).append((sid, cobj if isinstance(cobj, dict) else None))

    # Also ensure start connects: find nodes that have source 0
    def crm_ref(fid: int) -> str:
        if fid == 0:
            return "start"
        if fid == -1:
            return "end"
        return node_id_map.get(fid, f"missing_{fid}")

    route_i = 0
    for tid, sources in incoming.items():
        # group: conditional vs else
        else_edges = []
        cond_edges = []
        for sid, cobj in sources:
            if cobj and cobj.get("isElse"):
                else_edges.append((sid, cobj))
            elif cobj and (cobj.get("cond") or cobj.get("rel")):
                cond_edges.append((sid, cobj))
            else:
                # empty {} often means unconditional always
                else_edges.append((sid, cobj))

        for sid, cobj in cond_edges:
            route_i += 1
            cond = map_condition(cobj, widget_slug)
            r = {"id": f"r_{route_i}", "source": crm_ref(sid), "target": crm_ref(tid)}
            if cond:
                r["condition"] = cond
            routes.append(r)
        for sid, cobj in else_edges:
            route_i += 1
            r = {"id": f"r_{route_i}", "source": crm_ref(sid), "target": crm_ref(tid)}
            # if there are sibling cond edges from same source, else needs always-true or no cond
            # CRM: when mixed, unconditional acts as else
            routes.append(r)

    # If start has no outgoing, connect start to first approval
    if not any(r["source"] == "start" for r in routes):
        first = next((n["id"] for n in nodes if n["type"] == "approval"), "end")
        routes.append({"id": "r_start", "source": "start", "target": first})
        notes.append("未解析到发起后继，已兜底连到首个审批节点")

    # Ensure every approval/cc has a path to end eventually: if node has no outgoing, link to end
    sources = {r["source"] for r in routes}
    for n in nodes:
        if n["type"] in ("approval", "cc") and n["id"] not in sources:
            route_i += 1
            routes.append({"id": f"r_end_{route_i}", "source": n["id"], "target": "end"})
            notes.append(f"节点「{n['name']}」无出边，已接到结束")

    return nodes, routes, notes


def main():
    result = {}
    md = [
        "# 图纸通用流程表单字段对照",
        "",
        "> 状态：**已从简道云 live 拉取并对齐 CRM builtin**（app=`5e6c73fefc53170006bd4e9c`）。",
        "> entry：领用 `5e6ee08be3051400062159ee` / 安装图 `5e6edc5b44b7070006d191cb`。",
        "",
    ]
    for key, title in (
        ("drawing_requisition", "合同图纸（资料）领用申请"),
        ("install_drawing_notice", "安装图设计通知"),
    ):
        fields_raw = json.loads((OUT / f"_jdy_{key}_fields.json").read_text(encoding="utf-8"))
        wf_raw = json.loads((OUT / f"_jdy_{key}_workflows_raw.json").read_text(encoding="utf-8"))
        fields = build_fields(fields_raw)
        nodes, routes, notes = build_flow(wf_raw, fields, title)
        result[key] = {
            "name": title,
            "field_definitions": fields,
            "flow_nodes": nodes,
            "flow_routes": routes,
            "notes": notes,
        }
        md += [
            f"## {title}",
            "",
            f"- **builtin key**: `{key}`",
            f"- **字段数（去噪后）**: {len(fields)}",
            f"- **流程节点数（CRM）**: {len(nodes)} / 连线 {len(routes)}",
            "",
            "| slug | 标签 | type | 必填 | jdy_widget |",
            "|------|------|------|------|------------|",
        ]
        for fd in fields:
            md.append(
                f"| {fd['id']} | {fd['label']} | {fd['type']} | "
                f"{'是' if fd.get('required') else ''} | `{fd.get('jdy_widget','')}` |"
            )
        md += ["", "### 流程降级备注", ""]
        for n in notes:
            md.append(f"- {n}")
        md.append("")
        print(f"{key}: fields={len(fields)} nodes={len(nodes)} routes={len(routes)} notes={len(notes)}")

    GEN.write_text(
        "# -*- coding: utf-8 -*-\n"
        "\"\"\"Auto-generated from docs/product/_jdy_* drawing dumps. Do not edit by hand.\"\"\"\n"
        "from __future__ import annotations\n"
        "import json\n\n"
        f"DRAWING_JDY = json.loads(r'''{json.dumps(result, ensure_ascii=False)}''')\n",
        encoding="utf-8",
    )
    (OUT / "_jdy_drawing_forms.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("wrote", GEN)


if __name__ == "__main__":
    main()
