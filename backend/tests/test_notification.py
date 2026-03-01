"""Notification API integration tests."""

from httpx import AsyncClient


async def test_unread_count(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/notifications/unread_count", headers=auth_headers)
    data = resp.json()
    assert data["code"] == 0
    assert "count" in data["data"]


async def test_list_notifications(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/notifications", headers=auth_headers)
    data = resp.json()
    assert data["code"] == 0
    assert isinstance(data["data"], list)


async def test_list_unread_only(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/notifications?unread_only=true", headers=auth_headers)
    data = resp.json()
    assert data["code"] == 0


async def test_mark_all_read(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/notifications/mark_all_read", headers=auth_headers)
    assert resp.json()["code"] == 0

    # Verify count is 0
    count_resp = await client.get("/api/v1/notifications/unread_count", headers=auth_headers)
    assert count_resp.json()["data"]["count"] == 0
