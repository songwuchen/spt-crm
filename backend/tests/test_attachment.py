"""Attachment domain tests — upload, list, download, delete."""

import io

import pytest
from httpx import AsyncClient

from app.common.exceptions import BusinessException
from app.domains.attachment.router import (
    ALLOWED_EXTENSIONS,
    _validate_ext,
    _validate_upload_type,
)


def test_cad_extensions_allowlisted():
    for ext in (".dwg", ".dxf", ".step", ".stp", ".sldprt", ".ipt"):
        assert ext in ALLOWED_EXTENSIONS
        assert _validate_ext(f"a{ext}") == ext
    _validate_upload_type("layout.DWG", "application/acad")
    _validate_upload_type("model.step", "application/weird-cad-vendor")


def test_ofd_extension_allowlisted():
    """电子发票 OFD（开票申请附件常用）。"""
    assert ".ofd" in ALLOWED_EXTENSIONS
    assert _validate_ext("invoice.ofd") == ".ofd"
    _validate_upload_type("电子发票.OFD", "application/ofd")
    _validate_upload_type("fapiao.ofd", "application/octet-stream")


def test_exe_extension_rejected():
    with pytest.raises(BusinessException) as ei:
        _validate_ext("malware.exe")
    assert "不支持" in (ei.value.message or "")


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


async def test_attachment_cad_dwg_allowed(client: AsyncClient, auth_headers: dict):
    """CAD 版图（.dwg）应允许上传（报价询价单附件场景）。"""
    h = auth_headers
    resp = await client.post("/api/v1/attachments", headers=h, files={
        "file": ("layout.dwg", io.BytesIO(b"AC1018 fake dwg"), "application/acad"),
    }, data={"biz_type": "form_data", "biz_id": "00000000-0000-0000-0000-000000000099"})
    data = resp.json()
    assert data["code"] == 0, f"CAD upload failed: {data}"
    att_id = data["data"]["id"]
    await client.delete(f"/api/v1/attachments/{att_id}", headers=h)


async def test_attachment_rejects_exe(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/attachments", headers=auth_headers, files={
        "file": ("malware.exe", io.BytesIO(b"MZ"), "application/octet-stream"),
    })
    data = resp.json()
    assert data["code"] != 0
    assert "不支持" in (data.get("message") or "")