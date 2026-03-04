from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions, get_current_user
from app.common.schemas import ok
from app.domains.approval import service
from app.domains.approval.schemas import ApprovalSubmit, ApprovalResubmit, ApprovalDecide, ApprovalWithdraw, ApprovalDelegate, ApprovalBulkDecide

router = APIRouter(tags=["审批管理"])


def _flow_dict(f) -> dict:
    return {
        "id": f.id,
        "biz_type": f.biz_type,
        "biz_id": f.biz_id,
        "title": f.title,
        "status": f.status,
        "approval_mode": f.approval_mode,
        "current_node": f.current_node,
        "total_nodes": f.total_nodes,
        "submitted_by_id": f.submitted_by_id,
        "submitted_by_name": f.submitted_by_name,
        "parent_flow_id": f.parent_flow_id,
        "revision_no": f.revision_no,
        "created_at": f.created_at.isoformat() if f.created_at else "",
        "updated_at": f.updated_at.isoformat() if f.updated_at else "",
    }


def _task_dict(t) -> dict:
    return {
        "id": t.id,
        "flow_id": t.flow_id,
        "node_order": t.node_order,
        "assignee_id": t.assignee_id,
        "assignee_name": t.assignee_name,
        "status": t.status,
        "comment": t.comment,
        "decided_at": t.decided_at,
        "created_at": t.created_at.isoformat() if t.created_at else "",
    }


@router.get("/api/v1/approvals")
async def list_flows(
    biz_type: str | None = Query(None), biz_id: str | None = Query(None),
    status: str | None = Query(None),
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    items = await service.list_flows(db, tenant_id, biz_type=biz_type, biz_id=biz_id, status=status)
    return ok([_flow_dict(f) for f in items])


@router.post("/api/v1/approvals")
async def submit_approval(
    body: ApprovalSubmit,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    f = await service.submit_approval(db, tenant_id, body, current_user)
    return ok(_flow_dict(f))


@router.get("/api/v1/approvals/my/pending")
async def my_pending(
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    rows = await service.list_my_pending(db, tenant_id, current_user["sub"])
    result = []
    for task, flow in rows:
        d = _task_dict(task)
        d["flow"] = _flow_dict(flow)
        result.append(d)
    return ok(result)


@router.get("/api/v1/approvals/statistics")
async def statistics(
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    data = await service.get_statistics(db, tenant_id, date_from=date_from, date_to=date_to)
    return ok(data)


@router.get("/api/v1/approvals/{flow_id}")
async def get_flow(
    flow_id: str,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    f = await service.get_flow(db, tenant_id, flow_id)
    tasks = await service.get_flow_tasks(db, tenant_id, flow_id)
    data = _flow_dict(f)
    data["tasks"] = [_task_dict(t) for t in tasks]
    # Resolve business detail
    biz_detail = await service._resolve_biz_detail(db, tenant_id, f.biz_type, f.biz_id)
    if biz_detail:
        data["biz_detail"] = biz_detail
    return ok(data)


@router.post("/api/v1/approvals/{flow_id}/withdraw")
async def withdraw(
    flow_id: str, body: ApprovalWithdraw,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    f = await service.withdraw_flow(db, tenant_id, flow_id, body.reason, current_user)
    return ok(_flow_dict(f))


@router.post("/api/v1/approvals/{flow_id}/resubmit")
async def resubmit(
    flow_id: str, body: ApprovalResubmit,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    f = await service.resubmit_approval(db, tenant_id, flow_id, body, current_user)
    return ok(_flow_dict(f))


@router.post("/api/v1/approval_tasks/{task_id}/decide")
async def decide(
    task_id: str, body: ApprovalDecide,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    f = await service.decide(db, tenant_id, task_id, body.action, body.comment, current_user)
    return ok(_flow_dict(f))


@router.post("/api/v1/approval_tasks/{task_id}/delegate")
async def delegate(
    task_id: str, body: ApprovalDelegate,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    t = await service.delegate_task(db, tenant_id, task_id, body.target_user_id, body.reason, current_user)
    return ok(_task_dict(t))


@router.post("/api/v1/approval_tasks/bulk_decide")
async def bulk_decide(
    body: ApprovalBulkDecide,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    results = await service.bulk_decide(db, tenant_id, body.task_ids, body.action, body.comment, current_user)
    return ok(results)
