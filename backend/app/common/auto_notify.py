"""Auto-notification helpers for key business events."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.notification.service import send_notification


async def notify_stage_advance(db: AsyncSession, tenant_id: str, project_name: str,
                                from_stage: str, to_stage: str, owner_id: str, user_name: str):
    """Notify project owner when stage advances."""
    await send_notification(
        db, tenant_id, recipient_id=owner_id,
        type="stage_advance",
        title=f"商机「{project_name}」阶段推进: {from_stage} → {to_stage}",
        content=f"操作人: {user_name}",
        biz_type="project", sender_name=user_name,
    )


async def notify_contract_signed(db: AsyncSession, tenant_id: str, contract_no: str,
                                  owner_id: str, user_name: str, contract_id: str):
    """Notify project owner when contract is signed."""
    await send_notification(
        db, tenant_id, recipient_id=owner_id,
        type="contract_signed",
        title=f"合同「{contract_no}」已签署",
        content=f"签署人: {user_name}",
        biz_type="contract", biz_id=contract_id, sender_name=user_name,
    )


async def notify_ticket_assigned(db: AsyncSession, tenant_id: str, ticket_no: str,
                                  assignee_id: str, user_name: str, ticket_id: str):
    """Notify assignee when a service ticket is assigned to them."""
    await send_notification(
        db, tenant_id, recipient_id=assignee_id,
        type="ticket_assigned",
        title=f"售后工单「{ticket_no}」已分配给您",
        content=f"分配人: {user_name}",
        biz_type="service_ticket", biz_id=ticket_id, sender_name=user_name,
    )


async def notify_approval_submitted(db: AsyncSession, tenant_id: str, approver_id: str,
                                     title: str, user_name: str, flow_id: str):
    """Notify approver when an approval is submitted to them."""
    await send_notification(
        db, tenant_id, recipient_id=approver_id,
        type="approval_pending",
        title=f"您有新的审批待处理: {title}",
        content=f"提交人: {user_name}",
        biz_type="approval", biz_id=flow_id, sender_name=user_name,
    )


async def notify_payment_overdue(db: AsyncSession, tenant_id: str, plan_no: str,
                                  amount: float, owner_id: str, project_id: str):
    """Notify project owner when a payment plan becomes overdue."""
    await send_notification(
        db, tenant_id, recipient_id=owner_id,
        type="system",
        title=f"回款计划「{plan_no}」已逾期",
        content=f"金额: ¥{amount:,.2f}",
        biz_type="project", biz_id=project_id,
    )


async def notify_payment_received(db: AsyncSession, tenant_id: str, amount: float,
                                    owner_id: str, user_name: str, project_id: str):
    """Notify project owner when a payment record is created."""
    await send_notification(
        db, tenant_id, recipient_id=owner_id,
        type="system",
        title=f"收到回款 ¥{amount:,.2f}",
        content=f"录入人: {user_name}",
        biz_type="project", biz_id=project_id, sender_name=user_name,
    )


async def notify_project_won_lost(db: AsyncSession, tenant_id: str, project_name: str,
                                    status: str, owner_id: str, user_name: str, project_id: str):
    """Notify project owner when project is marked won or lost."""
    label = "赢单" if status == "won" else "丢单"
    await send_notification(
        db, tenant_id, recipient_id=owner_id,
        type="system",
        title=f"商机「{project_name}」已{label}",
        content=f"操作人: {user_name}",
        biz_type="project", biz_id=project_id, sender_name=user_name,
    )
