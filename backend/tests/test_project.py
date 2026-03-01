"""Project (opportunity) API integration tests."""

from httpx import AsyncClient


async def test_list_projects(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/projects", headers=auth_headers)
    data = resp.json()
    assert data["code"] == 0
    assert "items" in data["data"]


async def test_project_crud(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/customers", headers=auth_headers, json={"name": "项目测试客户"})
    cust_id = resp.json()["data"]["id"]

    resp = await client.post("/api/v1/projects", headers=auth_headers, json={
        "name": "测试商机_自动化", "customer_id": cust_id, "amount_expect": 500000,
    })
    data = resp.json()
    assert data["code"] == 0
    pid = data["data"]["id"]
    assert data["data"]["stage_code"] == "S1"

    resp = await client.get(f"/api/v1/projects/{pid}", headers=auth_headers)
    assert resp.json()["code"] == 0

    resp = await client.put(f"/api/v1/projects/{pid}", headers=auth_headers, json={
        "amount_expect": 600000, "probability": 50,
    })
    assert resp.json()["code"] == 0

    await client.delete(f"/api/v1/projects/{pid}", headers=auth_headers)
    await client.delete(f"/api/v1/customers/{cust_id}", headers=auth_headers)


async def test_project_export(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/projects/export/excel", headers=auth_headers)
    assert resp.status_code == 200
