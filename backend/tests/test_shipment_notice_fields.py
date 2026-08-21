"""发货通知 builtin 字段/流程回归。"""
from app.domains.lowcode._shipment_notice_generated import SHIPMENT_NOTICE_JDY
from app.domains.lowcode.builtin_templates import get_builtin
from app.domains.lowcode.shipment_notice_fields import (
    apply_shipment_notice_fields,
    build_shipment_fill_from_contract,
    map_contract_lines_to_shipment,
)
from app.domains.lowcode.workflow_service import (
    _flow_is_jdy_shipment_notice,
    apply_shipment_notice_approvers,
)


def test_shipment_notice_contract_fill():
    fill = build_shipment_fill_from_contract(
        contract_no="HT001",
        drawing_no="WMGF202504038",
        peer_contract_no="对方-001",
        assignee_id="u1",
        department_id="d1",
        customer_name="抚顺新钢铁",
        amount_total=128000.5,
        registration_json={
            "need_install": "指导安装",
            "accept_method": "指导安装不含验收",
            "accept_materials": "发货验收单",
        },
    )
    assert fill["counterparty_contract_no"] == "对方-001"
    assert fill["consignee_unit"] == "抚顺新钢铁"
    assert fill["contract_no_text"] == "WMGF202504038"
    assert fill["dept_contract_no"] == "HT001"
    assert fill["department"] == "d1"
    assert fill["sales_person"] == "u1"
    assert fill["need_install"] == "指导安装"
    assert fill["accept_method"] == "指导安装不含验收"
    assert fill["accept_docs"] == "发货验收单"
    assert fill["contract_amount"] == 128000.5


def test_map_contract_lines_to_shipment():
    lines = map_contract_lines_to_shipment([
        {
            "name": "弧形筛楔块",
            "spec": "WFHS-242060-2-YS",
            "unit": "件",
            "qty": 20,
            "amount": 1200,
            "line_remark": "备注1",
        }
    ], contract_no="HT001", drawing_no="WMGF202504038")
    assert lines == [{
        "goods_name": "弧形筛楔块",
        "spec_model": "WFHS-242060-2-YS",
        "unit": "件",
        "qty": 20.0,
        "contract_line_amount": 1200.0,
        "line_amount": 1200.0,
        "line_remark": "备注1",
        "line_contract_no": "WMGF202504038",
    }]


def test_shipment_notice_contract_fill_includes_ship_lines():
    fill = build_shipment_fill_from_contract(
        contract_no="HT001",
        drawing_no="WMGF202504038",
        peer_contract_no="对方-001",
        assignee_id="u1",
        department_id="d1",
        customer_name="抚顺新钢铁",
        amount_total=128000.5,
        registration_json={},
        key_clauses_json=[{
            "name": "筛板",
            "spec": "WMGF202312083.01SB.AZ01",
            "unit": "套",
            "qty": 1,
            "amount": 8748,
        }],
    )
    assert len(fill["ship_lines"]) == 1
    assert fill["ship_lines"][0]["goods_name"] == "筛板"
    assert fill["ship_lines"][0]["contract_line_amount"] == 8748.0
    assert fill["ship_lines"][0]["line_contract_no"] == "WMGF202504038"


def test_shipment_notice_contract_field_has_fill_mode():
    defs = [
        {"id": "serial_no", "type": "text", "label": "单据编号"},
        {"id": "contract_no", "type": "text", "props": {}},
    ]
    apply_shipment_notice_fields(defs)
    assert defs[0]["type"] == "auto_number"
    assert defs[0]["props"]["serial_rules"][0]["value"] == "24.1-"
    assert defs[1]["type"] == "contract"
    assert defs[1]["props"]["contract_fill"] == "shipment_notice"


def test_shipment_notice_builtin_has_core_fields():
    pack = SHIPMENT_NOTICE_JDY["shipment_notice"]
    ids = {f["id"] for f in pack["field_definitions"]}
    assert "serial_no" in ids
    assert "contract_no" in ids
    assert "ship_lines" in ids
    assert "consignee_unit" in ids
    sn = next(f for f in pack["field_definitions"] if f["id"] == "serial_no")
    rules = (sn.get("props") or {}).get("serial_rules") or []
    assert any(r.get("value") == "24.1-" for r in rules if isinstance(r, dict))


def test_shipment_notice_flow_topology():
    pack = SHIPMENT_NOTICE_JDY["shipment_notice"]
    nodes = pack["flow_nodes"]
    assert _flow_is_jdy_shipment_notice(nodes)
    names = {n.get("name") for n in nodes}
    assert "仓库" in names and "发货完毕" in names
    logi = next(n for n in nodes if n.get("name") == "物流审批")
    apply_shipment_notice_approvers(nodes)
    assert logi["approver_rule"]["type"] == "specified_user"


def test_shipment_notice_jdy_visibility_rules():
    pack = SHIPMENT_NOTICE_JDY["shipment_notice"]
    vis = [r for r in pack["rule_definitions"] if r.get("type") == "visibility"]
    targets = {r.get("target_field_id") for r in vis}
    assert vis, "应抄入简道云 fieldShowRules"
    assert "purchasers" in targets
    assert "address_2" in targets
    assert "return_goods_content" in targets
    assert "warehouse_handler" in targets
    assert "exit_pass_no" in targets
    assert "accept_attachments" in targets
    assert "contract_amount" in targets

    t = get_builtin("shipment_notice")
    assert t is not None
    assert t["name"] == "发货通知"
    assert any(f.get("id") == "ship_type" for f in t["field_definitions"])
    assert any(r.get("type") == "visibility" for r in (t.get("rule_definitions") or []))
    cn = next(f for f in t["field_definitions"] if f.get("id") == "contract_no")
    assert cn.get("type") == "contract"
    assert (cn.get("props") or {}).get("contract_fill") == "shipment_notice"
