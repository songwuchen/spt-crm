"""Audit log API integration tests."""

import pytest
from httpx import AsyncClient


async def _has_audit_permission(client: AsyncClient, auth_headers: dict) -> bool:
    resp = await client.get("/api/v1/audit_logs", headers=auth_headers)
    return resp.json().get("code") == 0


async def test_list_audit_logs(client: AsyncClient, auth_headers: dict):
    if not await _has_audit_permission(client, auth_headers):
        pytest.skip("Admin user lacks audit:view permission")
    resp = await client.get("/api/v1/audit_logs", headers=auth_headers)
    data = resp.json()
    assert data["code"] == 0
    assert "items" in data["data"]
    assert "total" in data["data"]


async def test_audit_log_pagination(client: AsyncClient, auth_headers: dict):
    if not await _has_audit_permission(client, auth_headers):
        pytest.skip("Admin user lacks audit:view permission")
    resp = await client.get("/api/v1/audit_logs", headers=auth_headers, params={
        "pageNo": 1, "pageSize": 5,
    })
    data = resp.json()
    assert data["code"] == 0
    assert len(data["data"]["items"]) <= 5


async def test_audit_statistics(client: AsyncClient, auth_headers: dict):
    if not await _has_audit_permission(client, auth_headers):
        pytest.skip("Admin user lacks audit:view permission")
    resp = await client.get("/api/v1/audit_logs/statistics", headers=auth_headers, params={"days": 30})
    data = resp.json()
    assert data["code"] == 0
    assert "total" in data["data"]
    assert "by_action" in data["data"]
    assert "by_resource" in data["data"]
    assert "daily" in data["data"]
    assert "top_operators" in data["data"]


async def test_audit_verify_integrity(client: AsyncClient, auth_headers: dict):
    if not await _has_audit_permission(client, auth_headers):
        pytest.skip("Admin user lacks audit:view permission")
    resp = await client.post("/api/v1/audit_logs/verify", headers=auth_headers)
    data = resp.json()
    assert data["code"] == 0
    assert "total_checked" in data["data"]
    assert "tampered_count" in data["data"]
    assert isinstance(data["data"]["tampered"], list)


async def test_audit_filter_by_resource(client: AsyncClient, auth_headers: dict):
    if not await _has_audit_permission(client, auth_headers):
        pytest.skip("Admin user lacks audit:view permission")
    resp = await client.get("/api/v1/audit_logs", headers=auth_headers, params={
        "resource_type": "auth",
    })
    data = resp.json()
    assert data["code"] == 0
    for item in data["data"]["items"]:
        assert item["resource_type"] == "auth"


async def test_audit_export(client: AsyncClient, auth_headers: dict):
    if not await _has_audit_permission(client, auth_headers):
        pytest.skip("Admin user lacks audit:view permission")
    resp = await client.get("/api/v1/audit_logs/export", headers=auth_headers)
    assert resp.status_code == 200
    # Should return an Excel file
    assert "spreadsheet" in resp.headers.get("content-type", "") or "octet-stream" in resp.headers.get("content-type", "")
