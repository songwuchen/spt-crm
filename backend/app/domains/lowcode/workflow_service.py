"""扩展平台 — 审批流程引擎服务(定义生命周期 + 运行时查询 + 表单绑定触发)。"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND, DUPLICATE_ENTRY, BUSINESS_ERROR
from app.database import generate_uuid
from app.domains.lowcode import workflow_schemas as ws
from app.domains.lowcode.workflow_models import (
    WfProcessDefinition, WfProcessDefinitionVersion, WfProcessInstance,
    WfNodeInstance, WfTaskInstance, WfTaskActionLog, WfProcessComment, WfProcessCc,
)
from app.domains.lowcode.workflow_engine import WorkflowEngine


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ==================== 流程定义 ====================

async def create_definition(db: AsyncSession, tenant_id: str, data: ws.WfDefinitionCreate, user: dict) -> WfProcessDefinition:
    code = data.code or f"WF_{generate_uuid()[:8].upper()}"
    exists = (await db.execute(select(WfProcessDefinition).where(
        WfProcessDefinition.tenant_id == tenant_id, WfProcessDefinition.code == code,
        WfProcessDefinition.is_deleted == False,  # noqa: E712
    ))).scalar_one_or_none()
    if exists:
        raise BusinessException(code=DUPLICATE_ENTRY, message=f"流程编码 {code} 已存在")
    d = WfProcessDefinition(
        id=generate_uuid(), tenant_id=tenant_id, name=data.name, code=code,
        description=data.description, category=data.category, icon=data.icon,
        form_template_id=data.form_template_id, biz_type=data.biz_type,
        status="draft", current_version=0, created_by=user.get("sub"),
    )
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return d


async def get_definition(db: AsyncSession, tenant_id: str, def_id: str) -> WfProcessDefinition:
    d = (await db.execute(select(WfProcessDefinition).where(
        WfProcessDefinition.id == def_id, WfProcessDefinition.tenant_id == tenant_id,
        WfProcessDefinition.is_deleted == False,  # noqa: E712
    ))).scalar_one_or_none()
    if not d:
        raise BusinessException(code=NOT_FOUND, message="流程定义不存在")
    return d


async def list_definitions(db, tenant_id, page_no, page_size, name=None):
    conds = [WfProcessDefinition.tenant_id == tenant_id, WfProcessDefinition.is_deleted == False]  # noqa: E712
    if name:
        conds.append(WfProcessDefinition.name.ilike(f"%{name}%"))
    total = (await db.execute(select(func.count()).select_from(WfProcessDefinition).where(*conds))).scalar_one()
    rows = (await db.execute(select(WfProcessDefinition).where(*conds)
            .order_by(WfProcessDefinition.created_at.desc())
            .offset((page_no - 1) * page_size).limit(page_size))).scalars().all()
    return list(rows), total


async def update_definition(db, tenant_id, def_id, data: ws.WfDefinitionUpdate) -> WfProcessDefinition:
    d = await get_definition(db, tenant_id, def_id)
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(d, k, v)
    await db.commit()
    await db.refresh(d)
    return d


async def delete_definition(db, tenant_id, def_id) -> None:
    d = await get_definition(db, tenant_id, def_id)
    d.is_deleted = True
    await db.commit()


async def _latest_version(db, tenant_id, def_id) -> WfProcessDefinitionVersion | None:
    return (await db.execute(select(WfProcessDefinitionVersion).where(
        WfProcessDefinitionVersion.tenant_id == tenant_id,
        WfProcessDefinitionVersion.process_definition_id == def_id,
    ).order_by(WfProcessDefinitionVersion.version_number.desc()).limit(1))).scalar_one_or_none()


async def _published_version(db, tenant_id, def_id) -> WfProcessDefinitionVersion | None:
    return (await db.execute(select(WfProcessDefinitionVersion).where(
        WfProcessDefinitionVersion.tenant_id == tenant_id,
        WfProcessDefinitionVersion.process_definition_id == def_id,
        WfProcessDefinitionVersion.status == "published",
    ).order_by(WfProcessDefinitionVersion.version_number.desc()).limit(1))).scalar_one_or_none()


async def save_design(db, tenant_id, def_id, data: ws.WfSaveDesign, user_id) -> WfProcessDefinitionVersion:
    await get_definition(db, tenant_id, def_id)
    latest = await _latest_version(db, tenant_id, def_id)
    if latest and latest.status == "draft":
        latest.node_definitions = data.node_definitions
        latest.route_definitions = data.route_definitions
        latest.approver_rules = data.approver_rules
        await db.commit()
        await db.refresh(latest)
        return latest
    v = WfProcessDefinitionVersion(
        id=generate_uuid(), tenant_id=tenant_id, process_definition_id=def_id,
        version_number=(latest.version_number + 1) if latest else 1,
        node_definitions=data.node_definitions, route_definitions=data.route_definitions,
        approver_rules=data.approver_rules, status="draft",
    )
    db.add(v)
    await db.commit()
    await db.refresh(v)
    return v


async def publish(db, tenant_id, def_id, user_id) -> WfProcessDefinitionVersion:
    d = await get_definition(db, tenant_id, def_id)
    latest = await _latest_version(db, tenant_id, def_id)
    if not latest or latest.status != "draft":
        raise BusinessException(code=BUSINESS_ERROR, message="没有可发布的草稿版本")
    # 基本校验: 必须有 start 与 end 节点
    types = {n.get("type") for n in (latest.node_definitions or [])}
    if "start" not in types or "end" not in types:
        raise BusinessException(code=BUSINESS_ERROR, message="流程必须包含开始与结束节点")
    old = await _published_version(db, tenant_id, def_id)
    if old:
        old.status = "deprecated"
    latest.status = "published"
    latest.published_at = _now()
    latest.published_by = user_id
    d.status = "published"
    d.current_version = latest.version_number
    await db.commit()
    await db.refresh(latest)
    return latest


async def get_design(db, tenant_id, def_id) -> WfProcessDefinitionVersion | None:
    return await _latest_version(db, tenant_id, def_id)


async def get_versions(db, tenant_id, def_id):
    rows = (await db.execute(select(WfProcessDefinitionVersion).where(
        WfProcessDefinitionVersion.tenant_id == tenant_id,
        WfProcessDefinitionVersion.process_definition_id == def_id,
    ).order_by(WfProcessDefinitionVersion.version_number.desc()))).scalars().all()
    return list(rows)


# ==================== 表单绑定触发 ====================

async def maybe_start_for_form(db, tenant_id, template_id, form_instance, user, form_data) -> WfProcessInstance | None:
    """表单提交后: 若该表单绑定了已发布流程,则起流程并返回;否则返回 None(表单按普通提交)。"""
    d = (await db.execute(select(WfProcessDefinition).where(
        WfProcessDefinition.tenant_id == tenant_id,
        WfProcessDefinition.form_template_id == template_id,
        WfProcessDefinition.status == "published",
        WfProcessDefinition.is_deleted == False,  # noqa: E712
    ).limit(1))).scalar_one_or_none()
    if not d:
        return None
    version = await _published_version(db, tenant_id, d.id)
    if not version:
        return None
    engine = WorkflowEngine(db, tenant_id)
    # 注意: 引擎内部会 commit;此处不额外 commit(调用方 create_instance 已在 flush 后)
    return await engine.submit(
        d.id, version, user, form_instance_id=form_instance.id,
        form_data=form_data, title=form_instance.title,
    )


async def start_for_biz(
    db, tenant_id, biz_type, biz_id, user, title=None, form_data=None,
) -> WfProcessInstance | None:
    """既有业务单据(报价/合同/订单/线索...)提交审批: 若该 biz_type 绑定了已发布流程,
    起新引擎流程并承载 (biz_type, biz_id);完成/驳回后由引擎回写业务表状态(wf_biz_writeback)。
    与旧 approval 引擎并存,按 biz_type 灰度切换。未绑定流程则返回 None(走原有逻辑)。"""
    d = (await db.execute(select(WfProcessDefinition).where(
        WfProcessDefinition.tenant_id == tenant_id,
        WfProcessDefinition.biz_type == biz_type,
        WfProcessDefinition.status == "published",
        WfProcessDefinition.is_deleted == False,  # noqa: E712
    ).limit(1))).scalar_one_or_none()
    if not d:
        return None
    # 防重: 同一业务单据已有进行中的流程时不再重复发起(对齐旧引擎 submit_approval 的
    # 「该对象已有进行中的审批流」保护),避免重复提交产生并发重复审批。返回已存在实例。
    existing = (await db.execute(select(WfProcessInstance).where(
        WfProcessInstance.tenant_id == tenant_id,
        WfProcessInstance.biz_type == biz_type,
        WfProcessInstance.biz_id == biz_id,
        WfProcessInstance.status == "running",
    ).limit(1))).scalar_one_or_none()
    if existing:
        return existing
    version = await _published_version(db, tenant_id, d.id)
    if not version:
        return None
    # 业务流没有表单：载入业务实体字段(金额/优先级/来源...)作为条件上下文，
    # 让连线条件能按业务字段分支(与业务字段目录、旧审批 _build_policy_context 一致)。
    ctx = form_data
    if ctx is None:
        try:
            from app.domains.approval.service import _build_policy_context
            ctx = await _build_policy_context(db, tenant_id, biz_type, biz_id)
        except Exception:
            ctx = {}
    return await WorkflowEngine(db, tenant_id).submit(
        d.id, version, user, biz_type=biz_type, biz_id=biz_id, title=title, form_data=ctx or {},
    )


# ==================== 运行时查询 ====================

async def list_todo(db, tenant_id, user_id, page_no, page_size):
    # 待办 = 本人被指派 + 本人作为「有效代理人」代办的委托人任务
    principals = await active_principals(db, tenant_id, user_id)
    assignees = [user_id, *principals]
    conds = [WfTaskInstance.tenant_id == tenant_id, WfTaskInstance.assignee_id.in_(assignees),
             WfTaskInstance.status == "pending"]
    total = (await db.execute(select(func.count()).select_from(WfTaskInstance).where(*conds))).scalar_one()
    tasks = (await db.execute(select(WfTaskInstance).where(*conds)
             .order_by(WfTaskInstance.created_at.desc())
             .offset((page_no - 1) * page_size).limit(page_size))).scalars().all()
    return await _enrich_tasks(db, list(tasks), viewer_id=user_id), total


async def list_done(db, tenant_id, user_id, page_no, page_size):
    conds = [WfTaskInstance.tenant_id == tenant_id, WfTaskInstance.assignee_id == user_id,
             WfTaskInstance.status.in_(["approved", "rejected", "transferred", "returned"])]
    total = (await db.execute(select(func.count()).select_from(WfTaskInstance).where(*conds))).scalar_one()
    tasks = (await db.execute(select(WfTaskInstance).where(*conds)
             .order_by(WfTaskInstance.action_at.desc())
             .offset((page_no - 1) * page_size).limit(page_size))).scalars().all()
    return await _enrich_tasks(db, list(tasks)), total


async def list_initiated(db, tenant_id, user_id, page_no, page_size):
    conds = [WfProcessInstance.tenant_id == tenant_id, WfProcessInstance.initiator_id == user_id]
    total = (await db.execute(select(func.count()).select_from(WfProcessInstance).where(*conds))).scalar_one()
    rows = (await db.execute(select(WfProcessInstance).where(*conds)
            .order_by(WfProcessInstance.created_at.desc())
            .offset((page_no - 1) * page_size).limit(page_size))).scalars().all()
    return [_inst_dict(i) for i in rows], total


async def _enrich_tasks(db, tasks: list[WfTaskInstance], viewer_id: str | None = None) -> list[dict]:
    # 若含代办任务，批量解析委托人姓名用于「代 XX 审批」标注
    principal_ids = {t.assignee_id for t in tasks if viewer_id and t.assignee_id != viewer_id}
    name_map: dict[str, str] = {}
    if principal_ids:
        from app.domains.auth.models import User
        rows = (await db.execute(select(User.id, User.real_name, User.username)
                .where(User.id.in_(principal_ids)))).all()
        name_map = {r[0]: (r[1] or r[2]) for r in rows}
    out = []
    for t in tasks:
        inst = await db.get(WfProcessInstance, t.process_instance_id)
        on_behalf = viewer_id is not None and t.assignee_id != viewer_id
        out.append({
            "task_id": t.id, "status": t.status, "opinion": t.opinion,
            "process_instance_id": t.process_instance_id,
            "title": inst.title if inst else None,
            "business_no": inst.business_no if inst else None,
            "initiator_id": inst.initiator_id if inst else None,
            "process_status": inst.status if inst else None,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "action_at": t.action_at.isoformat() if t.action_at else None,
            # 代理审批：非本人被指派的待办 = 代办，标注委托人
            "on_behalf_of": on_behalf,
            "delegator_id": t.assignee_id if on_behalf else None,
            "delegator_name": name_map.get(t.assignee_id) if on_behalf else None,
        })
    return out


# ==================== 代理审批(委托) ====================

async def active_principals(db, tenant_id, agent_id) -> list[str]:
    """返回当前时刻 agent_id 作为有效代理人所代理的委托人 user_id 列表。"""
    from app.domains.organization.models import UserAgent
    now = _now()
    rows = (await db.execute(select(UserAgent.user_id).where(
        UserAgent.tenant_id == tenant_id, UserAgent.agent_id == agent_id,
        UserAgent.status == "active", UserAgent.start_time <= now, UserAgent.end_time >= now,
    ))).scalars().all()
    return list(rows)


async def is_active_agent(db, tenant_id, principal_id: str, agent_id: str) -> bool:
    """agent_id 当前是否为 principal_id 的有效代理人。"""
    from app.domains.organization.models import UserAgent
    now = _now()
    r = (await db.execute(select(UserAgent.id).where(
        UserAgent.tenant_id == tenant_id, UserAgent.user_id == principal_id,
        UserAgent.agent_id == agent_id, UserAgent.status == "active",
        UserAgent.start_time <= now, UserAgent.end_time >= now,
    ).limit(1))).scalar_one_or_none()
    return r is not None


async def create_agent(db, tenant_id, principal_id: str, agent_id: str, start_time, end_time, note=None):
    """设置代理：principal_id 在 [start,end] 期间由 agent_id 代为审批。"""
    from app.domains.organization.models import UserAgent
    if principal_id == agent_id:
        raise BusinessException(code=BUSINESS_ERROR, message="不能设置自己为代理人")
    if end_time <= start_time:
        raise BusinessException(code=BUSINESS_ERROR, message="结束时间需晚于开始时间")
    ua = UserAgent(id=generate_uuid(), tenant_id=tenant_id, user_id=principal_id, agent_id=agent_id,
                   start_time=start_time, end_time=end_time, status="active", note=note)
    db.add(ua)
    await db.commit()
    await db.refresh(ua)
    return ua


async def list_agents(db, tenant_id, principal_id: str) -> list[dict]:
    """列出「我(principal_id)设置的代理」。"""
    from app.domains.organization.models import UserAgent
    from app.domains.auth.models import User
    rows = (await db.execute(select(UserAgent).where(
        UserAgent.tenant_id == tenant_id, UserAgent.user_id == principal_id,
    ).order_by(UserAgent.created_at.desc()))).scalars().all()
    agent_ids = {r.agent_id for r in rows}
    name_map: dict[str, str] = {}
    if agent_ids:
        urows = (await db.execute(select(User.id, User.real_name, User.username)
                 .where(User.id.in_(agent_ids)))).all()
        name_map = {u[0]: (u[1] or u[2]) for u in urows}
    now = _now()
    return [{
        "id": r.id, "agent_id": r.agent_id, "agent_name": name_map.get(r.agent_id),
        "start_time": r.start_time.isoformat() if r.start_time else None,
        "end_time": r.end_time.isoformat() if r.end_time else None,
        "status": r.status, "note": r.note,
        "active_now": r.status == "active" and (r.start_time <= now <= r.end_time),
    } for r in rows]


async def delete_agent(db, tenant_id, agent_row_id: str, principal_id: str) -> None:
    """撤销代理（仅委托人本人可撤销自己设置的代理）。"""
    from app.domains.organization.models import UserAgent
    ua = await db.get(UserAgent, agent_row_id)
    if ua and ua.tenant_id == tenant_id and ua.user_id == principal_id:
        await db.delete(ua)
        await db.commit()


def _inst_dict(i: WfProcessInstance) -> dict:
    return {
        "id": i.id, "title": i.title, "business_no": i.business_no, "status": i.status,
        "initiator_id": i.initiator_id, "form_instance_id": i.form_instance_id,
        "biz_type": i.biz_type, "biz_id": i.biz_id,
        "started_at": i.started_at.isoformat() if i.started_at else None,
        "completed_at": i.completed_at.isoformat() if i.completed_at else None,
        "created_at": i.created_at.isoformat() if i.created_at else None,
    }


async def get_instance_detail(db, tenant_id, instance_id) -> dict:
    inst = (await db.execute(select(WfProcessInstance).where(
        WfProcessInstance.id == instance_id, WfProcessInstance.tenant_id == tenant_id,
    ))).scalar_one_or_none()
    if not inst:
        raise BusinessException(code=NOT_FOUND, message="流程实例不存在")
    logs = (await db.execute(select(WfTaskActionLog).where(
        WfTaskActionLog.process_instance_id == instance_id,
    ).order_by(WfTaskActionLog.created_at.asc()))).scalars().all()
    tasks = (await db.execute(select(WfTaskInstance).where(
        WfTaskInstance.process_instance_id == instance_id,
    ))).scalars().all()
    comments = (await db.execute(select(WfProcessComment).where(
        WfProcessComment.process_instance_id == instance_id,
    ).order_by(WfProcessComment.created_at.asc()))).scalars().all()
    version = await db.get(WfProcessDefinitionVersion, inst.process_version_id)
    approval_nodes = [
        {"id": n.get("id"), "name": n.get("name") or "审批"}
        for n in (version.node_definitions if version else []) if n.get("type") == "approval"
    ]
    return {
        **_inst_dict(inst),
        "approval_nodes": approval_nodes,
        "timeline": [{
            "action": l.action, "actor_id": l.actor_id, "actor_name": l.actor_name,
            "opinion": l.opinion, "at": l.created_at.isoformat() if l.created_at else None,
        } for l in logs],
        "tasks": [{
            "id": t.id, "assignee_id": t.assignee_id, "status": t.status,
            "opinion": t.opinion, "task_order": t.task_order,
        } for t in tasks],
        "comments": [{
            "user_id": c.user_id, "user_name": c.user_name, "content": c.content,
            "at": c.created_at.isoformat() if c.created_at else None,
        } for c in comments],
    }
