"""Outbox/Inbox event bus API integration tests."""

import pytest
from httpx import AsyncClient


async def _has_event_permission(client: AsyncClient, auth_headers: dict) -> bool:
    resp = await client.get("/api/v1/events/outbox", headers=auth_headers)
    return resp.json().get("code") == 0


async def test_list_outbox_events(client: AsyncClient, auth_headers: dict):
    if not await _has_event_permission(client, auth_headers):
        pytest.skip("Admin user lacks project:view permission for events")
    resp = await client.get("/api/v1/events/outbox", headers=auth_headers)
    data = resp.json()
    assert data["code"] == 0
    assert "items" in data["data"]


async def test_outbox_event_crud(client: AsyncClient, auth_headers: dict):
    if not await _has_event_permission(client, auth_headers):
        pytest.skip("Admin user lacks event permissions")

    # Create outbox event
    resp = await client.post("/api/v1/events/outbox", headers=auth_headers, json={
        "event_type": "test.created",
        "aggregate_type": "test",
        "aggregate_id": "test-001",
        "payload_json": {"action": "test", "data": {"foo": "bar"}},
    })
    data = resp.json()
    assert data["code"] == 0
    eid = data["data"]["id"]
    assert data["data"]["event_type"] == "test.created"
    assert data["data"]["status"] == "pending"

    # Publish
    resp = await client.post(f"/api/v1/events/outbox/{eid}/publish", headers=auth_headers)
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["status"] == "published"


async def test_list_inbox_events(client: AsyncClient, auth_headers: dict):
    if not await _has_event_permission(client, auth_headers):
        pytest.skip("Admin user lacks event permissions")
    resp = await client.get("/api/v1/events/inbox", headers=auth_headers)
    data = resp.json()
    assert data["code"] == 0
    assert "items" in data["data"]


async def test_inbox_event_receive_and_process(client: AsyncClient, auth_headers: dict):
    if not await _has_event_permission(client, auth_headers):
        pytest.skip("Admin user lacks event permissions")

    # Receive inbox event
    resp = await client.post("/api/v1/events/inbox", headers=auth_headers, json={
        "source": "erp",
        "event_type": "order.synced",
        "external_id": "ERP-00123",
        "payload_json": {"order_no": "SO-001"},
    })
    data = resp.json()
    assert data["code"] == 0
    eid = data["data"]["id"]
    assert data["data"]["source"] == "erp"
    assert data["data"]["status"] in ("pending", "received")

    # Process
    resp = await client.post(f"/api/v1/events/inbox/{eid}/process", headers=auth_headers)
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["status"] == "processed"


async def test_outbox_filter_by_status(client: AsyncClient, auth_headers: dict):
    if not await _has_event_permission(client, auth_headers):
        pytest.skip("Admin user lacks event permissions")
    resp = await client.get("/api/v1/events/outbox", headers=auth_headers, params={"status": "pending"})
    data = resp.json()
    assert data["code"] == 0
    for item in data["data"]["items"]:
        assert item["status"] == "pending"
