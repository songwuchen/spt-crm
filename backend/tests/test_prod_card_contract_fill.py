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
        registration_json={
            "packaging": "木箱",
            "paint_req": "面漆",
            "tech_requirements": "参数",
            "special_note": "注意",
            "warranty_period": "12个月",
            "project_name": "项目A",
            "review_sn": "PS-1",
            "remark": "备注",
        },
        key_clauses_json=[{"name": "筛", "qty": 2}],
        mode="drawing_no_query",
    )
    assert fill["no_drawing_no"] == "WMGF202504038"
    assert fill["no_sales_person"] == "u1"
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
    ]
    apply_prod_card_contract_pick_fields(defs)
    assert defs[0]["default_value"] == "否"
    assert defs[1]["type"] == "contract"
    assert "选择合同" in defs[1]["label"]
    assert defs[1]["props"]["contract_fill"] == "drawing_no_query"
    assert defs[1]["props"]["filter_by_department_field"] == "department"
    assert defs[2]["type"] == "contract"
    assert defs[2]["props"]["contract_fill"] == "contract_no_select"
