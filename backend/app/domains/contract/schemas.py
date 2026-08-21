from typing import Optional, Union
from datetime import date
from pydantic import BaseModel, Field

# 收款计划 / 合同明细 等是多行子表（数组），也可能是单对象 —— 同时接受
JsonTerms = Union[dict, list]


class AllocateDrawingNoRequest(BaseModel):
    """新建合同登记「重新取号」。"""
    drawing_no: Optional[str] = Field(None, max_length=100, description="当前表单上的图纸编号")
    order_date: Optional[str] = Field(
        None,
        description="已废弃：图纸编号不再使用订货日；保留仅为兼容旧前端",
        deprecated=True,
    )
    number_attr: Optional[str] = Field(
        None, max_length=16,
        description="编号属性 WMGF|SY，与合同图纸对应表一致；默认 WMGF",
    )


class ContractCreate(BaseModel):
    title: Optional[str] = None
    project_id: Optional[str] = Field(None, max_length=36)  # 可选；合同管理入口可不挂商机
    # 直接关联客户主数据（可不挂商机）；有商机时可与商机客户一致或单独指定
    customer_id: Optional[str] = Field(None, max_length=36)
    # 合同号由业务手填；图纸编号打开表单时预览，创建时沿用（冲突则系统另取）
    contract_no: Optional[str] = Field(None, max_length=64)
    amount_total: Optional[float] = Field(None, ge=0)
    end_date: Optional[date] = None
    drawing_no: Optional[str] = Field(None, max_length=100)
    peer_contract_no: Optional[str] = Field(None, max_length=100)
    acquire_method: Optional[str] = Field(None, max_length=64)
    delivery_date: Optional[date] = None
    change_type: Optional[str] = Field(None, max_length=16)  # new / change
    order_date: Optional[date] = None
    card_date: Optional[date] = None
    payment_terms_json: Optional[JsonTerms] = None
    delivery_terms_json: Optional[JsonTerms] = None
    registration_json: Optional[dict] = None
    key_clauses_json: Optional[JsonTerms] = None
    assignee_id: Optional[str] = None
    assignee_name: Optional[str] = None
    department_id: Optional[str] = None
    department_name: Optional[str] = None
    custom_fields_json: Optional[dict] = None
    as_draft: bool = False  # True=仅存草稿，跳过必填校验


class ContractUpdate(BaseModel):
    status: Optional[str] = None
    customer_id: Optional[str] = Field(None, max_length=36)
    amount_total: Optional[float] = Field(None, ge=0)
    end_date: Optional[date] = None
    drawing_no: Optional[str] = Field(None, max_length=100)
    peer_contract_no: Optional[str] = Field(None, max_length=100)
    acquire_method: Optional[str] = Field(None, max_length=64)
    delivery_date: Optional[date] = None
    change_type: Optional[str] = Field(None, max_length=16)
    order_date: Optional[date] = None
    card_date: Optional[date] = None
    payment_terms_json: Optional[JsonTerms] = None
    delivery_terms_json: Optional[JsonTerms] = None
    registration_json: Optional[dict] = None
    assignee_id: Optional[str] = None
    assignee_name: Optional[str] = None
    department_id: Optional[str] = None
    department_name: Optional[str] = None
    custom_fields_json: Optional[dict] = None
    as_draft: bool = False  # True=仅存草稿，跳过必填校验
    contract_no: Optional[str] = Field(None, max_length=64)


class ContractVersionUpdate(BaseModel):
    title: Optional[str] = None
    doc_attachment_id: Optional[str] = None
    key_clauses_json: Optional[JsonTerms] = None
    risk_level: Optional[str] = None
    status: Optional[str] = None


class ContractVersionSubmit(BaseModel):
    """提交版本审批；assignee 仅在回退旧审批引擎且无策略时需要。"""
    assignee_ids: list[str] = []
    assignee_names: Optional[list[str]] = None


class ContractFromQuote(BaseModel):
    """Convert a quote into a contract."""
    quote_id: str


class ContractSign(BaseModel):
    signed_date: str
