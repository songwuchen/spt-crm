# 核价清单传递流程HJQD

> 菜单：`中央研究院 / 研究院统计 / 核价清单 / 核价清单传递流程HJQD`
> 简道云 app=`584658417562f37a227fa805` entry=`667638539c1f73c42e4bcbff`
> CRM builtin code: **`pricing_checklist_hjqd`**，路由：`/pricing-checklists`
> 流水号：`HJQD-` + `yyyyMMdd` + 5 位不重置
> 流程节点数: **7**；扁平字段: **47**（CRM 落地 41，去掉系统字段/分割线）。

## CRM 落地

- 生成器：`backend/scripts/_gen_pricing_checklist_hjqd_jdy.py`
- 生成包：`backend/app/domains/lowcode/_pricing_checklist_hjqd_generated.py`
- 审批流：`SYS_PRICING_CHECKLIST_HJQD`（发起 → 财务张光 → 按流程名称条件抄送对应申请人；抄送旁路）
- 财务节点可填：`has_issue` / `issue_details`
- 关联表单 linkfield 暂为文本（对齐其它 JDY 表单落地惯例）；按「流程名称」显隐关联块

## 产出文件

- `_jdy_pricing_checklist_hjqd_fields.json` — 字段原始
- `_jdy_pricing_checklist_hjqd_fields_flat.json` — 扁平字段
- `_jdy_pricing_checklist_hjqd_workflows_raw.json` — 流程/配置原始
- `_jdy_pricing_checklist_hjqd_flow_nodes.md` — 流程节点摘要
- `_jdy_pricing_checklist_hjqd_edit_raw.json` — 表单 edit 原始（已去密钥字段）

## 字段一览

| name | title | type | required | parent |
|------|-------|------|----------|--------|
| `_widget_1719023699757` | 流水号 | sn |  | `` |
| `_widget_1719023699758` | 流程名称* | radiogroup |  | `` |
| `_widget_1719023699776` | 选择安装图设计通知数据 | linkfield |  | `` |
| `_widget_1719023699779` | 流水号-安装图设计通知 | text |  | `` |
| `_widget_1719023699783` | 新设计卡号-安装图设计通知 | text |  | `` |
| `_widget_1719023699781` | 订货人（文本）-安装图设计通知 | text |  | `` |
| `_widget_1719023699780` | 申请人-安装图设计通知 | user |  | `` |
| `_widget_1719023699782` | 部门-安装图设计通知 | dept |  | `` |
| `_widget_1719023699789` | 选择合同图纸(资料)领用申请数据 | linkfield |  | `` |
| `_widget_1719023699791` | 流水号-合同图纸(资料)领用申请 | text |  | `` |
| `_widget_1719023699795` | 合同号-合同图纸(资料)领用申请 | text |  | `` |
| `_widget_1719023699793` | 申请人-合同图纸(资料)领用申请 | user |  | `` |
| `_widget_1719023699794` | 订货人（文本）-合同图纸(资料)领用申请 | text |  | `` |
| `_widget_1719023699792` | 部门-合同图纸(资料)领用申请 | dept |  | `` |
| `_widget_1719023699808` | 选择客服领图数据 | linkfield |  | `` |
| `_widget_1719035409175` | 流水号-客服领图 | text |  | `` |
| `_widget_1719035409178` | 合同号-客服领图 | text |  | `` |
| `_widget_1719035409180` | 订货人（文本）-客服领图 | text |  | `` |
| `_widget_1719035409177` | 申请人-客服领图 | user |  | `` |
| `_widget_1719035409176` | 部门-客服领图 | dept |  | `` |
| `_widget_1719023699807` | 选择中央研究院协同卡数据 | linkfield |  | `` |
| `_widget_1719035409184` | 流水号-中央研究院协同卡 | text |  | `` |
| `_widget_1719035409185` | 合同号-中央研究院协同卡 | text |  | `` |
| `_widget_1719035409187` | 订货人（文本）-中央研究院协同卡 | user |  | `` |
| `_widget_1719035409188` | 申请人-中央研究院协同卡 | user |  | `` |
| `_widget_1719035409186` | 订货部门-中央研究院协同卡 | dept |  | `` |
| `_widget_1719023699761` | 流水号 | text |  | `` |
| `_widget_1719023699760` | 对应设计卡号 | text |  | `` |
| `_widget_1719023699774` | 合同号 | text |  | `` |
| `_widget_1719023699762` | 订货人 | text |  | `` |
| `_widget_1719023699763` | 申请人 | text |  | `` |
| `_widget_1719035409198` | 业务部门 | text |  | `` |
| `_widget_1719044595812` | 分割线 | separator |  | `` |
| `_widget_1719023699765` | 设计员 | user |  | `` |
| `_widget_1719023699764` | 科室 | dept |  | `` |
| `_widget_1719023699766` | 日期时间 | datetime |  | `` |
| `_widget_1719023699767` | 核价单数量 | number |  | `` |
| `_widget_1719023699769` | 图片 | image |  | `` |
| `_widget_1719023699771` | 附件 | upload |  | `` |
| `_widget_1719023699773` | 备注 | text |  | `` |
| `_widget_1725840520052` | 核价清单是否有问题0909 | radiogroup |  | `` |
| `_widget_1725840520070` | 问题类型和具体问题明细0909 | subform |  | `` |
| `_widget_1725840520072` | 问题类型 | text |  | `_widget_1725840520070` |
| `_widget_1725840520073` | 具体问题 | text |  | `_widget_1725840520070` |
| `creator` | 提交人 | user |  | `` |
| `createTime` | 提交时间 | datetime |  | `` |
| `updateTime` | 更新时间 | datetime |  | `` |
