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
POLICY_KEY = "lead_reactivation"

# 页面可配字段默认值；.env 仅作未落库时的全局兜底
DEFAULT_CONFIG = {
    "enabled": True,
    "days": 180,
    "scan_time": "09:00",
    "skip_reporter_names": ["张贺"],
}


def env_default_config() -> dict:
    """从 Settings/.env 拼默认配置（租户未保存过页面配置时使用）。"""
    days = max(1, int(getattr(settings, "LEAD_REACTIVATION_DAYS", 180) or 180))
    scan_time = (getattr(settings, "LEAD_REACTIVATION_SCAN_TIME", None) or "09:00").strip() or "09:00"
    raw = getattr(settings, "LEAD_REACT_SKIP_REPORTER_NAMES", "") or ""
    names = [x.strip() for x in raw.split(",") if x.strip()] or list(DEFAULT_CONFIG["skip_reporter_names"])
    return {
        "enabled": True,
        "days": days,
        "scan_time": scan_time,
        "skip_reporter_names": names,
    }


def normalize_config(raw: dict | None) -> dict:
    """清洗页面/库里的配置，补全默认值。"""
    base = env_default_config()
    src = raw if isinstance(raw, dict) else {}
    days = src.get("days", base["days"])
    try:
        days = max(1, min(3650, int(days)))
    except (TypeError, ValueError):
        days = base["days"]
    scan_time = str(src.get("scan_time") or base["scan_time"]).strip() or base["scan_time"]
    # 接受 "9:00" / "09:00"
    try:
        hh, mm = [int(x) for x in scan_time.split(":")[:2]]
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            raise ValueError("bad time")
        scan_time = f"{hh:02d}:{mm:02d}"
    except Exception:
        scan_time = base["scan_time"]
    names_raw = src.get("skip_reporter_names", base["skip_reporter_names"])
    if isinstance(names_raw, str):
        names = [x.strip() for x in names_raw.replace("，", ",").split(",") if x.strip()]
    elif isinstance(names_raw, list):
        names = [str(x).strip() for x in names_raw if str(x).strip()]
    else:
        names = list(base["skip_reporter_names"])
    return {
        "enabled": bool(src["enabled"]) if "enabled" in src else True,
        "days": days,
        "scan_time": scan_time,
        "skip_reporter_names": names,
        "last_scan_at": src.get("last_scan_at"),
    }


async def get_tenant_config(db: AsyncSession, tenant_id: str) -> dict:
    """读取租户重激活配置（系统设置页可改）。"""
    from app.domains.admin.service import get_profile
    p = await get_profile(db, tenant_id)
    stored = (p.security_policy_json or {}).get(POLICY_KEY) if p else None
    return normalize_config(stored if isinstance(stored, dict) else None)


async def save_tenant_config(db: AsyncSession, tenant_id: str, data: dict) -> dict:
    """保存租户重激活配置到 TenantProfile.security_policy_json。"""
    from sqlalchemy.orm.attributes import flag_modified
    from app.domains.admin import service as admin_svc

    cleaned = normalize_config(data)
    # 保留 worker 写入的 last_scan_at（页面保存时前端可不传）
    p = await admin_svc.get_profile(db, tenant_id)
    if not p:
        p = await admin_svc.upsert_profile(db, tenant_id, {})
    policy = dict(p.security_policy_json or {})
    prev = policy.get(POLICY_KEY) if isinstance(policy.get(POLICY_KEY), dict) else {}
    if cleaned.get("last_scan_at") is None and prev.get("last_scan_at"):
        cleaned["last_scan_at"] = prev.get("last_scan_at")
    # 页面 API 不暴露 last_scan_at
    public = {k: cleaned[k] for k in ("enabled", "days", "scan_time", "skip_reporter_names")}
    policy[POLICY_KEY] = {**public, "last_scan_at": cleaned.get("last_scan_at")}
    p.security_policy_json = policy
    flag_modified(p, "security_policy_json")
    await db.commit()
    return public


async def _mark_tenant_scanned(db: AsyncSession, tenant_id: str, now_cn: datetime) -> None:
    from sqlalchemy.orm.attributes import flag_modified
    from app.domains.admin import service as admin_svc

    p = await admin_svc.get_profile(db, tenant_id)
    if not p:
        p = await admin_svc.upsert_profile(db, tenant_id, {})
    policy = dict(p.security_policy_json or {})
    cfg = normalize_config(policy.get(POLICY_KEY) if isinstance(policy.get(POLICY_KEY), dict) else None)
    cfg["last_scan_at"] = now_cn.isoformat()
    policy[POLICY_KEY] = cfg
    p.security_policy_json = policy
    flag_modified(p, "security_policy_json")
    await db.commit()


def reactivation_days(cfg: dict | None = None) -> int:
    if cfg:
        return max(1, int(cfg.get("days") or 180))
    return max(1, int(getattr(settings, "LEAD_REACTIVATION_DAYS", 180) or 180))


def skip_reporter_names(cfg: dict | None = None) -> set[str]:
    if cfg is not None:
        names = cfg.get("skip_reporter_names") or []
        if isinstance(names, str):
            return {x.strip() for x in names.replace("，", ",").split(",") if x.strip()}
        return {str(x).strip() for x in names if str(x).strip()}
    raw = getattr(settings, "LEAD_REACT_SKIP_REPORTER_NAMES", "") or ""
    return {x.strip() for x in raw.split(",") if x.strip()}


