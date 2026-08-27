from typing import Optional, List, Union, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator


# Full catalogue of scopes an app can be granted.
ALL_SCOPES = [
    "crm.customer.read",
    "crm.contact.read",
    "crm.project.read",
    "crm.contract.read",
    "crm.quote.read",
    "crm.order.read",
    "crm.payment.read",
    "crm.product.read",
    "crm.service.read",
    "crm.delivery.read",
    "crm.event.read",
    # write scopes (require Idempotency-Key)
    "crm.lead.write",
    "crm.activity.write",
    "crm.customer.write",
    "crm.service.write",
    "crm.order.write",
    "crm.contract.write",
    "crm.form.write",
]

_ACTIVITY_BIZ_TYPES = {"customer", "project", "lead"}
_ORDER_STATUSES = {"draft", "confirmed", "producing", "shipped", "completed", "cancelled"}
_CONTRACT_STATUSES = {"draft", "signed", "terminated"}
_CONTRACT_VERSION_STATUSES = {"draft", "submitted", "approved", "rejected", "signed"}


class OpenFlowHistoryStep(BaseModel):
    """简道云「流程动态」单节点，写入 CRM 已结束流程实例供详情页右侧展示。"""
    node_name: str = Field(..., min_length=1, max_length=128)
    handler_name: Optional[str] = Field(None, max_length=100)
    # 简道云 finishAction / 按钮文案；服务端归一为 submit/approve/reject 等。
    action: Optional[str] = Field(None, max_length=64)
    opinion: Optional[str] = Field(None, max_length=2000)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class OpenLeadCreate(BaseModel):
    """External lead-intake payload for POST /openapi/v1/leads."""
    title: str = Field(..., min_length=1, max_length=300)
    company_name: str = Field(..., min_length=1, max_length=300)
    contact_name: Optional[str] = Field(None, max_length=100)
    contact_phone: Optional[str] = Field(None, max_length=30)
    contact_email: Optional[str] = Field(None, max_length=200)
    source: Optional[str] = Field(None, max_length=100)
    # CRM「项目编号」：传简道云项目编号则沿用；不传则 CRM 自增。
    lead_code: Optional[str] = Field(None, max_length=64)
    # 评估区：简道云「客户类型」新/老 → new/old
    customer_newness: Optional[str] = Field(None, max_length=10)
    # 评估区：简道云「回退原因」
    reject_reason: Optional[str] = Field(None, max_length=2000)
    # CRM UI「备注1（线索内容）」← 简道云备注1
    demand_summary: Optional[str] = Field(None, max_length=2000)
    industry: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=200)
    province: Optional[str] = Field(None, max_length=50)
    city: Optional[str] = Field(None, max_length=50)
    district: Optional[str] = Field(None, max_length=50)
    region_code: Optional[str] = Field(None, max_length=12)
    budget_range: Optional[str] = Field(None, max_length=100)
    remark: Optional[str] = Field(None, max_length=2000)
    # 客户类型：字典码或中文标签（简道云申报信息）；服务端归一为 dict_code。
    customer_type: Optional[str] = Field(None, max_length=50)
    # 来源类别：自报/分发 → self_reported/distributed；也可直接传英文码。
    category: Optional[str] = Field(None, max_length=20)
    # 国别：国内/国外 → domestic/overseas。
    country_type: Optional[str] = Field(None, max_length=20)
    country_name: Optional[str] = Field(None, max_length=100)
    # 简道云申报信息对齐
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
    # 部门：可直接传 CRM 部门 UUID，或传名称由服务端按钉钉同步的组织架构反查。
    # department_id 优先；仅有 department_name 时做精确名匹配（trim 后全等）。
    department_id: Optional[str] = Field(None, max_length=36)
    department_name: Optional[str] = Field(None, max_length=200)
    # 负责人（简道云「申报人」）：传 CRM 用户 UUID，或按 real_name/username 精确匹配反查。
    owner_id: Optional[str] = Field(None, max_length=36)
    owner_name: Optional[str] = Field(None, max_length=100)
    # 报备人：通常与简道云「申报人」同源；传 UUID 或按姓名反查。
    reporter_id: Optional[str] = Field(None, max_length=36)
    reporter_name: Optional[str] = Field(None, max_length=100)
    # 报备时间：简道云申报时间 / createTime；ISO 8601。
    reported_at: Optional[datetime] = None
    # 列表「提交时间/更新时间」：有值时覆盖 CRM 系统时间（推送数据优先）。
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # 填表人（CRM created_by_*）：简道云「填表人」；勿落成开放平台伪用户。
    created_by_id: Optional[str] = Field(None, max_length=36)
    created_by_name: Optional[str] = Field(None, max_length=100)
    # 审核态：对接简道云「项目最终状态」。收录→approved（免 CRM 内审）；
    # 袭击→attacked；回退→rejected；待审/空→按草稿处理。也可直接传英文码。
    review_status: Optional[str] = Field(None, max_length=20)
    # 简道云流程动态（递呈信息 / 信息情报部审批 …）；免审导入时落成已结束流程实例。
    flow_history: Optional[List[OpenFlowHistoryStep]] = None


