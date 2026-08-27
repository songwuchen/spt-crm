"""技术协议评审 — 数据日志 diff / 审批写回预览。"""
import pytest

from app.domains.lowcode.wf_field_writeback import preview_field_update_changes
from tests.lead_intel_helpers import DEMO_TENANT


@pytest.mark.asyncio
async def test_preview_tech_agreement_review_field_changes(db):
    from app.domains.tech_agreement_review.models import TechAgreementReview
    from app.database import generate_uuid

    row = TechAgreementReview(
        id=generate_uuid(),
        tenant_id=DEMO_TENANT,
        review_code="HTJSXY-TEST-001",
        status="submitted",
        has_objection="否",
        form_json={"design_approver_ids": ["u-old"]},
    )
    db.add(row)
    await db.flush()

    changes = await preview_field_update_changes(
        db, DEMO_TENANT,
        biz_type="tech_agreement_review",
        biz_id=row.id,
        form_instance_id=None,
        updates={
            "has_objection": "是",
            "design_approver_ids": ["u-new"],
        },
    )
    assert changes.get("has_objection") == {"old": "否", "new": "是"}
    assert changes.get("form_json.design_approver_ids") == {
        "old": ["u-old"],
        "new": ["u-new"],
    }
