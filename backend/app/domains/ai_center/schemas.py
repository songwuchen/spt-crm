from pydantic import BaseModel
from typing import Optional


class AiTaskCreate(BaseModel):
    task_type: str
    biz_type: Optional[str] = None
    biz_id: Optional[str] = None
    priority: Optional[int] = 5
    model_name: Optional[str] = None
    prompt_template_id: Optional[str] = None
    input_ref_json: Optional[dict] = None
    budget_json: Optional[dict] = None


class AiTaskUpdate(BaseModel):
    status: Optional[str] = None
    model_name: Optional[str] = None
    token_in: Optional[int] = None
    token_out: Optional[int] = None
    cost_est: Optional[float] = None
    error_message: Optional[str] = None


class AiResultCreate(BaseModel):
    ai_task_id: str
    result_json: Optional[dict] = None
    evidence_json: Optional[dict] = None
    risk_level: Optional[str] = None
    quality_score: Optional[float] = None


class AiPromptTemplateCreate(BaseModel):
    code: str
    name: str
    task_type: str
    template_text: Optional[str] = None
    output_schema_json: Optional[dict] = None
    guardrails_json: Optional[dict] = None
    is_active: Optional[bool] = True


class AiPromptTemplateUpdate(BaseModel):
    name: Optional[str] = None
    template_text: Optional[str] = None
    output_schema_json: Optional[dict] = None
    guardrails_json: Optional[dict] = None
    is_active: Optional[bool] = None


# ==================== Knowledge Base ====================

class KnowledgeDocCreate(BaseModel):
    title: str
    doc_type: str = "other"
    content_text: str = ""
    source_filename: Optional[str] = None
    metadata_json: Optional[dict] = None


class KnowledgeDocUpdate(BaseModel):
    title: Optional[str] = None
    doc_type: Optional[str] = None
    content_text: Optional[str] = None
    metadata_json: Optional[dict] = None
    status: Optional[str] = None


class KnowledgeSearchQuery(BaseModel):
    query: str
    doc_type: Optional[str] = None
    top_k: int = 5
