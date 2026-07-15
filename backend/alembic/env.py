import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

from app.config import settings
from app.database import Base, TenantScopedBase, PlatformBase

# Import all models so they are registered on Base.metadata
from app.domains.auth.models import User, Role, Permission, UserRole, RolePermission
from app.domains.tenant.models import PlatformTenant
from app.domains.organization.models import Department, UserDepartment, Post, UserPost, UserAgent
from app.domains.customer.models import Customer, Contact, CustomerRelation, AclShare
from app.domains.lead.models import Lead
from app.domains.attachment.models import Attachment, AttachmentLink
from app.domains.audit.models import AuditLog
from app.domains.project.models import OpportunityProject, ProjectStageHistory, ProjectMember
from app.domains.quote.models import Quote, QuoteVersion, QuoteLine, CostSnapshot, QuoteSendLog
from app.domains.contract.models import Contract, ContractVersion
from app.domains.solution.models import Solution, SolutionVersion
from app.domains.delivery.models import ErpOrderLink, DeliveryMilestone
from app.domains.payment.models import Invoice, PaymentPlan, PaymentRecord
from app.domains.change.models import ChangeRequest
from app.domains.service_ticket.models import ServiceTicket, RenewalOpportunity
from app.domains.order.models import Order
from app.domains.tender.models import Tender
from app.domains.activity.models import Activity
from app.domains.ai_center.models import AiTask, AiResult, AiPromptTemplate
from app.domains.approval.models import ApprovalFlow, ApprovalTask
from app.domains.notification.models import Notification
from app.domains.outbox.models import OutboxEvent, InboxEvent
from app.domains.admin.models import (
    TenantPlan, TenantUsageMeter, TenantProfile, TenantFeatureToggle,
    StageDefinition, MarginPolicy, TenantAiPolicy, TenantAiBudget,
    IntegrationEndpoint, WebhookSubscription,
)
from app.domains.lowcode.models import (
    FormTemplate, FormTemplateVersion, FormInstance,
    FormInstanceDetailRow, SerialCounter,
)
from app.domains.lowcode.workflow_models import (
    WfProcessDefinition, WfProcessDefinitionVersion, WfProcessInstance,
    WfNodeInstance, WfTaskInstance, WfTaskActionLog, WfProcessComment, WfProcessCc,
)
from app.domains.lowcode.dashboard_models import Dashboard

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Combine metadata from all bases
target_metadata = Base.metadata
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
