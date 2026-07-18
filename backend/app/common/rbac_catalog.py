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
    ("dashboard:manage", "设计/管理仪表盘", "扩展平台"),
]

# Permissions EVERY standard role gets. Includes the 扩展平台「使用」层 so all
# staff can fill forms, view flows & dashboards.
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
LOWCODE_DESIGN = ["form:manage", "workflow:manage", "dashboard:manage", "form_data:delete"]

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
            "solution:view", "contract:view", "delivery:view", "payment:view",
            "order:view", "product:view", "tender:view",
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
            "solution:view", "contract:view", "delivery:view", "payment:view",
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
            "solution:view", "contract:view", "delivery:view", "payment:view",
            "order:view", "product:view", "tender:view", "commission:view",
            "approval:approve", "approval:decide", "approval:delegate",
        ],
    },
    {
        "code": "lead_intel", "name": "信息情报部内勤", "scope": "all",
        "desc": "线索审核/分发:审核业务员提交的线索;自身单条录入或Excel导入免审",
        "perms": [
            "customer:view",
            "lead:view", "lead:create", "lead:edit", "lead:review",
            "lead:qualify", "lead:discard",
            "approval:approve", "approval:decide", "approval:delegate",
        ],
    },
    {
        "code": "biz_support", "name": "商务/标书专员", "scope": "dept",
        "desc": "市场支持/国际业务支持:标书 + 协助报价",
        "perms": [
            "customer:view", "project:view", "quote:view", "quote:edit",
            "contract:view", "product:view",
            "tender:view", "tender:create", "tender:edit", "tender:delete",
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
        "code": "tech_chief", "name": "技术总工/评审", "scope": "all", "lowcode_admin": True,
        "desc": "全局技术只读 + 方案/变更评审与审批",
        "perms": [
            "customer:view", "project:view", "quote:view", "contract:view", "product:view",
            "solution:view", "solution:create", "solution:edit",
            "change:view", "change:create", "change:edit",
            "approval:approve", "approval:decide", "approval:delegate",
        ],
    },
    {
        "code": "production", "name": "生产/交付专员", "scope": "dept",
        "desc": "生产管理部及车间:交付里程碑 + 订单",
        "perms": [
            "customer:view", "project:view", "contract:view", "product:view",
            "delivery:view", "delivery:edit",
            "order:view", "order:create", "order:edit",
        ],
    },
    {
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
            "contract:view", "contract:edit",
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
        "desc": "客户服务部:工单 + 实测 + 设备档案",
        "perms": [
            "customer:view", "contract:view", "product:view",
            "service:view", "service:create", "service:edit",
        ],
    },
    {
        "code": "service_manager", "name": "售后主管", "scope": "dept", "lowcode_admin": True,
        "desc": "售后负责人:工单全权 + 审批",
        "perms": [
            "customer:view", "contract:view", "product:view",
            "service:view", "service:create", "service:edit", "service:delete",
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
        "code": "legal", "name": "合同法务", "scope": "all",
        "desc": "法务管理小组:合同审查/签署 + 合同审批",
        "perms": [
            "customer:view", "project:view", "quote:view",
            "contract:view", "contract:edit", "contract:sign",
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
