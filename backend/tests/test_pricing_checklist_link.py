# -*- coding: utf-8 -*-
from app.domains.lowcode.pricing_checklist_fields import (
    PICKABLE_EXCLUDED_STATUSES,
    PICK_COLUMNS,
    apply_pricing_checklist_fields,
    build_pricing_checklist_fill,
    pick_column_defs,
    resolve_design_office_department_id,
)


def test_apply_pricing_checklist_link_install_is_select_data():
    fields = [
        {"id": "link_install", "type": "text", "label": "选择安装图设计通知数据"},
        {"id": "install_serial_no", "type": "text", "label": "流水号-安装图设计通知"},
        {"id": "attachments", "type": "file", "label": "附件"},
    ]
    apply_pricing_checklist_fields(fields)
    by = {f["id"]: f for f in fields}
    assert by["link_install"]["type"] == "select_data"
    assert by["link_install"]["props"]["source_form_code"] == "install_drawing_notice"
    assert by["link_install"].get("required") is True
    assert by["install_serial_no"].get("form_editable") is False
    assert by["install_serial_no"]["props"].get("read_only") is True


def test_fill_install_notice_maps_serial_and_card():
    fill = build_pricing_checklist_fill(
        "link_install",
        business_no="AZT-1",
        form_data={
            "serial_no": "AZ20260817001",
            "design_card_no": "YY-20260817-01",
            "customer_name": "湖北优科",
            "applicant": "u-app",
            "department": "d-1",
        },
        user_names={"u-app": "张三"},
        dept_names={"d-1": "冶金矿山装备销售事业部"},
    )
    assert fill["install_serial_no"] == "AZ20260817001"
    assert fill["install_design_card_no"] == "YY-20260817-01"
    assert fill["install_order_person"] == "湖北优科"
    assert fill["install_applicant"] == "u-app"
    assert fill["install_department"] == "d-1"
    assert fill["summary_serial_no"] == "AZ20260817001"
    assert fill["contract_no"] == "无"
    assert fill["applicant"] == "张三"
    assert fill["business_dept"] == "冶金矿山装备销售事业部"


def test_fill_requisition_resolves_contract_id():
    cid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    fill = build_pricing_checklist_fill(
        "link_requisition",
        business_no="2026081301",
        form_data={"serial_no": "2026081301", "contract_no": cid, "applicant": "u1", "department": "d1"},
        user_names={"u1": "鲁亚飞"},
        dept_names={"d1": "冶金矿山装备销售事业部"},
        contract_names={cid: "WMGF202607087"},
    )
    assert fill["req_contract_no"] == "WMGF202607087"
    assert fill["contract_no"] == "WMGF202607087"


def test_builtin_pricing_checklist_link_install_select_data():
    from app.domains.lowcode.builtin_templates import get_builtin
    bt = get_builtin("pricing_checklist_hjqd")
    by = {f["id"]: f for f in (bt.get("field_definitions") or [])}
    assert by["link_install"]["type"] == "select_data"
    assert by["link_install"]["props"]["source_form_code"] == "install_drawing_notice"
    assert by["link_requisition"]["type"] == "select_data"
    assert by["link_cs_drawing"]["props"]["source_form_code"] == "cs_drawing_request"
    assert by["apply_datetime"]["type"] == "datetime"
    assert by["apply_datetime"]["props"]["default_today"] is True
    assert by["designer"].get("required") is True
    assert by["office"].get("required") is True
    assert by["pricing_qty"].get("default_value") == 1
    assert by["process_name"].get("required") is True
    assert by["link_install"].get("required") is True
    for fid in ("summary_serial_no", "design_card_no", "contract_no", "order_person", "applicant", "business_dept"):
        assert by[fid].get("form_editable") is False, fid
        assert by[fid]["props"].get("read_only") is True, fid


def test_apply_pricing_checklist_datetime_defaults_now():
    fields = [{"id": "apply_datetime", "type": "date", "label": "日期时间"}]
    apply_pricing_checklist_fields(fields)
    fd = fields[0]
    assert fd["type"] == "datetime"
    assert fd["props"]["default_today"] is True
    assert fd["props"].get("show_time") is True
    assert fd["props"].get("date_only") is None


def test_pickable_excludes_draft_and_withdrawn():
    assert "draft" in PICKABLE_EXCLUDED_STATUSES
    assert "withdrawn" in PICKABLE_EXCLUDED_STATUSES


def test_pick_columns_match_jdy_link_fields():
    coop = {c["key"] for c in pick_column_defs("research_coop_card")}
    assert coop == {"serial_no", "order_dept", "applicant", "drawing_no", "order_person"}
    inst = {c["title"] for c in pick_column_defs("install_drawing_notice")}
    assert "新设计卡号" in inst
    assert "install_drawing_notice" in PICK_COLUMNS
    prod = {c["key"] for c in pick_column_defs("install_drawing_notice", "prod_card_install")}
    assert prod == {"project_no_print", "customer_name", "sales_person", "matter"}


def test_resolve_design_office_department_id_prefers_design_room():
    rows = [
        ("d-sales", "冶金矿山装备销售事业部"),
        ("d-room", "设计一室"),
    ]
    assert resolve_design_office_department_id(rows) == "d-room"


def test_apply_pricing_checklist_pricing_qty_default():
    fields = [{"id": "pricing_qty", "type": "number", "label": "核价单数量"}]
    apply_pricing_checklist_fields(fields)
    assert fields[0]["default_value"] == 1
