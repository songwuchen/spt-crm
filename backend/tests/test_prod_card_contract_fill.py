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
        "yes_contract_no": "D9",
        "yes_sales_person": "u2",
        "yes_customer_name": "客户B",
        "contract_tech_review_sn": "R2",
    }


def test_build_fill_contract_no_select_falls_back_contract_no_without_drawing():
    fill = build_prod_card_fill_from_contract(
        contract_no="C9",
        drawing_no="",
        assignee_id="u2",
        assignee_name="李四",
        customer_name="客户B",
        registration_json={"review_sn": "R2"},
        key_clauses_json=[],
        mode="contract_no_select",
    )
    assert fill["yes_contract_no"] == "C9"


def test_apply_prod_card_std_room_designer_scope():
    from app.domains.lowcode.prod_card_contract_fill import (
        apply_prod_card_std_room_designer_scope,
        apply_prod_card_contract_pick_fields,
    )

    defs = [{
        "id": "std_room_fill",
        "type": "detail_table",
        "label": "标准化室填写",
        "detail_table_columns": [
            {"id": "material_code", "type": "text", "label": "物料代码"},
            {"id": "designer", "type": "person", "label": "设计人"},
        ],
    }]
    assert not apply_prod_card_std_room_designer_scope(defs, research_dept_id=None)
    assert apply_prod_card_std_room_designer_scope(defs, research_dept_id="dept-research-1")
    designer = next(c for c in defs[0]["detail_table_columns"] if c["id"] == "designer")
    assert designer["props"]["pickable_scope"] == {
        "dept_ids": ["dept-research-1"],
        "include_children": True,
    }

    defs2 = [{"id": "std_room_fill", "type": "detail_table", "detail_table_columns": [
        {"id": "designer", "type": "person", "label": "设计人"},
    ]}]
    apply_prod_card_contract_pick_fields(defs2, research_dept_id="dept-x")
    std = next(f for f in defs2 if f.get("id") == "std_room_fill")
    assert std["detail_table_columns"][0]["props"]["pickable_scope"]["dept_ids"] == ["dept-x"]


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
    assert by["confirm_agreement"]["available_on_create"] is False
    assert by["confirm_agreement"]["fill_stage"] == "approver"
    assert by["confirm_agreement"]["required"] is False
    assert by["install_project_no"]["available_on_create"] is True
    assert by["install_project_no"]["fill_stage"] == "initiator"
    assert by["f_0414"]["available_on_create"] is False
    assert by["f_0414"]["required"] is False
    assert "fill_stage" not in by["f_0414"]
    assert by["f_0414"]["props"]["hidden"] is True
    assert by["submitter"]["props"]["default_current_user"] is True


def test_apply_prod_card_detail_quick_fill_flags():
    from app.domains.lowcode.prod_card_contract_fill import apply_prod_card_detail_quick_fill_flags

    defs = [{"id": "std_room_fill", "type": "detail_table", "label": "标准化室填写"}]
    apply_prod_card_detail_quick_fill_flags(defs)
    assert defs[0]["props"]["quick_fill"] is True


def test_apply_prod_card_prune_std_room_columns():
    from app.domains.lowcode.prod_card_contract_fill import apply_prod_card_prune_std_room_columns

    defs = [
        {
            "id": "std_room_fill",
            "type": "detail_table",
            "label": "标准化室填写",
            "detail_table_columns": [
                {"id": "material_code", "type": "text", "label": "物料代码"},
                {"id": "theoretical_weight", "type": "number", "label": "理论重量"},
                {"id": "designer", "type": "person", "label": "设计人"},
            ],
        },
        {
            "id": "elec_workshop_fill",
            "type": "detail_table",
            "label": "电气车间填写",
            "detail_table_columns": [
                {"id": "material_code", "type": "text", "label": "物料代码"},
                {"id": "theoretical_weight_2", "type": "number", "label": "理论重量"},
            ],
        },
    ]
    apply_prod_card_prune_std_room_columns(defs)
    std_ids = [c["id"] for c in defs[0]["detail_table_columns"]]
    elec_ids = [c["id"] for c in defs[1]["detail_table_columns"]]
    assert "theoretical_weight" not in std_ids
    assert std_ids == ["material_code", "designer"]
    assert "theoretical_weight_2" not in elec_ids
    assert elec_ids == ["material_code"]


