# 售出产品/工具退回流程SCCP/GJTH（字段对照）

> 简道云 app=`58e2fbc7ffd1608b4ce92809` entry=`5e10538c0d5a270006df2763`。CRM key=`cs_product_return`。
> 流程节点数: **22**；扁平字段: **48**。

| name | title | type | required | parent |
|------|-------|------|----------|--------|
| `_widget_1578121055665` | 流水号 | sn |  | `` |
| `_widget_1703723955401` | 日期时间 | datetime |  | `` |
| `_widget_1672114764912` | *提交人 | user |  | `` |
| `_widget_1657678970356` | 发起部门 | dept |  | `` |
| `_widget_1703723955300` | 类型 | radiogroup |  | `` |
| `_widget_1577514157595` | 客户名称 | combo |  | `` |
| `_widget_1578119863142` | 业务部门 | dept |  | `` |
| `_widget_1577520412656` | 业务员 | user |  | `` |
| `_widget_1577514157633` | 现场联系人及电话 | text |  | `` |
| `_widget_1577514157611` | 货物地址 | address |  | `` |
| `_widget_1577519023451` | 备注 | textarea |  | `` |
| `_widget_1577519022536` | 售出产品退回 | subform |  | `` |
| `_widget_1577519022537` | 合同号 | combo |  | `_widget_1577519022536` |
| `_widget_1577519022538` | 设备名称 | text |  | `_widget_1577519022536` |
| `_widget_1577519022539` | 规格型号 | text |  | `_widget_1577519022536` |
| `_widget_1577519022540` | 数量 | number |  | `_widget_1577519022536` |
| `_widget_1578287861127` | 单位 | text |  | `_widget_1577519022536` |
| `_widget_1577519022541` | 发货日期 | datetime |  | `_widget_1577519022536` |
| `_widget_1577519022542` | 退回产品详细说明 | textarea |  | `_widget_1577519022536` |
| `_widget_1577519022543` | 备注 | textarea |  | `_widget_1577519022536` |
| `_widget_1665817650935` | 仓库判定* | radiogroup |  | `_widget_1577519022536` |
| `_widget_1665817556699` | 仓库确认231228取消 | radiogroup |  | `_widget_1577519022536` |
| `_widget_1764918545251` | 历史售出产品更换（补发）流程查看 | linkquery |  | `` |
| `_widget_1619070556652` | 图片 | subform |  | `` |
| `_widget_1619070556669` | 上传人 | text |  | `_widget_1619070556652` |
| `_widget_1619070556688` | 图片 | image |  | `_widget_1619070556652` |
| `_widget_1736757240448` | 发起节点上传退回图片 | subform |  | `` |
| `_widget_1736757240449` | 上传人 | text |  | `_widget_1736757240448` |
| `_widget_1736757240450` | 图片 | image |  | `_widget_1736757240448` |
| `_widget_1736757240488` | 其他节点查看发起人退回图片 | linkquery |  | `` |
| `_widget_1578537741743` | 图片 | image |  | `` |
| `_widget_1590721272018` | 附件 | upload |  | `` |
| `_widget_1620023611025` | 图片 | image |  | `` |
| `_widget_1578128358932` | 会签成员 | usergroup |  | `` |
| `_widget_1578128358916` | 会签（231228取消） | combo |  | `` |
| `_widget_1703723955512` | 分发质检人员 | usergroup |  | `` |
| `_widget_1703723955568` | 分发生产人员 | usergroup |  | `` |
| `_widget_1703723955540` | 分发采购人员 | usergroup |  | `` |
| `_widget_1586758707499` | 分发仓库人员 | usergroup |  | `` |
| `_widget_1578128358033` | 维修部门 | dept |  | `` |
| `_widget_1578127027977` | 仓库判定1 | combo |  | `` |
| `_widget_1691974761704` | 流程判断 | radiogroup |  | `` |
| `_widget_1753923897787` | 物流情况 | radiogroup |  | `` |
| `_widget_1734925951092` | 是否转相关人员 | radiogroup |  | `` |
| `_widget_1734925951094` | 转相关人员 | usergroup |  | `` |
| `creator` | 提交人 | user |  | `` |
| `createTime` | 提交时间 | datetime |  | `` |
| `updateTime` | 更新时间 | datetime |  | `` |
