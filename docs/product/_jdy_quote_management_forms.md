# 报价管理 — CRM 字段对照（简道云核价管理流程）

> 简道云 app=`5e6c73fefc53170006bd4e9c` entry=`5e6c740e6d74970006a67190`

- **builtin key**: `quote_management`
- **路由**: `/quotes`
- **字段数（去噪后）**: 16
- **必填字段**: 3
- **流程节点数（CRM）**: 20 / 连线 35
- **流水号**: `HJ` + yyyyMMdd + 三位日序

| slug | 标签 | type | 必填 | jdy_widget |
|------|------|------|------|------------|
| serial_no | 流程编号 | auto_number |  | `_widget_1584947843078` |
| department | 部门 | department | 是 | `_widget_1584171854303` |
| sales_person | 业务员 | person | 是 | `_widget_1584171854327` |
| ref_contract_no | 参考合同号 | text |  | `_widget_1584171854451` |
| customer_name | 客户名称 | customer | 是 | `_widget_1584171854467` |
| card_contract_no | 下卡合同号 | text |  | `_widget_1703483758901` |
| customer_category | 客户类别 | radio |  | `_widget_1584171854483` |
| price_type | 价格类型 | radio |  | `_widget_1584171854518` |
| price_lines | 价格明细 | detail_table |  | `_widget_1584171854537` |
| └ product_name | 产品名称 | text |  | `_widget_1584171854549` |
| └ spec_model | 规格型号 | text |  | `_widget_1584171854562` |
| └ unit | 单位 | text |  | `_widget_1584171854577` |
| └ qty | 数量 | number |  | `_widget_1584171854595` |
| need_purchase | 是否转采购 | radio |  | `_widget_1594186007096` |
| purchaser | 采购 | person |  | `_widget_1594186007147` |
| inquiry_attachments | 询价单附件 | file |  | `_widget_1584171854659` |
| cost_attachments | 成本价附件 | file |  | `_widget_1584171854768` |
| inquiry_images | 询价图片 | file |  | `_widget_1618967240669` |
| special_reminder | 特别提醒 | textarea |  | `_widget_1585297155465` |
| cost_price | 成本价 | textarea |  | `_widget_1584171854755` |

### 流程降级备注

- 审批「财务核价」具名用户 0433406811775721，无匹配用户时 auto_approve
- 审批「王玲玲审批」JDY 角色「王玲玲」→ 指定用户 01000533004677
- 审批「经理审批」JDY 角色「热能利用-段荣凯」→ 指定用户 02364714147257
- 审批「热能」JDY 角色「热能利用-段荣凯」→ 指定用户 02364714147257
- 审批「国际营销中心」具名用户 01000533004677，无匹配用户时 auto_approve
- 审批「冶金装备销售事业部」JDY 角色「27.7核价管理流程-冶金」→ 可选范围 `quote_metallurgy`
- 审批「通知矿山工程装备销售」具名用户 02374949202624，无匹配用户时 auto_approve
- 审批「赵亚芳」具名用户 060158356435457934，无匹配用户时 auto_approve
- 审批「经理审批」具名用户 02364714147257，无匹配用户时 auto_approve
- 审批「王玲玲审批」具名用户 01000533004677，无匹配用户时 auto_approve
- CC「抄送」绑定具名用户 02362556584221，CRM 无对应用户时 empty→auto_approve 不适用 CC，可能跳过
- 审批「袁文俊」具名用户 02364840011125，无匹配用户时 auto_approve
- 节点「n6」2 条出边已标互斥组 ex_n6
- 节点「start」3 条出边已标互斥组 ex_start
- 节点「n1」2 条出边已标互斥组 ex_n1
- 节点「n10」2 条出边已标互斥组 ex_n10
- 节点「n11」2 条出边已标互斥组 ex_n11
- 节点「n2」7 条出边已标互斥组 ex_n2
- 节点「n17」3 条出边已标互斥组 ex_n17
- 节点「抄送发起人」无出边（抄送旁路，不接到结束）
- 节点「抄送」无出边（抄送旁路，不接到结束）
- optAuth：5 个字段仅审批可写（创建 available_on_create=false，必填下沉到节点 field_perms）
- optAuth：1 个字段发起仅可见（form_editable=false）
- 财务核价：是否转采购 → editable（非必填）
- 部门审批×2：客户类别/价格类型 → editable（创建不填，非必填）
- 通知尚高华 → 通知发起人（approver_rule=creator）
- 财务核价→采购：并行（不与部门通知互斥）；采购→财务核价可重入
- 财务核价→部门通知：多条件并行可重入（通知发起人与热能等可同时命中）
- 通知发起人：是否转采购≠是才进入（对齐简道云采购回路实单）
- 客户类别/价格类型：创建隐藏，部门审批可填（非必填）

