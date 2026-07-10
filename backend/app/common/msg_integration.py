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


# -------- DingTalk 企业应用：工作通知 + 待办（推送给具体负责人） --------
# 群机器人(上面的 send_to_dingtalk)只能发到群；要把"待办"推给某个负责人，
# 需用企业内部应用：appKey/appSecret 换 access_token，再按手机号查到 userid，
# 通过「工作通知」(asyncsend_v2) 下发可点击卡片，并尽力创建钉钉「待办」(Todo)。

_dingtalk_token_cache: dict[str, tuple[str, float]] = {}


async def get_dingtalk_token(app_key: str, app_secret: str) -> str | None:
    """获取并缓存钉钉企业应用 access_token（有效期内复用）。"""
    if not app_key or not app_secret:
        return None
    now = time.time()
    cached = _dingtalk_token_cache.get(app_key)
    if cached and cached[1] > now + 60:
        return cached[0]
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://oapi.dingtalk.com/gettoken",
                params={"appkey": app_key, "appsecret": app_secret},
            )
            data = resp.json()
        if data.get("errcode") == 0 and data.get("access_token"):
            token = data["access_token"]
            _dingtalk_token_cache[app_key] = (token, now + int(data.get("expires_in", 7200)))
            return token
        logger.warning("DingTalk gettoken failed: %s", data)
    except Exception as e:
        logger.error("DingTalk gettoken error: %s", e)
    return None


async def get_dingtalk_userid_by_mobile(token: str, mobile: str) -> str | None:
    """按手机号查询钉钉 userid（CRM 用户 → 钉钉用户的映射）。"""
    if not token or not mobile:
        return None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"https://oapi.dingtalk.com/topapi/v2/user/getbymobile?access_token={token}",
                json={"mobile": mobile},
            )
            data = resp.json()
        if data.get("errcode") == 0:
            return (data.get("result") or {}).get("userid")
        logger.warning("DingTalk getbymobile failed for %s: %s", mobile, data)
    except Exception as e:
        logger.error("DingTalk getbymobile error: %s", e)
    return None


async def get_dingtalk_unionid(token: str, userid: str) -> str | None:
    """按 userid 查 unionId（创建钉钉「待办」需要 unionId）。"""
    if not token or not userid:
        return None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"https://oapi.dingtalk.com/topapi/v2/user/get?access_token={token}",
                json={"userid": userid},
            )
            data = resp.json()
        if data.get("errcode") == 0:
            return (data.get("result") or {}).get("unionid")
    except Exception as e:
        logger.error("DingTalk user/get error: %s", e)
    return None


async def send_dingtalk_work_notification(
    token: str, agent_id: str, userid_list: list[str],
    title: str, content: str, url: str | None = None,
) -> bool:
    """发送钉钉「工作通知」给指定用户（待办式推送）。有链接时用可点击卡片，否则用文本。"""
    if not token or not agent_id or not userid_list:
        return False
    if url:
        msg = {"msgtype": "action_card", "action_card": {
            "title": title, "markdown": f"### {title}\n\n{content}",
            "single_title": "查看详情", "single_url": url,
        }}
    else:
        msg = {"msgtype": "text", "text": {"content": f"{title}\n{content}"}}
    payload = {"agent_id": str(agent_id), "userid_list": ",".join(userid_list), "msg": msg}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"https://oapi.dingtalk.com/topapi/message/corpconversation/asyncsend_v2?access_token={token}",
                json=payload,
            )
            data = resp.json()
        if data.get("errcode") == 0:
            logger.info("DingTalk work notification sent to %s: %s", userid_list, title)
            return True
        logger.warning("DingTalk asyncsend_v2 failed: %s", data)
    except Exception as e:
        logger.error("DingTalk asyncsend_v2 error: %s", e)
    return False


async def create_dingtalk_todo(
    token: str, union_id: str, creator_union_id: str | None,
    subject: str, description: str | None = None,
    url: str | None = None, mobile_url: str | None = None,
) -> str | None:
    """在负责人的钉钉「待办」中创建一条任务（v1.0 Todo API）。

    返回钉钉待办 id（成功）或 None（失败/未配置）。注意响应里待办 id 字段是 "id"
    而非 "taskId"（这是 spt-lowcode 踩过的坑），读错会导致后续无法完结该待办。
    """
    if not token or not union_id:
        return None
    body: dict[str, Any] = {
        "subject": subject[:200],
        "creatorId": creator_union_id or union_id,
        "executorIds": [union_id],
        "participantIds": [union_id],
        "isOnlyShowExecutor": True,
        "notifyConfigs": {"dingNotify": "1"},
    }
    if description:
        body["description"] = description[:1000]
    if url or mobile_url:
        body["detailUrl"] = {"pcUrl": url or mobile_url, "appUrl": mobile_url or url}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"https://api.dingtalk.com/v1.0/todo/users/{union_id}/tasks",
                headers={"x-acs-dingtalk-access-token": token},
                json=body,
            )
        if resp.status_code in (200, 201):
            todo_id = (resp.json() or {}).get("id")
            logger.info("DingTalk todo created for %s: %s (id=%s)", union_id, subject, todo_id)
            return todo_id
        logger.warning("DingTalk todo create failed (%s): %s", resp.status_code, resp.text[:200])
    except Exception as e:
        logger.error("DingTalk todo create error: %s", e)
    return None


