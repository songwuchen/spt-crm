"""Service-level: OpenAPI form-instance upsert for drawing forms."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.domains.lowcode import service as lc_service
from app.domains.lowcode.models import FormInstance
from app.domains.openapi.schemas import OpenFormInstanceUpsert
from app.domains.openapi.service import create_form_instance_from_openapi
from sqlalchemy import delete, select


TENANT = "00000000-0000-0000-0000-000000000001"


class _Ctx:
    def __init__(self):
        self.tenant_id = TENANT
        self.app_id = "test-openapi-app"
        self.app_key = "ak_test"


@pytest.fixture
async def db():
    engine = create_async_engine(settings.DATABASE_URL, echo=False, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_form_instance_upsert_drawing_requisition(db):
    ctx = _Ctx()
    user = {"sub": "ut-admin", "username": "admin", "real_name": "UT"}
    try:
        await lc_service.ensure_builtin_form(db, TENANT, "drawing_requisition", user)
    except Exception as e:
        pytest.skip(f"drawing_requisition builtin unavailable: {e}")

    ext = f"jdy-ut-{uuid.uuid4().hex[:10]}"
    inst_id = None
    try:
        first = await create_form_instance_from_openapi(
            db, ctx,
            OpenFormInstanceUpsert(
                template_code="drawing_requisition",
                external_key=ext,
                title="UT图纸领用",
                as_draft=True,
                form_data={
                    "apply_reason": "单元测试申请事由",
                    "attachment_name": "test.pdf",
                    "transfer_channel": "钉钉",
                    "need_decrypt": "不解密",
                    "drawing_type": "其他",
                },
            ),
        )
        assert first["upsert"] == "created"
        assert first["external_key"] == ext
        assert first["status"] == "draft"
        inst_id = first["id"]

        second = await create_form_instance_from_openapi(
            db, ctx,
            OpenFormInstanceUpsert(
                template_code="drawing_requisition",
                external_key=ext,
                title="UT图纸领用-更新",
                as_draft=True,
                form_data={
                    "apply_reason": "已更新事由",
                    "attachment_name": "test.pdf",
                    "transfer_channel": "钉钉",
                    "need_decrypt": "不解密",
                    "drawing_type": "其他",
                },
            ),
        )
        assert second["upsert"] == "updated"
        assert second["id"] == inst_id

        row = (await db.execute(
            select(FormInstance).where(FormInstance.id == inst_id)
        )).scalar_one()
        assert (row.form_data or {}).get("apply_reason") == "已更新事由"
        assert (row.form_data or {}).get("_external_key") == ext
    finally:
        if inst_id:
            await db.execute(delete(FormInstance).where(FormInstance.id == inst_id))
            await db.commit()
