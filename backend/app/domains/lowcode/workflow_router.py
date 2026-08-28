"""扩展平台 — 审批流程引擎 API。前缀 /api/v1/lc/wf。

- 流程定义设计/管理: workflow:view / workflow:manage
- 运行时(发起/待办/审批): 登录即可,授权在引擎内做行级校验(assignee/initiator)。
"""
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import (
    get_db, get_tenant_id, get_current_user, require_permissions, require_any_permission,
)
from app.common.schemas import ok
from app.domains.lowcode import workflow_schemas as ws, workflow_service as wsvc
from app.domains.lowcode.workflow_engine import WorkflowEngine

router = APIRouter(prefix="/api/v1/lc/wf", tags=["扩展平台-审批流程"])


def _def_dict(d):
    return ws.WfDefinitionOut.model_validate(d).model_dump()


def _ver_dict(v):
    return ws.WfVersionOut.model_validate(v).model_dump(mode="json")


def _parse_list_filters(
    keyword: str | None = Query(None, description="标题/单号/流程名/表单字段关键词"),
    process_definition_id: str | None = Query(None),
    form_code: str | None = Query(None),
    node_name: str | None = Query(None, description="当前节点/任务节点"),
    initiator_id: str | None = Query(None),
    created_from: datetime | None = Query(None),
    created_to: datetime | None = Query(None),
    form_filters: str | None = Query(None, description='JSON: {match,rules:[{field,op,value}]}'),
) -> wsvc.WfListFilters | None:
    f = wsvc.WfListFilters(
        keyword=keyword,
        process_definition_id=process_definition_id,
        form_code=form_code,
        node_name=node_name,
        initiator_id=initiator_id,
        created_from=created_from,
        created_to=created_to,
        form_filters=form_filters,
    )
    return f if f.active() else None


# ==================== 流程定义 ====================

