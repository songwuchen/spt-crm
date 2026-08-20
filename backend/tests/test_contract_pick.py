"""合同选择弹窗列表。"""
from app.domains.lowcode.contract_pick import (
    _change_status_label,
    contract_pick_label,
    list_pickable_contracts_page,
)


def test_change_status_label():
    assert _change_status_label("new") == "新增"
    assert _change_status_label("change") == "变动"
    assert _change_status_label("新增") == "新增"


def test_contract_pick_label():
    assert contract_pick_label(
        drawing_no="WMGF001", contract_no="HT001", cid="x",
    ) == "WMGF001（HT001）"
    assert contract_pick_label(
        drawing_no="WMGF001", contract_no="WMGF001", cid="x",
    ) == "WMGF001"
