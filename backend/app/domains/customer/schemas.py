from typing import Optional, List, Union, Any
from datetime import date
from pydantic import BaseModel, Field, field_validator


class CustomerJdyFields(BaseModel):
    """简道云客户信息对齐字段。"""
    is_smart_filing: Optional[bool] = None
    is_foreign_trade: Optional[bool] = None
    need_info_distribute: Optional[bool] = None
    registered_capital: Optional[float] = None
    paid_in_capital: Optional[float] = None
    founded_year: Optional[int] = Field(None, ge=1800, le=2100)
    parent_company_note: Optional[str] = None
    customer_nature: Optional[str] = Field(None, max_length=50)
    customer_relation: Optional[str] = Field(None, max_length=50)
    primary_contact_title: Optional[str] = Field(None, max_length=100)
    wage_insurance_status: Optional[str] = Field(None, max_length=50)
    is_company_customer: Optional[bool] = None
    taxpayer_id: Optional[str] = Field(None, max_length=64)
    invoice_address_phone: Optional[str] = Field(None, max_length=300)
    bank_account: Optional[str] = Field(None, max_length=200)
    foreign_customer_code: Optional[str] = Field(None, max_length=100)
    foreign_customer_type: Optional[str] = Field(None, max_length=50)
    focus_product: Optional[str] = Field(None, max_length=100)
    customer_email: Optional[str] = Field(None, max_length=200)
    main_products_json: Optional[List[Any]] = None
    legal_person: Optional[str] = Field(None, max_length=100)
    smart_industry_category: Optional[str] = Field(None, max_length=200)
    annual_run_days: Optional[str] = Field(None, max_length=50)
    floor_area: Optional[str] = Field(None, max_length=100)
    financial_status: Optional[str] = None
    business_status: Optional[str] = None
    annual_power_usage: Optional[str] = Field(None, max_length=100)
    daily_operate_hours: Optional[str] = Field(None, max_length=50)


