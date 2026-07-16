import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
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
        analyze_receivable, recommend_sales_script,
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

    elif body.biz_type == "contract":
        # 合同 + 应收账款聚合（用于 receivable / sales_script）
        from app.domains.contract.models import Contract
        from app.domains.payment.models import PaymentPlan, PaymentRecord
        from app.domains.customer.models import Customer
        from sqlalchemy import select, func
        from datetime import date, datetime

        def _as_date(v):
            if isinstance(v, date):
                return v
            if isinstance(v, str) and v:
                try:
                    return datetime.fromisoformat(v[:10]).date()
                except ValueError:
                    return None
            return None

        c = (await db.execute(
            select(Contract).where(Contract.id == body.biz_id, Contract.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not c:
            raise BusinessException(code=NOT_FOUND, message="合同不存在")
        amount_total = float(c.amount_total or 0)
        collected = 0.0
        plans = []
        if c.project_id:
            collected = float((await db.execute(
                select(func.coalesce(func.sum(PaymentRecord.amount), 0)).where(
                    PaymentRecord.project_id == c.project_id, PaymentRecord.tenant_id == tenant_id)
            )).scalar() or 0)
            plans = (await db.execute(
                select(PaymentPlan).where(PaymentPlan.source_contract_id == c.id, PaymentPlan.tenant_id == tenant_id)
            )).scalars().all()
            if not plans:
                plans = (await db.execute(
                    select(PaymentPlan).where(PaymentPlan.project_id == c.project_id, PaymentPlan.tenant_id == tenant_id)
                )).scalars().all()
        outstanding = round(amount_total - collected, 2)
        today = date.today()
        overdue_amount = 0.0
        overdue_days = 0
        overdue_cnt = 0
        for p in plans:
            d = _as_date(p.due_date)
            if p.status != "paid" and d and d < today:
                overdue_amount += float(p.amount or 0)
                overdue_cnt += 1
                overdue_days = max(overdue_days, (today - d).days)
        customer_name = ""
        if c.customer_id:
            customer_name = (await db.execute(
                select(Customer.name).where(Customer.id == c.customer_id, Customer.tenant_id == tenant_id)
            )).scalar_one_or_none() or ""
        entity_data = {
            "contract_no": c.contract_no,
            "amount_total": amount_total,
            "collected": round(collected, 2),
            "outstanding": outstanding,
            "collection_rate": round(collected / amount_total * 100, 1) if amount_total else 0,
            "overdue_amount": round(overdue_amount, 2),
            "overdue_days": overdue_days,
            "overdue_plan_count": overdue_cnt,
            "plan_count": len(plans),
            "customer_name": customer_name,
            "signed_date": str(c.signed_date or ""),
            "end_date": str(c.end_date or ""),
        }

    else:
        raise BusinessException(code=42200, message=f"不支持的业务类型: {body.biz_type}")

    # 解析租户后台配置的对话模型(未配置则 chat_cfg=None → ai_engine 回退 env/mock)
    from app.domains.admin.service import resolve_ai_config
    ai_cfg = await resolve_ai_config(db, tenant_id)
    chat_cfg = ai_cfg.get("chat")

    # Run analysis
    try:
        if body.analysis_type == "risk":
            result = await analyze_project_risk(entity_data, tenant_id=tenant_id, chat_cfg=chat_cfg)
        elif body.analysis_type == "profile":
            result = await generate_customer_profile(entity_data, tenant_id=tenant_id, chat_cfg=chat_cfg)
        elif body.analysis_type == "win_probability":
            result = await predict_win_probability(entity_data, chat_cfg=chat_cfg)
        elif body.analysis_type == "next_actions":
            result = await suggest_next_actions(entity_data, tenant_id=tenant_id, chat_cfg=chat_cfg)
        elif body.analysis_type == "quote_review":
            result = await review_quote(entity_data, chat_cfg=chat_cfg)
        elif body.analysis_type == "contract_review":
            result = await review_contract(entity_data, chat_cfg=chat_cfg)
        elif body.analysis_type == "receivable":
            result = await analyze_receivable(entity_data, chat_cfg=chat_cfg)
        elif body.analysis_type == "sales_script":
            result = await recommend_sales_script(entity_data, chat_cfg=chat_cfg)
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

    from app.domains.admin.service import resolve_ai_config
    _cfg = await resolve_ai_config(db, tenant_id)
    try:
        result = await find_similar_projects(project_data, candidates, chat_cfg=_cfg.get("chat"))
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


# ==================== AI 助手 / RAG 问答 ====================

class AssistantRequest(BaseModel):
    question: str
    history: Optional[list[dict]] = None   # [{role: user/assistant, content}]
    use_knowledge: bool = True

_NO_AI_MSG = "AI 对话未启用。请在 系统设置 → AI模型 配置对话模型并启用后再使用。"


def _assistant_system(context: str) -> str:
    if context:
        return (
            "你是企业 CRM 的智能助手。请优先依据下面提供的【知识库片段】回答用户问题；"
            "若片段中确无相关信息，可基于常识回答，但要说明该结论未必来自企业知识库，切勿编造具体制度或数字。"
            "回答用简体中文、条理清晰，引用知识库内容时可在句末用 [片段N] 标注来源。\n\n【知识库片段】\n" + context
        )
    return (
        "你是企业 CRM 的智能助手。用简体中文、条理清晰地回答用户问题。"
        "若涉及企业内部制度或数据而你不确定，请提示用户到知识库或系统中核实，不要编造。"
    )


async def _require_ai(db: AsyncSession, tenant_id: str):
    from app.common.feature_flag import is_feature_enabled
    from app.common.exceptions import BusinessException
    if not await is_feature_enabled(db, tenant_id, "ai_center"):
        raise BusinessException(code=42300, message="AI 中心功能未启用，请联系管理员在功能开关中开启。")


async def _assistant_prepare(db: AsyncSession, tenant_id: str, body: "AssistantRequest"):
    from app.domains.admin.service import resolve_ai_config
    cfg = await resolve_ai_config(db, tenant_id)
    chat_cfg = cfg.get("chat")
    context, sources = "", []
    if body.use_knowledge:
        context, sources = await knowledge_service.retrieve_context(db, tenant_id, body.question)
    system = _assistant_system(context)
    hist = [
        {"role": m.get("role"), "content": m.get("content")}
        for m in (body.history or [])
        if m.get("role") in ("user", "assistant") and m.get("content")
    ][-8:]
    messages = [*hist, {"role": "user", "content": body.question}]
    return chat_cfg, system, messages, sources


async def _charge_ai_budget(tenant_id: str, usage: dict):
    """流式对话结束后计入月度 AI 预算(用独立会话,避免与请求会话生命周期耦合)。"""
    try:
        from datetime import datetime as _dt, timezone as _tz
        from app.database import async_session_factory
        from app.domains.admin.models import TenantAiBudget
        async with async_session_factory() as db2:
            period = _dt.now(_tz.utc).strftime("%Y-%m")
            b = (await db2.execute(
                select(TenantAiBudget).where(
                    TenantAiBudget.tenant_id == tenant_id, TenantAiBudget.period == period)
            )).scalar_one_or_none()
            if b:
                b.used_cost = float(b.used_cost or 0) + (usage.get("cost_est") or 0)
                b.used_tokens = (b.used_tokens or 0) + (usage.get("token_in", 0) + usage.get("token_out", 0))
                await db2.commit()
    except Exception:
        pass


@router.post("/api/v1/ai/assistant")
async def ai_assistant(
    body: AssistantRequest,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("project:view")),
):
    """非流式 RAG 问答(整段返回)。"""
    await _require_ai(db, tenant_id)
    chat_cfg, system, messages, sources = await _assistant_prepare(db, tenant_id, body)
    if not chat_cfg:
        return ok({"answer": _NO_AI_MSG, "sources": [], "usage": None})
    from app.common.ai_engine import stream_llm, get_last_usage
    buf = []
    async for delta in stream_llm(system, messages, chat_cfg):
        buf.append(delta)
    usage = get_last_usage()
    await _charge_ai_budget(tenant_id, usage)
    return ok({"answer": "".join(buf), "sources": sources, "usage": usage})


@router.post("/api/v1/ai/assistant/stream")
async def ai_assistant_stream(
    body: AssistantRequest,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("project:view")),
):
    """流式 RAG 问答(SSE)。事件: sources(一次) / delta(多次) / done(含usage) / error。"""
    await _require_ai(db, tenant_id)
    chat_cfg, system, messages, sources = await _assistant_prepare(db, tenant_id, body)

    async def gen():
        yield f"event: sources\ndata: {json.dumps(sources, ensure_ascii=False)}\n\n"
        if not chat_cfg:
            yield f"event: delta\ndata: {json.dumps({'t': _NO_AI_MSG}, ensure_ascii=False)}\n\n"
            yield "event: done\ndata: {}\n\n"
            return
        from app.common.ai_engine import stream_llm, get_last_usage
        try:
            async for delta in stream_llm(system, messages, chat_cfg):
                yield f"event: delta\ndata: {json.dumps({'t': delta}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)[:200]}, ensure_ascii=False)}\n\n"
        usage = get_last_usage()
        await _charge_ai_budget(tenant_id, usage)
        yield f"event: done\ndata: {json.dumps({'usage': usage}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
