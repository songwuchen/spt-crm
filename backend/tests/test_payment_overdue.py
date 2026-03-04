"""Payment overdue check + notification tests."""

import datetime
from httpx import AsyncClient


async def _setup(client: AsyncClient, h: dict) -> tuple[str, str]:
    cust = await client.post("/api/v1/customers", json={
        "name": "Overdue Corp", "industry": "Finance", "level": "A",
    }, headers=h)
    cust_id = cust.json()["data"]["id"]

    proj = await client.post("/api/v1/projects", json={
        "name": "Overdue Project", "customer_id": cust_id,
        "stage_code": "S6", "amount_expect": 500000,
    }, headers=h)
    proj_id = proj.json()["data"]["id"]
    return cust_id, proj_id


async def _cleanup(client: AsyncClient, h: dict, proj_id: str, cust_id: str):
    await client.delete(f"/api/v1/projects/{proj_id}", headers=h)
    await client.delete(f"/api/v1/customers/{cust_id}", headers=h)


async def test_check_overdue_endpoint(client: AsyncClient, auth_headers: dict):
    """Trigger overdue check via API and verify response."""
    h = auth_headers
    cust_id, proj_id = await _setup(client, h)

    # Create a payment plan with past due date
    past_date = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    await client.post(f"/api/v1/projects/{proj_id}/payment_plans", json={
        "plan_no": "PP-OVERDUE-001", "amount": 100000, "due_date": past_date,
    }, headers=h)

    # Trigger overdue check
    resp = await client.post("/api/v1/payment/check_overdue", headers=h)
    data = resp.json()
    assert data["code"] == 0, f"Check overdue failed: {data}"
    assert "notified_projects" in data["data"]

    await _cleanup(client, h, proj_id, cust_id)


async def test_payment_reconciliation(client: AsyncClient, auth_headers: dict):
    """Payment record auto-reconciliation marks matched plan as paid."""
    h = auth_headers
    cust_id, proj_id = await _setup(client, h)
    today = datetime.date.today().isoformat()

    # Create plan
    plan_resp = await client.post(f"/api/v1/projects/{proj_id}/payment_plans", json={
        "plan_no": "PP-REC-001", "amount": 50000, "due_date": "2026-12-31",
    }, headers=h)
    plan_id = plan_resp.json()["data"]["id"]

    # Create record matched to plan
    rec_resp = await client.post(f"/api/v1/projects/{proj_id}/payment_records", json={
        "received_date": today, "amount": 50000,
        "channel": "bank", "matched_plan_id": plan_id,
    }, headers=h)
    assert rec_resp.json()["code"] == 0

    # Verify plan status changed to paid
    plans = await client.get(f"/api/v1/projects/{proj_id}/payment_plans", headers=h)
    matched = next((p for p in plans.json()["data"] if p["id"] == plan_id), None)
    assert matched is not None
    assert matched["status"] == "paid"

    await _cleanup(client, h, proj_id, cust_id)