def test_apply_prod_card_design_assign_field_perms():
    from app.domains.lowcode.prod_card_contract_fill import (
        apply_prod_card_design_assign_field_perms,
    )
    nodes = [
        {
            "id": "n17",
            "name": "安排设计1",
            "type": "approval",
            "field_perms": [
                {"field": "need_dispatch", "access": "editable"},
                {"field": "has_contract_tech_review", "access": "editable"},
                {"field": "select_contract_tech_review", "access": "editable"},
                {"field": "design_dispatch", "access": "required"},
                {"field": "design_assignees", "access": "required"},
                {"field": "confirm_agreement", "access": "required"},
            ],
        }
    ]
    assert apply_prod_card_design_assign_field_perms(nodes) is True
    fields = {p["field"]: p["access"] for p in nodes[0]["field_perms"]}
    assert "confirm_agreement" not in fields
    assert "need_dispatch" not in fields
    assert "has_contract_tech_review" not in fields
    assert "select_contract_tech_review" not in fields
    assert "f_251128" not in fields
    assert "has_install_project" not in fields
    assert "install_project_no" not in fields
    assert "f_0414" not in fields
    assert fields["design_assignees"] == "required"
    assert apply_prod_card_design_assign_field_perms(nodes) is False


def test_apply_prod_card_prune_legacy_field_perms():
    from app.domains.lowcode.prod_card_contract_fill import (
        apply_prod_card_prune_legacy_field_perms,
        filter_prod_card_legacy_field_perms,
    )
    nodes = [
        {
            "id": "n17",
            "name": "安排设计1",
            "type": "approval",
            "field_perms": [
                {"field": "design_assignees", "access": "required"},
                {"field": "f_0414", "access": "required"},
            ],
        }
    ]
    assert apply_prod_card_prune_legacy_field_perms(nodes) is True
    fields = {p["field"] for p in nodes[0]["field_perms"]}
    assert "f_0414" not in fields
    assert filter_prod_card_legacy_field_perms(nodes[0]["field_perms"]) == [
        {"field": "design_assignees", "access": "required"},
    ]
    assert apply_prod_card_prune_legacy_field_perms(nodes) is False


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


def test_load_prod_card_fill_for_contract_merges_install_auto_fill(monkeypatch):
    import asyncio
    from types import SimpleNamespace

    from app.domains.lowcode.prod_card_contract_fill import load_prod_card_fill_for_contract

    contract = SimpleNamespace(
        id="cid-1",
        contract_no="HT001",
        drawing_no="D001",
        assignee_id=None,
        assignee_name=None,
        delivery_date=None,
        registration_json={},
        project_id="proj-1",
        customer_id=None,
        current_version_no=1,
    )
    version = SimpleNamespace(key_clauses_json={})

    async def fake_execute(stmt):
        class R:
            def scalar_one_or_none(self_inner):
                s = str(stmt)
                if "contract_versions" in s.lower() or "ContractVersion" in s:
                    return version
                if "contracts" in s.lower() or ".Contract" in s:
                    return contract
                return None

        return R()

    async def fake_enrich(_db, _tid, fill, _user):
        return fill

    async def fake_install(_db, _tid, *, project_id):
        assert project_id == "proj-1"
        return {
            "has_install_project": "是",
            "f_251128": [{"field_2": "inst-1"}],
            "install_project_no": "AZ202608104",
        }

    monkeypatch.setattr(
        "app.domains.lowcode.prod_card_contract_fill.enrich_prod_card_fill_with_region_manager",
        fake_enrich,
    )
    monkeypatch.setattr(
        "app.domains.lowcode.prod_card_contract_fill.build_prod_card_install_auto_fill_for_project",
        fake_install,
    )

    class FakeDb:
        async def execute(self, stmt):
            return await fake_execute(stmt)

    result = asyncio.run(load_prod_card_fill_for_contract(
        FakeDb(), "00000000-0000-0000-0000-000000000001", "cid-1", "drawing_no_query", None,
    ))
    assert result["has_install_project"] == "是"
    assert result["install_project_no"] == "AZ202608104"
    assert result["f_251128"] == [{"field_2": "inst-1"}]
    assert result["no_drawing_no"] == "D001"


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
    assert resolve_prod_card_contract_pick({
        "is_supplement": "否",
        "contract_no_select": "1.2.3-2026082201503",
        "drawing_no_query": {},
    }) == ("1.2.3-2026082201503", "drawing_no_query")


