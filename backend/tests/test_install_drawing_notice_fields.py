"""安装图设计通知：创建/审批字段阶段。"""
from app.domains.lowcode.dept_code import (
    apply_design_card_serial_rules,
    apply_install_drawing_serial_no_field,
)
from app.domains.lowcode.install_drawing_notice_fields import (
    apply_install_drawing_notice_fields,
)


def test_apply_install_drawing_notice_fields_stages():
    fields = [
        {"id": "project_no", "type": "select", "label": "项目号选择", "required": True,
         "available_on_create": True, "fill_stage": "initiator"},
        {"id": "sales_person", "type": "person", "label": "业务员",
         "available_on_create": True, "fill_stage": "initiator"},
        {"id": "design_dispatch", "type": "radio", "label": "设计单分派", "required": True},
        {"id": "need_submit_drawing", "type": "radio", "label": "是否上交图纸", "required": True},
        {"id": "remark", "type": "textarea", "label": "备注", "required": True},
        {"id": "score_attitude", "type": "number", "label": "态度分数", "required": True},
        {"id": "change_scheme", "type": "detail_table", "label": "修改方案"},
        {"id": "offices_multi", "type": "department", "label": "科室多选",
         "available_on_create": False, "fill_stage": "approver"},
    ]
    apply_install_drawing_notice_fields(fields)
    by = {f["id"]: f for f in fields}

    assert by["project_no"]["type"] == "project"
    assert by["project_no"]["props"]["prefer_code"] is True
    assert by["project_no"]["props"]["project_fill"] == "install_notice"
    assert by["sales_person"]["form_editable"] is False
    assert by["design_dispatch"]["available_on_create"] is False
    assert by["need_submit_drawing"]["available_on_create"] is False
    assert by["need_submit_drawing"]["required"] is False
    assert by["remark"]["available_on_create"] is False
    assert by["score_attitude"]["available_on_create"] is False
    assert by["change_scheme"]["available_on_create"] is False
    assert by["offices_multi"]["type"] == "department_multi"
    assert by["project_no"]["available_on_create"] is True


def test_install_serial_no_independent_of_design_card():
    fields = [
        {"id": "design_card_no", "type": "text", "label": "新设计卡号"},
        {"id": "apply_datetime", "type": "date", "label": "日期时间"},
        {"id": "dept_code", "type": "text", "label": "部门编号"},
    ]
    apply_design_card_serial_rules(fields)
    apply_install_drawing_serial_no_field(fields)
    by = {f["id"]: f for f in fields}
    assert by["serial_no"]["type"] == "auto_number"
    assert by["serial_no"]["label"] == "流水号"
    assert by["design_card_no"]["type"] == "auto_number"
    assert "设计卡" in by["design_card_no"]["label"]
    assert by["design_card_no"]["label"] != "流水号"
    sn_rules = by["serial_no"]["props"]["serial_rules"]
    card_rules = by["design_card_no"]["props"]["serial_rules"]
    assert sn_rules != card_rules
    assert any(r.get("digits") == 4 for r in sn_rules if r.get("type") == "counter")
    assert any(r.get("field_id") == "dept_code" for r in card_rules)
