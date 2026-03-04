"""AI Center tests — tasks, templates, analysis, similar projects."""

from httpx import AsyncClient


async def test_ai_template_crud(client: AsyncClient, auth_headers: dict):
    """Create, list, update, delete prompt templates."""
    h = auth_headers

    # Create template
    resp = await client.post("/api/v1/ai/templates", json={
        "code": "test_tpl_001",
        "name": "Test Template",
        "task_type": "customer_insight",
        "template_text": "请分析客户 {{name}} 的画像",
        "is_active": True,
    }, headers=h)
    data = resp.json()
    assert data["code"] == 0, f"Create template failed: {data}"
    tpl_id = data["data"]["id"]

    # List templates
    lst = await client.get("/api/v1/ai/templates", headers=h)
    assert lst.json()["code"] == 0
    assert any(t["id"] == tpl_id for t in lst.json()["data"])

    # Filter by task_type
    lst2 = await client.get("/api/v1/ai/templates?task_type=customer_insight", headers=h)
    assert lst2.json()["code"] == 0
    assert all(t["task_type"] == "customer_insight" for t in lst2.json()["data"])

    # Update template
    upd = await client.put(f"/api/v1/ai/templates/{tpl_id}", json={
        "name": "Updated Template", "is_active": False,
    }, headers=h)
    assert upd.json()["code"] == 0
    assert upd.json()["data"]["name"] == "Updated Template"

    # Delete template
    dl = await client.delete(f"/api/v1/ai/templates/{tpl_id}", headers=h)
    assert dl.json()["code"] == 0


async def test_ai_analyze_project_risk(client: AsyncClient, auth_headers: dict):
    """Run AI analysis (mock mode) for project risk."""
    h = auth_headers

    # Setup project
    cust = await client.post("/api/v1/customers", json={
        "name": "AI Test Corp", "industry": "Machinery", "level": "A",
    }, headers=h)
    cust_id = cust.json()["data"]["id"]

    proj = await client.post("/api/v1/projects", json={
        "name": "AI Risk Project", "customer_id": cust_id,
        "stage_code": "S2", "amount_expect": 300000,
    }, headers=h)
    proj_id = proj.json()["data"]["id"]

    # Run analysis
    resp = await client.post("/api/v1/ai/analyze", json={
        "biz_type": "project",
        "biz_id": proj_id,
        "analysis_type": "risk",
    }, headers=h)
    data = resp.json()
    assert data["code"] == 0, f"AI analyze failed: {data}"
    result = data["data"]
    assert "task_id" in result
    assert "result" in result

    # Verify task was created
    tasks = await client.get(f"/api/v1/ai/tasks?biz_type=project&biz_id={proj_id}", headers=h)
    assert tasks.json()["code"] == 0
    assert len(tasks.json()["data"]) >= 1

    # Cleanup
    await client.delete(f"/api/v1/projects/{proj_id}", headers=h)
    await client.delete(f"/api/v1/customers/{cust_id}", headers=h)


async def test_ai_similar_projects(client: AsyncClient, auth_headers: dict):
    """Find similar projects endpoint."""
    h = auth_headers

    cust = await client.post("/api/v1/customers", json={
        "name": "Similar Corp", "industry": "Tech", "level": "B",
    }, headers=h)
    cust_id = cust.json()["data"]["id"]

    proj = await client.post("/api/v1/projects", json={
        "name": "Similar Test", "customer_id": cust_id,
        "stage_code": "S3", "amount_expect": 200000,
    }, headers=h)
    proj_id = proj.json()["data"]["id"]

    resp = await client.post("/api/v1/ai/similar-projects", json={
        "project_id": proj_id,
    }, headers=h)
    data = resp.json()
    assert data["code"] == 0, f"Similar projects failed: {data}"
    assert "similar_projects" in data["data"]

    await client.delete(f"/api/v1/projects/{proj_id}", headers=h)
    await client.delete(f"/api/v1/customers/{cust_id}", headers=h)


async def test_ai_activity_summary(client: AsyncClient, auth_headers: dict):
    """AI activity summary endpoint."""
    h = auth_headers

    cust = await client.post("/api/v1/customers", json={
        "name": "Summary Corp", "industry": "Tech", "level": "A",
    }, headers=h)
    cust_id = cust.json()["data"]["id"]

    # Create some activities
    for i in range(3):
        await client.post("/api/v1/activities", json={
            "biz_type": "customer", "biz_id": cust_id,
            "activity_type": "call", "subject": f"Follow up call #{i+1}",
            "content": f"Discussed requirements round {i+1}",
        }, headers=h)

    # Summarize
    resp = await client.post(f"/api/v1/activities/ai-summary?biz_type=customer&biz_id={cust_id}", headers=h)
    data = resp.json()
    assert data["code"] == 0, f"AI summary failed: {data}"
    assert "summary" in data["data"]
    assert "key_points" in data["data"]

    await client.delete(f"/api/v1/customers/{cust_id}", headers=h)


async def test_ai_no_auth(client: AsyncClient):
    """AI endpoints should reject unauthenticated requests."""
    resp = await client.get("/api/v1/ai/tasks")
    assert resp.json()["code"] != 0
