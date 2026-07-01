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


async def notify_task_assigned(db: AsyncSession, tenant_id: str, task_title: str,
                                assignee_id: str, user_name: str, task_id: str, count: int = 1):
    """Notify assignee when a task is assigned to them by someone else."""
    if count > 1:
        title = f"{user_name} 给您分配了 {count} 个任务"
        content = f"其中包括「{task_title}」等"
    else:
        title = f"您有新任务待处理: {task_title}"
        content = f"分配人: {user_name}"
    await send_notification(
        db, tenant_id, recipient_id=assignee_id,
        type="task_assigned",
        title=title, content=content,
        biz_type="task", biz_id=task_id, sender_name=user_name,
    )


async def notify_lead_assigned(db: AsyncSession, tenant_id: str, lead_name: str,
                                assignee_id: str, user_name: str, lead_id: str, count: int = 1):
    """Notify new owner when a lead is (re)assigned to them by someone else."""
    if count > 1:
        title = f"{user_name} 给您分配了 {count} 条线索"
        content = f"其中包括「{lead_name}」等，请及时跟进"
    else:
        title = f"您有新线索待跟进: {lead_name}"
        content = f"分配人: {user_name}"
    await send_notification(
        db, tenant_id, recipient_id=assignee_id,
        type="lead_assigned",
        title=title, content=content,
        biz_type="lead", biz_id=lead_id, sender_name=user_name,
    )


async def notify_customer_assigned(db: AsyncSession, tenant_id: str, customer_name: str,
                                    assignee_id: str, user_name: str, customer_id: str):
    """Notify new owner when a customer is assigned/transferred to them by someone else."""
    await send_notification(
        db, tenant_id, recipient_id=assignee_id,
        type="customer_assigned",
        title=f"您有新客户待跟进: {customer_name}",
        content=f"分配人: {user_name}",
        biz_type="customer", biz_id=customer_id, sender_name=user_name,
    )


async def notify_project_assigned(db: AsyncSession, tenant_id: str, project_name: str,
                                   assignee_id: str, user_name: str, project_id: str):
    """Notify new owner when an opportunity is (re)assigned/transferred to them."""
    await send_notification(
        db, tenant_id, recipient_id=assignee_id,
        type="project_assigned",
        title=f"您有新商机待跟进: {project_name}",
        content=f"分配人: {user_name}",
        biz_type="project", biz_id=project_id, sender_name=user_name,
    )


async def notify_order_assigned(db: AsyncSession, tenant_id: str, order_no: str,
                                 assignee_id: str, user_name: str, order_id: str):
    """Notify owner when an order is created/assigned to them (生成待办，推送给负责人)."""
    await send_notification(
        db, tenant_id, recipient_id=assignee_id,
        type="order_assigned",
        title=f"您有新订单待处理: {order_no}",
        content=f"创建人: {user_name}",
        biz_type="order", biz_id=order_id, sender_name=user_name,
    )


async def notify_milestone_created(db: AsyncSession, tenant_id: str, project_name: str,
                                    milestone_name: str, recipient_id: str, user_name: str, project_id: str):
    """Notify the responsible person when a delivery milestone is created (issue #62)."""
    await send_notification(
        db, tenant_id, recipient_id=recipient_id,
        type="milestone_created",
        title=f"新交付里程碑「{milestone_name}」",
        content=f"所属商机: {project_name}\n创建人: {user_name}\n请关注交付进度。",
        biz_type="project", biz_id=project_id, sender_name=user_name,
    )


_MILESTONE_STATUS_LABELS = {
    "not_start": "未开始", "doing": "进行中", "done": "已完成", "delayed": "已延期",
}


async def notify_milestone_status_changed(db: AsyncSession, tenant_id: str, project_name: str,
                                          milestone_name: str, old_status: str, new_status: str,
                                          recipient_id: str, user_name: str, project_id: str):
    """Notify the responsible person when a delivery milestone's status changes (issue #76)."""
    old_label = _MILESTONE_STATUS_LABELS.get(old_status, old_status)
    new_label = _MILESTONE_STATUS_LABELS.get(new_status, new_status)
    await send_notification(
        db, tenant_id, recipient_id=recipient_id,
        type="milestone_status_changed",
        title=f"交付里程碑「{milestone_name}」状态更新为{new_label}",
        content=f"所属商机: {project_name}\n状态: {old_label} → {new_label}\n操作人: {user_name}",
        biz_type="project", biz_id=project_id, sender_name=user_name,
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
