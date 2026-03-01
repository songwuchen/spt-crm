"""Attachment domain tests — upload, list, download, delete."""

import io
from httpx import AsyncClient


async def test_attachment_upload_and_list(client: AsyncClient, auth_headers: dict):
    """Upload a file, list by biz, then delete."""
    h = auth_headers

    # Create a customer to attach files to
    cust = await client.post("/api/v1/customers", json={
        "name": "Attachment Test Corp", "industry": "IT", "level": "A",
    }, headers=h)
    cust_id = cust.json()["data"]["id"]

    # Upload file
    file_content = b"Hello, this is a test document."
    resp = await client.post("/api/v1/attachments", headers=h, files={
        "file": ("test.txt", io.BytesIO(file_content), "text/plain"),
    }, data={
        "biz_type": "customer",
        "biz_id": cust_id,
    })
    data = resp.json()
    assert data["code"] == 0, f"Upload failed: {data}"
    att_id = data["data"]["id"]

    # List by biz
    lst = await client.get("/api/v1/attachments/by_biz", params={
        "biz_type": "customer", "biz_id": cust_id,
    }, headers=h)
    assert lst.json()["code"] == 0
    assert len(lst.json()["data"]) >= 1

    # Download
    dl = await client.get(f"/api/v1/attachments/{att_id}/download", headers=h)
    assert dl.status_code == 200

    # Delete attachment
    rm = await client.delete(f"/api/v1/attachments/{att_id}", headers=h)
    assert rm.json()["code"] == 0

    # Cleanup
    await client.delete(f"/api/v1/customers/{cust_id}", headers=h)


async def test_attachment_no_auth(client: AsyncClient):
    """Attachment endpoints should reject unauthenticated requests."""
    resp = await client.get("/api/v1/attachments/by_biz", params={
        "biz_type": "customer", "biz_id": "fake",
    })
    assert resp.json()["code"] != 0
