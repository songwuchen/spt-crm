from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.domains.ai_center import service
from app.domains.ai_center.schemas import (
    AiTaskCreate, AiTaskUpdate, AiResultCreate,
    AiPromptTemplateCreate, AiPromptTemplateUpdate,
    KnowledgeDocCreate, KnowledgeDocUpdate, KnowledgeSearchQuery,
)
from app.domains.ai_center import knowledge_service

router = APIRouter(tags=["AI中心"])


def _task_dict(t) -> dict:
    return {
        "id": t.id,
        "task_type": t.task_type,
        "biz_type": t.biz_type,
        "biz_id": t.biz_id,
        "status": t.status,
        "priority": t.priority,
        "model_name": t.model_name,
        "prompt_template_id": t.prompt_template_id,
        "input_ref_json": t.input_ref_json,
        "budget_json": t.budget_json,
        "token_in": t.token_in,
        "token_out": t.token_out,
        "cost_est": float(t.cost_est) if t.cost_est is not None else None,
        "retry_count": t.retry_count,
        "error_message": t.error_message,
        "created_by_id": t.created_by_id,
        "created_by_name": t.created_by_name,
        "created_at": t.created_at.isoformat() if t.created_at else "",
        "updated_at": t.updated_at.isoformat() if t.updated_at else "",
    }


def _result_dict(r) -> dict:
    return {
        "id": r.id,
        "ai_task_id": r.ai_task_id,
        "result_json": r.result_json,
        "evidence_json": r.evidence_json,
        "risk_level": r.risk_level,
        "quality_score": float(r.quality_score) if r.quality_score is not None else None,
        "created_at": r.created_at.isoformat() if r.created_at else "",
    }


def _template_dict(t) -> dict:
    return {
        "id": t.id,
        "code": t.code,
        "name": t.name,
        "task_type": t.task_type,
        "template_text": t.template_text,
        "output_schema_json": t.output_schema_json,
        "guardrails_json": t.guardrails_json,
        "is_active": t.is_active,
        "created_at": t.created_at.isoformat() if t.created_at else "",
        "updated_at": t.updated_at.isoformat() if t.updated_at else "",
    }


# ==================== AiTask ====================

@router.get("/api/v1/ai/tasks")
async def list_tasks(
    biz_type: str | None = Query(None), biz_id: str | None = Query(None),
    status: str | None = Query(None),
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("project:view")),
):
    items = await service.list_tasks(db, tenant_id, biz_type=biz_type, biz_id=biz_id, status=status)
    return ok([_task_dict(t) for t in items])


@router.post("/api/v1/ai/tasks")
async def create_task(
    body: AiTaskCreate,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("project:edit")),
):
    t = await service.create_task(db, tenant_id, body, current_user)
    return ok(_task_dict(t))


@router.get("/api/v1/ai/tasks/{task_id}")
async def get_task(
    task_id: str, tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("project:view")),
):
    t = await service.get_task(db, tenant_id, task_id)
    data = _task_dict(t)
    # Attach result if done
    if t.status == "done":
        r = await service.get_result_by_task(db, tenant_id, task_id)
        if r:
            data["result"] = _result_dict(r)
    return ok(data)


@router.put("/api/v1/ai/tasks/{task_id}")
async def update_task(
    task_id: str, body: AiTaskUpdate,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("project:edit")),
):
    t = await service.update_task(db, tenant_id, task_id, body)
    return ok(_task_dict(t))


# ==================== AiResult ====================

@router.get("/api/v1/ai/results/{task_id}")
async def get_result(
    task_id: str, tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db), _user=Depends(require_permissions("project:view")),
):
    r = await service.get_result_by_task(db, tenant_id, task_id)
    if not r:
        return ok(None)
    return ok(_result_dict(r))


@router.post("/api/v1/ai/results")
async def create_result(
    body: AiResultCreate,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("project:edit")),
):
    r = await service.create_result(db, tenant_id, body)
    return ok(_result_dict(r))


# ==================== AiPromptTemplate ====================

@router.get("/api/v1/ai/templates")
async def list_templates(
    task_type: str | None = Query(None),
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("project:view")),
):
    items = await service.list_templates(db, tenant_id, task_type=task_type)
    return ok([_template_dict(t) for t in items])


@router.post("/api/v1/ai/templates")
async def create_template(
    body: AiPromptTemplateCreate,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("role:edit")),
):
    t = await service.create_template(db, tenant_id, body, current_user)
    return ok(_template_dict(t))


