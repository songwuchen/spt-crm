# 图纸相关表单字段对照

## 0. 合同图纸对应表（图纸档案管理，非通用流程）

- **builtin key / code**: `contract_drawing_map`
- **路由**: `/contract-drawing-maps`
- **简道云**: app=`5b2af2c3a57134271be3717b` / entry=`5b2af2e131765151ee89230c`

| slug | 标签 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| pre_issue | 预下号 | radio(是/否) | 是 | 默认「否」 |
| apply_date | 日期时间 | date | 是 | 默认当天；参与编号日期段 |
| number_attr | 编号属性 | radio(WMGF/SY) | 是 | 默认 WMGF；分序列 |
| contract_no | 合同号 | text | 是 | |
| department | 业务部门 | department | | |
| drawing_no | 图纸编号 | auto_number | | WMGF+yyyyMM+3位月序 / SY+yy+3位年序；填报页 peek 预览 |
| remark | 备注 | textarea | | |

编号示例：`WMGF202608018`、`SY26001`。合同登记「编号查询」从此表带出合同号/图纸编号/业务部门。

---

# 图纸通用流程表单字段对照

> 状态：**已从简道云 live 拉取并对齐 CRM builtin**（app=`5e6c73fefc53170006bd4e9c`）。
> entry：领用 `5e6ee08be3051400062159ee` / 安装图 `5e6edc5b44b7070006d191cb`。
>
> **必填 / 显隐规则**来源：`_jdy_drawing_*_edit_raw.json` → `_jdy_drawing_forms_linkages.json`
> （`allowBlank===false`、`fieldShowRules`、`subformFieldShowRules`）。
> wrapper `GET /api/form/.../fields` 不含这些细节；生成器 `_gen_drawing_jdy.py` 合并进 builtin。

## 合同图纸（资料）领用申请

- **builtin key**: `drawing_requisition`
- **字段数（去噪后）**: 25
- **必填字段**: 9
- **规则**: 显隐 4 / 条件必填 3
- **流程节点数（CRM）**: 21 / 连线 30

| slug | 标签 | type | 必填 | jdy_widget |
|------|------|------|------|------------|
| apply_datetime | 日期时间 | datetime | 是 | `_widget_1584324747780` |
| department | 部门 | department | 是 | `_widget_1584324747793` |
| applicant | 申请人 | person | 是 | `_widget_1584324747817` |
| involve_std_drawing | 是否涉及企标图纸 | radio |  | `_widget_1712285733642` |
| order_person | 订货人 | person | 是 | `_widget_1670208477895` |
| order_person_text | 订货人（文本） | text |  | `_widget_1584324747971` |
| contract_no | 合同号 | select |  | `_widget_1584324747987` |
| apply_reason | 申请事由 | text | 是 | `_widget_1584324748032` |
| designer | 设计人 | person |  | `_widget_1625449621349` |
| designer_text | 设计人(文本) | text |  | `_widget_1584324748048` |
| product_model | 产品型号 | text |  | `_widget_1584324748064` |
| transfer_channel | 图纸传递途径 | radio | 是 | `_widget_1726128540953` |
| need_decrypt | 是否解密 | radio | 是 | `_widget_1584324748140` |
| need_decrypt_note | 是否解密* | text |  | `_widget_1744187653651` |
| paper_print_tip | 打印纸质图提醒 | text |  | `_widget_1750032665998` |
| drawing_type | 图纸类型 | radio | 是 | `_widget_1584324748225` |
| attachment_name | 附件/图片名称 | text | 是 | `_widget_1669617286395` |
| attachments | 附件 | file |  | `_widget_1584324748414` |
| images | 图片 | file |  | `_widget_1584324748427` |
| design_dispatch | 设计单分派 | radio |  | `_widget_1669426933010` |
| transfer_packaging_users | 转新乡、工艺包装 | person |  | `_widget_1669426933009` |
| design_assignees | 设计指派 | person |  | `_widget_1669426933008` |
| offices | 科室 | department |  | `_widget_1676005090837` |
| order_date | 下单日期 | datetime |  | `_widget_1676005090838` |
| need_gm_approval | 是否需要总经理审批 | radio |  | `_widget_1699839662506` |