def test_resolve_contract_id_for_fill_by_serial(monkeypatch):
    import asyncio

    from app.domains.lowcode.prod_card_contract_fill import resolve_contract_id_for_fill

    n = 0

    async def fake_execute(_stmt):
        nonlocal n
        n += 1

        class R:
            def scalar_one_or_none(self_inner):
                return "ee6049dc-aaaa-bbbb-cccc-dddddddddddd" if n >= 1 else None

        return R()

    class FakeDb:
        async def execute(self, stmt):
            return await fake_execute(stmt)

    cid = asyncio.run(resolve_contract_id_for_fill(
        FakeDb(), "00000000-0000-0000-0000-000000000001", "1.2.3-2026082201503",
    ))
    assert cid == "ee6049dc-aaaa-bbbb-cccc-dddddddddddd"
    assert n >= 1


def test_resolve_contract_id_for_fill_by_registration_json_serial():
    import asyncio

    from app.domains.lowcode.prod_card_contract_fill import resolve_contract_id_for_fill

    calls = {"n": 0}
    target = "aa11bb22-cc33-dd44-ee55-ff6677889900"

    async def fake_execute(_stmt):
        calls["n"] += 1
        hit = calls["n"] == 6  # uuid + 5 cols fail, 6th = registration_json

        class R:
            def scalar_one_or_none(self_inner):
                return target if hit else None

        return R()

    class FakeDb:
        async def execute(self, stmt):
            return await fake_execute(stmt)

    cid = asyncio.run(resolve_contract_id_for_fill(
        FakeDb(), "00000000-0000-0000-0000-000000000001", "1.2.3-2026081901475",
    ))
    assert cid == target
    assert calls["n"] == 6


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
    assert fill["yes_contract_no"] == "D9"


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
    cols = {c["id"]: c for c in defs[0]["detail_table_columns"]}
    col = cols["field_2"]
    assert col["type"] == "select_data"
    assert col["props"]["source_form_code"] == "install_drawing_notice"
    assert col["props"]["link_fill"] == "prod_card_install"
    assert col["props"]["link_field"] == "prod_card_install"
    assert cols["field_5"]["label"] == "项目号（打印模板显示）"
    assert cols["field_5"].get("form_editable") is False
    assert cols["field_3"]["label"] == "业务员"
    assert cols["field_4"]["label"] == "现场"
    assert cols["field_6"]["label"] == "事项"
    assert defs[1]["form_editable"] is False


def test_build_prod_card_install_fill():
    from app.domains.lowcode.prod_card_contract_fill import build_prod_card_install_fill
    pid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    fill = build_prod_card_install_fill(
        business_no="AZ20260817001",
        form_data={
            "serial_no": "AZ202608104",
            "project_no": pid,
            "design_card_no": "YY-01",
            "matter": "事项A",
            "customer_name": "内蒙古汇能煤电集团巴隆图煤炭有限公司",
            "sales_person": "u-sales",
        },
        project_codes={pid: "PRJ-2026-001"},
        user_names={"u-sales": "韩开强"},
    )
    assert fill["install_project_no"] == "AZ202608104"
    assert fill["field_5"] == "AZ202608104"
    assert fill["field_3"] == "韩开强"
    assert fill["field_4"] == "内蒙古汇能煤电集团巴隆图煤炭有限公司"
    assert fill["field_6"] == "事项A"
    fill2 = build_prod_card_install_fill(
        business_no="AZ20260817001",
        form_data={"matter": "事项B", "design_card_no": "YY-02"},
    )
    assert fill2 == {
        "install_project_no": "AZ20260817001",
        "field_5": "AZ20260817001",
        "field_3": "",
        "field_4": "",
        "field_6": "事项B",
    }


