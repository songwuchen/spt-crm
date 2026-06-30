"""资源字段注册表 —— 高级搜索的单一数据源（前端 schema + 后端编译共用）。

延迟构建（首次使用时导入各 domain 模型），避免与 service 层产生导入环。
"""
from sqlalchemy import asc, desc

from .fields import (
    TextField, NumberField, DateField, EnumField, BooleanField,
    RelationField, PeopleField,
)


class ResourceSchema:
    def __init__(self, resource, label, fields):
        self.resource = resource
        self.label = label
        self.fields = fields
        self._map = {f.key: f for f in fields}

    def field(self, key):
        return self._map.get(key)

    def schema_dict(self) -> dict:
        return {
            "resource": self.resource,
            "label": self.label,
            "fields": [f.schema() for f in self.fields],
        }

    def sort_clause(self, sort_by, sort_order):
        if not sort_by:
            return None
        f = self._map.get(sort_by)
        if f is None or not f.sortable:
            return None
        return desc(f.column) if (sort_order or "desc").lower() == "desc" else asc(f.column)


_STAGE_OPTS = [("S1", "S1"), ("S2", "S2"), ("S3", "S3"), ("S4", "S4"), ("S5", "S5"), ("S6", "S6")]
_RISK_OPTS = [("L", "低"), ("M", "中"), ("H", "高")]


