# 售出产品更换（补发） — CRM 字段对照

> 简道云 app=`58e2fbc7ffd1608b4ce92809` entry=`5e06f4ad2a9eb70007f7c164`

- **builtin key**: `cs_product_replace`
- **路由**: `/cs-product-replaces`
- **字段数**: 33（发起必填 0；明细列必填 0）
- **流程节点**: 19 / 连线 29
- **流水号前缀**: `GH`
- **必填来源**: `_jdy_customer_service_linkages.json`（edit allowBlank=false）

| slug | 标签 | type | 必填 | 创建可填 | stage | jdy_widget |
|------|------|------|------|----------|-------|------------|
| serial_no | 流程编号 | auto_number |  | 是 | initiator | `_widget_1578121055665` |
| field | 日期时间 | datetime |  | 是 | initiator | `_widget_1617689215719` |
| field_2 | 业务部门 | department |  | 是 | initiator | `_widget_1578119863142` |
| sales_person | 业务员 | person |  | 是 | initiator | `_widget_1577520412656` |
| field_3 | 对应区域经理或组长 | person |  | 是 | initiator | `_widget_1770085266610` |
| customer_name | 客户名称 | customer |  | 是 | initiator | `_widget_1577514157595` |
| field_4 | 货物地址 | text |  | 是 | initiator | `_widget_1577514157611` |
| field_5 | 现场联系人及电话 | text |  | 是 | initiator | `_widget_1577514157633` |
| remark | 备注 | textarea |  | 是 | initiator | `_widget_1577519023451` |
| field_6 | 是否需退回 | radio |  | 是 | initiator | `_widget_1675673210466` |
| field_7 | 是否关联验收回款 | radio |  | 是 | initiator | `_widget_1749182322753` |
| field_8 | 是否需打借据 | radio |  |  | approver | `_widget_1675673210468` |
| field_9 | 紧急程度判定-业务经理 | radio |  |  | approver | `_widget_1739261778534` |
| field_10 | 紧急程度判定-客服经理 | radio |  |  | approver | `_widget_1739261778536` |
| field_11 | 紧急程度判定-总经理 | radio |  |  | approver | `_widget_1739318635777` |
| field_12 | 最终紧急程度判定 | text |  | 是 |  | `_widget_1739318635876` |
| field_13 | 换货（含补发） | detail_table |  | 是 | initiator | `_widget_1577519022536` |
| └ contract_no | 合同号 | text |  | | | `_widget_1577519022537` |
| └ field_14 | 设备名称 | text |  | | | `_widget_1577519022538` |
| └ field_15 | 规格型号 | text |  | | | `_widget_1577519022539` |
| └ field_16 | 数量 | number |  | | | `_widget_1577519022540` |
| └ field_17 | 单位 | text |  | | | `_widget_1578287834987` |
| └ field_18 | 发货日期 | datetime |  | | | `_widget_1577519022541` |
| └ field_19 | 退换详细说明 | textarea |  | | | `_widget_1577519022542` |
| └ field_20 | 故障分类 | text |  | | | `_widget_1617691334516` |
| field_21 | 成本价 | text |  |  | approver | `_widget_1687499358442` |
| field_22 | 图片 | detail_table |  | 是 | initiator | `_widget_1619070274799` |
| └ field_23 | 上传人 | text |  | | | `_widget_1619070274816` |
| └ field_24 | 图片 | image |  | | | `_widget_1619070274835` |
| f_0418 | 附件0418 | file |  | 是 | initiator | `_widget_1578271183948` |
| f_0418_2 | 客服附件0418 | file |  |  | approver | `_widget_1578271183961` |
| f_0418_3 | 客服补登附件0418 | file |  |  | approver | `_widget_1578702338220` |
| f_0418_4 | 会签附件0418 | file |  |  | approver | `_widget_1589433529814` |
| field_25 | 需要补登 | radio |  |  | approver | `_widget_1578452391724` |
| field_26 | 货是否发完 | radio |  |  | approver | `_widget_1675988284441` |
| field_27 | 是否小萌 | radio |  | 是 | initiator | `_widget_1716164018678` |
| field_28 | 会签 | radio |  |  | approver | `_widget_1578127027977` |
| f_0418_5 | 图片0418 | image |  | 是 | initiator | `_widget_1618966943220` |
| field_29 | 会签人员 | person_multi |  |  | approver | `_widget_1578127028052` |
| field_30 | 责任方 | text |  |  | approver | `_widget_1617689215015` |
| field_31 | 是否需要转交相关人员处理后补登 | radio |  |  | approver | `_widget_1593825383660` |
| field_32 | 相关人员处理 | person |  |  | approver | `_widget_1593825383717` |
| field_33 | 客服备注 | detail_table |  |  | approver | `_widget_1774333375920` |
| └ field_34 | 内容 | text |  | | | `_widget_1774333375922` |
| └ field_35 | 附件 | file |  | | | `_widget_1774333375923` |

### 流程降级备注

- 审批「客服会签」JDY 角色「7.1.2售出产品更换（补发）流程-客服补登」降级为 sales_manager
- 审批「总工审批」JDY 角色「7.1.1售后服务申请及反馈-总工审批」降级为 sales_manager
- 审批「总经理审批」JDY 角色「总经理」降级为 sales_manager
- 审批「客服补登」JDY 角色「7.1.2售出产品更换（补发）流程-客服补登」降级为 sales_manager
- 审批「王玲玲」JDY 角色「7.1.1售后服务申请及反馈-王玲玲」降级为 sales_manager
- 审批「客服补登」JDY 角色「7.1.2售出产品更换（补发）流程-客服补登」降级为 sales_manager
- 审批「业务经理审批」JDY 角色「热能利用-段荣凯」降级为 sales_manager
- 审批「财务核算」JDY 角色「7.1.2售出产品更换（补发）流程-财务开票抄送」降级为 sales_manager
- 审批「部门经理审批1」具名用户 02255532014443，无匹配用户时 auto_approve
- 审批「技术审批」具名用户 02391125207699，无匹配用户时 auto_approve
- 审批「迅焊总经理审批」具名用户 02352513566524，无匹配用户时 auto_approve
- CC「抄送潘惠敏」绑定具名用户 286057106726080520，CRM 无对应用户时 empty→auto_approve 不适用 CC，可能跳过
- 审批「部门经理审批2」具名用户 02352513566524，无匹配用户时 auto_approve
- 节点「n9」2 条出边已标互斥组 ex_n9
- 节点「start」7 条出边已标互斥组 ex_start
- 节点「n4」2 条出边已标互斥组 ex_n4
- 节点「n6」3 条出边已标互斥组 ex_n6
- 节点「n18」2 条出边已标互斥组 ex_n18
- 节点「抄送潘惠敏」无出边（抄送旁路，不接到结束）
- optAuth：16 个字段仅审批可写（创建 available_on_create=false，必填下沉到节点 field_perms）
- optAuth：3 个字段发起仅可见（form_editable=false）

