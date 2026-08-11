# 客服借据 — CRM 字段对照

> 简道云 app=`58e2fbc7ffd1608b4ce92809` entry=`62cccb4c8ee15d0009136487`

- **builtin key**: `cs_loan_slip`
- **路由**: `/cs-loan-slips`
- **字段数**: 14（发起必填 0；明细列必填 0）
- **流程节点**: 7 / 连线 8
- **流水号前缀**: `JJ`
- **必填来源**: `_jdy_customer_service_linkages.json`（edit allowBlank=false）

| slug | 标签 | type | 必填 | 创建可填 | stage | jdy_widget |
|------|------|------|------|----------|-------|------------|
| serial_no | 流程编号 | auto_number |  | 是 | initiator | `_widget_1597215968591` |
| field | 借据日期 | datetime |  | 是 | initiator | `_widget_1562729205516` |
| customer_name | 客户名称 | customer |  | 是 | initiator | `_widget_1562729205685` |
| contract_no | 合同号 | contract |  | 是 | initiator | `_widget_1562983148782` |
| field_2 | 业务部门 | department |  | 是 | initiator | `_widget_1562813161623` |
| sales_person | 业务员 | person |  | 是 | initiator | `_widget_1562729205744` |
| field_3 | 对应内勤 | person_multi |  | 是 | initiator | `_widget_1774490710430` |
| field_4 | 明细 | detail_table |  | 是 | initiator | `_widget_1562730672596` |
| └ field_5 | 设备名称 | text |  | | | `_widget_1562730672619` |
| └ field_6 | 规格型号 | text |  | | | `_widget_1562917785582` |
| └ field_7 | 数量 | number |  | | | `_widget_1562730672647` |
| └ field_8 | 单位 | text |  | | | `_widget_1562922344901` |
| field_9 | 是否已抽条 | radio |  |  | approver | `_widget_1749513825257` |
| field_10 | 抽条日期 | datetime |  |  | approver | `_widget_1655946162663` |
| field_11 | 附件 | file |  | 是 | initiator | `_widget_1657596605516` |
| field_12 | 图片 | image |  | 是 | initiator | `_widget_1657596605551` |
| field_13 | 抽条备注 | textarea |  |  | approver | `_widget_1562730825101` |
| field_14 | 区域经理/组长 | person |  | 是 | initiator | `_widget_1770085770735` |

### 流程降级备注

- 审批「财务处理」具名用户 03303022525221387032，无匹配用户时 auto_approve
- 审批「迅焊经理」具名用户 ['02255532014443', '02352513566524']，无匹配用户时 auto_approve
- 节点「start」3 条出边已标互斥组 ex_start
- 节点「抄送节点」无出边（抄送旁路，不接到结束）
- optAuth：3 个字段仅审批可写（创建 available_on_create=false，必填下沉到节点 field_perms）
- optAuth：2 个字段发起仅可见（form_editable=false）

