"""扩展平台 — 审批流程引擎 API。前缀 /api/v1/lc/wf。

- 流程定义设计/管理: workflow:view / workflow:manage
- 运行时(发起/待办/审批): 登录即可,授权在引擎内做行级校验(assignee/initiator)。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, get_current_user, require_permissions
from app.common.schemas import ok
from app.domains.lowcode import workflow_schemas as ws, workflow_service as wsvc
from app.domains.lowcode.workflow_engine import WorkflowEngine

router = APIRouter(prefix="/api/v1/lc/wf", tags=["扩展平台-审批流程"])


def _def_dict(d):
    return ws.WfDefinitionOut.model_validate(d).model_dump()


def _ver_dict(v):
    return ws.WfVersionOut.model_validate(v).model_dump(mode="json")


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
                  tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
                  user: dict = Depends(get_current_user)):
    items, total = await wsvc.list_todo(db, tenant_id, user.get("sub"), pageNo, pageSize)
    return ok({"items": items, "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.get("/tasks/done")
async def my_done(pageNo: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100),
                  tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
                  user: dict = Depends(get_current_user)):
    items, total = await wsvc.list_done(db, tenant_id, user.get("sub"), pageNo, pageSize)
    return ok({"items": items, "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.get("/instances/mine")
async def my_initiated(pageNo: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100),
                       tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
                       user: dict = Depends(get_current_user)):
    items, total = await wsvc.list_initiated(db, tenant_id, user.get("sub"), pageNo, pageSize)
    return ok({"items": items, "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.get("/instances/{instance_id}")
async def instance_detail(instance_id: str, tenant_id: str = Depends(get_tenant_id),
                          db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    return ok(await wsvc.get_instance_detail(db, tenant_id, instance_id))


@router.post("/tasks/{task_id}/act")
async def act_task(task_id: str, body: ws.WfActRequest, tenant_id: str = Depends(get_tenant_id),
                   db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    await WorkflowEngine(db, tenant_id).act(task_id, user, body.action, body.opinion,
                                            body.transfer_to, body.to_node_id)
    return ok(None)


@router.post("/instances/{instance_id}/withdraw")
async def withdraw(instance_id: str, tenant_id: str = Depends(get_tenant_id),
                   db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    await WorkflowEngine(db, tenant_id).withdraw(instance_id, user)
    return ok(None)


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
