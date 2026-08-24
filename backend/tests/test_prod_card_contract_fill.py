from app.domains.lowcode.prod_card_contract_fill import (
    apply_prod_card_contract_pick_fields,
    build_prod_card_fill_from_contract,
    map_contract_lines_to_prod_card,
)


def test_map_contract_lines_to_prod_card():
    rows = map_contract_lines_to_prod_card([
        {
            "product_type": "振动筛",
            "name": "筛机",
            "spec": "ZKR-2056",
            "unit": "台",
            "qty": 1,
            "elec_ctrl": "不含电控",
            "standard": "附协议",
            "line_remark": "备注1",
        }
    ])
    assert rows == [{
        "product_type_2": "振动筛",
        "product_name_3": "筛机",
        "spec_model_3": "ZKR-2056",
        "unit_3": "台",
        "qty_3": 1,
        "electric_control": "不含电控",
        "tech_params_line": "附协议",
        "field_3": "备注1",
    }]


def test_build_fill_drawing_no_query():
    fill = build_prod_card_fill_from_contract(
        contract_no="C1",
        drawing_no="WMGF202504038",
        assignee_id="u1",
        assignee_name="张三",
        customer_name="抚顺新钢铁",
        delivery_date="2026-08-20",
        registration_json={
            "packaging": "木箱",
            "paint_req": "面漆",
            "tech_requirements": "参数",
            "special_note": "注意",
            "warranty_period": "12个月",
            "project_name": "项目A",
            "review_sn": "PS-1",
            "remark": "备注",
            "has_intelligence": "否",
            "is_export": "否",
        },
        key_clauses_json=[{"name": "筛", "qty": 2}],
        mode="drawing_no_query",
    )
    assert fill["no_drawing_no"] == "WMGF202504038"
    assert fill["no_sales_person"] == "u1"
    assert fill["yes_customer_name"] == "抚顺新钢铁"
    assert fill["contract_delivery_date"] == "2026-08-20"
    assert fill["has_intelligence"] == "否"
    assert fill["is_export_equipment"] == "否"
    assert fill["packaging_req"] == "木箱"
    assert fill["prod_card_line_items"][0]["product_name_3"] == "筛"
    assert fill["contract_tech_review_sn"] == "PS-1"


def test_build_fill_contract_no_select():
    fill = build_prod_card_fill_from_contract(
        contract_no="C9",
        drawing_no="D9",
        assignee_id="u2",
        assignee_name="李四",
        customer_name="客户B",
        registration_json={"review_sn": "R2"},
        key_clauses_json=[],
        mode="contract_no_select",
    )
    assert fill == {
        "yes_contract_no": "C9",
        "yes_sales_person": "u2",
        "yes_customer_name": "客户B",
        "contract_tech_review_sn": "R2",
    }


