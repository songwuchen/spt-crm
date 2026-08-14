"""download_roles：附件字段可读/可下载白名单。"""
from app.domains.lowcode.field_permission import (
    field_downloadable,
    filter_read,
    sanitize_write,
)


ATTACH_DEFS = [
    {
        "id": "attachments",
        "type": "file",
        "label": "附件",
        "download_roles": ["finance", "finance_manager"],
    },
    {"id": "title", "type": "text", "label": "标题"},
]

ATT_VAL = [{"id": "att-1", "name": "核价.xlsx"}]


def test_filter_read_strips_attachments_without_download_role():
    defs, data = filter_read(
        ATTACH_DEFS,
        {"attachments": ATT_VAL, "title": "T"},
        ["sales_rep"],
    )
    assert data["title"] == "T"
    assert data["attachments"] == []
    att_fd = next(f for f in defs if f["id"] == "attachments")
    assert att_fd.get("download_denied") is True


def test_filter_read_keeps_attachments_for_finance():
    defs, data = filter_read(
        ATTACH_DEFS,
        {"attachments": ATT_VAL, "title": "T"},
        ["finance"],
    )
    assert data["attachments"] == ATT_VAL
    att_fd = next(f for f in defs if f["id"] == "attachments")
    assert not att_fd.get("download_denied")


def test_filter_read_creator_bypass():
    _, data = filter_read(
        ATTACH_DEFS,
        {"attachments": ATT_VAL},
        ["sales_rep"],
        is_creator=True,
    )
    assert data["attachments"] == ATT_VAL


def test_sanitize_write_blocks_clearing_without_download():
    out = sanitize_write(
        {"attachments": [], "title": "x"},
        {"attachments": ATT_VAL, "title": "old"},
        ATTACH_DEFS,
        ["sales_rep"],
    )
    assert out["attachments"] == ATT_VAL
    assert out["title"] == "x"


def test_sanitize_write_finance_can_replace():
    new_val = [{"id": "att-2", "name": "b.xlsx"}]
    out = sanitize_write(
        {"attachments": new_val},
        {"attachments": ATT_VAL},
        ATTACH_DEFS,
        ["finance_manager"],
    )
    assert out["attachments"] == new_val


def test_field_downloadable_unrestricted_when_empty():
    fd = {"id": "a", "type": "file"}
    assert field_downloadable(fd, {"sales_rep"}) is True


def test_pricing_checklist_builtin_has_download_roles():
    from app.domains.lowcode.builtin_templates import get_builtin
    bt = get_builtin("pricing_checklist_hjqd")
    assert bt
    by_id = {f["id"]: f for f in bt["field_definitions"] if isinstance(f, dict)}
    for fid in ("attachments", "images"):
        assert by_id[fid].get("download_roles") == ["finance", "finance_manager"]
