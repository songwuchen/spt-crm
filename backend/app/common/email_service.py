"""
Email sending service.
SMTP configuration is read from IntegrationEndpoint (type=email / system_code=smtp).
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.admin.models import IntegrationEndpoint

logger = logging.getLogger("email_service")


async def _get_smtp_config(db: AsyncSession, tenant_id: str) -> dict | None:
    """Load SMTP config from IntegrationEndpoint with system_code='smtp'."""
    ep = (await db.execute(
        select(IntegrationEndpoint).where(
            IntegrationEndpoint.tenant_id == tenant_id,
            IntegrationEndpoint.system_code == "smtp",
            IntegrationEndpoint.status == "active",
        )
    )).scalar_one_or_none()
    if not ep or not ep.auth_config_json:
        return None
    from app.common.crypto import decrypt_config_json
    config = decrypt_config_json(ep.auth_config_json) or {}
    # Expected config keys: host, port, username, password, from_email, use_tls
    return {
        "host": config.get("host", ""),
        "port": int(config.get("port", 587)),
        "username": config.get("username", ""),
        "password": config.get("password", ""),
        "from_email": config.get("from_email", config.get("username", "")),
        "use_tls": config.get("use_tls", True),
    }


async def send_email(db: AsyncSession, tenant_id: str, to: str, subject: str, body_html: str) -> bool:
    """Send an email using the tenant's SMTP configuration.
    Returns True on success, False on failure.
    """
    config = await _get_smtp_config(db, tenant_id)
    if not config or not config["host"]:
        logger.warning(f"No SMTP config for tenant {tenant_id}, skipping email send")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = config["from_email"]
        msg["To"] = to
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        if config["use_tls"]:
            server = smtplib.SMTP(config["host"], config["port"], timeout=15)
            server.starttls()
        else:
            server = smtplib.SMTP(config["host"], config["port"], timeout=15)

        if config["username"] and config["password"]:
            server.login(config["username"], config["password"])

        server.sendmail(config["from_email"], to.split(","), msg.as_string())
        server.quit()
        logger.info(f"Email sent to {to}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Email send failed to {to}: {e}")
        return False
