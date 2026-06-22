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


async def test_payment_plan_bulk_create(client: AsyncClient, auth_headers: dict):
    """Bulk-create payment plans (e.g. generated from a contract's payment terms)."""
    h = auth_headers
    cust_id, proj_id = await _setup_project(client, h)

    # Bulk create 3 plans; plan_no omitted so each gets auto-generated
    resp = await client.post(f"/api/v1/projects/{proj_id}/payment_plans/bulk", json={
        "plans": [
            {"amount": 30000, "due_date": "2026-06-30", "remark": "预付款"},
            {"amount": 60000, "due_date": "2026-09-30", "remark": "进度款"},
            {"amount": 10000, "remark": "尾款"},  # no due_date — allowed
        ],
    }, headers=h)
    data = resp.json()
    assert data["code"] == 0, f"Bulk create failed: {data}"
    assert len(data["data"]) == 3
    # Auto-generated plan numbers must be unique
    nos = [p["plan_no"] for p in data["data"]]
    assert len(set(nos)) == 3, f"plan_no not unique: {nos}"

    # All three should now be listed
    lst = await client.get(f"/api/v1/projects/{proj_id}/payment_plans", headers=h)
    assert lst.json()["code"] == 0
    assert len(lst.json()["data"]) == 3

    await _cleanup(client, h, proj_id, cust_id)


async def test_payment_plan_bulk_source_and_replace(client: AsyncClient, auth_headers: dict):
    """Bulk-create tracks source_contract_id + milestone, and replace_existing
    only overwrites plans from the same contract (manual/other plans untouched)."""
    h = auth_headers
    cust_id, proj_id = await _setup_project(client, h)

    # A manually-created plan (no source) must survive any regeneration
    await client.post(f"/api/v1/projects/{proj_id}/payment_plans", json={
        "plan_no": "PP-MANUAL", "amount": 5000, "due_date": "2026-12-31",
    }, headers=h)

    # First generation from contract CT-1 (2 plans, one tied to a milestone)
    r1 = await client.post(f"/api/v1/projects/{proj_id}/payment_plans/bulk", json={
        "source_contract_id": "CT-1",
        "plans": [
            {"amount": 40000, "due_date": "2026-06-30", "remark": "预付款"},
            {"amount": 60000, "trigger_milestone_code": "M2", "remark": "进度款"},
        ],
    }, headers=h)
    assert r1.json()["code"] == 0
    gen = r1.json()["data"]
    assert all(p["source_contract_id"] == "CT-1" for p in gen)
    assert any(p["trigger_milestone_code"] == "M2" for p in gen)

    # 1 manual + 2 generated = 3
    lst = await client.get(f"/api/v1/projects/{proj_id}/payment_plans", headers=h)
    assert len(lst.json()["data"]) == 3

    # Regenerate CT-1 with replace_existing -> old 2 dropped, new 1 added
    r2 = await client.post(f"/api/v1/projects/{proj_id}/payment_plans/bulk", json={
        "source_contract_id": "CT-1", "replace_existing": True,
        "plans": [{"amount": 100000, "due_date": "2026-07-31", "remark": "全款"}],
    }, headers=h)
    assert r2.json()["code"] == 0

    lst2 = (await client.get(f"/api/v1/projects/{proj_id}/payment_plans", headers=h)).json()["data"]
    # manual (1) + regenerated CT-1 (1) = 2
    assert len(lst2) == 2
    manual = [p for p in lst2 if p["source_contract_id"] is None]
    ct1 = [p for p in lst2 if p["source_contract_id"] == "CT-1"]
    assert len(manual) == 1 and manual[0]["plan_no"] == "PP-MANUAL"
    assert len(ct1) == 1 and float(ct1[0]["amount"]) == 100000

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
