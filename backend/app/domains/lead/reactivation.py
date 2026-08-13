"""线索 180 天循环重激活。

收录/袭击后从 cycle_anchor_at 起满 N 天 → 申报人待办填写近况；
暂缓/取消/落标 → 结束本轮；否则 → 填表人确认 → 信息情报部审批；
再收录/袭击后重新计时。张贺等配置姓名跳过申报人，直接给填表人。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import generate_uuid, utcnow
from app.domains.audit.service import log_action
from app.domains.lead.models import Lead

logger = logging.getLogger(__name__)

REACT_NONE = "none"
REACT_AWAITING_REPORTER = "awaiting_reporter"
REACT_AWAITING_FILLER = "awaiting_filler"
REACT_PENDING_REVIEW = "pending_review"
REACT_CLOSED = "closed"

# 选这些结果则流程结束，不再进情报审 / 不再自动重激活
CLOSE_PROJECT_STATUSES = frozenset({"暂缓", "暂停", "取消", "落标"})

TASK_BIZ_TYPE = "lead_reactivation"


def reactivation_days() -> int:
    return max(1, int(getattr(settings, "LEAD_REACTIVATION_DAYS", 180) or 180))


def skip_reporter_names() -> set[str]:
    raw = getattr(settings, "LEAD_REACT_SKIP_REPORTER_NAMES", "") or ""
    return {x.strip() for x in raw.split(",") if x.strip()}


def should_skip_reporter(lead: Lead) -> bool:
    """申报人姓名在跳过名单（如张贺）时，重激活不进申报人待办。"""
    names = skip_reporter_names()
    if not names:
        return False
    name = (lead.reporter_name or "").strip()
    return bool(name and name in names)


def mark_cycle_reset(lead: Lead, *, now: datetime | None = None) -> None:
    """收录/袭击后重置 180 天计时。"""
    lead.cycle_anchor_at = now or utcnow()
    lead.reactivation_status = REACT_NONE
    lead.reactivation_notified_at = None


def _anchor_of(lead: Lead) -> datetime | None:
    return lead.cycle_anchor_at or lead.reported_at or lead.created_at


async def _complete_open_tasks(db: AsyncSession, tenant_id: str, lead_id: str) -> None:
    from app.domains.task.models import UserTask
    await db.execute(
        update(UserTask).where(
            UserTask.tenant_id == tenant_id,
            UserTask.biz_type == TASK_BIZ_TYPE,
            UserTask.biz_id == lead_id,
            UserTask.is_completed == False,  # noqa: E712
        ).values(is_completed=True, status="done")
    )


async def _create_task_and_notify(
    db: AsyncSession, tenant_id: str, lead: Lead,
    *, assignee_id: str, assignee_name: str | None, stage: str,
) -> None:
    from app.domains.task.models import UserTask
    from app.domains.notification.service import send_notification

    await _complete_open_tasks(db, tenant_id, lead.id)
    title = f"线索重激活跟进: {(lead.lead_code + ' ') if lead.lead_code else ''}{lead.title}"
    if stage == REACT_AWAITING_FILLER:
        desc = (
            f"申报人已更新近况，请填表人核对后提交信息情报部审批。"
            f"项目状态：{lead.report_project_status or '-'}"
        )
    else:
        desc = (
            f"该线索自收录/袭击已满 {reactivation_days()} 天，请填写项目近况、跟进进度、"
            f"实地拜访情况与项目状态（暂缓/取消/落标将结束本轮；其他结果将进入审批）。"
        )
    task = UserTask(
        id=generate_uuid(),
        tenant_id=tenant_id,
        title=title,
        description=desc,
        priority="high",
        status="todo",
        assignee_id=assignee_id,
        assignee_name=assignee_name,
        created_by_id=None,
        created_by_name="系统",
        biz_type=TASK_BIZ_TYPE,
        biz_id=lead.id,
        biz_name=lead.title,
    )
    db.add(task)
    await db.flush()
    try:
        await send_notification(
            db=db,
            tenant_id=tenant_id,
            recipient_id=assignee_id,
            type="system",
            title=title,
            content=desc,
            biz_type="lead",
            biz_id=lead.id,
            sender_name="系统",
            extra_json={"reactivation": True, "stage": stage, "task_id": task.id},
        )
    except Exception as e:
        logger.warning("lead reactivation notify failed lead=%s: %s", lead.id, e)


def _resolve_assignee(lead: Lead, *, prefer_filler: bool) -> tuple[str | None, str | None, str]:
    """返回 (userignee_id, assignee_name, reactivation_status)。"""
    filler_id = lead.created_by_id
    filler_name = lead.created_by_name
    reporter_id = lead.reporter_id or lead.owner_id or filler_id
    reporter_name = lead.reporter_name or lead.owner_name or filler_name

    if prefer_filler or should_skip_reporter(lead):
        # 跳过申报人：优先填表人；填表人缺失或就是申报人本人时退到负责人
        if filler_id and filler_id != reporter_id:
            return filler_id, filler_name, REACT_AWAITING_FILLER
        if lead.owner_id and lead.owner_id != reporter_id:
            return lead.owner_id, lead.owner_name, REACT_AWAITING_FILLER
        if filler_id:
            return filler_id, filler_name, REACT_AWAITING_FILLER
        return reporter_id, reporter_name, REACT_AWAITING_REPORTER

    return reporter_id, reporter_name, REACT_AWAITING_REPORTER


async def activate_lead(db: AsyncSession, tenant_id: str, lead: Lead) -> bool:
    """对单条到期线索发起重激活待办。成功返回 True。"""
    if lead.is_deleted or lead.status == "discarded":
        return False
    if lead.review_status not in ("approved", "attacked"):
        return False
    if (lead.reactivation_status or REACT_NONE) not in (REACT_NONE,):
        return False

    assignee_id, assignee_name, stage = _resolve_assignee(lead, prefer_filler=False)
    if not assignee_id:
        logger.warning("lead reactivation skip (no assignee): %s", lead.id)
        return False

    if not lead.cycle_anchor_at:
        lead.cycle_anchor_at = _anchor_of(lead) or utcnow()
    lead.reactivation_status = stage
    lead.reactivation_notified_at = utcnow()
    lead.reactivation_round = int(lead.reactivation_round or 0) + 1
    await _create_task_and_notify(
        db, tenant_id, lead,
        assignee_id=assignee_id, assignee_name=assignee_name, stage=stage,
    )
    return True


async def scan_and_activate(db: AsyncSession, *, limit: int = 200) -> int:
    """扫描到期线索并起待办。由 reminder_worker 按日调用。"""
    days = reactivation_days()
    cutoff = utcnow() - timedelta(days=days)
    # 锚点优先 cycle_anchor_at，否则 reported_at / created_at
    anchor = func.coalesce(Lead.cycle_anchor_at, Lead.reported_at, Lead.created_at)
    q = (
        select(Lead)
        .where(
            Lead.is_deleted == False,  # noqa: E712
            Lead.status != "discarded",
            Lead.review_status.in_(("approved", "attacked")),
            or_(Lead.reactivation_status == REACT_NONE, Lead.reactivation_status.is_(None)),
            anchor.is_not(None),
            anchor <= cutoff,
        )
        .order_by(anchor.asc())
        .limit(limit)
    )
    leads = (await db.execute(q)).scalars().all()
    activated = 0
    for lead in leads:
        try:
            if await activate_lead(db, lead.tenant_id, lead):
                await db.commit()
                activated += 1
            else:
                await db.rollback()
        except Exception as e:
            logger.warning("activate lead %s failed: %s", lead.id, e)
            try:
                await db.rollback()
            except Exception:
                pass
    return activated


async def submit_reactivation(
    db: AsyncSession, tenant_id: str, lead_id: str, user: dict, data,
) -> Lead:
    """申报人/填表人提交重激活跟进。"""
    from app.common.error_codes import VALIDATION_ERROR, FORBIDDEN, BUSINESS_ERROR
    from app.common.exceptions import BusinessException
    from app.domains.lead import service as lead_service

    lead = await lead_service.get_lead(db, tenant_id, lead_id, user)
    status = lead.reactivation_status or REACT_NONE
    if status not in (REACT_AWAITING_REPORTER, REACT_AWAITING_FILLER):
        raise BusinessException(code=VALIDATION_ERROR, message="当前线索不在重激活待办阶段")

    uid = user.get("sub")
    if status == REACT_AWAITING_REPORTER:
        expected = lead.reporter_id or lead.owner_id or lead.created_by_id
    else:
        expected = lead.created_by_id or lead.reporter_id or lead.owner_id
    if not expected or expected != uid:
        # 管理员可代填
        roles = user.get("roles") or []
        if not ({"admin", "super_admin", "tenant_admin"} & set(roles)):
            raise BusinessException(code=FORBIDDEN, message="仅当前待办人可提交重激活跟进")

    project_status = (data.report_project_status or "").strip()
    if not project_status:
        raise BusinessException(code=VALIDATION_ERROR, message="请选择项目状态")

    lead.project_recent = (data.project_recent or "").strip() or None
    lead.follow_progress = (data.follow_progress or "").strip() or None
    lead.site_visit = (data.site_visit or "").strip() or None
    lead.report_project_status = project_status

    # 暂缓/取消/落标 → 结束
    if project_status in CLOSE_PROJECT_STATUSES:
        lead.reactivation_status = REACT_CLOSED
        await _complete_open_tasks(db, tenant_id, lead.id)
        await db.commit()
        await db.refresh(lead)
        await _notify_cycle_closed(db, tenant_id, lead)
        await log_action(
            db, tenant_id=tenant_id, user_id=user["sub"],
            user_name=user.get("real_name") or user.get("username"),
            action="reactivation_close", resource_type="lead", resource_id=lead.id,
            summary=f"重激活结束({project_status}): {lead.title}",
        )
        return lead

    # 申报人阶段且存在不同填表人 → 转填表人
    filler_id = lead.created_by_id
    if status == REACT_AWAITING_REPORTER and filler_id and filler_id != uid:
        lead.reactivation_status = REACT_AWAITING_FILLER
        await _create_task_and_notify(
            db, tenant_id, lead,
            assignee_id=filler_id, assignee_name=lead.created_by_name,
            stage=REACT_AWAITING_FILLER,
        )
        await db.commit()
        await db.refresh(lead)
        await log_action(
            db, tenant_id=tenant_id, user_id=user["sub"],
            user_name=user.get("real_name") or user.get("username"),
            action="reactivation_to_filler", resource_type="lead", resource_id=lead.id,
            summary=f"重激活转填表人: {lead.title}",
        )
        return lead

    # 提交信息情报部审批（可对已收录/袭击线索再起一轮）
    if lead.review_status not in ("approved", "attacked", "rejected", "draft"):
        if lead.review_status == "pending":
            raise BusinessException(code=BUSINESS_ERROR, message="线索已在审批中，请勿重复提交")

    lead.review_status = "pending"
    lead.reject_reason = None
    lead.reactivation_status = REACT_PENDING_REVIEW
    await _complete_open_tasks(db, tenant_id, lead.id)
    await db.commit()

    try:
        inst = await lead_service.submit_lead_review(db, tenant_id, lead, user)
    except Exception as e:
        logger.warning("reactivation review submit failed for %s: %s", lead.id, e)
        await db.rollback()
        lead = await lead_service.get_lead(db, tenant_id, lead_id)
        lead.reactivation_status = REACT_AWAITING_FILLER if filler_id else REACT_AWAITING_REPORTER
        lead.review_status = "approved"  # 回退到可再提交态
        await db.commit()
        raise BusinessException(code=BUSINESS_ERROR, message=f"提交情报审批失败: {e}") from e

    await lead_service._apply_review_flow(db, tenant_id, lead, inst, user)
    await db.refresh(lead)
    # 若免审直接通过，writeback/apply 会重置周期
    if lead.review_status in ("approved", "attacked"):
        mark_cycle_reset(lead)
        await db.commit()
        await db.refresh(lead)

    await log_action(
        db, tenant_id=tenant_id, user_id=user["sub"],
        user_name=user.get("real_name") or user.get("username"),
        action="reactivation_submit_review", resource_type="lead", resource_id=lead.id,
        summary=f"重激活提交情报审批: {lead.title}",
    )
    return lead


async def _notify_cycle_closed(db: AsyncSession, tenant_id: str, lead: Lead) -> None:
    from app.domains.notification.service import send_notification
    recipient = lead.reporter_id or lead.owner_id or lead.created_by_id
    if not recipient:
        return
    try:
        await send_notification(
            db=db, tenant_id=tenant_id, recipient_id=recipient,
            type="system",
            title=f"线索重激活已结束: {lead.title}",
            content=f"项目状态为「{lead.report_project_status}」，本轮跟进已结束。",
            biz_type="lead", biz_id=lead.id, sender_name="系统",
        )
    except Exception as e:
        logger.warning("close notify failed lead=%s: %s", lead.id, e)


async def on_review_terminal(
    db: AsyncSession, tenant_id: str, lead_id: str, *, outcome: str,
) -> None:
    """审批终态钩子：completed(收录/袭击) 重置周期；rejected 且在重激活中则退回填表人。"""
    lead = (await db.execute(
        select(Lead).where(Lead.id == lead_id, Lead.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not lead:
        return
    if outcome == "completed":
        mark_cycle_reset(lead)
        await _complete_open_tasks(db, tenant_id, lead_id)
    elif outcome == "rejected" and lead.reactivation_status == REACT_PENDING_REVIEW:
        lead.reactivation_status = (
            REACT_AWAITING_FILLER if lead.created_by_id else REACT_AWAITING_REPORTER
        )
    await db.flush()


# 供 worker 判断「今天是否已扫过」的简易内存戳（多进程下各扫一次可接受）
_last_scan_date: str | None = None


def should_run_daily_scan(now_cn: datetime) -> bool:
    global _last_scan_date
    raw = (getattr(settings, "LEAD_REACTIVATION_SCAN_TIME", None) or "09:00").strip()
    try:
        hh, mm = [int(x) for x in raw.split(":")[:2]]
    except Exception:
        hh, mm = 9, 0
    scheduled = now_cn.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if now_cn < scheduled:
        return False
    day_key = now_cn.strftime("%Y-%m-%d")
    if _last_scan_date == day_key:
        return False
    return True


def mark_daily_scan_done(now_cn: datetime) -> None:
    global _last_scan_date
    _last_scan_date = now_cn.strftime("%Y-%m-%d")
