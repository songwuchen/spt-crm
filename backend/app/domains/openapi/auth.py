"""Open API authentication & authorization.

Two credential modes, selected per-app by ``OpenApiApp.auth_mode``:

* ``apikey`` — client sends ``X-API-Key: <secret>``. The server hashes it (SHA-256)
  and looks the app up by ``secret_hash`` (unique index — no table scan).
* ``hmac``   — client sends ``X-App-Id`` (= ``app_key``), ``X-Timestamp`` and
  ``X-Signature``. The server decrypts the stored secret and verifies
  ``HMAC-SHA256(secret, METHOD\nPATH\nQUERY\nTIMESTAMP\nSHA256(BODY))``.
  Timestamp skew must be ≤ 5 min (replay window). Per-nonce replay protection
  requires Redis and is therefore deferred while Redis is disabled.

After the app is resolved we enforce: enabled status, IP whitelist, and an
in-process per-app sliding-window rate limit, then expose the resolved
``OpenApiContext`` (tenant_id + scopes) for the route to use.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
import ipaddress
from collections import defaultdict
from dataclasses import dataclass, field

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.common.crypto import decrypt_value
from app.domains.openapi.models import OpenApiApp
from app.domains.openapi.errors import (
    OpenApiException,
    CRM_UNAUTHORIZED,
    CRM_INVALID_SIGNATURE,
    CRM_APP_DISABLED,
    CRM_IP_NOT_ALLOWED,
    CRM_FORBIDDEN_SCOPE,
    CRM_RATE_LIMITED,
)

TIMESTAMP_TOLERANCE_SECONDS = 300


# ----------------------------------------------------------------- secrets
def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def generate_app_key() -> str:
    return "app_" + secrets.token_hex(12)


def generate_secret() -> str:
    # URL-safe, ~43 chars of entropy; carried verbatim in X-API-Key / HMAC key.
    return "sk_" + secrets.token_urlsafe(32)


# -------------------------------------------------- in-process rate limiter
_hits: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(app_key: str, limit_per_minute: int) -> None:
    now = time.time()
    cutoff = now - 60
    bucket = [t for t in _hits[app_key] if t > cutoff]
    if len(bucket) >= limit_per_minute:
        _hits[app_key] = bucket
        raise OpenApiException(
            CRM_RATE_LIMITED, "请求过于频繁，请稍后再试", http_status=429,
            details={"limit_per_minute": limit_per_minute},
        )
    bucket.append(now)
    _hits[app_key] = bucket


# ------------------------------------------------------------------ context
@dataclass
class OpenApiContext:
    app_id: str
    app_key: str
    tenant_id: str
    scopes: list[str] = field(default_factory=list)

    def has_scope(self, scope: str) -> bool:
        return scope in (self.scopes or [])


# --------------------------------------------------------------- IP helpers
def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


def _ip_allowed(ip: str | None, whitelist: list | None) -> bool:
    if not whitelist:
        return True
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for cidr in whitelist:
        try:
            if addr in ipaddress.ip_network(str(cidr), strict=False):
                return True
        except ValueError:
            continue
    return False


# ----------------------------------------------------------- HMAC verifying
async def _verify_hmac(request: Request, app: OpenApiApp) -> None:
    ts = request.headers.get("X-Timestamp", "")
    sig = request.headers.get("X-Signature", "")
    if not ts or not sig:
        raise OpenApiException(CRM_INVALID_SIGNATURE, "缺少签名头", http_status=401)
    try:
        skew = abs(time.time() - float(ts))
    except ValueError:
        raise OpenApiException(CRM_INVALID_SIGNATURE, "时间戳无效", http_status=401)
    if skew > TIMESTAMP_TOLERANCE_SECONDS:
        raise OpenApiException(CRM_INVALID_SIGNATURE, "时间戳已过期", http_status=401)

    secret = decrypt_value(app.secret_enc) if app.secret_enc else None
    if not secret or secret == "***":
        raise OpenApiException(CRM_INVALID_SIGNATURE, "应用密钥不可用于签名校验", http_status=401)

    body = await request.body()
    body_hash = hashlib.sha256(body or b"").hexdigest()
    canonical = "\n".join([
        request.method,
        request.url.path,
        request.url.query or "",
        ts,
        body_hash,
    ])
    expected = hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    provided = sig.split("=", 1)[1] if sig.startswith("sha256=") else sig
    if not hmac.compare_digest(expected, provided.strip()):
        raise OpenApiException(CRM_INVALID_SIGNATURE, "签名校验失败", http_status=401)


# -------------------------------------------------------- main dependency
async def get_openapi_context(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> OpenApiContext:
    api_key = request.headers.get("X-API-Key")
    app_id_hdr = request.headers.get("X-App-Id")

    app: OpenApiApp | None = None
    if app_id_hdr or request.headers.get("X-Signature"):
        # HMAC attempt — resolve by public app_key
        app = (await db.execute(
            select(OpenApiApp).where(
                OpenApiApp.app_key == app_id_hdr,
                OpenApiApp.is_deleted == False,  # noqa: E712
            )
        )).scalar_one_or_none()
        if not app:
            raise OpenApiException(CRM_UNAUTHORIZED, "应用不存在或未授权", http_status=401)
        if app.auth_mode != "hmac":
            raise OpenApiException(CRM_UNAUTHORIZED, "该应用未启用 HMAC 签名认证", http_status=401)
        await _verify_hmac(request, app)
    elif api_key:
        app = (await db.execute(
            select(OpenApiApp).where(
                OpenApiApp.secret_hash == hash_secret(api_key),
                OpenApiApp.is_deleted == False,  # noqa: E712
            )
        )).scalar_one_or_none()
        if not app:
            raise OpenApiException(CRM_UNAUTHORIZED, "API Key 无效", http_status=401)
        if app.auth_mode != "apikey":
            raise OpenApiException(CRM_UNAUTHORIZED, "该应用需使用 HMAC 签名认证", http_status=401)
    else:
        raise OpenApiException(CRM_UNAUTHORIZED, "缺少认证凭据 (X-API-Key 或 X-App-Id)", http_status=401)

    if app.status != "enabled":
        raise OpenApiException(CRM_APP_DISABLED, "应用已停用", http_status=403)

    if not _ip_allowed(_client_ip(request), app.ip_whitelist_json):
        raise OpenApiException(CRM_IP_NOT_ALLOWED, "来源 IP 不在白名单内", http_status=403)

    _check_rate_limit(app.app_key, app.rate_limit_per_minute or 600)

    # Expose for the call-log middleware / downstream.
    request.state.openapi_app_key = app.app_key
    request.state.openapi_tenant_id = app.tenant_id

    return OpenApiContext(
        app_id=app.id,
        app_key=app.app_key,
        tenant_id=app.tenant_id,
        scopes=app.scopes_json or [],
    )


def require_scope(scope: str):
    """Dependency factory: authenticate, then assert the app holds ``scope``."""

    async def _checker(ctx: OpenApiContext = Depends(get_openapi_context)) -> OpenApiContext:
        if not ctx.has_scope(scope):
            raise OpenApiException(
                CRM_FORBIDDEN_SCOPE, f"应用缺少所需权限范围: {scope}",
                http_status=403, details={"required_scope": scope},
            )
        return ctx

    return _checker
