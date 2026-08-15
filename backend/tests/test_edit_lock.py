"""提交后锁编辑：status / running 流程闸门。"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.common.exceptions import BusinessException
from app.domains.lowcode.edit_lock import (
    assert_biz_editable,
    assert_content_update_allowed,
    assert_contract_record_editable,
    assert_form_instance_editable,
    assert_lead_editable,
    is_status_editable,
)


def test_is_status_editable_matrix():
    assert is_status_editable("contract_version", "draft")
    assert is_status_editable("contract_version", "rejected")
    assert not is_status_editable("contract_version", "submitted")
    assert not is_status_editable("contract_version", "approved")
    assert is_status_editable("form_instance", "draft")
    assert not is_status_editable("form_instance", "completed")
    assert is_status_editable("solution", "draft")
    assert not is_status_editable("solution", "reviewing")
    assert not is_status_editable("service_ticket", "submitted")
    assert is_status_editable("service_ticket", "open")


@pytest.mark.asyncio
async def test_assert_biz_editable_allows_draft():
    db = MagicMock()
    with patch(
        "app.domains.lowcode.edit_lock.has_running_process",
        new_callable=AsyncMock,
        return_value=False,
    ):
        await assert_biz_editable(db, "t1", "contract_version", "v1", "draft")
        await assert_biz_editable(db, "t1", "contract_version", "v1", "rejected")


@pytest.mark.asyncio
async def test_assert_biz_editable_rejects_submitted():
    db = MagicMock()
    with patch(
        "app.domains.lowcode.edit_lock.has_running_process",
        new_callable=AsyncMock,
        return_value=False,
    ):
        with pytest.raises(BusinessException) as ei:
            await assert_biz_editable(db, "t1", "contract_version", "v1", "submitted")
        assert "不可编辑" in ei.value.message


@pytest.mark.asyncio
async def test_assert_biz_editable_rejects_running():
    db = MagicMock()
    with patch(
        "app.domains.lowcode.edit_lock.has_running_process",
        new_callable=AsyncMock,
        return_value=True,
    ):
        with pytest.raises(BusinessException):
            await assert_biz_editable(db, "t1", "contract_version", "v1", "draft")


@pytest.mark.asyncio
async def test_assert_content_update_allowed_submit_from_draft():
    db = MagicMock()
    with patch(
        "app.domains.lowcode.edit_lock.has_running_process",
        new_callable=AsyncMock,
        return_value=False,
    ):
        await assert_content_update_allowed(
            db, "t1", "contract_version", "v1", "draft", {"status": "submitted"})
        with pytest.raises(BusinessException):
            await assert_content_update_allowed(
                db, "t1", "contract_version", "v1", "submitted",
                {"key_clauses_json": []},
            )


@pytest.mark.asyncio
async def test_assert_contract_signed_locked():
    db = MagicMock()
    contract = MagicMock(status="signed", id="c1", current_version_no=1)
    with pytest.raises(BusinessException) as ei:
        await assert_contract_record_editable(db, "t1", contract)
    assert "签署" in ei.value.message or "终止" in ei.value.message


@pytest.mark.asyncio
async def test_assert_lead_pending_without_running_ok():
    db = MagicMock()
    with patch(
        "app.domains.lowcode.edit_lock.has_running_process",
        new_callable=AsyncMock,
        return_value=False,
    ):
        await assert_lead_editable(db, "t1", "l1", "pending")
        await assert_lead_editable(db, "t1", "l1", "draft")


@pytest.mark.asyncio
async def test_assert_lead_rejected_locked():
    db = MagicMock()
    with patch(
        "app.domains.lowcode.edit_lock.has_running_process",
        new_callable=AsyncMock,
        return_value=False,
    ):
        with pytest.raises(BusinessException) as ei:
            await assert_lead_editable(db, "t1", "l1", "rejected")
        assert "驳回" in ei.value.message


@pytest.mark.asyncio
async def test_assert_lead_approved_locked():
    """收录后整单不可编辑（详情动态添加记录不经本闸门）。"""
    db = MagicMock()
    with patch(
        "app.domains.lowcode.edit_lock.has_running_process",
        new_callable=AsyncMock,
        return_value=False,
    ):
        with pytest.raises(BusinessException) as ei:
            await assert_lead_editable(db, "t1", "l1", "approved")
        assert "收录" in ei.value.message
        assert "不可再编辑" in ei.value.message


@pytest.mark.asyncio
async def test_assert_lead_attacked_locked():
    db = MagicMock()
    with patch(
        "app.domains.lowcode.edit_lock.has_running_process",
        new_callable=AsyncMock,
        return_value=False,
    ):
        with pytest.raises(BusinessException) as ei:
            await assert_lead_editable(db, "t1", "l1", "attacked")
        assert "袭击" in ei.value.message


@pytest.mark.asyncio
async def test_assert_lead_pending_with_running_locked():
    db = MagicMock()
    with patch(
        "app.domains.lowcode.edit_lock.has_running_process",
        new_callable=AsyncMock,
        return_value=True,
    ):
        with pytest.raises(BusinessException):
            await assert_lead_editable(db, "t1", "l1", "pending")


@pytest.mark.asyncio
async def test_assert_form_instance_editable_status():
    db = MagicMock()
    with patch(
        "app.domains.lowcode.edit_lock.has_running_process",
        new_callable=AsyncMock,
        return_value=False,
    ):
        # form_instance_id 二次查询：无 running
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=exec_result)
        await assert_form_instance_editable(db, "t1", "fi1", "draft")
        with pytest.raises(BusinessException):
            await assert_form_instance_editable(db, "t1", "fi1", "submitted")