def test_apply_prod_card_contract_pick_fields():
    defs = [
        {"id": "is_supplement", "type": "radio", "label": "是否为补充"},
        {"id": "drawing_no_query", "type": "text", "label": "图纸编号查询"},
        {"id": "contract_no_select", "type": "text", "label": "合同号选择"},
        {"id": "select_contract_tech_review", "type": "text", "label": "选择合同技术协议评审"},
        {"id": "contract_tech_review_sn", "type": "text", "label": "合同技术协议评审流水号"},
        {"id": "submitter", "type": "person", "label": "提交人"},
        {"id": "department", "type": "department", "label": "所在部门"},
        {"id": "yes_customer_name", "type": "text", "label": "（是）单位名称", "available_on_create": False},
        {"id": "no_drawing_no", "type": "text", "label": "图纸编号", "available_on_create": False},
        {"id": "prod_card_line_items", "type": "detail_table", "label": "合同明细", "available_on_create": False},
        {"id": "no_sales_person", "type": "person", "label": "（否）业务人员"},
        {"id": "region_manager", "type": "person", "label": "区域经理/组长"},
        {"id": "yes_contract_no", "type": "text", "label": "合同号", "available_on_create": False},
    ]
    apply_prod_card_contract_pick_fields(defs)
    by_id = {f["id"]: f for f in defs}
    assert by_id["serial_no"]["type"] == "auto_number"
    assert by_id["is_supplement"]["default_value"] == "否"
    assert by_id["drawing_no_query"]["type"] == "contract"
    assert by_id["drawing_no_query"]["label"] == "选择合同"
    assert by_id["drawing_no_query"]["props"]["contract_fill"] == "drawing_no_query"
    assert by_id["drawing_no_query"]["props"]["filter_by_department_field"] == "department"
    assert by_id["contract_no_select"]["type"] == "contract"
    assert by_id["contract_no_select"]["props"]["contract_fill"] == "contract_no_select"
    assert by_id["select_contract_tech_review"]["type"] == "tech_agreement_review"
    assert by_id["select_contract_tech_review"]["props"]["tar_fill"] == "prod_card_sn"
    assert by_id["select_contract_tech_review"]["props"]["filter_by_submitter_field"] == "submitter"
    assert by_id["contract_tech_review_sn"]["props"]["readonly"] is True
    assert by_id["submitter"]["props"]["default_current_user"] is True
    assert by_id["department"]["props"]["default_current_dept"] is True
    for fid in (
        "yes_customer_name", "no_drawing_no", "prod_card_line_items",
        "no_sales_person", "region_manager", "yes_contract_no",
    ):
        assert by_id[fid]["available_on_create"] is True, fid
        assert by_id[fid]["fill_stage"] == "initiator", fid
        assert by_id[fid]["form_editable"] is False, fid


def test_prod_card_approver_only_fields_hidden_on_create():
    defs = [
        {"id": "confirm_agreement", "type": "radio", "label": "请确认", "required": True},
        {"id": "install_project_no", "type": "text", "label": "安装图项目号"},
        {"id": "f_0414", "type": "detail_table", "label": "室主任0414", "required": True},
        {"id": "submitter", "type": "person", "label": "提交人"},
    ]
    apply_prod_card_contract_pick_fields(defs)
    by = {f["id"]: f for f in defs}
    for fid in ("confirm_agreement", "install_project_no", "f_0414"):
        assert by[fid]["available_on_create"] is False
        assert by[fid]["fill_stage"] == "approver"
        assert by[fid]["required"] is False
    assert by["submitter"]["props"]["default_current_user"] is True


def test_apply_prod_card_design_assign_field_perms():
    from app.domains.lowcode.prod_card_contract_fill import (
        apply_prod_card_design_assign_field_perms,
    )
    nodes = [
        {
            "id": "n17",
            "name": "研管办安排1",
            "type": "approval",
            "field_perms": [
                {"field": "design_dispatch", "access": "required"},
                {"field": "design_assignees", "access": "required"},
                {"field": "confirm_agreement", "access": "required"},
            ],
        }
    ]
    assert apply_prod_card_design_assign_field_perms(nodes) is True
    fields = {p["field"]: p["access"] for p in nodes[0]["field_perms"]}
    assert "confirm_agreement" not in fields
    assert fields["install_project_no"] == "editable"
    assert fields["f_0414"] == "required"
    assert fields["design_assignees"] == "required"


def test_apply_prod_card_sales_confirm_field_perms():
    from app.domains.lowcode.prod_card_contract_fill import (
        apply_prod_card_sales_confirm_field_perms,
    )
    nodes = [
        {
            "id": "n_sales_confirm",
            "name": "业务员确认",
            "type": "approval",
            "approver_rule": {
                "type": "form_field_person",
                "value": ["yes_sales_person", "no_sales_person"],
            },
        }
    ]
    assert apply_prod_card_sales_confirm_field_perms(nodes) is True
    fields = {p["field"]: p["access"] for p in nodes[0]["field_perms"]}
    assert fields["confirm_agreement"] == "required"
    assert apply_prod_card_sales_confirm_field_perms(nodes) is False