class OpenActivityCreate(BaseModel):
    """External follow-up / activity record for POST /openapi/v1/activities."""
    biz_type: str = Field(..., description="customer / project / lead")
    biz_id: str = Field(..., max_length=36)
    activity_type: str = Field("note", max_length=32)  # call/visit/meeting/email/note
    subject: Optional[str] = Field(None, max_length=300)
    content: Optional[str] = Field(None, max_length=4000)
    next_follow_date: Optional[str] = None

    @field_validator("biz_type")
    @classmethod
    def _check_biz_type(cls, v: str) -> str:
        if v not in _ACTIVITY_BIZ_TYPES:
            raise ValueError(f"biz_type must be one of {sorted(_ACTIVITY_BIZ_TYPES)}")
        return v


class OpenCustomerCreate(BaseModel):
    """External customer-intake payload for POST /openapi/v1/customers.

    对齐简道云「客户信息」主档。
    Upsert：有 ``external_key``（简道云 data_id）时按租户 + external_key；
    否则 ``customer_code`` 非空时按客户编号。无编号也可稳定 1:1。
    布尔/数字可用字符串（中间件 flatten 后常见）。
    """
    name: str = Field(..., min_length=1, max_length=200)
    external_key: Optional[str] = Field(
        None, max_length=128,
        description="外部唯一键（简道云 data_id）；优先于 customer_code 做 upsert",
    )
    customer_code: Optional[str] = Field(None, max_length=100)
    short_name: Optional[str] = Field(None, max_length=100)
    industry: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=200)
    province: Optional[str] = Field(None, max_length=50)
    city: Optional[str] = Field(None, max_length=50)
    district: Optional[str] = Field(None, max_length=50)
    region_code: Optional[str] = Field(None, max_length=12)
    address: Optional[str] = Field(None, max_length=500)
    website: Optional[str] = Field(None, max_length=500)
    source: Optional[str] = Field(None, max_length=100)
    level: Optional[str] = Field(None, max_length=8)
    remark: Optional[str] = Field(None, max_length=2000)
    # 负责人 / 部门（名称反查）
    owner_id: Optional[str] = Field(None, max_length=36)
    owner_name: Optional[str] = Field(None, max_length=100)
    department_id: Optional[str] = Field(None, max_length=36)
    department_name: Optional[str] = Field(None, max_length=200)
    country: Optional[str] = Field(None, max_length=50)
    headcount: Optional[Union[int, str]] = None
    # 简道云对齐
    is_smart_filing: Optional[Union[bool, str]] = None
    is_foreign_trade: Optional[Union[bool, str]] = None
    is_company_customer: Optional[Union[bool, str]] = None
    need_info_distribute: Optional[Union[bool, str]] = None
    registered_capital: Optional[Union[float, int, str]] = None
    paid_in_capital: Optional[Union[float, int, str]] = None
    founded_year: Optional[Union[int, str]] = None
    parent_company_note: Optional[str] = None
    customer_nature: Optional[str] = Field(None, max_length=50)
    customer_relation: Optional[str] = Field(None, max_length=50)
    primary_contact_title: Optional[str] = Field(None, max_length=100)
    wage_insurance_status: Optional[str] = Field(None, max_length=50)
    taxpayer_id: Optional[str] = Field(None, max_length=64)
    invoice_address_phone: Optional[str] = Field(None, max_length=300)
    bank_account: Optional[str] = Field(None, max_length=200)
    foreign_customer_code: Optional[str] = Field(None, max_length=100)
    foreign_customer_type: Optional[str] = Field(None, max_length=50)
    focus_product: Optional[str] = Field(None, max_length=100)
    customer_email: Optional[str] = Field(None, max_length=200)
    main_products_json: Optional[Union[List[Any], str]] = None
    legal_person: Optional[str] = Field(None, max_length=100)
    smart_industry_category: Optional[str] = Field(None, max_length=200)
    annual_run_days: Optional[str] = Field(None, max_length=50)
    floor_area: Optional[str] = Field(None, max_length=100)
    financial_status: Optional[str] = None
    business_status: Optional[str] = None
    annual_power_usage: Optional[str] = Field(None, max_length=100)
    daily_operate_hours: Optional[str] = Field(None, max_length=50)
    # 开放平台写入默认不启 CRM 客户信息审批（简道云侧已审）；可显式传 false。
    as_draft: Optional[Union[bool, str]] = True
    # 有值时覆盖 CRM 系统创建/更新时间（推送数据优先）。
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # 简道云流程动态 → CRM 详情「流程动态」
    flow_history: Optional[List[OpenFlowHistoryStep]] = None

    @field_validator("level")
    @classmethod
    def _check_level(cls, v):
        if v is None or str(v).strip() == "":
            return None
        text = str(v).strip().upper()
        if text in ("A", "B", "C", "D"):
            return text
        if text[:1] in ("A", "B", "C", "D"):
            return text[:1]
        raise ValueError("level 必须为 A/B/C/D")


