# 售出产品/工具退回 — CRM 字段对照

> 简道云 app=`58e2fbc7ffd1608b4ce92809` entry=`5e10538c0d5a270006df2763`

- **builtin key**: `cs_product_return`
- **路由**: `/cs-product-returns`
- **字段数**: 28（发起必填 0；明细列必填 0）
- **流程节点**: 22 / 连线 29
- **流水号前缀**: `TH`
- **必填来源**: `_jdy_customer_service_linkages.json`（edit allowBlank=false）

| slug | 标签 | type | 必填 | 创建可填 | stage | jdy_widget |
|------|------|------|------|----------|-------|------------|
| serial_no | 流程编号 | auto_number |  | 是 | initiator | `_widget_1578121055665` |
| apply_datetime | 日期时间 | datetime |  | 是 | initiator | `_widget_1703723955401` |
| field | *提交人 | person |  | 是 | initiator | `_widget_1672114764912` |
| field_2 | 发起部门 | department |  | 是 | initiator | `_widget_1657678970356` |
| field_3 | 类型 | radio |  | 是 | initiator | `_widget_1703723955300` |
| customer_name | 客户名称 | customer |  | 是 | initiator | `_widget_1577514157595` |
| field_4 | 业务部门 | department |  | 是 | initiator | `_widget_1578119863142` |
| sales_person | 业务员 | person |  | 是 | initiator | `_widget_1577520412656` |
| field_5 | 现场联系人及电话 | text |  | 是 | initiator | `_widget_1577514157633` |
| field_6 | 货物地址 | text |  | 是 | initiator | `_widget_1577514157611` |
| remark | 备注 | textarea |  | 是 | initiator | `_widget_1577519023451` |
| field_7 | 售出产品退回 | detail_table |  | 是 | initiator | `_widget_1577519022536` |
| └ contract_no | 合同号 | text |  | | | `_widget_1577519022537` |
| └ field_8 | 设备名称 | text |  | | | `_widget_1577519022538` |
| └ field_9 | 规格型号 | text |  | | | `_widget_1577519022539` |
| └ field_10 | 数量 | number |  | | | `_widget_1577519022540` |
| └ field_11 | 单位 | text |  | | | `_widget_1578287861127` |
| └ field_12 | 发货日期 | datetime |  | | | `_widget_1577519022541` |
| └ field_13 | 退回产品详细说明 | textarea |  | | | `_widget_1577519022542` |
| └ remark_2 | 备注 | textarea |  | | | `_widget_1577519022543` |
| └ field_14 | 仓库判定* | radio |  | | | `_widget_1665817650935` |
| images | 图片 | detail_table |  | 是 | initiator | `_widget_1619070556652` |
| └ field_15 | 上传人 | text |  | | | `_widget_1619070556669` |
| └ images_2 | 图片 | image |  | | | `_widget_1619070556688` |
| field_16 | 发起节点上传退回图片 | detail_table |  | 是 | initiator | `_widget_1736757240448` |
| └ field_17 | 上传人 | text |  | | | `_widget_1736757240449` |
| └ images_3 | 图片 | image |  | | | `_widget_1736757240450` |
| images_4 | 图片 | image |  | 是 | initiator | `_widget_1578537741743` |
| attachments | 附件 | file |  | 是 | initiator | `_widget_1590721272018` |
| images_5 | 图片 | image |  |  | approver | `_widget_1620023611025` |
| field_18 | 会签成员 | person_multi |  |  | approver | `_widget_1578128358932` |
| field_19 | 分发质检人员 | person_multi |  |  | approver | `_widget_1703723955512` |
| field_20 | 分发生产人员 | person_multi |  |  | approver | `_widget_1703723955568` |
| field_21 | 分发采购人员 | person_multi |  |  | approver | `_widget_1703723955540` |
| field_22 | 分发仓库人员 | person_multi |  |  | approver | `_widget_1586758707499` |
| field_23 | 维修部门 | department |  | 是 |  | `_widget_1578128358033` |
| f_1 | 仓库判定1 | select |  | 是 |  | `_widget_1578127027977` |
| field_24 | 流程判断 | radio |  | 是 |  | `_widget_1691974761704` |
| field_25 | 物流情况 | radio |  |  | approver | `_widget_1753923897787` |
| field_26 | 是否转相关人员 | radio |  | 是 | initiator | `_widget_1734925951092` |
| field_27 | 转相关人员 | person_multi |  | 是 | initiator | `_widget_1734925951094` |

### 流程降级备注

- 审批「仓库接收1」具名用户 02366368263850，无匹配用户时 auto_approve
- 审批「客服办理/会签」JDY 角色「230902客服内勤」降级为 sales_manager
- 审批「质检」具名用户 191811255038139135，无匹配用户时 auto_approve
- 审批「财务判定」具名用户 03303022525221387032，无匹配用户时 auto_approve
- 审批「质检二次鉴定」具名用户 191811255038139135，无匹配用户时 auto_approve
- 审批「仓库接收2」具名用户 02366368263850，无匹配用户时 auto_approve
- 审批「财务备案」具名用户 03303022525221387032，无匹配用户时 auto_approve
- 审批「物流中心」具名用户 ['575448583538947351', '02362440128774']，无匹配用户时 auto_approve
- 审批「客服办理/会签」JDY 角色「230902客服内勤」降级为 sales_manager
- 审批「质检鉴定」具名用户 191811255038139135，无匹配用户时 auto_approve
- 审批「生产」具名用户 02364437547295，无匹配用户时 auto_approve
- 审批「采购」具名用户 054351591124488512，无匹配用户时 auto_approve
- 审批「采购」具名用户 1135263833366065，无匹配用户时 auto_approve
- 节点「n20」5 条出边已标互斥组 ex_n20
- 节点「n17」2 条出边已标互斥组 ex_n17
- 节点「start」3 条出边已标互斥组 ex_start
- 节点「n31」2 条出边已标互斥组 ex_n31
- optAuth：7 个字段仅审批可写（创建 available_on_create=false，必填下沉到节点 field_perms）
- optAuth：3 个字段发起仅可见（form_editable=false）

