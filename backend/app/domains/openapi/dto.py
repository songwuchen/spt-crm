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
