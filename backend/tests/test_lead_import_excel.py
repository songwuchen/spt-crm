"""Unit tests for lead Excel import header mapping / normalization."""
from app.domains.lead.import_excel import (
    LEAD_IMPORT_HEADERS,
    lead_import_sample_row,
    map_header_row,
    row_to_payload,
)


def test_sample_row_matches_headers():
    assert len(lead_import_sample_row()) == len(LEAD_IMPORT_HEADERS)


def test_parse_csv_upload():
    from app.domains.lead.import_excel import parse_upload_rows, rows_for_preview
    raw = "项目名称,来源,公司名称\nA项目,自报,公司甲\n".encode("utf-8-sig")
    rows = parse_upload_rows(raw, "x.csv")
    headers, data = rows_for_preview(rows)
    assert headers[0] == "项目名称"
    assert data[0][0] == "A项目"


def test_map_new_headers():
    colmap = map_header_row(tuple(LEAD_IMPORT_HEADERS))
    assert colmap["title"] == 0
    assert colmap["category"] == 1
    assert colmap["company_name"] == 2
    assert colmap["department_name"] == LEAD_IMPORT_HEADERS.index("部门")
    assert colmap["source"] == LEAD_IMPORT_HEADERS.index("线索来源")


def test_map_legacy_headers():
    headers = ["标题", "公司名称", "联系人", "联系电话", "邮箱", "来源",
               "客户类型", "行业", "类别", "地区", "业务日期", "负责人"]
    colmap = map_header_row(headers)
    assert colmap["title"] == 0
    assert colmap["category"] == 8  # 类别
    assert colmap["source"] == 5  # 旧「来源」→ 线索来源
    assert colmap["contact_email"] == 4
    assert colmap["region"] == 9
    assert colmap["owner_name"] == 11


def test_row_to_payload_new_template():
    colmap = map_header_row(tuple(LEAD_IMPORT_HEADERS))
    row = tuple(lead_import_sample_row())
    p = row_to_payload(row, colmap)
    assert p["title"] == "某某设备采购线索"
    assert p["category"] == "self_reported"
    assert p["country_type"] == "domestic"
    assert p["customer_type"] == "design_institute"
    assert p["industry"] == "screening_metallurgy"
    assert p["has_internal_conflict"] == "否"
    assert p["project_activity"] == "拟建"
    assert p["source"] == "expo"
    assert p["department_name"] == "信息情报部"
    assert p["province"] == "浙江省"


def test_legacy_source_column_as_lead_source():
    """旧模板只有「来源=展会」且无「类别」时，应落到线索来源。"""
    headers = ["标题", "公司名称", "来源"]
    colmap = map_header_row(headers)
    p = row_to_payload(("项目A", "公司A", "展会"), colmap)
    assert p["title"] == "项目A"
    assert p.get("category") is None
    assert p["source"] == "expo"
