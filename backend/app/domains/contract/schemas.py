from typing import Optional, Union
from datetime import date
from pydantic import BaseModel, Field

# 收款计划 / 合同明细 等是多行子表（数组），也可能是单对象 —— 同时接受
JsonTerms = Union[dict, list]


class ContractCreate(BaseModel):
    title: Optional[str] = None
    amount_total: Optional[float] = Field(None, ge=0)
    end_date: Optional[date] = None
    payment_terms_json: Optional[JsonTerms] = None
    delivery_terms_json: Optional[JsonTerms] = None
    key_clauses_json: Optional[JsonTerms] = None
    assignee_id: Optional[str] = None
    assignee_name: Optional[str] = None
    department_id: Optional[str] = None
    department_name: Optional[str] = None


class ContractUpdate(BaseModel):
    status: Optional[str] = None
    amount_total: Optional[float] = Field(None, ge=0)
    end_date: Optional[date] = None
    payment_terms_json: Optional[JsonTerms] = None
    delivery_terms_json: Optional[JsonTerms] = None
    assignee_id: Optional[str] = None
    assignee_name: Optional[str] = None
    department_id: Optional[str] = None
    department_name: Optional[str] = None


class ContractVersionUpdate(BaseModel):
    title: Optional[str] = None
    doc_attachment_id: Optional[str] = None
    key_clauses_json: Optional[JsonTerms] = None
    risk_level: Optional[str] = None
    status: Optional[str] = None


class ContractFromQuote(BaseModel):
    """Convert a quote into a contract."""
    quote_id: str


class ContractSign(BaseModel):
    signed_date: str
