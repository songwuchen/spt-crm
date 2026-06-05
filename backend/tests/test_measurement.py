"""Service measurement (售后现场实测数据) tests."""

import datetime
from httpx import AsyncClient


async def test_measurement_crud_and_stats(client: AsyncClient, auth_headers: dict):
    h = auth_headers
    cust = await client.post("/api/v1/customers", json={"name": "实测数据客户"}, headers=h)
    cust_id = cust.json()["data"]["id"]
    today = datetime.date.today().isoformat()

    m1 = await client.post("/api/v1/measurements", json={
        "customer_id": cust_id, "customer_name": "实测数据客户", "service_date": today,
        "industry": "冶金", "equipment_name": "圆振筛", "equipment_model": "YA1530",
        "material_name": "烧结矿", "screen_efficiency": 92.5, "throughput_tph": 300, "running_current_a": 45,
    }, headers=h)
    d1 = m1.json()
    assert d1["code"] == 0, f"create measurement failed: {d1}"
    mid = d1["data"]["id"]
    assert d1["data"]["record_no"]
    assert abs(d1["data"]["screen_efficiency"] - 92.5) < 1e-6

    # second of same model
    await client.post("/api/v1/measurements", json={
        "customer_id": cust_id, "equipment_model": "YA1530", "screen_efficiency": 88.5, "throughput_tph": 320,
    }, headers=h)

    lst = await client.get("/api/v1/measurements", headers=h, params={"equipment_model": "YA1530"})
    assert lst.json()["data"]["total"] >= 2

    stats = await client.get("/api/v1/measurements/stats", headers=h)
    row = next((r for r in stats.json()["data"] if r["equipment_model"] == "YA1530"), None)
    assert row is not None and row["count"] >= 2
    assert row["avg_efficiency"] is not None  # ~90.5

    upd = await client.put(f"/api/v1/measurements/{mid}", json={"throughput_tph": 310}, headers=h)
    assert abs(upd.json()["data"]["throughput_tph"] - 310) < 1e-6

    exp = await client.get("/api/v1/measurements/export/excel", headers=h)
    assert exp.status_code == 200

    await client.delete(f"/api/v1/measurements/{mid}", headers=h)
    await client.delete(f"/api/v1/customers/{cust_id}", headers=h)


async def test_measurement_no_auth(client: AsyncClient):
    assert (await client.get("/api/v1/measurements")).json()["code"] != 0
