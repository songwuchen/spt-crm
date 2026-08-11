# 客服借据（字段对照）

> 简道云 app=`58e2fbc7ffd1608b4ce92809` entry=`62cccb4c8ee15d0009136487`。CRM key=`cs_loan_slip`。
> 流程节点数: **7**；扁平字段: **22**。

| name | title | type | required | parent |
|------|-------|------|----------|--------|
| `_widget_1597215968591` | 流水号 | sn |  | `` |
| `_widget_1562729205516` | 借据日期 | datetime |  | `` |
| `_widget_1562729205685` | 客户名称 | combo |  | `` |
| `_widget_1562983148782` | 合同号 | combo |  | `` |
| `_widget_1562813161623` | 业务部门 | dept |  | `` |
| `_widget_1562729205744` | 业务员 | user |  | `` |
| `_widget_1774490710430` | 对应内勤 | usergroup |  | `` |
| `_widget_1562730672596` | 明细 | subform |  | `` |
| `_widget_1562730672619` | 设备名称 | text |  | `_widget_1562730672596` |
| `_widget_1562917785582` | 规格型号 | text |  | `_widget_1562730672596` |
| `_widget_1562730672647` | 数量 | number |  | `_widget_1562730672596` |
| `_widget_1562922344901` | 单位 | text |  | `_widget_1562730672596` |
| `_widget_1749513825257` | 是否已抽条 | radiogroup |  | `` |
| `_widget_1655946162663` | 抽条日期 | datetime |  | `` |
| `_widget_1657596605516` | 附件 | upload |  | `` |
| `_widget_1657596605551` | 图片 | image |  | `` |
| `_widget_1562730825101` | 抽条备注 | textarea |  | `` |
| `_widget_1770085770734` | 业务员ID（辅助） | text |  | `` |
| `_widget_1770085770735` | 区域经理/组长 | user |  | `` |
| `creator` | 提交人 | user |  | `` |
| `createTime` | 提交时间 | datetime |  | `` |
| `updateTime` | 更新时间 | datetime |  | `` |