### 显隐 / 条件必填规则

| id | type | target | condition |
|----|------|--------|-----------|
| `jdy_vis_design_assignees` | visibility | `design_assignees` | design_dispatch in ['总部单', '共同'] |
| `jdy_req_design_assignees` | required | `design_assignees` | design_dispatch in ['总部单', '共同'] |
| `jdy_vis_transfer_packaging_users` | visibility | `transfer_packaging_users` | design_dispatch in ['新乡单', '郑州单', '共同', '包装单'] |
| `jdy_req_transfer_packaging_users` | required | `transfer_packaging_users` | design_dispatch in ['新乡单', '郑州单', '共同', '包装单'] |
| `jdy_vis_need_decrypt` | visibility | `need_decrypt` | transfer_channel ne '图纸数据管理（查图机）' |
| `jdy_req_need_decrypt` | required | `need_decrypt` | transfer_channel ne '图纸数据管理（查图机）' |
| `jdy_vis_paper_print_tip` | visibility | `paper_print_tip` | transfer_channel in ['打印纸质图'] |

### 流程降级备注

- 审批「总工审批」具名用户 02364335378133，无匹配用户时 auto_approve
- 审批「研究院安排」具名用户 013807685436426800，无匹配用户时 auto_approve
- CC「抄送节点」绑定具名用户 ['02364335378133', '02336214315748']，CRM 无对应用户时 empty→auto_approve 不适用 CC，可能跳过
- CC「抄送李兴玉」绑定具名用户 02365312411349，CRM 无对应用户时 empty→auto_approve 不适用 CC，可能跳过
- CC「抄送王东明」绑定具名用户 02365310056917，CRM 无对应用户时 empty→auto_approve 不适用 CC，可能跳过
- CC「抄送周彦立」绑定具名用户 02365625057413，CRM 无对应用户时 empty→auto_approve 不适用 CC，可能跳过
- CC「抄送刘松潮」绑定具名用户 01142154504565，CRM 无对应用户时 empty→auto_approve 不适用 CC，可能跳过
- CC「抄送樊磊」绑定具名用户 0236562418583，CRM 无对应用户时 empty→auto_approve 不适用 CC，可能跳过
- 审批「市场支持中心」具名用户 023641581817，无匹配用户时 auto_approve
- 审批「总经理审批」具名用户 02336214315748，无匹配用户时 auto_approve
- 审批「企标委审批」具名用户 0236420233847，无匹配用户时 auto_approve
- 审批「工艺包装」具名用户 02365223402283，无匹配用户时 auto_approve
- 节点「抄送订货人」无出边（抄送旁路，不接到结束）
- 节点「抄送节点」无出边（抄送旁路，不接到结束）
- 节点「抄送李兴玉」无出边（抄送旁路，不接到结束）
- 节点「抄送王东明」无出边（抄送旁路，不接到结束）
- 节点「抄送周彦立」无出边（抄送旁路，不接到结束）
- 节点「抄送刘松潮」无出边（抄送旁路，不接到结束）
- 节点「抄送樊磊」无出边（抄送旁路，不接到结束）
- 节点「抄送组长」无出边（抄送旁路，不接到结束）
- optAuth：6 个字段仅审批可写（创建 available_on_create=false，必填下沉到节点 field_perms）

## 安装图设计通知

- **builtin key**: `install_drawing_notice`
- **字段数（去噪后）**: 51
- **必填字段**: 20（含子表列 11）
- **规则**: 显隐 29 / 条件必填 16
- **流程节点数（CRM）**: 21 / 连线 27

