"""Single source of truth for the standard RBAC catalog.

- ``PERMISSIONS``    — every permission code the app's ``require_permissions()``
                       guards reference (global, tenant-agnostic rows).
- ``STANDARD_ROLES`` — the built-in FUNCTION roles (销售/财务/生产/售后/…) plus a
                       baseline ``employee`` role, each with its permission set +
                       ``data_scope``.
- ``CORE``           — permissions EVERY standard role gets (incl. the low-code
                       "use" tier: view/fill forms, view flows & dashboards).
- ``LOWCODE_DESIGN`` — low-code "design/manage" perms, only for roles flagged
                       ``lowcode_admin`` (主管/总监/总工).

Both the seed scripts (``scripts/seed.py``, ``scripts/seed_function_roles.py``)
and the admin "同步标准角色与权限" API import from here, so the catalog can never
diverge again. (The 扩展平台-only-shows-审批中心 bug was caused by two
hand-maintained copies of these lists drifting apart.)

Role-def ``perms`` lists hold ONLY the role-specific permissions; call
``role_perm_codes(rd)`` to get the full, de-duplicated list (CORE + role perms
+ LOWCODE_DESIGN when applicable).
"""

# (code, display name, group) — the global permission catalog.
PERMISSIONS = [
    ("customer:view", "查看客户", "客户"),
    ("customer:create", "创建客户", "客户"),
    ("customer:edit", "编辑客户", "客户"),
    ("customer:delete", "删除客户", "客户"),
    ("contact:view", "查看联系人", "联系人"),
    ("contact:create", "创建联系人", "联系人"),
    ("contact:edit", "编辑联系人", "联系人"),
    ("contact:delete", "删除联系人", "联系人"),
    ("lead:view", "查看线索", "线索"),
    ("lead:create", "创建线索", "线索"),
    ("lead:edit", "编辑线索", "线索"),
    ("lead:delete", "删除线索", "线索"),
    ("lead:qualify", "转化线索", "线索"),
    ("lead:discard", "废弃线索", "线索"),
    ("lead:review", "审核线索", "线索"),
    ("project:view", "查看商机", "商机"),
    ("project:create", "创建商机", "商机"),
    ("project:edit", "编辑商机", "商机"),
    ("project:delete", "删除商机", "商机"),
    ("project:advance", "推进商机阶段", "商机"),
    ("project:transfer", "转移商机负责人", "商机"),
    ("quote:view", "查看报价", "报价"),
    ("quote:create", "创建报价", "报价"),
    ("quote:edit", "编辑报价", "报价"),
    ("quote:delete", "删除报价", "报价"),
    ("quote:view_cost", "查看报价成本/毛利", "报价"),
    ("quote:view_discount", "查看报价折扣", "报价"),
    ("contract:view", "查看合同", "合同"),
    ("contract:create", "创建合同", "合同"),
    ("contract:edit", "编辑合同", "合同"),
    ("contract:delete", "删除合同", "合同"),
    ("contract:sign", "签署合同", "合同"),
    ("contract_review:view", "查看合同评审", "合同评审"),
    ("contract_review:create", "创建合同评审", "合同评审"),
    ("contract_review:edit", "编辑合同评审", "合同评审"),
    ("contract_review:delete", "删除合同评审", "合同评审"),
    ("tech_agreement_review:view", "查看技术协议评审", "技术协议评审"),
    ("tech_agreement_review:create", "创建技术协议评审", "技术协议评审"),
    ("tech_agreement_review:edit", "编辑技术协议评审", "技术协议评审"),
    ("tech_agreement_review:delete", "删除技术协议评审", "技术协议评审"),
    ("solution:view", "查看方案", "方案"),
    ("solution:create", "创建方案", "方案"),
    ("solution:edit", "编辑方案", "方案"),
    ("solution:delete", "删除方案", "方案"),
    ("delivery:view", "查看交付", "交付"),
    ("delivery:edit", "编辑交付", "交付"),
    ("delivery:delete", "删除交付", "交付"),
    ("payment:view", "查看回款", "回款"),
    ("payment:edit", "编辑回款", "回款"),
    ("change:view", "查看变更", "变更"),
    ("change:create", "创建变更", "变更"),
    ("change:edit", "编辑变更", "变更"),
    ("change:delete", "删除变更", "变更"),
    ("service:view", "查看工单", "工单"),
    ("service:create", "创建工单", "工单"),
    ("service:edit", "编辑工单", "工单"),
    ("service:delete", "删除工单", "工单"),
    ("approval:view", "查看审批", "审批"),
    ("approval:approve", "审批操作", "审批"),
    ("approval:decide", "审批决定", "审批"),
    ("approval:delegate", "委托审批", "审批"),
    ("approval:withdraw", "撤回审批", "审批"),
    ("approval:resubmit", "重新提交审批", "审批"),
    ("approval:manage", "管理审批", "审批"),
    ("attachment:upload", "上传附件", "附件"),
    ("attachment:download", "下载附件", "附件"),
    ("task:view", "查看任务", "任务"),
    ("task:create", "创建任务", "任务"),
    ("task:edit", "编辑任务", "任务"),
    ("task:delete", "删除任务", "任务"),
    ("notification:view", "查看通知", "通知"),
    ("notification:manage", "管理通知", "通知"),
    ("product:view", "查看产品", "产品"),
    ("product:create", "创建产品", "产品"),
    ("product:edit", "编辑产品", "产品"),
    ("product:delete", "删除产品", "产品"),
    ("order:view", "查看订单", "订单"),
    ("order:create", "创建订单", "订单"),
    ("order:edit", "编辑订单", "订单"),
    ("order:delete", "删除订单", "订单"),
    ("tender:view", "查看标书", "标书"),
    ("tender:create", "创建标书", "标书"),
    ("tender:edit", "编辑标书", "标书"),
    ("tender:delete", "删除标书", "标书"),
    ("commission:view", "查看提成", "提成"),
    ("commission:edit", "编辑提成", "提成"),
    ("commission:manage", "管理提成政策", "提成"),
    ("collection:view", "查看应收清欠", "应收清欠"),
    ("collection:edit", "编辑应收清欠", "应收清欠"),
    ("collection:manage", "管理应收清欠", "应收清欠"),
    ("guarantee:view", "查看保函", "保函"),
    ("guarantee:edit", "编辑保函", "保函"),
    ("audit:view", "查看审计", "审计"),
    ("dashboard:view", "查看销售目标/仪表盘", "报表"),
    ("data:view_all", "查看全部数据", "数据权限"),
    ("role:view", "查看角色", "系统"),
    ("role:edit", "编辑角色", "系统"),
    ("role:manage", "管理角色", "系统"),
    ("user:view", "查看用户", "系统"),
    ("user:manage", "管理用户", "系统"),
    ("dept:view", "查看部门", "组织"),
    ("dept:manage", "管理部门", "组织"),
    ("tenant:view", "查看租户", "平台"),
    ("tenant:manage", "管理租户", "平台"),
    # ---- 扩展平台(低代码): 表单引擎 / 流程引擎 / 仪表盘 ----
    ("form:view", "查看表单模板", "扩展平台"),
    ("form:manage", "设计/管理表单模板", "扩展平台"),
    ("form_data:view", "查看表单数据", "扩展平台"),
    ("form_data:create", "填报表单数据", "扩展平台"),
    ("form_data:edit", "编辑表单数据", "扩展平台"),
    ("form_data:delete", "删除表单数据", "扩展平台"),
    ("workflow:view", "查看流程定义", "扩展平台"),
    ("workflow:manage", "设计/管理流程定义", "扩展平台"),
    ("workflow:activate", "激活已结束流程", "扩展平台"),
    ("dashboard:manage", "设计/管理仪表盘", "扩展平台"),
]