def test_apply_prod_card_sales_before_region():
    from app.domains.lowcode.prod_card_contract_fill import (
        apply_prod_card_sales_before_region,
    )
    nodes = [
        {"id": "start", "type": "start", "name": "生产卡发起"},
        {"id": "n_sales_confirm", "type": "approval", "name": "业务员确认"},
        {"id": "n47", "type": "approval", "name": "区域经理/组长"},
        {"id": "n1", "type": "approval", "name": "部门审批"},
        {"id": "end", "type": "end", "name": "结束"},
    ]
    routes = [
        {
            "id": "r_region",
            "source": "start",
            "target": "n47",
            "condition": {
                "field": "region_manager",
                "operator": "is_not_empty",
                "value": None,
            },
            "exclusive_group": "ex_start",
        },
        {
            "id": "r_else",
            "source": "start",
            "target": "n_sales_confirm",
            "exclusive_group": "ex_start",
        },
        {"id": "r_sales_dept", "source": "n_sales_confirm", "target": "n1"},
        {
            "id": "r_region_dept",
            "source": "n47",
            "target": "n1",
            "condition": {"field": "__always", "operator": "is_empty"},
        },
    ]
    assert apply_prod_card_sales_before_region(nodes, routes) is True
    outs = [(r["source"], r["target"]) for r in routes if r["source"] in ("start", "n_sales_confirm")]
    assert ("start", "n47") not in outs
    assert ("n_sales_confirm", "n47") in outs
    assert ("n_sales_confirm", "n1") in outs
    assert ("start", "n_sales_confirm") in outs
    sales_region = next(r for r in routes if r["source"] == "n_sales_confirm" and r["target"] == "n47")
    sales_dept = next(r for r in routes if r["source"] == "n_sales_confirm" and r["target"] == "n1")
    assert sales_region["exclusive_group"] == "ex_n_sales_confirm"
    assert sales_dept["exclusive_group"] == "ex_n_sales_confirm"
    # 区域边排在 else 前
    sales_idxs = [i for i, r in enumerate(routes) if r["source"] == "n_sales_confirm"]
    assert routes[sales_idxs[0]]["target"] == "n47"
    assert apply_prod_card_sales_before_region(nodes, routes) is False


def test_strip_and_resolve_prod_card_contract_live():
    from app.domains.lowcode.prod_card_contract_fill import (
        strip_prod_card_contract_snapshot,
        resolve_prod_card_contract_pick,
        PROD_CARD_CONTRACT_LIVE_KEYS,
    )
    raw = {
        "is_supplement": "否",
        "drawing_no_query": "cid-1",
        "no_drawing_no": "D1",
        "yes_customer_name": "甲公司",
        "prod_card_line_items": [{"product_name_3": "筛"}],
        "remark": "手填备注应保留",
    }
    stripped = strip_prod_card_contract_snapshot(raw)
    assert stripped["drawing_no_query"] == "cid-1"
    assert stripped["remark"] == "手填备注应保留"
    for k in ("no_drawing_no", "yes_customer_name", "prod_card_line_items"):
        assert k not in stripped
        assert k in PROD_CARD_CONTRACT_LIVE_KEYS
    assert resolve_prod_card_contract_pick({
        "is_supplement": "是", "contract_no_select": "c-yes", "drawing_no_query": "c-no",
    }) == ("c-yes", "contract_no_select")
    assert resolve_prod_card_contract_pick({
        "is_supplement": "否", "drawing_no_query": "c-no",
    }) == ("c-no", "drawing_no_query")


def test_build_fill_contract_no_select_falls_back_reg_customer():
    fill = build_prod_card_fill_from_contract(
        contract_no="C9",
        drawing_no="D9",
        assignee_id="u2",
        assignee_name="李四",
        customer_name=None,
        registration_json={"customer_name": "登记单位甲", "review_sn": "R2"},
        key_clauses_json=[],
        mode="contract_no_select",
    )
    assert fill["yes_customer_name"] == "登记单位甲"
    assert fill["yes_contract_no"] == "C9"


