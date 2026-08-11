# 客户服务申请及反馈 — CRM 字段对照

> 简道云 app=`58e2fbc7ffd1608b4ce92809` entry=`5e06c8a92675f1000634baf1`

- **builtin key**: `cs_service_request`
- **路由**: `/cs-service-requests`
- **字段数**: 31（发起必填 9；明细列必填 15）
- **流程节点**: 21 / 连线 28
- **流水号前缀**: `KF`
- **必填来源**: `_jdy_customer_service_linkages.json`（edit allowBlank=false）

| slug | 标签 | type | 必填 | 创建可填 | stage | jdy_widget |
|------|------|------|------|----------|-------|------------|
| serial_no | 流程编号 | auto_number |  | 是 | initiator | `_widget_1578287685594` |
| field | 所属部门 | department | 是 | 是 | initiator | `_widget_1577494164593` |
| sales_person | 业务员 | person | 是 | 是 | initiator | `_widget_1577494164575` |
| field_2 | 区域经理/组长 | person |  | 是 | initiator | `_widget_1770083447771` |
| customer_name | 客户名称 | customer | 是 | 是 | initiator | `_widget_1577494164611` |
| field_3 | 是否是小萌 | radio | 是 | 是 | initiator | `_widget_1684370183791` |
| field_4 | 服务地点 | text | 是 | 是 | initiator | `_widget_1577494164627` |
| field_5 | 服务要求 | text | 是 | 是 | initiator | `_widget_1577494164659` |
| field_6 | 乘车路线及费用 | text | 是 | 是 | initiator | `_widget_1577494164643` |
| field_7 | 服务性质 | checkbox | 是 | 是 | initiator | `_widget_1577513844817` |
| remark | 备注 | text |  | 是 | initiator | `_widget_1578643639316` |
| field_8 | 客户种类 | radio |  |  | approver | `_widget_1649229021346` |
| field_9 | 紧急情况 | checkbox |  |  | approver | `_widget_1646903016596` |
| field_10 | 主要产品信息 | detail_table |  | 是 | initiator | `_widget_1577495431595` |
| └ field_11 | 有无合同号 | radio | 是 | | | `_widget_1712128588465` |
| └ contract_no | 合同号 | text | 是 | | | `_widget_1577495431618` |
| └ field_12 | 现场联系人及电话 | text | 是 | | | `_widget_1578108364286` |
| └ field_13 | 设备名称 | text | 是 | | | `_widget_1577495431631` |
| └ field_14 | 设备型号 | text | 是 | | | `_widget_1577495431646` |
| └ field_15 | 数量 | number | 是 | | | `_widget_1577495431703` |
| └ field_16 | 单位 | text | 是 | | | `_widget_1578287341598` |
| └ field_17 | 发货日期 | datetime | 是 | | | `_widget_1577495431722` |
| field_18 | 其它待排查产品 | select | 是 | 是 | initiator | `_widget_1577495432709` |
| field_19 | 有其它排产产品明细 | detail_table |  | 是 | initiator | `_widget_1577495432749` |
| └ field_20 | 有无合同号 | radio |  | | | `_widget_1712128588499` |
| └ contract_no_2 | 合同号 | text | 是 | | | `_widget_1577495432750` |
| └ field_21 | 现场联系人及电话 | text | 是 | | | `_widget_1577495433532` |
| └ field_22 | 设备名称 | text | 是 | | | `_widget_1577495432751` |
| └ field_23 | 设备型号 | text | 是 | | | `_widget_1577495432752` |
| └ field_24 | 数量 | number | 是 | | | `_widget_1577495432753` |
| └ field_25 | 单位 | text | 是 | | | `_widget_1578287341623` |
| └ field_26 | 发货日期 | datetime | 是 | | | `_widget_1577495432754` |
| field_27 | 总工转交 | radio |  |  | approver | `_widget_1600497623100` |
| field_28 | 总工下转 | person |  |  | approver | `_widget_1600497620698` |
| field_29 | 附件 | file |  | 是 | initiator | `_widget_1578270713998` |
| field_30 | 客服附件 | file |  |  | approver | `_widget_1578270714335` |
| field_31 | 客服安排附件 | file |  |  | approver | `_widget_1586759656542` |
| field_32 | 图片 | image |  | 是 | initiator | `_widget_1618967086538` |
| field_33 | 需要协作 | select |  |  | approver | `_widget_1578109421544` |
| field_34 | 协作人员 | person_multi |  |  | approver | `_widget_1586759657262` |
| field_35 | 是否需要转交 | radio |  |  | approver | `_widget_1599529315677` |
| field_36 | 转交人员 | person_multi |  |  | approver | `_widget_1599529315858` |
| field_37 | 是否需要通知相关人员 | radio |  |  | approver | `_widget_1599529317113` |
| field_38 | 通知相关人员 | person_multi |  |  | approver | `_widget_1599529317145` |
| field_39 | 客服组长 | person_multi |  |  | approver | `_widget_1776385827924` |
| field_40 | 是否需要总经理批示 | radio |  |  | approver | `_widget_1736846540976` |
| field_41 | 客服备注 | detail_table |  |  | approver | `_widget_1774333506025` |
| └ field_42 | 内容 | text |  | | | `_widget_1774333506027` |
| └ field_43 | 附件 | file |  | | | `_widget_1774333506028` |

### 流程降级备注

- 审批「客服落实」JDY 角色「230902客服内勤」降级为 sales_manager
- 审批「总工审批」具名用户 02364335378133，无匹配用户时 auto_approve
- 审批「总经理」JDY 角色「总经理」降级为 sales_manager
- 审批「客服安排1」JDY 角色「服务申请及反馈-客服安排」降级为 sales_manager
- 审批「业务经理」具名用户 01000533004677，无匹配用户时 auto_approve
- 审批「业务经理」具名用户 02364714147257，无匹配用户时 auto_approve
- 审批「客服经理」具名用户 02352513566524，无匹配用户时 auto_approve
- 审批「客服安排2」具名用户 02352513566524，无匹配用户时 auto_approve
- 审批「总经理」JDY 角色「总经理」降级为 sales_manager
- 节点「n6__1」2 条出边已标互斥组 ex_n6__1
- 节点「start」6 条出边已标互斥组 ex_start
- 节点「n4」2 条出边已标互斥组 ex_n4
- 节点「n8」2 条出边已标互斥组 ex_n8
- 节点「抄送节点」无出边（抄送旁路，不接到结束）
- 节点「通知相关人员」无出边（抄送旁路，不接到结束）
- optAuth：15 个字段仅审批可写（创建 available_on_create=false，必填下沉到节点 field_perms）
- optAuth：2 个字段发起仅可见（form_editable=false）
- 节点 validator：6 处审批必填（如「客户种类必填」）
- edit_raw allowBlank=false：31 个必填 widget
- fieldShowRules → 8 条显隐/条件必填规则

