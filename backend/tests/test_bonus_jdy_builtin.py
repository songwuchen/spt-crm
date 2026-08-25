"""Builtin templates: 业务奖金模块三表单."""
from app.domains.lowcode.builtin_templates import get_builtin, list_builtin


def test_builtin_templates_include_bonus_keys():
    keys = {t["key"] for t in list_builtin()}
    assert "biz_bonus_transfer" in keys
    assert "biz_bonus_biz_initiate" in keys
    assert "commission_database" in keys


def test_bonus_transfer_pack():
    bt = get_builtin("biz_bonus_transfer")
    assert bt is not None
    assert bt["category"] == "财务"
    from app.domains.lowcode._bonus_jdy_generated import BONUS_JDY
    pack = BONUS_JDY["biz_bonus_transfer"]
    fields = pack["field_definitions"]
    assert any(f.get("id") == "bonus_no" for f in fields)
    assert any(f.get("id") == "payment_status" for f in fields)
    assert len(pack["flow_nodes"]) >= 7


def test_commission_database_pack():
    from app.domains.lowcode._bonus_jdy_generated import BONUS_JDY
    pack = BONUS_JDY["commission_database"]
    assert len(pack["field_definitions"]) >= 10
    assert len(pack["flow_nodes"]) >= 5