class OpenServiceTicketCreate(BaseModel):
    """External support-ticket intake for POST /openapi/v1/service-tickets."""
    type: str = Field(..., max_length=32, description="fault/maintenance/training/spare/upgrade")
    customer_id: Optional[str] = Field(None, max_length=36)
    project_id: Optional[str] = Field(None, max_length=36)
    priority: Optional[str] = Field("medium", max_length=16)  # low/medium/high/critical
    description: Optional[str] = Field(None, max_length=4000)


class OpenOrderCreate(BaseModel):
    """External order intake for POST /openapi/v1/orders."""
    customer_id: str = Field(..., min_length=1, max_length=36)
    project_id: Optional[str] = Field(None, max_length=36)
    contract_id: Optional[str] = Field(None, max_length=36)
    title: Optional[str] = Field(None, max_length=300)
    amount: Optional[float] = Field(None, ge=0)
    currency: Optional[str] = Field("CNY", max_length=8)
    status: Optional[str] = Field("draft", max_length=16)
    order_date: Optional[str] = None
    delivery_date: Optional[str] = None
    remark: Optional[str] = Field(None, max_length=2000)

    @field_validator("status")
    @classmethod
    def _check_status(cls, v):
        if v is not None and v not in _ORDER_STATUSES:
            raise ValueError(f"status must be one of {sorted(_ORDER_STATUSES)}")
        return v


class OpenContractCreate(BaseModel):
    """External contract intake for POST /openapi/v1/contracts.

    供中间服务（如 crm-integration）从简道云等源系统拉取后推送。
    ``customer_id`` 与 ``registration_json.customer_name`` 至少其一（简道云合同可不挂客户档案）。
    ``project_id`` is optional.

    Upsert key:
    - 有 ``external_key``（简道云 data_id）时按 tenant + external_key（一条登记单 ↔ 一行）
    - 否则回落 tenant + ``contract_no``（旧行为）
    """
    customer_id: Optional[str] = Field(None, max_length=36)
    project_id: Optional[str] = Field(None, max_length=36)
    external_key: Optional[str] = Field(
        None, max_length=128,
        description="外部幂等键（简道云 data_id）；有则按此 upsert，同合同号可多行",
    )
    contract_no: Optional[str] = Field(None, max_length=64)
    title: Optional[str] = Field(None, max_length=300)
    # Allow negatives: 简道云「变动」合同登记常带负金额冲减。
    amount_total: Optional[float] = None
    status: Optional[str] = Field("draft", max_length=16)
    signed_date: Optional[str] = None
    end_date: Optional[str] = None
    drawing_no: Optional[str] = Field(None, max_length=100)
    peer_contract_no: Optional[str] = Field(None, max_length=100)
    acquire_method: Optional[str] = Field(None, max_length=64)
    delivery_date: Optional[str] = None
    change_type: Optional[str] = Field(None, max_length=16)  # new / change
    order_date: Optional[str] = None
    card_date: Optional[str] = None
    serial_no: Optional[str] = Field(None, max_length=64, description="登记流水号（简道云 sn；未传则自动生成）")
    # 业务员 / 部门：可传 UUID 或名称（名称按钉钉同步组织精确匹配）
    assignee_id: Optional[str] = Field(None, max_length=36)
    assignee_name: Optional[str] = Field(None, max_length=100)
    department_id: Optional[str] = Field(None, max_length=36)
    department_name: Optional[str] = Field(None, max_length=200)
    # 提交人/填表人（CRM created_by_*）：简道云「提交人」；勿落成开放平台伪用户。
    # 未传时回落 registration_json.submitter。
    created_by_id: Optional[str] = Field(None, max_length=36)
    created_by_name: Optional[str] = Field(None, max_length=100)
    payment_terms_json: Optional[dict | list] = None
    delivery_terms_json: Optional[dict | list] = None
    key_clauses_json: Optional[dict | list] = None
    registration_json: Optional[dict] = None
    custom_fields: Optional[dict] = None
    # 当前版本审批态：驱动合同列表「草稿/审批中/待签署/已驳回」展示。
    version_status: Optional[str] = Field(None, max_length=16)
    # 简道云流程动态；导入到 contract_version 流程实例（详情「流程动态」）。
    flow_history: Optional[List[OpenFlowHistoryStep]] = None
    # 简道云流程是否已结束；False=进行中（实例 status=running）。缺省按步骤推断为已结束。
    flow_finished: Optional[bool] = None
    # 合同附件槽位：biz_type → 文件名列表或 [{name, ossKey?}]；CRM 转为 jdy-meta/jdy-oss 引用存 registration_json._attachments
    attachments_json: Optional[dict[str, Any]] = None

    @field_validator("status")
    @classmethod
    def _check_status(cls, v):
        if v is not None and v not in _CONTRACT_STATUSES:
            raise ValueError(f"status must be one of {sorted(_CONTRACT_STATUSES)}")
        return v

    @field_validator("version_status")
    @classmethod
    def _check_version_status(cls, v):
        if v is not None and v not in _CONTRACT_VERSION_STATUSES:
            raise ValueError(f"version_status must be one of {sorted(_CONTRACT_VERSION_STATUSES)}")
        return v

    @model_validator(mode="after")
    def _check_customer_ref(self):
        cid = (self.customer_id or "").strip()
        reg = self.registration_json if isinstance(self.registration_json, dict) else {}
        cname = (reg.get("customer_name") or "").strip() if reg else ""
        if not cid and not cname:
            raise ValueError("customer_id or registration_json.customer_name is required")
        return self


