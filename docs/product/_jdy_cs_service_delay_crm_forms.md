# 客户服务延期申请 — CRM 字段对照

> 简道云 app=`58e2fbc7ffd1608b4ce92809` entry=`5f9b6dacb6ec680007f9c46f`

- **builtin key**: `cs_service_delay`
- **路由**: `/cs-service-delays`
- **字段数**: 10（发起必填 0；明细列必填 0）
- **流程节点**: 9 / 连线 8
- **流水号前缀**: `YQ`
- **必填来源**: `_jdy_customer_service_linkages.json`（edit allowBlank=false）

| slug | 标签 | type | 必填 | 创建可填 | stage | jdy_widget |
|------|------|------|------|----------|-------|------------|
| serial_no | 流程编号 | auto_number |  |  | initiator | `_widget_1604021830267` |
| contract_no | 合同号 | contract |  | 是 | initiator | `_widget_1585191665097` |
| sales_person | 业务员 | person |  | 是 | initiator | `_widget_1585191665061` |
| field | 所属部门 | department |  | 是 | initiator | `_widget_1585191665079` |
| field_2 | 设备信息 | detail_table |  | 是 | initiator | `_widget_1585191665113` |
| └ field_3 | 产品名称 | text |  | | | `_widget_1585191665125` |
| └ field_4 | 规格型号 | text |  | | | `_widget_1585191665148` |
| └ field_5 | 数量/单位 | text |  | | | `_widget_1585191665207` |
| field_6 | 服务公司 | text |  | 是 | initiator | `_widget_1585191665226` |
| field_7 | 服务事项 | text |  | 是 | initiator | `_widget_1585191665241` |
| field_8 | 延期至 | datetime |  | 是 | initiator | `_widget_1585191665258` |
| field_9 | 延期原因 | text |  | 是 | initiator | `_widget_1585191665284` |
| remark | 备注 | textarea |  | 是 | initiator | `_widget_1585191665301` |

### 流程降级备注

- 审批「部门经理」→ 表单人员「sales_person」所属部门负责人
- 审批「客服反馈」JDY 角色「7.5客户服务延期申请-客服反馈」降级为 sales_manager
- 审批「客服审批」JDY 角色「7.5客户服务延期申请-客服审批」降级为 sales_manager
- 审批「曹工审批」JDY 角色「曹修国」→ 指定用户 02364335378133
- 审批「总经理审批」JDY 角色「总经理」→ 指定用户 02336214315748
- 审批「客服备案」JDY 角色「7.5客户服务延期申请-客服反馈」降级为 sales_manager
- optAuth：1 个字段仅审批可写（创建 available_on_create=false，必填下沉到节点 field_perms）

