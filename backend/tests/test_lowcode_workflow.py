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
    assert len(approval) == 2, "情报审批 + 业务员确认是否转商机"
    intel = next(n for n in approval if (n.get("approver_rule") or {}).get("value") == "lead_intel")
    confirm = next(n for n in approval if n.get("id") == "approval_owner_confirm"
                   or "转商机" in (n.get("name") or ""))
    rule = intel["approver_rule"]
    assert rule["type"] == "specified_role" and rule["value"] == "lead_intel"
    # 排除提交人本人，保持与旧实现一致（旧实现 exclude_user_id=提交人）
    assert rule.get("exclude_initiator") is True
    # 无审批人时自动通过，避免线索卡在 pending 无法转化
    assert intel["empty_strategy"] == "auto_approve"
    assert confirm["type"] == "approval"
    assert (confirm.get("approver_rule") or {}).get("type") == "form_field_person"


@pytest.mark.asyncio
async def test_list_definitions_seeds_contract_default_flows(client: AsyncClient, auth_headers, db):
    """打开流程管理列表应幂等补齐合同版本/合同评审默认流，无需等业务首次提交。"""
    from app.domains.lowcode.workflow_models import WfProcessDefinition, WfProcessDefinitionVersion

    resp = await client.get("/api/v1/lc/wf/definitions", headers=auth_headers, params={"pageNo": 1, "pageSize": 50})
    assert resp.json()["code"] == 0, resp.json()
    items = resp.json()["data"]["items"]
    by_code = {i["code"]: i for i in items}
    assert "SYS_CONTRACT_VERSION_APPROVAL" in by_code
    assert by_code["SYS_CONTRACT_VERSION_APPROVAL"]["biz_type"] == "contract_version"
    assert by_code["SYS_CONTRACT_VERSION_APPROVAL"]["status"] == "published"
    assert "SYS_CONTRACT_REVIEW_APPROVAL" in by_code
    assert by_code["SYS_CONTRACT_REVIEW_APPROVAL"]["biz_type"] == "contract_review"
    assert by_code["SYS_CONTRACT_REVIEW_APPROVAL"]["status"] == "published"

    # DB 侧确认 category=system_default
    for code in ("SYS_CONTRACT_VERSION_APPROVAL", "SYS_CONTRACT_REVIEW_APPROVAL"):
        d = (await db.execute(select(WfProcessDefinition).where(
            WfProcessDefinition.tenant_id == DEMO_TENANT,
            WfProcessDefinition.code == code,
        ))).scalar_one_or_none()
        assert d is not None and d.category == "system_default"

    # 合同版本：简道云登记运营图（财务 + merge_ops + 标准交付条件）
    cv = (await db.execute(select(WfProcessDefinition).where(
        WfProcessDefinition.tenant_id == DEMO_TENANT,
        WfProcessDefinition.code == "SYS_CONTRACT_VERSION_APPROVAL",
    ))).scalar_one()
    ver = (await db.execute(select(WfProcessDefinitionVersion).where(
        WfProcessDefinitionVersion.process_definition_id == cv.id,
        WfProcessDefinitionVersion.status == "published",
    ).order_by(WfProcessDefinitionVersion.version_number.desc()))).scalars().first()
    assert ver is not None
    ids = {n.get("id") for n in (ver.node_definitions or [])}
    assert "approval_finance" in ids and "merge_ops" in ids
    assert "approval_production" in ids and "approval_procurement" in ids
    cond_routes = [r for r in (ver.route_definitions or []) if r.get("condition")]
    assert any(
        any(c.get("field") == "standard_delivery" for c in (r.get("condition") or {}).get("cond", []))
        for r in cond_routes
    )

    # 合同评审：会签汇聚 + 总经理/财务意见 + 法务可填风险
    cr = (await db.execute(select(WfProcessDefinition).where(
        WfProcessDefinition.tenant_id == DEMO_TENANT,
        WfProcessDefinition.code == "SYS_CONTRACT_REVIEW_APPROVAL",
    ))).scalar_one()
    cr_ver = (await db.execute(select(WfProcessDefinitionVersion).where(
        WfProcessDefinitionVersion.process_definition_id == cr.id,
        WfProcessDefinitionVersion.status == "published",
    ).order_by(WfProcessDefinitionVersion.version_number.desc()))).scalars().first()
    assert cr_ver is not None
    cr_by_id = {n.get("id"): n for n in (cr_ver.node_definitions or [])}
    assert "merge_review" in cr_by_id and "approval_gm" in cr_by_id
    assert "approval_biz" in cr_by_id and "approval_legal" in cr_by_id
    assert "approval_legal_sup" in cr_by_id
    assert "approval_region" in cr_by_id and "approval_info_feedback" in cr_by_id
    assert "approval_design_fb" in cr_by_id and "approval_initiator" in cr_by_id
    for cid in ("cc_owner", "cc_install", "cc_related", "cc_lili", "cc_xunhan"):
        assert cid in cr_by_id
    legal_fp = cr_by_id["approval_legal"].get("field_perms") or []
    assert any(p.get("field") == "legal_risk" for p in legal_fp)
    assert cr_by_id["approval_gm"].get("opinion_required") is True
    # 法务 → 法务主管 → 汇聚；财务意见 → 信息反馈；发起旁路抄送
    routes = cr_ver.route_definitions or []
    assert any(r.get("source") == "approval_legal" and r.get("target") == "approval_legal_sup" for r in routes)
    assert any(
        r.get("source") == "approval_finance_opinion" and r.get("target") == "approval_info_feedback"
        for r in routes
    )
    assert any(
        r.get("source") == "approval_design_fb" and r.get("target") == "approval_gm"
        for r in routes
    )
    assert any(r.get("source") == "start" and r.get("target") == "cc_owner" and r.get("always") for r in routes)


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
        allow_lead_intel=True,
    )

    await db.refresh(lead)
    assert lead.review_status == "rejected"
    assert lead.reject_reason == "资料不全", "驳回原因未回写到线索"

    # 驳回后节点实例必须结束，否则流程动态会一直显示「处理中」
    from app.domains.lowcode.workflow_models import WfNodeInstance
    from app.domains.lowcode import workflow_service as wf_svc
    await db.refresh(inst)
    assert inst.status == "rejected"
    running_nodes = (await db.execute(select(WfNodeInstance).where(
        WfNodeInstance.process_instance_id == inst.id,
        WfNodeInstance.status == "running",
    ))).scalars().all()
    assert running_nodes == [], "驳回后不应残留 running 节点"
    rejected_nodes = (await db.execute(select(WfNodeInstance).where(
        WfNodeInstance.process_instance_id == inst.id,
        WfNodeInstance.status == "rejected",
    ))).scalars().all()
    assert rejected_nodes, "驳回节点应标记为 rejected"
    detail = await wf_svc.get_instance_detail(db, DEMO_TENANT, inst.id)
    current_steps = [s for s in detail["flow_steps"] if s.get("is_current")]
    assert current_steps == [], "驳回后流程动态不应有「处理中」节点"
    assert any(s["status"] == "rejected" and s["status_text"] == "已驳回" for s in detail["flow_steps"])


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

    # 情报节点 field_perms 要求 customer_newness；裸 approve 仅测试允许时也须带齐必填写回
    await WorkflowEngine(db, DEMO_TENANT).act(
        task.id, {"sub": reviewer_id, "real_name": "测试内勤"}, "approve", opinion="ok",
        field_updates={"customer_newness": "new"},
        allow_lead_intel=True,
    )

    await db.refresh(lead)
    assert lead.review_status == "approved"
    assert lead.reject_reason is None, "通过后仍残留旧的驳回原因"
    assert lead.customer_newness == "new"


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
        allow_lead_intel=True,
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


