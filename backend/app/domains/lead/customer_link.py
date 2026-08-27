"""线索转商机：按公司名称匹配客户管理，唯一命中则绑定。"""
from __future__ import annotations

import re
import unicodedata
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.customer.models import Customer
from app.domains.lead.models import Lead

CUSTOMER_LINK_MATCHED = "matched"
CUSTOMER_LINK_UNMATCHED = "unmatched"
CUSTOMER_LINK_AMBIGUOUS = "ambiguous"
CUSTOMER_LINK_AUTO_CREATED = "auto_created"

CustomerLinkSource = Literal["matched", "unmatched", "ambiguous", "auto_created"]

_PAREN_SUFFIX_RE = re.compile(r"(采购|使用现场|使用方|业主)$")


def normalize_company_name(name: str | None) -> str:
    if not name:
        return ""
    t = unicodedata.normalize("NFKC", str(name).strip())
    t = re.sub(r"\s+", "", t)
    return t.lower()


def _strip_company_name(raw: str) -> str:
    """去掉括号备注、多主体分隔后的主公司名（展示/比对共用）。"""
    base = re.sub(r"[（(].*?[）)]", "", raw).strip() or raw
    parts = re.split(r"[,，、/\\|；;]+", base)
    for p in parts:
        p = p.strip()
        p = _PAREN_SUFFIX_RE.sub("", p).strip()
        if p:
            return p
    return base


def company_match_key(name: str | None) -> str:
    """线索与客户名称比对用 canonical key（全半角统一、去空白、去括号备注）。"""
    if not name:
        return ""
    raw = unicodedata.normalize("NFKC", str(name).strip())
    return normalize_company_name(_strip_company_name(raw))


def _primary_company_name(lead: Lead) -> str:
    raw = (lead.company_name or "").strip()
    if not raw:
        return ""
    return _strip_company_name(unicodedata.normalize("NFKC", raw))


async def find_unique_customer_by_company_name(
    db: AsyncSession, tenant_id: str, company_name: str,
) -> Customer | Literal["ambiguous"] | None:
    """按公司名称精确匹配唯一客户；重名则返回 ambiguous（不自动绑定）。"""
    key = company_match_key(company_name)
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
            if not candidate:
                continue
            if company_match_key(candidate) != key:
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


async def create_customer_from_lead_convert(
    db: AsyncSession, tenant_id: str, lead: Lead, user: dict,
) -> Customer:
    """线索转商机时未匹配到已有客户：按线索公司信息自动建档（不启客户信息审批）。"""
    from app.common.code_generator import generate_code
    from app.database import generate_uuid
    from app.domains.outbox.service import emit_event

    raw_name = unicodedata.normalize("NFKC", (lead.company_name or "").strip())
    name = raw_name or _primary_company_name(lead)
    if not name:
        raise ValueError("线索缺少公司名称，无法自动创建客户")

    owner_id = lead.reporter_id or lead.owner_id or lead.created_by_id or user.get("sub")
    owner_name = lead.reporter_name or lead.owner_name or lead.created_by_name

    _uname = user.get("real_name") or user.get("username")
    lead_ref = lead.lead_code or lead.id
    customer = Customer(
        id=generate_uuid(),
        tenant_id=tenant_id,
        customer_code=await generate_code(db, tenant_id, "customer"),
        name=name,
        industry=lead.industry,
        region=lead.region,
        province=lead.province,
        city=lead.city,
        district=lead.district,
        region_code=lead.region_code,
        source=lead.source,
        owner_id=owner_id,
        owner_name=owner_name,
        created_by_id=user.get("sub"),
        created_by_name=_uname,
        updated_by_id=user.get("sub"),
        updated_by_name=_uname,
        review_status="approved",
        status="active",
        remark=f"线索 {lead_ref} 转商机时系统自动创建",
    )
    db.add(customer)
    await emit_event(db, tenant_id, "crm.customer.created", "customer", customer.id, {
        "customer_id": customer.id,
        "customer_code": customer.customer_code,
        "name": customer.name,
        "source": "lead_convert",
        "lead_id": lead.id,
    })
    await db.flush()
    return customer


async def resolve_customer_for_lead_convert(
    db: AsyncSession, tenant_id: str, lead: Lead, user: dict,
) -> tuple[str | None, str | None, Customer | None]:
    """返回 (customer_id, customer_link_source, customer_obj)。

    唯一匹配已有客户则绑定；未匹配则自动建档并标 auto_created；重名则 ambiguous。
    """
    company = _primary_company_name(lead)
    if not company:
        return None, CUSTOMER_LINK_UNMATCHED, None

    found = await find_unique_customer_by_company_name(db, tenant_id, company)
    if found == "ambiguous":
        return None, CUSTOMER_LINK_AMBIGUOUS, None
    if isinstance(found, Customer):
        return found.id, CUSTOMER_LINK_MATCHED, found

    created = await create_customer_from_lead_convert(db, tenant_id, lead, user)
    return created.id, CUSTOMER_LINK_AUTO_CREATED, created
