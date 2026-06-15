from sqlalchemy import String, Integer, Boolean, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class OpenApiApp(TenantScopedBase):
    """External application allowed to call the SPT-CRM Open API.

    One row = one integration partner / external system, bound to a tenant.
    The secret is shown to the operator only once at creation/rotation:
    - ``secret_hash``  SHA-256 of the secret, used for fast lookup in apikey mode
    - ``secret_enc``   reversible (Fernet) ciphertext, decrypted to verify HMAC signatures
    """
    __tablename__ = "openapi_apps"

    app_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    # public identifier, e.g. app_3f9a2c... — sent as X-App-Id in HMAC mode
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    app_type: Mapped[str] = mapped_column(String(64), default="external_system")
    auth_mode: Mapped[str] = mapped_column(String(16), default="apikey")  # apikey | hmac
    status: Mapped[str] = mapped_column(String(16), default="enabled")     # enabled | disabled
    scopes_json: Mapped[list | None] = mapped_column(JSON)                 # ["crm.customer.read", ...]
    secret_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    secret_enc: Mapped[str | None] = mapped_column(Text)
    secret_prefix: Mapped[str | None] = mapped_column(String(32))          # first chars for display
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=600)
    ip_whitelist_json: Mapped[list | None] = mapped_column(JSON)           # ["10.0.0.0/8", ...]
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    remark: Mapped[str | None] = mapped_column(String(500))


class OpenApiCallLog(TenantScopedBase):
    """Lightweight access log for Open API calls (metadata only, no request body)."""
    __tablename__ = "openapi_call_logs"

    trace_id: Mapped[str | None] = mapped_column(String(64), index=True)
    app_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(16))
    path: Mapped[str] = mapped_column(String(500))
    query_string: Mapped[str | None] = mapped_column(String(1000))
    status_code: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(128))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    client_ip: Mapped[str | None] = mapped_column(String(64))
