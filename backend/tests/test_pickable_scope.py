from app.domains.lowcode.pickable_scope import (
    pickable_scope_from_jdy_limit,
    role_codes_from_field,
    scope_code_from_field,
    filter_by_fields_from_field,
    JDY_ROLE_TO_CRM_CODE,
)


def test_jdy_room_leader_role_mapped():
    assert JDY_ROLE_TO_CRM_CODE["63815e3a7fb607000acc9195"] == "room_leader"


def test_pickable_scope_from_jdy_limit():
    assert pickable_scope_from_jdy_limit(None) is None
    assert pickable_scope_from_jdy_limit({}) is None
    assert pickable_scope_from_jdy_limit({"roles": ["unknown"]}) is None
    assert pickable_scope_from_jdy_limit(
        {"roles": ["63815e3a7fb607000acc9195"]}
    ) == {
        "scope_code": "room_leaders",
    }


def test_role_codes_from_field():
    assert role_codes_from_field(None) == []
    assert role_codes_from_field({"id": "x"}) == []
    assert role_codes_from_field({
        "id": "design_assignees",
        "props": {"pickable_scope": {"role_codes": ["room_leader"]}},
    }) == ["room_leader"]
    # 有 scope_code 时不再走 role_codes 分支
    assert role_codes_from_field({
        "id": "design_assignees",
        "props": {"pickable_scope": {"scope_code": "room_leaders", "role_codes": ["room_leader"]}},
    }) == []


def test_scope_code_from_field():
    assert scope_code_from_field(None) is None
    assert scope_code_from_field({
        "props": {"pickable_scope": {"scope_code": "room_leaders"}},
    }) == "room_leaders"
    assert filter_by_fields_from_field({
        "props": {"pickable_scope": {"filter_by_fields": ["offices"]}},
    }) == ["offices"]
