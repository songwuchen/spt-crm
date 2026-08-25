"""明细子表列进入筛选字段列表。"""
from app.domains.lowcode.service import expand_filterable_form_fields


def test_expand_filterable_includes_detail_columns():
    defs = [
        {"id": "serial_no", "type": "auto_number", "label": "流水号"},
        {
            "id": "lines",
            "type": "detail_table",
            "label": "开票明细",
            "detail_table_columns": [
                {"id": "contract_no", "type": "text", "label": "合同号"},
                {"id": "amount", "type": "amount", "label": "金额"},
                {"id": "file_col", "type": "file", "label": "附件"},
            ],
        },
    ]
    out = expand_filterable_form_fields(defs)
    ids = {x["id"] for x in out}
    assert "serial_no" in ids
    assert "contract_no" in ids
    assert "amount" in ids
    assert "file_col" not in ids
    by_id = {x["id"]: x for x in out}
    assert by_id["contract_no"]["label"] == "合同号"


def test_expand_filterable_includes_formula_as_number():
    """公式汇总字段（开票「总价合计」）应出现在筛选列表。"""
    defs = [
        {"id": "total_amount", "type": "formula", "label": "总价合计",
         "props": {"formula": "SUM($contract_lines_new.line_amount#)"}},
        {"id": "total_amount_adjusted", "type": "number", "label": "总价合计（调整后）*"},
    ]
    out = expand_filterable_form_fields(defs)
    by_id = {x["id"]: x for x in out}
    assert "total_amount" in by_id
    assert by_id["total_amount"]["type"] == "number"
    assert by_id["total_amount"]["label"] == "总价合计"
    assert "total_amount_adjusted" in by_id


def test_expand_filterable_disambiguates_duplicate_labels():
    defs = [
        {
            "id": "a",
            "type": "detail_table",
            "label": "明细A",
            "detail_table_columns": [{"id": "c1", "type": "text", "label": "合同号"}],
        },
        {
            "id": "b",
            "type": "detail_table",
            "label": "明细B",
            "detail_table_columns": [{"id": "c2", "type": "text", "label": "合同号"}],
        },
    ]
    out = expand_filterable_form_fields(defs)
    labels = {x["id"]: x["label"] for x in out}
    assert labels["c1"] == "明细A·合同号"
    assert labels["c2"] == "明细B·合同号"