# Permissions EVERY standard role gets. Includes the 扩展平台「使用」层 so all
# staff can fill forms / view flows via 业务模块与审批中心.
# 侧栏「扩展平台」设计入口不看这些权限，只对系统管理员（role:manage）开放。
CORE = [
    "notification:view",
    "attachment:download", "attachment:upload",
    "task:view", "task:create", "task:edit",
    "approval:view", "approval:resubmit", "approval:withdraw",
    "form:view", "form_data:view", "form_data:create", "form_data:edit",
    "workflow:view", "dashboard:view",
]

# 扩展平台「设计/管理」层 — only roles flagged lowcode_admin (主管/总监/总工).
# form_data:delete lives here (deleting form data is more sensitive than filling).
# workflow:activate 是运行时操作（重开已结束流程），不是设计权；内勤等角色可单独授予，
# 主管已有 workflow:manage，接口按二者任一放行。
LOWCODE_DESIGN = [
    "form:manage", "workflow:manage",
    "dashboard:manage", "form_data:delete",
]

# 客服相关：默认仍 dept/self；客户/选合同/客服类表单列表需看全部
_CS_MODULE_SCOPE_ALL = {"customer": "all", "contract": "all", "form_data": "all"}

CS_CUSTOMER_ALL_ROLE_CODES = frozenset({
    "service_engineer",
    "service_manager",
    "cs_office",
    "cs_arrange",
    "cs_delay_approve",
    "cs_named_fjj_zdd_jw",
    "cs_service_cc",
    "cs_replace_trace",
    "cs_special_release",
    "cs_service_record",
})

