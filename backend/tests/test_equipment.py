"""Customer equipment + process survey tests (精细化营销/工艺设备档案)."""

import datetime
from httpx import AsyncClient


async def test_equipment_crud_and_replacement(client: AsyncClient, auth_headers: dict):
    h = auth_headers
    cust = await client.post("/api/v1/customers", json={"name": "工艺设备客户"}, headers=h)
    cust_id = cust.json()["data"]["id"]
    soon = (datetime.date.today() + datetime.timedelta(days=120)).isoformat()

    e = await client.post("/api/v1/equipment/equipments", json={
        "customer_id": cust_id, "customer_name": "工艺设备客户",
        "name": "振动筛", "spec": "YA1530", "supplier": "竞品厂家A",
        "is_competitor": True, "usage_years": 8, "replace_plan_date": soon,
    }, headers=h)
    ed = e.json()
    assert ed["code"] == 0, f"create equipment failed: {ed}"
    eid = ed["data"]["id"]
    assert ed["data"]["is_competitor"] is True

    lst = await client.get("/api/v1/equipment/equipments", headers=h, params={"customer_id": cust_id, "is_competitor": True})
    assert lst.json()["data"]["total"] >= 1

    cand = await client.get("/api/v1/equipment/replacement-candidates", headers=h, params={"months": 12})
    assert any(x["id"] == eid for x in cand.json()["data"])

    # convert to renewal opportunity
    conv = await client.post(f"/api/v1/equipment/equipments/{eid}/to-renewal", json={"amount_expect": 200000}, headers=h)
    assert conv.json()["code"] == 0 and conv.json()["data"]["id"]

    upd = await client.put(f"/api/v1/equipment/equipments/{eid}", json={"usage_years": 9}, headers=h)
    assert abs(upd.json()["data"]["usage_years"] - 9) < 1e-6

    await client.delete(f"/api/v1/equipment/equipments/{eid}", headers=h)
    await client.delete(f"/api/v1/customers/{cust_id}", headers=h)


async def test_process_survey_crud(client: AsyncClient, auth_headers: dict):
    h = auth_headers
    cust = await client.post("/api/v1/customers", json={"name": "工艺调研客户"}, headers=h)
    cust_id = cust.json()["data"]["id"]

    s = await client.post("/api/v1/equipment/surveys", json={
        "customer_id": cust_id, "customer_name": "工艺调研客户",
        "industry": "冶金", "main_products": "烧结矿", "process_desc": "高炉系统筛分",
    }, headers=h)
    sd = s.json()
    assert sd["code"] == 0, f"create survey failed: {sd}"
    sid = sd["data"]["id"]

    lst = await client.get("/api/v1/equipment/surveys", headers=h, params={"customer_id": cust_id, "industry": "冶金"})
    assert lst.json()["data"]["total"] >= 1

    upd = await client.put(f"/api/v1/equipment/surveys/{sid}", json={"annual_output": "200万吨"}, headers=h)
    assert upd.json()["data"]["annual_output"] == "200万吨"

    await client.delete(f"/api/v1/equipment/surveys/{sid}", headers=h)
    await client.delete(f"/api/v1/customers/{cust_id}", headers=h)


async def test_equipment_no_auth(client: AsyncClient):
    assert (await client.get("/api/v1/equipment/equipments")).json()["code"] != 0
