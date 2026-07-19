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


async def test_gate_has_related_status_filter(client):
    """has_related gate can require a related entity with a specific status
    (e.g. S6 requires a *signed* contract), configured via StageDefinition."""
    from app.domains.project.models import OpportunityProject
    from app.domains.contract.models import Contract
    from app.domains.admin.models import StageDefinition
    from app.domains.project.service import check_gate_rules

    async with db_module.async_session_factory() as db:
        pid = generate_uuid()
        cid = generate_uuid()
        # Temporarily override the seeded S6 stage definition's gate rules
        sd = (await db.execute(select(StageDefinition).where(
            StageDefinition.tenant_id == TENANT, StageDefinition.stage_code == "S6",
        ))).scalars().first()
        original_rules = sd.gate_rules_json if sd else None
        original_enabled = sd.enabled if sd else None
        try:
            project = OpportunityProject(
                id=pid, tenant_id=TENANT, project_code="PRJ-GATE-TEST",
                name="闸门状态测试", stage_code="S5", owner_id=ADMIN, owner_name="Admin",
            )
            db.add(project)
            # A draft (not signed) contract
            db.add(Contract(id=cid, tenant_id=TENANT, project_id=pid,
                            contract_no="CT-GATE-TEST", status="draft", amount_total=1000))
            assert sd is not None, "演示租户应已 seed S6 阶段定义"
            sd.enabled = True
            sd.gate_rules_json = [{
                "code": "HAS_SIGNED_CONTRACT", "name": "已签署合同",
                "check": "has_related", "entity": "contract", "status": "signed",
                "message": "请先签署合同，再进入交付验收。",
            }]
            await db.commit()

            # Draft contract -> gate fails
            failed = await check_gate_rules(db, TENANT, project, "S6")
            assert any(f["code"] == "HAS_SIGNED_CONTRACT" for f in failed), "草稿合同应不满足'已签署'闸门"

            # Sign the contract -> gate passes
            c = (await db.execute(select(Contract).where(Contract.id == cid))).scalar_one()
            c.status = "signed"
            await db.commit()
            failed2 = await check_gate_rules(db, TENANT, project, "S6")
            assert not any(f["code"] == "HAS_SIGNED_CONTRACT" for f in failed2), "已签署合同应满足闸门"
        finally:
            await db.execute(delete(Contract).where(Contract.id == cid))
            await db.execute(delete(OpportunityProject).where(OpportunityProject.id == pid))
            if sd is not None:
                sd.gate_rules_json = original_rules
                sd.enabled = original_enabled
            await db.commit()


async def test_solution_review_triggers_approval_and_approve_marks_approved(client):
    from app.domains.admin.models import ApprovalPolicy
    from app.domains.solution.models import Solution, SolutionVersion
    from app.domains.solution.schemas import SolutionCreate, SolutionUpdate
    from app.domains.solution.service import create_solution, update_solution
    from app.domains.approval.models import ApprovalFlow, ApprovalTask
    from app.domains.approval.service import decide
    from app.domains.project.models import OpportunityProject

    user = {"sub": ADMIN, "real_name": "Admin", "username": "admin"}
    async with db_module.async_session_factory() as db:
        pid = generate_uuid()
        policy_id = generate_uuid()
        sid = None
        try:
            # 方案必须挂在真实商机下：create_solution 会校验父商机可见性（数据范围），
            # 用一个凭空生成的 project_id 会直接 404。
            db.add(OpportunityProject(
                id=pid, tenant_id=TENANT, project_code=f"PJ-{pid[:8]}",
                name="方案审批测试商机", stage_code="S1", status="active",
                owner_id=ADMIN, is_deleted=False,
            ))
            await db.commit()
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
            await db.execute(delete(OpportunityProject).where(OpportunityProject.id == pid))
            await db.commit()
