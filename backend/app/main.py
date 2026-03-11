from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.common.exceptions import BusinessException
from app.middleware.trace_middleware import TraceMiddleware
from app.middleware.tenant_middleware import TenantMiddleware
from app.middleware.rate_limiter import RateLimitMiddleware
from app.middleware.error_handler import (
    business_exception_handler,
    validation_exception_handler,
    generic_exception_handler,
)

from app.domains.auth.router import router as auth_router
from app.domains.tenant.router import router as tenant_router
from app.domains.organization.router import router as org_router
from app.domains.customer.router import router as customer_router
from app.domains.lead.router import router as lead_router, public_router as lead_public_router
from app.domains.attachment.router import router as attachment_router
from app.domains.audit.router import router as audit_router
from app.domains.dashboard.router import router as dashboard_router
from app.domains.project.router import router as project_router
from app.domains.quote.router import router as quote_router
from app.domains.contract.router import router as contract_router
from app.domains.solution.router import router as solution_router
from app.domains.delivery.router import router as delivery_router
from app.domains.payment.router import router as payment_router
from app.domains.change.router import router as change_router
from app.domains.service_ticket.router import router as service_ticket_router
from app.domains.activity.router import router as activity_router
from app.domains.ai_center.router import router as ai_center_router
from app.domains.approval.router import router as approval_router
from app.domains.admin.router import router as admin_console_router
from app.domains.notification.router import router as notification_router
from app.domains.notification.ws import router as ws_router
from app.domains.outbox.router import router as outbox_router
from app.domains.product.router import router as product_router
from app.domains.task.router import router as task_router
from app.domains.dashboard.saved_view import router as saved_view_router
from app.domains.customer.contact_router import router as contact_router

from app.config import settings
from app.common.logging_config import setup_logging

import os
setup_logging(
    json_format=os.getenv("LOG_FORMAT", "").lower() == "json",
    level=os.getenv("LOG_LEVEL", "INFO"),
)

app = FastAPI(
    title="SPT-CRM API",
    version="1.0.0",
    description="SPT-CRM 后端 API — 客户管理、商机、报价、合同、交付、工单一站式管理平台",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "认证", "description": "登录 / Token / 用户信息"},
        {"name": "客户", "description": "客户 CRUD + 联系人"},
        {"name": "线索", "description": "线索管理 + 转化"},
        {"name": "商机项目", "description": "商机项目 CRUD + 阶段推进"},
        {"name": "报价", "description": "报价管理 + 版本 + 行项"},
        {"name": "合同", "description": "合同管理 + 版本 + 签署"},
        {"name": "方案", "description": "方案管理 + 版本 + 配置/风险清单"},
        {"name": "交付", "description": "交付里程碑管理"},
        {"name": "回款", "description": "回款计划 + 发票 + 收款记录"},
        {"name": "变更", "description": "变更请求管理"},
        {"name": "工单", "description": "售后服务工单"},
        {"name": "审批", "description": "审批流程中心"},
        {"name": "AI 中心", "description": "AI 任务管理"},
        {"name": "动态", "description": "业务动态/跟进记录"},
        {"name": "通知", "description": "站内通知"},
        {"name": "工作台", "description": "Dashboard 统计 + 告警 + 分析"},
        {"name": "附件", "description": "文件上传/下载"},
        {"name": "审计", "description": "操作日志"},
        {"name": "组织", "description": "部门管理"},
        {"name": "管理后台", "description": "系统管理 + 用户/角色"},
    ],
)

# --- CORS ---
_cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Middleware (order: outermost first) ---
app.add_middleware(TraceMiddleware)
app.add_middleware(TenantMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=120)

# --- Exception handlers ---
app.add_exception_handler(BusinessException, business_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# --- Routers ---
app.include_router(auth_router)
app.include_router(tenant_router)
app.include_router(org_router)
app.include_router(customer_router)
app.include_router(lead_router)
app.include_router(attachment_router)
app.include_router(audit_router)
app.include_router(dashboard_router)
app.include_router(project_router)
app.include_router(quote_router)
app.include_router(contract_router)
app.include_router(solution_router)
app.include_router(delivery_router)
app.include_router(payment_router)
app.include_router(change_router)
app.include_router(service_ticket_router)
app.include_router(activity_router)
app.include_router(ai_center_router)
app.include_router(approval_router)
app.include_router(admin_console_router)
app.include_router(notification_router)
app.include_router(outbox_router)
app.include_router(product_router)
app.include_router(task_router)
app.include_router(lead_public_router)
app.include_router(saved_view_router)
app.include_router(contact_router)
app.include_router(ws_router)


@app.post("/api/v1/frontend-errors", tags=["系统"])
async def report_frontend_error(request: Request):
    """Receive frontend error reports for monitoring."""
    import logging
    logger = logging.getLogger("frontend_errors")
    try:
        body = await request.json()
        logger.warning(
            "Frontend error: %s at %s",
            body.get("message", "unknown"),
            body.get("url", ""),
            extra={"frontend_error": body},
        )
    except Exception:
        pass
    return {"code": 0, "message": "ok", "data": None}


@app.get("/health", tags=["系统"])
async def health():
    """基础健康检查"""
    return {"status": "ok", "version": "1.0.0"}


@app.get("/health/ready", tags=["系统"])
async def health_ready():
    """就绪检查：验证数据库连接"""
    from app.database import async_session_factory
    try:
        async with async_session_factory() as session:
            await session.execute(select(1))
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={"status": "error", "db": str(e)},
        )
