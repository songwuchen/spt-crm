"""Order (订单) + Tender (标书) domains and customer report tests."""

from httpx import AsyncClient


async def _customer(client: AsyncClient, h: dict, name: str) -> str:
    resp = await client.post("/api/v1/customers", json={"name": name}, headers=h)
    return resp.json()["data"]["id"]


async def test_order_crud_and_export(client: AsyncClient, auth_headers: dict):
    h = auth_headers
    cust_id = await _customer(client, h, "订单测试客户")

    resp = await client.post("/api/v1/orders", json={
        "customer_id": cust_id, "title": "首批设备订单",
        "amount": 88000, "status": "confirmed", "order_date": "2026-05-01",
    }, headers=h)
    data = resp.json()
    assert data["code"] == 0, f"create order failed: {data}"
    oid = data["data"]["id"]
    assert data["data"]["order_no"]
    assert data["data"]["status"] == "confirmed"

    lst = await client.get("/api/v1/orders", headers=h, params={"customer_id": cust_id})
    assert lst.json()["code"] == 0
    assert lst.json()["data"]["total"] >= 1

    upd = await client.put(f"/api/v1/orders/{oid}", json={"status": "shipped"}, headers=h)
    assert upd.json()["code"] == 0 and upd.json()["data"]["status"] == "shipped"

    exp = await client.get("/api/v1/orders/export/excel", headers=h)
    assert exp.status_code == 200

    dl = await client.delete(f"/api/v1/orders/{oid}", headers=h)
    assert dl.json()["code"] == 0

    await client.delete(f"/api/v1/customers/{cust_id}", headers=h)


async def test_tender_crud_and_export(client: AsyncClient, auth_headers: dict):
    h = auth_headers
    cust_id = await _customer(client, h, "标书测试客户")

    resp = await client.post("/api/v1/tenders", json={
        "customer_id": cust_id, "title": "某产线招标",
        "bid_amount": 1200000, "budget_amount": 1500000,
        "status": "submitted", "submit_date": "2026-05-10",
    }, headers=h)
    data = resp.json()
    assert data["code"] == 0, f"create tender failed: {data}"
    tid = data["data"]["id"]
    assert data["data"]["tender_no"]

    lst = await client.get("/api/v1/tenders", headers=h, params={"customer_id": cust_id})
    assert lst.json()["code"] == 0
    assert lst.json()["data"]["total"] >= 1

    upd = await client.put(f"/api/v1/tenders/{tid}", json={"status": "won", "result": "中标"}, headers=h)
    assert upd.json()["code"] == 0 and upd.json()["data"]["status"] == "won"

    exp = await client.get("/api/v1/tenders/export/excel", headers=h)
    assert exp.status_code == 200

    dl = await client.delete(f"/api/v1/tenders/{tid}", headers=h)
    assert dl.json()["code"] == 0

    await client.delete(f"/api/v1/customers/{cust_id}", headers=h)


async def test_customer_report_and_export(client: AsyncClient, auth_headers: dict):
    h = auth_headers
    cust_id = await _customer(client, h, "报表测试客户")

    # one project, one order, one tender linked to the customer
    proj = await client.post("/api/v1/projects", json={
        "name": "报表商机", "customer_id": cust_id, "amount_expect": 300000,
    }, headers=h)
    proj_id = proj.json()["data"]["id"]
    order = await client.post("/api/v1/orders", json={"customer_id": cust_id, "amount": 50000}, headers=h)
    oid = order.json()["data"]["id"]
    tender = await client.post("/api/v1/tenders", json={"customer_id": cust_id, "title": "报表标书"}, headers=h)
    tid = tender.json()["data"]["id"]

    rep = await client.get(f"/api/v1/customers/{cust_id}/report", headers=h)
    data = rep.json()
    assert data["code"] == 0, f"report failed: {data}"
    d = data["data"]
    assert d["summary"]["project_count"] >= 1
    assert d["summary"]["order_count"] >= 1
    assert d["summary"]["tender_count"] >= 1
    assert any(p["id"] == proj_id for p in d["projects"])
    assert any(o["id"] == oid for o in d["orders"])
    assert any(t["id"] == tid for t in d["tenders"])

    exp = await client.get(f"/api/v1/customers/{cust_id}/report/export", headers=h)
    assert exp.status_code == 200
    assert "spreadsheet" in exp.headers.get("content-type", "")

    await client.delete(f"/api/v1/orders/{oid}", headers=h)
    await client.delete(f"/api/v1/tenders/{tid}", headers=h)
    await client.delete(f"/api/v1/projects/{proj_id}", headers=h)
    await client.delete(f"/api/v1/customers/{cust_id}", headers=h)


async def test_order_tender_no_auth(client: AsyncClient):
    assert (await client.get("/api/v1/orders")).json()["code"] != 0
    assert (await client.get("/api/v1/tenders")).json()["code"] != 0
