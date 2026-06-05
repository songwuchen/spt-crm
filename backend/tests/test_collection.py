"""Collection (应收清欠) tests — AR aging, debt transfer + claim, follow-ups."""

import datetime
from httpx import AsyncClient


async def test_ar_aging(client: AsyncClient, auth_headers: dict):
    h = auth_headers
    today = datetime.date.today().isoformat()
    cust = await client.post("/api/v1/customers", json={"name": "账龄测试客户"}, headers=h)
    cust_id = cust.json()["data"]["id"]
    proj = await client.post("/api/v1/projects", json={"name": "账龄商机", "customer_id": cust_id}, headers=h)
    proj_id = proj.json()["data"]["id"]
    c = await client.post(f"/api/v1/projects/{proj_id}/contracts", json={"amount_total": 100000}, headers=h)
    contract_id = c.json()["data"]["contract"]["id"]
    await client.post(f"/api/v1/contracts/{contract_id}/sign", json={"signed_date": today}, headers=h)
    await client.post(f"/api/v1/projects/{proj_id}/payment_records", json={"amount": 30000, "received_date": today}, headers=h)

    rep = await client.get("/api/v1/collection/aging", headers=h)
    data = rep.json()
    assert data["code"] == 0, f"aging failed: {data}"
    row = next((r for r in data["data"]["rows"] if r["customer_id"] == cust_id), None)
    assert row is not None, "customer not in aging report"
    assert abs(row["outstanding"] - 70000) < 0.5
    assert abs(row["d0_30"] - 70000) < 0.5  # signed today -> 0-30 bucket

    exp = await client.get("/api/v1/collection/aging/export/excel", headers=h)
    assert exp.status_code == 200

    await client.delete(f"/api/v1/contracts/{contract_id}", headers=h)
    await client.delete(f"/api/v1/projects/{proj_id}", headers=h)
    await client.delete(f"/api/v1/customers/{cust_id}", headers=h)


async def test_debt_transfer_claim_flow(client: AsyncClient, auth_headers: dict):
    h = auth_headers
    cust = await client.post("/api/v1/customers", json={"name": "清欠移交客户"}, headers=h)
    cust_id = cust.json()["data"]["id"]

    # create transfer -> pending
    t = await client.post("/api/v1/collection/transfers", json={
        "customer_id": cust_id, "customer_name": "清欠移交客户",
        "transfer_type": "sales_to_collection", "debt_amount": 50000,
        "to_department_name": "清欠办", "debt_note": "长期拖欠",
    }, headers=h)
    td = t.json()
    assert td["code"] == 0, f"create transfer failed: {td}"
    tid = td["data"]["id"]
    assert td["data"]["status"] == "pending"
    assert td["data"]["transfer_no"]

    # pool listing
    pool = await client.get("/api/v1/collection/transfers", headers=h, params={"status": "pending"})
    assert any(x["id"] == tid for x in pool.json()["data"]["items"])

    # claim (抢单)
    claim = await client.post(f"/api/v1/collection/transfers/{tid}/claim", json={"commitment": "3个月内清收"}, headers=h)
    cd = claim.json()
    assert cd["code"] == 0 and cd["data"]["status"] == "claimed"
    claimer = cd["data"]["claimed_by_name"]
    assert claimer

    # customer owner should now be the claimer
    cust_after = await client.get(f"/api/v1/customers/{cust_id}", headers=h)
    assert cust_after.json()["data"]["owner_name"] == claimer

    # cannot withdraw after claim
    w = await client.post(f"/api/v1/collection/transfers/{tid}/withdraw", headers=h)
    assert w.json()["code"] != 0

    await client.delete(f"/api/v1/collection/transfers/{tid}", headers=h)
    await client.delete(f"/api/v1/customers/{cust_id}", headers=h)


async def test_debt_transfer_withdraw(client: AsyncClient, auth_headers: dict):
    h = auth_headers
    t = await client.post("/api/v1/collection/transfers", json={
        "customer_name": "撤回测试", "debt_amount": 1000,
    }, headers=h)
    tid = t.json()["data"]["id"]
    w = await client.post(f"/api/v1/collection/transfers/{tid}/withdraw", headers=h)
    assert w.json()["code"] == 0 and w.json()["data"]["status"] == "withdrawn"
    await client.delete(f"/api/v1/collection/transfers/{tid}", headers=h)


async def test_collection_followup(client: AsyncClient, auth_headers: dict):
    h = auth_headers
    cust = await client.post("/api/v1/customers", json={"name": "催收跟进客户"}, headers=h)
    cust_id = cust.json()["data"]["id"]
    f = await client.post("/api/v1/collection/followups", json={
        "customer_id": cust_id, "customer_name": "催收跟进客户",
        "method": "phone", "feedback": "承诺月底付款", "expected_date": "2026-06-30", "amount_promised": 20000,
    }, headers=h)
    assert f.json()["code"] == 0
    lst = await client.get("/api/v1/collection/followups", headers=h, params={"customer_id": cust_id})
    assert lst.json()["data"]["total"] >= 1
    await client.delete(f"/api/v1/customers/{cust_id}", headers=h)


async def test_collection_no_auth(client: AsyncClient):
    assert (await client.get("/api/v1/collection/aging")).json()["code"] != 0
    assert (await client.get("/api/v1/collection/transfers")).json()["code"] != 0
