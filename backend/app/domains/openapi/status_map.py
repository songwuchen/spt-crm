"""External status mapping layer.

Internal status values may evolve; the values exposed through the Open API are a
stable contract. Each map translates an internal value to its external form.
Unknown values fall through unchanged so new internal states never crash a call —
they simply surface as-is until an explicit mapping is added.
"""
from __future__ import annotations

CUSTOMER_STATUS = {
    "active": "active",
    "inactive": "inactive",
}

PROJECT_STATUS = {
    "active": "active",
    "won": "won",
    "lost": "lost",
    "suspended": "suspended",
}

CONTRACT_STATUS = {
    "draft": "draft",
    "signed": "signed",
    "terminated": "terminated",
}


def map_status(table: dict[str, str], value: str | None) -> str | None:
    if value is None:
        return None
    return table.get(value, value)