| slug | 标签 | type | 必填 | jdy_widget |
|------|------|------|------|------------|
| apply_datetime | 日期时间 | datetime |  | `_widget_1584323675993` |
| is_new_project | 是否为新项目0816 | radio | 是 | `_widget_1723596746484` |
| project_no | 项目号选择 | select | 是 | `_widget_1723598024203` |
| sales_person | 业务员 | person |  | `_widget_1723703918992` |
| customer_name | 公司名称 | text |  | `_widget_1723703918990` |
| matter | 事项 | text |  | `_widget_1723703918991` |
| applicant | 申请人 | person |  | `_widget_1584323676049` |
| department | 部门 | department |  | `_widget_1584323676006` |
| order_person | 订货人 | person | 是 | `_widget_1624943050844` |
| order_person_text | 订货人（文本） | text |  | `_widget_1584323676189` |
| dept_code | 部门编号 | text |  | `_widget_1697272822537` |
| is_xiaomeng | 是否小萌方案 | radio | 是 | `_widget_1662702145763` |
| design_card_no | 新设计卡号 | text |  | `_widget_1697272822538` |
| drawing_issue_type | 下图类型 | radio | 是 | `_widget_1624352911105` |
| drawing_types | 图纸类型（可多选） | checkbox | 是 | `_widget_1622075095219` |
| need_decrypt | 是否解密 | radio | 是 | `_widget_1584323676350` |
| pickup_purpose | 领图目的 | radio | 是 | `_widget_1669604747098` |
| apply_or_change | 申请事由/修改事项 | text |  | `_widget_1584323676275` |
| apply_reason_star | *申请事由 | text | 是 | `_widget_1662702831365` |
| biz_feedback | 业务反馈240416 | radio |  | `_widget_1713252188931` |
| lose_bid_reason | 落标原因240416 | text |  | `_widget_1713252188933` |
| card_date | 下卡日期 | datetime |  | `_widget_1624352039272` |
| pre_designers | 前期沟通设计人员 | person |  | `_widget_1624352911480` |
| require_draw_date | 要求交图时间 | datetime |  | `_widget_1624352911499` |
| product_model | 产品型号 | text |  | `_widget_1584323676307` |
| pre_designer_text | 前期沟通的设计员（文本） | text |  | `_widget_1584323676291` |
| scheme_detail | 出方案图填写明细 | detail_table | 是 | `_widget_1624352909418` |
| └ equipment_name | 设备名称 | text |  | `_widget_1624352909435` |
| └ design_req | 设计要求 | text |  | `_widget_1624352909494` |
| └ has_attach_or_rev | 是否有附件/修改图 | radio |  | `_widget_1624352909611` |
| └ drawing_qty | 图纸数量 | text |  | `_widget_1624352909986` |
| └ need_pricing | 是否核价 | radio |  | `_widget_1624352910183` |
| install_env | 安装环境和现场条件 | detail_table | 是 | `_widget_1624434803711` |
| └ altitude_m | 海拔高度（m) | text |  | `_widget_1624434803728` |
| └ env_temp_c | 环境温度­°C（最高/最低） | text |  | `_widget_1624434803793` |
| └ atm_pressure_kp | 大气压力KP | text |  | `_widget_1624434804053` |
| └ power_supply_v | 供电电源V | text |  | `_widget_1624434804260` |
| └ explosion_zone | 防爆区域 | radio |  | `_widget_1624434804437` |
| └ process_position | 工艺位置 | text | 是 | `_widget_1624434804752` |
| install_position | 安装位置 | radio | 是 | `_widget_1624352910598` |
| foundation_drawing | 设备基础图纸 | radio | 是 | `_widget_1624352910630` |
| install_method | 安装方式 | radio | 是 | `_widget_1624352910614` |
| change_scheme | 修改方案 | detail_table |  | `_widget_1624352911556` |
| └ change_equipment_name | 需要修改的设备名称 | text |  | `_widget_1624352911573` |
| └ change_part | 修改部位 | text |  | `_widget_1624352911656` |
| └ change_reason | 修改原因 | text |  | `_widget_1624352911741` |
| └ pre_designers_2 | 前期沟通设计人员 | person |  | `_widget_1624583924385` |
| scheme_material | 出方案图填写明细-物料特性 | detail_table |  | `_widget_1624352910323` |
| └ industry_star | 行业* | select | 是 | `_widget_1670209699036` |
| └ industry | 行业 | text |  | `_widget_1624505906027` |
| └ material_names | 物料名称（可多选） | checkbox | 是 | `_widget_1685081858434` |
| └ material_name | 物料名称 | text |  | `_widget_1624352910340` |
| └ bulk_density_star | *堆密度（kg/m³) | text | 是 | `_widget_1670209699039` |
| └ bulk_density | 堆密度（kg/m³) | text |  | `_widget_1624434805021` |
| └ temp_c | 温度­°C | text |  | `_widget_1624434805300` |
| └ mesh_size_star | 筛孔尺寸mm* | text | 是 | `_widget_1685081858184` |
| └ mesh_size | 筛孔尺寸mm | text |  | `_widget_1624434805496` |
| └ throughput_star | *处理量(t/h) | text | 是 | `_widget_1670209699040` |
| └ throughput | 处理量(t/h) | text |  | `_widget_1624352910498` |
| └ feed_size_star | *入料粒度 | text | 是 | `_widget_1670209699041` |
| └ feed_size | 入料粒度 | text |  | `_widget_1629079817970` |
| └ need_screening_eff_star | *筛分效率是否有要求 | radio | 是 | `_widget_1670312768934` |
| └ need_screening_eff | 筛分效率是否有要求 | text |  | `_widget_1624434806187` |
| └ particle_dist_star | *粒度分布 | text | 是 | `_widget_1670209699042` |
| └ particle_dist | 粒度分布 | text |  | `_widget_1624352910389` |
| └ screening_eff_star | *筛分效率 | text | 是 | `_widget_1670209699043` |
| └ screening_eff | 筛分效率 | text |  | `_widget_1625038769012` |
| └ moisture_star | *水分含量% | text | 是 | `_widget_1670209699044` |
| └ moisture | 水分含量% | text |  | `_widget_1624434805419` |
| └ particle_composition | 粒度组成 | text |  | `_widget_1624434806260` |
| non_scheme_material | 非出方案图填写明细-物料特性 | detail_table |  | `_widget_1670207254643` |
| └ industry_2 | 行业 | select |  | `_widget_1670207254644` |
| └ material_name_2 | 物料名称 | text |  | `_widget_1670207254645` |
| └ bulk_density_2 | 堆密度（kg/m³) | text |  | `_widget_1670207254646` |
| └ temp_c_2 | 温度­°C | text |  | `_widget_1670207254647` |
| └ mesh_size_2 | 筛孔尺寸mm | text |  | `_widget_1670207254648` |
| └ throughput_2 | 处理量(t/h) | text |  | `_widget_1670207254649` |
| └ feed_size_2 | 入料粒度 | text |  | `_widget_1670207254650` |
| └ need_screening_eff_2 | 筛分效率是否有要求 | radio |  | `_widget_1670207254651` |
| └ particle_dist_2 | 粒度分布 | text |  | `_widget_1670207254652` |
| └ screening_eff_2 | 筛分效率 | text |  | `_widget_1670207254653` |
| └ moisture_2 | 水分含量% | text |  | `_widget_1670207254654` |
| └ particle_composition_2 | 粒度组成 | text |  | `_widget_1670207254655` |
| attention | 注意 | text |  | `_widget_1679722777387` |
| attachment_names | 附件名称 | textarea | 是 | `_widget_1586759251628` |
| design_dispatch | 设计单分派 | radio |  | `_widget_1668992972400` |
| transfer_packaging_users | 转新乡、工艺包装 | person |  | `_widget_1668992972425` |
| design_assignees | 设计指派 | person |  | `_widget_1584415118691` |
| need_submit_drawing | 是否上交图纸 | radio | 是 | `_widget_1674957454888` |
| offices_multi | 科室多选 | department |  | `_widget_1676007312737` |
| order_date | 下单日期 | datetime |  | `_widget_1676007312736` |
| transfer_sw_lwt | 转孙伟、刘万涛 | person |  | `_widget_1662703176057` |
| attachments_no_image | 附件（不能放图片） | file |  | `_widget_1584348631246` |
| images | 图片 | file |  | `_widget_1584348816654` |
| score_attitude | 态度分数 | number | 是 | `_widget_1676601972672` |
| score_progress | 进度、准确性分数 | number | 是 | `_widget_1676601972673` |
| score_skill | 专业技能分数 | number | 是 | `_widget_1676601972674` |
| remark | 备注 | textarea | 是 | `_widget_1676601353553` |
| score_total | 总分 | number |  | `_widget_1676601972702` |
| score_date | 打分日期 | datetime |  | `_widget_1677119447744` |