def _build_registry() -> dict:
    from app.domains.customer.models import Customer, Contact
    from app.domains.lead.models import Lead
    from app.domains.project.models import OpportunityProject as Project
    from app.domains.quote.models import Quote
    from app.domains.contract.models import Contract
    from app.domains.order.models import Order
    from app.domains.product.models import Product
    from app.domains.service_ticket.models import ServiceTicket
    from app.domains.commission.models import CommissionRecord
    from app.domains.tender.models import Tender
    from app.domains.guarantee.models import Guarantee
    from app.domains.solution.models import Solution
    from app.domains.change.models import ChangeRequest
    from app.domains.delivery.models import DeliveryMilestone
    from app.domains.payment.models import PaymentRecord
    from app.domains.collection.models import DebtTransfer

    reg: dict[str, ResourceSchema] = {}

    reg["customer"] = ResourceSchema("customer", "客户", [
        TextField("name", "客户名称", Customer.name),
        TextField("customer_code", "客户编码", Customer.customer_code),
        TextField("short_name", "简称", Customer.short_name),
        TextField("industry", "行业", Customer.industry),
        TextField("region", "区域", Customer.region),
        EnumField("level", "客户等级", Customer.level,
                  options=[("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")]),
        TextField("scale_level", "规模等级", Customer.scale_level),
        TextField("source", "来源", Customer.source),
        EnumField("status", "状态", Customer.status,
                  options=[("active", "启用"), ("inactive", "停用")]),
        PeopleField("owner_id", "负责人", Customer.owner_id, option_source="users"),
        TextField("owner_name", "负责人姓名", Customer.owner_name),
        DateField("created_at", "创建时间", Customer.created_at, is_datetime=True),
    ])

    reg["lead"] = ResourceSchema("lead", "线索", [
        TextField("lead_code", "线索编号", Lead.lead_code),
        TextField("title", "线索标题", Lead.title),
        TextField("company_name", "公司名称", Lead.company_name),
        TextField("contact_name", "联系人", Lead.contact_name),
        TextField("contact_phone", "联系电话", Lead.contact_phone),
        TextField("source", "来源", Lead.source),
        TextField("industry", "行业", Lead.industry),
        EnumField("status", "状态", Lead.status,
                  options=[("new", "新建"), ("following", "跟进中"),
                           ("qualified", "已确认"), ("discarded", "已废弃")]),
        TextField("customer_type", "客户类型", Lead.customer_type),
        EnumField("category", "分类", Lead.category,
                  options=[("self_reported", "自报"), ("distributed", "分配")]),
        EnumField("country_type", "国别", Lead.country_type,
                  options=[("domestic", "国内"), ("overseas", "海外")]),
        TextField("province", "省份", Lead.province),
        TextField("city", "城市", Lead.city),
        NumberField("score", "评分", Lead.score),
        PeopleField("owner_id", "负责人", Lead.owner_id, option_source="users"),
        TextField("owner_name", "负责人姓名", Lead.owner_name),
        DateField("created_at", "创建时间", Lead.created_at, is_datetime=True),
    ])

    reg["project"] = ResourceSchema("project", "商机", [
        TextField("project_code", "商机编号", Project.project_code),
        TextField("name", "商机名称", Project.name),
        RelationField("customer_id", "客户", Project.customer_id, option_source="customers"),
        EnumField("stage_code", "阶段", Project.stage_code, options=_STAGE_OPTS),
        EnumField("status", "状态", Project.status,
                  options=[("active", "进行中"), ("won", "赢单"),
                           ("lost", "输单"), ("suspended", "暂停")]),
        NumberField("amount_expect", "预计金额", Project.amount_expect),
        NumberField("probability", "赢单率", Project.probability),
        EnumField("risk_level", "风险等级", Project.risk_level, options=_RISK_OPTS),
        DateField("close_date_expect", "预计成交日期", Project.close_date_expect),
        PeopleField("owner_id", "负责人", Project.owner_id, option_source="users"),
        TextField("owner_name", "负责人姓名", Project.owner_name),
        DateField("created_at", "创建时间", Project.created_at, is_datetime=True),
    ])

    reg["quote"] = ResourceSchema("quote", "报价", [
        TextField("quote_no", "报价单号", Quote.quote_no),
        EnumField("status", "状态", Quote.status,
                  options=[("draft", "草稿"), ("sent", "已发送"),
                           ("won", "赢单"), ("lost", "输单")]),
        PeopleField("assignee_id", "负责人", Quote.assignee_id, option_source="users"),
        TextField("assignee_name", "负责人姓名", Quote.assignee_name),
        TextField("department_name", "负责部门", Quote.department_name),
        DateField("created_at", "创建时间", Quote.created_at, is_datetime=True),
    ])

    reg["contract"] = ResourceSchema("contract", "合同", [
        TextField("contract_no", "合同编号", Contract.contract_no),
        EnumField("status", "状态", Contract.status,
                  options=[("draft", "草稿"), ("signed", "已签署"), ("terminated", "已终止")]),
        NumberField("amount_total", "合同金额", Contract.amount_total),
        DateField("signed_date", "签署日期", Contract.signed_date),
        DateField("end_date", "到期日期", Contract.end_date),
        PeopleField("assignee_id", "负责人", Contract.assignee_id, option_source="users"),
        TextField("assignee_name", "负责人姓名", Contract.assignee_name),
        TextField("department_name", "负责部门", Contract.department_name),
        DateField("created_at", "创建时间", Contract.created_at, is_datetime=True),
    ])

    reg["order"] = ResourceSchema("order", "订单", [
        TextField("order_no", "订单编号", Order.order_no),
        TextField("title", "订单标题", Order.title),
        RelationField("customer_id", "客户", Order.customer_id, option_source="customers"),
        EnumField("status", "状态", Order.status,
                  options=[("draft", "草稿"), ("confirmed", "已确认"), ("producing", "生产中"),
                           ("shipped", "已发货"), ("completed", "已完成"), ("cancelled", "已取消")]),
        NumberField("amount", "订单金额", Order.amount),
        TextField("currency", "币种", Order.currency),
        DateField("order_date", "下单日期", Order.order_date),
        DateField("delivery_date", "交期", Order.delivery_date),
        PeopleField("owner_id", "负责人", Order.owner_id, option_source="users"),
        TextField("owner_name", "负责人姓名", Order.owner_name),
        DateField("created_at", "创建时间", Order.created_at, is_datetime=True),
    ])

    reg["contact"] = ResourceSchema("contact", "联系人", [
        TextField("name", "姓名", Contact.name),
        TextField("title", "职位", Contact.title),
        EnumField("role_type", "角色", Contact.role_type, options=[
            ("decision_maker", "决策者"), ("influencer", "影响者"), ("user", "使用者"),
            ("finance", "财务"), ("procurement", "采购")]),
        TextField("phone", "电话", Contact.phone),
        TextField("mobile", "手机", Contact.mobile),
        TextField("email", "邮箱", Contact.email),
        BooleanField("is_primary", "主联系人", Contact.is_primary),
        RelationField("customer_id", "所属客户", Contact.customer_id, option_source="customers"),
        DateField("created_at", "创建时间", Contact.created_at, is_datetime=True),
    ])

    reg["product"] = ResourceSchema("product", "产品", [
        TextField("product_code", "产品编码", Product.product_code),
        TextField("name", "产品名称", Product.name),
        EnumField("item_type", "类型", Product.item_type, options=[
            ("standard", "标准件"), ("nonstandard", "非标"), ("service", "服务"), ("spare", "备件")]),
        TextField("spec", "规格", Product.spec),
        TextField("unit", "单位", Product.unit),
        NumberField("unit_price", "单价", Product.unit_price),
        NumberField("cost_price", "成本价", Product.cost_price),
        NumberField("leadtime_days", "交期(天)", Product.leadtime_days),
        BooleanField("is_active", "启用", Product.is_active),
        DateField("created_at", "创建时间", Product.created_at, is_datetime=True),
    ])

    reg["service_ticket"] = ResourceSchema("service_ticket", "售后工单", [
        TextField("ticket_no", "工单号", ServiceTicket.ticket_no),
        TextField("type", "类型", ServiceTicket.type),
        EnumField("priority", "优先级", ServiceTicket.priority, options=[
            ("low", "低"), ("medium", "中"), ("high", "高"), ("urgent", "紧急")]),
        TextField("status", "状态", ServiceTicket.status),
        PeopleField("assigned_to_id", "处理人", ServiceTicket.assigned_to_id, option_source="users"),
        TextField("assigned_to_name", "处理人姓名", ServiceTicket.assigned_to_name),
        RelationField("customer_id", "客户", ServiceTicket.customer_id, option_source="customers"),
        DateField("created_at", "创建时间", ServiceTicket.created_at, is_datetime=True),
    ])

    reg["commission"] = ResourceSchema("commission", "提成", [
        TextField("record_no", "提成单号", CommissionRecord.record_no),
        TextField("customer_name", "客户", CommissionRecord.customer_name),
        PeopleField("owner_id", "归属人", CommissionRecord.owner_id, option_source="users"),
        TextField("owner_name", "归属人姓名", CommissionRecord.owner_name),
        TextField("department_name", "部门", CommissionRecord.department_name),
        EnumField("status", "状态", CommissionRecord.status, options=[
            ("draft", "草稿"), ("submitted", "已提交"), ("approved", "已审批"), ("paid", "已发放")]),
        NumberField("contract_amount", "合同金额", CommissionRecord.contract_amount),
        NumberField("commission_amount", "提成金额", CommissionRecord.commission_amount),
        DateField("signed_date", "签约日期", CommissionRecord.signed_date),
        DateField("created_at", "创建时间", CommissionRecord.created_at, is_datetime=True),
    ])

    reg["tender"] = ResourceSchema("tender", "标书", [
        TextField("tender_no", "标书编号", Tender.tender_no),
        TextField("title", "标题", Tender.title),
        RelationField("customer_id", "客户", Tender.customer_id, option_source="customers"),
        TextField("status", "状态", Tender.status),
        NumberField("bid_amount", "投标金额", Tender.bid_amount),
        NumberField("budget_amount", "预算金额", Tender.budget_amount),
        DateField("submit_date", "投标日期", Tender.submit_date),
        DateField("open_date", "开标日期", Tender.open_date),
        PeopleField("owner_id", "负责人", Tender.owner_id, option_source="users"),
        TextField("owner_name", "负责人姓名", Tender.owner_name),
        DateField("created_at", "创建时间", Tender.created_at, is_datetime=True),
    ])

    reg["guarantee"] = ResourceSchema("guarantee", "保函", [
        TextField("guarantee_no", "保函编号", Guarantee.guarantee_no),
        TextField("type", "类型", Guarantee.type),
        EnumField("direction", "方向", Guarantee.direction, options=[("outgoing", "对外"), ("incoming", "对内")]),
        TextField("customer_name", "客户", Guarantee.customer_name),
        NumberField("amount", "金额", Guarantee.amount),
        TextField("issuer", "出具机构", Guarantee.issuer),
        TextField("status", "状态", Guarantee.status),
        DateField("effective_date", "生效日期", Guarantee.effective_date),
        DateField("expiry_date", "到期日期", Guarantee.expiry_date),
        PeopleField("owner_id", "负责人", Guarantee.owner_id, option_source="users"),
        TextField("owner_name", "负责人姓名", Guarantee.owner_name),
        DateField("created_at", "创建时间", Guarantee.created_at, is_datetime=True),
    ])

    reg["solution"] = ResourceSchema("solution", "方案", [
        TextField("solution_no", "方案编号", Solution.solution_no),
        EnumField("status", "状态", Solution.status, options=[
            ("draft", "草稿"), ("reviewing", "审核中"), ("approved", "已批准"), ("obsolete", "已作废")]),
        PeopleField("assignee_id", "负责人", Solution.assignee_id, option_source="users"),
        TextField("assignee_name", "负责人姓名", Solution.assignee_name),
        TextField("department_name", "负责部门", Solution.department_name),
        DateField("created_at", "创建时间", Solution.created_at, is_datetime=True),
    ])

    reg["change"] = ResourceSchema("change", "变更", [
        TextField("change_no", "变更编号", ChangeRequest.change_no),
        TextField("change_type", "变更类型", ChangeRequest.change_type),
        TextField("status", "状态", ChangeRequest.status),
        PeopleField("assignee_id", "负责人", ChangeRequest.assignee_id, option_source="users"),
        TextField("assignee_name", "负责人姓名", ChangeRequest.assignee_name),
        TextField("department_name", "负责部门", ChangeRequest.department_name),
        DateField("created_at", "创建时间", ChangeRequest.created_at, is_datetime=True),
    ])

    reg["milestone"] = ResourceSchema("milestone", "交付里程碑", [
        TextField("milestone_code", "里程碑编码", DeliveryMilestone.milestone_code),
        TextField("name", "名称", DeliveryMilestone.name),
        TextField("status", "状态", DeliveryMilestone.status),
        DateField("plan_date", "计划日期", DeliveryMilestone.plan_date),
        DateField("actual_date", "实际日期", DeliveryMilestone.actual_date),
        PeopleField("assignee_id", "负责人", DeliveryMilestone.assignee_id, option_source="users"),
        TextField("assignee_name", "负责人姓名", DeliveryMilestone.assignee_name),
        DateField("created_at", "创建时间", DeliveryMilestone.created_at, is_datetime=True),
    ])

    reg["payment"] = ResourceSchema("payment", "回款", [
        TextField("reference_no", "凭证号", PaymentRecord.reference_no),
        TextField("channel", "回款渠道", PaymentRecord.channel),
        NumberField("amount", "回款金额", PaymentRecord.amount),
        DateField("received_date", "到账日期", PaymentRecord.received_date),
        DateField("created_at", "创建时间", PaymentRecord.created_at, is_datetime=True),
    ])

    reg["collection"] = ResourceSchema("collection", "应收清欠", [
        TextField("transfer_no", "移交单号", DebtTransfer.transfer_no),
        TextField("customer_name", "客户", DebtTransfer.customer_name),
        TextField("transfer_type", "移交类型", DebtTransfer.transfer_type),
        TextField("status", "状态", DebtTransfer.status),
        NumberField("debt_amount", "欠款金额", DebtTransfer.debt_amount),
        TextField("to_department_name", "接收部门", DebtTransfer.to_department_name),
        DateField("deadline", "清欠期限", DebtTransfer.deadline),
        DateField("created_at", "创建时间", DebtTransfer.created_at, is_datetime=True),
    ])

    return reg


_REGISTRY: dict | None = None


def get_registry() -> dict:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _build_registry()
    return _REGISTRY


def get_schema(resource: str):
    return get_registry().get(resource)
