"""Auth API integration tests."""

from httpx import AsyncClient


async def test_login_success(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", json={
        "username": "admin", "password": "admin123",
    })
    data = resp.json()
    assert data["code"] == 0
    assert "access_token" in data["data"]
    assert "refresh_token" in data["data"]


async def test_login_wrong_password(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", json={
        "username": "admin", "password": "wrong",
    })
    data = resp.json()
    assert data["code"] != 0


async def test_me_endpoint(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["username"] == "admin"


async def test_me_no_auth(client: AsyncClient):
    resp = await client.get("/api/v1/auth/me")
    data = resp.json()
    assert data["code"] != 0


async def test_refresh_token(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", json={
        "username": "admin", "password": "admin123",
    })
    refresh_token = resp.json()["data"]["refresh_token"]
    resp2 = await client.post("/api/v1/auth/refresh", json={
        "refresh_token": refresh_token,
    })
    data2 = resp2.json()
    assert data2["code"] == 0
    assert "access_token" in data2["data"]
