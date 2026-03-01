"""Payment domain tests — invoices, payment plans, payment records."""

import datetime
from httpx import AsyncClient


async def _setup_project(client: AsyncClient, h: dict) -> tuple[str, str]:
    """Create a customer + project for payment tests."""
    cust = await client.post("/api/v1/customers", json={
        "name": "Payment Test Corp", "industry": "Finance", "level": "A",
    }, headers=h)
    cust_id = cust.json()["data"]["id"]

    proj = await client.post("/api/v1/projects", json={
        "name": "Payment Test Project", "customer_id": cust_id,
        "stage_code": "S1", "amount_expect": 100000,
    }, headers=h)
    proj_id = proj.json()["data"]["id"]
    return cust_id, proj_id


async def _cleanup(client: AsyncClient, h: dict, proj_id: str, cust_id: str):
    await client.delete(f"/api/v1/projects/{proj_id}", headers=h)
    await client.delete(f"/api/v1/customers/{cust_id}", headers=h)


async def test_invoice_crud(client: AsyncClient, auth_headers: dict):
    """Create, list, update invoices."""
    h = auth_headers
    cust_id, proj_id = await _setup_project(client, h)
    today = datetime.date.today().isoformat()

    # Create invoice
    resp = await client.post(f"/api/v1/projects/{proj_id}/invoices", json={
        "invoice_no": "INV-TEST-001", "amount": 50000, "invoice_date": today,
    }, headers=h)
    data = resp.json()
    assert data["code"] == 0, f"Create invoice failed: {data}"
    inv_id = data["data"]["id"]

    # List invoices
    lst = await client.get(f"/api/v1/projects/{proj_id}/invoices", headers=h)
    assert lst.json()["code"] == 0
    assert len(lst.json()["data"]) >= 1

    # Update invoice
    upd = await client.put(f"/api/v1/invoices/{inv_id}", json={
        "amount": 55000, "remark": "Updated amount",
    }, headers=h)
    assert upd.json()["code"] == 0

    await _cleanup(client, h, proj_id, cust_id)


async def test_payment_plan_crud(client: AsyncClient, auth_headers: dict):
    """Create, list, update payment plans."""
    h = auth_headers
    cust_id, proj_id = await _setup_project(client, h)

    # Create payment plan
    resp = await client.post(f"/api/v1/projects/{proj_id}/payment_plans", json={
        "plan_no": "PP-TEST-001", "amount": 30000, "due_date": "2026-06-30",
    }, headers=h)
    data = resp.json()
    assert data["code"] == 0, f"Create plan failed: {data}"
    plan_id = data["data"]["id"]

    # List plans
    lst = await client.get(f"/api/v1/projects/{proj_id}/payment_plans", headers=h)
    assert lst.json()["code"] == 0
    assert len(lst.json()["data"]) >= 1

    # Update plan
    upd = await client.put(f"/api/v1/payment_plans/{plan_id}", json={
        "status": "received", "remark": "Paid",
    }, headers=h)
    assert upd.json()["code"] == 0

    await _cleanup(client, h, proj_id, cust_id)


async def test_payment_record_crud(client: AsyncClient, auth_headers: dict):
    """Create and list payment records."""
    h = auth_headers
    cust_id, proj_id = await _setup_project(client, h)
    today = datetime.date.today().isoformat()

    # Create payment record
    resp = await client.post(f"/api/v1/projects/{proj_id}/payment_records", json={
        "received_date": today, "amount": 25000, "channel": "bank_transfer",
        "reference_no": "REF-001",
    }, headers=h)
    data = resp.json()
    assert data["code"] == 0, f"Create record failed: {data}"

    # List records
    lst = await client.get(f"/api/v1/projects/{proj_id}/payment_records", headers=h)
    assert lst.json()["code"] == 0
    assert len(lst.json()["data"]) >= 1

    await _cleanup(client, h, proj_id, cust_id)


async def test_invoice_no_auth(client: AsyncClient):
    """Invoice endpoints should reject unauthenticated requests."""
    resp = await client.get("/api/v1/projects/fake-id/invoices")
    assert resp.json()["code"] != 0