class OpenFormInstanceUpsert(BaseModel):
    """Upsert a low-code form instance (e.g. 合同图纸领用 / 安装图设计通知).

    Intended for middleware push from 简道云. Upsert key: tenant + template_code +
    ``external_key`` (stored in form_data._external_key). Default ``as_draft=true``
    so historical sync does not re-trigger CRM approval.
    """
    template_code: str = Field(..., min_length=1, max_length=64)
    external_key: str = Field(..., min_length=1, max_length=128)
    title: Optional[str] = Field(None, max_length=255)
    remark: Optional[str] = Field(None, max_length=2000)
    as_draft: bool = True
    form_data: dict[str, Any] = Field(default_factory=dict)


class OpenOrderStatusUpdate(BaseModel):
    """Status write-back (ERP → CRM) for POST /openapi/v1/orders/{id}/status."""
    status: str = Field(..., max_length=16)

    @field_validator("status")
    @classmethod
    def _check_status(cls, v):
        if v not in _ORDER_STATUSES:
            raise ValueError(f"status must be one of {sorted(_ORDER_STATUSES)}")
        return v

_AUTH_MODES = {"apikey", "hmac"}
_STATUSES = {"enabled", "disabled"}


class OpenApiAppCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    app_type: str = Field("external_system", max_length=64)
    auth_mode: str = "apikey"
    scopes: List[str] = Field(default_factory=list)
    rate_limit_per_minute: int = Field(600, ge=1, le=100000)
    ip_whitelist: Optional[List[str]] = None
    remark: Optional[str] = Field(None, max_length=500)

    @field_validator("auth_mode")
    @classmethod
    def _check_auth_mode(cls, v: str) -> str:
        if v not in _AUTH_MODES:
            raise ValueError(f"auth_mode must be one of {sorted(_AUTH_MODES)}")
        return v

    @field_validator("scopes")
    @classmethod
    def _check_scopes(cls, v: List[str]) -> List[str]:
        bad = [s for s in v if s not in ALL_SCOPES]
        if bad:
            raise ValueError(f"unknown scopes: {bad}")
        return v


class OpenApiAppUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    status: Optional[str] = None
    auth_mode: Optional[str] = None
    scopes: Optional[List[str]] = None
    rate_limit_per_minute: Optional[int] = Field(None, ge=1, le=100000)
    ip_whitelist: Optional[List[str]] = None
    remark: Optional[str] = Field(None, max_length=500)

    @field_validator("status")
    @classmethod
    def _check_status(cls, v):
        if v is not None and v not in _STATUSES:
            raise ValueError(f"status must be one of {sorted(_STATUSES)}")
        return v

    @field_validator("auth_mode")
    @classmethod
    def _check_auth_mode(cls, v):
        if v is not None and v not in _AUTH_MODES:
            raise ValueError(f"auth_mode must be one of {sorted(_AUTH_MODES)}")
        return v

    @field_validator("scopes")
    @classmethod
    def _check_scopes(cls, v):
        if v is not None:
            bad = [s for s in v if s not in ALL_SCOPES]
            if bad:
                raise ValueError(f"unknown scopes: {bad}")
        return v

