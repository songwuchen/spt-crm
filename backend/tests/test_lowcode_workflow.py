"""扩展平台工作流引擎 + 线索审核切换 的回归测试。

这个文件存在的直接原因：线索(lead)曾经是唯一一个「新引擎侧全部配好、前端可选、
但提交路径从未调用新引擎」的业务实体 —— 灰度接线那次提交漏改了 lead/service.py，
而当时 wf 引擎没有任何测试，所以漏接线一直没被发现。下面第一个用例就是钉住这一点。
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings
from app.database import generate_uuid

DEMO_TENANT = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
async def db():
    engine = create_async_engine(settings.DATABASE_URL, echo=False, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _create_lead(client: AsyncClient, headers: dict, title: str) -> str:
    resp = await client.post("/api/v1/leads", headers=headers, json={
        "title": title, "company_name": f"{title}-公司",
    })
    data = resp.json()
    assert data["code"] == 0, data
    return data["data"]["id"]


# ---------- 接线守卫 ----------

@pytest.mark.asyncio
async def test_lead_submit_goes_through_workflow_engine(client: AsyncClient, auth_headers, db):
    """线索提交必须落到新引擎的 wf_process_instance，而不是旧的 approval_flows。

    这是防止「灰度接线漏掉某个业务实体」重演的守卫用例。
    """
    from app.domains.lowcode.workflow_models import WfProcessInstance

    lead_id = await _create_lead(client, auth_headers, "接线守卫-线索")

    inst = (await db.execute(select(WfProcessInstance).where(
        WfProcessInstance.tenant_id == DEMO_TENANT,
        WfProcessInstance.biz_type == "lead",
        WfProcessInstance.biz_id == lead_id,
    ))).scalar_one_or_none()
    assert inst is not None, "线索审核没有走新工作流引擎（wf_process_instance 无记录）"

    # 同时确认没有再往旧引擎写 lead 审批流
    old = (await db.execute(text(
        "SELECT id FROM approval_flows WHERE tenant_id = :t AND biz_type = 'lead' AND biz_id = :b"
    ), {"t": DEMO_TENANT, "b": lead_id})).first()
    assert old is None, "线索仍在旧 approval 引擎创建审批流"


@pytest.mark.asyncio
async def test_default_lead_flow_is_provisioned_and_published(client: AsyncClient, auth_headers, db):
    """未配置可视化流程时，系统兜底流程应被自动创建并发布，且审批人规则是 lead_intel。"""
    from app.domains.lowcode.workflow_models import WfProcessDefinition, WfProcessDefinitionVersion
    from app.domains.lead.service import LEAD_DEFAULT_FLOW_CODE

    await _create_lead(client, auth_headers, "兜底流程-线索")

    d = (await db.execute(select(WfProcessDefinition).where(
        WfProcessDefinition.tenant_id == DEMO_TENANT,
        WfProcessDefinition.code == LEAD_DEFAULT_FLOW_CODE,
    ))).scalar_one_or_none()
    assert d is not None and d.status == "published"
    assert d.biz_type == "lead"

    v = (await db.execute(select(WfProcessDefinitionVersion).where(
        WfProcessDefinitionVersion.process_definition_id == d.id,
        WfProcessDefinitionVersion.status == "published",
    ))).scalars().first()
    assert v is not None
    approval = [n for n in v.node_definitions if n.get("type") == "approval"]
    assert len(approval) == 1
    rule = approval[0]["approver_rule"]
    assert rule["type"] == "specified_role" and rule["value"] == "lead_intel"
    # 排除提交人本人，保持与旧实现一致（旧实现 exclude_user_id=提交人）
    assert rule.get("exclude_initiator") is True
    # 无审批人时自动通过，避免线索卡在 pending 无法转化
    assert approval[0]["empty_strategy"] == "auto_approve"


# ---------- 降级语义 ----------

@pytest.mark.asyncio
async def test_lead_auto_approved_when_no_reviewer(client: AsyncClient, auth_headers, db):
    """没有 lead_intel 成员时，引擎按 empty_strategy 自动放行，线索可继续转化。

    等价于旧实现的「无审核人 → 免审通过」。测试库是共享的（其它用例会造内勤用户），
    所以这里显式把 lead_intel 成员全部停用来构造前置条件，用完恢复。
    """
    from app.domains.auth.models import User, UserRole, Role
    from app.domains.lead.models import Lead

    members = (await db.execute(
        select(User).join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(User.tenant_id == DEMO_TENANT, Role.code == "lead_intel", User.is_active == True)  # noqa: E712
    )).scalars().all()
    restore = [u.id for u in members]
    for u in members:
        u.is_active = False
    await db.commit()

    try:
        lead_id = await _create_lead(client, auth_headers, "无审核人-线索")
        lead = (await db.execute(select(Lead).where(Lead.id == lead_id))).scalar_one()
        assert lead.review_status == "approved", (
            f"无审批人时应免审通过，实际 review_status={lead.review_status}（线索会卡死无法转化）"
        )
    finally:
        if restore:
            await db.execute(text("UPDATE users SET is_active = true WHERE id = ANY(:ids)"),
                             {"ids": restore})
            await db.commit()


# ---------- 有审批人时的完整闭环 ----------

@pytest.fixture
async def lead_intel_user(db):
    """造一个 lead_intel 角色的活跃用户，用完彻底清理。

    测试库是共享的且不做隔离（见 conftest：直连 DATABASE_URL），若把这个用户留在库里，
    之后所有新建线索都会变成待审核 —— test_lead.py 的 qualify 用例就会因「线索尚未通过
    审核」而失败。所以这里必须自己收尾。
    """
    from app.domains.auth.models import User, UserRole, Role

    role = (await db.execute(select(Role).where(
        Role.tenant_id == DEMO_TENANT, Role.code == "lead_intel",
    ))).scalar_one_or_none()
    created_role = False
    if role is None:
        role = Role(id=generate_uuid(), tenant_id=DEMO_TENANT, code="lead_intel", name="信息情报部内勤")
        db.add(role)
        await db.flush()
        created_role = True

    u = User(id=generate_uuid(), tenant_id=DEMO_TENANT, username=f"wf_test_intel_{generate_uuid()[:8]}",
             real_name="测试内勤", password_hash="x", is_active=True)
    db.add(u)
    await db.flush()
    db.add(UserRole(id=generate_uuid(), tenant_id=DEMO_TENANT, user_id=u.id, role_id=role.id))
    await db.commit()

    yield u.id

    await db.execute(text("DELETE FROM user_roles WHERE user_id = :uid"), {"uid": u.id})
    await db.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": u.id})
    if created_role:
        await db.execute(text("DELETE FROM roles WHERE id = :rid"), {"rid": role.id})
    await db.commit()


@pytest.mark.asyncio
async def test_lead_review_pending_then_reject_writes_reason(client: AsyncClient, auth_headers, db, lead_intel_user):
    """有审核人时线索进入待审；驳回后 review_status=rejected 且驳回原因回写到线索。

    reject_reason 的回写是切换到新引擎时最容易丢的一环（旧引擎在
    _on_approval_rejected 里写，新引擎的 writeback 起初只写 review_status）。
    """
    from app.domains.lead.models import Lead
    from app.domains.lowcode.workflow_models import WfProcessInstance, WfTaskInstance
    from app.domains.lowcode.workflow_engine import WorkflowEngine

    reviewer_id = lead_intel_user
    lead_id = await _create_lead(client, auth_headers, "待审-线索")

    lead = (await db.execute(select(Lead).where(Lead.id == lead_id))).scalar_one()
    assert lead.review_status == "pending"

    inst = (await db.execute(select(WfProcessInstance).where(
        WfProcessInstance.biz_type == "lead", WfProcessInstance.biz_id == lead_id,
    ))).scalar_one()
    assert inst.status == "running"

    task = (await db.execute(select(WfTaskInstance).where(
        WfTaskInstance.process_instance_id == inst.id,
        WfTaskInstance.status == "pending",
    ))).scalars().first()
    assert task is not None and task.assignee_id == reviewer_id

    await WorkflowEngine(db, DEMO_TENANT).act(
        task.id, {"sub": reviewer_id, "real_name": "测试内勤"}, "reject", opinion="资料不全",
    )

    await db.refresh(lead)
    assert lead.review_status == "rejected"
    assert lead.reject_reason == "资料不全", "驳回原因未回写到线索"


@pytest.mark.asyncio
async def test_lead_approve_clears_previous_reject_reason(client: AsyncClient, auth_headers, db, lead_intel_user):
    """通过时要清空上一次的驳回原因，否则详情页会一直显示旧的驳回理由。"""
    from app.domains.lead.models import Lead
    from app.domains.lowcode.workflow_models import WfProcessInstance, WfTaskInstance
    from app.domains.lowcode.workflow_engine import WorkflowEngine

    reviewer_id = lead_intel_user
    lead_id = await _create_lead(client, auth_headers, "通过-线索")

    lead = (await db.execute(select(Lead).where(Lead.id == lead_id))).scalar_one()
    lead.reject_reason = "上一轮的驳回原因"
    await db.commit()

    inst = (await db.execute(select(WfProcessInstance).where(
        WfProcessInstance.biz_type == "lead", WfProcessInstance.biz_id == lead_id,
    ))).scalar_one()
    task = (await db.execute(select(WfTaskInstance).where(
        WfTaskInstance.process_instance_id == inst.id, WfTaskInstance.status == "pending",
    ))).scalars().first()

    await WorkflowEngine(db, DEMO_TENANT).act(
        task.id, {"sub": reviewer_id, "real_name": "测试内勤"}, "approve", opinion="ok",
    )

    await db.refresh(lead)
    assert lead.review_status == "approved"
    assert lead.reject_reason is None, "通过后仍残留旧的驳回原因"


@pytest.mark.asyncio
async def test_deleted_default_flow_is_revived_not_silently_bypassed(
    client: AsyncClient, auth_headers, db,
):
    """兜底流程被软删/取消发布后必须自动恢复，绝不能变成「线索永久免审」。

    唯一索引 (tenant_id, code) 不区分软删，所以直接重建会撞唯一键；早期实现会因此
    拿到那条已删除的定义、start_for_biz 返回 None，从而把每条线索都静默放行。
    """
    from app.domains.lowcode.workflow_models import WfProcessDefinition, WfProcessInstance
    from app.domains.lead.service import LEAD_DEFAULT_FLOW_CODE

    # 先触发一次，确保兜底流程已存在
    await _create_lead(client, auth_headers, "恢复前-线索")
    d = (await db.execute(select(WfProcessDefinition).where(
        WfProcessDefinition.tenant_id == DEMO_TENANT,
        WfProcessDefinition.code == LEAD_DEFAULT_FLOW_CODE,
    ))).scalar_one()

    # 模拟管理员删掉它
    d.is_deleted = True
    d.status = "draft"
    await db.commit()

    lead_id = await _create_lead(client, auth_headers, "恢复后-线索")

    await db.refresh(d)
    assert d.is_deleted is False and d.status == "published", "兜底流程未被恢复"
    inst = (await db.execute(select(WfProcessInstance).where(
        WfProcessInstance.biz_type == "lead", WfProcessInstance.biz_id == lead_id,
    ))).scalar_one_or_none()
    assert inst is not None, "流程被删后线索直接免审放行了（审核门禁被静默绕过）"


# ---------- 通知层 ----------

@pytest.mark.asyncio
async def test_notifies_reviewer_on_submit_and_initiator_on_reject(
    client: AsyncClient, auth_headers, db, lead_intel_user,
):
    """新引擎必须发站内通知：提交时通知审批人、驳回时通知发起人。

    新引擎此前只在催办和 SLA 超时两处发通知，任务创建/流转/结束全程静默 —— 业务一旦
    切过来，审批人不会收到任何推送。这个用例钉住补齐后的行为。
    """
    from app.domains.notification.models import Notification
    from app.domains.lowcode.workflow_models import WfProcessInstance, WfTaskInstance
    from app.domains.lowcode.workflow_engine import WorkflowEngine

    lead_id = await _create_lead(client, auth_headers, "通知-线索")
    inst = (await db.execute(select(WfProcessInstance).where(
        WfProcessInstance.biz_type == "lead", WfProcessInstance.biz_id == lead_id,
    ))).scalar_one()

    # 提交 → 审批人收到 approval_pending
    notes = (await db.execute(select(Notification).where(
        Notification.tenant_id == DEMO_TENANT,
        Notification.recipient_id == lead_intel_user,
        Notification.biz_type == "wf_instance",
        Notification.biz_id == inst.id,
    ))).scalars().all()
    assert any(n.type == "approval_pending" for n in notes), "审批人没有收到待办通知"

    task = (await db.execute(select(WfTaskInstance).where(
        WfTaskInstance.process_instance_id == inst.id, WfTaskInstance.status == "pending",
    ))).scalars().first()
    await WorkflowEngine(db, DEMO_TENANT).act(
        task.id, {"sub": lead_intel_user, "real_name": "测试内勤"}, "reject", opinion="不合格",
    )

    # 驳回 → 发起人收到 approval_decided
    done = (await db.execute(select(Notification).where(
        Notification.tenant_id == DEMO_TENANT,
        Notification.recipient_id == inst.initiator_id,
        Notification.biz_type == "wf_instance",
        Notification.biz_id == inst.id,
        Notification.type == "approval_decided",
    ))).scalars().all()
    assert done, "驳回后发起人没有收到结果通知"


# ---------- 审批人解析 ----------

@pytest.mark.asyncio
async def test_resolver_excludes_initiator_when_flagged(db, lead_intel_user):
    """exclude_initiator=True 时提交人不应出现在审批人里（避免自己审自己）。"""
    from app.domains.lowcode.approver_resolver import ApproverResolver, ApprovalContext

    reviewer_id = lead_intel_user
    resolver = ApproverResolver(db, DEMO_TENANT)
    rule = {"type": "specified_role", "value": "lead_intel", "exclude_initiator": True}

    ids = await resolver.resolve(rule, ApprovalContext(initiator_id=reviewer_id, form_data={}, nominated={}))
    assert reviewer_id not in ids

    # 不开开关时保持原行为
    resolver2 = ApproverResolver(db, DEMO_TENANT)
    ids2 = await resolver2.resolve(
        {"type": "specified_role", "value": "lead_intel"},
        ApprovalContext(initiator_id=reviewer_id, form_data={}, nominated={}),
    )
    assert reviewer_id in ids2


@pytest.mark.asyncio
async def test_resolver_creator_ignores_exclude_initiator(db, lead_intel_user):
    """creator 类型就是以发起人为审批人，exclude_initiator 不能把它清空。"""
    from app.domains.lowcode.approver_resolver import ApproverResolver, ApprovalContext

    uid = lead_intel_user
    ids = await ApproverResolver(db, DEMO_TENANT).resolve(
        {"type": "creator", "exclude_initiator": True},
        ApprovalContext(initiator_id=uid, form_data={}, nominated={}),
    )
    assert ids == [uid]