class CustomerCreate(CustomerJdyFields):
    name: str = Field(..., min_length=1, max_length=200)
    as_draft: bool = False  # True=仅存草稿不发起客户信息审批
    customer_code: Optional[str] = Field(None, max_length=64)
    short_name: Optional[str] = Field(None, max_length=100)
    industry: Optional[str] = None
    scale_level: Optional[str] = None
    region: Optional[str] = Field(None, max_length=200)
    province: Optional[str] = Field(None, max_length=50)
    city: Optional[str] = Field(None, max_length=50)
    district: Optional[str] = Field(None, max_length=50)
    region_code: Optional[str] = Field(None, max_length=12)
    address: Optional[str] = Field(None, max_length=500)
    website: Optional[str] = Field(None, max_length=500)
    source: Optional[str] = None
    level: Optional[str] = None
    owner_id: Optional[str] = None
    tags_json: Optional[Union[dict, list]] = None
    custom_fields_json: Optional[dict] = None
    remark: Optional[str] = Field(None, max_length=2000)
    # ===== 商机要素(BANT)快照 + 公司档案增补 =====
    intent_level: Optional[str] = None            # 采购意向类别 A/B/C/D（缺省由采购时间推档）
    key_contact_id: Optional[str] = None          # 关键人（contacts.id）
    demand: Optional[str] = None                  # 核心需求
    need_match_level: Optional[str] = None         # 产品与需求匹配程度
    budget_amount: Optional[float] = None          # 客户预算
    expected_purchase_date: Optional[date] = None  # 预计采购时间
    headcount: Optional[int] = None                # 公司总人数
    industry_l1: Optional[str] = None
    industry_l2: Optional[str] = None
    industry_l3: Optional[str] = None
    country: Optional[str] = Field(None, max_length=50)
    postal_code: Optional[str] = Field(None, max_length=20)
    currency: Optional[str] = Field(None, max_length=10)
    pool_id: Optional[str] = None                  # 所属区域公海

    @field_validator("level", "intent_level")
    @classmethod
    def validate_level(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("A", "B", "C", "D"):
            raise ValueError("级别必须为 A/B/C/D")
        return v


class CustomerUpdate(CustomerJdyFields):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    customer_code: Optional[str] = Field(None, max_length=64)
    short_name: Optional[str] = Field(None, max_length=100)
    industry: Optional[str] = None
    scale_level: Optional[str] = None
    region: Optional[str] = Field(None, max_length=200)
    province: Optional[str] = Field(None, max_length=50)
    city: Optional[str] = Field(None, max_length=50)
    district: Optional[str] = Field(None, max_length=50)
    region_code: Optional[str] = Field(None, max_length=12)
    address: Optional[str] = Field(None, max_length=500)
    website: Optional[str] = Field(None, max_length=500)
    source: Optional[str] = None
    level: Optional[str] = None
    status: Optional[str] = None
    owner_id: Optional[str] = None
    tags_json: Optional[Union[dict, list]] = None
    custom_fields_json: Optional[dict] = None
    remark: Optional[str] = Field(None, max_length=2000)
    # ===== 商机要素(BANT)快照 + 公司档案增补 =====
    intent_level: Optional[str] = None
    key_contact_id: Optional[str] = None
    demand: Optional[str] = None
    need_match_level: Optional[str] = None
    budget_amount: Optional[float] = None
    expected_purchase_date: Optional[date] = None
    headcount: Optional[int] = None
    industry_l1: Optional[str] = None
    industry_l2: Optional[str] = None
    industry_l3: Optional[str] = None
    country: Optional[str] = Field(None, max_length=50)
    postal_code: Optional[str] = Field(None, max_length=20)
    currency: Optional[str] = Field(None, max_length=10)
    pool_id: Optional[str] = None

    @field_validator("level", "intent_level")
    @classmethod
    def validate_level(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("A", "B", "C", "D"):
            raise ValueError("级别必须为 A/B/C/D")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("active", "inactive"):
            raise ValueError("状态必须为 active/inactive")
        return v


class CustomerOut(CustomerJdyFields):
    id: str
    customer_code: Optional[str] = None
    name: str
    short_name: Optional[str] = None
    industry: Optional[str] = None
    scale_level: Optional[str] = None
    region: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    region_code: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    owner_id: Optional[str] = None
    owner_name: Optional[str] = None
    source: Optional[str] = None
    level: Optional[str] = None
    status: str
    review_status: Optional[str] = None
    review_flow_id: Optional[str] = None
    reject_reason: Optional[str] = None
    tags_json: Optional[Union[dict, list]] = None
    custom_fields_json: Optional[dict] = None
    remark: Optional[str] = None
    intent_level: Optional[str] = None
    key_contact_id: Optional[str] = None
    demand: Optional[str] = None
    need_match_level: Optional[str] = None
    budget_amount: Optional[float] = None
    expected_purchase_date: Optional[str] = None
    headcount: Optional[int] = None
    industry_l1: Optional[str] = None
    industry_l2: Optional[str] = None
    industry_l3: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    currency: Optional[str] = None
    department_id: Optional[str] = None
    department_name: Optional[str] = None
    updated_by_id: Optional[str] = None
    updated_by_name: Optional[str] = None
    last_activity_at: Optional[str] = None
    last_activity_by_name: Optional[str] = None
    won_deal_count: int = 0
    pool_id: Optional[str] = None
    pool_source: Optional[str] = None
    pool_entered_at: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""

    model_config = {"from_attributes": True}


class ContactCreate(BaseModel):
    name: str
    title: Optional[str] = None
    department: Optional[str] = None
    role_type: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    is_primary: bool = False
    reports_to_id: Optional[str] = None
    remark: Optional[str] = None
    custom_fields_json: Optional[dict] = None


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    department: Optional[str] = None
    role_type: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    is_primary: Optional[bool] = None
    reports_to_id: Optional[str] = None
    remark: Optional[str] = None
    custom_fields_json: Optional[dict] = None


class ContactOut(BaseModel):
    id: str
    customer_id: str
    name: str
    title: Optional[str] = None
    department: Optional[str] = None
    role_type: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    is_primary: bool
    reports_to_id: Optional[str] = None
    remark: Optional[str] = None
    custom_fields_json: Optional[dict] = None

    model_config = {"from_attributes": True}



class RelationCreate(BaseModel):
    to_customer_id: str
    relation_type: str
    note: Optional[str] = None


class ShareCreate(BaseModel):
    shared_to_type: str = "user"
    shared_to_id: str
    shared_to_name: Optional[str] = None
    permission: str = "view"


class BatchReleaseRequest(BaseModel):
    customer_ids: List[str]


class CustomerPoolCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=300)
    region_scope: Optional[str] = Field(None, max_length=300)  # 行政区划编码前缀，逗号分隔
    rules_json: Optional[dict] = None  # {enabled, idle_days:{A,B,C,D}, default_idle_days}
    is_default: bool = False
    is_active: bool = True
    sort_order: int = 0


class CustomerPoolUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=300)
    region_scope: Optional[str] = Field(None, max_length=300)
    rules_json: Optional[dict] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None