@router.get("/definitions")
async def list_defs(pageNo: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100),
                    name: str = Query(None), tenant_id: str = Depends(get_tenant_id),
                    db: AsyncSession = Depends(get_db), _u=Depends(require_permissions("workflow:view"))):
    items, total = await wsvc.list_definitions(db, tenant_id, pageNo, pageSize, name)
    return ok({"items": [_def_dict(d) for d in items], "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.post("/definitions")
async def create_def(body: ws.WfDefinitionCreate, tenant_id: str = Depends(get_tenant_id),
                     db: AsyncSession = Depends(get_db), user: dict = Depends(require_permissions("workflow:manage"))):
    return ok(_def_dict(await wsvc.create_definition(db, tenant_id, body, user)))


@router.get("/definitions/{def_id}")
async def get_def(def_id: str, tenant_id: str = Depends(get_tenant_id),
                  db: AsyncSession = Depends(get_db), _u=Depends(require_permissions("workflow:view"))):
    return ok(_def_dict(await wsvc.get_definition(db, tenant_id, def_id)))


@router.put("/definitions/{def_id}")
async def update_def(def_id: str, body: ws.WfDefinitionUpdate, tenant_id: str = Depends(get_tenant_id),
                     db: AsyncSession = Depends(get_db), _u=Depends(require_permissions("workflow:manage"))):
    return ok(_def_dict(await wsvc.update_definition(db, tenant_id, def_id, body)))


@router.delete("/definitions/{def_id}")
async def delete_def(def_id: str, tenant_id: str = Depends(get_tenant_id),
                     db: AsyncSession = Depends(get_db), _u=Depends(require_permissions("workflow:manage"))):
    await wsvc.delete_definition(db, tenant_id, def_id)
    return ok(None)


@router.get("/definitions/{def_id}/design")
async def load_design(def_id: str, tenant_id: str = Depends(get_tenant_id),
                      db: AsyncSession = Depends(get_db), _u=Depends(require_permissions("workflow:view"))):
    await wsvc.get_definition(db, tenant_id, def_id)
    v = await wsvc.get_design(db, tenant_id, def_id)
    if not v:
        return ok({"node_definitions": [], "route_definitions": [], "approver_rules": []})
    return ok(_ver_dict(v))


@router.post("/definitions/{def_id}/design")
async def save_design(def_id: str, body: ws.WfSaveDesign, tenant_id: str = Depends(get_tenant_id),
                      db: AsyncSession = Depends(get_db), user: dict = Depends(require_permissions("workflow:manage"))):
    return ok(_ver_dict(await wsvc.save_design(db, tenant_id, def_id, body, user.get("sub"))))


@router.post("/definitions/{def_id}/publish")
async def publish_def(def_id: str, tenant_id: str = Depends(get_tenant_id),
                      db: AsyncSession = Depends(get_db), user: dict = Depends(require_permissions("workflow:manage"))):
    return ok(_ver_dict(await wsvc.publish(db, tenant_id, def_id, user.get("sub"))))


@router.get("/definitions/{def_id}/versions")
async def list_versions(def_id: str, tenant_id: str = Depends(get_tenant_id),
                        db: AsyncSession = Depends(get_db), _u=Depends(require_permissions("workflow:view"))):
    return ok([_ver_dict(v) for v in await wsvc.get_versions(db, tenant_id, def_id)])


# ==================== 运行时 ====================

@router.get("/tasks/todo")
async def my_todo(pageNo: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100),
                  biz_type: str | None = Query(None), biz_id: str | None = Query(None),
                  filters: wsvc.WfListFilters | None = Depends(_parse_list_filters),
                  tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
                  user: dict = Depends(get_current_user)):
    items, total = await wsvc.list_todo(db, tenant_id, user.get("sub"), pageNo, pageSize,
                                        biz_type=biz_type, biz_id=biz_id, filters=filters)
    return ok({"items": items, "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.get("/tasks/done")
async def my_done(pageNo: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100),
                  filters: wsvc.WfListFilters | None = Depends(_parse_list_filters),
                  tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
                  user: dict = Depends(get_current_user)):
    items, total = await wsvc.list_done(db, tenant_id, user.get("sub"), pageNo, pageSize, filters=filters)
    return ok({"items": items, "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.get("/instances/mine")
async def my_initiated(pageNo: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100),
                       filters: wsvc.WfListFilters | None = Depends(_parse_list_filters),
                       tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
                       user: dict = Depends(get_current_user)):
    items, total = await wsvc.list_initiated(db, tenant_id, user.get("sub"), pageNo, pageSize, filters=filters)
    return ok({"items": items, "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.get("/instances/cc")
async def my_cc(pageNo: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100),
                filters: wsvc.WfListFilters | None = Depends(_parse_list_filters),
                tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
                user: dict = Depends(get_current_user)):
    """抄送给我的。"""
    items, total = await wsvc.list_cc(db, tenant_id, user.get("sub"), pageNo, pageSize, filters=filters)
    return ok({"items": items, "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.get("/instances/filter-options")
async def filter_options(
    process_definition_id: str | None = Query(None, description="指定流程时返回该表单可筛字段"),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _u=Depends(get_current_user),
):
    """审批中心筛选项：已发布流程、常见节点名、流程表单字段。"""
    return ok(await wsvc.list_filter_options(db, tenant_id, process_definition_id=process_definition_id))


@router.get("/instances/by-biz")
async def instance_by_biz(
    biz_type: str = Query(..., min_length=1),
    biz_id: str = Query(..., min_length=1),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """业务详情页：按业务单据查最新流程实例（含 timeline / flow_steps）。无则 data=null。"""
    detail = await wsvc.find_latest_instance_by_biz(
        db, tenant_id, biz_type, biz_id,
        viewer_id=user.get("sub"), viewer_perms=user.get("permissions"),
    )
    return ok(detail)


@router.get("/instances/by-form-instance")
async def instance_by_form_instance(
    form_instance_id: str = Query(..., min_length=1),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """表单详情：按 form_instance_id 查最新流程实例。无则 data=null。"""
    detail = await wsvc.find_latest_instance_by_form_instance(
        db, tenant_id, form_instance_id,
        viewer_id=user.get("sub"), viewer_perms=user.get("permissions"),
    )
    return ok(detail)


@router.get("/instances/{instance_id}")
async def instance_detail(
    instance_id: str,
    task_id: str | None = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return ok(await wsvc.get_instance_detail(
        db, tenant_id, instance_id,
        viewer_id=user.get("sub"), task_id=task_id,
        viewer_perms=user.get("permissions"),
    ))


@router.post("/tasks/{task_id}/act")
async def act_task(task_id: str, body: ws.WfActRequest, tenant_id: str = Depends(get_tenant_id),
                   db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    await WorkflowEngine(db, tenant_id).act(
        task_id, user, body.action, body.opinion,
        body.transfer_to, body.to_node_id, body.field_updates,
    )
    return ok(None)


@router.post("/tasks/{task_id}/end")
async def end_process_by_task(
    task_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """修订待办入口：手动结束所属流程（取消修订待办）。"""
    await WorkflowEngine(db, tenant_id).end_process_by_task(task_id, user)
    return ok(None)


@router.post("/instances/{instance_id}/comments")
async def add_comment(
    instance_id: str,
    body: ws.WfCommentRequest,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """发表数据评论（对齐简道云），不推进/不完结审批。"""
    await WorkflowEngine(db, tenant_id).add_comment(instance_id, user, body.content)
    return ok(None)


@router.post("/instances/{instance_id}/withdraw")
async def withdraw(instance_id: str, tenant_id: str = Depends(get_tenant_id),
                   db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    await WorkflowEngine(db, tenant_id).withdraw(instance_id, user)
    return ok(None)


@router.post("/instances/{instance_id}/end")
async def end_process(
    instance_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """手动结束流程：进行中终止，或驳回/撤回后关闭修订待办。"""
    await WorkflowEngine(db, tenant_id).end_process(instance_id, user)
    return ok(None)


@router.post("/instances/{instance_id}/resubmit")
async def resubmit(instance_id: str, tenant_id: str = Depends(get_tenant_id),
                   db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    """已撤回/已驳回：发起人重新发起审批（新建流程实例）。"""
    inst = await WorkflowEngine(db, tenant_id).resubmit(instance_id, user)
    return ok({"id": inst.id, "status": inst.status, "title": inst.title})


@router.post("/instances/{instance_id}/urge")
async def urge(instance_id: str, tenant_id: str = Depends(get_tenant_id),
               db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    """催办: 发起人提醒当前待办人尽快处理。"""
    n = await WorkflowEngine(db, tenant_id).urge(instance_id, user)
    return ok({"notified": n})


@router.get("/instances/{instance_id}/activate-nodes")
async def activate_nodes(
    instance_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    # manage 可设计流程，视为包含激活；兼容登录 JWT 尚未带上新权限码的情况
    _u=Depends(require_any_permission("workflow:activate", "workflow:manage")),
):
    """可激活节点列表（开始 + 审批）。"""
    return ok(await wsvc.get_activate_nodes(db, tenant_id, instance_id))


@router.post("/instances/{instance_id}/activate")
async def activate_instance(
    instance_id: str,
    body: ws.WfActivateRequest,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_any_permission("workflow:activate", "workflow:manage")),
):
    """激活已结束流程：跳到指定开始/审批节点（同实例）。"""
    inst = await WorkflowEngine(db, tenant_id).activate(instance_id, user, body.to_node_id)
    return ok({"id": inst.id, "status": inst.status, "title": inst.title})


@router.get("/biz-fields/{biz_type}")
async def biz_fields(biz_type: str, _u=Depends(get_current_user)):
    """业务类型审批流的可用业务字段(供条件分支/字段选择;业务流无表单时使用)。"""
    from app.domains.lowcode.biz_field_catalog import get_catalog
    return ok(get_catalog(biz_type))


# ==================== 代理审批(委托) ====================

@router.get("/agents")
async def list_my_agents(tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
                         user: dict = Depends(get_current_user)):
    """我设置的代理（谁在某时段代我审批）。"""
    return ok(await wsvc.list_agents(db, tenant_id, user.get("sub")))


@router.post("/agents")
async def create_my_agent(body: ws.WfAgentCreate, tenant_id: str = Depends(get_tenant_id),
                          db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    """设置代理：本人在 [start,end] 期间由 agent_id 代为审批。"""
    ua = await wsvc.create_agent(db, tenant_id, user.get("sub"), body.agent_id,
                                 body.start_time, body.end_time, body.note)
    return ok({"id": ua.id})


@router.delete("/agents/{agent_row_id}")
async def delete_my_agent(agent_row_id: str, tenant_id: str = Depends(get_tenant_id),
                          db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    await wsvc.delete_agent(db, tenant_id, agent_row_id, user.get("sub"))
    return ok(None)
