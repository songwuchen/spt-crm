"""Generate CRM builtin fields + flow graphs from pulled JDY drawing dumps.

Also emits rule_definitions from docs/product/_jdy_drawing_forms_linkages.json
(allowBlank / fieldShowRules / subformFieldShowRules). Do NOT re-pull JDY.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

OUT = Path(r"g:\ruolin-a\spt-crm\docs\product")
GEN = Path(r"g:\ruolin-a\spt-crm\backend\app\domains\lowcode\_drawing_jdy_generated.py")
LINKAGES = OUT / "_jdy_drawing_forms_linkages.json"

# Soft noise: drop unused junk. Overridden when field is required or in show-rules.
SOFT_NOISE_KEYS = (
    "辅助", "已取消", "打印模板", "同一天", "补位",
    "count辅助", "240829", "240912", "240416", "0816", "260601", "20230112",
)
# Always drop even if they appear in show-rules (cancelled / disabled junk).
HARD_DROP_KEYS = ("取消", "停用", "不用显示", "22/11/28", "230320", "前期沟通的设计员（文本）")
SYS_IDS = {"creator", "createTime", "updateTime", "appId", "entryId", "_id"}
SKIP_TYPES = {"separator", "button", "pagebreak", "hint", "flowstate", "sn", "aggregation"}
# Separator we promote to a text hint field (show-rule target).
PAPER_TIP_MARKERS = ("打印纸质图提醒",)

# 简道云多为 datetime，业务上只需选到「日」
DATE_ONLY_FIELD_IDS = frozenset({
    "apply_datetime",
    "order_date",
    "card_date",
    "require_draw_date",
    "score_date",
})

FORM_LINKAGE_KEY = {
    "drawing_requisition": "requisition",
    "install_drawing_notice": "install_notice",
}

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
    "业务反馈240416": "biz_feedback",
    "落标原因240416": "lose_bid_reason",
    "打印纸质图提醒：": "paper_print_tip",
    "打印纸质图提醒": "paper_print_tip",
    # detail columns
    "设备名称": "equipment_name",
    "设计要求": "design_req",
    "是否有附件/修改图": "has_attach_or_rev",
    "图纸数量": "drawing_qty",
    "是否核价": "need_pricing",
    "海拔高度（m)": "altitude_m",
    "环境温度­°C（最高/最低）": "env_temp_c",
    "大气压力KP": "atm_pressure_kp",
    "供电电源V": "power_supply_v",
    "防爆区域": "explosion_zone",
    "工艺位置": "process_position",
    "需要修改的设备名称": "change_equipment_name",
    "修改部位": "change_part",
    "修改原因": "change_reason",
    "行业*": "industry_star",
    "行业": "industry",
    "物料名称（可多选）": "material_names",
    "物料名称": "material_name",
    "*堆密度（kg/m³)": "bulk_density_star",
    "堆密度（kg/m³)": "bulk_density",
    "温度­°C": "temp_c",
    "筛孔尺寸mm*": "mesh_size_star",
    "筛孔尺寸mm": "mesh_size",
    "*处理量(t/h)": "throughput_star",
    "处理量(t/h)": "throughput",
    "*入料粒度": "feed_size_star",
    "入料粒度": "feed_size",
    "*筛分效率是否有要求": "need_screening_eff_star",
    "筛分效率是否有要求": "need_screening_eff",
    "*粒度分布": "particle_dist_star",
    "粒度分布": "particle_dist",
    "*筛分效率": "screening_eff_star",
    "筛分效率": "screening_eff",
    "*水分含量%": "moisture_star",
    "水分含量%": "moisture",
    "粒度组成": "particle_composition",
}


def label_of(f: dict) -> str:
    return (f.get("title") or f.get("text") or f.get("label") or "").strip()


def is_hard_drop(label: str, name: str) -> bool:
    if name in SYS_IDS:
        return True
    lab = label or ""
    if not lab or lab.startswith("_"):
        return True
    return any(k in lab for k in HARD_DROP_KEYS)


def is_soft_noise(label: str) -> bool:
    return any(k in (label or "") for k in SOFT_NOISE_KEYS)


def is_paper_tip(label: str) -> bool:
    return any(m in (label or "") for m in PAPER_TIP_MARKERS)


def should_keep_field(
    label: str,
    name: str,
    required_widgets: set[str],
    rule_widgets: set[str],
) -> bool:
    """Keep unless hard-drop junk; soft-noise kept when required / in show-rules."""
    if is_hard_drop(label, name):
        return False
    if name in required_widgets or name in rule_widgets:
        return True
    if is_soft_noise(label):
        return False
    return True


def map_type(t: str) -> str:
    t = (t or "").lower()
    return {
        "text": "text", "textarea": "textarea", "number": "number",
        "datetime": "datetime", "date": "date",
        "radiogroup": "radio", "radio": "radio",
        "checkboxgroup": "checkbox", "checkbox": "checkbox", "combocheck": "checkbox",
        "combo": "select", "select": "select",
        "user": "person", "usergroup": "person_multi",
        "dept": "department", "department": "department", "deptgroup": "department_multi",
        "upload": "file", "image": "file", "file": "file",
        "subform": "detail_table", "switch": "switch",
        "separator": "text",  # only used when promoted (paper tip)
    }.get(t, "text")


def jdy_widget_limit(f: dict) -> dict | None:
    """字段上的人选/部门限制：可能在顶层或嵌套 widget 里。"""
    lim = f.get("limit")
    if isinstance(lim, dict):
        return lim
    w = f.get("widget")
    if isinstance(w, dict) and isinstance(w.get("limit"), dict):
        return w["limit"]
    return None


def apply_pickable_scope(fd: dict, limit: dict | None = None, jdy_field: dict | None = None) -> None:
    """把 JDY limit.roles 写成 props.pickable_scope.role_codes。"""
    from app.domains.lowcode.pickable_scope import pickable_scope_from_jdy_limit
    lim = limit if limit is not None else (jdy_widget_limit(jdy_field or {}) if jdy_field else None)
    scope = pickable_scope_from_jdy_limit(lim)
    if not scope:
        return
    props = dict(fd.get("props") or {})
    props["pickable_scope"] = scope
    fd["props"] = props


def load_widget_limits_from_edit_raw(path: Path) -> dict[str, dict]:
    """从 *_edit_raw.json 提取 widgetName -> limit。"""
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}

    def walk(node):
        if isinstance(node, dict):
            w = node.get("widget") if isinstance(node.get("widget"), dict) else node
            name = w.get("widgetName") or w.get("name") or node.get("name")
            lim = w.get("limit") if isinstance(w.get("limit"), dict) else None
            if name and lim and (lim.get("roles") or lim.get("departs")):
                out[str(name)] = lim
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for it in node:
                walk(it)

    walk(raw)
    return out


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


def load_linkage_pack(key: str) -> dict:
    if not LINKAGES.exists():
        return {}
    data = json.loads(LINKAGES.read_text(encoding="utf-8"))
    lk = FORM_LINKAGE_KEY.get(key, key)
    return (data.get("forms") or {}).get(lk) or {}


def collect_linkage_sets(pack: dict) -> tuple[set[str], set[str], set[str]]:
    """Return (required_widgets, rule_widgets, required_detail_widgets)."""
    required: set[str] = set()
    for r in pack.get("required_fields") or []:
        if isinstance(r, dict) and r.get("widget"):
            required.add(r["widget"])
    rule_widgets: set[str] = set()
    for rule in pack.get("fieldShowRules") or []:
        for c in rule.get("conditions") or []:
            if c.get("trigger_widget"):
                rule_widgets.add(c["trigger_widget"])
        for sf in rule.get("show_fields") or []:
            if sf.get("widget"):
                rule_widgets.add(sf["widget"])
    for rule in pack.get("subformFieldShowRules") or []:
        if rule.get("subform_widget"):
            rule_widgets.add(rule["subform_widget"])
        for c in rule.get("conditions") or []:
            if c.get("trigger_widget"):
                rule_widgets.add(c["trigger_widget"])
        for sf in rule.get("show_fields") or []:
            if sf.get("widget"):
                rule_widgets.add(sf["widget"])
    return required, rule_widgets, required


def sub_columns(
    f: dict,
    used: set[str],
    required_widgets: set[str],
    rule_widgets: set[str],
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
        if typ == "detail_table":
            continue
        fd = {"id": slug_for(lab, used), "type": typ, "label": lab}
        if name in required_widgets:
            fd["required"] = True
        opts = options_of(c)
        if opts and typ in ("select", "radio", "checkbox"):
            fd["options"] = opts
        if name:
            fd["jdy_widget"] = name
        out.append(fd)
    return out


def build_fields(
    raw: dict,
    required_widgets: set[str],
    rule_widgets: set[str],
    widget_limits: dict[str, dict] | None = None,
) -> list[dict]:
    data = raw.get("data", raw)
    fields = data.get("fields") if isinstance(data, dict) else data
    used: set[str] = set()
    limits = widget_limits or {}
    out = []
    for f in fields or []:
        if not isinstance(f, dict):
            continue
        typ0 = (f.get("type") or "").lower()
        lab = label_of(f)
        name = f.get("name") or ""
        promote_tip = typ0 == "separator" and is_paper_tip(lab)
        if typ0 in SKIP_TYPES and not promote_tip:
            continue
        if not lab or not should_keep_field(lab, name, required_widgets, rule_widgets):
            # paper tip: keep even if not yet in rule_widgets set edge-case
            if not (promote_tip and name in rule_widgets):
                continue
        if promote_tip:
            typ0 = "text"
            lab = lab.rstrip("：").rstrip(":")
        slug = slug_for(lab, used)
        typ = map_type(typ0)
        # 对齐 JDY usergroup：转新乡等字段必须多选（历史生成曾被误写成 person）
        if slug == "transfer_packaging_users" or typ0 == "usergroup":
            typ = "person_multi"
        fd: dict = {"id": slug, "type": typ, "label": lab}
        if name in required_widgets or f.get("required"):
            fd["required"] = True
        if promote_tip:
            tip = (f.get("value") or "").strip()
            if tip:
                tip_plain = re.sub(r"<[^>]+>", "", tip).strip()
                fd["description"] = tip_plain or tip
            else:
                fd["description"] = (
                    "流程通过后，请发起人等候研究院通知，到档案室签字领取纸质图，"
                    "图纸使用完毕，需第一时间归还给档案室。"
                )
            fd["props"] = {**(fd.get("props") or {}), "readonly": True}
        opts = options_of(f)
        if opts and typ in ("select", "radio", "checkbox"):
            fd["options"] = opts
        if typ == "detail_table":
            cols = sub_columns(f, used, required_widgets, rule_widgets)
            if cols:
                fd["detail_table_columns"] = cols
        if name:
            fd["jdy_widget"] = name
        apply_pickable_scope(fd, limit=limits.get(name) or jdy_widget_limit(f))
        # 业务日期字段：CRM 统一为仅日期（不含时分）
        if slug in DATE_ONLY_FIELD_IDS:
            fd["type"] = "date"
            fd["props"] = {**(fd.get("props") or {}), "show_time": False, "date_only": True}
        out.append(fd)
    return out


def widget_slug_map(fields: list[dict]) -> dict[str, str]:
    m: dict[str, str] = {}
    for f in fields:
        if f.get("jdy_widget"):
            m[f["jdy_widget"]] = f["id"]
        for c in f.get("detail_table_columns") or []:
            if c.get("jdy_widget"):
                m[c["jdy_widget"]] = c["id"]
    return m


def required_slug_set(fields: list[dict]) -> set[str]:
    out: set[str] = set()
    for f in fields:
        if f.get("required"):
            out.add(f["id"])
        for c in f.get("detail_table_columns") or []:
            if c.get("required"):
                out.add(c["id"])
    return out


def map_show_condition(rel: str | None, conditions: list, widget_slug: dict[str, str]) -> dict | None:
    """Map one JDY filter to CRM condition. eq/ne unwrap single-value lists."""
    mapped = []
    for c in conditions or []:
        if not isinstance(c, dict):
            continue
        field = c.get("trigger_widget") or c.get("field")
        if not field:
            continue
        slug = widget_slug.get(field)
        if not slug:
            # trigger not in CRM fields → cannot evaluate; skip leaf
            continue
        method = c.get("method") or "eq"
        op = {
            "eq": "eq", "ne": "ne", "in": "in", "nin": "not_in",
            "empty": "is_empty", "not_empty": "is_not_empty",
        }.get(method, "eq")
        val = c.get("value")
        if isinstance(val, list) and len(val) == 1 and op in ("eq", "ne"):
            val = val[0]
        mapped.append({"field": slug, "operator": op, "value": val})
    if not mapped:
        return None
    rel_s = (rel or "and").lower()
    if len(mapped) == 1 and rel_s == "and":
        return mapped[0]
    return {"rel": rel_s, "cond": mapped}


def or_merge(conds: list[dict]) -> dict:
    if len(conds) == 1:
        return conds[0]
    return {"rel": "or", "cond": conds}


def _prefer_screening_star_trigger(cond: dict) -> dict:
    """子表显隐：把 need_screening_eff 文本桩改成用户填写的 need_screening_eff_star 单选。"""
    import copy
    c = copy.deepcopy(cond)

    def walk(node: dict | list | None) -> None:
        if isinstance(node, list):
            for x in node:
                if isinstance(x, dict):
                    walk(x)
            return
        if not isinstance(node, dict):
            return
        if node.get("field") == "need_screening_eff":
            node["field"] = "need_screening_eff_star"
        if node.get("field") == "need_screening_eff_2":
            pass
        for x in node.get("cond") or []:
            if isinstance(x, dict):
                walk(x)

    walk(c)
    return c


def build_rule_definitions(linkage: dict, fields: list[dict]) -> list[dict]:
    widget_slug = widget_slug_map(fields)
    req_slugs = required_slug_set(fields)
    # target_slug -> list of CRM conditions that show it
    by_target: dict[str, list[dict]] = defaultdict(list)

    for rule in linkage.get("fieldShowRules") or []:
        cond = map_show_condition(rule.get("rel"), rule.get("conditions") or [], widget_slug)
        if not cond:
            continue
        for sf in rule.get("show_fields") or []:
            wid = (sf or {}).get("widget")
            slug = widget_slug.get(wid) if wid else None
            if not slug:
                continue  # orphan / hard-dropped / separator skipped
            by_target[slug].append(cond)

    for rule in linkage.get("subformFieldShowRules") or []:
        cond = map_show_condition(rule.get("rel"), rule.get("conditions") or [], widget_slug)
        if not cond:
            continue
        # 简道云触发器常是文本桩 need_screening_eff；CRM 界面填写的是单选 _star
        cond = _prefer_screening_star_trigger(cond)
        for sf in rule.get("show_fields") or []:
            wid = (sf or {}).get("widget")
            slug = widget_slug.get(wid) if wid else None
            if not slug:
                continue
            by_target[slug].append(cond)

    rules: list[dict] = []
    for slug, conds in by_target.items():
        # de-dupe identical condition dicts
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
            "id": f"jdy_vis_{slug}",
            "type": "visibility",
            "target_field_id": slug,
            "condition": merged,
            "action": {"visible": True},
        })
        if slug in req_slugs:
            rules.append({
                "id": f"jdy_req_{slug}",
                "type": "required",
                "target_field_id": slug,
                "condition": merged,
                "action": {"required": True},
            })
    return rules


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
    # 简道云「部门主管」挂在表单部门控件上 → CRM form_field_dept（取该字段所选部门的负责人）
    # 勿写成 dept_head（那是发起人所属部门负责人，且 exclude_initiator 易空审跳过）
    dept_widgets = dm.get("deptWidgets") or {}
    if isinstance(dept_widgets, dict) and dept_widgets:
        w = next(iter(dept_widgets.keys()))
        slug = widget_slug.get(w, w)
        # 常见 widget → 业务字段 id
        if slug.startswith("_widget_") and "department" in widget_slug.values():
            slug = "department"
        elif slug.startswith("_widget_"):
            slug = widget_slug.get(w) or "department"
        return {"type": "form_field_dept", "value": slug}
    if dm.get("creator") or dm.get("charger"):
        return {"type": "dept_head", "exclude_initiator": True}
    roles = c.get("roles") or []
    if roles and isinstance(roles[0], dict) and roles[0].get("name"):
        return {"type": "specified_role", "value": "sales_manager", "exclude_initiator": True,
                "jdy_role_hint": roles[0].get("name")}
    return {"type": "specified_role", "value": "sales_manager", "exclude_initiator": True}


def map_condition(cond_obj: dict | None, widget_slug: dict[str, str]) -> dict | None:
    """JDY condition value like {rel, cond:[{field, method, value, type}], isElse} → CRM route condition."""
    if not cond_obj or not isinstance(cond_obj, dict):
        return None
    if cond_obj.get("isElse"):
        return None
    conds = cond_obj.get("cond") or []
    if not conds:
        return {"field": "__always", "operator": "is_empty"}
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
        if isinstance(val, list) and len(val) == 1 and op in ("eq", "ne"):
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
    widget_slug = widget_slug_map(fields)

    by_id = {}
    for f in flows:
        if isinstance(f, dict) and "flowId" in f:
            by_id[f["flowId"]] = f

    start_name = "发起"
    for f in flows:
        if isinstance(f, dict) and f.get("flowId") == 0 and (f.get("name") or "").strip():
            start_name = str(f["name"]).strip()
            break
    nodes: list[dict] = [{"id": "start", "type": "start", "name": start_name}]
    routes: list[dict] = []
    node_id_map: dict[int, str] = {}

    def nid(fid, name, typ):
        safe = re.sub(r"[^a-zA-Z0-9_]+", "_", f"n{fid}_{name}")[:48].strip("_") or f"n{fid}"
        node_id_map[fid] = safe
        return safe

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

    incoming: dict[int, list[tuple[int, dict | None]]] = {}
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

    def crm_ref(fid: int) -> str:
        if fid == 0:
            return "start"
        if fid == -1:
            return "end"
        return node_id_map.get(fid, f"missing_{fid}")

    route_i = 0
    for tid, sources in incoming.items():
        else_edges = []
        cond_edges = []
        for sid, cobj in sources:
            if cobj and cobj.get("isElse"):
                else_edges.append((sid, cobj))
            elif cobj and (cobj.get("cond") or cobj.get("rel")):
                cond_edges.append((sid, cobj))
            else:
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
            routes.append(r)

    if not any(r["source"] == "start" for r in routes):
        first = next((n["id"] for n in nodes if n["type"] == "approval"), "end")
        routes.append({"id": "r_start", "source": "start", "target": first})
        notes.append("未解析到发起后继，已兜底连到首个审批节点")

    # 抄送是旁路通知：入边标 always，避免与主链 else 互斥；叶子抄送不要接到 end，
    # 否则会与主链并行时提前把整单标成已通过（图纸领取等节点变孤儿）。
    cc_ids = {n["id"] for n in nodes if n.get("type") == "cc"}
    for r in routes:
        if r.get("target") in cc_ids and not r.get("always"):
            r["always"] = True

    # 简道云同源多出边：默认 if/else 互斥组；含「工艺包装」的分叉为多条件并行
    # （新乡单∥人选含李海春可同时进第二研究院安排+工艺包装），标 fork=parallel、不设互斥。
    name_by_id = {n["id"]: (n.get("name") or "") for n in nodes}
    by_src: dict[str, list] = {}
    for r in routes:
        if r.get("always"):
            continue
        by_src.setdefault(r["source"], []).append(r)
    for src, outs in by_src.items():
        if len(outs) < 2:
            continue
        if any(name_by_id.get(r.get("target") or "") == "工艺包装" for r in outs):
            for r in outs:
                r.pop("exclusive_group", None)
                r["fork"] = "parallel"
            notes.append(
                f"节点「{src}」含工艺包装分叉：{len(outs)} 条出边标并行(fork=parallel)"
            )
            continue
        gid = f"ex_{src}"
        for r in outs:
            r["exclusive_group"] = gid
        notes.append(f"节点「{src}」{len(outs)} 条出边已标互斥组 {gid}")

    sources = {r["source"] for r in routes}
    for n in nodes:
        if n["id"] in sources:
            continue
        if n["type"] == "cc":
            notes.append(f"节点「{n['name']}」无出边（抄送旁路，不接到结束）")
            continue
        if n["type"] == "approval":
            route_i += 1
            routes.append({"id": f"r_end_{route_i}", "source": n["id"], "target": "end"})
            notes.append(f"节点「{n['name']}」无出边，已接到结束")

    apply_jdy_opt_auth(fields, flows, nodes, node_id_map, notes)
    return nodes, routes, notes


# 简道云 optAuth 位：1=可见 2=可写 4=简报
_JDY_OPT_VIEW = 1
_JDY_OPT_EDIT = 2


def _slug_from_opt_widget(widget: str, widget_slug: dict[str, str]) -> str | None:
    if widget in widget_slug:
        return widget_slug[widget]
    top = str(widget).split(".", 1)[0]
    return widget_slug.get(top)


def apply_jdy_opt_auth(
    fields: list[dict],
    flows: list,
    nodes: list[dict],
    node_id_map: dict[int, str],
    notes: list[str],
) -> None:
    """把简道云节点 optAuth 落到字段阶段属性 + 审批节点 field_perms。

    - 发起节点可写 → available_on_create=True（创建可填/可必填）
    - 仅审批节点可写 → available_on_create=False，创建隐藏且去掉 required；
      对应节点 field_perms=required（原 allowBlank=false）或 editable
    """
    widget_slug = widget_slug_map(fields)
    by_id = {
        f.get("flowId"): f for f in flows
        if isinstance(f, dict) and "flowId" in f
    }
    start_oa = (by_id.get(0) or {}).get("optAuth") or {}
    start_edit: set[str] = set()
    start_view: set[str] = set()
    for w, flags in start_oa.items() if isinstance(start_oa, dict) else []:
        if not isinstance(flags, int):
            continue
        slug = _slug_from_opt_widget(str(w), widget_slug)
        if not slug:
            continue
        if flags & _JDY_OPT_VIEW:
            start_view.add(slug)
        if flags & _JDY_OPT_EDIT:
            start_edit.add(slug)

    approval_edit: dict[str, set[str]] = {}
    for fid, f in by_id.items():
        if fid in (-1, 0) or (f.get("type") or "flow") == "cc":
            continue
        crm_id = node_id_map.get(fid)
        if not crm_id:
            continue
        oa = f.get("optAuth") or {}
        if not isinstance(oa, dict):
            continue
        for w, flags in oa.items():
            if not isinstance(flags, int) or not (flags & _JDY_OPT_EDIT):
                continue
            slug = _slug_from_opt_widget(str(w), widget_slug)
            if slug:
                approval_edit.setdefault(slug, set()).add(crm_id)

    originally_required = {fd["id"] for fd in fields if fd.get("required")}
    n_approver_only = 0
    for fd in fields:
        fid = fd.get("id")
        if not fid or not fd.get("jdy_widget"):
            continue
        if fid in start_edit:
            fd["available_on_create"] = True
            fd["fill_stage"] = "initiator"
            continue
        if fid in approval_edit:
            fd["available_on_create"] = False
            fd["fill_stage"] = "approver"
            if fd.get("required"):
                fd["required"] = False
            n_approver_only += 1
            continue
        if fid in start_view:
            fd["available_on_create"] = True
            fd["fill_stage"] = "initiator"
            if fd.get("required") and fid not in start_edit:
                fd["required"] = False
                fd["form_editable"] = False
            continue
        # 无 optAuth 条目：保持生成器原样，避免误藏 CRM 自有字段

    for fid, f in by_id.items():
        if fid in (-1, 0) or (f.get("type") or "flow") == "cc":
            continue
        crm_id = node_id_map.get(fid)
        node = next((n for n in nodes if n.get("id") == crm_id), None)
        if not node or node.get("type") != "approval":
            continue
        perms: list[dict] = []
        seen: set[str] = set()
        oa = f.get("optAuth") or {}
        if not isinstance(oa, dict):
            continue
        for w, flags in oa.items():
            if not isinstance(flags, int) or not (flags & _JDY_OPT_EDIT):
                continue
            slug = _slug_from_opt_widget(str(w), widget_slug)
            if not slug or slug in seen:
                continue
            seen.add(slug)
            if slug not in start_edit and slug in originally_required:
                access = "required"
            else:
                access = "editable"
            perms.append({"field": slug, "access": access})
        if perms:
            node["field_perms"] = perms

    if n_approver_only:
        notes.append(
            f"optAuth：{n_approver_only} 个字段仅审批可写"
            f"（创建 available_on_create=false，必填下沉到节点 field_perms）"
        )


def _cond_summary(cond: dict) -> str:
    if not cond:
        return ""
    if "cond" in cond and isinstance(cond.get("cond"), list):
        parts = [_cond_summary(c) if isinstance(c, dict) and "cond" in c else
                 f"{c.get('field')} {c.get('operator')} {c.get('value')!r}"
                 for c in cond["cond"] if isinstance(c, dict)]
        return f"({(cond.get('rel') or 'and').upper()} " + "; ".join(parts) + ")"
    return f"{cond.get('field')} {cond.get('operator')} {cond.get('value')!r}"


CONTRACT_DRAWING_MAP_MD = """# 图纸相关表单字段对照

