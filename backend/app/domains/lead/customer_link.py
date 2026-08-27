"""线索转商机：按公司名称匹配客户管理，唯一命中则绑定。"""
from __future__ import annotations

import re
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.customer.models import Customer
from app.domains.lead.models import Lead

CUSTOMER_LINK_MATCHED = "matched"
CUSTOMER_LINK_UNMATCHED = "unmatched"
CUSTOMER_LINK_AMBIGUOUS = "ambiguous"

CustomerLinkSource = Literal["matched", "unmatched", "ambiguous"]


def normalize_company_name(name: str | None) -> str:
    if not name:
        return ""
    t = str(name).strip()
    t = re.sub(r"\s+", "", t)
    return t.lower()


def _primary_company_name(lead: Lead) -> str:
    raw = (lead.company_name or "").strip()
    if not raw:
        return ""
    base = re.sub(r"[（(].*?[）)]", "", raw).strip() or raw
    parts = re.split(r"[,，、/\\|；;]+", base)
    for p in parts:
        p = p.strip()
        p = re.sub(r"(采购|使用现场|使用方|业主)$", "", p).strip()
        if p:
            return p
    return base


async def find_unique_customer_by_company_name(
    db: AsyncSession, tenant_id: str, company_name: str,
) -> Customer | Literal["ambiguous"] | None:
    """按公司名称精确匹配唯一客户；重名则返回 ambiguous（不自动绑定）。"""
    key = normalize_company_name(company_name)
    if not key:
        return None
    rows = (await db.execute(
        select(Customer).where(
            Customer.tenant_id == tenant_id,
            Customer.is_deleted == False,  # noqa: E712
        )
    )).scalars().all()
    hits: list[Customer] = []
    seen: set[str] = set()
    for c in rows:
        for candidate in (c.name, c.short_name):
            if normalize_company_name(candidate) != key:
                continue
            if c.id in seen:
                break
            seen.add(c.id)
            hits.append(c)
            break
    if not hits:
        return None
    if len(hits) > 1:
        return "ambiguous"
    return hits[0]


async def resolve_customer_for_lead_convert(
    db: AsyncSession, tenant_id: str, lead: Lead, user: dict,
) -> tuple[str | None, str | None, Customer | None]:
    """返回 (customer_id, customer_link_source, customer_obj)。无匹配时不建档、不绑定。"""
    del user  # 保留签名供后续扩展（如审计）
    company = _primary_company_name(lead)
    if not company:
        return None, CUSTOMER_LINK_UNMATCHED, None

    found = await find_unique_customer_by_company_name(db, tenant_id, company)
    if found == "ambiguous":
        return None, CUSTOMER_LINK_AMBIGUOUS, None
    if isinstance(found, Customer):
        return found.id, CUSTOMER_LINK_MATCHED, found

    return None, CUSTOMER_LINK_UNMATCHED, None