def test_build_prod_card_fill_from_tar():
    from app.domains.lowcode.prod_card_contract_fill import build_prod_card_fill_from_tar
    assert build_prod_card_fill_from_tar(review_code=" HTJSXY00001 ") == {
        "contract_tech_review_sn": "HTJSXY00001",
    }


def test_apply_prod_card_supplement_rules_notice_when_not_supplement():
    from app.domains.lowcode.prod_card_contract_fill import apply_prod_card_supplement_rules

    rules = apply_prod_card_supplement_rules([
        {
            "id": "keep_me",
            "type": "visibility",
            "target_field_id": "is_turnkey",
            "condition": {"field": "is_supplement", "operator": "in", "value": ["否"]},
            "action": {"visible": True},
        },
        {
            "id": "crm_vis_prod_notice_packaging_req",
            "type": "visibility",
            "target_field_id": "packaging_req",
            "condition": {"field": "is_supplement", "operator": "in", "value": ["是"]},
            "action": {"visible": True},
        },
    ])
    by_id = {r["id"]: r for r in rules}
    assert "keep_me" in by_id
    # 包装情况改由「否 + 已选图纸合同」显隐，不再单独走 notice 规则
    fill_vis = by_id["crm_vis_pc_contract_fill_packaging_req"]
    assert fill_vis["condition"]["rel"] == "and"
    assert fill_vis["condition"]["cond"][0]["value"] == ["否"]
    assert fill_vis["condition"]["cond"][1]["field"] == "drawing_no_query"
    assert sum(1 for r in rules if str(r.get("id") or "").startswith("crm_vis_prod_notice_")) == 1
    assert any(r.get("id") == "crm_vis_pc_contract_fill_shared_yes_customer_name" for r in rules)


def test_apply_prod_card_contract_fill_visibility():
    from app.domains.lowcode.prod_card_contract_fill import apply_prod_card_contract_fill_visibility

    rules = apply_prod_card_contract_fill_visibility([])
    by_id = {r["id"]: r for r in rules}
    vis = by_id["crm_vis_pc_contract_fill_prod_card_line_items"]
    assert vis["condition"]["rel"] == "and"
    assert vis["condition"]["cond"][1]["field"] == "drawing_no_query"
    yes_vis = by_id["crm_vis_pc_yes_contract_fill_yes_contract_no"]
    assert yes_vis["condition"]["cond"][0]["value"] == ["是"]
    assert yes_vis["condition"]["cond"][1]["field"] == "contract_no_select"
    shared = by_id["crm_vis_pc_contract_fill_shared_yes_customer_name"]
    assert shared["condition"]["rel"] == "or"


def test_ensure_prod_card_serial_no_field():
    from app.domains.lowcode.prod_card_contract_fill import (
        PROD_CARD_SERIAL_NO_RULES,
        apply_prod_card_contract_pick_fields,
        ensure_prod_card_serial_no_field,
    )

    defs: list = [{"id": "card_date", "type": "datetime", "label": "下卡日期"}]
    ensure_prod_card_serial_no_field(defs)
    assert defs[0]["id"] == "serial_no"
    assert defs[0]["type"] == "auto_number"
    assert defs[0]["props"]["serial_rules"] == PROD_CARD_SERIAL_NO_RULES

    # 再次 ensure 不重复插入
    ensure_prod_card_serial_no_field(defs)
    assert sum(1 for f in defs if f.get("id") == "serial_no") == 1

    apply_prod_card_contract_pick_fields([{"id": "is_supplement", "type": "radio"}])
    defs2: list = [{"id": "is_supplement", "type": "radio"}]
    apply_prod_card_contract_pick_fields(defs2)
    assert defs2[0]["id"] == "serial_no"
    assert defs2[1]["default_value"] == "否"


