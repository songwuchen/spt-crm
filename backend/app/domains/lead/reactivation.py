"""线索 180 天循环重激活。

计时锚点 cycle_anchor_at 对齐简道云「申报时间」：收录/袭击状态下，
自该日期起满 N 天（可配）且尚未进入本轮重激活的线索视为到期；
每日 09:00 扫描「精确满 N 天当天」的线索（与简道云一致，非积压全扫）。
触发建待办需 activate_on_scan=true。
否则 → 填表人确认 → 信息情报部审批；再收录/袭击后重新计时。
张贺等配置姓名跳过申报人，直接给填表人。

编号约定：简道云迁移线索保留原号（申报信息-/24.23.1- 等）；
CRM 自建线索用 YYYYMM###，二者通过 lead_code 格式区分。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import generate_uuid, utcnow
from app.domains.audit.service import log_action
from app.domains.lead.models import Lead, LeadReactivationRecord

logger = logging.getLogger(__name__)

REACT_NONE = "none"
REACT_AWAITING_REPORTER = "awaiting_reporter"
REACT_AWAITING_FILLER = "awaiting_filler"
REACT_PENDING_REVIEW = "pending_review"
REACT_CLOSED = "closed"

# 简道云 180天激活：仅「进行中」进内勤→情报审；其它（中标/已签合同等）业务员 else 直接结束
PROGRESS_STATUS = "进行中"

# 选这些结果则流程结束，不再进情报审 / 不再自动重激活
CLOSE_PROJECT_STATUSES = frozenset({"暂缓", "暂停", "取消", "落标"})

TASK_BIZ_TYPE = "lead_reactivation"
WF_BIZ_TYPE = "lead_reactivation"
# 流程节点 id（与 workflow_service 默认图一致）
REACT_NODE_SALES = "approval_sales"
REACT_NODE_FILLER_SKIP = "approval_filler_skip"
REACT_NODE_FILLER = "approval_filler"
REACT_FILLER_NODE_IDS = frozenset({REACT_NODE_FILLER_SKIP, REACT_NODE_FILLER})
# 需要填写跟进字段的内勤（简道云 flowId=5；flowId=3 仅确认）
REACT_FILLER_FILL_NODE_IDS = frozenset({REACT_NODE_FILLER_SKIP})
REACT_NODE_INTEL = "approval_intel"

LEAD_REACT_FLOW_CODE = "SYS_LEAD_REACTIVATION_REVIEW"
POLICY_KEY = "lead_reactivation"

# 跟进字段（业务员/内勤节点可填）
REACT_FOLLOW_FIELDS = (
    "project_recent", "follow_progress", "site_visit", "report_project_status",
)

SYSTEM_INITIATOR = {
    "sub": "00000000-0000-0000-0000-000000000001",
    "username": "system",
    "real_name": "系统",
}

# 页面可配字段默认值；.env 仅作未落库时的全局兜底
DEFAULT_CONFIG = {
    "enabled": True,
    "activate_on_scan": False,
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
        "activate_on_scan": bool(src["activate_on_scan"]) if "activate_on_scan" in src else False,
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
    public = {k: cleaned[k] for k in ("enabled", "activate_on_scan", "days", "scan_time", "skip_reporter_names")}
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


def needs_intel_review(project_status: str | None) -> bool:
    """对齐简道云业务员节点：仅「进行中」进入内勤/情报审。"""
    return (project_status or "").strip() == PROGRESS_STATUS


def ends_reactivation_round(project_status: str | None) -> bool:
    """非进行中且非暂缓/取消/落标：简道云 else 分支直接结束本轮（不重置计时）。"""
    ps = (project_status or "").strip()
    return bool(ps and ps not in CLOSE_PROJECT_STATUSES and ps != PROGRESS_STATUS)


def _anchor_of(lead: Lead) -> datetime | None:
    return lead.cycle_anchor_at or lead.reported_at or lead.created_at


def reactivation_status_for_node(node_def_id: str | None) -> str | None:
    """workflow 节点 → leads.reactivation_status。"""
    nid = (node_def_id or "").strip()
    if nid == REACT_NODE_SALES:
        return REACT_AWAITING_REPORTER
    if nid in REACT_FILLER_NODE_IDS:
        return REACT_AWAITING_FILLER
    if nid == REACT_NODE_INTEL:
        return REACT_PENDING_REVIEW
    return None


async def build_reactivation_wf_context(
    db: AsyncSession, tenant_id: str, lead: Lead, cfg: dict | None = None,
) -> dict:
    """流程条件分支上下文（跳过申报人 / 是否需内勤核对）。"""
    cfg = cfg or await get_tenant_config(db, tenant_id)
    reporter_id = lead.reporter_id or lead.owner_id or lead.created_by_id
    filler_id = lead.created_by_id
    return {
        "report_project_status": lead.report_project_status,
        "reporter_name": lead.reporter_name,
        "reporter_id": lead.reporter_id,
        "created_by_id": lead.created_by_id,
        "owner_id": lead.owner_id,
        "department_id": lead.department_id,
        "react_skip_reporter": should_skip_reporter(lead, cfg),
        "react_need_filler": bool(filler_id and reporter_id and filler_id != reporter_id),
    }


async def resolve_intel_return_node(
    db: AsyncSession, process_instance_id: str,
) -> str:
    """情报审退回：对齐简道云 backNodes=[内勤3, 业务员, 内勤5]。

    优先退回本轮已完成的内勤；若业务员直接进情报审（无内勤），则退回业务员。
    """
    from app.domains.lowcode.workflow_models import WfNodeInstance

    row = (await db.execute(
        select(WfNodeInstance.node_def_id).where(
            WfNodeInstance.process_instance_id == process_instance_id,
            WfNodeInstance.node_def_id.in_(
                tuple(REACT_FILLER_NODE_IDS | {REACT_NODE_SALES}),
            ),
            WfNodeInstance.status == "completed",
        ).order_by(WfNodeInstance.completed_at.desc()).limit(1)
    )).scalar_one_or_none()
    return row or REACT_NODE_FILLER


async def sync_reactivation_status_from_wf(
    db: AsyncSession, tenant_id: str, lead_id: str,
) -> None:
    """按当前 running 流程的 pending 节点同步 reactivation_status。"""
    from app.domains.lowcode.workflow_models import WfProcessInstance, WfNodeInstance, WfTaskInstance

    inst = (await db.execute(
        select(WfProcessInstance).where(
            WfProcessInstance.tenant_id == tenant_id,
            WfProcessInstance.biz_type == WF_BIZ_TYPE,
            WfProcessInstance.biz_id == lead_id,
            WfProcessInstance.status == "running",
        ).order_by(WfProcessInstance.started_at.desc()).limit(1)
    )).scalar_one_or_none()
    if not inst:
        return
    node_def_id = (await db.execute(
        select(WfNodeInstance.node_def_id)
        .join(WfTaskInstance, WfTaskInstance.node_instance_id == WfNodeInstance.id)
        .where(
            WfTaskInstance.process_instance_id == inst.id,
            WfTaskInstance.status == "pending",
        ).limit(1)
    )).scalar_one_or_none()
    # scalar_one_or_none 直接返回 node_def_id 字符串，不可再按下标取首字符
    st = reactivation_status_for_node(node_def_id)
    if not st:
        return
    lead = (await db.execute(
        select(Lead).where(Lead.id == lead_id, Lead.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if lead:
        lead.reactivation_status = st
        await db.flush()


async def start_reactivation_workflow(
    db: AsyncSession, tenant_id: str, lead: Lead, *, cfg: dict | None = None,
):
    """触发 180 天激活：起 lead_reactivation 全流程实例（替代 UserTask）。"""
    from app.domains.lowcode.workflow_models import WfProcessInstance
    from app.domains.lowcode.workflow_service import (
        _lead_intel_approver_rule,
        ensure_default_definition,
        start_for_biz,
    )

    existing = (await db.execute(
        select(WfProcessInstance).where(
            WfProcessInstance.tenant_id == tenant_id,
            WfProcessInstance.biz_type == WF_BIZ_TYPE,
            WfProcessInstance.biz_id == lead.id,
            WfProcessInstance.status == "running",
        ).limit(1)
    )).scalar_one_or_none()
    if existing:
        await sync_reactivation_status_from_wf(db, tenant_id, lead.id)
        return existing

    cfg = cfg or await get_tenant_config(db, tenant_id)
    await ensure_default_definition(
        db, tenant_id,
        biz_type=WF_BIZ_TYPE,
        code=LEAD_REACT_FLOW_CODE,
        name="180天项目激活审批",
        approver_rule=_lead_intel_approver_rule(),
        multi_mode="or_sign",
        empty_strategy="auto_approve",
    )
    ctx = await build_reactivation_wf_context(db, tenant_id, lead, cfg)
    # 180天由系统扫描触发（对齐简道云递呈），发起人须为 system，否则 reporter 节点 exclude_initiator 会空审自动过
    initiator = dict(SYSTEM_INITIATOR)
    title = f"180天项目激活: {(lead.lead_code + ' ') if lead.lead_code else ''}{lead.title}"
    inst = await start_for_biz(
        db, tenant_id, WF_BIZ_TYPE, lead.id, initiator, title=title, form_data=ctx,
    )
    if inst:
        await sync_reactivation_status_from_wf(db, tenant_id, lead.id)
    return inst


async def _complete_open_tasks(db: AsyncSession, tenant_id: str, lead_id: str) -> None:
    """清理历史 UserTask（全链路 workflow 后仅作兼容）。"""
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

    assignee_id, _, _ = _resolve_assignee(lead, prefer_filler=False, cfg=cfg)
    if not assignee_id:
        logger.warning("lead reactivation skip (no assignee): %s", lead.id)
        return False

    if not lead.cycle_anchor_at:
        lead.cycle_anchor_at = _anchor_of(lead) or utcnow()
    lead.reactivation_notified_at = utcnow()
    lead.reactivation_round = int(lead.reactivation_round or 0) + 1
    await _create_round_record_on_activate(db, tenant_id, lead)
    await _complete_open_tasks(db, tenant_id, lead.id)
    try:
        await start_reactivation_workflow(db, tenant_id, lead, cfg=cfg)
    except Exception as e:
        logger.warning("reactivation workflow start failed lead=%s: %s", lead.id, e)
        return False
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
    """按租户配置扫描到期线索并起待办（系统设置可配天数/时刻/跳过名单）。

    到期口径（对齐简道云）：锚点北京时间日期 == 今天 - N 天（精确当天）。
    仅当 activate_on_scan=true 时才会真正建待办，否则只扫描并写 last_scan_at。
    """
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
            # 锚点满 N 天当天（对齐简道云「180天前上午9点触发」）
            target_date = now_cn.date() - timedelta(days=days)
            anchor = func.coalesce(Lead.cycle_anchor_at, Lead.reported_at, Lead.created_at)
            anchor_cn_date = func.date(func.timezone("Asia/Shanghai", anchor))
            q = (
                select(Lead)
                .where(
                    Lead.tenant_id == tenant_id,
                    Lead.is_deleted == False,  # noqa: E712
                    Lead.status != "discarded",
                    Lead.review_status.in_(("approved", "attacked")),
                    or_(Lead.reactivation_status == REACT_NONE, Lead.reactivation_status.is_(None)),
                    anchor.is_not(None),
                    anchor_cn_date == target_date,
                )
                .order_by(anchor.asc())
                .limit(limit)
            )
            leads = (await db.execute(q)).scalars().all()
            if not cfg.get("activate_on_scan", False):
                if leads:
                    logger.info(
                        "lead reactivation due tenant=%s count=%s (activate_on_scan=false, skipped)",
                        tenant_id,
                        len(leads),
                    )
                await _mark_tenant_scanned(db, tenant_id, now_cn)
                continue
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


async def _create_round_record_on_activate(
    db: AsyncSession, tenant_id: str, lead: Lead,
) -> LeadReactivationRecord:
    """触发时新建本轮激活单（对齐简道云满 180 天自动建 180天项目激活数据）。"""
    round_no = max(1, int(lead.reactivation_round or 0))
    existing = (await db.execute(
        select(LeadReactivationRecord).where(
            LeadReactivationRecord.tenant_id == tenant_id,
            LeadReactivationRecord.lead_id == lead.id,
            LeadReactivationRecord.round_no == round_no,
        ).limit(1)
    )).scalar_one_or_none()
    if existing:
        return existing
    row = LeadReactivationRecord(
        id=generate_uuid(),
        tenant_id=tenant_id,
        lead_id=lead.id,
        original_lead_code=lead.lead_code,
        round_no=round_no,
    )
    db.add(row)
    await db.flush()
    return row


async def _upsert_reactivation_record(
    db: AsyncSession, tenant_id: str, lead: Lead, user: dict,
) -> LeadReactivationRecord:
    """按轮次写入/更新激活内容（对齐简道云「180天项目激活」一行）。"""
    round_no = max(1, int(lead.reactivation_round or 0))
    existing = (await db.execute(
        select(LeadReactivationRecord).where(
            LeadReactivationRecord.tenant_id == tenant_id,
            LeadReactivationRecord.lead_id == lead.id,
            LeadReactivationRecord.round_no == round_no,
        ).limit(1)
    )).scalar_one_or_none()
    now = utcnow()
    submitter_name = user.get("real_name") or user.get("username")
    if existing:
        existing.original_lead_code = lead.lead_code or existing.original_lead_code
        existing.project_recent = lead.project_recent
        existing.follow_progress = lead.follow_progress
        existing.site_visit = lead.site_visit
        existing.report_project_status = lead.report_project_status
        existing.submitted_by_id = user.get("sub")
        existing.submitted_by_name = submitter_name
        existing.submitted_at = now
        await db.flush()
        return existing
    row = LeadReactivationRecord(
        tenant_id=tenant_id,
        lead_id=lead.id,
        original_lead_code=lead.lead_code,
        round_no=round_no,
        project_recent=lead.project_recent,
        follow_progress=lead.follow_progress,
        site_visit=lead.site_visit,
        report_project_status=lead.report_project_status,
        submitted_by_id=user.get("sub"),
        submitted_by_name=submitter_name,
        submitted_at=now,
    )
    db.add(row)
    await db.flush()
    return row


async def list_reactivation_records(
    db: AsyncSession, tenant_id: str, lead_id: str,
) -> list[LeadReactivationRecord]:
    """线索详情：180 天激活内容查看（按轮次倒序）。"""
    return list((await db.execute(
        select(LeadReactivationRecord).where(
            LeadReactivationRecord.tenant_id == tenant_id,
            LeadReactivationRecord.lead_id == lead_id,
        ).order_by(
            LeadReactivationRecord.round_no.desc(),
            LeadReactivationRecord.submitted_at.desc().nullslast(),
        )
    )).scalars().all())


def derive_record_flow_status(record: LeadReactivationRecord, lead: Lead) -> str:
    """单条激活记录的流程状态（对齐简道云 flowState 列）。"""
    is_current = int(record.round_no or 0) == int(lead.reactivation_round or 0)
    if not is_current:
        return "completed"
    st = lead.reactivation_status or REACT_NONE
    if st == REACT_NONE:
        return "completed" if record.submitted_at else "running"
    if st == REACT_CLOSED:
        return "closed"
    return st


def _record_to_dict(record: LeadReactivationRecord, lead: Lead) -> dict:
    """列表/详情公共字段。"""
    flow_status = derive_record_flow_status(record, lead)
    is_current = int(record.round_no or 0) == int(lead.reactivation_round or 0)
    return {
        "id": record.id,
        "lead_id": lead.id,
        "original_lead_code": record.original_lead_code or lead.lead_code,
        "round_no": record.round_no,
        "project_recent": record.project_recent,
        "follow_progress": record.follow_progress,
        "site_visit": record.site_visit,
        "report_project_status": record.report_project_status,
        "submitted_by_id": record.submitted_by_id,
        "submitted_by_name": record.submitted_by_name,
        "submitted_at": record.submitted_at.isoformat() if record.submitted_at else None,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        "lead_title": lead.title,
        "lead_company_name": lead.company_name,
        "lead_reporter_name": lead.reporter_name,
        "lead_filler_name": lead.created_by_name,
        "lead_department_name": getattr(lead, "department_name", None),
        "reactivation_status": lead.reactivation_status if is_current else "none",
        "flow_status": flow_status,
        "is_current_round": is_current,
    }


async def reactivation_record_stats(db: AsyncSession, tenant_id: str) -> dict:
    """180天激活列表顶栏统计（按激活单维度）。"""
    row = (await db.execute(
        text("""
            SELECT
              count(*) AS total,
              count(*) FILTER (
                WHERE l.reactivation_status IN ('awaiting_reporter', 'awaiting_filler', 'pending_review')
              ) AS active,
              count(*) FILTER (WHERE l.reactivation_status = 'none') AS completed,
              count(*) FILTER (WHERE l.reactivation_status = 'closed') AS closed
            FROM lead_reactivation_records r
            JOIN leads l ON l.id = r.lead_id
            WHERE r.tenant_id = :tid
              AND l.tenant_id = :tid
              AND l.is_deleted = false
        """),
        {"tid": tenant_id},
    )).mappings().one()
    total = int(row["total"] or 0)
    active = int(row["active"] or 0)
    completed = int(row["completed"] or 0)
    closed = int(row["closed"] or 0)
    return {
        "total": total,
        "active": active,
        "completed": completed,
        "closed": closed,
        "finished": completed + closed,
    }


async def list_reactivation_records_page(
    db: AsyncSession,
    tenant_id: str,
    *,
    page_no: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    flow_status: str | None = None,
    reactivation_status: str | None = None,
) -> tuple[list[dict], int]:
    """180天项目激活列表（按激活单维度，对齐简道云数据管理）。"""
    base = (
        select(LeadReactivationRecord, Lead)
        .join(Lead, Lead.id == LeadReactivationRecord.lead_id)
        .where(
            LeadReactivationRecord.tenant_id == tenant_id,
            Lead.tenant_id == tenant_id,
            Lead.is_deleted == False,  # noqa: E712
        )
    )
    if keyword:
        kw = f"%{keyword.strip()}%"
        base = base.where(
            LeadReactivationRecord.original_lead_code.ilike(kw)
            | Lead.lead_code.ilike(kw)
            | Lead.title.ilike(kw)
            | Lead.company_name.ilike(kw)
        )
    rows = list((await db.execute(
        base.order_by(
            LeadReactivationRecord.created_at.desc(),
            LeadReactivationRecord.round_no.desc(),
        )
    )).all())

    items: list[dict] = []
    for record, lead in rows:
        item = _record_to_dict(record, lead)
        if reactivation_status and item.get("is_current_round"):
            if (lead.reactivation_status or REACT_NONE) != reactivation_status:
                continue
        elif reactivation_status and not item.get("is_current_round"):
            continue
        if flow_status == "active":
            if item["flow_status"] in ("completed", "closed"):
                continue
        elif flow_status == "finished":
            if item["flow_status"] not in ("completed", "closed"):
                continue
        elif flow_status and item["flow_status"] != flow_status:
            continue
        items.append(item)

    total = len(items)
    start = max(0, (page_no - 1) * page_size)
    return items[start:start + page_size], total


async def get_reactivation_record_detail(
    db: AsyncSession, tenant_id: str, record_id: str,
) -> dict | None:
    """单条 180 天激活详情（含原申报信息快照）。"""
    row = (await db.execute(
        select(LeadReactivationRecord, Lead).join(
            Lead, Lead.id == LeadReactivationRecord.lead_id,
        ).where(
            LeadReactivationRecord.id == record_id,
            LeadReactivationRecord.tenant_id == tenant_id,
            Lead.tenant_id == tenant_id,
            Lead.is_deleted == False,  # noqa: E712
        ).limit(1)
    )).first()
    if not row:
        return None
    record, lead = row
    data = _record_to_dict(record, lead)
    data["lead_snapshot"] = {
        "lead_code": lead.lead_code,
        "title": lead.title,
        "company_name": lead.company_name,
        "source": lead.source,
        "category": lead.category,
        "customer_type": lead.customer_type,
        "industry": lead.industry,
        "region": lead.region,
        "province": lead.province,
        "city": lead.city,
        "district": lead.district,
        "country_type": lead.country_type,
        "has_internal_conflict": lead.has_internal_conflict,
        "project_activity": lead.project_activity,
        "reporter_name": lead.reporter_name,
        "created_by_name": lead.created_by_name,
        "reported_at": lead.reported_at.isoformat() if lead.reported_at else None,
        "review_status": lead.review_status,
    }
    return data


async def _finish_reactivation_round(
    db: AsyncSession, tenant_id: str, lead: Lead, *,
    status: str = REACT_NONE, reset_cycle: bool = False,
) -> None:
    """结束本轮重激活待办；仅情报审收录/袭击时 reset_cycle=True。"""
    if reset_cycle:
        mark_cycle_reset(lead)
    else:
        lead.reactivation_status = status
    await _complete_open_tasks(db, tenant_id, lead.id)


async def apply_early_end_from_status(
    db: AsyncSession, tenant_id: str, lead: Lead, *,
    notify: bool = True,
) -> None:
    """业务员/内勤选非「进行中」后流程提前结束时的业务态。"""
    ps = (lead.report_project_status or "").strip()
    if ps in CLOSE_PROJECT_STATUSES:
        lead.reactivation_status = REACT_CLOSED
        if notify:
            await _notify_cycle_closed(db, tenant_id, lead)
    elif ends_reactivation_round(ps):
        lead.reactivation_status = REACT_NONE
    await _complete_open_tasks(db, tenant_id, lead.id)
    await db.flush()


async def upsert_reactivation_record_for_user(
    db: AsyncSession, tenant_id: str, lead: Lead, user: dict,
) -> None:
    """业务员/内勤节点通过后写入激活单。"""
    await _upsert_reactivation_record(db, tenant_id, lead, user)


async def reactivation_intel_review(
    db: AsyncSession, tenant_id: str, lead_id: str, user: dict,
    decision: str, task_id: str,
    customer_newness: str | None = None,
    return_reason: str | None = None,
    opinion: str | None = None,
    assess_remark: str | None = None,
    has_internal_conflict: str | None = None,
    conflict_note: str | None = None,
) -> Lead:
    """180天激活情报审：收录/袭击重置计时；回退退回内勤/业务员（不改申报 review_status）。

    对齐简道云：无「驳回」终态，仅 收录/袭击/回退/暂存。
    """
    from app.common.error_codes import VALIDATION_ERROR, FORBIDDEN, BUSINESS_ERROR, NOT_FOUND
    from app.common.exceptions import BusinessException
    from app.domains.lead import service as lead_service
    from app.domains.lead.schemas import LeadIntelReviewIn
    from app.domains.lowcode.workflow_engine import WorkflowEngine
    from app.domains.lowcode.workflow_models import WfNodeInstance, WfProcessInstance, WfTaskInstance
    from app.domains.lead.service import _intel_field_updates

    # 简道云 180天激活无「驳回」；若前端误传 return，按回退处理
    if decision == "return":
        decision = "revise"

    LeadIntelReviewIn(
        decision=decision, task_id=task_id, customer_newness=customer_newness,
        return_reason=return_reason, opinion=opinion, assess_remark=assess_remark,
    )
    task = (await db.execute(select(WfTaskInstance).where(
        WfTaskInstance.id == task_id, WfTaskInstance.tenant_id == tenant_id,
    ))).scalar_one_or_none()
    if not task:
        raise BusinessException(code=NOT_FOUND, message="待办不存在")
    if task.status != "pending":
        raise BusinessException(code=BUSINESS_ERROR, message="该待办已处理")
    inst = await db.get(WfProcessInstance, task.process_instance_id)
    if not inst or inst.tenant_id != tenant_id:
        raise BusinessException(code=NOT_FOUND, message="流程实例不存在")
    if inst.biz_type != WF_BIZ_TYPE or inst.biz_id != lead_id:
        raise BusinessException(code=VALIDATION_ERROR, message="待办与180天激活不匹配")
    if task.assignee_id != user.get("sub"):
        raise BusinessException(code=FORBIDDEN, message="非当前待办的处理人")

    node_inst = await db.get(WfNodeInstance, task.node_instance_id)
    if not node_inst or node_inst.node_def_id != REACT_NODE_INTEL:
        raise BusinessException(code=VALIDATION_ERROR, message="当前不在重激活情报审批阶段")

    lead = await lead_service.get_lead(db, tenant_id, lead_id)
    # 以流程节点为准；同步 status 便于列表筛选
    lead.reactivation_status = REACT_PENDING_REVIEW

    if customer_newness is not None:
        lead.customer_newness = customer_newness
    if opinion is not None:
        lead.review_opinion = opinion or None
    if assess_remark is not None:
        lead.assess_remark = assess_remark.strip() or None
    if has_internal_conflict is not None:
        lead.has_internal_conflict = has_internal_conflict.strip() or None
    if conflict_note is not None:
        lead.conflict_note = conflict_note.strip() or None

    field_updates = _intel_field_updates(
        customer_newness=customer_newness,
        return_reason=return_reason,
        assess_remark=assess_remark,
        has_internal_conflict=has_internal_conflict,
        conflict_note=conflict_note,
    )

    if decision == "draft":
        if return_reason is not None:
            lead.reject_reason = return_reason.strip() or None
        if opinion is not None:
            task.opinion = opinion or None
        await db.commit()
        await db.refresh(lead)
        return lead

    engine = WorkflowEngine(db, tenant_id)
    if decision == "revise":
        reason = (return_reason or "").strip()
        lead.reject_reason = reason or None
        await db.commit()
        return_to = await resolve_intel_return_node(db, inst.id)
        await engine.act(
            task_id, user, "return", opinion=reason or opinion,
            return_to=return_to,
            field_updates=field_updates,
            allow_lead_intel=True,
        )
        await db.refresh(lead)
        await sync_reactivation_status_from_wf(db, tenant_id, lead.id)
        await db.commit()
        await db.refresh(lead)
        return lead

    # include / attack：仅重置 180 天计时，不动申报信息 review_status
    lead.reject_reason = None
    await db.commit()
    await engine.act(
        task_id, user, "approve", opinion=opinion,
        field_updates=field_updates,
        allow_lead_intel=True,
    )
    await db.refresh(lead)
    return lead


async def submit_reactivation(
    db: AsyncSession, tenant_id: str, lead_id: str, user: dict, data,
) -> Lead:
    """已迁移至 workflow 待办；保留 API 返回明确提示。"""
    from app.common.error_codes import VALIDATION_ERROR
    from app.common.exceptions import BusinessException
    raise BusinessException(
        code=VALIDATION_ERROR,
        message="180天重激活已改为流程待办办理，请在线索详情或审批中心打开 workflow 待办",
    )


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

