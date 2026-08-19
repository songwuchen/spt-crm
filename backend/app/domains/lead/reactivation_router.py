"""180天项目激活：独立列表/详情（对齐简道云「180天项目激活」数据管理）。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.error_codes import NOT_FOUND
from app.common.exceptions import BusinessException
from app.common.schemas import ok
from app.dependencies import get_db, get_tenant_id, require_permissions
from app.domains.lead import reactivation as react_svc

router = APIRouter(prefix="/api/v1/lead-reactivations", tags=["180天项目激活"])


@router.get("")
async def list_lead_reactivations(
    pageNo: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
    keyword: str | None = Query(None, description="项目编号/名称/公司"),
    flow_status: str | None = Query(
        None,
        description="流程状态筛选：active=进行中 completed=已结束 closed=关闭",
    ),
    reactivation_status: str | None = Query(
        None,
        description="当前轮重激活状态（awaiting_reporter/awaiting_filler/pending_review 等）",
    ),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("lead:view")),
):
    items, total = await react_svc.list_reactivation_records_page(
        db, tenant_id,
        page_no=pageNo,
        page_size=pageSize,
        keyword=keyword,
        flow_status=flow_status,
        reactivation_status=reactivation_status,
    )
    return ok({"items": items, "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.get("/{record_id}")
async def get_lead_reactivation_detail(
    record_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("lead:view")),
):
    row = await react_svc.get_reactivation_record_detail(db, tenant_id, record_id)
    if not row:
        raise BusinessException(code=NOT_FOUND, message="180天激活记录不存在")
    return ok(row)
