# 售前服务通知 — CRM 字段对照（简道云售前服务通知流程）

> 简道云 app=`5de0b3e85600ec0006f420f2` entry=`5e79b7e9b587cc0006b632d7`

- **builtin key**: `presale_service_notice`
- **路由**: `/presale-service-notices`
- **字段数（去噪后）**: 26
- **静态必填**: 8
- **流程节点数（CRM）**: 13 / 连线 16
- **联动规则**: 10
- **流水号**: `24.13-` + yyyyMMdd + 四位日序

| slug | 标签 | type | 必填 | jdy_widget |
|------|------|------|------|------------|
| serial_no | 流程编号 | auto_number |  | `_widget_1585030991874` |
| applicant | 申请人 | person | 是 | `_widget_1585030991951` |
| department | 所属部门 | department | 是 | `_widget_1585030991969` |
| is_smart | 是否智能化 | radio | 是 | `_widget_1676250045146` |
| need_jwx_onsite | 是否需要金微星去现场 | radio | 是 | `_widget_1677464667996` |
| project_status | 项目状态 | radio |  | `_widget_1672367052763` |
| smart_project_status | 智能化项目状态 | radio |  | `_widget_1676250045169` |
| attachments | 附件 | file |  | `_widget_1685405177505` |
| desired_staff | 希望派遣人员 | person |  | `_widget_1676250045148` |
| contract_no | 合同号 | contract |  | `_widget_1585030992152` |
| service_location | 服务地点 | text | 是 | `_widget_1585030992168` |
| service_time | 服务时间 | date | 是 | `_widget_1585030992184` |
| estimated_days | 预计天数 | text | 是 | `_widget_1585030992197` |
| contact_phone | 联系人/联系电话 | text | 是 | `_widget_1585030992213` |
| drawing_tech_status | 有无图纸及前期技术 | text |  | `_widget_1585030992228` |
| service_content | 服务内容 | textarea |  | `_widget_1585030992259` |
| work_schedule | 工作日程计划 | detail_table |  | `_widget_1585030992272` |
| └ schedule_datetime | 日期时间 | datetime |  | `_widget_1585030992295` |
| └ schedule_item | 工作日程 | text |  | `_widget_1585030992305` |
| remark | 备注 | textarea |  | `_widget_1585030992321` |
| staff_coordination | 人员协调 | person_multi |  | `_widget_1585030993520` |
| product_name | 产品名称 | text |  | `_widget_1585030992378` |
| spec_model | 规格型号 | text |  | `_widget_1585030992393` |
| surveyor | 测绘人 | text |  | `_widget_1585030992409` |
| survey_data | 测绘数据 | detail_table |  | `_widget_1585030992426` |
| └ item_name | 名称 | text |  | `_widget_1585030992438` |
| └ spec_model_2 | 规格型号 | text |  | `_widget_1585030992451` |
| └ qty | 数量 | number |  | `_widget_1585030992466` |
| └ unit | 单位 | text |  | `_widget_1585030992541` |
| └ unit_weight | 单重 | text |  | `_widget_1585030992613` |
| need_xjwm_staff | 是否需要新疆威猛人员 | radio |  | `_widget_1779413786198` |
| xjwm_staff | 新疆威猛人员 | person_multi |  | `_widget_1779413786190` |
| other_notes | 其他说明 | textarea |  | `_widget_1585030992645` |

### 流程降级备注

- 对齐简道云销售中心「售前服务通知流程」；流水号 24.13-+yyyyMMdd+四位日序。
- 审批「总工审批」JDY 角色「24.2.3合同/项目评审-设计-曹修国」→ 指定用户 02364335378133
- 审批「生产审批」具名用户 01210720669288，无匹配用户时 auto_approve
- 审批「韩利民」具名用户 02364307332960，无匹配用户时 auto_approve
- 审批「新疆威猛」具名用户 02364714147257，无匹配用户时 auto_approve
- 节点「n4」2 条出边已标互斥组 ex_n4
- 节点「n2」2 条出边已标互斥组 ex_n2
- 节点「start」2 条出边已标互斥组 ex_start
- 节点「n14」2 条出边已标互斥组 ex_n14
- 节点「抄送节点」无出边（抄送旁路，不接到结束）
- 节点「抄送节点」无出边（抄送旁路，不接到结束）
- optAuth：8 个字段仅审批可写（创建 available_on_create=false，必填下沉到节点 field_perms）
- optAuth：1 个字段发起仅可见（form_editable=false）
- 抄送节点：发起人本人 + 表单申请人（组合去重）。