# ---------- 情报审批：收录 / 袭击 / 回退 / 暂存 ----------

async def _create_pending_lead(db, title: str, initiator: dict) -> str:
    from app.domains.lead.schemas import LeadCreate
    from app.domains.lead import service as lead_svc
    lead = await lead_svc.create_lead(
        db, DEMO_TENANT,
        LeadCreate(title=title, company_name=f"{title}-公司"),
        initiator,
    )
    assert lead.review_status == "pending", f"expected pending, got {lead.review_status}"
    return lead.id


async def _pending_task_for_lead(db, lead_id: str, assignee_id: str | None = None):
    from app.domains.lowcode.workflow_models import WfProcessInstance, WfTaskInstance
    inst = (await db.execute(select(WfProcessInstance).where(
        WfProcessInstance.biz_type == "lead", WfProcessInstance.biz_id == lead_id,
    ))).scalar_one()
    q = select(WfTaskInstance).where(
        WfTaskInstance.process_instance_id == inst.id, WfTaskInstance.status == "pending",
    )
    if assignee_id:
        q = q.where(WfTaskInstance.assignee_id == assignee_id)
    task = (await db.execute(q)).scalars().first()
    assert task is not None, f"no pending task for lead={lead_id} assignee={assignee_id}"
    return task


async def _admin_user(db) -> dict:
    from app.domains.auth.models import User
    u = (await db.execute(select(User).where(
        User.tenant_id == DEMO_TENANT, User.username == "admin", User.is_active == True,  # noqa: E712
    ))).scalar_one_or_none()
    assert u is not None, "测试库缺少 admin 用户"
    return {"sub": u.id, "real_name": u.real_name or "admin", "username": u.username}


