from typing import Literal, Optional, List
from datetime import date, datetime
from pydantic import BaseModel, Field, field_validator, model_validator
import re


LeadCategory = Literal["self_reported", "distributed"]
LeadCountryType = Literal["domestic", "overseas"]
LeadCustomerNewness = Literal["new", "old"]
LeadIntelDecision = Literal["include", "attack", "return", "revise", "draft"]


class LeadProductIn(BaseModel):
    """线索产品明细(子表)一行。"""
    product_name: Optional[str] = Field(None, max_length=300)
    product_spec: Optional[str] = Field(None, max_length=300)
    quantity: Optional[float] = Field(None, ge=0)
    remark: Optional[str] = Field(None, max_length=2000)


class LeadProductOut(LeadProductIn):
    id: str
    model_config = {"from_attributes": True}


def _validate_email(v: Optional[str]) -> Optional[str]:
    if v is not None and v != "" and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
        raise ValueError("邮箱格式不正确")
    return v


class LeadCreate(BaseModel):
    # max_length 与 models.Lead 的列宽保持一致（title/company_name 300、contact_phone 30），
    # 早前 schema 比列窄，会把列宽内的合法值提前判 422。
    title: str = Field(..., min_length=1, max_length=300)
    # 必填与否交由租户字段策略(native_field_catalog + enforce_native_field_policy)判定，
    # 出厂默认仍必填；这里若写死 required，租户在后台关掉必填也依然会被 422 挡回。
    # title 例外：leads.title 是 NOT NULL 列，属 system_required，任何租户都不可放开。
    company_name: Optional[str] = Field(None, max_length=300)
    contact_name: Optional[str] = Field(None, max_length=100)
    contact_phone: Optional[str] = Field(None, max_length=30)
    contact_email: Optional[str] = Field(None, max_length=200)
    contact_raw_json: Optional[dict] = None
    source: Optional[str] = None
    source_detail_json: Optional[dict] = None
    demand_summary: Optional[str] = Field(None, max_length=2000)
    industry: Optional[str] = None
    customer_type: Optional[str] = Field(None, max_length=50)
    category: Optional[LeadCategory] = None
    country_type: Optional[LeadCountryType] = None
    country_name: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=200)
    province: Optional[str] = Field(None, max_length=50)
    city: Optional[str] = Field(None, max_length=50)
    district: Optional[str] = Field(None, max_length=50)
    region_code: Optional[str] = Field(None, max_length=12)
    department_id: Optional[str] = Field(None, max_length=36)
    budget_range: Optional[str] = None
    reporter_id: Optional[str] = Field(None, max_length=36)
    reported_at: Optional[datetime] = None
    biz_date: Optional[date] = None
    remark: Optional[str] = Field(None, max_length=2000)
    # 简道云「申报信息」对齐
    has_internal_conflict: Optional[str] = Field(None, max_length=10)
    conflict_note: Optional[str] = Field(None, max_length=500)
    bid_result: Optional[str] = Field(None, max_length=50)
    bid_fail_reason: Optional[str] = Field(None, max_length=500)
    entrust_status: Optional[str] = Field(None, max_length=20)
    entrust_issued_at: Optional[datetime] = None
    entrust_term: Optional[str] = Field(None, max_length=100)
    project_activity: Optional[str] = Field(None, max_length=50)
    project_recent: Optional[str] = Field(None, max_length=500)
    follow_progress: Optional[str] = Field(None, max_length=500)
    site_visit: Optional[str] = Field(None, max_length=500)
    report_project_status: Optional[str] = Field(None, max_length=50)
    assess_remark: Optional[str] = Field(None, max_length=2000)
    # 评估区（简道云审批填写）
    customer_newness: Optional[LeadCustomerNewness] = None  # new / old
    reject_reason: Optional[str] = Field(None, max_length=2000)
    products: Optional[List[LeadProductIn]] = None
    custom_fields_json: Optional[dict] = None
    # True=仅落库不启审（存草稿）；False/默认=创建后自动提交情报审批
    as_draft: bool = False
    # 外部指定项目号（如简道云「项目编号」）；有值则跳过 CRM 自增规则。
    lead_code: Optional[str] = Field(None, max_length=64)

    @field_validator("contact_email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        return _validate_email(v)

    @model_validator(mode="after")
    def _country_name_only_when_overseas(self):
        # Guard against stale country_name sticking around after switching back to domestic
        if self.country_type != "overseas":
            self.country_name = None
        return self


class LeadUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=300)
    company_name: Optional[str] = Field(None, min_length=1, max_length=300)
    contact_name: Optional[str] = Field(None, max_length=100)
    contact_phone: Optional[str] = Field(None, max_length=30)
    contact_email: Optional[str] = Field(None, max_length=200)
    contact_raw_json: Optional[dict] = None
    source: Optional[str] = None
    source_detail_json: Optional[dict] = None
    demand_summary: Optional[str] = Field(None, max_length=2000)
    industry: Optional[str] = None
    customer_type: Optional[str] = Field(None, max_length=50)
    category: Optional[LeadCategory] = None
    country_type: Optional[LeadCountryType] = None
    country_name: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=200)
    province: Optional[str] = Field(None, max_length=50)
    city: Optional[str] = Field(None, max_length=50)
    district: Optional[str] = Field(None, max_length=50)
    region_code: Optional[str] = Field(None, max_length=12)
    department_id: Optional[str] = Field(None, max_length=36)
    budget_range: Optional[str] = None
    reporter_id: Optional[str] = Field(None, max_length=36)
    reported_at: Optional[datetime] = None
    biz_date: Optional[date] = None
    status: Optional[str] = None
    remark: Optional[str] = Field(None, max_length=2000)
    has_internal_conflict: Optional[str] = Field(None, max_length=10)
    conflict_note: Optional[str] = Field(None, max_length=500)
    bid_result: Optional[str] = Field(None, max_length=50)
    bid_fail_reason: Optional[str] = Field(None, max_length=500)
    entrust_status: Optional[str] = Field(None, max_length=20)
    entrust_issued_at: Optional[datetime] = None
    entrust_term: Optional[str] = Field(None, max_length=100)
    project_activity: Optional[str] = Field(None, max_length=50)
    project_recent: Optional[str] = Field(None, max_length=500)
    follow_progress: Optional[str] = Field(None, max_length=500)
    site_visit: Optional[str] = Field(None, max_length=500)
    report_project_status: Optional[str] = Field(None, max_length=50)
    assess_remark: Optional[str] = Field(None, max_length=2000)
    customer_newness: Optional[LeadCustomerNewness] = None
    reject_reason: Optional[str] = Field(None, max_length=2000)
    products: Optional[List[LeadProductIn]] = None
    custom_fields_json: Optional[dict] = None
    # 开放平台补全/更正项目号（如简道云「项目编号」）
    lead_code: Optional[str] = Field(None, max_length=64)

    @field_validator("contact_email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        return _validate_email(v)


class LeadIntelReviewIn(BaseModel):
    """情报审批裁定：收录 / 袭击 / 驳回 / 回退 / 暂存。"""
    decision: LeadIntelDecision
    task_id: str = Field(..., min_length=1, max_length=36)
    customer_newness: Optional[LeadCustomerNewness] = None
    return_reason: Optional[str] = Field(None, max_length=2000)
    opinion: Optional[str] = Field(None, max_length=2000)
    assess_remark: Optional[str] = Field(None, max_length=2000)

    @model_validator(mode="after")
    def _require_fields_by_decision(self):
        if self.decision in ("include", "attack", "return", "revise") and not self.customer_newness:
            raise ValueError("请选择客户类型（新/老）")
        if self.decision == "return" and not (self.return_reason or "").strip():
            raise ValueError("驳回须填写驳回原因")
        if self.decision == "revise" and not (self.return_reason or "").strip():
            raise ValueError("回退须填写回退原因（供申报人修改参考）")
        return self


class LeadReactivationSubmitIn(BaseModel):
    """180 天重激活跟进提交。"""
    project_recent: Optional[str] = Field(None, max_length=500)
    follow_progress: Optional[str] = Field(None, max_length=500)
    site_visit: Optional[str] = Field(None, max_length=500)
    report_project_status: str = Field(..., min_length=1, max_length=50)


# 线索出参没有 Out schema：序列化统一走 router._lead_dict()。
# 曾存在的 LeadOut 是零引用死代码，且已与 _lead_dict 分叉（少 lead_code、多 custom_fields_json），
# 正是「看起来权威、实际没人用」导致字段遗漏的根源，故删除。改出参请直接改 _lead_dict。
