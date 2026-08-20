# 迅焊公司合同评审 — CRM 字段对照

> 简道云 app=`5de0b3e85600ec0006f420f2` entry=`67d3d515c8df85cc24de064f`（销售中心 / 合同）

- **builtin key**: `xunhan_contract_review`
- **路由**: `/xunhan-contract-reviews`
- **字段数（去噪后）**: 73
- **静态必填**: 8
- **流程节点数（CRM）**: 19 / 连线 25
- **联动规则**: 8
- **流水号**: `24.2.3` + yyyyMMdd + 五位月序

| slug | 标签 | type | 必填 | jdy_widget |
|------|------|------|------|------------|
| serial_no | 流水号 | auto_number |  | `_widget_1601273674993` |
| has_pricing | 是否核价 | radio | 是 | `_widget_1669597630356` |
| need_install | 是否需要安装 | radio | 是 | `_widget_1636957088887` |
| sales_person | 业务员 | person | 是 | `_widget_1574756606514` |
| department | 业务部门 | department | 是 | `_widget_1574756606496` |
| customer_name | 公司名称 | customer | 是 | `_widget_1712364068119` |
| is_foreign_trade | 是否外贸客户 | text |  | `_widget_1700446723223` |
| is_xiaomeng | 是否小萌 | radio |  | `_widget_1721093361440` |
| elec_control | 电控装置 | radio |  | `_widget_1723685156828` |
| pricing_pick | 选择27.7核价管理信息 | text |  | `_widget_1677810182290` |
| pricing_no | 核价单号 | text |  | `_widget_1669789398113` |
| cost_attachments | 成本附件250122 | file |  | `_widget_1737505642219` |
| cost_price | 成本价250122 | textarea |  | `_widget_1737505642376` |
| pricing_motor | 核价配置要求的电机 | text |  | `_widget_1669789398145` |
| pricing_bearing | 核价配置要求的轴承 | text |  | `_widget_1669789398148` |
| pricing_material | 核价配置要求的主材材质 | text |  | `_widget_1669789398149` |
| pricing_liner | 核价配置要求的衬板/筛板 | text |  | `_widget_1669789398151` |
| special_req | 特殊要求 | textarea |  | `_widget_1669789398152` |
| customer_type | 客户类型 | radio | 是 | `_widget_1552369403178` |
| contract_copies | 正式合同份数 | number |  | `_widget_1575620563294` |
| company_nature | 公司性质 | text |  | `_widget_1552369403180` |
| industry | 所属行业 | text |  | `_widget_1552369403182` |
| scale_fund | 规模及资金（万元） | number |  | `_widget_1571980668231` |
| customer_relation | 客户关系 | text |  | `_widget_1552369403185` |
| dishonesty_count | 失信信息 | number |  | `_widget_1574923502794` |
| lawsuit_count | 诉讼纠纷 | number |  | `_widget_1573546023205` |
| env_penalty_count | 环保处罚 | number |  | `_widget_1573546023251` |
| tax_penalty_count | 税务处罚 | number |  | `_widget_1573546023339` |
| other_penalty_count | 其它行政处罚 | number |  | `_widget_1573546023421` |
| contacts | 联系信息 | detail_table |  | `_widget_1666143568899` |
| └ contact_name | 联系人 | text |  | `_widget_1666143568901` |
| └ contact_leader | 上级领导 | text |  | `_widget_1666143568902` |
| └ contact_mobile | 手机号码 | text |  | `_widget_1666143568903` |
| └ contact_title | 职务 | text |  | `_widget_1666143568904` |
| └ email_or_request | 邮箱or请示 | radio |  | `_widget_1678428794483` |
| └ contact_email | 邮箱 | text |  | `_widget_1666143568905` |
| └ contact_request | 请示 | text |  | `_widget_1678428794562` |
| └ contact_address | 地址 | address |  | `_widget_1666143568906` |
| parent_company_desc | 母公司或控股公司的情况及性质说明 | text |  | `_widget_1574409968702` |
| project_name_app | 项目名称及应用 | textarea |  | `_widget_1552447447285` |
| salary_insurance | 工资及保险情况 | text |  | `_widget_1552369403186` |
| contract_price | 合同价格（元） | number | 是 | `_widget_1571965661951` |
| delivery_period | 交货期 | text |  | `_widget_1552369403191` |
| has_guarantee | 是否有保函 | radio | 是 | `_widget_1552445539881` |
| guarantee_type | 保函类型 | radio |  | `_widget_1552445539906` |
| has_weight_req | 是否有重量要求 | radio |  | `_widget_1616203849373` |
| use_idle_equipment | 是否趁用呆滞设备 | radio |  | `_widget_1601356599650` |
| has_smart_part | 合同是否含智能化部分 | radio |  | `_widget_1577784147558` |
| sign_basis | 合同签订依据及情况 | text |  | `_widget_1552445540017` |
| ref_contract_no | 参考合同号 | text |  | `_widget_1574409652548` |
| payment_method | 付款方式 | text |  | `_widget_1552435959889` |
| company_survey | 公司现状调查 | text |  | `_widget_1574150406585` |
| bid_status | 项目报备与投标情况 | text |  | `_widget_1574150406569` |
| sales_supplement | 针对销售情况的补充 | text |  | `_widget_1574150406601` |
| survey_req | 现场测绘及要求 | text |  | `_widget_1552453980743` |
| attachments | 附件 | file |  | `_widget_1574756606691` |
| images | 图片 | file |  | `_widget_1619053749212` |
| legal_clause_opinion | 合同条款审核意见 | textarea |  | `_widget_1574150406495` |
| legal_risk_level | 法务风险等级判断 | radio |  | `_widget_1736576180940` |
| legal_risk_desc | 法务风险等级文字描述 | text |  | `_widget_1736576180942` |
| tech_risk_level | 技术风险等级判断 | radio |  | `_widget_1736736740214` |
| tech_risk_desc | 技术风险等级文字描述 | text |  | `_widget_1736736740216` |
| biz_risk_level | 业务风险等级判断 | radio |  | `_widget_1736576180965` |
| biz_risk_desc | 业务风险等级文字描述 | text |  | `_widget_1736576180968` |
| finance_risk_level | 财务风险等级判断 | radio |  | `_widget_1736576180963` |
| finance_risk_desc | 财务风险等级文字描述 | text |  | `_widget_1736576180967` |
| purchase_risk_level | 采购风险等级判断 | radio |  | `_widget_1737505642531` |
| purchase_risk_desc | 采购风险等级文字描述 | text |  | `_widget_1737505641998` |
| export_risk_level | 出口风险等级判断 | radio |  | `_widget_1736576181070` |
| export_risk_desc | 出口风险等级文字描述 | text |  | `_widget_1736576181072` |
| credit_level | 重点数据及信用等级 | text |  | `_widget_1574150406737` |
| history_biz_desc | 前期业务来往描述 | text |  | `_widget_1574150406753` |
| pricing_quote_supplement | 核价报价补充 | text |  | `_widget_1574150406769` |
| payment_term | 账期 | text |  | `_widget_1733555512882` |
| conclusion_desc | 结论描述 | textarea |  | `_widget_1571965662023` |
| need_feedback | 是否反馈 | radio |  | `_widget_1571965662256` |
| feedback_members | 成员多选 | person_multi |  | `_widget_1577171437278` |
| feedback_attachments | 反馈附件 | file |  | `_widget_1577171437265` |
| feedback_images | 反馈图片 | file |  | `_widget_1619053749445` |
| drawing_no | 图纸编号 | text |  | `_widget_1673836407417` |
| review_opinion_exec | 合同评审意见执行情况 | textarea |  | `_widget_1675495250350` |

