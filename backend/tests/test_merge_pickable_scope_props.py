# -*- coding: utf-8 -*-
from app.domains.lowcode.service import _merge_field_props, _merge_builtin_field_defs


def test_merge_keeps_tenant_pickable_scope_when_builtin_empty():
    want = [{"id": "transfer_packaging_users", "type": "person", "label": "转新乡"}]
    current = [{
        "id": "transfer_packaging_users",
        "type": "person",
        "label": "转新乡、工艺包装",
        "props": {"pickable_scope": {"scope_code": "fa-zxxgy"}},
    }]
    out = _merge_builtin_field_defs(want, current)
    assert out[0]["props"]["pickable_scope"]["scope_code"] == "fa-zxxgy"
    assert out[0]["label"] == "转新乡、工艺包装"  # tenant label override


def test_merge_builtin_scope_wins():
    want = [{
        "id": "design_assignees",
        "type": "person_multi",
        "props": {"pickable_scope": {"scope_code": "room_leaders", "filter_by_fields": ["offices"]}},
    }]
    current = [{
        "id": "design_assignees",
        "props": {"pickable_scope": {"scope_code": "old_scope"}},
    }]
    out = _merge_builtin_field_defs(want, current)
    assert out[0]["props"]["pickable_scope"]["scope_code"] == "room_leaders"


def test_merge_field_props_unit():
    assert _merge_field_props(None, None) is None
    m = _merge_field_props({}, {"pickable_scope": {"scope_code": "fa-zxxgy"}})
    assert m["pickable_scope"]["scope_code"] == "fa-zxxgy"
