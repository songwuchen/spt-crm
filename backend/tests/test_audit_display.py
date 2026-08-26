"""数据日志展示增强。"""
from app.common.audit_display import (
    _collect_ids,
    _compute_detail_table_diff,
    _format_detail_table_rows,
    _format_display_value,
    filter_create_log_changes,
    hydrate_audit_log_detail,
)


def test_collect_ids_parses_json_array_string():
    assert _collect_ids('["1ba1708e-62ee-45af-8f52-483b5637ce0b"]') == [
        "1ba1708e-62ee-45af-8f52-483b5637ce0b",
    ]


def test_format_display_value_resolves_unknown_person_multi():
    uid = "1ba1708e-62ee-45af-8f52-483b5637ce0b"
    labels = {uid: "王东明"}
    out = _format_display_value([uid], "", labels, {})
    assert out == "王东明"


def test_create_log_prefers_serial_no():
    changes = {
        "serial_no": {"old": None, "new": "24.13-202605234535"},
        "applicant": {"old": None, "new": "uuid-1"},
        "service_location": {"old": None, "new": "哈密"},
    }
    out = filter_create_log_changes(changes)
    assert list(out.keys()) == ["serial_no"]
    assert out["serial_no"]["new"] == "24.13-202605234535"


def test_create_log_skips_empty_without_serial():
    changes = {
        "remark": {"old": None, "new": ""},
        "service_location": {"old": None, "new": "哈密"},
    }
    out = filter_create_log_changes(changes)
    assert list(out.keys()) == ["service_location"]


def test_format_detail_table_rows_readable():
    field_def = {
        "id": "std_room_fill",
        "type": "detail_table",
        "detail_table_columns": [
            {"id": "material_code", "type": "text", "label": "物料代码"},
            {"id": "product_name", "type": "text", "label": "产品名称"},
        ],
    }
    rows = [{"material_code": "02.01.04.079", "product_name": "复合陶瓷衬板"}]
    out = _format_detail_table_rows(rows, field_def, {}, {})
    assert "物料代码 02.01.04.079" in out
    assert "产品名称 复合陶瓷衬板" in out
    assert "[object Object]" not in out


def test_compute_detail_table_diff_cell_change():
    field_def = {
        "id": "std_room_fill",
        "type": "detail_table",
        "detail_table_columns": [
            {"id": "material_code", "type": "text", "label": "物料代码"},
            {"id": "product_name", "type": "text", "label": "产品名称"},
            {"id": "spec_model", "type": "text", "label": "规格型号"},
        ],
    }
    old = [{"material_code": "02.01.04.076", "product_name": "复合陶瓷衬板", "spec_model": "66+4+20(20*20"}]
    new = [{"material_code": "02.01.04.079", "product_name": "复合陶瓷衬板", "spec_model": "66+4+20(17.5*1"}]
    diff = _compute_detail_table_diff(old, new, field_def, {}, {})
    assert diff is not None
    assert diff["columns"][0]["label"] == "物料代码"
    row = diff["rows"][0]
    by_col = {c["col_id"]: c for c in row["cells"]}
    assert by_col["material_code"]["changed"] is True
    assert by_col["material_code"]["old"] == "02.01.04.076"
    assert by_col["material_code"]["new"] == "02.01.04.079"
    assert by_col["product_name"]["changed"] is False


def test_enrich_detail_table_json_legacy_display():
    import asyncio
    from unittest.mock import AsyncMock
    from app.common.audit_display import enrich_form_changes_for_display

    field_def = {
        "id": "std_room_fill",
        "type": "detail_table",
        "label": "标准化室填写",
        "detail_table_columns": [
            {"id": "contract_line_ref", "type": "text", "label": "对应的合同明细"},
            {"id": "material_code_time", "type": "datetime", "label": "填写物料代码时间"},
        ],
    }
    changes = {
        "std_room_fill": {
            "label": "标准化室填写",
            "old": [{"contract_line_ref": "1", "material_code_time": "2026-08-26 08:32:43"}],
            "new": [
                {"contract_line_ref": "1", "material_code_time": "2026-08-26 08:32:43"},
                {"contract_line_ref": "2"},
            ],
            "display_old": '[{"contract_line_ref": "1"}]',
            "display_new": '[{"contract_line_ref": "1"}, {"contract_line_ref": "2"}]',
        }
    }
    out = asyncio.run(enrich_form_changes_for_display(AsyncMock(), "tid", changes, [field_def]))
    ch = out["std_room_fill"]
    assert ch.get("detail_table_diff")
    assert "对应的合同明细" in (ch.get("display_new") or "")
    assert "[object Object]" not in (ch.get("display_new") or "")