### 显隐 / 条件必填规则

| id | type | target | condition |
|----|------|--------|-----------|
| `jdy_vis_scheme_detail` | visibility | `scheme_detail` | drawing_issue_type in ['出方案图'] |
| `jdy_req_scheme_detail` | required | `scheme_detail` | drawing_issue_type in ['出方案图'] |
| `jdy_vis_install_env` | visibility | `install_env` | drawing_issue_type in ['出方案图'] |
| `jdy_req_install_env` | required | `install_env` | drawing_issue_type in ['出方案图'] |
| `jdy_vis_install_position` | visibility | `install_position` | drawing_issue_type in ['出方案图'] |
| `jdy_req_install_position` | required | `install_position` | drawing_issue_type in ['出方案图'] |
| `jdy_vis_foundation_drawing` | visibility | `foundation_drawing` | drawing_issue_type in ['出方案图'] |
| `jdy_req_foundation_drawing` | required | `foundation_drawing` | drawing_issue_type in ['出方案图'] |
| `jdy_vis_install_method` | visibility | `install_method` | drawing_issue_type in ['出方案图'] |
| `jdy_req_install_method` | required | `install_method` | drawing_issue_type in ['出方案图'] |
| `jdy_vis_scheme_material` | visibility | `scheme_material` | drawing_issue_type in ['出方案图'] |
| `jdy_vis_biz_feedback` | visibility | `biz_feedback` | (OR drawing_issue_type in ['出方案图']; drawing_issue_type eq '领图') |
| `jdy_req_biz_feedback` | required | `biz_feedback` | (OR drawing_issue_type in ['出方案图']; drawing_issue_type eq '领图') |
| `jdy_vis_drawing_types` | visibility | `drawing_types` | drawing_issue_type eq '领图' |
| `jdy_req_drawing_types` | required | `drawing_types` | drawing_issue_type eq '领图' |
| `jdy_vis_need_decrypt` | visibility | `need_decrypt` | drawing_issue_type eq '领图' |
| `jdy_req_need_decrypt` | required | `need_decrypt` | drawing_issue_type eq '领图' |
| `jdy_vis_require_draw_date` | visibility | `require_draw_date` | drawing_issue_type in ['出方案图', '出测绘图', '修改方案'] |
| `jdy_vis_product_model` | visibility | `product_model` | drawing_issue_type in ['出方案图', '出测绘图', '修改方案'] |
| `jdy_vis_non_scheme_material` | visibility | `non_scheme_material` | drawing_issue_type in ['领图', '出测绘图'] |
| `jdy_vis_attachment_names` | visibility | `attachment_names` | is_xiaomeng in ['否'] |
| `jdy_req_attachment_names` | required | `attachment_names` | is_xiaomeng in ['否'] |
| `jdy_vis_pre_designers` | visibility | `pre_designers` | is_xiaomeng in ['否'] |
| `jdy_vis_apply_or_change` | visibility | `apply_or_change` | is_xiaomeng in ['否'] |
| `jdy_vis_apply_reason_star` | visibility | `apply_reason_star` | is_xiaomeng eq '是' |
| `jdy_req_apply_reason_star` | required | `apply_reason_star` | is_xiaomeng eq '是' |
| `jdy_vis_transfer_packaging_users` | visibility | `transfer_packaging_users` | design_dispatch in ['新乡单', '郑州单', '共同', '包装单'] |
| `jdy_req_transfer_packaging_users` | required | `transfer_packaging_users` | design_dispatch in ['新乡单', '郑州单', '共同', '包装单'] |
| `jdy_vis_design_assignees` | visibility | `design_assignees` | design_dispatch in ['总部单', '共同'] |
| `jdy_req_design_assignees` | required | `design_assignees` | design_dispatch in ['总部单', '共同'] |
| `jdy_vis_lose_bid_reason` | visibility | `lose_bid_reason` | biz_feedback eq '落标' |
| `jdy_req_lose_bid_reason` | required | `lose_bid_reason` | biz_feedback eq '落标' |
| `jdy_vis_moisture` | visibility | `moisture` | need_screening_eff eq '是' |
| `jdy_vis_screening_eff` | visibility | `screening_eff` | need_screening_eff eq '是' |
| `jdy_vis_particle_dist` | visibility | `particle_dist` | need_screening_eff eq '是' |
| `jdy_vis_particle_dist_star` | visibility | `particle_dist_star` | need_screening_eff eq '是' |
| `jdy_req_particle_dist_star` | required | `particle_dist_star` | need_screening_eff eq '是' |
| `jdy_vis_screening_eff_star` | visibility | `screening_eff_star` | need_screening_eff eq '是' |
| `jdy_req_screening_eff_star` | required | `screening_eff_star` | need_screening_eff eq '是' |
| `jdy_vis_moisture_star` | visibility | `moisture_star` | need_screening_eff eq '是' |
| `jdy_req_moisture_star` | required | `moisture_star` | need_screening_eff eq '是' |
| `jdy_vis_moisture_2` | visibility | `moisture_2` | need_screening_eff_2 eq '是' |
| `jdy_vis_screening_eff_2` | visibility | `screening_eff_2` | need_screening_eff_2 eq '是' |
| `jdy_vis_particle_composition_2` | visibility | `particle_composition_2` | need_screening_eff_2 eq '是' |
| `jdy_vis_particle_dist_2` | visibility | `particle_dist_2` | need_screening_eff_2 eq '是' |

