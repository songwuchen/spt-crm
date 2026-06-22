"""Tests for the known-limitation fixes:
- send_notification honors NotificationPreference (opt-out toggle now real)
- Solution review goes through the approval engine; approval marks solution approved
These are service-layer tests against the default session factory.
"""
from sqlalchemy import select, delete

import app.database as db_module
from app.database import generate_uuid

TENANT = "00000000-0000-0000-0000-000000000001"
ADMIN = "00000000-0000-0000-0000-000000000010"

# These are service-layer tests. They take the `client` fixture purely so app.main
# is imported (registers every ORM mapper) and the test engine is configured; we then
# use the fixture-configured session factory directly.


async def test_notification_preference_suppresses_disabled_type(client):
    from app.domains.notification.models import Notification, NotificationPreference
    from app.domains.notification.service import send_notification

    async with db_module.async_session_factory() as db:
        uid = generate_uuid()
        try:
            # No preference row -> sent
            assert await send_notification(db, TENANT, uid, "payment_overdue", "before") is not None
            # Disable payment_overdue for this user
            db.add(NotificationPreference(
                id=generate_uuid(), tenant_id=TENANT, user_id=uid,
                preferences_json={"payment_overdue": False},
            ))
            await db.commit()
            # Disabled type -> suppressed (returns None, no row)
            assert await send_notification(db, TENANT, uid, "payment_overdue", "blocked") is None
            # A different type is unaffected
            assert await send_notification(db, TENANT, uid, "system", "other") is not None

            rows = (await db.execute(
                select(Notification).where(Notification.recipient_id == uid)
            )).scalars().all()
            assert {r.title for r in rows} == {"before", "other"}
        finally:
            await db.execute(delete(Notification).where(Notification.recipient_id == uid))
            await db.execute(delete(NotificationPreference).where(NotificationPreference.user_id == uid))
            await db.commit()


async def test_solution_review_triggers_approval_and_approve_marks_approved(client):
    from app.domains.admin.models import ApprovalPolicy
    from app.domains.solution.models import Solution, SolutionVersion
    from app.domains.solution.schemas import SolutionCreate, SolutionUpdate
    from app.domains.solution.service import create_solution, update_solution
    from app.domains.approval.models import ApprovalFlow, ApprovalTask
    from app.domains.approval.service import decide

    user = {"sub": ADMIN, "real_name": "Admin", "username": "admin"}
    async with db_module.async_session_factory() as db:
        pid = generate_uuid()
        policy_id = generate_uuid()
        sid = None
        try:
            # Policy: any solution submitted for review -> approved by the admin user
            db.add(ApprovalPolicy(
                id=policy_id, tenant_id=TENANT, biz_type="solution", name="方案审批",
                approver_rules_json=[{"type": "user", "value": ADMIN}],
                approval_mode="sequential", enabled=True,
            ))
            await db.commit()

            res = await create_solution(db, TENANT, pid, SolutionCreate(title="V1"), user)
            sid = res["solution"].id

            # Submit for review -> should auto-create an approval flow + pending task
            await update_solution(db, TENANT, sid, SolutionUpdate(status="reviewing"), user)
            flow = (await db.execute(select(ApprovalFlow).where(
                ApprovalFlow.tenant_id == TENANT,
                ApprovalFlow.biz_type == "solution",
                ApprovalFlow.biz_id == sid,
            ))).scalar_one_or_none()
            assert flow is not None, "提交评审应自动发起方案审批流"
            task = (await db.execute(select(ApprovalTask).where(
                ApprovalTask.flow_id == flow.id, ApprovalTask.status == "pending",
            ))).scalar_one_or_none()
            assert task is not None

            # Approve -> _on_approval_completed should mark the Solution approved (满足 S4 闸门)
            await decide(db, TENANT, task.id, "approved", "ok", user)
            sol = (await db.execute(select(Solution).where(Solution.id == sid))).scalar_one()
            assert sol.status == "approved", f"审批通过后方案应为 approved, 实际 {sol.status}"
        finally:
            if sid:
                fl = (await db.execute(select(ApprovalFlow).where(ApprovalFlow.biz_id == sid))).scalars().all()
                for f in fl:
                    await db.execute(delete(ApprovalTask).where(ApprovalTask.flow_id == f.id))
                    await db.delete(f)
                await db.execute(delete(SolutionVersion).where(SolutionVersion.solution_id == sid))
                await db.execute(delete(Solution).where(Solution.id == sid))
            await db.execute(delete(ApprovalPolicy).where(ApprovalPolicy.id == policy_id))
            await db.commit()
