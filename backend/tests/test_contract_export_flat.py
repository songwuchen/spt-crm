"""合同登记单表全览导出单元测试。"""
from app.domains.contract.export_flat import (
    build_flat_export_rows,
    flat_export_headers,
)


def test_flat_export_headers_include_line_and_pay_columns():
    headers = flat_export_headers()
    assert "流水号" in headers
    assert "明细-产品名称" in headers
    assert "收款-付款方式" in headers
    assert "流程记录摘要" in headers
    assert "行业分类" in headers


def test_build_flat_export_rows_expands_line_items():
    rows = build_flat_export_rows([{
        "serial_no": "HT001",
        "status": "draft",
        "change_type": "new",
        "registration_json": {"industry": "矿山"},
        "key_clauses_json": [
            {"name": "产品A", "qty": 1},
            {"name": "产品B", "qty": 2},
        ],
        "payment_terms_json": [{"kind": "电汇", "ratio": 30}],
    }])
    assert len(rows) == 2
    assert rows[0][1] == "HT001"
    idx = flat_export_headers().index("明细-产品名称")
    assert rows[0][idx] == "产品A"
    assert rows[1][idx] == "产品B"
    pay_idx = flat_export_headers().index("收款-付款方式")
    assert rows[0][pay_idx] == "电汇"
    assert rows[1][pay_idx] == ""


def test_source_label_native_vs_external():
    from app.domains.contract.export_flat import _source_label

    assert _source_label({"registration_json": {}}) == "CRM内录"
    assert _source_label({"external_key": "jdy-1"}) == "外部推送"
    assert _source_label({
        "registration_json": {"_external_source": "jdy"},
    }) == "外部推送"