# The standard roles. ``perms`` = role-specific perms only (CORE is added by
# role_perm_codes). ``scope`` -> data_scope: self / dept / all.
STANDARD_ROLES = [
    {
        "code": "employee", "name": "基础员工", "scope": "self",
        "desc": "全员基础角色:扩展平台使用(填表单/看流程/看仪表盘)+ 客户/商机只读 + 任务/审批参与",
        "perms": ["customer:view", "project:view"],
    },
    {
        "code": "sales_rep", "name": "销售专员", "scope": "self",
        "desc": "商机 owner:客户/线索/商机/报价;上下游只读",
        "perms": [
            "customer:view", "customer:create", "customer:edit",
            "contact:view", "contact:create", "contact:edit",
            "lead:view", "lead:create", "lead:edit", "lead:qualify", "lead:discard",
            "project:view", "project:create", "project:edit", "project:advance",
            "quote:view", "quote:create", "quote:edit",
            "solution:view", "contract:view",
            "contract_review:view", "contract_review:create", "contract_review:edit",
            "tech_agreement_review:view", "tech_agreement_review:create", "tech_agreement_review:edit",
            "delivery:view", "payment:view",
            "order:view", "product:view", "tender:view",
        ],
    },
    {
        # 一线业务员：只看本人线索/客户/商机；方案三表（图纸领用/安装图/售前）仅本人单据
        "code": "salesperson", "name": "业务员", "scope": "self",
        "scope_by_resource": {
            "drawing_requisition": "self",
            "install_drawing_notice": "self",
            "presale_service_notice": "self",
        },
        "desc": "业务员:仅看本人线索/客户/商机及本人方案三表单据;收录后确认是否转化为客户与商机",
        "perms": [
            "customer:view", "customer:create",
            "contact:view", "contact:create",
            "lead:view", "lead:qualify",
            "project:view", "project:create",
            # CORE 已含 form_data:view/create；显式写出便于对照方案三表菜单
            "form_data:view", "form_data:create",
        ],
    },
    {
        "code": "sales_manager", "name": "销售主管", "scope": "dept", "lowcode_admin": True,
        "desc": "本部门子树销售数据 + 审批 + 提成查看",
        "perms": [
            "customer:view", "customer:create", "customer:edit",
            "contact:view", "contact:create", "contact:edit",
            "lead:view", "lead:create", "lead:edit", "lead:qualify", "lead:discard",
            "project:view", "project:create", "project:edit", "project:advance",
            "quote:view", "quote:create", "quote:edit",
            "solution:view", "contract:view",
            "contract_review:view", "contract_review:create", "contract_review:edit", "contract_review:delete",
            "tech_agreement_review:view", "tech_agreement_review:create", "tech_agreement_review:edit", "tech_agreement_review:delete",
            "delivery:view", "payment:view",
            "order:view", "product:view", "tender:view", "commission:view",
            "approval:approve", "approval:decide", "approval:delegate",
        ],
    },
    {
        "code": "sales_director", "name": "销售总监", "scope": "all", "lowcode_admin": True,
        "desc": "全租户销售数据 + 审批",
        "perms": [
            "customer:view", "customer:create", "customer:edit",
            "contact:view", "contact:create", "contact:edit",
            "lead:view", "lead:create", "lead:edit", "lead:qualify", "lead:discard",
            "project:view", "project:create", "project:edit", "project:advance",
            "quote:view", "quote:create", "quote:edit",
            "solution:view", "contract:view",
            "contract_review:view", "contract_review:create", "contract_review:edit", "contract_review:delete",
            "tech_agreement_review:view", "tech_agreement_review:create", "tech_agreement_review:edit", "tech_agreement_review:delete",
            "delivery:view", "payment:view",
            "order:view", "product:view", "tender:view", "commission:view",
            "approval:approve", "approval:decide", "approval:delegate",
        ],
    },
    {
        "code": "lead_intel", "name": "信息情报部内勤", "scope": "self",
        "desc": "线索审核/分发:仅看本人负责业务部门的线索;自身录入或导入可走审核流",
        "perms": [
            "customer:view",
            "lead:view", "lead:create", "lead:edit", "lead:review",
            "lead:qualify", "lead:discard",
            "approval:approve", "approval:decide", "approval:delegate",
            "workflow:activate",
        ],
    },
    {
        "code": "biz_support", "name": "商务/标书专员", "scope": "dept",
        "desc": "市场支持/国际业务支持:标书 + 协助报价",
        "perms": [
            "customer:view", "project:view", "quote:view", "quote:edit",
            "contract:view", "contract_review:view", "product:view",
            "tech_agreement_review:view",
            "tender:view", "tender:create", "tender:edit", "tender:delete",
        ],
    },
    {
        # 市场技术支持中心：默认本部门；客户主数据需看全部（scope_by_resource）
        # 核价清单传递：列表按单据业务部门/申请人匹配；需在用户上配置「负责业务部门」
        "code": "mkt_support", "name": "市场技术支持中心", "scope": "dept",
        "scope_by_resource": {"customer": "all"},
        "desc": "市场技术支持:本部门业务数据;客户可看全部;核价清单/收款登记按单据部门可见",
        "perms": [
            "customer:view", "customer:create", "customer:edit",
            "contact:view", "contact:create", "contact:edit",
            "lead:view", "lead:create", "lead:edit",
            "project:view", "project:create", "project:edit",
            "quote:view", "quote:edit",
            "contract:view", "contract_review:view",
            "tech_agreement_review:view",
            "product:view", "tender:view",
            "form_data:view",
        ],
    },
    {
        "code": "design_engineer", "name": "方案设计工程师", "scope": "self",
        "desc": "研究院/技术/工艺:方案 + 技术变更;靠 assignee 看到被指派的商机",
        "perms": [
            "customer:view", "project:view", "quote:view", "contract:view", "product:view",
            "solution:view", "solution:create", "solution:edit",
            "change:view", "change:create", "change:edit",
        ],
    },
    {
        "code": "room_leader", "name": "设计指派27.3~4/1.2.8/6.8/27.16/19.3", "scope": "dept",
        "scope_by_resource": {
            "prod_card_supplement": "all",
            "scheme_management": "all",
            "drawing_requisition": "all",
            "install_drawing_notice": "all",
        },
        "desc": "对齐简道云设计指派人选（JDY role 63815e3a7fb607000acc9195）；方案/图纸/生产卡等「设计指派」字段",
        "perms": [
            "customer:view", "project:view", "quote:view", "contract:view", "product:view",
            "solution:view",
            "approval:approve", "approval:decide",
        ],
    },
    {
        "code": "transfer_packaging", "name": "转新乡、工艺包装", "scope": "dept",
        "scope_by_resource": {
            "prod_card_supplement": "all",
            "scheme_management": "all",
        },
        "desc": "对齐简道云角色 6942502ab4606b6b5375dc4f：方案/图纸/生产卡「转新乡、工艺包装」人选",
        "perms": [
            "customer:view", "project:view", "quote:view", "contract:view", "product:view",
            "solution:view",
            "approval:approve", "approval:decide",
        ],
    },
    {
        "code": "tech_chief", "name": "技术总工/评审", "scope": "all", "lowcode_admin": True,
        "desc": "全局技术只读 + 方案/变更评审与审批",
        "perms": [
            "customer:view", "project:view", "quote:view", "contract:view", "product:view",
            "contract_review:view", "contract_review:edit",
            "tech_agreement_review:view", "tech_agreement_review:edit",
            "solution:view", "solution:create", "solution:edit",
            "change:view", "change:create", "change:edit",
            "approval:approve", "approval:decide", "approval:delegate",
        ],
    },
    {
        "code": "production", "name": "生产/交付专员", "scope": "dept",
        "desc": "生产管理部及车间:交付里程碑 + 订单；可参与合同登记审批",
        "perms": [
            "customer:view", "project:view", "contract:view", "product:view",
            "delivery:view", "delivery:edit",
            "order:view", "order:create", "order:edit",
            "approval:approve", "approval:decide",
        ],
    },    {
        "code": "production_manager", "name": "生产主管", "scope": "dept", "lowcode_admin": True,
        "desc": "生产负责人:交付/订单全权 + 交付审批",
        "perms": [
            "customer:view", "project:view", "contract:view", "product:view", "quote:view",
            "delivery:view", "delivery:edit", "delivery:delete",
            "order:view", "order:create", "order:edit", "order:delete",
            "approval:approve", "approval:decide",
        ],
    },
    {
        "code": "finance", "name": "财务专员", "scope": "all",
        "desc": "全公司回款/清欠/发票/提成/保函;合同等只读",
        "perms": [
            "customer:view", "project:view", "quote:view", "contract:view", "order:view",
            "contract_review:view",
            "tech_agreement_review:view",
            "payment:view", "payment:edit",
            "collection:view", "collection:edit", "collection:manage",
            "commission:view", "commission:edit",
            "guarantee:view", "guarantee:edit",
        ],
    },
    {
        "code": "finance_manager", "name": "财务主管", "scope": "all", "lowcode_admin": True,
        "desc": "财务负责人:+ 合同财务条款 + 金额/毛利红线审批",
        "perms": [
            "customer:view", "project:view", "quote:view", "order:view",
            "contract:view", "contract:edit", "contract_review:view", "contract_review:edit",
            "tech_agreement_review:view", "tech_agreement_review:edit",
            "payment:view", "payment:edit",
            "collection:view", "collection:edit", "collection:manage",
            "commission:view", "commission:edit", "commission:manage",
            "guarantee:view", "guarantee:edit",
            "approval:approve", "approval:decide", "approval:delegate", "approval:manage",
        ],
    },
    {
        "code": "collection_officer", "name": "清欠专员", "scope": "all",
        "desc": "清欠办:应收清欠 + 回款登记",
        "perms": [
            "customer:view", "contract:view",
            "collection:view", "collection:edit", "collection:manage",
            "payment:view", "payment:edit",
        ],
    },
    {
        "code": "service_engineer", "name": "售后工程师", "scope": "self",
        "scope_by_resource": _CS_MODULE_SCOPE_ALL,
        "desc": "客户服务部:工单 + 实测 + 设备档案;客户可看全部",
        "perms": [
            "customer:view", "contract:view", "product:view",
            "service:view", "service:create", "service:edit",
        ],
    },
    {
        "code": "service_manager", "name": "售后主管", "scope": "dept", "lowcode_admin": True,
        "scope_by_resource": _CS_MODULE_SCOPE_ALL,
        "desc": "售后负责人:工单全权 + 审批;客户可看全部",
        "perms": [
            "customer:view", "contract:view", "product:view",
            "service:view", "service:create", "service:edit", "service:delete",
            "approval:approve", "approval:decide",
        ],
    },
    {
        # 对齐简道云「230902客服内勤」：客服落实/客服补登等节点审批人（或签）
        "code": "cs_office", "name": "230902客服内勤", "scope": "dept",
        "scope_by_resource": _CS_MODULE_SCOPE_ALL,
        "desc": "简道云客服内勤岗:客户服务申请落实、产品更换客服补登等流程审批;客户可看全部",
        "perms": [
            "customer:view", "service:view",
            "approval:approve", "approval:decide",
        ],
    },
    {
        # 对齐简道云「服务申请及反馈-客服安排」：客服安排1 等节点审批人（线上仅付加婧）
        "code": "cs_arrange", "name": "服务申请及反馈-客服安排", "scope": "dept",
        "scope_by_resource": _CS_MODULE_SCOPE_ALL,
        "desc": "简道云客服安排岗:客户服务申请及反馈「客服安排」节点审批（仅付加婧）;客户可看全部",
        "perms": [
            "customer:view", "service:view",
            "approval:approve", "approval:decide",
        ],
    },
    {
        "code": "cs_delay_approve", "name": "7.5客户服务延期申请-客服审批", "scope": "dept",
        "scope_by_resource": _CS_MODULE_SCOPE_ALL,
        "desc": "简道云客服延期审批岗:客户服务延期申请「客服审批」节点;客户可看全部",
        "perms": [
            "customer:view", "service:view",
            "approval:approve", "approval:decide",
        ],
    },
    {
        "code": "logistics_approval", "name": "物流审批", "scope": "dept",
        "scope_by_resource": {"shipment_notice": "all"},
        "desc": "发货通知「物流审批」节点；发货通知列表看全部",
        "perms": [
            "delivery:view",
            "approval:approve", "approval:decide",
        ],
    },
    {
        "code": "ship_sales_outbound", "name": "24.1发货通知流程-销售出库", "scope": "dept",
        "scope_by_resource": {"shipment_notice": "all"},
        "desc": "简道云发货通知销售出库仓:仓库/仓库判定节点审批",
        "perms": [
            "order:view", "delivery:view",
            "approval:approve", "approval:decide",
        ],
    },
    {
        "code": "gate_guard", "name": "240706门岗保卫组", "scope": "dept",
        "scope_by_resource": {"shipment_notice": "all"},
        "desc": "简道云门岗保卫组:发货通知抄送门岗",
        "perms": [
            "delivery:view",
            "approval:approve", "approval:decide",
        ],
    },
    {
        "code": "prod_material_code", "name": "1.2.8生产卡/补充流程-物料编码", "scope": "dept",
        "scope_by_resource": {"prod_card_supplement": "all"},
        "desc": "简道云生产卡「物料编码」节点：韩青芳、司子潆、郭雪",
        "perms": [
            "order:view", "product:view",
            "approval:approve", "approval:decide",
        ],
    },
    {
        "code": "procurement", "name": "采购专员", "scope": "dept",
        "desc": "采购部/外购:订单 + 产品;合同/交付只读",
        "perms": [
            "project:view", "contract:view", "delivery:view",
            "order:view", "order:create", "order:edit",
            "product:view", "product:edit",
        ],
    },
    {
        "code": "legal", "name": "24.2.3合同/项目评审-法务审批多人", "scope": "all",
        "scope_by_resource": {
            "prod_card_supplement": "all",
            "xunhan_contract_review": "all",
        },
        "desc": "对齐简道云「24.2.3合同/项目评审-法务审批多人」/生产卡法务审核；成员杜习慧、孔雪、张孟杰",
        "perms": [
            "contract_review:view",
            "approval:approve", "approval:decide",
        ],
    },
    {
        "code": "cs_named_fjj_zdd_jw", "name": "付加靖-张丹丹  姜婉", "scope": "dept",
        "scope_by_resource": _CS_MODULE_SCOPE_ALL,
        "desc": "简道云具名客服组:付加婧、张丹丹、段尉利;客户可看全部",
        "perms": [
            "customer:view", "service:view",
            "approval:approve", "approval:decide",
        ],
    },
    {
        "code": "cs_service_cc", "name": "7.1.1售后服务申请及反馈-客服安排抄送", "scope": "dept",
        "scope_by_resource": _CS_MODULE_SCOPE_ALL,
        "desc": "简道云客服安排抄送岗;客户可看全部",
        "perms": [
            "customer:view", "service:view",
            "approval:approve", "approval:decide",
        ],
    },
    {
        "code": "cs_replace_trace", "name": "7.1.2售出产品更换（补发）流程-发起追溯", "scope": "dept",
        "scope_by_resource": _CS_MODULE_SCOPE_ALL,
        "desc": "简道云售出产品更换发起追溯;客户可看全部",
        "perms": [
            "customer:view", "service:view",
            "approval:approve", "approval:decide",
        ],
    },
    {
        "code": "cs_special_release", "name": "27.10特殊放行申请-客服备案", "scope": "dept",
        "scope_by_resource": _CS_MODULE_SCOPE_ALL,
        "desc": "简道云特殊放行客服备案;客户可看全部",
        "perms": [
            "customer:view", "service:view",
            "approval:approve", "approval:decide",
        ],
    },
    {
        "code": "cs_service_record", "name": "7.3客户服务记录-审核登记", "scope": "dept",
        "scope_by_resource": _CS_MODULE_SCOPE_ALL,
        "desc": "简道云客户服务记录审核登记;客户可看全部",
        "perms": [
            "customer:view", "service:view",
            "approval:approve", "approval:decide",
        ],
    },
    {
        "code": "trip_overtime_init15", "name": "22.13出差加班申请流程-15人发起", "scope": "dept",
        "desc": "简道云出差加班 15 人发起组",
        "perms": [
            "approval:approve", "approval:decide",
        ],
    },
    {
        "code": "loan_eng_mgmt", "name": "1.1.2借款流程-工程管理中心", "scope": "dept",
        "desc": "简道云借款流程工程管理中心",
        "perms": [
            "approval:approve", "approval:decide",
        ],
    },
    {
        "code": "biz_backoffice", "name": "业务内勤", "scope": "dept",
        "desc": "简道云业务内勤岗",
        "perms": [
            "customer:view", "contract:view",
            "approval:approve", "approval:decide",
        ],
    },
    {
        "code": "jdy_sub_admin", "name": "子管理员", "scope": "all", "lowcode_admin": True,
        "desc": "简道云子管理员:扩展平台设计/管理 + 全数据范围",
        "perms": [
            "customer:view", "contract:view", "service:view",
            "approval:approve", "approval:decide", "approval:delegate",
        ],
    },
    {
        "code": "executive", "name": "高管(只读)", "scope": "all",
        "desc": "总经办/总经理:全模块只读 + 审批 + 审计;不可增改",
        "perms": [
            "customer:view", "contact:view", "lead:view", "project:view", "quote:view",
            "contract:view", "solution:view", "change:view", "delivery:view",
            "payment:view", "collection:view", "commission:view", "guarantee:view",
            "order:view", "tender:view", "product:view", "service:view", "audit:view",
            "approval:approve", "approval:decide", "approval:delegate",
        ],
    },
]

STANDARD_ROLE_CODES = frozenset(r["code"] for r in STANDARD_ROLES)


def role_perm_codes(role_def: dict) -> list[str]:
    """Full, de-duplicated permission code list for a standard role definition:
    CORE + role-specific perms + (LOWCODE_DESIGN if lowcode_admin)."""
    codes = list(CORE) + list(role_def["perms"])
    if role_def.get("lowcode_admin"):
        codes += LOWCODE_DESIGN
    return list(dict.fromkeys(codes))