## 0. 合同图纸对应表（图纸档案管理，非通用流程）

- **builtin key / code**: `contract_drawing_map`
- **路由**: `/contract-drawing-maps`
- **简道云**: app=`5b2af2c3a57134271be3717b` / entry=`5b2af2e131765151ee89230c`

| slug | 标签 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| pre_issue | 预下号 | radio(是/否) | 是 | 默认「否」 |
| apply_date | 日期时间 | date | 是 | 默认当天；参与编号日期段 |
| number_attr | 编号属性 | radio(WMGF/SY) | 是 | 默认 WMGF；分序列 |
| contract_no | 合同号 | text | 是 | |
| department | 业务部门 | department | | |
| drawing_no | 图纸编号 | auto_number | | WMGF+yyyyMM+3位月序 / SY+yy+3位年序；填报页 peek 预览 |
| remark | 备注 | textarea | | |

编号示例：`WMGF202608018`、`SY26001`。合同登记「编号查询」从此表带出合同号/图纸编号/业务部门。

---
"""


def main():
    result = {}
    md = [
        CONTRACT_DRAWING_MAP_MD.rstrip(),
        "",
        "# 图纸通用流程表单字段对照",
        "",
        "> 状态：**已从简道云 live 拉取并对齐 CRM builtin**（app=`5e6c73fefc53170006bd4e9c`）。",
        "> entry：领用 `5e6ee08be3051400062159ee` / 安装图 `5e6edc5b44b7070006d191cb`。",
        ">",
        "> **必填 / 显隐规则**来源：`_jdy_drawing_*_edit_raw.json` → `_jdy_drawing_forms_linkages.json`",
        "> （`allowBlank===false`、`fieldShowRules`、`subformFieldShowRules`）。",
        "> wrapper `GET /api/form/.../fields` 不含这些细节；生成器 `_gen_drawing_jdy.py` 合并进 builtin。",
        "",
    ]
    for key, title in (
        ("drawing_requisition", "合同图纸（资料）领用申请"),
        ("install_drawing_notice", "安装图设计通知"),
    ):
        fields_raw = json.loads((OUT / f"_jdy_{key}_fields.json").read_text(encoding="utf-8"))
        wf_raw = json.loads((OUT / f"_jdy_{key}_workflows_raw.json").read_text(encoding="utf-8"))
        linkage = load_linkage_pack(key)
        required_widgets, rule_widgets, _ = collect_linkage_sets(linkage)
        widget_limits = load_widget_limits_from_edit_raw(OUT / f"_jdy_{key}_edit_raw.json")
        fields = build_fields(fields_raw, required_widgets, rule_widgets, widget_limits)
        rules = build_rule_definitions(linkage, fields)
        nodes, routes, notes = build_flow(wf_raw, fields, title)
        result[key] = {
            "name": title,
            "field_definitions": fields,
            "rule_definitions": rules,
            "flow_nodes": nodes,
            "flow_routes": routes,
            "notes": notes,
        }
        n_req = sum(1 for f in fields if f.get("required"))
        n_req_cols = sum(
            1 for f in fields for c in (f.get("detail_table_columns") or []) if c.get("required")
        )
        n_vis = sum(1 for r in rules if r.get("type") == "visibility")
        n_req_r = sum(1 for r in rules if r.get("type") == "required")
        md += [
            f"## {title}",
            "",
            f"- **builtin key**: `{key}`",
            f"- **字段数（去噪后）**: {len(fields)}",
            f"- **必填字段**: {n_req}" + (f"（含子表列 {n_req_cols}）" if n_req_cols else ""),
            f"- **规则**: 显隐 {n_vis} / 条件必填 {n_req_r}",
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
            for col in fd.get("detail_table_columns") or []:
                md.append(
                    f"| └ {col['id']} | {col['label']} | {col['type']} | "
                    f"{'是' if col.get('required') else ''} | `{col.get('jdy_widget','')}` |"
                )
        md += ["", "### 显隐 / 条件必填规则", ""]
        if not rules:
            md.append("- （无）")
        else:
            md.append(f"| id | type | target | condition |")
            md.append(f"|----|------|--------|-----------|")
            for r in rules:
                md.append(
                    f"| `{r['id']}` | {r['type']} | `{r.get('target_field_id','')}` | "
                    f"{_cond_summary(r.get('condition') or {})} |"
                )
        md += ["", "### 流程降级备注", ""]
        for n in notes:
            md.append(f"- {n}")
        md.append("")
        print(
            f"{key}: fields={len(fields)} required={n_req}+cols{n_req_cols} "
            f"rules={len(rules)}(vis={n_vis},req={n_req_r}) "
            f"nodes={len(nodes)} routes={len(routes)}"
        )

    GEN.write_text(
        "# -*- coding: utf-8 -*\n"
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
