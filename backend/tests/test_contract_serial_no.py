"""合同登记流水号生成与格式。"""

import pytest
from httpx import AsyncClient


async def test_contract_create_assigns_serial_no(client: AsyncClient, auth_headers: dict):
    """新建合同登记应自动生成简道云口径流水号 1.2.3-…"""
    h = auth_headers
    peek = (await client.get("/api/v1/contracts/peek-serial-no", headers=h)).json()
    assert peek["code"] == 0, peek
    expected_prefix = "1.2.3-"

    body = {
        "customer_id": None,
        "card_date": "2026-08-25",
        "order_date": "2026-08-25",
        "change_type": "new",
        "acquire_method": "协商一致",
        "amount_total": 1000,
        "as_draft": True,
        "registration_json": {"tax_included": "是", "is_export": "否", "need_install": "不需要安装", "info_complete": "是"},
    }
    # 需有关联客户 — 从列表取一个或跳过若环境无客户
    cust = (await client.get("/api/v1/customers?pageNo=1&pageSize=1", headers=h)).json()
    items = (cust.get("data") or {}).get("items") or []
    if not items:
        pytest.skip("no customers in test db")
    body["customer_id"] = items[0]["id"]
    body["department_id"] = items[0].get("department_id") or body.get("department_id")
    body["assignee_id"] = items[0].get("owner_id")

    r = await client.post("/api/v1/contracts", json=body, headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["code"] == 0, data
    serial = (data.get("data") or {}).get("contract", {}).get("serial_no") or ""
    assert serial.startswith(expected_prefix), serial
    assert len(serial) >= len(expected_prefix) + 13  # yyyyMMdd + 5 digits

    cid = data["data"]["contract"]["id"]
    await client.delete(f"/api/v1/contracts/{cid}", headers=h)
