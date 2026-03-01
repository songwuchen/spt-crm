from sqlalchemy import String, Text, JSON, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class AiPromptTemplate(TenantScopedBase):
    __tablename__ = "ai_prompt_templates"

    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # demand_extract / quote_risk / contract_risk / similar_project / meeting_summary / next_action
    template_text: Mapped[str | None] = mapped_column(Text)
    output_schema_json: Mapped[dict | None] = mapped_column(JSON)
    guardrails_json: Mapped[dict | None] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(default=True)


class AiTask(TenantScopedBase):
    __tablename__ = "ai_tasks"

    task_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # demand_extract / quote_risk / contract_risk / similar_project / meeting_summary / next_action / recommendation
    biz_type: Mapped[str | None] = mapped_column(String(32))
    # project / quote_version / contract_version / lead / activity
    biz_id: Mapped[str | None] = mapped_column(String(36), index=True)
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    # queued / running / done / failed
    priority: Mapped[int] = mapped_column(Integer, default=5)
    model_name: Mapped[str | None] = mapped_column(String(100))
    prompt_template_id: Mapped[str | None] = mapped_column(String(36))
    input_ref_json: Mapped[dict | None] = mapped_column(JSON)
    budget_json: Mapped[dict | None] = mapped_column(JSON)
    # {"max_tokens": 1800, "max_cost": 0.2}
    token_in: Mapped[int | None] = mapped_column(Integer)
    token_out: Mapped[int | None] = mapped_column(Integer)
    cost_est: Mapped[float | None] = mapped_column(Numeric(10, 4))
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[str | None] = mapped_column(String(36))
    created_by_name: Mapped[str | None] = mapped_column(String(100))


class AiResult(TenantScopedBase):
    __tablename__ = "ai_results"

    ai_task_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    result_json: Mapped[dict | None] = mapped_column(JSON)
    evidence_json: Mapped[dict | None] = mapped_column(JSON)
    # [{"ref":"doc:912#chunk:h1","type":"doc_chunk","snippet":"..."},...]
    risk_level: Mapped[str | None] = mapped_column(String(2))
    # L / M / H
    quality_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
