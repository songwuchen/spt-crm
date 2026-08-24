# -*- coding: utf-8 -*-
"""客户驳回后可编辑。"""
from __future__ import annotations

import pytest

from app.common.exceptions import BusinessException
from app.database import generate_uuid
from app.domains.lowcode.edit_lock import assert_customer_editable
from tests.lead_intel_helpers import DEMO_TENANT


@pytest.mark.asyncio
async def test_customer_rejected_is_editable(db):
    await assert_customer_editable(db, DEMO_TENANT, generate_uuid(), "rejected")


@pytest.mark.asyncio
async def test_customer_rejected_running_still_locked(db, monkeypatch):
    async def _running(*_a, **_k):
        return True

    monkeypatch.setattr(
        "app.domains.lowcode.edit_lock.has_running_process",
        _running,
    )
    with pytest.raises(BusinessException):
        await assert_customer_editable(db, DEMO_TENANT, generate_uuid(), "rejected")
