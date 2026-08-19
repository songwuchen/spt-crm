"""数据日志展示增强。"""
from app.common.audit_display import (
    _collect_ids,
    _format_display_value,
    filter_create_log_changes,
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