@pytest.mark.asyncio
async def test_intel_include_allows_qualify(client, db, lead_intel_user):
    """收录 → review_status=approved，可转化。"""
    from app.domains.lead import service as lead_svc

    _ = client  # 加载 app.main，确保 ORM relationship 全部注册
    initiator = await _admin_user(db)
    reviewer_id = lead_intel_user
    lead_id = await _create_pending_lead(db, "情报-收录", initiator)
    task = await _pending_task_for_lead(db, lead_id, reviewer_id)

    lead = await lead_svc.intel_review_lead(
        db, DEMO_TENANT, lead_id,
        {"sub": reviewer_id, "real_name": "测试内勤", "username": "intel"},
        decision="include", task_id=task.id, customer_newness="new", opinion="可跟进",
    )
    assert lead.review_status == "approved"
    assert lead.customer_newness == "new"
    assert lead.review_opinion == "可跟进"

    result = await lead_svc.qualify_lead(
        db, DEMO_TENANT, lead_id,
        {"sub": reviewer_id, "real_name": "测试内勤", "username": "intel"},
    )
    assert result["customer_id"]


@pytest.mark.asyncio
async def test_intel_attack_blocks_qualify(client, db, lead_intel_user):
    """袭击 → review_status=attacked，不可转化。"""
    from app.domains.lead import service as lead_svc
    from app.common.exceptions import BusinessException

    _ = client
    initiator = await _admin_user(db)
    reviewer_id = lead_intel_user
    lead_id = await _create_pending_lead(db, "情报-袭击", initiator)
    task = await _pending_task_for_lead(db, lead_id, reviewer_id)

    lead = await lead_svc.intel_review_lead(
        db, DEMO_TENANT, lead_id,
        {"sub": reviewer_id, "real_name": "测试内勤", "username": "intel"},
        decision="attack", task_id=task.id, customer_newness="old",
    )
    assert lead.review_status == "attacked"
    assert lead.customer_newness == "old"

    with pytest.raises(BusinessException) as ei:
        await lead_svc.qualify_lead(
            db, DEMO_TENANT, lead_id,
            {"sub": reviewer_id, "real_name": "测试内勤", "username": "intel"},
        )
    assert "袭击" in ei.value.message


@pytest.mark.asyncio
async def test_intel_return_writes_reason(client, db, lead_intel_user):
    """回退 → rejected + reject_reason，且不可再提交审核。"""
    from app.domains.lead import service as lead_svc
    from app.common.exceptions import BusinessException

    _ = client
    initiator = await _admin_user(db)
    reviewer_id = lead_intel_user
    lead_id = await _create_pending_lead(db, "情报-回退", initiator)
    task = await _pending_task_for_lead(db, lead_id, reviewer_id)

    lead = await lead_svc.intel_review_lead(
        db, DEMO_TENANT, lead_id,
        {"sub": reviewer_id, "real_name": "测试内勤", "username": "intel"},
        decision="return", task_id=task.id, customer_newness="new",
        return_reason="资料不全", opinion="请补充",
    )
    assert lead.review_status == "rejected"
    assert lead.reject_reason == "资料不全"

    with pytest.raises(BusinessException) as ei:
        await lead_svc.resubmit_lead_review(
            db, DEMO_TENANT, lead_id,
            {"sub": initiator["sub"], "real_name": "发起人", "username": "u", "roles": ["admin"]},
        )
    assert "驳回" in ei.value.message

    with pytest.raises(BusinessException) as ei2:
        await lead_svc.qualify_lead(
            db, DEMO_TENANT, lead_id,
            {"sub": initiator["sub"], "real_name": "发起人", "username": "u"},
        )
    assert "驳回" in ei2.value.message


