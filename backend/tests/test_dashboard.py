"""Dashboard API integration tests."""

from httpx import AsyncClient


async def test_dashboard_stats(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/dashboard/stats", headers=auth_headers)
    data = resp.json()
    assert data["code"] == 0
    # Check dashboard returns stats (key names may vary)
    assert isinstance(data["data"], dict)
    assert len(data["data"]) > 0


async def test_dashboard_alerts(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/dashboard/alerts", headers=auth_headers)
    data = resp.json()
    assert data["code"] == 0
    assert isinstance(data["data"], list)


async def test_dashboard_search(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/dashboard/search", headers=auth_headers, params={"q": "test"})
    data = resp.json()
    assert data["code"] == 0
    assert isinstance(data["data"], list)
