# 客服领图 — CRM 字段对照

> 简道云 app=`58e2fbc7ffd1608b4ce92809` entry=`63840316a3241c000a805869`

- **builtin key**: `cs_drawing_request`
- **路由**: `/cs-drawing-requests`
- **字段数**: 21（发起必填 9；明细列必填 0）
- **流程节点**: 16 / 连线 18
- **流水号前缀**: ``
- **必填来源**: `_jdy_customer_service_linkages.json`（edit allowBlank=false）

| slug | 标签 | type | 必填 | 创建可填 | stage | jdy_widget |
|------|------|------|------|----------|-------|------------|
| serial_no | 流水号 | auto_number |  | 是 | initiator | `_widget_1584423635442` |
| apply_datetime | 日期时间 | datetime | 是 | 是 | initiator | `_widget_1584324747780` |
| department | 部门 | department | 是 | 是 | initiator | `_widget_1584324747793` |
| applicant | 申请人 | person | 是 | 是 | initiator | `_widget_1584324747817` |
| contract_no | 合同号 | contract | 是 | 是 | initiator | `_widget_1584324747987` |
| drawing_no_note | 图号231021 | text | 是 | 是 | initiator | `_widget_1697850315211` |
| order_person | 订货人 | person | 是 | 是 | initiator | `_widget_1669604044008` |
| apply_reason | 申请事由* | text |  |  | approver | `_widget_1584324748032` |
| apply_reason_2 | 申请事由 | textarea | 是 | 是 | initiator | `_widget_1669620743951` |
| designer | 设计人 | person |  | 是 | initiator | `_widget_1625449621349` |
| product_model | 产品型号 | text |  | 是 | initiator | `_widget_1584324748064` |
| transfer_channel | 图纸传递途径 | radio | 是 | 是 | initiator | `_widget_1726128717250` |
| attachment_name | 附件名称 | text | 是 | 是 | initiator | `_widget_1669614721963` |
| images | 图片 | image |  | 是 | initiator | `_widget_1669702693339` |
| attachments | 附件 | file |  | 是 | initiator | `_widget_1584324748414` |
| dept_dispatch | 部门指派 | radio |  | 是 | initiator | `_widget_1765346720634` |
| design_dispatch | 设计单分派 | radio |  |  | approver | `_widget_1669426933010` |
| transfer_packaging_users | 转新乡、工艺包装 | person_multi |  |  | approver | `_widget_1669426933009` |
| design_assignees | 设计指派 | person_multi |  |  | approver | `_widget_1669426933008` |
| offices | 科室 | department_multi |  |  | approver | `_widget_1676005046207` |
| order_date | 下单时间 | datetime |  |  | approver | `_widget_1676005046206` |

### 流程降级备注

- 审批「部门指派-研管办」JDY 角色「27.3图纸领用申请-研究院安排」仅郑志颖 → 指定用户 `013807685436426800`
- CC「抄送客服部长」绑定具名用户 02364335378133，CRM 无对应用户时 empty→auto_approve 不适用 CC，可能跳过
- CC「抄送节点」绑定具名用户 02364335378133，CRM 无对应用户时 empty→auto_approve 不适用 CC，可能跳过
- CC「抄送李兴玉」绑定具名用户 02365312411349，CRM 无对应用户时 empty→auto_approve 不适用 CC，可能跳过
- CC「抄送王东明」绑定具名用户 02365310056917，CRM 无对应用户时 empty→auto_approve 不适用 CC，可能跳过
- CC「抄送周彦立」绑定具名用户 02365625057413，CRM 无对应用户时 empty→auto_approve 不适用 CC，可能跳过
- CC「抄送刘松潮」绑定具名用户 01142154504565，CRM 无对应用户时 empty→auto_approve 不适用 CC，可能跳过
- CC「抄送樊磊」绑定具名用户 0236562418583，CRM 无对应用户时 empty→auto_approve 不适用 CC，可能跳过
- 审批「工艺包装」具名用户 02365223402283，无匹配用户时 auto_approve
- 审批「部门指派-孙伟」具名用户 02391125207699，无匹配用户时 auto_approve
- 审批「物料编码」具名用户 02364636608946，无匹配用户时 auto_approve
- 节点「start」2 条出边已标互斥组 ex_start
- 节点「n5」3 条出边已标互斥组 ex_n5（含工艺包装优先）
- 节点「抄送客服部长」无出边（抄送旁路，不接到结束）
- 节点「抄送节点」无出边（抄送旁路，不接到结束）
- 节点「抄送李兴玉」无出边（抄送旁路，不接到结束）
- 节点「抄送王东明」无出边（抄送旁路，不接到结束）
- 节点「抄送周彦立」无出边（抄送旁路，不接到结束）
- 节点「抄送刘松潮」无出边（抄送旁路，不接到结束）
- 节点「抄送樊磊」无出边（抄送旁路，不接到结束）
- 节点「抄送组长」无出边（抄送旁路，不接到结束）
- optAuth：6 个字段仅审批可写（创建 available_on_create=false，必填下沉到节点 field_perms）
- optAuth：1 个字段发起仅可见（form_editable=false）
- edit_raw allowBlank=false：14 个必填 widget

