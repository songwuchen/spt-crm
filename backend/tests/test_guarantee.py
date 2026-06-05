"""Guarantee (保函/保证金) tests — CRUD, return, expiring, auto-expire, summary."""

import datetime
from httpx import AsyncClient


async def test_guarantee_crud_return_summary(client: AsyncClient, auth_headers: dict):
    h = auth_headers
    future = (datetime.date.today() + datetime.timedelta(days=200)).isoformat()
    resp = await client.post("/api/v1/guarantees", json={
        "type": "performance", "customer_name": "保函客户", "amount": 100000,
        "issuer": "工商银行", "effective_date": datetime.date.today().isoformat(), "expiry_date": future,
    }, headers=h)
    data = resp.json()
    assert data["code"] == 0, f"create guarantee failed: {data}"
    gid = data["data"]["id"]
    assert data["data"]["guarantee_no"]
    assert data["data"]["status"] == "active"

    lst = await client.get("/api/v1/guarantees", headers=h, params={"status": "active"})
    assert lst.json()["code"] == 0 and lst.json()["data"]["total"] >= 1

    summ = (await client.get("/api/v1/guarantees/summary", headers=h)).json()
    assert summ["code"] == 0
    assert summ["data"]["active_amount"] >= 100000

    upd = await client.put(f"/api/v1/guarantees/{gid}", json={"amount": 120000}, headers=h)
    assert abs(upd.json()["data"]["amount"] - 120000) < 1e-6

    ret = await client.post(f"/api/v1/guarantees/{gid}/return", json={"return_date": datetime.date.today().isoformat()}, headers=h)
    assert ret.json()["code"] == 0 and ret.json()["data"]["status"] == "returned"
    assert ret.json()["data"]["return_date"]

    exp = await client.get("/api/v1/guarantees/export/excel", headers=h)
    assert exp.status_code == 200

    await client.delete(f"/api/v1/guarantees/{gid}", headers=h)


async def test_guarantee_expiring_and_autoexpire(client: AsyncClient, auth_headers: dict):
    h = auth_headers
    soon = (datetime.date.today() + datetime.timedelta(days=10)).isoformat()
    past = (datetime.date.today() - datetime.timedelta(days=5)).isoformat()

    g_soon = await client.post("/api/v1/guarantees", json={
        "type": "advance", "customer_name": "即将到期", "amount": 5000, "expiry_date": soon,
    }, headers=h)
    soon_id = g_soon.json()["data"]["id"]
    g_past = await client.post("/api/v1/guarantees", json={
        "type": "quality", "customer_name": "已过期", "amount": 3000, "expiry_date": past,
    }, headers=h)
    past_id = g_past.json()["data"]["id"]

    # expiring within 30 days includes the soon one
    expiring = await client.get("/api/v1/guarantees/expiring", headers=h, params={"days": 30})
    ids = [g["id"] for g in expiring.json()["data"]]
    assert soon_id in ids

    # listing triggers auto-expire of the past-due one
    await client.get("/api/v1/guarantees", headers=h)
    past_after = await client.get(f"/api/v1/guarantees/{past_id}", headers=h)
    assert past_after.json()["data"]["status"] == "expired"

    await client.delete(f"/api/v1/guarantees/{soon_id}", headers=h)
    await client.delete(f"/api/v1/guarantees/{past_id}", headers=h)


async def test_guarantee_no_auth(client: AsyncClient):
    assert (await client.get("/api/v1/guarantees")).json()["code"] != 0
