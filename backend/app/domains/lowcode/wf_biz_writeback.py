"""流程结果回写到既有业务单据(灰度替换旧 approval 引擎的关键桥接)。

当 wf_process_instance 绑定了业务单据(biz_type/biz_id)时,流程完成/驳回后按 REGISTRY
把结果写回业务表的状态列。表名/列名来自白名单 REGISTRY(防注入),值走绑定参数。
此机制与旧 ApprovalPolicy/ApprovalFlow 并存,可按 biz_type 逐个灰度切换,保留回滚。
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# biz_type -> {table, status_col, approved, rejected, withdrawn?, submitted?, reason_col?}
# 覆盖旧 approval 引擎 _on_approval_completed/_rejected 的全部 biz_type，保证任一业务
# 灰度切换到新引擎后，完成/驳回都能把状态回写到对应业务表（值与旧引擎保持一致）。
# reason_col(可选): 驳回意见落库的列。驳回时写入审批意见、通过时清空，
# 与旧引擎 _on_approval_rejected/_completed 对 leads.reject_reason 的处理一致。
# withdrawn: 发起人撤回后回写到可再提交状态；submitted: 重新发起时置为审批中。
REGISTRY: dict[str, dict[str, str]] = {
    "order": {"table": "orders", "status_col": "status", "approved": "confirmed", "rejected": "cancelled"},
    "lead": {"table": "leads", "status_col": "review_status", "approved": "approved", "rejected": "rejected",
             "withdrawn": "pending", "submitted": "pending", "reason_col": "reject_reason"},
    "service_ticket": {"table": "service_tickets", "status_col": "status", "approved": "processing", "rejected": "rejected",
                       "withdrawn": "draft", "submitted": "submitted"},
    "quote_version": {"table": "quote_versions", "status_col": "status", "approved": "approved", "rejected": "rejected",
                      "withdrawn": "draft", "submitted": "submitted"},
    "contract_version": {"table": "contract_versions", "status_col": "status", "approved": "approved", "rejected": "rejected",
                         "withdrawn": "draft", "submitted": "submitted"},
    "contract_review": {"table": "contract_reviews", "status_col": "status", "approved": "approved", "rejected": "rejected",
                        "withdrawn": "draft", "submitted": "submitted"},
    "tech_agreement_review": {"table": "tech_agreement_reviews", "status_col": "status", "approved": "approved", "rejected": "rejected",
                              "withdrawn": "draft", "submitted": "submitted"},
    "change_request": {"table": "change_requests", "status_col": "status", "approved": "approved", "rejected": "rejected",
                       "withdrawn": "draft", "submitted": "submitted"},
    "solution": {"table": "solutions", "status_col": "status", "approved": "approved", "rejected": "rejected",
                 "withdrawn": "draft", "submitted": "submitted"},
}


def supported_biz_types() -> list[str]:
    return list(REGISTRY.keys())


async def _lead_reset_reactivation_cycle(db: AsyncSession, tenant_id: str, lead_id: str) -> None:
    """收录/袭击通过后重置 180 天重激活计时。"""
    await db.execute(
        text(
            "UPDATE leads SET cycle_anchor_at = NOW(), reactivation_status = 'none', "
            "reactivation_notified_at = NULL "
            "WHERE id = :bid AND tenant_id = :tenant"
        ),
        {"bid": lead_id, "tenant": tenant_id},
    )


async def _lead_reactivation_on_reject(db: AsyncSession, tenant_id: str, lead_id: str) -> None:
    """重激活提交情报审被回退时，退回填表人/申报人待办态。"""
    await db.execute(
        text(
            "UPDATE leads SET reactivation_status = CASE "
            "WHEN reactivation_status = 'pending_review' AND created_by_id IS NOT NULL "
            "THEN 'awaiting_filler' "
            "WHEN reactivation_status = 'pending_review' THEN 'awaiting_reporter' "
            "ELSE reactivation_status END "
            "WHERE id = :bid AND tenant_id = :tenant"
        ),
        {"bid": lead_id, "tenant": tenant_id},
    )


async def writeback(
    db: AsyncSession, tenant_id: str, biz_type: str, biz_id: str, flow_status: str,
    reason: str | None = None,
) -> None:
    """flow_status: completed / rejected / withdrawn / submitted。按 REGISTRY 更新业务单据状态列。未注册则忽略。

    reason 为审批意见：注册了 reason_col 的业务，驳回时写入该列、通过时清空。
    """
    reg = REGISTRY.get(biz_type)
    if not reg or not biz_id:
        return
    if flow_status == "completed":
        val = reg["approved"]
    elif flow_status == "rejected":
        val = reg["rejected"]
    elif flow_status == "withdrawn":
        val = reg.get("withdrawn")
    elif flow_status == "submitted":
        val = reg.get("submitted")
    else:
        val = None
    if val is None:
        return
    # 线索袭击：intel_review 会先把 review_status 写成 attacked，通过回写时不得覆盖为 approved
    if biz_type == "lead" and flow_status == "completed":
        cur = (await db.execute(
            text("SELECT review_status FROM leads WHERE id = :bid AND tenant_id = :tenant"),
            {"bid": biz_id, "tenant": tenant_id},
        )).scalar_one_or_none()
        if cur == "attacked":
            reason_col = reg.get("reason_col")
            if reason_col:
                await db.execute(
                    text(f"UPDATE leads SET {reason_col} = NULL WHERE id = :bid AND tenant_id = :tenant"),
                    {"bid": biz_id, "tenant": tenant_id},
                )
            await _lead_reset_reactivation_cycle(db, tenant_id, biz_id)
            return
    sets = [f"{reg['status_col']} = :val"]
    params: dict[str, object] = {"val": val, "bid": biz_id, "tenant": tenant_id}
    reason_col = reg.get("reason_col")
    if reason_col:
        # 驳回写入意见；通过时清空上一次的驳回原因，避免详情页残留旧原因
        sets.append(f"{reason_col} = :reason")
        params["reason"] = reason if flow_status == "rejected" else None
    await db.execute(
        text(f"UPDATE {reg['table']} SET {', '.join(sets)} WHERE id = :bid AND tenant_id = :tenant"),
        params,
    )
    if biz_type == "lead" and flow_status == "completed":
        await _lead_reset_reactivation_cycle(db, tenant_id, biz_id)
    elif biz_type == "lead" and flow_status == "rejected":
        await _lead_reactivation_on_reject(db, tenant_id, biz_id)