### 流程降级备注

- 对齐简道云销售中心「迅焊公司合同评审」；流水号 24.2.3+yyyyMMdd+五位月序。
- 简道云 fieldShowRules 13 条 → CRM 显隐 8 条。
- 审批「法务审批」JDY 角色「24.2.3合同/项目评审-法务审批多人」降级为 sales_manager
- 审批「总经理审批」具名用户 02336214315748，无匹配用户时 auto_approve
- 审批「财务意见」具名用户 0433406811775721，无匹配用户时 auto_approve
- 审批「设计审批」具名用户 02364335378133，无匹配用户时 auto_approve
- CC「抄送李莉」绑定具名用户 02364313303546，CRM 无对应用户时 empty→auto_approve 不适用 CC，可能跳过
- 审批「财务总监意见」具名用户 02362556584221，无匹配用户时 auto_approve
- 审批「生产审批」具名用户 01210720669288，无匹配用户时 auto_approve
- 审批「采购审批」具名用户 02352513566524，无匹配用户时 auto_approve
- 审批「质检审批」具名用户 0236420233847，无匹配用户时 auto_approve
- CC「抄送迅焊」绑定具名用户 01670210101135172，CRM 无对应用户时 empty→auto_approve 不适用 CC，可能跳过
- 审批「设计审批1」具名用户 02364335378133，无匹配用户时 auto_approve
- 审批「法务主管审批」具名用户 492105073721398323，无匹配用户时 auto_approve
- 节点「n1__2」2 条出边已标互斥组 ex_n1__2
- 节点「n6」5 条出边已标互斥组 ex_n6
- 节点「抄送相关人」无出边（抄送旁路，不接到结束）
- 节点「抄送业务员」无出边（抄送旁路，不接到结束）
- 节点「抄送李莉」无出边（抄送旁路，不接到结束）
- 节点「抄送迅焊」无出边（抄送旁路，不接到结束）
- optAuth：31 个字段仅审批可写（创建 available_on_create=false，必填下沉到节点 field_perms）
- optAuth：6 个字段发起仅可见（form_editable=false）

