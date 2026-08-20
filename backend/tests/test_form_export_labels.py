"""表单导出：人员/部门 id 转显示名；明细子表展开为多 sheet。"""
from __future__ import annotations

from types import SimpleNamespace
from datetime import datetime

from app.domains.lowcode.router import (
    _collect_ref_ids,
    _fmt_export_cell,
    _scan_export_ref_ids_from_defs,
    _build_form_export_sheets,
    _export_detail_columns,
)


def test_collect_ref_ids():
    assert _collect_ref_ids("abc") == ["abc"]
    assert _collect_ref_ids({"id": "u1", "name": "张三"}) == ["u1"]
    assert _collect_ref_ids([{"id": "a"}, "b"]) == ["a", "b"]
    assert _collect_ref_ids(None) == []


def test_fmt_export_department_uses_label_map():
    labels = {"depts": {"d1": "精品砂石事业部"}}
    assert _fmt_export_cell("department", "d1", labels) == "精品砂石事业部"
    assert _fmt_export_cell("department", "d1", None) == "d1"
    assert _fmt_export_cell("dept_code", "03", labels) == "03"


def test_fmt_export_person_multi():
    labels = {"users": {"u1": "张三", "u2": "李四"}}
    assert _fmt_export_cell("person_multi", ["u1", "u2"], labels) == "张三、李四"


def test_fmt_export_detail_table_summary():
    assert _fmt_export_cell("detail_table", [{"amount": 1}, {"amount": 2}]) == "2 行"
    assert _fmt_export_cell("detail_table", []) == "0 行"


def test_scan_export_ref_ids_from_detail_columns():
    person_ids: set[str] = set()
    dept_ids: set[str] = set()
    project_ids: set[str] = set()
    contract_ids: set[str] = set()
    customer_ids: set[str] = set()
    field_defs = [
        {"id": "department", "type": "department"},
        {
            "id": "payment_details",
            "type": "detail_table",
            "detail_table_columns": [
                {"id": "amount", "type": "number"},
                {"id": "sales_person", "type": "person"},
            ],
        },
    ]
    fd_data = {
        "department": "d1",
        "payment_details": [
            {"amount": 100, "sales_person": "u1"},
            {"amount": 200, "sales_person": {"id": "u2", "name": "李四"}},
        ],
    }
    _scan_export_ref_ids_from_defs(
        field_defs, fd_data,
        person_ids, dept_ids, project_ids, contract_ids, customer_ids,
    )
    assert dept_ids == {"d1"}
    assert person_ids == {"u1", "u2"}


def test_export_detail_columns_respects_visible_roles():
    dfd = {
        "id": "payment_details",
        "type": "detail_table",
        "detail_table_columns": [
            {"id": "amount", "type": "number", "label": "金额"},
            {
                "id": "secret", "type": "text", "label": "机密",
                "visible_roles": ["finance"],
            },
        ],
    }
    cols = _export_detail_columns(dfd, {"salesperson"})
    assert [c["id"] for c in cols] == ["amount"]
    cols_fin = _export_detail_columns(dfd, {"finance"})
    assert [c["id"] for c in cols_fin] == ["amount", "secret"]


def test_build_form_export_sheets_expands_details():
    data_fields = [
        {"id": "customer_name", "type": "customer", "label": "单位名称"},
        {
            "id": "payment_details",
            "type": "detail_table",
            "label": "来款明细",
            "detail_table_columns": [
                {"id": "payment_method", "type": "select", "label": "来款形式"},
                {"id": "amount", "type": "number", "label": "金额"},
            ],
        },
        {
            "id": "payment_allocation",
            "type": "detail_table",
            "label": "款项分配",
            "detail_table_columns": [
                {"id": "drawing_no", "type": "text", "label": "图纸编号"},
                {"id": "alloc_amount", "type": "number", "label": "分配金额"},
            ],
        },
    ]
    inst = SimpleNamespace(
        business_no="SK001",
        title="测试收款",
        status="completed",
        created_at=datetime(2026, 8, 20, 10, 30),
    )
    fd_data = {
        "customer_name": "c1",
        "payment_details": [
            {"payment_method": "电汇", "amount": 1000},
            {"payment_method": "承兑", "amount": 500},
        ],
        "payment_allocation": [
            {"drawing_no": "WMGF-1", "alloc_amount": 1500},
        ],
    }
    labels = {"customers": {"c1": "珠海粤裕丰钢铁有限公司"}}
    sheets = _build_form_export_sheets(
        sheet_title="收款登记",
        data_fields=data_fields,
        filtered_rows=[(inst, fd_data)],
        label_maps=labels,
        roles=set(),
        truncated=False,
    )
    assert len(sheets) == 3
    assert sheets[0][0] == "收款登记"
    main_headers, main_rows = sheets[0][1], sheets[0][2]
    assert main_headers[:5] == ["业务编号", "标题", "状态", "创建人", "创建时间"]
    assert main_rows[0][0] == "SK001"
    assert main_rows[0][3] == ""  # 无 initiator_id
    assert main_rows[0][5] == "珠海粤裕丰钢铁有限公司"
    assert main_rows[0][6] == "2 行"  # 来款明细摘要
    assert main_rows[0][7] == "1 行"  # 款项分配摘要

    detail_name, detail_headers, detail_rows = sheets[1]
    assert detail_name == "来款明细"
    assert detail_headers == ["业务编号", "标题", "状态", "来款形式", "金额"]
    assert len(detail_rows) == 2
    assert detail_rows[0] == ["SK001", "测试收款", "已通过", "电汇", "1000"]
    assert detail_rows[1][4] == "500"

    alloc_name, alloc_headers, alloc_rows = sheets[2]
    assert alloc_name == "款项分配"
    assert alloc_headers == ["业务编号", "标题", "状态", "图纸编号", "分配金额"]
    assert alloc_rows == [["SK001", "测试收款", "已通过", "WMGF-1", "1500"]]


def test_build_form_export_sheets_empty_detail_headers_only():
    data_fields = [
        {
            "id": "payment_details",
            "type": "detail_table",
            "label": "来款明细",
            "detail_table_columns": [
                {"id": "amount", "type": "number", "label": "金额"},
            ],
        },
    ]
    inst = SimpleNamespace(
        business_no="SK002",
        title="空明细",
        status="draft",
        created_at=None,
    )
    sheets = _build_form_export_sheets(
        sheet_title="收款登记",
        data_fields=data_fields,
        filtered_rows=[(inst, {"payment_details": []})],
        label_maps={},
        roles=set(),
        truncated=False,
    )
    assert len(sheets) == 2
    assert sheets[1][0] == "来款明细"
    assert sheets[1][1] == ["业务编号", "标题", "状态", "金额"]
    assert sheets[1][2] == []


def test_build_form_export_sheets_truncation_note():
    data_fields = [{"id": "remark", "type": "text", "label": "备注"}]
    inst = SimpleNamespace(
        business_no="X", title="t", status="running", created_at=None,
    )
    sheets = _build_form_export_sheets(
        sheet_title="表",
        data_fields=data_fields,
        filtered_rows=[(inst, {"remark": "a"})],
        label_maps={},
        roles=set(),
        truncated=True,
    )
    assert len(sheets[0][2]) == 2
    assert "导出上限" in str(sheets[0][2][1][0])
