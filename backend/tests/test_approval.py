"""Approval API integration tests."""

from httpx import AsyncClient


async def test_list_approvals(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/approvals", headers=auth_headers)
    data = resp.json()
    assert data["code"] == 0
    assert isinstance(data["data"], dict)
    assert isinstance(data["data"]["items"], list)
    assert "total" in data["data"]


async def test_pending_approvals(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/approvals/my/pending", headers=auth_headers)
    data = resp.json()
    assert data["code"] == 0
    assert isinstance(data["data"], list)
