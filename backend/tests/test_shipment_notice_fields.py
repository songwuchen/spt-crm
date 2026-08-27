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
        prior_shipped_amount=12000,
    )
    assert len(fill["ship_lines"]) == 1
    assert fill["ship_lines"][0]["goods_name"] == "筛板"
    assert fill["ship_lines"][0]["contract_line_amount"] == 8748.0
    assert fill["ship_lines"][0]["line_contract_no"] == "WMGF202504038"
    assert fill["ship_amount"] == 8748.0
    assert fill["prior_shipped_amount"] == 12000.0
    assert fill["shipped_amount_incl"] == 20748.0
    assert fill["unshipped_amount"] == 107252.5


def test_shipment_notice_ship_amount_is_formula():
    defs = [
        {"id": "ship_amount", "type": "number", "label": "发货金额"},
        {"id": "shipped_amount_incl", "type": "number", "label": "累计已发货（含本次）"},
        {"id": "unshipped_amount", "type": "number", "label": "未发货"},
        {"id": "contract_amount", "type": "number", "label": "合同金额"},
    ]
    apply_shipment_notice_fields(defs)
    by_id = {d["id"]: d for d in defs}
    assert by_id["ship_amount"]["type"] == "formula"
    assert by_id["ship_amount"]["props"]["formula"] == "SUM($ship_lines.line_amount#)"
    assert by_id["shipped_amount_incl"]["props"]["formula"] == "$prior_shipped_amount#+$ship_amount#"
    assert by_id["shipped_amount_incl"]["props"]["formula_editable"] is True
    assert by_id["shipped_amount_incl"]["form_editable"] is True
    assert by_id["unshipped_amount"]["props"]["formula"] == "$contract_amount#-$shipped_amount_incl#"
    assert by_id["unshipped_amount"]["props"]["formula_editable"] is True
    assert by_id["unshipped_amount"]["form_editable"] is True
    assert by_id["prior_shipped_amount"]["props"]["hidden"] is True


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
    assert logi["approver_rule"]["type"] == "specified_role"
    assert logi["approver_rule"]["value"] == "logistics_approval"


def test_shipment_notice_parallel_fork_after_pick():
    from app.domains.lowcode._shipment_notice_generated import SHIPMENT_NOTICE_JDY
    from app.domains.lowcode.shipment_notice_fields import shipment_parallel_fork_broken
    routes = [dict(r) for r in SHIPMENT_NOTICE_JDY["shipment_notice"]["flow_routes"]]
    pick_routes = [r for r in routes if r.get("source") == "n3" and r.get("target") in ("n9", "n10")]
    assert len(pick_routes) == 2
    assert not shipment_parallel_fork_broken(routes)
    assert all(not r.get("exclusive_group") for r in pick_routes)


def test_shipment_notice_build_flow_n3_parallel_from_jdy():
    """对照简道云：开具提货单后生产领料与仓库判定均为无条件并行，不应标 ex_n3。"""
    import json
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts))
    from _gen_drawing_jdy import build_flow  # noqa: E402
    from _gen_shipment_notice_jdy import unwrap_wf  # noqa: E402

    from app.domains.lowcode._shipment_notice_generated import SHIPMENT_NOTICE_JDY

    wf_raw = unwrap_wf(
        json.loads((root / "docs/product/_jdy_shipment_notice_workflows_raw.json").read_text(encoding="utf-8"))
    )
    fields = SHIPMENT_NOTICE_JDY["shipment_notice"]["field_definitions"]
    _nodes, routes, notes = build_flow(wf_raw, fields, "发货通知")
    pick = [r for r in routes if r.get("source") == "n3" and r.get("target") in ("n9", "n10")]
    assert len(pick) == 2
    assert all(not r.get("exclusive_group") for r in pick)
    assert any("无条件出边保持并行" in n for n in notes)


def test_shipment_notice_sales_accept_field_perms():
    from app.domains.lowcode.shipment_notice_fields import (
        apply_shipment_notice_sales_accept_field_perms,
        shipment_sales_accept_perms_ok,
    )
    nodes = [
        {"id": "n18__4", "name": "通知业务员4", "type": "approval", "field_perms": []},
        {"id": "n9", "name": "生产领料", "type": "approval"},
    ]
    assert apply_shipment_notice_sales_accept_field_perms(nodes)
    perms = {p["field"]: p["access"] for p in nodes[0]["field_perms"]}
    assert perms["accept_attachments"] == "editable"
    assert perms["accept_method"] == "readonly"
    assert perms["accept_docs"] == "readonly"
    assert shipment_sales_accept_perms_ok(nodes)
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
