"""Task API integration tests."""

import pytest
from httpx import AsyncClient


async def test_list_tasks(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/tasks", headers=auth_headers)
    data = resp.json()
    assert data["code"] == 0
    assert "items" in data["data"]
    assert isinstance(data["data"]["items"], list)


async def test_task_crud(client: AsyncClient, auth_headers: dict):
    # Create
    resp = await client.post("/api/v1/tasks", headers=auth_headers, json={
        "title": "测试任务-单元测试",
        "description": "自动化测试创建的任务",
        "priority": "high",
        "due_date": "2026-12-31",
    })
    data = resp.json()
    assert data["code"] == 0
    tid = data["data"]["id"]
    assert data["data"]["title"] == "测试任务-单元测试"
    assert data["data"]["priority"] == "high"
    assert data["data"]["is_completed"] is False

    # Update
    resp = await client.put(f"/api/v1/tasks/{tid}", headers=auth_headers, json={
        "title": "测试任务-已修改",
        "priority": "urgent",
    })
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["title"] == "测试任务-已修改"
    assert resp.json()["data"]["priority"] == "urgent"

    # Complete
    resp = await client.put(f"/api/v1/tasks/{tid}", headers=auth_headers, json={
        "is_completed": True,
    })
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["is_completed"] is True
    assert resp.json()["data"]["status"] == "done"

    # Delete
    resp = await client.delete(f"/api/v1/tasks/{tid}", headers=auth_headers)
    assert resp.json()["code"] == 0


async def test_task_filter_by_status(client: AsyncClient, auth_headers: dict):
    # Create a task and complete it
    resp = await client.post("/api/v1/tasks", headers=auth_headers, json={
        "title": "筛选测试-已完成", "priority": "normal",
    })
    tid = resp.json()["data"]["id"]
    await client.put(f"/api/v1/tasks/{tid}", headers=auth_headers, json={"is_completed": True})

    # Filter by done
    resp = await client.get("/api/v1/tasks", headers=auth_headers, params={"status": "done"})
    data = resp.json()
    assert data["code"] == 0
    for item in data["data"]["items"]:
        assert item["status"] == "done"

    # Cleanup
    await client.delete(f"/api/v1/tasks/{tid}", headers=auth_headers)


async def test_task_filter_by_priority(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/tasks", headers=auth_headers, json={
        "title": "紧急任务测试", "priority": "urgent",
    })
    tid = resp.json()["data"]["id"]

    resp = await client.get("/api/v1/tasks", headers=auth_headers, params={"priority": "urgent"})
    data = resp.json()
    assert data["code"] == 0
    assert any(t["title"] == "紧急任务测试" for t in data["data"]["items"])

    await client.delete(f"/api/v1/tasks/{tid}", headers=auth_headers)


async def test_task_keyword_search(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/tasks", headers=auth_headers, json={
        "title": "关键词搜索XYZ任务", "priority": "low",
    })
    tid = resp.json()["data"]["id"]

    resp = await client.get("/api/v1/tasks", headers=auth_headers, params={"keyword": "XYZ"})
    data = resp.json()
    assert data["code"] == 0
    assert any("XYZ" in t["title"] for t in data["data"]["items"])

    await client.delete(f"/api/v1/tasks/{tid}", headers=auth_headers)


async def test_delete_nonexistent_task(client: AsyncClient, auth_headers: dict):
    resp = await client.delete("/api/v1/tasks/nonexistent-id-000", headers=auth_headers)
    assert resp.json()["code"] != 0
