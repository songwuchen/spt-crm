"""合同选择弹窗列表。"""
import asyncio
from types import SimpleNamespace

from app.domains.lowcode.contract_pick import (
    _change_status_label,
    _scalar_person_ref,
    contract_pick_label,
    list_pickable_contracts_page,
    resolve_contract_assignee_id,
    resolve_contract_sales_person_ref,
)
from app.domains.lowcode.invoice_application_fields import build_invoice_fill_from_contract


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


def test_scalar_person_ref():
    assert _scalar_person_ref("4f7b0135-813e-4060-8817-30c9ef3e169b") == (
        "4f7b0135-813e-4060-8817-30c9ef3e169b", None,
    )
    assert _scalar_person_ref("张三") == (None, "张三")
    assert _scalar_person_ref({"id": "u1", "name": "李四"}) == ("u1", "李四")
    assert _scalar_person_ref([{"id": "u2"}]) == ("u2", None)


def test_resolve_contract_assignee_id_from_name(monkeypatch):
    async def _fake_resolve(db, tenant_id, *, owner_id, owner_name):
        assert tenant_id == "t1"
        if owner_name == "杨沙沙":
            return "user-yss"
        return owner_id

    monkeypatch.setattr(
        "app.domains.openapi.service.resolve_owner_id",
        _fake_resolve,
    )
    c = SimpleNamespace(
        assignee_id=None,
        assignee_name="杨沙沙",
        registration_json={},
    )

    async def _run():
        return await resolve_contract_assignee_id(None, "t1", c)

    assert asyncio.run(_run()) == "user-yss"


def test_resolve_contract_sales_person_ref_falls_back_to_name(monkeypatch):
    async def _no_uid(db, tenant_id, contract):
        return None

    monkeypatch.setattr(
        "app.domains.lowcode.contract_pick.resolve_contract_assignee_id",
        _no_uid,
    )
    c = SimpleNamespace(
        assignee_id=None,
        assignee_name="杨沙沙",
        registration_json={},
    )

    async def _run():
        return await resolve_contract_sales_person_ref(None, "t1", c)

    assert asyncio.run(_run()) == "杨沙沙"


def test_invoice_fill_uses_resolved_assignee():
    fill = build_invoice_fill_from_contract(
        contract_no="KS24395",
        drawing_no="WMGF202411120",
        peer_contract_no=None,
        assignee_id="user-yss",
        customer_name="甲公司",
        customer_code="C1",
        amount_total=100,
        taxpayer_id="T1",
        invoice_address_phone="addr",
        bank_account="bank",
        key_clauses_json=[],
    )
    assert fill["sales_person"] == "user-yss"