### 流程降级备注

- 审批「设计指派安排」具名用户 013807685436426800，无匹配用户时 auto_approve
- 审批「总工审批」具名用户 02364335378133，无匹配用户时 auto_approve
- 审批「周经理审批」具名用户 01210720669288，无匹配用户时 auto_approve
- 审批「市场支持中心」具名用户 023641581817，无匹配用户时 auto_approve
- CC「抄送总经理」绑定具名用户 02336214315748，CRM 无对应用户时 empty→auto_approve 不适用 CC，可能跳过
- CC「抄送王东明」绑定具名用户 02365310056917，CRM 无对应用户时 empty→auto_approve 不适用 CC，可能跳过
- CC「抄送李兴玉」绑定具名用户 02365312411349，CRM 无对应用户时 empty→auto_approve 不适用 CC，可能跳过
- CC「抄送刘松潮」绑定具名用户 01142154504565，CRM 无对应用户时 empty→auto_approve 不适用 CC，可能跳过
- CC「抄送樊磊」绑定具名用户 0236562418583，CRM 无对应用户时 empty→auto_approve 不适用 CC，可能跳过
- 审批「工艺包装」具名用户 02365223402283，无匹配用户时 auto_approve
- 节点「抄送设计指派1」无出边（抄送旁路，不接到结束）
- 节点「抄送订货人」无出边（抄送旁路，不接到结束）
- 节点「抄送总经理」无出边（抄送旁路，不接到结束）
- 节点「抄送设计指派2」无出边（抄送旁路，不接到结束）
- 节点「抄送王东明」无出边（抄送旁路，不接到结束）
- 节点「抄送组长」无出边（抄送旁路，不接到结束）
- 节点「抄送李兴玉」无出边（抄送旁路，不接到结束）
- 节点「抄送刘松潮」无出边（抄送旁路，不接到结束）
- 节点「抄送樊磊」无出边（抄送旁路，不接到结束）
- optAuth：8 个字段仅审批可写（创建 available_on_create=false，必填下沉到节点 field_perms）

