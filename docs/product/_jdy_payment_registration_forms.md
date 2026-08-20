# 收款登记 — CRM 字段对照

> 简道云 app=`56ca77ce1efc301d279b8a4d` entry=`5d63721786b06824f3fcc07f`

- **builtin key**: `payment_registration`
- **路由**: `/payment-registrations`
- **字段数（去噪后）**: 13
- **必填字段**: 4
- **流程节点数（CRM）**: 21 / 连线 42

| slug | 标签 | type | 必填 | jdy_widget |
|------|------|------|------|------------|
| payment_no | 收款号 | text |  | `_widget_1597214338291` |
| payment_date | 来款日期 | date | 是 | `_widget_1566798360384`；仅选日期 |
| customer_name | 单位名称 | customer | 是 | `_widget_1566798360397` |
| department | 部门 | department | 是 | `_widget_1566798360541` |
| payment_details | 来款明细 | detail_table | 是 | `_widget_1566798360592` |
| └ payment_method | 来款形式 | select |  | `_widget_1566798360604` |
| └ amount | 金额 | number |  | `_widget_1566798360619` |
| └ acceptance_no | 承兑号 | text |  | `_widget_1566798360836` |
| └ issuing_bank | 出票银行 | text |  | `_widget_1566798360817` |
| └ due_date | 到期日 | datetime |  | `_widget_1566798360803` |
| └ remark | 备注 | text |  | `_widget_1567674910625` |
| payment_total | 来款合计 | formula |  | `_widget_1566798361100` |
| sales_person | 业务人员 | person |  | `_widget_1566798361197` |
| payment_allocation | 款项分配 | detail_table |  | `_widget_1566798361280` |
| └ drawing_no | 图纸编号 | text |  | `_widget_1566798361303` |
| └ contract_no | 合同号240222添加 | text |  | `_widget_1708572036504` |
| └ payment_nature | 款项性质 | select |  | `_widget_1583377647110` |
| └ alloc_amount | 分配金额 | number |  | `_widget_1566798361344` |
| alloc_total | 分配金额合计 | formula |  | `_widget_1566798361432` |
| discount_docs | 贴息手续 | file |  | `_widget_1566798360977` |
| penalty_docs | 罚款手续 | file |  | `_widget_1566798361076` |
| images | 图片 | file |  | `_widget_1619061529091` |
| remark_2 | 备注 | textarea |  | `_widget_1566798361491` |

### 流程降级备注

- 审批「内勤处理」具名用户 034739380024350007，无匹配用户时 auto_approve
- 审批「内勤处理」具名用户 5252426618846750，无匹配用户时 auto_approve
- 审批「内勤处理」具名用户 ['02371402218363', '02364460327617']，无匹配用户时 auto_approve
- 审批「内勤处理」具名用户 263517372323629184，无匹配用户时 auto_approve
- 审批「内勤处理」具名用户 ['060266566126118095', '034739380024350007']，无匹配用户时 auto_approve
- 审批「内勤处理」具名用户 060832423223953982，无匹配用户时 auto_approve
- 审批「内勤处理」具名用户 5252426618846750，无匹配用户时 auto_approve
- 审批「内勤处理」具名用户 ['1767691603763250', '034739380024350007']，无匹配用户时 auto_approve
- 审批「内勤处理」具名用户 ['1012683212672619', '5252426618846750']，无匹配用户时 auto_approve
- 审批「内勤处理」具名用户 02374949202624，无匹配用户时 auto_approve
- 审批「内勤处理」具名用户 263517372323629184，无匹配用户时 auto_approve
- 审批「内勤处理」具名用户 4723152427763414，无匹配用户时 auto_approve
- 审批「内勤处理」具名用户 286057106726080520，无匹配用户时 auto_approve
- 审批「采购」具名用户 02352513566524，无匹配用户时 auto_approve
- CC「抄送节点」绑定具名用户 ['023641581817', 'manager2820']，CRM 无对应用户时 empty→auto_approve 不适用 CC，可能跳过
- CC「抄送节点」绑定具名用户 ['023641581817', 'manager2820', '263517372323629184', '023643375426243110']，CRM 无对应用户时 empty→auto_approve 不适用 CC，可能跳过
- 审批「内勤处理」具名用户 ['1012683212672619', '5252426618846750', '023641581817']，无匹配用户时 auto_approve
- CC「迅焊抄送」绑定具名用户 ['02352513566524', '023641581817']，CRM 无对应用户时 empty→auto_approve 不适用 CC，可能跳过
- 审批「内勤处理」具名用户 5252426618846750，无匹配用户时 auto_approve
- 节点「start」15 条出边已标互斥组 ex_start
- 节点「抄送节点」无出边（抄送旁路，不接到结束）
- 节点「抄送节点」无出边（抄送旁路，不接到结束）
- 节点「迅焊抄送」无出边（抄送旁路，不接到结束）
- optAuth：6 个字段仅审批可写（创建 available_on_create=false，必填下沉到节点 field_perms）

