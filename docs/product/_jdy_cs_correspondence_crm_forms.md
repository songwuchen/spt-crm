# 客服往来函件 — CRM 字段对照

> 简道云 app=`58e2fbc7ffd1608b4ce92809` entry=`65de94717b566a9ff2059102`

- **builtin key**: `cs_correspondence`
- **路由**: `/cs-correspondences`
- **字段数**: 13（发起必填 0；明细列必填 0）
- **流程节点**: 7 / 连线 7
- **流水号前缀**: `WH`
- **必填来源**: `_jdy_customer_service_linkages.json`（edit allowBlank=false）

| slug | 标签 | type | 必填 | 创建可填 | stage | jdy_widget |
|------|------|------|------|----------|-------|------------|
| serial_no | 流程编号 | auto_number |  | 是 | initiator | `_widget_1709085809841` |
| field | 申请日期 | datetime |  | 是 | initiator | `_widget_1709085809140` |
| applicant | 申请人 | person |  | 是 | initiator | `_widget_1709085809141` |
| field_2 | 申请部门 | department |  | 是 | initiator | `_widget_1709085809142` |
| field_3 | 申请部门（文本） | text |  |  | approver | `_widget_1709085809854` |
| field_4 | 选择合同数据 | text |  | 是 | initiator | `_widget_1709085809842` |
| contract_no | 合同号 | contract |  | 是 | initiator | `_widget_1709085809143` |
| customer_name | 客户名称 | customer |  | 是 | initiator | `_widget_1709085809144` |
| field_5 | 业务部门 | department |  | 是 | initiator | `_widget_1709085809843` |
| sales_person | 业务员 | person |  | 是 | initiator | `_widget_1709085809145` |
| field_6 | 区域经理/组长 | person |  | 是 | initiator | `_widget_1770086518838` |
| field_7 | 具体情况描述 | text |  | 是 | initiator | `_widget_1709085809146` |
| field_8 | 附件与图片 | detail_table |  | 是 | initiator | `_widget_1709085809844` |
| └ images | 图片 | image |  | | | `_widget_1709085809846` |
| └ attachments | 附件 | file |  | | | `_widget_1709085809847` |

### 流程降级备注

- 审批「客服经理审批」具名用户 02364335378133，无匹配用户时 auto_approve
- 审批「内勤办理」JDY 角色「230902客服内勤」→ 指定用户 ['0236446249514', '181359282120075679', '113236314224043072', '01364955133227249077']
- 节点「start」2 条出边已标互斥组 ex_start
- 节点「抄送节点」无出边（抄送旁路，不接到结束）
- optAuth：1 个字段仅审批可写（创建 available_on_create=false，必填下沉到节点 field_perms）
- optAuth：4 个字段发起仅可见（form_editable=false）

