# 售出产品更换（补发）流程（字段对照）

> 简道云 app=`58e2fbc7ffd1608b4ce92809` entry=`5e06f4ad2a9eb70007f7c164`。CRM key=`cs_product_replace`。
> 流程节点数: **19**；扁平字段: **53**。

| name | title | type | required | parent |
|------|-------|------|----------|--------|
| `_widget_1578121055665` | 流水号 | sn |  | `` |
| `_widget_1617689215719` | 日期时间 | datetime |  | `` |
| `_widget_1578119863142` | 业务部门 | dept |  | `` |
| `_widget_1577520412656` | 业务员 | user |  | `` |
| `_widget_1770085266609` | 业务员ID（辅助） | text |  | `` |
| `_widget_1770085266610` | 对应区域经理或组长 | user |  | `` |
| `_widget_1577514157595` | 客户名称 | combo |  | `` |
| `_widget_1647329433188` | 客户类别 | linkquery |  | `` |
| `_widget_1577514157611` | 货物地址 | address |  | `` |
| `_widget_1577514157633` | 现场联系人及电话 | text |  | `` |
| `_widget_1577519023451` | 备注 | textarea |  | `` |
| `_widget_1675673210466` | 是否需退回 | radiogroup |  | `` |
| `_widget_1749182322753` | 是否关联验收回款 | radiogroup |  | `` |
| `_widget_1675673210468` | 是否需打借据 | radiogroup |  | `` |
| `_widget_1739261778534` | 紧急程度判定-业务经理 | radiogroup |  | `` |
| `_widget_1739261778536` | 紧急程度判定-客服经理 | radiogroup |  | `` |
| `_widget_1739261778538` | 最终紧急程度判定（辅助） | text |  | `` |
| `_widget_1739318635777` | 紧急程度判定-总经理 | radiogroup |  | `` |
| `_widget_1739318635876` | 最终紧急程度判定 | text |  | `` |
| `_widget_1739261778695` | 紧急程度判定情况查看 | linkquery |  | `` |
| `_widget_1577519022536` | 换货（含补发） | subform |  | `` |
| `_widget_1577519022537` | 合同号 | combo |  | `_widget_1577519022536` |
| `_widget_1577519022538` | 设备名称 | text |  | `_widget_1577519022536` |
| `_widget_1577519022539` | 规格型号 | text |  | `_widget_1577519022536` |
| `_widget_1577519022540` | 数量 | number |  | `_widget_1577519022536` |
| `_widget_1578287834987` | 单位 | text |  | `_widget_1577519022536` |
| `_widget_1577519022541` | 发货日期 | datetime |  | `_widget_1577519022536` |
| `_widget_1577519022542` | 退换详细说明 | textarea |  | `_widget_1577519022536` |
| `_widget_1617691334516` | 故障分类 | text |  | `_widget_1577519022536` |
| `_widget_1687499358442` | 成本价 | text |  | `` |
| `_widget_1619070274799` | 图片 | subform |  | `` |
| `_widget_1619070274816` | 上传人 | text |  | `_widget_1619070274799` |
| `_widget_1619070274835` | 图片 | image |  | `_widget_1619070274799` |
| `_widget_1578271183948` | 附件0418 | upload |  | `` |
| `_widget_1578271183961` | 客服附件0418 | upload |  | `` |
| `_widget_1578702338220` | 客服补登附件0418 | upload |  | `` |
| `_widget_1589433529814` | 会签附件0418 | upload |  | `` |
| `_widget_1578452391724` | 需要补登 | radiogroup |  | `` |
| `_widget_1675988284441` | 货是否发完 | radiogroup |  | `` |
| `_widget_1716164018678` | 是否小萌 | radiogroup |  | `` |
| `_widget_1578127027977` | 会签 | radiogroup |  | `` |
| `_widget_1618966943220` | 图片0418 | image |  | `` |
| `_widget_1578127028052` | 会签人员 | usergroup |  | `` |
| `_widget_1586759362043` | 是否追溯（已取消） | radiogroup |  | `` |
| `_widget_1617689215015` | 责任方 | text |  | `` |
| `_widget_1593825383660` | 是否需要转交相关人员处理后补登 | radiogroup |  | `` |
| `_widget_1593825383717` | 相关人员处理 | user |  | `` |
| `_widget_1774333375920` | 客服备注 | subform |  | `` |
| `_widget_1774333375922` | 内容 | text |  | `_widget_1774333375920` |
| `_widget_1774333375923` | 附件 | upload |  | `_widget_1774333375920` |
| `creator` | 提交人 | user |  | `` |
| `createTime` | 提交时间 | datetime |  | `` |
| `updateTime` | 更新时间 | datetime |  | `` |
