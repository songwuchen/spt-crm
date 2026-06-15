"""Outward DTO layer for the Open API.

These builders translate internal ORM rows into the *stable, external* shape:
internal-only fields (tenant_id, owner_id, custom_fields_json, is_deleted, internal
flow nodes, …) are deliberately dropped. Values are normalised to JSON primitives
(Decimal→float, date/datetime→ISO string) so the documented field types are exact.
"""
from __future__ import annotations

from decimal import Decimal
from datetime import date, datetime

from app.domains.openapi import status_map as sm


def _iso(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return str(v)


def _num(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    return v


# ---------------------------------------------------------------- customers
def customer_to_dto(c) -> dict:
    return {
        "id": c.id,
        "customer_code": c.customer_code,
        "name": c.name,
        "short_name": c.short_name,
        "industry": c.industry,
        "region": c.region,
        "address": c.address,
        "website": c.website,
        "level": c.level,
        "source": c.source,
        "status": sm.map_status(sm.CUSTOMER_STATUS, c.status),
        "owner_name": c.owner_name,
        "tags": c.tags_json,
        "created_at": _iso(c.created_at),
        "updated_at": _iso(c.updated_at),
    }


# ----------------------------------------------------------------- contacts
def contact_to_dto(c) -> dict:
    return {
        "id": c.id,
        "customer_id": c.customer_id,
        "name": c.name,
        "title": c.title,
        "role_type": c.role_type,
        "phone": c.phone,
        "mobile": c.mobile,
        "email": c.email,
        "is_primary": bool(c.is_primary),
        "created_at": _iso(c.created_at),
        "updated_at": _iso(c.updated_at),
    }


# ------------------------------------------------------------------ projects
def project_to_dto(p) -> dict:
    return {
        "id": p.id,
        "project_code": p.project_code,
        "customer_id": p.customer_id,
        "name": p.name,
        "stage_code": p.stage_code,
        "status": sm.map_status(sm.PROJECT_STATUS, p.status),
        "amount_expect": _num(p.amount_expect),
        "probability": p.probability,
        "close_date_expect": _iso(p.close_date_expect),
        "risk_level": p.risk_level,
        "owner_name": p.owner_name,
        "created_at": _iso(p.created_at),
        "updated_at": _iso(p.updated_at),
    }


# ----------------------------------------------------------------- contracts
def contract_to_dto(c) -> dict:
    return {
        "id": c.id,
        "contract_no": c.contract_no,
        "project_id": c.project_id,
        "status": sm.map_status(sm.CONTRACT_STATUS, c.status),
        "amount_total": _num(c.amount_total),
        "current_version_no": c.current_version_no,
        "signed_date": _iso(c.signed_date),
        "end_date": _iso(c.end_date),
        "created_at": _iso(c.created_at),
        "updated_at": _iso(c.updated_at),
    }


# --------------------------------------------------------------------- leads
def lead_to_dto(l) -> dict:
    return {
        "id": l.id,
        "lead_code": l.lead_code,
        "title": l.title,
        "company_name": l.company_name,
        "contact_name": l.contact_name,
        "contact_phone": l.contact_phone,
        "contact_email": l.contact_email,
        "source": l.source,
        "industry": l.industry,
        "region": l.region,
        "status": l.status,
        "owner_name": l.owner_name,
        "created_at": _iso(l.created_at),
        "updated_at": _iso(l.updated_at),
    }


# ------------------------------------------------------------------ products
def product_to_dto(p) -> dict:
    # NB: cost_price is internal — intentionally not exposed.
    return {
        "id": p.id,
        "product_code": p.product_code,
        "name": p.name,
        "item_type": p.item_type,
        "spec": p.spec,
        "unit": p.unit,
        "unit_price": _num(p.unit_price),
        "leadtime_days": p.leadtime_days,
        "is_active": bool(p.is_active),
        "created_at": _iso(p.created_at),
        "updated_at": _iso(p.updated_at),
    }


# -------------------------------------------------------------------- orders
def order_to_dto(o) -> dict:
    return {
        "id": o.id,
        "order_no": o.order_no,
        "customer_id": o.customer_id,
        "project_id": o.project_id,
        "contract_id": o.contract_id,
        "title": o.title,
        "amount": _num(o.amount),
        "currency": o.currency,
        "status": o.status,
        "order_date": _iso(o.order_date),
        "delivery_date": _iso(o.delivery_date),
        "owner_name": o.owner_name,
        "created_at": _iso(o.created_at),
        "updated_at": _iso(o.updated_at),
    }


# -------------------------------------------------------------------- quotes
def quote_to_dto(q) -> dict:
    return {
        "id": q.id,
        "quote_no": q.quote_no,
        "project_id": q.project_id,
        "status": q.status,
        "current_version_no": q.current_version_no,
        "created_at": _iso(q.created_at),
        "updated_at": _iso(q.updated_at),
    }


def quote_line_to_dto(line) -> dict:
    # NB: cost_est is internal — intentionally not exposed.
    return {
        "line_no": line.line_no,
        "item_type": line.item_type,
        "item_name": line.item_name,
        "item_code": line.item_code,
        "spec": line.spec,
        "qty": _num(line.qty),
        "unit": line.unit,
        "unit_price": _num(line.unit_price),
        "line_total": _num(line.line_total),
        "leadtime_days": line.leadtime_days,
    }


# ------------------------------------------------------------------ payments
def payment_to_dto(r) -> dict:
    return {
        "id": r.id,
        "project_id": r.project_id,
        "amount": _num(r.amount),
        "received_date": _iso(r.received_date),
        "channel": r.channel,
        "reference_no": r.reference_no,
        "matched_plan_id": r.matched_plan_id,
        "created_at": _iso(r.created_at),
        "updated_at": _iso(r.updated_at),
    }


# ------------------------------------------------------------- service tickets
def service_ticket_to_dto(t) -> dict:
    return {
        "id": t.id,
        "ticket_no": t.ticket_no,
        "customer_id": t.customer_id,
        "project_id": t.project_id,
        "type": t.type,
        "priority": t.priority,
        "status": t.status,
        "description": t.description,
        "resolution": t.resolution,
        "assigned_to_name": t.assigned_to_name,
        "satisfaction_score": t.satisfaction_score,
        "created_at": _iso(t.created_at),
        "updated_at": _iso(t.updated_at),
    }


# ------------------------------------------------------------ delivery milestone
def milestone_to_dto(m) -> dict:
    return {
        "id": m.id,
        "project_id": m.project_id,
        "milestone_code": m.milestone_code,
        "name": m.name,
        "status": m.status,
        "plan_date": _iso(m.plan_date),
        "actual_date": _iso(m.actual_date),
        "source_type": m.source_type,
        "created_at": _iso(m.created_at),
        "updated_at": _iso(m.updated_at),
    }


# --------------------------------------------------------------- activities
def activity_to_dto(a) -> dict:
    return {
        "id": a.id,
        "biz_type": a.biz_type,
        "biz_id": a.biz_id,
        "activity_type": a.activity_type,
        "subject": a.subject,
        "content": a.content,
        "next_follow_date": _iso(a.next_follow_date),
        "created_by_name": a.created_by_name,
        "created_at": _iso(a.created_at),
    }


# -------------------------------------------------------------------- events
def event_to_dto(e) -> dict:
    return {
        "event_id": e.id,
        "event_type": e.event_type,
        "event_version": "1.0",
        "aggregate_type": e.aggregate_type,
        "aggregate_id": e.aggregate_id,
        "occurred_at": _iso(e.created_at),
        "source_system": "spt-crm",
        "data": e.payload_json,
    }
