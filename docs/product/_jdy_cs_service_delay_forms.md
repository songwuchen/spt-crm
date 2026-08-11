# 客户服务延期申请（字段对照）

> 简道云 app=`58e2fbc7ffd1608b4ce92809` entry=`5f9b6dacb6ec680007f9c46f`。CRM key=`cs_service_delay`。
> 流程节点数: **9**；扁平字段: **16**。

| name | title | type | required | parent |
|------|-------|------|----------|--------|
| `_widget_1604021830267` | 流水号 | sn |  | `` |
| `_widget_1585191665097` | 合同号 | combo |  | `` |
| `_widget_1585191665061` | 业务员 | user |  | `` |
| `_widget_1585191665079` | 所属部门 | dept |  | `` |
| `_widget_1585191665113` | 设备信息 | subform |  | `` |
| `_widget_1585191665125` | 产品名称 | text |  | `_widget_1585191665113` |
| `_widget_1585191665148` | 规格型号 | text |  | `_widget_1585191665113` |
| `_widget_1585191665207` | 数量/单位 | text |  | `_widget_1585191665113` |
| `_widget_1585191665226` | 服务公司 | text |  | `` |
| `_widget_1585191665241` | 服务事项 | text |  | `` |
| `_widget_1585191665258` | 延期至 | datetime |  | `` |
| `_widget_1585191665284` | 延期原因 | text |  | `` |
| `_widget_1585191665301` | 备注 | textarea |  | `` |
| `creator` | 提交人 | user |  | `` |
| `createTime` | 提交时间 | datetime |  | `` |
| `updateTime` | 更新时间 | datetime |  | `` |
