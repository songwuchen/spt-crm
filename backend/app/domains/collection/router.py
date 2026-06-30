from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.common.export import build_excel, excel_response
from app.domains.collection import service
from app.domains.collection.schemas import (
    DebtTransferCreate, DebtTransferUpdate, DebtTransferClaim, CollectionFollowUpCreate,
)

router = APIRouter(prefix="/api/v1/collection", tags=["应收清欠"])

BUCKET_LABEL = {"d0_30": "0-30天", "d31_60": "31-60天", "d61_90": "61-90天", "d91_180": "91-180天", "d180p": "180天以上"}
TYPE_LABEL = {
    "sales_to_collection": "销售转清欠", "collection_to_sales": "清欠转回销售",
    "to_legal": "转法务", "dept_to_dept": "部门间移交", "finance_to_litigation": "财务转诉讼",
}
STATUS_LABEL = {"pending": "待接收", "claimed": "已接收", "withdrawn": "已撤回", "done": "已完成", "rejected": "已驳回"}


def _transfer_dict(t) -> dict:
    return {
        "id": t.id, "transfer_no": t.transfer_no,
        "customer_id": t.customer_id, "customer_name": t.customer_name,
        "transfer_type": t.transfer_type,
        "from_department_name": t.from_department_name, "from_owner_name": t.from_owner_name,
        "to_department_id": t.to_department_id, "to_department_name": t.to_department_name,
        "debt_amount": float(t.debt_amount) if t.debt_amount is not None else None,
        "contact": t.contact, "contact_phone": t.contact_phone,
        "debt_note": t.debt_note, "reason": t.reason,
        "deadline": str(t.deadline) if t.deadline else None,
        "assess_date": str(t.assess_date) if t.assess_date else None,
        "commitment": t.commitment, "status": t.status,
        "claimed_by_name": t.claimed_by_name, "claimed_department_name": t.claimed_department_name,
        "claimed_at": t.claimed_at.isoformat() if t.claimed_at else None,
        "created_by_name": t.created_by_name,
        "created_at": t.created_at.isoformat() if t.created_at else "",
    }


def _followup_dict(f) -> dict:
    return {
        "id": f.id, "customer_id": f.customer_id, "customer_name": f.customer_name,
        "transfer_id": f.transfer_id,
        "follow_date": str(f.follow_date) if f.follow_date else None,
        "method": f.method, "feedback": f.feedback,
        "expected_date": str(f.expected_date) if f.expected_date else None,
        "amount_promised": float(f.amount_promised) if f.amount_promised is not None else None,
        "next_action": f.next_action, "created_by_name": f.created_by_name,
        "created_at": f.created_at.isoformat() if f.created_at else "",
    }


# ---------- Aging ----------
@router.get("/aging")
async def aging(tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
                _u=Depends(require_permissions("collection:view"))):
    return ok(await service.aging_report(db, tenant_id))


@router.get("/aging/export/excel")
async def aging_export(tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
                       _u=Depends(require_permissions("collection:view"))):
    report = await service.aging_report(db, tenant_id)
    headers = ["客户", "负责人", "合同应收", "已回款", "应收余额"] + [BUCKET_LABEL[b] for b in report["buckets"]]
    rows = []
    for r in report["rows"]:
        rows.append([
            r["customer_name"], r.get("owner_name") or "",
            r["contract_total"], r["received_total"], r["outstanding"],
        ] + [r[b] for b in report["buckets"]])
    buf = build_excel("应收账龄", headers, rows)
    return excel_response(buf, "ar_aging.xlsx")


@router.post("/aging/notify")
async def aging_notify(tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
                       _u=Depends(require_permissions("collection:view"))):
    n = await service.check_overdue_receivables(db, tenant_id)
    return ok({"notified": n})


# ---------- Follow-ups ----------
@router.get("/followups")
async def list_followups(customer_id: str = Query(None), transfer_id: str = Query(None),
                         pageNo: int = Query(1, ge=1), pageSize: int = Query(50, ge=1, le=200),
                         tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
                         _u=Depends(require_permissions("collection:view"))):
    items, total = await service.list_followups(db, tenant_id, customer_id, transfer_id, pageNo, pageSize)
    return ok({"items": [_followup_dict(f) for f in items], "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.post("/followups")
async def create_followup(body: CollectionFollowUpCreate, tenant_id: str = Depends(get_tenant_id),
                          db: AsyncSession = Depends(get_db), u=Depends(require_permissions("collection:edit"))):
    return ok(_followup_dict(await service.create_followup(db, tenant_id, body, u)))


# ---------- Transfers ----------
@router.get("/transfers")
async def list_transfers(pageNo: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100),
                         status: str = Query(None), keyword: str = Query(None), to_department_id: str = Query(None),
                         filter: str = Query(None, description="高级筛选 FilterDsl(JSON)"),
                         sort_by: str = Query(None), sort_order: str = Query(None),
                         tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
                         current_user: dict = Depends(require_permissions("collection:view"))):
    items, total = await service.list_transfers(db, tenant_id, pageNo, pageSize, status, keyword, to_department_id,
                                                adv_filter=filter, sort_by=sort_by, sort_order=sort_order,
                                                current_user=current_user)
    return ok({"items": [_transfer_dict(t) for t in items], "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.post("/transfers")
async def create_transfer(body: DebtTransferCreate, tenant_id: str = Depends(get_tenant_id),
                          db: AsyncSession = Depends(get_db), u=Depends(require_permissions("collection:edit"))):
    return ok(_transfer_dict(await service.create_transfer(db, tenant_id, body, u)))


@router.get("/transfers/{transfer_id}")
async def get_transfer(transfer_id: str, tenant_id: str = Depends(get_tenant_id),
                       db: AsyncSession = Depends(get_db), _u=Depends(require_permissions("collection:view"))):
    return ok(_transfer_dict(await service.get_transfer(db, tenant_id, transfer_id)))


@router.put("/transfers/{transfer_id}")
async def update_transfer(transfer_id: str, body: DebtTransferUpdate, tenant_id: str = Depends(get_tenant_id),
                          db: AsyncSession = Depends(get_db), u=Depends(require_permissions("collection:edit"))):
    return ok(_transfer_dict(await service.update_transfer(db, tenant_id, transfer_id, body, u)))


@router.post("/transfers/{transfer_id}/claim")
async def claim_transfer(transfer_id: str, body: DebtTransferClaim, tenant_id: str = Depends(get_tenant_id),
                         db: AsyncSession = Depends(get_db), u=Depends(require_permissions("collection:edit"))):
    return ok(_transfer_dict(await service.claim_transfer(db, tenant_id, transfer_id, body, u)))


@router.post("/transfers/{transfer_id}/withdraw")
async def withdraw_transfer(transfer_id: str, tenant_id: str = Depends(get_tenant_id),
                            db: AsyncSession = Depends(get_db), u=Depends(require_permissions("collection:edit"))):
    return ok(_transfer_dict(await service.withdraw_transfer(db, tenant_id, transfer_id, u)))


@router.delete("/transfers/{transfer_id}")
async def delete_transfer(transfer_id: str, tenant_id: str = Depends(get_tenant_id),
                          db: AsyncSession = Depends(get_db), u=Depends(require_permissions("collection:manage"))):
    await service.delete_transfer(db, tenant_id, transfer_id, u)
    return ok()
