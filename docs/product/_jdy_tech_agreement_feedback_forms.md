# 技术协议反馈单 — CRM 字段对照

> 简道云 app=`584658417562f37a227fa805` entry=`5e707cbf45da660006ec37c7`

- **builtin key**: `tech_agreement_feedback`
- **路由**: `/tech-agreement-feedbacks`
- **字段数（去噪后）**: 18
- **静态必填**: 8
- **流程节点数（CRM）**: 15 / 连线 16
- **联动规则**: 4

| slug | 标签 | type | 必填 | jdy_widget |
|------|------|------|------|------------|
| serial_no | 流水号 | auto_number |  | `_widget_1679289179293` |
| apply_datetime | 日期时间 | datetime |  | `_widget_1679289179304` |
| applicant | 申请人 | person |  | `_widget_1584427607939` |
| office | 科室 | department |  | `_widget_1679723953371` |
| contract_no | 合同号 | contract | 是 | `_widget_1584427608063` |
| order_person | 订货人 | person | 是 | `_widget_1584427608079` |
| department | 所属部门 | department | 是 | `_widget_1585192885954` |
| design_reviewer | 设计审核人 | person | 是 | `_widget_1585378012012` |
| notify_purchase | 是否通知采购 | radio | 是 | `_widget_1633478604038` |
| design_dispatch | 设计单分派 | radio | 是 | `_widget_1679290627717` |
| transfer_rd_centers | 转新乡、郑州研发中心 | person_multi |  | `_widget_1679290627721` |
| dept_clerk | 部门内勤 | person | 是 | `_widget_1584430285733` |
| salesperson | 业务员 | person |  | `_widget_1679301680440` |
| agreement_content | 协议内容 | textarea | 是 | `_widget_1584427608200` |
| business_feedback | 业务反馈 | textarea |  | `_widget_1679303185547` |
| feedback_suggestion | 反馈建议 | textarea |  | `_widget_1584430284641` |
| attachments | 附件 | file |  | `_widget_1584430284601` |
| images | 图片 | file |  | `_widget_1584430284614` |

### 流程备注

- 简道云 workflow_config 未取到（中央研究院 app 未接入 data-hub）；按流程设计实单重建 CRM 拓扑。
- 发起抄业务员 → 设计审核 → 总工意见 ∥ 内勤安排 → 内勤核查 → （业务员空/非空）→ 财务核算 → 部门意见 → 总经理审批 → 通知抄送。