@pytest.mark.asyncio
async def test_intel_draft_keeps_pending(client, db, lead_intel_user):
    """暂存不结束任务，字段落库，review_status 仍 pending。"""
    from app.domains.lead import service as lead_svc

    _ = client
    initiator = await _admin_user(db)
    reviewer_id = lead_intel_user
    lead_id = await _create_pending_lead(db, "情报-暂存", initiator)
    task = await _pending_task_for_lead(db, lead_id, reviewer_id)

    lead = await lead_svc.intel_review_lead(
        db, DEMO_TENANT, lead_id,
        {"sub": reviewer_id, "real_name": "测试内勤", "username": "intel"},
        decision="draft", task_id=task.id, customer_newness="old", opinion="先记一下",
    )
    assert lead.review_status == "pending"
    assert lead.customer_newness == "old"
    assert lead.review_opinion == "先记一下"

    await db.refresh(task)
    assert task.status == "pending"
    lead2 = await lead_svc.intel_review_lead(
        db, DEMO_TENANT, lead_id,
        {"sub": reviewer_id, "real_name": "测试内勤", "username": "intel"},
        decision="include", task_id=task.id, customer_newness="old",
    )
    assert lead2.review_status == "approved"


@pytest.mark.asyncio
async def test_lead_bare_approve_rejected(client, db, lead_intel_user):
    """审批中心裸通过线索必须被引擎拒绝，须走情报裁定。"""
    from app.domains.lowcode.workflow_engine import WorkflowEngine
    from app.common.exceptions import BusinessException

    _ = client
    initiator = await _admin_user(db)
    reviewer_id = lead_intel_user
    lead_id = await _create_pending_lead(db, "裸通过拦截", initiator)
    task = await _pending_task_for_lead(db, lead_id, reviewer_id)

    with pytest.raises(BusinessException) as ei:
        await WorkflowEngine(db, DEMO_TENANT).act(
            task.id, {"sub": reviewer_id, "real_name": "测试内勤"}, "approve", opinion="ok",
        )
    assert "情报审批" in ei.value.message

    with pytest.raises(BusinessException) as ei2:
        await WorkflowEngine(db, DEMO_TENANT).act(
            task.id, {"sub": reviewer_id, "real_name": "测试内勤"}, "reject", opinion="no",
        )
    assert "情报审批" in ei2.value.message

    await db.refresh(task)
    assert task.status == "pending"


@pytest.mark.asyncio
async def test_intel_attack_cc_not_convert_prompt(client, db, lead_intel_user):
    """袭击后抄送负责人的文案不得引导转化。"""
    from app.domains.lead import service as lead_svc
    from app.domains.lead.models import Lead
    from app.domains.notification.models import Notification

    _ = client
    initiator = await _admin_user(db)
    reviewer_id = lead_intel_user
    lead_id = await _create_pending_lead(db, "袭击-抄送文案", initiator)
    lead = (await db.execute(select(Lead).where(Lead.id == lead_id))).scalar_one()
    owner_id = lead.owner_id or initiator["sub"]
    if lead.owner_id != owner_id:
        lead.owner_id = owner_id
        await db.commit()

    task = await _pending_task_for_lead(db, lead_id, reviewer_id)
    await lead_svc.intel_review_lead(
        db, DEMO_TENANT, lead_id,
        {"sub": reviewer_id, "real_name": "测试内勤", "username": "intel"},
        decision="attack", task_id=task.id, customer_newness="new",
    )

    notes = (await db.execute(select(Notification).where(
        Notification.tenant_id == DEMO_TENANT,
        Notification.recipient_id == owner_id,
        Notification.biz_type == "lead",
        Notification.biz_id == lead_id,
    ))).scalars().all()
    assert notes, "袭击后负责人应收到抄送通知"
    for n in notes:
        body = f"{n.title or ''}\n{n.content or ''}"
        assert "袭击" in body
        assert "自行选择是否转化" not in body
        assert "请转化为" not in body