@router.put("/api/v1/ai/templates/{template_id}")
async def update_template(
    template_id: str, body: AiPromptTemplateUpdate,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:edit")),
):
    t = await service.update_template(db, tenant_id, template_id, body)
    return ok(_template_dict(t))


@router.delete("/api/v1/ai/templates/{template_id}")
async def delete_template(
    template_id: str,
    tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:edit")),
):
    await service.delete_template(db, tenant_id, template_id)
    return ok(None)


# ==================== AI Analysis Endpoints ====================

from pydantic import BaseModel
from typing import Optional


class AnalyzeRequest(BaseModel):
    biz_type: str  # project / customer / quote_version / contract_version
    biz_id: str
    analysis_type: str  # risk / profile / win_probability / next_actions / quote_review / contract_review


@router.post("/api/v1/ai/analyze")
async def run_analysis(
    body: AnalyzeRequest,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("project:view")),
):
    """Run AI analysis on a business entity. Returns structured JSON result."""
    from app.common.ai_engine import (
        analyze_project_risk, generate_customer_profile,
        predict_win_probability, suggest_next_actions,
        review_quote, review_contract,
    )
    from app.common.exceptions import BusinessException
    from app.common.error_codes import NOT_FOUND

    # Feature flag check: AI center must be enabled
    from app.common.feature_flag import is_feature_enabled
    if not await is_feature_enabled(db, tenant_id, "ai_center"):
        raise BusinessException(code=42300, message="AI 中心功能未启用，请联系管理员在功能开关中开启。")

    # AI budget quota check
    try:
        from datetime import datetime, timezone
        from app.domains.admin.models import TenantAiBudget
        period = datetime.now(timezone.utc).strftime("%Y-%m")
        budget = (await db.execute(
            select(TenantAiBudget).where(
                TenantAiBudget.tenant_id == tenant_id,
                TenantAiBudget.period == period,
            )
        )).scalar_one_or_none()
        if budget and budget.hard_limit:
            if budget.budget_cost and budget.used_cost and float(budget.used_cost) >= float(budget.budget_cost):
                raise BusinessException(code=42900, message=f"本月 AI 预算已用尽（已用 ${float(budget.used_cost):.2f} / ${float(budget.budget_cost):.2f}），请联系管理员调整配额。")
            if budget.budget_tokens and budget.used_tokens and budget.used_tokens >= budget.budget_tokens:
                raise BusinessException(code=42900, message=f"本月 AI Token 配额已用尽（已用 {budget.used_tokens:,} / {budget.budget_tokens:,}），请联系管理员调整配额。")
    except BusinessException:
        raise
    except Exception:
        pass  # Non-critical: if budget check fails, allow the request

    entity_data = {}

    if body.biz_type == "project":
        from app.domains.project.models import OpportunityProject
        from sqlalchemy import select
        p = (await db.execute(
            select(OpportunityProject).where(
                OpportunityProject.id == body.biz_id,
                OpportunityProject.tenant_id == tenant_id,
            )
        )).scalar_one_or_none()
        if not p:
            raise BusinessException(code=NOT_FOUND, message="商机不存在")
        # Fetch customer name if linked
        customer_name = ""
        if p.customer_id:
            from app.domains.customer.models import Customer
            cust = (await db.execute(
                select(Customer.name).where(Customer.id == p.customer_id, Customer.tenant_id == tenant_id)
            )).scalar_one_or_none()
            customer_name = cust or ""
        entity_data = {
            "name": p.name, "stage_code": p.stage_code,
            "amount_expect": float(p.amount_expect) if p.amount_expect else 0,
            "risk_level": p.risk_level or "M",
            "customer_name": customer_name,
            "industry": "",
        }

    elif body.biz_type == "customer":
        from app.domains.customer.models import Customer
        from sqlalchemy import select
        c = (await db.execute(
            select(Customer).where(
                Customer.id == body.biz_id,
                Customer.tenant_id == tenant_id,
            )
        )).scalar_one_or_none()
        if not c:
            raise BusinessException(code=NOT_FOUND, message="客户不存在")
        entity_data = {
            "name": c.name, "industry": c.industry or "",
            "level": c.level or "",
        }
    elif body.biz_type == "quote_version":
        from app.domains.quote.models import Quote, QuoteVersion, QuoteLine
        from sqlalchemy import select, func
        qv = (await db.execute(
            select(QuoteVersion).where(QuoteVersion.id == body.biz_id, QuoteVersion.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not qv:
            raise BusinessException(code=NOT_FOUND, message="报价版本不存在")
        q = (await db.execute(select(Quote).where(Quote.id == qv.quote_id, Quote.tenant_id == tenant_id))).scalar_one_or_none()
        line_count = (await db.execute(
            select(func.count(QuoteLine.id)).where(QuoteLine.quote_version_id == qv.id, QuoteLine.tenant_id == tenant_id)
        )).scalar() or 0
        entity_data = {
            "quote_no": q.quote_no if q else "",
            "version_no": qv.version_no,
            "total_amount": float(qv.total_amount) if qv.total_amount else 0,
            "total_cost": float(qv.total_cost) if qv.total_cost else 0,
            "line_count": line_count,
            "customer_name": "",
        }

    elif body.biz_type == "contract_version":
        from app.domains.contract.models import Contract, ContractVersion
        from sqlalchemy import select
        cv = (await db.execute(
            select(ContractVersion).where(ContractVersion.id == body.biz_id, ContractVersion.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not cv:
            raise BusinessException(code=NOT_FOUND, message="合同版本不存在")
        c = (await db.execute(select(Contract).where(Contract.id == cv.contract_id, Contract.tenant_id == tenant_id))).scalar_one_or_none()
        entity_data = {
            "contract_no": c.contract_no if c else "",
            "amount_total": float(c.amount_total) if c and c.amount_total else 0,
            "version_no": cv.version_no,
            "customer_name": "",
        }

    else:
        raise BusinessException(code=42200, message=f"不支持的业务类型: {body.biz_type}")

    # Run analysis
    try:
        if body.analysis_type == "risk":
            result = await analyze_project_risk(entity_data)
        elif body.analysis_type == "profile":
            result = await generate_customer_profile(entity_data)
        elif body.analysis_type == "win_probability":
            result = await predict_win_probability(entity_data)
        elif body.analysis_type == "next_actions":
            result = await suggest_next_actions(entity_data)
        elif body.analysis_type == "quote_review":
            result = await review_quote(entity_data)
        elif body.analysis_type == "contract_review":
            result = await review_contract(entity_data)
        else:
            raise BusinessException(code=42200, message=f"不支持的分析类型: {body.analysis_type}")
    except BusinessException:
        raise
    except Exception as e:
        raise BusinessException(code=50000, message=f"AI 分析执行失败: {str(e)}")

    # Get token usage from the LLM call
    from app.common.ai_engine import get_last_usage
    usage = get_last_usage()

    # Save as AiTask + AiResult
    from app.domains.ai_center.schemas import AiTaskCreate, AiResultCreate
    task = await service.create_task(db, tenant_id, AiTaskCreate(
        task_type=body.analysis_type,
        biz_type=body.biz_type,
        biz_id=body.biz_id,
    ), current_user)

    await service.update_task(db, tenant_id, task.id, AiTaskUpdate(
        status="done",
        model_name=usage.get("model"),
        token_in=usage.get("token_in", 0),
        token_out=usage.get("token_out", 0),
        cost_est=usage.get("cost_est", 0),
    ))

    ai_result = await service.create_result(db, tenant_id, AiResultCreate(
        ai_task_id=task.id,
        result_json=result,
        risk_level=result.get("risk_level") if isinstance(result, dict) else None,
    ))

    # Update AI budget usage
    try:
        from datetime import datetime as dt, timezone as tz
        from app.domains.admin.models import TenantAiBudget
        period = dt.now(tz.utc).strftime("%Y-%m")
        budget = (await db.execute(
            select(TenantAiBudget).where(
                TenantAiBudget.tenant_id == tenant_id,
                TenantAiBudget.period == period,
            )
        )).scalar_one_or_none()
        if budget:
            budget.used_cost = float(budget.used_cost or 0) + usage.get("cost_est", 0)
            budget.used_tokens = (budget.used_tokens or 0) + usage.get("token_in", 0) + usage.get("token_out", 0)
            await db.commit()
    except Exception:
        pass  # Non-critical

    return ok({
        "task_id": task.id,
        "analysis_type": body.analysis_type,
        "result": result,
        "usage": usage,
    })


class SimilarProjectRequest(BaseModel):
    project_id: str


@router.post("/api/v1/ai/similar-projects")
async def find_similar(
    body: SimilarProjectRequest,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("project:view")),
):
    """Find projects similar to the given one based on AI analysis."""
    from app.domains.project.models import OpportunityProject
    from app.common.ai_engine import find_similar_projects
    from app.common.feature_flag import is_feature_enabled

    if not await is_feature_enabled(db, tenant_id, "ai_center"):
        from app.common.exceptions import BusinessException
        raise BusinessException(code=42300, message="AI 中心功能未启用，请联系管理员在功能开关中开启。")

    proj = (await db.execute(
        select(OpportunityProject).where(
            OpportunityProject.id == body.project_id,
            OpportunityProject.tenant_id == tenant_id,
        )
    )).scalar_one_or_none()
    if not proj:
        from app.common.exceptions import BusinessException
        from app.common.error_codes import NOT_FOUND
        raise BusinessException(code=NOT_FOUND, message="商机不存在")

    # Fetch other projects as candidates
    others = (await db.execute(
        select(OpportunityProject).where(
            OpportunityProject.tenant_id == tenant_id,
            OpportunityProject.id != body.project_id,
            OpportunityProject.is_deleted == False,
        ).limit(50)
    )).scalars().all()

    project_data = {
        "name": proj.name, "stage_code": proj.stage_code,
        "amount_expect": float(proj.amount_expect) if proj.amount_expect else 0,
        "industry": "",
    }
    candidates = [
        {
            "name": o.name, "stage_code": o.stage_code,
            "amount_expect": float(o.amount_expect) if o.amount_expect else 0,
            "status": o.status, "industry": "",
        }
        for o in others
    ]

    try:
        result = await find_similar_projects(project_data, candidates)
    except Exception as e:
        from app.common.exceptions import BusinessException
        raise BusinessException(code=50000, message=f"相似商机分析失败: {str(e)}")
    return ok(result or {"similar_projects": [], "insights": ""})


# ==================== Knowledge Base ====================

def _doc_dict(d) -> dict:
    return {
        "id": d.id, "title": d.title, "doc_type": d.doc_type,
        "source_filename": d.source_filename,
        "chunk_count": d.chunk_count, "status": d.status,
        "metadata_json": d.metadata_json,
        "created_by_name": d.created_by_name,
        "created_at": d.created_at.isoformat() if d.created_at else "",
        "updated_at": d.updated_at.isoformat() if d.updated_at else "",
    }


@router.get("/api/v1/ai/knowledge/documents")
async def list_knowledge_docs(
    doc_type: str | None = Query(None),
    keyword: str | None = Query(None),
    pageNo: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("project:view")),
):
    items, total = await knowledge_service.list_documents(
        db, tenant_id, doc_type=doc_type, keyword=keyword, page=pageNo, page_size=pageSize,
    )
    return ok({"items": [_doc_dict(d) for d in items], "total": total})


@router.get("/api/v1/ai/knowledge/documents/{doc_id}")
async def get_knowledge_doc(
    doc_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("project:view")),
):
    doc = await knowledge_service.get_document(db, tenant_id, doc_id)
    data = _doc_dict(doc)
    data["content_text"] = doc.content_text
    return ok(data)


@router.post("/api/v1/ai/knowledge/documents")
async def create_knowledge_doc(
    body: KnowledgeDocCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("project:edit")),
):
    doc = await knowledge_service.create_document(
        db, tenant_id, body.model_dump(), current_user,
    )
    return ok(_doc_dict(doc))


@router.put("/api/v1/ai/knowledge/documents/{doc_id}")
async def update_knowledge_doc(
    doc_id: str, body: KnowledgeDocUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("project:edit")),
):
    doc = await knowledge_service.update_document(
        db, tenant_id, doc_id, body.model_dump(exclude_unset=True),
    )
    return ok(_doc_dict(doc))


@router.delete("/api/v1/ai/knowledge/documents/{doc_id}")
async def delete_knowledge_doc(
    doc_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("project:edit")),
):
    await knowledge_service.delete_document(db, tenant_id, doc_id)
    return ok(None)


@router.post("/api/v1/ai/knowledge/search")
async def search_knowledge(
    body: KnowledgeSearchQuery,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("project:view")),
):
    chunks = await knowledge_service.search_chunks(
        db, tenant_id, body.query, doc_type=body.doc_type, top_k=body.top_k,
    )
    return ok(chunks)
