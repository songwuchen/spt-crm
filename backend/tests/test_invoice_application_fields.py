"""开票申请字段：合同明细可在本单编辑，不回写合同。"""
from app.domains.lowcode.invoice_application_fields import (
    apply_invoice_application_fields,
    build_invoice_fill_from_contract,
    map_contract_lines_to_invoice,
)


def test_contract_lines_new_is_form_editable():
    defs = [
        {"id": "drawing_no_select", "type": "text", "label": "选择图纸编号"},
        {"id": "contract_lines_new", "type": "detail_table", "label": "合同明细（新增）",
         "form_editable": False, "description": "旧说明"},
        {"id": "total_amount", "type": "number", "label": "合计总价"},
        {"id": "drawing_no", "type": "text", "label": "图纸编号"},
    ]
    apply_invoice_application_fields(defs)
    lines = next(f for f in defs if f["id"] == "contract_lines_new")
    assert lines["form_editable"] is True
    assert "不影响合同" in (lines.get("description") or "")
    total = next(f for f in defs if f["id"] == "total_amount")
    assert total["form_editable"] is False
    assert total["type"] == "formula"
    drawing = next(f for f in defs if f["id"] == "drawing_no")
    assert drawing["form_editable"] is False


def test_fill_copies_lines_without_mutating_source():
    source = [{"name": "吊挂装置", "spec": "ZG-60F配", "unit": "件", "qty": 80, "price": 270}]
    mapped = map_contract_lines_to_invoice(source)
    assert mapped[0]["product_name"] == "吊挂装置"
    assert mapped[0]["line_amount"] == 21600.0
    # 源行未被改写
    assert source[0]["name"] == "吊挂装置"
    assert "product_name" not in source[0]

    fill = build_invoice_fill_from_contract(
        contract_no="HT001", drawing_no="TZ001", peer_contract_no=None,
        assignee_id="u1", customer_name="天空兄弟", customer_code="C1",
        taxpayer_id="T", invoice_address_phone="A", bank_account="B",
        key_clauses_json=source,
    )
    fill["contract_lines_new"].append({"product_name": "本单加行", "qty": 1, "unit_price": 10})
    assert len(source) == 1
    assert len(fill["contract_lines_new"]) == 2
