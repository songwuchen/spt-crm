"""扩展平台工作流引擎 + 线索审核切换 的回归测试。

这个文件存在的直接原因：线索(lead)曾经是唯一一个「新引擎侧全部配好、前端可选、
但提交路径从未调用新引擎」的业务实体 —— 灰度接线那次提交漏改了 lead/service.py，
而当时 wf 引擎没有任何测试，所以漏接线一直没被发现。下面第一个用例就是钉住这一点。
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from app.database import generate_uuid
from tests.lead_intel_helpers import DEMO_TENANT, pending_intel_task


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
    """未配置可视化流程时，系统兜底流程应被自动创建并发布，且审批人规则是指定崔艳丽、杨光。"""
    from app.domains.lowcode.workflow_models import WfProcessDefinition, WfProcessDefinitionVersion
    from app.domains.lead.service import LEAD_DEFAULT_FLOW_CODE
    from app.domains.lowcode.workflow_service import _LEAD_INTEL_APPROVER_USERNAMES

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
    intel = next(
        n for n in approval
        if "情报" in (n.get("name") or "")
        or (n.get("approver_rule") or {}).get("type") == "specified_user"
    )
    confirm = next(n for n in approval if n.get("id") == "approval_owner_confirm"
                   or "转商机" in (n.get("name") or ""))
    rule = intel["approver_rule"]
    assert rule["type"] == "specified_user"
    vals = rule["value"] if isinstance(rule["value"], list) else [rule["value"]]
    assert set(vals) >= set(_LEAD_INTEL_APPROVER_USERNAMES)
    # 排除提交人本人，保持与旧实现一致（旧实现 exclude_user_id=提交人）
    assert rule.get("exclude_initiator") is True
    # 无审批人时自动通过，避免线索卡在 pending 无法转化
    assert intel["empty_strategy"] == "auto_approve"
    assert confirm["type"] == "approval"
    assert (confirm.get("approver_rule") or {}).get("type") == "form_field_person"
    assert (confirm.get("approver_rule") or {}).get("value") == "reporter_id"


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
async def test_lead_stays_pending_when_intel_approvers_unresolved(client: AsyncClient, auth_headers, db):
    """指定情报审批人账号不存在/停用时，不得静默 auto_approve，线索保持待审。"""
    from app.domains.auth.models import User
    from app.domains.lead.models import Lead
    from app.domains.lowcode.workflow_service import _LEAD_INTEL_APPROVER_USERNAMES

    members = (await db.execute(
        select(User).where(
            User.tenant_id == DEMO_TENANT,
            User.username.in_(_LEAD_INTEL_APPROVER_USERNAMES),
            User.is_active == True,  # noqa: E712
        )
    )).scalars().all()
    restore = [u.id for u in members]
    for u in members:
        u.is_active = False
    await db.commit()

    try:
        lead_id = await _create_lead(client, auth_headers, "无审核人-线索")
        lead = (await db.execute(select(Lead).where(Lead.id == lead_id))).scalar_one()
        assert lead.review_status == "pending", (
            f"指定审批人未匹配时不应静默免审，实际 review_status={lead.review_status}"
        )
    finally:
        if restore:
            await db.execute(text("UPDATE users SET is_active = true WHERE id = ANY(:ids)"),
                             {"ids": restore})
            await db.commit()


# ---------- 有审批人时的完整闭环 ----------

async def _pending_task_for_lead(db, lead_id: str, assignee_id: str | None = None):
    return await pending_intel_task(db, lead_id, assignee_id)


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
    from app.domains.lowcode.workflow_service import _LEAD_INTEL_APPROVER_USERNAMES

    reviewer_id = lead_intel_user
    resolver = ApproverResolver(db, DEMO_TENANT)
    rule = {
        "type": "specified_user",
        "value": list(_LEAD_INTEL_APPROVER_USERNAMES),
        "exclude_initiator": True,
    }

    ids = await resolver.resolve(rule, ApprovalContext(initiator_id=reviewer_id, form_data={}, nominated={}))
    assert reviewer_id not in ids

    # 不开开关时保持原行为
    resolver2 = ApproverResolver(db, DEMO_TENANT)
    ids2 = await resolver2.resolve(
        {"type": "specified_user", "value": list(_LEAD_INTEL_APPROVER_USERNAMES)},
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
    """驳回 → rejected + reject_reason，且不可再提交审核。"""
    from app.domains.lead import service as lead_svc
    from app.common.exceptions import BusinessException

    _ = client
    initiator = await _admin_user(db)
    reviewer_id = lead_intel_user
    lead_id = await _create_pending_lead(db, "情报-驳回", initiator)
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
async def test_intel_revise_sends_back_for_resubmit(client, db, lead_intel_user):
    """回退 → 草稿 + 修订待办，申报人可改后再提。"""
    from sqlalchemy import select
    from app.domains.lead import service as lead_svc
    from app.domains.lead.models import Lead
    from app.domains.lowcode.workflow_models import WfTaskInstance, WfNodeInstance

    _ = client
    initiator = await _admin_user(db)
    reviewer_id = lead_intel_user
    lead_id = await _create_pending_lead(db, "情报-回退改提", initiator)
    # 申报人指向发起人，修订待办应派给申报人
    lead_row = (await db.execute(select(Lead).where(Lead.id == lead_id))).scalar_one()
    lead_row.reporter_id = initiator["sub"]
    await db.commit()

    task = await _pending_task_for_lead(db, lead_id, reviewer_id)
    lead = await lead_svc.intel_review_lead(
        db, DEMO_TENANT, lead_id,
        {"sub": reviewer_id, "real_name": "测试内勤", "username": "intel"},
        decision="revise", task_id=task.id, customer_newness="new",
        return_reason="请补全联系人", opinion="回退修改",
    )
    assert lead.review_status == "draft"
    assert lead.reject_reason == "请补全联系人"

    revise_tasks = (await db.execute(
        select(WfTaskInstance)
        .join(WfNodeInstance, WfNodeInstance.id == WfTaskInstance.node_instance_id)
        .where(
            WfTaskInstance.tenant_id == DEMO_TENANT,
            WfNodeInstance.node_type == "revise",
            WfTaskInstance.status == "pending",
        )
    )).scalars().all()
    assert any(t.assignee_id == initiator["sub"] for t in revise_tasks)


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
    from app.domains.lowcode.workflow_models import WfProcessInstance

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

    inst = (await db.execute(select(WfProcessInstance).where(
        WfProcessInstance.biz_type == "lead", WfProcessInstance.biz_id == lead_id,
    ))).scalar_one()
    # 抄送站内通知已统一为 approval_cc + wf_instance（对齐「抄送我的」）
    # flush_notifications 可能异步，稍等再查
    import asyncio
    from app.domains.lowcode.workflow_models import WfProcessCc

    for _ in range(20):
        notes = (await db.execute(select(Notification).where(
            Notification.tenant_id == DEMO_TENANT,
            Notification.recipient_id == owner_id,
            Notification.type == "approval_cc",
            Notification.biz_type == "wf_instance",
            Notification.biz_id == inst.id,
        ))).scalars().all()
        if notes:
            break
        await asyncio.sleep(0.1)
    assert notes, "袭击后负责人应收到抄送通知"
    for n in notes:
        body = f"{n.title or ''}\n{n.content or ''}"
        assert "袭击" in body
        assert "自行选择是否转化" not in body
        assert "请转化为" not in body

    cc_rows = (await db.execute(select(WfProcessCc).where(
        WfProcessCc.tenant_id == DEMO_TENANT,
        WfProcessCc.process_instance_id == inst.id,
    ))).scalars().all()
    assert cc_rows, "袭击知会须写入 wf_process_cc，审批中心「抄送我的」才能看到"
    cc_uids = {c.user_id for c in cc_rows}
    assert owner_id in cc_uids or any(n.recipient_id in cc_uids for n in notes)


# ---------- 流程激活（已结束选节点重开） ----------

async def _reject_lead_flow(db, lead_id: str, reviewer_id: str):
    from app.domains.lowcode.workflow_engine import WorkflowEngine
    task = await _pending_task_for_lead(db, lead_id, reviewer_id)
    await WorkflowEngine(db, DEMO_TENANT).act(
        task.id, {"sub": reviewer_id, "real_name": "测试内勤"}, "reject", opinion="激活用例驳回",
        allow_lead_intel=True,
    )


def _nodes_of(inst, db_version):
    nodes = db_version.node_definitions or []
    start = next(n for n in nodes if n.get("type") == "start")
    approval = next(n for n in nodes if n.get("type") == "approval")
    return start, approval


@pytest.mark.asyncio
async def test_activate_approval_reopens_ended_instance(client, db, lead_intel_user):
    """已驳回实例激活到审批节点 → running + 新 pending 待办。"""
    from app.domains.lowcode.workflow_models import (
        WfProcessInstance, WfTaskInstance, WfProcessDefinitionVersion,
    )
    from app.domains.lowcode.workflow_engine import WorkflowEngine
    from app.common.exceptions import BusinessException

    _ = client
    initiator = await _admin_user(db)
    reviewer_id = lead_intel_user
    lead_id = await _create_pending_lead(db, "激活-审批节点", initiator)
    await _reject_lead_flow(db, lead_id, reviewer_id)

    inst = (await db.execute(select(WfProcessInstance).where(
        WfProcessInstance.biz_type == "lead", WfProcessInstance.biz_id == lead_id,
    ))).scalar_one()
    assert inst.status == "rejected"
    version = await db.get(WfProcessDefinitionVersion, inst.process_version_id)
    _, approval = _nodes_of(inst, version)

    actor = {"sub": initiator["sub"], "real_name": "admin", "username": "admin"}
    out = await WorkflowEngine(db, DEMO_TENANT).activate(inst.id, actor, approval["id"])
    assert out.status == "running"
    assert out.completed_at is None

    pending = (await db.execute(select(WfTaskInstance).where(
        WfTaskInstance.process_instance_id == inst.id,
        WfTaskInstance.status == "pending",
    ))).scalars().all()
    assert pending, "激活审批节点后应有待办"
    assert any(t.assignee_id == reviewer_id for t in pending)

    # running 不可再激活
    with pytest.raises(BusinessException) as ei:
        await WorkflowEngine(db, DEMO_TENANT).activate(inst.id, actor, approval["id"])
    assert "退回" in ei.value.message or "进行中" in ei.value.message


@pytest.mark.asyncio
async def test_activate_start_creates_revise_todo(client, db, lead_intel_user):
    """已结束激活到开始节点 → 发起人修订待办（可改数重提）。"""
    from app.domains.lowcode.workflow_models import (
        WfProcessInstance, WfTaskInstance, WfNodeInstance, WfProcessDefinitionVersion,
    )
    from app.domains.lowcode.workflow_engine import WorkflowEngine

    _ = client
    initiator = await _admin_user(db)
    reviewer_id = lead_intel_user
    lead_id = await _create_pending_lead(db, "激活-开始节点", initiator)
    await _reject_lead_flow(db, lead_id, reviewer_id)

    inst = (await db.execute(select(WfProcessInstance).where(
        WfProcessInstance.biz_type == "lead", WfProcessInstance.biz_id == lead_id,
    ))).scalar_one()
    version = await db.get(WfProcessDefinitionVersion, inst.process_version_id)
    start, _ = _nodes_of(inst, version)

    actor = {"sub": initiator["sub"], "real_name": "admin", "username": "admin"}
    out = await WorkflowEngine(db, DEMO_TENANT).activate(inst.id, actor, start["id"])
    assert out.status == "withdrawn"

    revise = (await db.execute(
        select(WfTaskInstance)
        .join(WfNodeInstance, WfNodeInstance.id == WfTaskInstance.node_instance_id)
        .where(
            WfTaskInstance.process_instance_id == inst.id,
            WfTaskInstance.status == "pending",
            WfNodeInstance.node_type == "revise",
        )
    )).scalars().all()
    assert revise, "激活开始节点应给发起人修订待办"
    assert any(t.assignee_id == initiator["sub"] for t in revise)


@pytest.mark.asyncio
async def test_withdraw_resubmit_reuses_same_process_instance(client, db, lead_intel_user):
    """撤回后重新提交应复用同一流程实例，「我发起的」不应出现两条。"""
    from app.domains.lowcode.workflow_models import WfProcessInstance, WfTaskInstance
    from app.domains.lowcode.workflow_engine import WorkflowEngine

    _ = client
    initiator = await _admin_user(db)
    reviewer_id = lead_intel_user
    lead_id = await _create_pending_lead(db, "撤回-重提同实例", initiator)

    inst = (await db.execute(select(WfProcessInstance).where(
        WfProcessInstance.biz_type == "lead", WfProcessInstance.biz_id == lead_id,
    ))).scalar_one()
    original_id = inst.id

    actor = {"sub": initiator["sub"], "real_name": "admin", "username": "admin"}
    await WorkflowEngine(db, DEMO_TENANT).withdraw(inst.id, actor)
    await db.refresh(inst)
    assert inst.status == "withdrawn"

    out = await WorkflowEngine(db, DEMO_TENANT).resubmit(inst.id, actor)
    assert out.id == original_id
    assert out.status == "running"
    assert out.completed_at is None

    all_insts = (await db.execute(select(WfProcessInstance).where(
        WfProcessInstance.biz_type == "lead", WfProcessInstance.biz_id == lead_id,
    ))).scalars().all()
    assert len(all_insts) == 1, "重新提交不应新建第二条流程实例"

    pending = (await db.execute(select(WfTaskInstance).where(
        WfTaskInstance.process_instance_id == original_id,
        WfTaskInstance.status == "pending",
    ))).scalars().all()
    assert pending, "重新提交后应有审批待办"


@pytest.mark.asyncio
async def test_delete_form_instance_blocked_after_flow_started(db):
    """表单数据一旦绑定流程实例，禁止直接删除（草稿未发起仍可删）。"""
    from app.common.exceptions import BusinessException
    from app.domains.lowcode.models import FormInstance
    from app.domains.lowcode.service import delete_instance
    from app.domains.lowcode.workflow_service import STARTED_FLOW_DELETE_MSG

    user = {"sub": "ut-admin", "username": "admin", "real_name": "UT"}
    draft = FormInstance(
        id=generate_uuid(), tenant_id=DEMO_TENANT,
        template_id=generate_uuid(), template_version_id=generate_uuid(),
        title="草稿可删", status="draft", initiator_id=user["sub"],
        form_data={}, field_definitions=[],
    )
    started = FormInstance(
        id=generate_uuid(), tenant_id=DEMO_TENANT,
        template_id=generate_uuid(), template_version_id=generate_uuid(),
        title="已发起不可删", status="running", initiator_id=user["sub"],
        process_instance_id=generate_uuid(),
        form_data={}, field_definitions=[],
    )
    db.add_all([draft, started])
    await db.commit()

    await delete_instance(db, DEMO_TENANT, draft.id, user)
    await db.refresh(draft)
    assert draft.is_deleted is True

    with pytest.raises(BusinessException) as exc:
        await delete_instance(db, DEMO_TENANT, started.id, user)
    assert STARTED_FLOW_DELETE_MSG in str(exc.value.message)
    await db.refresh(started)
    assert started.is_deleted is False

    # 旧数据可能没回写 process_instance_id，仍按 form_instance_id 拦住
    from app.domains.lowcode.workflow_models import WfProcessInstance
    orphan = FormInstance(
        id=generate_uuid(), tenant_id=DEMO_TENANT,
        template_id=generate_uuid(), template_version_id=generate_uuid(),
        title="仅流程侧绑定", status="running", initiator_id=user["sub"],
        form_data={}, field_definitions=[],
    )
    db.add(orphan)
    await db.flush()
    db.add(WfProcessInstance(
        id=generate_uuid(), tenant_id=DEMO_TENANT,
        process_definition_id=generate_uuid(), process_version_id=generate_uuid(),
        form_instance_id=orphan.id, initiator_id=user["sub"], status="running",
    ))
    await db.commit()
    with pytest.raises(BusinessException) as exc2:
        await delete_instance(db, DEMO_TENANT, orphan.id, user)
    assert STARTED_FLOW_DELETE_MSG in str(exc2.value.message)


@pytest.mark.asyncio
async def test_delete_payment_registration_allowed_after_flow_started(db):
    """收款登记：有 form_data:delete 时允许删除已走流程单据（对齐简道云财务权限组）。"""
    from sqlalchemy import select
    from app.domains.lowcode.models import FormInstance, FormTemplate, FormTemplateVersion
    from app.domains.lowcode.service import delete_instance

    user = {"sub": "ut-finance", "username": "finance", "real_name": "财务UT"}
    tpl = (await db.execute(
        select(FormTemplate).where(
            FormTemplate.tenant_id == DEMO_TENANT,
            FormTemplate.code == "payment_registration",
        ).limit(1)
    )).scalar_one_or_none()
    if not tpl:
        tpl_id = generate_uuid()
        ver_id = generate_uuid()
        db.add(FormTemplate(
            id=tpl_id, tenant_id=DEMO_TENANT, code="payment_registration",
            name="收款登记UT", status="published", current_version=1,
        ))
        db.add(FormTemplateVersion(
            id=ver_id, tenant_id=DEMO_TENANT, template_id=tpl_id, version_number=1,
            status="published", field_definitions=[],
        ))
        await db.flush()
        tpl = await db.get(FormTemplate, tpl_id)
    ver = (await db.execute(
        select(FormTemplateVersion).where(
            FormTemplateVersion.template_id == tpl.id,
            FormTemplateVersion.version_number == (tpl.current_version or 1),
        ).limit(1)
    )).scalar_one_or_none()
    ver_id = ver.id if ver else generate_uuid()
    if not ver:
        db.add(FormTemplateVersion(
            id=ver_id, tenant_id=DEMO_TENANT, template_id=tpl.id, version_number=1,
            status="published", field_definitions=[],
        ))
        await db.flush()
    started = FormInstance(
        id=generate_uuid(), tenant_id=DEMO_TENANT,
        template_id=tpl.id, template_version_id=ver_id,
        title="已发起可删", status="running", initiator_id=user["sub"],
        process_instance_id=generate_uuid(),
        form_data={}, field_definitions=[],
    )
    db.add(started)
    await db.commit()

    await delete_instance(db, DEMO_TENANT, started.id, user)
    await db.refresh(started)
    assert started.is_deleted is True


@pytest.mark.asyncio
async def test_abort_deleted_form_cancels_pending_todo(db):
    """表单已软删时，作废进行中流程并取消待办。"""
    from app.domains.lowcode.models import FormInstance
    from app.domains.lowcode.workflow_engine import WorkflowEngine
    from app.domains.lowcode.workflow_models import WfNodeInstance, WfProcessInstance, WfTaskInstance
    from app.domains.lowcode.workflow_service import list_todo

    fi = FormInstance(
        id=generate_uuid(), tenant_id=DEMO_TENANT,
        template_id=generate_uuid(), template_version_id=generate_uuid(),
        title="已删单据", status="running", initiator_id="u-init",
        is_deleted=True, form_data={}, field_definitions=[],
    )
    inst = WfProcessInstance(
        id=generate_uuid(), tenant_id=DEMO_TENANT,
        process_definition_id=generate_uuid(), process_version_id=generate_uuid(),
        form_instance_id=fi.id, initiator_id="u-init", status="running",
        title="已删单据流程",
    )
    ni = WfNodeInstance(
        id=generate_uuid(), tenant_id=DEMO_TENANT,
        process_instance_id=inst.id, node_def_id="n1",
        node_type="approval", node_name="财务核价", status="running",
    )
    task = WfTaskInstance(
        id=generate_uuid(), tenant_id=DEMO_TENANT,
        process_instance_id=inst.id, node_instance_id=ni.id,
        assignee_id="u-approver", status="pending",
    )
    db.add_all([fi, inst, ni, task])
    await db.commit()

    items, total = await list_todo(db, DEMO_TENANT, "u-approver", 1, 20)
    assert total == 0, "已删表单的待办不应出现在列表里"

    ok = await WorkflowEngine(db, DEMO_TENANT).abort_deleted_form(inst.id)
    assert ok is True
    await db.refresh(inst)
    await db.refresh(task)
    await db.refresh(ni)
    assert inst.status == "cancelled"
    assert task.status == "cancelled"
    assert ni.status == "cancelled"


@pytest.mark.asyncio
async def test_submit_reuses_running_process_for_same_form(db):
    """同一表单已有进行中流程时，再次 submit 不得再开一条。"""
    from app.domains.lowcode.workflow_engine import WorkflowEngine
    from app.domains.lowcode.workflow_models import WfProcessInstance

    fid = generate_uuid()
    running = WfProcessInstance(
        id=generate_uuid(), tenant_id=DEMO_TENANT,
        process_definition_id=generate_uuid(), process_version_id=generate_uuid(),
        form_instance_id=fid, initiator_id="u-init", status="running", title="dup",
    )
    db.add(running)
    await db.commit()

    eng = WorkflowEngine(db, DEMO_TENANT)
    got = await eng._running_by_form(fid)
    assert got is not None and got.id == running.id

    class _Ver:
        node_definitions = [{"id": "start", "type": "start", "name": "开始"}]
        route_definitions = []

    reused = await eng.submit(
        running.process_definition_id, _Ver(), {"sub": "u-init"},
        form_instance_id=fid, title="dup-again",
    )
    assert reused.id == running.id
    rows = (await db.execute(
        select(WfProcessInstance).where(WfProcessInstance.form_instance_id == fid)
    )).scalars().all()
    assert len(rows) == 1


