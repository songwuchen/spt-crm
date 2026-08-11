# 客户服务申请及反馈（字段对照）

> 简道云 app=`58e2fbc7ffd1608b4ce92809` entry=`5e06c8a92675f1000634baf1`。CRM key=`cs_service_request`。
> 流程节点数: **21**；扁平字段: **55**。

| name | title | type | required | parent |
|------|-------|------|----------|--------|
| `_widget_1578287685594` | 流水号 | sn |  | `` |
| `_widget_1626769978165` | 离职人员 | text |  | `` |
| `_widget_1577494164593` | 所属部门 | dept |  | `` |
| `_widget_1577494164575` | 业务员 | user |  | `` |
| `_widget_1770083447770` | 业务员ID（辅助） | text |  | `` |
| `_widget_1770083447771` | 区域经理/组长 | user |  | `` |
| `_widget_1577494164611` | 客户名称 | combo |  | `` |
| `_widget_1684370183791` | 是否是小萌 | radiogroup |  | `` |
| `_widget_1577494164627` | 服务地点 | text |  | `` |
| `_widget_1577494164659` | 服务要求 | text |  | `` |
| `_widget_1577494164643` | 乘车路线及费用 | text |  | `` |
| `_widget_1577513844817` | 服务性质 | checkboxgroup |  | `` |
| `_widget_1578643639316` | 备注 | text |  | `` |
| `_widget_1646903018469` | 客户种类（取消多选） | checkboxgroup |  | `` |
| `_widget_1649229021346` | 客户种类 | radiogroup |  | `` |
| `_widget_1646903016596` | 紧急情况 | checkboxgroup |  | `` |
| `_widget_1577495431595` | 主要产品信息 | subform |  | `` |
| `_widget_1712128588465` | 有无合同号 | radiogroup |  | `_widget_1577495431595` |
| `_widget_1577495431618` | 合同号 | combo |  | `_widget_1577495431595` |
| `_widget_1578108364286` | 现场联系人及电话 | text |  | `_widget_1577495431595` |
| `_widget_1577495431631` | 设备名称 | text |  | `_widget_1577495431595` |
| `_widget_1577495431646` | 设备型号 | text |  | `_widget_1577495431595` |
| `_widget_1577495431703` | 数量 | number |  | `_widget_1577495431595` |
| `_widget_1578287341598` | 单位 | text |  | `_widget_1577495431595` |
| `_widget_1577495431722` | 发货日期 | datetime |  | `_widget_1577495431595` |
| `_widget_1577495432709` | 其它待排查产品 | combo |  | `` |
| `_widget_1577495432749` | 有其它排产产品明细 | subform |  | `` |
| `_widget_1712128588499` | 有无合同号 | radiogroup |  | `_widget_1577495432749` |
| `_widget_1577495432750` | 合同号 | combo |  | `_widget_1577495432749` |
| `_widget_1577495433532` | 现场联系人及电话 | text |  | `_widget_1577495432749` |
| `_widget_1577495432751` | 设备名称 | text |  | `_widget_1577495432749` |
| `_widget_1577495432752` | 设备型号 | text |  | `_widget_1577495432749` |
| `_widget_1577495432753` | 数量 | number |  | `_widget_1577495432749` |
| `_widget_1578287341623` | 单位 | text |  | `_widget_1577495432749` |
| `_widget_1577495432754` | 发货日期 | datetime |  | `_widget_1577495432749` |
| `_widget_1600497623100` | 总工转交 | radiogroup |  | `` |
| `_widget_1600497620698` | 总工下转 | user |  | `` |
| `_widget_1578270713998` | 附件 | upload |  | `` |
| `_widget_1578270714335` | 客服附件 | upload |  | `` |
| `_widget_1586759656542` | 客服安排附件 | upload |  | `` |
| `_widget_1618967086538` | 图片 | image |  | `` |
| `_widget_1578109421544` | 需要协作 | combo |  | `` |
| `_widget_1586759657262` | 协作人员 | usergroup |  | `` |
| `_widget_1599529315677` | 是否需要转交 | radiogroup |  | `` |
| `_widget_1599529315858` | 转交人员 | usergroup |  | `` |
| `_widget_1599529317113` | 是否需要通知相关人员 | radiogroup |  | `` |
| `_widget_1599529317145` | 通知相关人员 | usergroup |  | `` |
| `_widget_1776385827924` | 客服组长 | usergroup |  | `` |
| `_widget_1736846540976` | 是否需要总经理批示 | radiogroup |  | `` |
| `_widget_1774333506025` | 客服备注 | subform |  | `` |
| `_widget_1774333506027` | 内容 | text |  | `_widget_1774333506025` |
| `_widget_1774333506028` | 附件 | upload |  | `_widget_1774333506025` |
| `creator` | 提交人 | user |  | `` |
| `createTime` | 提交时间 | datetime |  | `` |
| `updateTime` | 更新时间 | datetime |  | `` |
