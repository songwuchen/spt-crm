# -*- coding: utf-8 -*-
from app.domains.lowcode.pricing_checklist_fields import (
    CONTRACT_OUTSOURCE_PROD_CARD_LINK,
    PICKABLE_EXCLUDED_STATUSES,
    PICKABLE_FORM_CODES,
    PROD_CARD_SUPPLEMENT_PICKABLE_EXCLUDED_STATUSES,
    _pick_cell,
    _prod_card_form_contract_ref_conds,
    _resolve_prod_card_contract_for_outsource,
    apply_contract_row_to_lookup_maps,
    build_contract_outsource_prod_card_fill,
    pick_column_defs,
    pickable_excluded_statuses,
)


def test_prod_card_supplement_in_pickable_form_codes():
    assert "prod_card_supplement" in PICKABLE_FORM_CODES


def test_pick_columns_for_contract_outsource_link():
    cols = {c["key"] for c in pick_column_defs(
        "prod_card_supplement", CONTRACT_OUTSOURCE_PROD_CARD_LINK,
    )}
    assert cols == {"serial_no", "drawing_no", "design_assign", "office"}


def test_prod_card_form_contract_ref_conds_empty():
    assert _prod_card_form_contract_ref_conds([], []) is None


def test_prod_card_form_contract_ref_conds_matches_serial_in_drawing_no_query():
    cid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    cond = _prod_card_form_contract_ref_conds(
        [cid],
        ["1.2.3-2026082201503", "WMGF202608141"],
    )
    assert cond is not None


def test_prod_card_supplement_pickable_allows_draft():
    assert "draft" in PICKABLE_EXCLUDED_STATUSES
    assert "draft" not in PROD_CARD_SUPPLEMENT_PICKABLE_EXCLUDED_STATUSES
    assert pickable_excluded_statuses("prod_card_supplement") == ("withdrawn",)
    assert pickable_excluded_statuses("install_drawing_notice") == PICKABLE_EXCLUDED_STATUSES


def test_build_contract_outsource_prod_card_fill_maps_fields():
    cid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    fill = build_contract_outsource_prod_card_fill(
        business_no="1.2.812800001",
        form_data={
            "serial_no": "1.2.812800001",
            "drawing_no_query": cid,
            "no_drawing_no": "WMGF202608141",
            "design_assignees": ["u1", "u2"],
            "offices": ["d1"],
        },
        user_names={"u1": "张三", "u2": "李四"},
        dept_names={"d1": "设计科"},
        contract_names={cid: "WMGF202608141"},
    )
    assert fill["prod_card_serial"] == "1.2.812800001"
    assert fill["contract_no"] == cid
    assert fill["design_assign"] == ["u1", "u2"]
    assert fill["office"] == ["d1"]


def test_build_contract_outsource_prod_card_fill_supplement_contract_select():
    cid = "bbbbbbbb-bbbb-cccc-dddd-eeeeeeeeeeee"
    fill = build_contract_outsource_prod_card_fill(
        business_no="1.2.812800002",
        form_data={
            "serial_no": "1.2.812800002",
            "is_supplement": "是",
            "contract_no_select": cid,
            "yes_contract_no": "YJ26527",
            "design_assignees": "u9",
            "offices": "d9",
        },
        user_names={"u9": "王五"},
        dept_names={"d9": "工艺科"},
        contract_names={cid: "YJ26527"},
    )
    assert fill["prod_card_serial"] == "1.2.812800002"
    assert fill["contract_no"] == cid
    assert fill["design_assign"] == "u9"
    assert fill["office"] == "d9"


def test_resolve_prod_card_contract_serial_ref_shows_drawing_no():
    cid = "ee6049dc-e41f-4327-8ec6-14fa3f154aba"
    serial = "1.2.3-2026082201503"
    names: dict[str, str] = {}
    id_by_ref: dict[str, str] = {}
    apply_contract_row_to_lookup_maps(
        names, id_by_ref,
        contract_id=cid,
        serial_no=serial,
        contract_no="YJ26527",
        drawing_no="WMGF202608141",
    )
    resolved_id, label = _resolve_prod_card_contract_for_outsource(
        {"drawing_no_query": serial},
        contract_names=names,
        contract_id_by_ref=id_by_ref,
    )
    assert resolved_id == cid
    assert label == "WMGF202608141"


def test_pick_cell_drawing_no_prefers_drawing_over_serial():
    cid = "ee6049dc-e41f-4327-8ec6-14fa3f154aba"
    serial = "1.2.3-2026082201503"
    names: dict[str, str] = {}
    id_by_ref: dict[str, str] = {}
    apply_contract_row_to_lookup_maps(
        names, id_by_ref,
        contract_id=cid,
        serial_no=serial,
        contract_no="YJ26527",
        drawing_no="WMGF202608141",
    )
    cell = _pick_cell(
        "drawing_no",
        business_no="1.2.817755",
        form_data={"drawing_no_query": serial},
        user_names={},
        dept_names={},
        contract_names=names,
    )
    assert cell == "WMGF202608141"


def test_build_contract_outsource_prod_card_fill_resolves_serial_ref_to_uuid():
    cid = "ee6049dc-e41f-4327-8ec6-14fa3f154aba"
    serial = "1.2.3-2026082201503"
    names: dict[str, str] = {}
    id_by_ref: dict[str, str] = {}
    apply_contract_row_to_lookup_maps(
        names, id_by_ref,
        contract_id=cid,
        serial_no=serial,
        contract_no="YJ26527",
        drawing_no="WMGF202608141",
    )
    fill = build_contract_outsource_prod_card_fill(
        business_no="1.2.817755",
        form_data={"serial_no": "1.2.817755", "drawing_no_query": serial},
        contract_names=names,
        contract_id_by_ref=id_by_ref,
    )
    assert fill["contract_no"] == cid
