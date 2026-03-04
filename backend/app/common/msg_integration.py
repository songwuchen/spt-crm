"""
Messaging Integration — DingTalk (钉钉) and WeCom (企业微信) notification hooks.

Sends business notifications to external messaging platforms when configured.
Configuration is stored in `integration_endpoints` table with system_code
'dingtalk' or 'wecom'.

Usage:
    from app.common.msg_integration import send_to_dingtalk, send_to_wecom, dispatch_message

    await dispatch_message(db, tenant_id, title="审批通知", content="...", msg_type="approval")
"""
import hashlib
import hmac
import logging
import time
import base64
import urllib.parse
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.admin.models import IntegrationEndpoint

logger = logging.getLogger("spt_crm.msg_integration")


# -------- DingTalk (钉钉) --------

async def send_to_dingtalk(
    webhook_url: str,
    title: str,
    content: str,
    secret: str | None = None,
) -> bool:
    """Send a markdown message to a DingTalk group robot.

    Args:
        webhook_url: DingTalk robot webhook URL
        title: Message title
        content: Markdown content
        secret: Optional signing secret for security verification
    """
    if not webhook_url:
        return False

    url = webhook_url
    if secret:
        timestamp = str(int(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(secret.encode(), string_to_sign.encode(), hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code).decode())
        url = f"{webhook_url}&timestamp={timestamp}&sign={sign}"

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": content,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            data = resp.json()
            if data.get("errcode") == 0:
                logger.info(f"DingTalk message sent: {title}")
                return True
            logger.warning(f"DingTalk send failed: {data}")
            return False
    except Exception as e:
        logger.error(f"DingTalk send error: {e}")
        return False


# -------- WeCom (企业微信) --------

async def send_to_wecom(
    webhook_url: str,
    title: str,
    content: str,
) -> bool:
    """Send a markdown message to a WeCom group robot.

    Args:
        webhook_url: WeCom robot webhook URL
        title: Message title (prepended to content)
        content: Markdown content
    """
    if not webhook_url:
        return False

    full_content = f"## {title}\n{content}"

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": full_content,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json=payload)
            data = resp.json()
            if data.get("errcode") == 0:
                logger.info(f"WeCom message sent: {title}")
                return True
            logger.warning(f"WeCom send failed: {data}")
            return False
    except Exception as e:
        logger.error(f"WeCom send error: {e}")
        return False


# -------- Unified Dispatch --------

async def _get_msg_endpoint(db: AsyncSession, tenant_id: str, system_code: str) -> IntegrationEndpoint | None:
    """Load an active messaging endpoint for the tenant."""
    return (await db.execute(
        select(IntegrationEndpoint).where(
            IntegrationEndpoint.tenant_id == tenant_id,
            IntegrationEndpoint.system_code == system_code,
            IntegrationEndpoint.status == "active",
        )
    )).scalar_one_or_none()


async def dispatch_message(
    db: AsyncSession,
    tenant_id: str,
    title: str,
    content: str,
    msg_type: str = "system",
) -> dict[str, bool]:
    """Dispatch a notification message to all configured messaging platforms.

    Checks for active DingTalk and WeCom endpoints and sends to each.

    Args:
        db: Database session
        tenant_id: Tenant ID
        title: Message title
        content: Message content (markdown)
        msg_type: Business type tag for filtering (approval, payment, system, etc.)

    Returns:
        Dict of {platform: success_bool}
    """
    results: dict[str, bool] = {}

    # DingTalk
    dingtalk_ep = await _get_msg_endpoint(db, tenant_id, "dingtalk")
    if dingtalk_ep and dingtalk_ep.base_url:
        config = dingtalk_ep.auth_config_json or {}
        # Check if this msg_type should be sent
        allowed_types = config.get("msg_types")
        if not allowed_types or msg_type in allowed_types or "*" in allowed_types:
            secret = config.get("secret")
            results["dingtalk"] = await send_to_dingtalk(
                webhook_url=dingtalk_ep.base_url,
                title=title,
                content=content,
                secret=secret,
            )

    # WeCom
    wecom_ep = await _get_msg_endpoint(db, tenant_id, "wecom")
    if wecom_ep and wecom_ep.base_url:
        config = wecom_ep.auth_config_json or {}
        allowed_types = config.get("msg_types")
        if not allowed_types or msg_type in allowed_types or "*" in allowed_types:
            results["wecom"] = await send_to_wecom(
                webhook_url=wecom_ep.base_url,
                title=title,
                content=content,
            )

    if results:
        logger.info(f"Message dispatched [{msg_type}] '{title}': {results}")
    return results


async def notify_approval_pending(
    db: AsyncSession, tenant_id: str,
    approver_name: str, biz_type: str, biz_title: str,
) -> dict[str, bool]:
    """Send approval pending notification to messaging platforms."""
    title = "审批待处理通知"
    content = (
        f"**审批人**: {approver_name}\n\n"
        f"**业务类型**: {biz_type}\n\n"
        f"**审批对象**: {biz_title}\n\n"
        f"请尽快登录系统处理审批。"
    )
    return await dispatch_message(db, tenant_id, title, content, msg_type="approval")


async def notify_payment_overdue(
    db: AsyncSession, tenant_id: str,
    project_name: str, plan_no: str, amount: float, due_date: str,
) -> dict[str, bool]:
    """Send payment overdue notification to messaging platforms."""
    title = "回款逾期提醒"
    content = (
        f"**项目**: {project_name}\n\n"
        f"**回款计划**: {plan_no}\n\n"
        f"**金额**: ¥{amount:,.2f}\n\n"
        f"**到期日**: {due_date}\n\n"
        f"请跟进催款事宜。"
    )
    return await dispatch_message(db, tenant_id, title, content, msg_type="payment")


async def notify_contract_signed(
    db: AsyncSession, tenant_id: str,
    contract_no: str, customer_name: str, amount: float,
) -> dict[str, bool]:
    """Send contract signed notification to messaging platforms."""
    title = "合同签署通知"
    content = (
        f"**合同编号**: {contract_no}\n\n"
        f"**客户**: {customer_name}\n\n"
        f"**金额**: ¥{amount:,.2f}\n\n"
        f"合同已完成签署，请相关部门跟进后续工作。"
    )
    return await dispatch_message(db, tenant_id, title, content, msg_type="contract")
