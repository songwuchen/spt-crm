"""Service ticket API integration tests."""

from httpx import AsyncClient


async def test_list_tickets(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/service_tickets", headers=auth_headers)
    data = resp.json()
    assert data["code"] == 0
    assert "items" in data["data"]
    assert isinstance(data["data"]["items"], list)


async def test_ticket_crud(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/service_tickets", headers=auth_headers, json={
        "type": "fault", "priority": "high", "description": "自动化测试工单",
    })
    data = resp.json()
    assert data["code"] == 0
    tid = data["data"]["id"]

    resp = await client.get(f"/api/v1/service_tickets/{tid}", headers=auth_headers)
    assert resp.json()["code"] == 0

    resp = await client.put(f"/api/v1/service_tickets/{tid}", headers=auth_headers, json={
        "status": "processing",
    })
    assert resp.json()["code"] == 0


async def test_ticket_export(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/service_tickets/export/excel", headers=auth_headers)
    assert resp.status_code == 200
