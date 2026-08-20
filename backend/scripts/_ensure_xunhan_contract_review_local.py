#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import json
import sys
import urllib.request

import asyncpg
import bcrypt

BASE = "http://127.0.0.1:8005"
TENANT = "00000000-0000-0000-0000-000000000001"
PWD = "Admin@local1"


async def reset_pw() -> None:
    conn = await asyncpg.connect("postgresql://postgres:postgres@localhost:5432/spt_crm")
    try:
        h = bcrypt.hashpw(PWD.encode(), bcrypt.gensalt()).decode()
        await conn.execute(
            "UPDATE users SET password_hash=$1 WHERE tenant_id::text=$2 AND username='admin'",
            h,
            TENANT,
        )
        print("pw reset")
    finally:
        await conn.close()


def http(method: str, path: str, body=None, token=None):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=180) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def main() -> None:
    asyncio.run(reset_pw())
    code, body = http(
        "POST",
        "/api/v1/auth/login",
        {"username": "admin", "password": PWD, "tenant_code": "default"},
    )
    print("login", code)
    token = (body.get("data") or {}).get("access_token")
    if not token:
        print(body)
        sys.exit(1)
    code, body = http(
        "POST",
        "/api/v1/lc/builtin-templates/xunhan_contract_review/ensure",
        token=token,
    )
    print("ensure", code)
    d = body.get("data") or {}
    print("id", d.get("id"), "name", d.get("name"), "fields", len(d.get("field_definitions") or []))
    if code != 200 or not d.get("id"):
        print(body)
        sys.exit(2)
    print("OK open http://localhost:5175/xunhan-contract-reviews")


if __name__ == "__main__":
    main()
