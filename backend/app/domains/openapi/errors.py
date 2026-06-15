"""Open API error model.

Unlike the internal `/api/v1` surface (which returns only an int ``code`` +
``message``), the Open API additionally returns a *stable string* ``error_code``
so integration partners can branch on errors without parsing Chinese messages.
"""
from __future__ import annotations


# ---- Stable error codes (do not rename; partners depend on these strings) ----
CRM_UNAUTHORIZED = "CRM_UNAUTHORIZED"            # missing / invalid credentials
CRM_INVALID_SIGNATURE = "CRM_INVALID_SIGNATURE"  # HMAC signature / timestamp invalid
CRM_APP_DISABLED = "CRM_APP_DISABLED"            # app exists but is disabled
CRM_IP_NOT_ALLOWED = "CRM_IP_NOT_ALLOWED"        # client IP not in whitelist
CRM_FORBIDDEN_SCOPE = "CRM_FORBIDDEN_SCOPE"      # app lacks the required scope
CRM_RATE_LIMITED = "CRM_RATE_LIMITED"            # per-app rate limit exceeded
CRM_NOT_FOUND = "CRM_NOT_FOUND"                  # resource does not exist
CRM_VALIDATION_ERROR = "CRM_VALIDATION_ERROR"    # bad query / path parameter
CRM_INTERNAL_ERROR = "CRM_INTERNAL_ERROR"        # unexpected server error


class OpenApiException(Exception):
    """Raised inside `/openapi/v1` handlers; rendered by the registered handler."""

    def __init__(
        self,
        error_code: str,
        message: str,
        http_status: int = 400,
        details: dict | None = None,
    ):
        self.error_code = error_code
        self.message = message
        self.http_status = http_status
        self.details = details or {}
        super().__init__(message)
