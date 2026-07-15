"""流程结果回写到既有业务单据(灰度替换旧 approval 引擎的关键桥接)。

当 wf_process_instance 绑定了业务单据(biz_type/biz_id)时,流程完成/驳回后按 REGISTRY
把结果写回业务表的状态列。表名/列名来自白名单 REGISTRY(防注入),值走绑定参数。
此机制与旧 ApprovalPolicy/ApprovalFlow 并存,可按 biz_type 逐个灰度切换,保留回滚。
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# biz_type -> {table, status_col, approved, rejected}
# 覆盖旧 approval 引擎 _on_approval_completed/_rejected 的全部 biz_type，保证任一业务
# 灰度切换到新引擎后，完成/驳回都能把状态回写到对应业务表（值与旧引擎保持一致）。
REGISTRY: dict[str, dict[str, str]] = {
    "order": {"table": "orders", "status_col": "status", "approved": "confirmed", "rejected": "cancelled"},
    "lead": {"table": "leads", "status_col": "review_status", "approved": "approved", "rejected": "rejected"},
    "service_ticket": {"table": "service_tickets", "status_col": "status", "approved": "processing", "rejected": "rejected"},
    "quote_version": {"table": "quote_versions", "status_col": "status", "approved": "approved", "rejected": "rejected"},
    "contract_version": {"table": "contract_versions", "status_col": "status", "approved": "approved", "rejected": "rejected"},
    "change_request": {"table": "change_requests", "status_col": "status", "approved": "approved", "rejected": "rejected"},
    "solution": {"table": "solutions", "status_col": "status", "approved": "approved", "rejected": "rejected"},
}


def supported_biz_types() -> list[str]:
    return list(REGISTRY.keys())


async def writeback(db: AsyncSession, tenant_id: str, biz_type: str, biz_id: str, flow_status: str) -> None:
    """flow_status: completed / rejected。按 REGISTRY 更新业务单据状态列。未注册则忽略。"""
    reg = REGISTRY.get(biz_type)
    if not reg or not biz_id:
        return
    val = reg["approved"] if flow_status == "completed" else reg["rejected"] if flow_status == "rejected" else None
    if val is None:
        return
    await db.execute(
        text(f"UPDATE {reg['table']} SET {reg['status_col']} = :val WHERE id = :bid AND tenant_id = :tenant"),
        {"val": val, "bid": biz_id, "tenant": tenant_id},
    )
