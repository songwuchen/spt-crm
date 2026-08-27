"""Unit tests for lead -> customer matching on qualify."""

from tests.lead_intel_helpers import DEMO_TENANT

from app.domains.lead.customer_link import (
    CUSTOMER_LINK_AMBIGUOUS,
    CUSTOMER_LINK_AUTO_CREATED,
    company_match_key,
    find_unique_customer_by_company_name,
    normalize_company_name,
    resolve_customer_for_lead_convert,
    _primary_company_name,
)


def test_normalize_company_name():
    assert normalize_company_name("  ABC 公司 ") == normalize_company_name("ABC公司")
    assert normalize_company_name("中冶焦耐（大连）") == normalize_company_name("中冶焦耐(大连)")


def test_company_match_key_paren_width():
    a = "中冶焦耐（大连）工程技术有限公司"
    b = "中冶焦耐(大连)工程技术有限公司"
    assert company_match_key(a) == company_match_key(b)
    assert company_match_key(a) == company_match_key("中冶焦耐工程技术有限公司")


def test_primary_company_name_strips_paren_and_splits():
    from types import SimpleNamespace
    lead = SimpleNamespace(company_name="中冶节能环保有限责任公司（总包）")
    assert _primary_company_name(lead) == "中冶节能环保有限责任公司"


async def test_find_unique_customer_exact(db):
    from app.domains.customer.models import Customer
    from app.database import generate_uuid

    c = Customer(
        id=generate_uuid(), tenant_id=DEMO_TENANT, name="唯一匹配测试公司",
        customer_code="C-UNIQ-001", review_status="approved",
    )
    db.add(c)
    await db.flush()

    found = await find_unique_customer_by_company_name(db, DEMO_TENANT, "唯一匹配测试公司")
    assert found is not None
    assert found != CUSTOMER_LINK_AMBIGUOUS
    assert found.id == c.id


async def test_find_unique_customer_fullwidth_paren(db):
    from app.domains.customer.models import Customer
    from app.database import generate_uuid

    tag = generate_uuid()[:8]
    half = f"括号匹配测试(分支{tag})有限公司"
    full = f"括号匹配测试（分支{tag}）有限公司"
    c = Customer(
        id=generate_uuid(), tenant_id=DEMO_TENANT,
        name=half,
        customer_code=f"C-PAREN-{tag}", review_status="approved",
    )
    db.add(c)
    await db.flush()

    found = await find_unique_customer_by_company_name(db, DEMO_TENANT, full)
    assert found is not None
    assert found != CUSTOMER_LINK_AMBIGUOUS
    assert found.id == c.id


async def test_find_unique_customer_ambiguous(db):
    from app.domains.customer.models import Customer
    from app.database import generate_uuid

    dup_name = f"重名测试公司-{generate_uuid()[:8]}"
    for i in range(2):
        db.add(Customer(
            id=generate_uuid(), tenant_id=DEMO_TENANT, name=dup_name,
            customer_code=f"C-DUP-{generate_uuid()[:8]}", review_status="approved",
        ))
    await db.flush()

    found = await find_unique_customer_by_company_name(db, DEMO_TENANT, dup_name)
    assert found == CUSTOMER_LINK_AMBIGUOUS


async def test_resolve_auto_creates_customer(db):
    from types import SimpleNamespace
    from app.database import generate_uuid

    company = f"自动建档公司-{generate_uuid()[:8]}"
    lead = SimpleNamespace(
        id=generate_uuid(),
        lead_code=f"LC{generate_uuid()[:6]}",
        company_name=company,
        industry=None,
        region=None,
        province=None,
        city=None,
        district=None,
        region_code=None,
        source="website",
        reporter_id=None,
        reporter_name=None,
        owner_id=None,
        owner_name=None,
        created_by_id=None,
        created_by_name=None,
    )
    user = {"sub": "test-user", "real_name": "测试员", "username": "tester"}

    cid, source, customer = await resolve_customer_for_lead_convert(db, DEMO_TENANT, lead, user)
    assert source == CUSTOMER_LINK_AUTO_CREATED
    assert cid == customer.id
    assert customer.name == company
    assert customer.review_status == "approved"
