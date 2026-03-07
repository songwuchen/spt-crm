from typing import Optional
from datetime import date
from pydantic import BaseModel


class ContractCreate(BaseModel):
    title: Optional[str] = None
    amount_total: Optional[float] = None
    end_date: Optional[date] = None
    payment_terms_json: Optional[dict] = None
    delivery_terms_json: Optional[dict] = None


class ContractUpdate(BaseModel):
    status: Optional[str] = None
    amount_total: Optional[float] = None
    end_date: Optional[date] = None
    payment_terms_json: Optional[dict] = None
    delivery_terms_json: Optional[dict] = None


class ContractVersionUpdate(BaseModel):
    title: Optional[str] = None
    doc_attachment_id: Optional[str] = None
    key_clauses_json: Optional[dict] = None
    risk_level: Optional[str] = None
    status: Optional[str] = None


class ContractFromQuote(BaseModel):
    """Convert a quote into a contract."""
    quote_id: str


class ContractSign(BaseModel):
    signed_date: str
