"""Attachment domain tests — upload, list, download, delete."""

import io
import urllib.parse

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


def test_video_extensions_allowlisted():
    """MP4 等常见视频（售后/现场附件）。"""
    for ext in (".mp4", ".mov", ".avi", ".wmv", ".mkv", ".webm", ".m4v"):
        assert ext in ALLOWED_EXTENSIONS
        assert _validate_ext(f"clip{ext}") == ext
    _validate_upload_type("现场.MP4", "video/mp4")
    _validate_upload_type("demo.webm", "video/webm")
    _validate_upload_type("a.mov", "application/octet-stream")


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

    # Download（对象存储走 302/307 预签名；测试用 proxy=1 经本服务转发拿正文）
    dl = await client.get(
        f"/api/v1/attachments/{att_id}/download",
        headers=h,
        params={"proxy": 1},
    )
    assert dl.status_code == 200
    assert dl.content == file_content

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


async def test_print_preview_named_url(client: AsyncClient, auth_headers: dict):
    """Chrome PDF 工具栏用 URL 末段当文件名，不能是 blob UUID。"""
    pdf = b"%PDF-1.4 fake"
    resp = await client.post(
        "/api/v1/attachments/print-previews",
        headers=auth_headers,
        files={"file": ("WMGF202503004白宗凯合同资料领用2026-08-17.pdf", io.BytesIO(pdf), "application/pdf")},
    )
    body = resp.json()
    assert body["code"] == 0, body
    url = body["data"]["url"]
    assert "WMGF202503004" in url
    assert "白宗凯" in urllib.parse.unquote(url)
    got = await client.get(url)
    assert got.status_code == 200
    assert got.content == pdf
    assert "application/pdf" in (got.headers.get("content-type") or "")


async def test_print_preview_requires_login(client: AsyncClient):
    resp = await client.post(
        "/api/v1/attachments/print-previews",
        files={"file": ("a.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
    )
    assert resp.json()["code"] != 0


async def test_attachment_rejects_exe(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/attachments", headers=auth_headers, files={
        "file": ("malware.exe", io.BytesIO(b"MZ"), "application/octet-stream"),
    })
    data = resp.json()
    assert data["code"] != 0
    assert "不支持" in (data.get("message") or "")


@pytest.mark.asyncio
async def test_can_download_via_biz_visibility_parent_record(db):
    """父业务在数据范围内即可预览附件，不必单独授予 attachment:download。"""
    from sqlalchemy import text
    from sqlalchemy.exc import ProgrammingError

    from app.domains.attachment.router import _can_download_via_biz_visibility

    tenant = "00000000-0000-0000-0000-000000000001"
    try:
        row = (await db.execute(text("""
            SELECT c.id AS cust_id,
                   al.attachment_id AS att_id,
                   c.owner_id
            FROM customer c
            JOIN attachment_link al ON al.biz_id = c.id AND al.biz_type = 'customer'
            WHERE c.tenant_id = :tenant
            LIMIT 1
        """), {"tenant": tenant})).mappings().first()
    except ProgrammingError:
        pytest.skip("本地库未初始化业务表")
    if not row or not row["att_id"]:
        pytest.skip("本地无客户附件样本")
    ok = await _can_download_via_biz_visibility(
        db, tenant,
        {"sub": row["owner_id"], "roles": [], "permissions": ["customer:view"]},
        attachment_id=row["att_id"],
    )
    assert ok is True


@pytest.mark.asyncio
async def test_can_download_via_wf_lowcode_form_participant(db):
    """流程审批人预览表单内附件，不必单独授予 attachment:download。"""
    from sqlalchemy import text

    from app.domains.attachment.router import _can_download_via_wf

    tenant = "00000000-0000-0000-0000-000000000001"
    row = (await db.execute(text("""
        SELECT fi.id AS form_id,
               fi.form_data->'attachments'->0->>'id' AS att_id,
               ti.assignee_id
        FROM lc_form_instance fi
        JOIN lc_form_template t ON t.id = fi.template_id
        JOIN wf_process_instance pi ON pi.form_instance_id = fi.id
        JOIN wf_task_instance ti ON ti.process_instance_id = pi.id AND ti.status = 'pending'
        WHERE t.code = 'cs_product_return'
          AND jsonb_array_length(COALESCE(fi.form_data->'attachments', '[]'::jsonb)) > 0
        LIMIT 1
    """))).mappings().first()
    if not row or not row["att_id"]:
        pytest.skip("本地无带附件的 cs_product_return 流程待办")
    ok = await _can_download_via_wf(
        db, tenant, row["assignee_id"], attachment_id=row["att_id"],
    )
    assert ok is True