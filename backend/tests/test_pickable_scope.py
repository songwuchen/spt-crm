from app.domains.lowcode.pickable_scope import (
    pickable_scope_from_jdy_limit,
    role_codes_from_field,
    scope_code_from_field,
    filter_by_fields_from_field,
    strip_spt_scheme_pickable_scopes,
    DEFAULT_TENANT_ID,
    JDY_ROLE_TO_CRM_CODE,
    JDY_ROLE_TO_SCOPE_CODE,
)


def test_jdy_room_leader_role_mapped():
    assert JDY_ROLE_TO_CRM_CODE["63815e3a7fb607000acc9195"] == "room_leader"


def test_jdy_dept_dispatch_ygb_role_mapped():
    assert JDY_ROLE_TO_SCOPE_CODE["5f46008a6344180006bfa81a"] == "dept_dispatch_ygb"
    assert pickable_scope_from_jdy_limit(
        {"roles": ["5f46008a6344180006bfa81a"]}
    ) == {"scope_code": "dept_dispatch_ygb"}


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


def test_apply_scheme_design_person_scope_rules():
    from app.domains.lowcode.pickable_scope import apply_scheme_design_person_scope_rules

    defs = [
        {
            "id": "designer",
            "props": {"pickable_scope": {"scope_code": "room_leaders"}},
        },
        {
            "id": "design_assignees",
            "props": {
                "pickable_scope": {
                    "scope_code": "room_leaders",
                    "filter_by_fields": ["offices"],
                },
            },
        },
    ]
    apply_scheme_design_person_scope_rules(defs)
    assert "pickable_scope" not in (defs[0].get("props") or {})
    assert defs[1]["props"]["pickable_scope"] == {"scope_code": "room_leaders"}
    assert "filter_by_fields" not in defs[1]["props"]["pickable_scope"]


def test_merge_field_props_clears_designer_scope():
    from app.domains.lowcode.service import _merge_field_props

    merged = _merge_field_props(
        {"default_current_user": True},
        {"pickable_scope": {"scope_code": "room_leaders"}},
        field_id="designer",
    )
    assert merged == {"default_current_user": True}
    assert "pickable_scope" not in merged


def test_strip_spt_scheme_pickable_scopes_only_non_default():
    defs = [
        {"id": "design_assignees", "props": {"pickable_scope": {"scope_code": "room_leaders"}}},
        {"id": "applicant", "props": {"default_current_user": True}},
    ]
    kept = strip_spt_scheme_pickable_scopes(DEFAULT_TENANT_ID, defs)
    assert kept[0]["props"]["pickable_scope"]["scope_code"] == "room_leaders"
    stripped = strip_spt_scheme_pickable_scopes("9365954a-a6b3-461a-b478-27e786b08c78", defs)
    assert stripped[0].get("props") in (None, {})
    assert stripped[1]["props"]["default_current_user"] is True
