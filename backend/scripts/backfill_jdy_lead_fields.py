#!/usr/bin/env python3
"""Dry-run / apply backfill for JDY-synced CRM leads (department/owner/reporter/reported_at).

Usage (inside spt-crm-backend container or host with DATABASE_URL + JDY creds):

  python -m scripts.backfill_jdy_lead_fields --dry-run
  python -m scripts.backfill_jdy_lead_fields --apply

Only touches leads that were created via openapi with Idempotency-Key jdy-lead-{data_id}.
Owner/department are overwritten only when name resolution succeeds.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

# Allow running from /tmp inside the backend image (PYTHONPATH=/app).
_ROOT = os.environ.get("APP_ROOT", "/app")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

JDY_APP_ID = "5de0b3e85600ec0006f420f2"
JDY_ENTRY_ID = "636ca7a4493618000af57265"
WIDGET_DEPT = "_widget_1668065189184"
WIDGET_OWNER = "_widget_1668065189147"
PREFIX = "jdy-lead-"


def _name_of(val: Any) -> str | None:
    if val is None:
        return None
    if isinstance(val, dict):
        return (val.get("name") or val.get("username") or "").strip() or None
    if isinstance(val, list) and val:
        return _name_of(val[0])
    s = str(val).strip()
    return s or None


def _jdy_sign_get(base: str, app_key: str, secret: str, path: str, query: dict, retries: int = 6) -> dict:
    empty = hashlib.sha256(b"").hexdigest()
    q = urllib.parse.urlencode(query)
    last_err: Exception | None = None
    for attempt in range(retries):
        ts = str(int(time.time()))
        nonce = uuid.uuid4().hex
        canonical = "\n".join(["GET", path, q, ts, nonce, empty])
        sig = hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
        url = base.rstrip("/") + path + ("?" + q if q else "")
        req = urllib.request.Request(
            url,
            headers={
                "X-App-Key": app_key,
                "X-Timestamp": ts,
                "X-Nonce": nonce,
                "X-Signature": sig,
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                env = json.load(resp)
            if env.get("code") not in (0, None):
                raise RuntimeError(f"jdy error: {env}")
            return env.get("data") or {}
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (429, 502, 503, 504) and attempt < retries - 1:
                time.sleep(min(30, 1.5 ** attempt))
                continue
            raise
    raise last_err  # type: ignore[misc]


def fetch_all_jdy_records(base: str, app_key: str, secret: str) -> dict[str, dict]:
    """Page through GET /records for the lead form; return data_id -> record."""
    out: dict[str, dict] = {}
    skip = 0
    limit = 100
    while True:
        data = _jdy_sign_get(
            base, app_key, secret, "/api/open/v1/records",
            {"app_id": JDY_APP_ID, "entry_id": JDY_ENTRY_ID, "skip": str(skip), "limit": str(limit)},
        )
        items = data.get("items") or []
        for rec in items:
            did = rec.get("data_id") or rec.get("id")
            if did:
                out[str(did)] = rec
        if len(items) < limit:
            break
        skip += limit
        time.sleep(0.2)
    return out


def fetch_jdy_record(base: str, app_key: str, secret: str, data_id: str) -> dict | None:
    path = f"/api/open/v1/records/{JDY_APP_ID}/{JDY_ENTRY_ID}/{data_id}"
    try:
        return _jdy_sign_get(base, app_key, secret, path, {})
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def parse_reported_at(rec: dict) -> datetime | None:
    raw = rec.get("jdy_create_time") or rec.get("createTime") or rec.get("create_time")
    data = rec.get("data") or {}
    if not raw:
        # some hubs put system times on the record root only
        pass
    if not raw:
        return None
    s = str(raw).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        try:
            return datetime.fromisoformat(s[:19]).replace(tzinfo=timezone.utc)
        except ValueError:
            return None


async def run(dry_run: bool, limit: int | None, sample: int) -> int:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy.pool import NullPool

    from app.config import settings
    # Ensure ORM relationship class names are registered before Department queries.
    import app.domains.auth.models  # noqa: F401
    import app.domains.organization.models  # noqa: F401
    from app.domains.openapi.models import OpenApiIdempotencyKey
    from app.domains.lead.models import Lead
    from app.domains.lead.schemas import LeadUpdate
    from app.domains.lead.service import update_lead
    from app.domains.openapi.service import (
        resolve_department_id, resolve_owner_id, resolve_reporter_id,
    )
    from app.domains.lowcode.field_permission import SYSTEM_ROLE

    jdy_base = os.environ.get("JDY_BASE_URL", "http://192.168.0.6:8011")
    jdy_key = os.environ.get("JDY_APP_KEY") or ""
    jdy_secret = os.environ.get("JDY_APP_SECRET") or ""
    if not jdy_key or not jdy_secret:
        print("ERROR: set JDY_APP_KEY and JDY_APP_SECRET", file=sys.stderr)
        return 2

    engine = create_async_engine(settings.DATABASE_URL, echo=False, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    stats = {
        "total_keys": 0,
        "missing_lead": 0,
        "missing_jdy": 0,
        "skipped_no_change": 0,
        "would_update": 0,
        "updated": 0,
        "failed": 0,
        "dept_resolved": 0,
        "owner_resolved": 0,
        "reporter_resolved": 0,
        "reported_at_set": 0,
    }
    samples: list[dict] = []

    print(f"loading JDY records for {JDY_APP_ID}/{JDY_ENTRY_ID} ...")
    jdy_by_id = fetch_all_jdy_records(jdy_base, jdy_key, jdy_secret)
    print(f"jdy records loaded: {len(jdy_by_id)}")

    async with factory() as db:
        q = (
            select(OpenApiIdempotencyKey)
            .where(
                OpenApiIdempotencyKey.idempotency_key.like(PREFIX + "%"),
                OpenApiIdempotencyKey.status == "completed",
            )
            .order_by(OpenApiIdempotencyKey.created_at.asc())
        )
        rows = (await db.execute(q)).scalars().all()
        if limit is not None:
            rows = rows[:limit]
        stats["total_keys"] = len(rows)
        print(f"idempotency keys (jdy-lead-*, completed): {len(rows)}")

        class _Ctx:
            app_id = "backfill-script"
            app_key = "backfill"
            tenant_id = None

        for rec in rows:
            key = rec.idempotency_key or ""
            data_id = key[len(PREFIX):] if key.startswith(PREFIX) else ""
            lead_id = (rec.response_json or {}).get("id")
            tenant_id = rec.tenant_id
            if not lead_id or not data_id:
                stats["missing_lead"] += 1
                continue

            lead = (await db.execute(
                select(Lead).where(Lead.id == lead_id, Lead.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if not lead:
                stats["missing_lead"] += 1
                continue
            if getattr(lead, "is_deleted", False):
                stats["missing_lead"] += 1
                continue

            jdy_rec = jdy_by_id.get(data_id)
            if not jdy_rec:
                stats["missing_jdy"] += 1
                continue

            if "data" not in jdy_rec and isinstance(jdy_rec.get("record"), dict):
                jdy_rec = jdy_rec["record"]
            data = jdy_rec.get("data") or {}
            dept_name = _name_of(data.get(WIDGET_DEPT))
            owner_name = _name_of(data.get(WIDGET_OWNER))
            reported_at = parse_reported_at(jdy_rec)
            if reported_at is None and jdy_rec.get("createTime"):
                reported_at = parse_reported_at({"jdy_create_time": jdy_rec["createTime"]})

            dept_id = await resolve_department_id(
                db, tenant_id, department_id=None, department_name=dept_name,
            )
            owner_id = await resolve_owner_id(
                db, tenant_id, owner_id=None, owner_name=owner_name,
            )
            reporter_id = await resolve_reporter_id(
                db, tenant_id, reporter_id=None, reporter_name=owner_name,
            )

            patch: dict[str, Any] = {}
            if dept_id:
                stats["dept_resolved"] += 1
                if dept_id != lead.department_id:
                    patch["department_id"] = dept_id

            if owner_id:
                stats["owner_resolved"] += 1
                if owner_id != lead.owner_id:
                    patch["owner_id"] = owner_id

            if reporter_id:
                stats["reporter_resolved"] += 1
                if reporter_id != lead.reporter_id:
                    patch["reporter_id"] = reporter_id

            if reported_at is not None:
                stats["reported_at_set"] += 1
                cur = lead.reported_at
                if cur is None or cur != reported_at:
                    patch["reported_at"] = reported_at

            sample_row = {
                "data_id": data_id,
                "lead_id": lead_id,
                "title": lead.title,
                "dept_name": dept_name,
                "dept_id": dept_id,
                "owner_name": owner_name,
                "owner_id": owner_id,
                "reporter_id": reporter_id,
                "reported_at": reported_at.isoformat() if reported_at else None,
                "patch_keys": sorted(patch.keys()),
            }
            if len(samples) < sample:
                samples.append(sample_row)

            if not patch:
                stats["skipped_no_change"] += 1
                continue

            stats["would_update"] += 1
            if dry_run:
                continue

            try:
                # permissions=* so get_lead/assert_in_scope treats us as full-tenant
                # (SYSTEM_ROLE alone only bypasses field policy, not data scope).
                user = {
                    "sub": "backfill-script",
                    "username": "openapi:backfill",
                    "real_name": "开放平台回刷",
                    "roles": [SYSTEM_ROLE],
                    "permissions": ["*"],
                }
                await update_lead(db, tenant_id, lead_id, LeadUpdate(**patch), user)
                stats["updated"] += 1
            except Exception as e:
                stats["failed"] += 1
                msg = getattr(e, "message", None) or repr(e)
                print(f"FAIL update {lead_id}: {msg}")
                try:
                    await db.rollback()
                except Exception:
                    pass

    await engine.dispose()

    print("\n=== samples ===")
    print(json.dumps(samples, ensure_ascii=False, indent=2))
    print("\n=== stats ===")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0 if stats["failed"] == 0 else 1


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", default=False)
    p.add_argument("--apply", action="store_true", default=False)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--sample", type=int, default=5)
    args = p.parse_args()
    dry = not args.apply
    if args.dry_run:
        dry = True
    import asyncio
    raise SystemExit(asyncio.run(run(dry_run=dry, limit=args.limit, sample=args.sample)))


if __name__ == "__main__":
    main()