def test_ensure_prod_card_install_fields_on_create():
    from app.domains.lowcode.prod_card_contract_fill import ensure_prod_card_install_fields_on_create

    defs = [
        {"id": "has_install_project", "type": "radio"},
        {"id": "f_251128", "type": "detail_table", "available_on_create": False, "fill_stage": "approver"},
        {"id": "install_project_no", "type": "text", "available_on_create": False, "fill_stage": "approver"},
        {"id": "design_assignees", "type": "person", "available_on_create": False, "fill_stage": "approver"},
    ]
    ensure_prod_card_install_fields_on_create(defs)
    by = {f["id"]: f for f in defs}
    assert by["has_install_project"]["available_on_create"] is True
    assert by["has_install_project"]["fill_stage"] == "initiator"
    assert by["has_install_project"]["required"] is True
    assert by["f_251128"]["fill_stage"] == "initiator"
    assert by["f_251128"]["required"] is False
    assert by["install_project_no"]["fill_stage"] == "initiator"
    assert by["design_assignees"]["fill_stage"] == "approver"


def test_apply_prod_card_install_visibility_rules():
    from app.domains.lowcode.prod_card_contract_fill import _apply_prod_card_install_visibility_rules

    rules = _apply_prod_card_install_visibility_rules([])
    vis = {r["target_field_id"]: r for r in rules if r.get("type") == "visibility"}
    assert vis["f_251128"]["condition"]["cond"][0]["field"] == "has_install_project"
    assert vis["install_project_no"]["type"] == "visibility"
    req = [r for r in rules if r.get("type") == "required" and r.get("target_field_id") == "f_251128"]
    assert len(req) == 1


def test_prod_card_install_auto_fill_clear_keys():
    from app.domains.lowcode.prod_card_contract_fill import prod_card_install_auto_fill_clear_keys

    assert prod_card_install_auto_fill_clear_keys() == [
        "has_install_project", "f_251128", "install_project_no",
    ]


def test_install_auto_fill_no_project():
    import asyncio
    from app.domains.lowcode.prod_card_contract_fill import build_prod_card_install_auto_fill_for_project

    result = asyncio.run(build_prod_card_install_auto_fill_for_project(
        None, "00000000-0000-0000-0000-000000000001", project_id=None,
    ))
    assert result["has_install_project"] == "否"
    assert result["f_251128"] == []
    assert result["install_project_no"] is None


def test_install_auto_fill_with_notice(monkeypatch):
    import asyncio
    from types import SimpleNamespace

    from app.domains.lowcode.prod_card_contract_fill import build_prod_card_install_auto_fill_for_project

    pid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    inst = SimpleNamespace(
        id="11111111-2222-3333-4444-555555555555",
        business_no="AZ202608104",
        form_data={"serial_no": "AZ202608104", "project_no": pid},
    )

    async def fake_find(_db, _tid, project_id):
        assert project_id == pid
        return inst

    monkeypatch.setattr(
        "app.domains.lowcode.prod_card_contract_fill._find_install_notice_for_project",
        fake_find,
    )

    async def fake_row_ctx(_db, _tid, _inst, _pid):
        return {
            "install_project_no": "AZ202608104",
            "field_3": "韩开强",
            "field_4": "测试客户",
            "field_5": "AZ202608104",
            "field_6": "测试事项",
        }

    monkeypatch.setattr(
        "app.domains.lowcode.prod_card_contract_fill._build_install_row_fill_for_notice",
        fake_row_ctx,
    )

    result = asyncio.run(build_prod_card_install_auto_fill_for_project(
        None, "00000000-0000-0000-0000-000000000001", project_id=pid,
    ))
    assert result["has_install_project"] == "是"
    assert result["install_project_no"] == "AZ202608104"
    assert len(result["f_251128"]) == 1
    row = result["f_251128"][0]
    assert row["field_2"] == inst.id
    assert row["field_3"] == "韩开强"
    assert row["field_4"] == "测试客户"
    assert row["field_6"] == "测试事项"


def test_builtin_prod_card_install_detail_select_data():
    from app.domains.lowcode.builtin_templates import get_builtin
    bt = get_builtin("prod_card_supplement")
    assert bt
    by = {f["id"]: f for f in (bt.get("field_definitions") or [])}
    detail = by.get("f_251128") or {}
    cols = {c["id"]: c for c in (detail.get("detail_table_columns") or []) if isinstance(c, dict)}
    assert cols["field_2"]["type"] == "select_data"
    assert cols["field_2"]["props"]["source_form_code"] == "install_drawing_notice"
