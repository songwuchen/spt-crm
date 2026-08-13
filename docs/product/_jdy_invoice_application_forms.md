# 开票申请 — CRM 字段对照

> 简道云 app=`56ca77ce1efc301d279b8a4d` entry=`5dd34ddf26aecf000655a354`

- **builtin key**: `invoice_application`
- **路由**: `/invoice-applications`
- **字段数（去噪后）**: 22
- **必填字段**: 3
- **流程节点数（CRM）**: 5 / 连线 4

| slug | 标签 | type | 必填 | jdy_widget |
|------|------|------|------|------------|
| serial_no | 流水号 | text |  | `_widget_1597214853301` |
| apply_date | 申请日期 | datetime | 是 | `_widget_1574129454620` |
| department | 所在部门 | department | 是 | `_widget_1577350546209` |
| drawing_no_select | 选择图纸编号 | text |  | `_widget_1697444647116` |
| drawing_no | 图纸编号 | text |  | `_widget_1574129454682` |
| customer_name | 单位名称 | text |  | `_widget_1574129454712` |
| dept_contract_no | 部门合同号240222增 | text |  | `_widget_1708572834892` |
| customer_no | 客户编号 | text |  | `_widget_1693447273150` |
| sales_person | 业务员 | person | 是 | `_widget_1596699346316` |
| contract_data | 合同数据 | text |  | `_widget_1676943123926` |
| contract_lines_new | 合同明细（新增） | detail_table |  | `_widget_1576574684319` |
| └ product_name | 产品名称 | text |  | `_widget_1576574684342` |
| └ spec_model | 规格型号 | text |  | `_widget_1576574684370` |
| └ unit | 单位 | text |  | `_widget_1576574684418` |
| └ qty | 数量 | number |  | `_widget_1576574684355` |
| └ unit_price | 单价 | number |  | `_widget_1576574684458` |
| └ line_amount | 合计 | number |  | `_widget_1589784473386` |
| total_amount | 总价合计 | number |  | `_widget_1576574684565` |
| total_amount_adjusted | 总价合计（调整后）* | number |  | `_widget_1668647796154` |
| customer_code | 客户编码 | text |  | `_widget_1576648200954` |
| invoice_datetime | 开票时间 | datetime |  | `_widget_1574130671470` |
| invoice_special_req | 开票特殊要求 | text |  | `_widget_1574130671454` |
| invoice_no | 发票号码 | text |  | `_widget_1594256425821` |
| remark | 备注 | text |  | `_widget_1676096052376` |
| invoice_email | 接收发票邮箱地址 | text |  | `_widget_1689932068658` |
| attachments | 附件 | file |  | `_widget_1574130671538` |
| images | 图片 | file |  | `_widget_1619053367909` |

### 流程降级备注

- 审批「开票」具名用户 442558535226341870，无匹配用户时 auto_approve
- CC「北京小萌抄送」绑定具名用户 02364313303546，CRM 无对应用户时 empty→auto_approve 不适用 CC，可能跳过
- 节点「北京小萌抄送」无出边（抄送旁路，不接到结束）
- optAuth：4 个字段仅审批可写（创建 available_on_create=false，必填下沉到节点 field_perms）
- CRM：`drawing_no_select` 改为合同选择；选中后带出图纸号/单位/业务员/开票信息/合同明细；已去掉无用「合同明细（变动）」