def should_skip_reporter(lead: Lead, cfg: dict | None = None) -> bool:
    """申报人姓名在跳过名单（如张贺）时：重激活 / 转商机确认不进申报人待办。"""
    names = skip_reporter_names(cfg)
    if not names:
        return False
    name = (lead.reporter_name or "").strip()
    return bool(name and name in names)


def lead_confirm_assignee_id(lead: Lead, cfg: dict | None = None) -> str | None:
    """「确认是否转商机」待办指派人。

    默认申报人；申报人在跳过名单（如张贺）时改派填表人；均无则回退负责人。
    """
    if should_skip_reporter(lead, cfg):
        return lead.created_by_id or lead.reporter_id or lead.owner_id
    return lead.reporter_id or lead.owner_id or lead.created_by_id


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
    days: int | None = None,
) -> None:
    from app.domains.task.models import UserTask
    from app.domains.notification.service import send_notification

    await _complete_open_tasks(db, tenant_id, lead.id)
    title = f"线索重激活跟进: {(lead.lead_code + ' ') if lead.lead_code else ''}{lead.title}"
    cycle_days = days if days is not None else reactivation_days()
    if stage == REACT_AWAITING_FILLER:
        desc = (
            f"申报人已更新近况，请填表人核对后提交信息情报部审批。"
            f"项目状态：{lead.report_project_status or '-'}"
        )
    else:
        desc = (
            f"该线索自收录/袭击已满 {cycle_days} 天，请填写项目近况、跟进进度、"
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


def _resolve_assignee(
    lead: Lead, *, prefer_filler: bool, cfg: dict | None = None,
) -> tuple[str | None, str | None, str]:
    """返回 (assignee_id, assignee_name, reactivation_status)。"""
    filler_id = lead.created_by_id
    filler_name = lead.created_by_name
    reporter_id = lead.reporter_id or lead.owner_id or filler_id
    reporter_name = lead.reporter_name or lead.owner_name or filler_name

    if prefer_filler or should_skip_reporter(lead, cfg):
        # 跳过申报人：优先填表人；填表人缺失或就是申报人本人时退到负责人
        if filler_id and filler_id != reporter_id:
            return filler_id, filler_name, REACT_AWAITING_FILLER
        if lead.owner_id and lead.owner_id != reporter_id:
            return lead.owner_id, lead.owner_name, REACT_AWAITING_FILLER
        if filler_id:
            return filler_id, filler_name, REACT_AWAITING_FILLER
        return reporter_id, reporter_name, REACT_AWAITING_REPORTER

    return reporter_id, reporter_name, REACT_AWAITING_REPORTER


async def activate_lead(
    db: AsyncSession, tenant_id: str, lead: Lead, *, cfg: dict | None = None,
) -> bool:
    """对单条到期线索发起重激活待办。成功返回 True。"""
    if lead.is_deleted or lead.status == "discarded":
        return False
    if lead.review_status not in ("approved", "attacked"):
        return False
    if (lead.reactivation_status or REACT_NONE) not in (REACT_NONE,):
        return False

    cfg = cfg or await get_tenant_config(db, tenant_id)
    if not cfg.get("enabled", True):
        return False

    assignee_id, assignee_name, stage = _resolve_assignee(lead, prefer_filler=False, cfg=cfg)
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
        days=reactivation_days(cfg),
    )
    return True


def _tenant_due_for_scan(cfg: dict, now_cn: datetime) -> bool:
    if not cfg.get("enabled", True):
        return False
    raw = (cfg.get("scan_time") or "09:00").strip()
    try:
        hh, mm = [int(x) for x in raw.split(":")[:2]]
    except Exception:
        hh, mm = 9, 0
    scheduled = now_cn.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if now_cn < scheduled:
        return False
    last = cfg.get("last_scan_at")
    if last:
        try:
            last_dt = datetime.fromisoformat(str(last))
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=now_cn.tzinfo)
            if last_dt >= scheduled:
                return False
        except Exception:
            pass
    return True


async def scan_and_activate(db: AsyncSession, *, limit: int = 200) -> int:
    """按租户配置扫描到期线索并起待办（系统设置可配天数/时刻/跳过名单）。"""
    from datetime import timezone as tz
    from app.domains.tenant.models import PlatformTenant

    CN_TZ = tz(timedelta(hours=8))
    now_cn = datetime.now(CN_TZ)
    tenant_ids = list((await db.execute(
        select(PlatformTenant.id).where(PlatformTenant.is_active == True)  # noqa: E712
    )).scalars().all())

    activated = 0
    for tenant_id in tenant_ids:
        try:
            cfg = await get_tenant_config(db, tenant_id)
            if not _tenant_due_for_scan(cfg, now_cn):
                continue
            days = reactivation_days(cfg)
            cutoff = utcnow() - timedelta(days=days)
            anchor = func.coalesce(Lead.cycle_anchor_at, Lead.reported_at, Lead.created_at)
            q = (
                select(Lead)
                .where(
                    Lead.tenant_id == tenant_id,
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
            for lead in leads:
                try:
                    if await activate_lead(db, tenant_id, lead, cfg=cfg):
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
            await _mark_tenant_scanned(db, tenant_id, now_cn)
        except Exception as e:
            logger.warning("lead reactivation scan failed tenant=%s: %s", tenant_id, e)
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

