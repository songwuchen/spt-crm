"""FieldDefinition.props 接受 null（设计器回传内置字段时常见）。"""
from app.domains.lowcode.schemas import FieldDefinition, SaveDesignRequest


def test_field_definition_props_null_coerces_to_dict():
    fd = FieldDefinition.model_validate({
        "id": "elec_workshop_fill",
        "type": "detail_table",
        "label": "电气车间填写",
        "props": None,
    })
    assert fd.props == {}


def test_save_design_accepts_null_props_at_index():
    req = SaveDesignRequest.model_validate({
        "field_definitions": [
            {"id": "a", "type": "text", "label": "A"},
            {"id": "b", "type": "detail_table", "label": "B", "props": None},
        ],
        "layout_definition": {},
        "rule_definitions": [],
    })
    assert req.field_definitions[1].props == {}