async def complete_dingtalk_todo(token: str, union_id: str, task_id: str) -> bool:
    """完结钉钉个人待办。

    必须走 executorStatus 子接口（operatorId 为 query 参数），直接 PUT tasks/{id}
    传 isDone 钉钉不认、待办不消失（spt-lowcode 生产事故修复过）。
    """
    if not token or not union_id or not task_id:
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.put(
                f"https://api.dingtalk.com/v1.0/todo/users/{union_id}/tasks/{task_id}/executorStatus",
                params={"operatorId": union_id},
                headers={"x-acs-dingtalk-access-token": token},
                json={"executorStatusList": [{"id": union_id, "isDone": True}]},
            )
        if resp.status_code in (200, 201):
            logger.info("DingTalk todo completed for %s: %s", union_id, task_id)
            return True
        logger.warning("DingTalk todo complete failed (%s): %s", resp.status_code, resp.text[:200])
    except Exception as e:
        logger.error("DingTalk todo complete error: %s", e)
    return False


async def _dingtalk_app_config(db: AsyncSession, tenant_id: str) -> dict | None:
    """取租户钉钉企业应用配置（app_key/app_secret/agent_id 齐全才算可用），否则 None。"""
    ep = await _get_msg_endpoint(db, tenant_id, "dingtalk")
    if not ep:
        return None
    from app.common.crypto import decrypt_config_json
    config = decrypt_config_json(ep.auth_config_json or {}) or {}
    if not (config.get("app_key") and config.get("app_secret") and config.get("agent_id")):
        return None  # 仅群机器人、未配置企业应用 → 无法推个人待办
    return config


def _abs_url(config: dict, link: str | None, mobile: bool = False) -> str | None:
    """把站内相对路径拼成绝对 URL；移动端优先用 crm_h5_base_url。"""
    if not link:
        return None
    if link.startswith("http"):
        return link
    base = (config.get("crm_h5_base_url") if mobile else config.get("crm_base_url")) or config.get("crm_base_url") or ""
    base = base.rstrip("/")
    return base + link if base else None


async def dispatch_todo(
    db: AsyncSession, tenant_id: str, assignee_user_id: str,
    title: str, content: str, link: str | None = None, mobile_link: str | None = None,
) -> dict[str, Any]:
    """把"待办"推送给指定负责人（钉钉工作通知 + 创建钉钉待办）。

    需要租户配置了钉钉企业应用（dingtalk 集成的 auth_config_json 含 app_key/app_secret/agent_id），
    且该负责人在 CRM 中填了手机号（用于匹配钉钉账号）。未配置或匹配不到时安全跳过（站内通知已兜底）。

    返回 {work_notification: bool, todo: bool, todo_id: str|None, union_id: str|None}。
    """
    results: dict[str, Any] = {}
    if not assignee_user_id:
        return results
    config = await _dingtalk_app_config(db, tenant_id)
    if not config:
        return results
    token = await get_dingtalk_token(config["app_key"], config["app_secret"])
    if not token:
        return results

    from app.domains.auth.models import User
    user = (await db.execute(
        select(User).where(User.id == assignee_user_id, User.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not user or not user.phone:
        logger.info("dispatch_todo skipped: assignee %s has no phone", assignee_user_id)
        return results

    userid = await get_dingtalk_userid_by_mobile(token, user.phone)
    if not userid:
        return results

    pc_url = _abs_url(config, link, mobile=False)
    app_url = _abs_url(config, mobile_link or link, mobile=True)

    results["work_notification"] = await send_dingtalk_work_notification(
        token, config["agent_id"], [userid], title, content, app_url or pc_url)

    # 创建真正的钉钉待办（需 unionId + 应用具备待办权限）
    union_id = await get_dingtalk_unionid(token, userid)
    if union_id:
        todo_id = await create_dingtalk_todo(token, union_id, None, title, content, pc_url, app_url)
        results["todo"] = bool(todo_id)
        results["todo_id"] = todo_id
        results["union_id"] = union_id
    return results


async def complete_todo_for_user(
    db: AsyncSession, tenant_id: str, assignee_user_id: str, todo_id: str,
) -> bool:
    """完结某负责人名下的一条钉钉待办（审批任务被处理/取消时调用）。

    完结时重新按手机号解析该用户的 unionId（待办完结接口需要 unionId）。未配置钉钉、
    无手机号或解析失败时安全返回 False。
    """
    if not (assignee_user_id and todo_id):
        return False
    config = await _dingtalk_app_config(db, tenant_id)
    if not config:
        return False
    token = await get_dingtalk_token(config["app_key"], config["app_secret"])
    if not token:
        return False
    from app.domains.auth.models import User
    user = (await db.execute(
        select(User).where(User.id == assignee_user_id, User.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not user or not user.phone:
        return False
    userid = await get_dingtalk_userid_by_mobile(token, user.phone)
    if not userid:
        return False
    union_id = await get_dingtalk_unionid(token, userid)
    if not union_id:
        return False
    return await complete_dingtalk_todo(token, union_id, todo_id)


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
    from app.common.crypto import decrypt_config_json
    dingtalk_ep = await _get_msg_endpoint(db, tenant_id, "dingtalk")
    if dingtalk_ep and dingtalk_ep.base_url:
        config = decrypt_config_json(dingtalk_ep.auth_config_json or {}) or {}
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
        config = decrypt_config_json(wecom_ep.auth_config_json or {}) or {}
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
