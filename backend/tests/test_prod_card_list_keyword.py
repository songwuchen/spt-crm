"""生产卡列表：按关联合同图纸号搜索。"""
from __future__ import annotations

import app.domains.organization.models  # noqa: F401
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.database import generate_uuid
from app.domains.contract.models import Contract
from app.domains.lowcode.models import FormInstance, FormTemplate, FormTemplateVersion
from app.domains.lowcode.service import list_instances

DEMO_TENANT = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
async def db():
    engine = create_async_engine(settings.DATABASE_URL, echo=False, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_prod_card_list_keyword_by_contract_drawing_no(db):
    tpl = (await db.execute(
        select(FormTemplate).where(
            FormTemplate.tenant_id == DEMO_TENANT,
            FormTemplate.code == "prod_card_supplement",
        ).limit(1)
    )).scalar_one_or_none()
    if not tpl:
        pytest.skip("prod_card_supplement template not seeded")
    ver = (await db.execute(
        select(FormTemplateVersion).where(
            FormTemplateVersion.tenant_id == DEMO_TENANT,
            FormTemplateVersion.template_id == tpl.id,
            FormTemplateVersion.status == "published",
        ).order_by(FormTemplateVersion.version_number.desc()).limit(1)
    )).scalar_one_or_none()
    if not ver:
        pytest.skip("prod_card_supplement published version missing")

    token = generate_uuid()[:8]
    drawing = f"WMGF-UT-{token}"
    reg_serial = f"1.2.3-UT-{token}"
    contract_id = generate_uuid()
    inst_id = generate_uuid()

    db.add(Contract(
        id=contract_id, tenant_id=DEMO_TENANT,
        contract_no=f"KS-UT-{token}", drawing_no=drawing,
        serial_no=f"CRM-SN-{token}",
        registration_json={"serial_no": reg_serial},
        status="active",
    ))
    db.add(FormInstance(
        id=inst_id, tenant_id=DEMO_TENANT, template_id=tpl.id,
        template_version_id=ver.id,
        business_no=f"1.2.UT.{token}", title=f"1.2.UT.{token}",
        status="draft",
        form_data={
            "is_supplement": "否",
            "drawing_no_query": reg_serial,
        },
        initiator_id=generate_uuid(),
    ))
    await db.commit()

    rows, total = await list_instances(
        db, DEMO_TENANT, tpl.id, 1, 20,
        keyword=drawing, owner_ids=None,
    )
    assert total == 1
    assert rows[0].id == inst_id

    _miss, miss_n = await list_instances(
        db, DEMO_TENANT, tpl.id, 1, 20,
        keyword=f"WMGF-NOPE-{token}", owner_ids=None,
    )
    assert miss_n == 0
