"""扩展平台审批引擎 — 超时(SLA)扫描与处理。

由 reminder_worker 周期调用: 找出运行中、配置了 timeout 且已过期未触发的审批节点实例,
按节点配置的动作(notify/auto_approve/auto_reject/auto_transfer)处置,并发对应通知。
跨租户扫描,按 node_instance.tenant_id 实例化引擎处理。
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.lowcode.workflow_models import WfNodeInstance
from app.domains.lowcode.workflow_engine import WorkflowEngine


async def scan_and_fire(db: AsyncSession) -> int:
    """扫描并处理超时审批节点。返回触发处置的节点数。"""
    now = datetime.now(timezone.utc)
    nodes = (await db.execute(select(WfNodeInstance).where(
        WfNodeInstance.node_type == "approval",
        WfNodeInstance.status == "running",
    ).limit(5000))).scalars().all()

    from app.domains.notification.service import send_notification
    fired = 0
    for ni in nodes:
        cfg = ni.config or {}
        to = cfg.get("timeout")
        if not isinstance(to, dict) or cfg.get("sla_fired"):
            continue
        hours = to.get("hours")
        if not hours or not ni.started_at:
            continue
        try:
            deadline = ni.started_at + timedelta(hours=float(hours))
        except (TypeError, ValueError):
            continue
        if now < deadline:
            continue

        engine = WorkflowEngine(db, ni.tenant_id)
        try:
            notify = await engine.fire_timeout(ni)
            await db.commit()
        except Exception:
            await db.rollback()
            continue
        fired += 1
        # 超时处置可能推进流程(激活新节点/驳回结束)，其待办通知与钉钉待办由引擎排队，
        # fire_timeout 自身不提交，需在此提交后统一下发。
        await engine.flush_notifications()

        if notify:
            for uid in {u for u in (notify.get("recipients") or []) if u and u != "system"}:
                try:
                    await send_notification(
                        db=db, tenant_id=ni.tenant_id, recipient_id=uid,
                        type="system", title=notify["title"], content=notify["content"],
                        biz_type="wf_instance", biz_id=notify.get("instance_id"),
                    )
                except Exception:
                    pass
            try:
                await db.commit()
            except Exception:
                await db.rollback()
    return fired
