"""开票申请字段：合同明细可在本单编辑，不回写合同。"""
from app.domains.lowcode.invoice_application_fields import (
    apply_invoice_application_fields,
    build_invoice_fill_from_contract,
    map_contract_lines_to_invoice,
)


def test_serial_no_is_auto_number_with_jdy_rules():
    defs = [{"id": "serial_no", "type": "text", "label": "流水号"}]
    apply_invoice_application_fields(defs)
    serial = next(f for f in defs if f["id"] == "serial_no")
    assert serial["type"] == "auto_number"
    assert serial["form_editable"] is False
    rules = (serial.get("props") or {}).get("serial_rules") or []
    assert rules[0] == {"type": "text", "value": "KPSQ-"}
    assert rules[1]["type"] == "counter"
    assert rules[1]["digits"] == 5
    assert rules[1]["reset_period"] == "none"


def test_contract_lines_new_is_form_editable():
    defs = [
        {"id": "drawing_no_select", "type": "text", "label": "选择图纸编号"},
        {"id": "contract_lines_new", "type": "detail_table", "label": "合同明细（新增）",
         "form_editable": False, "description": "旧说明"},
        {"id": "total_amount", "type": "number", "label": "合计总价"},
        {"id": "drawing_no", "type": "text", "label": "图纸编号"},
    ]
    apply_invoice_application_fields(defs)
    pick = next(f for f in defs if f["id"] == "drawing_no_select")
    assert pick["type"] == "contract"
    assert pick["props"]["contract_fill"] == "invoice_application"
    assert "filter_by_department_field" not in (pick.get("props") or {})
    lines = next(f for f in defs if f["id"] == "contract_lines_new")
    assert lines["form_editable"] is True
    assert "不影响合同" in (lines.get("description") or "")
    total = next(f for f in defs if f["id"] == "total_amount")
    assert total["form_editable"] is False
    assert total["type"] == "formula"
    drawing = next(f for f in defs if f["id"] == "drawing_no")
    assert drawing["form_editable"] is False


def test_summarize_invoice_application_row():
    from types import SimpleNamespace
    from app.domains.lowcode.invoice_application_fields import summarize_invoice_application_row

    fi = SimpleNamespace(
        id="f1",
        status="completed",
        business_no="KPSQ-00001",
        form_data={
            "total_amount": 1000,
            "invoice_no": "INV1",
            "invoice_datetime": "2026-08-01",
            "drawing_no": "WMGF1",
            "customer_name": "甲",
        },
        created_at=None,
    )
    row = summarize_invoice_application_row(fi)
    assert row["serial_no"] == "KPSQ-00001"
    assert row["status_label"] == "已通过"
    assert row["total_amount"] == 1000.0
    assert row["invoice_no"] == "INV1"


def test_line_amount_stays_editable():
    defs = [
        {"id": "contract_lines_new", "type": "detail_table", "label": "合同明细（新增）",
         "detail_table_columns": [
             {"id": "qty", "type": "number", "label": "数量"},
             {"id": "unit_price", "type": "number", "label": "单价"},
             {"id": "line_amount", "type": "formula", "label": "合计",
              "form_editable": False, "props": {"formula": "$qty# * $unit_price#"}},
         ]},
        {"id": "total_amount", "type": "number", "label": "合计总价"},
    ]
    apply_invoice_application_fields(defs)
    lines = next(f for f in defs if f["id"] == "contract_lines_new")
    amount = next(c for c in lines["detail_table_columns"] if c["id"] == "line_amount")
    assert amount["type"] == "number"
    assert amount["form_editable"] is True


def test_sales_person_is_form_editable():
    defs = [
        {"id": "drawing_no_select", "type": "text", "label": "选择合同号"},
        {"id": "sales_person", "type": "person", "label": "业务员",
         "required": True, "form_editable": False},
    ]
    apply_invoice_application_fields(defs)
    sp = next(f for f in defs if f["id"] == "sales_person")
    assert sp["form_editable"] is True
    assert sp["available_on_create"] is True
    assert sp["fill_stage"] == "initiator"
    assert "可手改" in (sp.get("description") or "")


def test_customer_name_visible_on_create():
    defs = [
        {"id": "drawing_no_select", "type": "text", "label": "选择图纸编号"},
        {"id": "customer_name", "type": "text", "label": "单位名称",
         "available_on_create": False, "fill_stage": "approver"},
        {"id": "customer_no", "type": "text", "label": "客户编号"},
        {"id": "total_amount", "type": "number", "label": "合计总价"},
    ]
    apply_invoice_application_fields(defs)
    cn = next(f for f in defs if f["id"] == "customer_name")
    assert cn["available_on_create"] is True
    assert cn["fill_stage"] == "initiator"
    assert cn["form_editable"] is False
    assert cn["label"] == "客户名称"


def test_fill_overwrites_stale_line_amount():
    mapped = map_contract_lines_to_invoice(
        [{"name": "筛", "qty": 0.6, "price": 1140000, "amount": 1}],
    )
    assert mapped[0]["line_amount"] == 684000.0