def test_prod_card_design_dispatch_hides_transfer_on_hq():
    """总部单不需要「转新乡、工艺包装」（对齐简道云 fieldShowRules）。"""
    from app.domains.lowcode.builtin_templates import get_builtin
    from app.domains.lowcode.cs_drawing_request_fields import CS_DRAWING_DISPATCH_RULES
    from app.domains.lowcode.prod_card_contract_fill import apply_prod_card_supplement_rules
    from app.domains.lowcode.rule_engine import compute_field_states

    bt = get_builtin("prod_card_supplement")
    assert bt
    rules = apply_prod_card_supplement_rules(bt.get("rule_definitions") or [])
    ids = {r.get("id") for r in rules if isinstance(r, dict)}
    for r in CS_DRAWING_DISPATCH_RULES:
        assert r["id"] in ids

    fields = bt["field_definitions"]
    perms = [
        {"fieldId": x, "access": "required"}
        for x in (
            "design_dispatch",
            "transfer_packaging_users",
            "design_assignees",
            "offices",
            "order_datetime",
        )
    ]
    st_hq = compute_field_states(fields, {"design_dispatch": "总部单"}, rules, perms)
    assert st_hq["transfer_packaging_users"]["visible"] is False
    assert st_hq["transfer_packaging_users"]["required"] is False
    assert st_hq["design_assignees"]["visible"] is True
    assert st_hq["design_assignees"]["required"] is True

    st_xx = compute_field_states(fields, {"design_dispatch": "新乡单"}, rules, perms)
    assert st_xx["transfer_packaging_users"]["visible"] is True
    assert st_xx["transfer_packaging_users"]["required"] is True
    assert st_xx["design_assignees"]["visible"] is False
    assert st_xx["design_assignees"]["required"] is False


def test_apply_prod_card_install_pick_fields():
    from app.domains.lowcode.prod_card_contract_fill import apply_prod_card_install_pick_fields
    defs = [
        {
            "id": "f_251128",
            "type": "detail_table",
            "label": "项目号选择251128",
            "detail_table_columns": [
                {"id": "field_2", "type": "text", "label": "选择数据"},
            ],
        },
        {"id": "install_project_no", "type": "text", "label": "安装图项目号"},
    ]
    apply_prod_card_install_pick_fields(defs)
    col = defs[0]["detail_table_columns"][0]
    assert col["type"] == "select_data"
    assert col["props"]["source_form_code"] == "install_drawing_notice"
    assert col["props"]["link_fill"] == "prod_card_install"
    assert col["props"]["link_field"] == "prod_card_install"
    assert defs[1]["form_editable"] is False


def test_build_prod_card_install_fill():
    from app.domains.lowcode.prod_card_contract_fill import build_prod_card_install_fill
    pid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    fill = build_prod_card_install_fill(
        business_no="AZ20260817001",
        form_data={
            "project_no": pid,
            "design_card_no": "YY-01",
            "matter": "事项A",
        },
        project_codes={pid: "PRJ-2026-001"},
    )
    assert fill == {"install_project_no": "PRJ-2026-001"}
    fill2 = build_prod_card_install_fill(
        business_no="AZ20260817001",
        form_data={"matter": "事项B", "design_card_no": "YY-02"},
    )
    assert fill2 == {"install_project_no": "事项B"}


def test_builtin_prod_card_install_detail_select_data():
    from app.domains.lowcode.builtin_templates import get_builtin
    bt = get_builtin("prod_card_supplement")
    assert bt
    by = {f["id"]: f for f in (bt.get("field_definitions") or [])}
    detail = by.get("f_251128") or {}
    cols = {c["id"]: c for c in (detail.get("detail_table_columns") or []) if isinstance(c, dict)}
    assert cols["field_2"]["type"] == "select_data"
    assert cols["field_2"]["props"]["source_form_code"] == "install_drawing_notice"
