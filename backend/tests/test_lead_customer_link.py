"""Unit tests for lead -> customer matching on qualify."""

from tests.lead_intel_helpers import DEMO_TENANT

from app.domains.lead.customer_link import (
    CUSTOMER_LINK_AMBIGUOUS,
    find_unique_customer_by_company_name,
    normalize_company_name,
    _primary_company_name,
)


def test_normalize_company_name():
    assert normalize_company_name("  ABC 公司 ") == normalize_company_name("ABC公司")


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
