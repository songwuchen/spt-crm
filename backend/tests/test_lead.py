"""Lead API integration tests."""

from httpx import AsyncClient


async def test_list_leads(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/leads", headers=auth_headers)
    data = resp.json()
    assert data["code"] == 0
    assert "items" in data["data"]


async def test_lead_crud(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/leads", headers=auth_headers, json={
        "title": "测试线索_自动化", "company_name": "测试公司", "source": "website",
    })
    data = resp.json()
    assert data["code"] == 0
    lid = data["data"]["id"]
    assert data["data"]["lead_code"] is not None

    resp = await client.get(f"/api/v1/leads/{lid}", headers=auth_headers)
    assert resp.json()["code"] == 0

    resp = await client.put(f"/api/v1/leads/{lid}", headers=auth_headers, json={
        "title": "测试线索_已更新", "score": 80,
    })
    assert resp.json()["code"] == 0

    await client.delete(f"/api/v1/leads/{lid}", headers=auth_headers)


async def test_lead_export(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/leads/export/excel", headers=auth_headers)
    assert resp.status_code == 200
