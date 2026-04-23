"""Seed DataDictionary values for lead classification (issue #17).

Idempotent: inserts customer_type + industry entries for every existing tenant,
skipping codes that already exist. Industry entries replace legacy generic values
by disabling any prior industry dict_codes that are not in the new list.

Run:
  python -m scripts.seed_lead_dicts                 # auto-discover tenants
  python -m scripts.seed_lead_dicts <tenant_id>     # explicit tenant

Discovery: prefers platform_tenants, falls back to distinct tenant_ids in users
(platform_tenants may be empty in setups that never ran the full seed).
"""
import asyncio
import sys
import uuid

from sqlalchemy import select, text

from app.database import async_session_factory
from app.domains.admin.models import DataDictionary
from app.domains.tenant.models import PlatformTenant


CUSTOMER_TYPES = [
    ("terminal_soe", "终端客户-央企/国企"),
    ("terminal_large_private", "终端客户-大型民企（注册资本10亿以上）"),
    ("terminal_private", "终端客户-一般民企"),
    ("design_institute", "设计院"),
    ("general_contractor", "总包商"),
    ("supporting_vendor", "配套商"),
    ("trader", "贸易商"),
    ("other", "其他"),
]

INDUSTRIES = [
    ("screening_metallurgy", "筛分分选-冶金"),
    ("screening_mining", "筛分分选-矿山"),
    ("screening_aggregate", "筛分分选-砂石"),
    ("screening_coking", "筛分分选-焦化"),
    ("screening_coal", "筛分分选-煤炭"),
    ("screening_power", "筛分分选-电力"),
    ("screening_chemical", "筛分分选-化工"),
    ("screening_pharma", "筛分分选-医药"),
    ("screening_spare_parts", "筛分分选-备件"),
    ("circular_economy", "循环经济"),
    ("scrap_steel", "废钢利用"),
    ("bulk_material_intelligent", "智能化大宗物料管理"),
]


async def seed_for_tenant(session, tenant_id: str) -> dict:
    stats = {"customer_type_added": 0, "industry_added": 0, "industry_disabled": 0}

    # customer_type: insert any missing codes; don't touch existing (idempotent)
    existing_ct = {
        r.dict_code for r in (
            await session.execute(
                select(DataDictionary).where(
                    DataDictionary.tenant_id == tenant_id,
                    DataDictionary.dict_type == "customer_type",
                )
            )
        ).scalars().all()
    }
    for i, (code, label) in enumerate(CUSTOMER_TYPES):
        if code in existing_ct:
            continue
        session.add(DataDictionary(
            id=str(uuid.uuid4()), tenant_id=tenant_id,
            dict_type="customer_type", dict_code=code, dict_label=label,
            sort_order=i, enabled=True,
        ))
        stats["customer_type_added"] += 1

    # industry: insert new business-specific codes; disable any legacy codes not in the new list
    new_codes = {code for code, _ in INDUSTRIES}
    existing_industry = (
        await session.execute(
            select(DataDictionary).where(
                DataDictionary.tenant_id == tenant_id,
                DataDictionary.dict_type == "industry",
            )
        )
    ).scalars().all()
    existing_industry_codes = {d.dict_code for d in existing_industry}

    for i, (code, label) in enumerate(INDUSTRIES):
        if code in existing_industry_codes:
            continue
        session.add(DataDictionary(
            id=str(uuid.uuid4()), tenant_id=tenant_id,
            dict_type="industry", dict_code=code, dict_label=label,
            sort_order=i, enabled=True,
        ))
        stats["industry_added"] += 1

    # Soft-disable any legacy industry codes that the business no longer wants shown
    for d in existing_industry:
        if d.dict_code not in new_codes and d.enabled:
            d.enabled = False
            stats["industry_disabled"] += 1

    return stats


async def _discover_tenant_ids(session) -> list[tuple[str, str]]:
    """Return [(tenant_id, display_name), ...]. Prefer platform_tenants; else fall back to users.

    Raw SQL for the fallback avoids importing User (which pulls in a web of
    mapper relationships that need all sibling models loaded before use).
    """
    tenants = (await session.execute(select(PlatformTenant))).scalars().all()
    if tenants:
        return [(t.id, getattr(t, "name", "?") or "?") for t in tenants]

    rows = (await session.execute(text("SELECT DISTINCT tenant_id FROM users"))).all()
    return [(r[0], "(discovered from users)") for r in rows if r[0]]


async def main():
    explicit = sys.argv[1] if len(sys.argv) > 1 else None
    async with async_session_factory() as session:
        if explicit:
            tenant_pairs = [(explicit, "(explicit)")]
        else:
            tenant_pairs = await _discover_tenant_ids(session)

        if not tenant_pairs:
            print("No tenants found; skipping.")
            return

        for tid, name in tenant_pairs:
            stats = await seed_for_tenant(session, tid)
            print(f"[tenant={tid} name={name}] {stats}")
        await session.commit()
        print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
