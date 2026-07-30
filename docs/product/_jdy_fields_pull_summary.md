# JDY 合同登记/评审 fields 拉取结果

## 鉴权说明
- 用户提供的 `ak_fe5b...` 是 Open 平台 AppKey，对 `/api/form/*` 返回 401：`登录已过期或凭证无效，请重新登录`
- `/api/form/*` 成功使用的是 wrapper `X-API-Key`（来自内网 mcp `FORM_API_KEY`）
- Open API 需 `X-App-Key` + `X-App-Secret`；用 AppKey+Secret 直传 `/api/open/v1/ping` 成功
- Base: `http://192.168.0.6:8015`（8011 同样可用）

## 合同登记统计
- 主表字段（不含 subform 容器）: **109**
- 子表: **4**（合同明细(14), 收款计划(7), 地址不符时上传附件(2), 验收资料上传(3)）
- 含子表内字段合计: **139**

## 合同登记全部字段 name/title/type

| name | title | type | parent |
|---|---|---|---|
| `_widget_1681712851050` | 流水号 | sn |  |
| `_widget_1565937861689` | *提交人 | user |  |
| `_widget_1563772783339` | 下卡日期 | datetime |  |
| `_widget_1693447186027` | 客户编号 | text |  |
| `_widget_1593849162158` | 编号查询 | linkfield |  |
| `_widget_1561431499614` | 单位名称 | combo |  |
| `_widget_1561431499461` | 部门 | dept |  |
| `_widget_1561431499444` | 业务人员 | user |  |
| `_widget_1593849161675` | 合同状态 | radiogroup |  |
| `_widget_1613546005247` | 变动原因 | text |  |
| `_widget_1703462723292` | 合同获取信息方式 | radiogroup |  |
| `_widget_1404460362158` | 编号查询-（合同号） | text |  |
| `_widget_1677801576468` | 合同/项目评审信息 | separator |  |
| `_widget_1677806810340` | 选择合同/项目评审信息 | linkfield |  |
| `_widget_1677801667664` | 合同/项目评审流水号 | text |  |
| `_widget_1677801576469` | 24.2.3合同/项目评审信息查看0303 | linkquery |  |
| `_widget_1701052288708` | 以下为小萌合同评审内容1127 | separator |  |
| `_widget_1701052288707` | 选择小萌合同评审1127 | linkfield |  |
| `_widget_1701052373745` | 小萌合同评审流水号1127 | text |  |
| `_widget_1701052373744` | 选择小萌合同评审信息查看1127 | linkquery |  |
| `_widget_1634520599437` | 出厂编号 | text |  |
| `_widget_1623374466649` | 合同产品信息 | separator |  |
| `_widget_1610591432200` | 注释 | separator |  |
| `_widget_1561431499432` | 订货日期 | datetime |  |
| `_widget_1561431501010` | 合同类型 | radiogroup |  |
| `_widget_1561431499698` | 合同号 | text |  |
| `_widget_1563607519120` | 图纸编号 | text |  |
| `_widget_1561431499782` | 项目名称 | text |  |
| `_widget_1561431499731` | 对方合同号 | text |  |
| `_widget_1561431500134` | 是否含税 | radiogroup |  |
| `_widget_1575182444885` | 设备是否出口 | radiogroup |  |
| `_widget_1647391665368` | 是否需要安装 | radiogroup |  |
| `_widget_1664948274718` | 信息是否齐全 | radiogroup |  |
| `_widget_1664948274739` | 缺少项 | checkboxgroup |  |
| `_widget_1666255890740` | 信息不齐全备注 | textarea |  |
| `_widget_1621411268101` | 出口类型 | text |  |
| `_widget_1676104999490` | 合同形式 | radiogroup |  |
| `_widget_1721205724881` | 是否标准交付 | radiogroup |  |
| `_widget_1721205724883` | 方式 | radiogroup |  |
| `_widget_1749715722571` | 是否为旋振筛 | radiogroup |  |
| `_widget_1721293963816` | 填写代码 | text |  |
| `_widget_1721205725083` | 采购员多选 | usergroup |  |
| `_widget_1721205725117` | 质检员多选 | usergroup |  |
| `_widget_1561431500151` | 合同明细 | subform |  |
| `_widget_1621411268784` | 是否外币合同 | radiogroup | 合同明细 |
| `_widget_1561431500162` | 产品类型 | combo | 合同明细 |
| `_widget_1561431500376` | 产品名称 | text | 合同明细 |
| `_widget_1561431500392` | 规格型号 | text | 合同明细 |
| `_widget_1561431500419` | 单位 | text | 合同明细 |
| `_widget_1561431500458` | 数量 | number | 合同明细 |
| `_widget_1621411268153` | 外币单价 | number | 合同明细 |
| `_widget_1621411269220` | 汇率 | number | 合同明细 |
| `_widget_1561431500490` | 单价 | number | 合同明细 |
| `_widget_1561431500514` | 总价 | number | 合同明细 |
| `_widget_1621411268210` | 外币总价 | number | 合同明细 |
| `_widget_1561431500595` | 电控装置 | combo | 合同明细 |
| `_widget_1565223122750` | 技术参数及要求 | text | 合同明细 |
| `_widget_1697420581927` | 备注(①生产卡上按序号排列的项目，某设备已经包含在其他设备内时，在备注栏加填*。②生产卡上按序号排列的项目，某设备不需要供货时，在备注栏加填#） | text | 合同明细 |
| `_widget_1561511175392` | 合同总金额 | number |  |
| `_widget_1565157771516` | 技术参数及要求 | textarea |  |
| `_widget_1561431501051` | 包装情况 | text |  |
| `_widget_1566366881094` | 油漆要求 | radiogroup |  |
| `_widget_1563281842830` | 工作量 | radiogroup |  |
| `_widget_1623374466732` | 合同收款信息 | separator |  |
| `_widget_1561431500766` | 付款形式 | checkboxgroup |  |
| `_widget_1561431500955` | 付款方式文字描述 | text |  |
| `_widget_1561431500970` | 合同交货期 | datetime |  |
| `_widget_1561431500982` | 交货期条款 | text |  |
| `_widget_1561431500797` | 收款计划 | subform |  |
| `_widget_1661242797064` | 日期时间 | datetime | 收款计划 |
| `_widget_1561431500818` | 付款方式 | combo | 收款计划 |
| `_widget_1561431500832` | 付款比例（%） | number | 收款计划 |
| `_widget_1561431500855` | 付款金额 | number | 收款计划 |
| `_widget_1665380027624` | ID辅助 | text | 收款计划 |
| `_widget_1665380028160` | 是否提醒 | text | 收款计划 |
| `_widget_1665380027757` | 消息辅助 | text | 收款计划 |
| `_widget_1696822285599` | 质保期限 | text |  |
| `_widget_1696822285597` | 质保金额 | number |  |
| `_widget_1623374466832` | 合同其他信息 | separator |  |
| `_widget_1561431499820` | 行业分类 | combo |  |
| `_widget_1561431499871` | 地区 | combo |  |
| `_widget_1561431499996` | 应用领域 | combo |  |
| `_widget_1576116537439` | 应用物料 | combo |  |
| `_widget_1579240052161` | 是否含智能化 | radiogroup |  |
| `_widget_1582439670467` | 智能点 | combocheck |  |
| `_widget_1563280700625` | 备注 | textarea |  |
| `_widget_1561431501066` | 特别提醒 | text |  |
| `_widget_1561511175252` | 附件（合同、协议） | upload |  |
| `_widget_1561511175264` | 图片（合同、协议） | image |  |
| `_widget_1573192575054` | 验收单 | upload |  |
| `_widget_1627697874959` | 生产卡信息 | linkquery |  |
| `_widget_1661242797021` | 日期时间 | datetime |  |
| `_widget_1698917219543` | 选择服务费数据 | linkfield |  |
| `_widget_1720749080105` | 变动查看 | linkquery |  |
| `_widget_1752304126294` | 关联数据 | lookup |  |
| `_widget_1759559814671` | 附件同步知识库时间 | datetime |  |
| `_widget_1666331897364` | 合同回款信息 | linkquery |  |
| `_widget_1596086134880` | 单位回款信息 | linkquery |  |
| `_widget_1594173385303` | 开票信息查询 | linkquery |  |
| `_widget_1667291302111` | 运费承担方 | radiogroup |  |
| `_widget_1667286001079` | 合同约定地址 | address |  |
| `_widget_1730100756545` | 发货地址 | linkfield |  |
| `_widget_1667286001084` | 发货地址 | address |  |
| `_widget_1667286001085` | 比对地址辅助 | text |  |
| `_widget_1667291302128` | 发货地址（到区）（辅助） | text |  |
| `_widget_1667291302129` | 合同地址（到区）（辅助） | text |  |
| `_widget_1667291302115` | 地址不符时上传附件 | subform |  |
| `_widget_1667291302117` | 图片 | image | 地址不符时上传附件 |
| `_widget_1667291302118` | 附件 | upload | 地址不符时上传附件 |
| `_widget_1594173385329` | 发货信息查询 | linkquery |  |
| `_widget_1623889620353` | 运费登记表 | linkquery |  |
| `_widget_1662088494543` | 发货状态 | text |  |
| `_widget_1594173385664` | 最后发货日期（241012停用） | datetime |  |
| `_widget_1594173385703` | 发货总额（241012停用） | number |  |
| `_widget_1668417748847` | 验收方式 | radiogroup |  |
| `_widget_1668417749220` | 验收所需资料 | text |  |
| `_widget_1668417748935` | 验收资料上传 | subform |  |
| `_widget_1668417748995` | 验收日期 | datetime | 验收资料上传 |
| `_widget_1668417748937` | 图片 | image | 验收资料上传 |
| `_widget_1668417748966` | 附件 | upload | 验收资料上传 |
| `_widget_1698823518549` | 行业分类-小萌 | radiogroup |  |
| `_widget_1698908493692` | 成本-小萌231101 | number |  |
| `_widget_1698908493693` | 运费-小萌231101 | number |  |
| `_widget_1705729384963` | 地区-小萌240120 | text |  |
| `_widget_1705729384962` | 省份-小萌240120 | text |  |
| `_widget_1698908493694` | 服务费-小萌231101 | number |  |
| `_widget_1616210898698` | 以下是辅助信息字段 | separator |  |
| `_widget_1614213005939` | 单行文本（辅助） | text |  |
| `_widget_1609113829970` | 判断是否含新增（辅助） | text |  |
| `_widget_1670549305841` | 判断对方合同号是否含新增（辅助） | text |  |
| `_widget_1594185418743` | 合同总额（辅助） | number |  |
| `_widget_1670549305842` | *限制同一对方合同号只能新增一次 | text |  |
| `_widget_1610611018415` | 限制同一合同号只能新增一次 | text |  |
| `_widget_1616999695532` | 下卡日期辅助（辅助） | number |  |
| `_widget_1729124887299` | 辅助是否含需要提醒（241017增，用于辅助筛选出需要提醒的数据，大于0则是含有需要提醒的数据） | text |  |
| `_widget_1631177786890` | 合同提交状态（辅助） | radiogroup |  |
| `creator` | 提交人 | user |  |
| `createTime` | 提交时间 | datetime |  |
| `updateTime` | 更新时间 | datetime |  |

## CRM 已知字段精确对照

- `contract_no` ← 合同号 (`_widget_1561431499698`, text)
- `drawing_no` ← 图纸编号 (`_widget_1563607519120`, text)
- `peer_contract_no` ← 对方合同号 (`_widget_1561431499731`, text)
- `acquire_method` ← 合同获取信息方式 (`_widget_1703462723292`, radiogroup)
- `delivery_date` ← 合同交货期 (`_widget_1561431500970`, datetime)
- `change_type` ← 合同状态 (`_widget_1593849161675`, radiogroup)
- `amount` ← 合同总金额 (`_widget_1561511175392`, number)
- `payment` ← 收款计划 (`_widget_1561431500797`, subform)
- `lines` ← 合同明细 (`_widget_1561431500151`, subform)

## 明显缺口（JDY 有、CRM 已知列/已映射未覆盖）

- `_widget_1565937861689` | 提交人 | user
- `_widget_1563772783339` | 下卡日期 | datetime
- `_widget_1693447186027` | 客户编号 | text
- `_widget_1613546005247` | 变动原因 | text
- `_widget_1404460362158` | 编号查询-（合同号） | text
- `_widget_1677801667664` | 合同/项目评审流水号 | text
- `_widget_1701052373745` | 小萌合同评审流水号1127 | text
- `_widget_1634520599437` | 出厂编号 | text
- `_widget_1561431499432` | 订货日期 | datetime
- `_widget_1561431501010` | 合同类型 | radiogroup
- `_widget_1561431500134` | 是否含税 | radiogroup
- `_widget_1575182444885` | 设备是否出口 | radiogroup
- `_widget_1647391665368` | 是否需要安装 | radiogroup
- `_widget_1664948274718` | 信息是否齐全 | radiogroup
- `_widget_1664948274739` | 缺少项 | checkboxgroup
- `_widget_1666255890740` | 信息不齐全备注 | textarea
- `_widget_1621411268101` | 出口类型 | text
- `_widget_1676104999490` | 合同形式 | radiogroup
- `_widget_1721205724881` | 是否标准交付 | radiogroup
- `_widget_1721205724883` | 方式 | radiogroup
- `_widget_1749715722571` | 是否为旋振筛 | radiogroup
- `_widget_1721293963816` | 填写代码 | text
- `_widget_1721205725083` | 采购员多选 | usergroup
- `_widget_1721205725117` | 质检员多选 | usergroup
- `_widget_1561431501051` | 包装情况 | text
- `_widget_1566366881094` | 油漆要求 | radiogroup
- `_widget_1563281842830` | 工作量 | radiogroup
- `_widget_1561431500766` | 付款形式 | checkboxgroup
- `_widget_1561431500955` | 付款方式文字描述 | text
- `_widget_1561431500982` | 交货期条款 | text
- `_widget_1696822285599` | 质保期限 | text
- `_widget_1696822285597` | 质保金额 | number
- `_widget_1561431499820` | 行业分类 | combo
- `_widget_1561431499871` | 地区 | combo
- `_widget_1561431499996` | 应用领域 | combo
- `_widget_1576116537439` | 应用物料 | combo
- `_widget_1579240052161` | 是否含智能化 | radiogroup
- `_widget_1582439670467` | 智能点 | combocheck
- `_widget_1563280700625` | 备注 | textarea
- `_widget_1561431501066` | 特别提醒 | text
- `_widget_1561511175252` | 附件（合同、协议） | upload
- `_widget_1561511175264` | 图片（合同、协议） | image
- `_widget_1573192575054` | 验收单 | upload
- `_widget_1759559814671` | 附件同步知识库时间 | datetime
- `_widget_1667291302111` | 运费承担方 | radiogroup
- `_widget_1667286001079` | 合同约定地址 | address
- `_widget_1667286001084` | 发货地址 | address
- `_widget_1667286001085` | 比对地址辅助 | text
- `_widget_1667291302128` | 发货地址（到区）（辅助） | text
- `_widget_1667291302129` | 合同地址（到区）（辅助） | text
- `_widget_1667291302115` | 地址不符时上传附件 | subform
- `_widget_1662088494543` | 发货状态 | text
- `_widget_1594173385664` | 最后发货日期（241012停用） | datetime
- `_widget_1594173385703` | 发货总额（241012停用） | number
- `_widget_1668417748847` | 验收方式 | radiogroup
- `_widget_1668417749220` | 验收所需资料 | text
- `_widget_1668417748935` | 验收资料上传 | subform
- `_widget_1698823518549` | 行业分类-小萌 | radiogroup
- `_widget_1698908493692` | 成本-小萌231101 | number
- `_widget_1698908493693` | 运费-小萌231101 | number
- `_widget_1705729384963` | 地区-小萌240120 | text
- `_widget_1705729384962` | 省份-小萌240120 | text
- `_widget_1698908493694` | 服务费-小萌231101 | number
- `_widget_1614213005939` | 单行文本（辅助） | text
- `_widget_1609113829970` | 判断是否含新增（辅助） | text
- `_widget_1670549305841` | 判断对方合同号是否含新增（辅助） | text
- `_widget_1594185418743` | 合同总额（辅助） | number
- `_widget_1670549305842` | 限制同一对方合同号只能新增一次 | text
- `_widget_1610611018415` | 限制同一合同号只能新增一次 | text
- `_widget_1616999695532` | 下卡日期辅助（辅助） | number
- `_widget_1729124887299` | 辅助是否含需要提醒（241017增，用于辅助筛选出需要提醒的数据，大于0则是含有需要提醒的数据） | text
- `_widget_1631177786890` | 合同提交状态（辅助） | radiogroup
- `creator` | 提交人 | user
- `createTime` | 提交时间 | datetime
- `updateTime` | 更新时间 | datetime

## 抽样 2 条

### 6a6999ca20b75987e7c85437
- 流水号: 1.2.3-2026072901330
- 合同号: KS26213
- 图纸编号: WMGF202607081
- 对方合同号: 无
- 合同状态: 变动
- 合同获取信息方式: 协商一致
- 合同交货期: 2026-07-17T16:00:00.000Z
- 合同总金额: 1200
- 单位名称: 西安墨源机电设备有限公司
- 项目名称: 无
- 收款计划: [subform x1]
- 合同明细: [subform x1]
- 变动原因: 新增 弧形筛楔块 WFHS-242060-2-YS 合同金额变更为4560

### 6a6974c464474b4cde2dfeb7
- 流水号: 1.2.3-2026072901329
- 合同号: XJ26119
- 图纸编号: WMGF202607184
- 对方合同号: /
- 合同状态: 新增
- 合同获取信息方式: 协商一致
- 合同交货期: 2026-09-09T16:00:00.000Z
- 合同总金额: 8748
- 单位名称: 新疆威猛工业智能装备有限公司
- 项目名称: 无
- 收款计划: [subform x1]
- 合同明细: [subform x1]

## 合同评审
- 主表字段: **96**，子表: ['联系信息']，合计含下钻: **105**

| name | title | type | parent |
|---|---|---|---|
| `_widget_1601273674993` | 流水号 | sn |  |
| `_widget_1571965661665` | 合同评审/项目评审（260518取消） | radiogroup |  |
| `_widget_1700817134166` | 是否出口合同 | radiogroup |  |
| `_widget_1669597630356` | 是否核价 | radiogroup |  |
| `_widget_1636957088887` | 是否需要安装 | radiogroup |  |
| `_widget_1574756606514` | 业务员 | user |  |
| `_widget_1770087198715` | 业务员ID（辅助） | text |  |
| `_widget_1770087198714` | 区域经理/组长 | user |  |
| `_widget_1574756606496` | 业务部门 | dept |  |
| `_widget_1712364068119` | 选择公司名称 | linkfield |  |
| `_widget_1552369403179` | 公司名称 | text |  |
| `_widget_1700446723223` | 是否外贸客户 | text |  |
| `_widget_1721093361440` | 是否小萌240716(250314禁用） | radiogroup |  |
| `_widget_1644561606451` | 是否销售小萌（23.11.25取消） | radiogroup |  |
| `_widget_1723685156828` | 电控装置 | radiogroup |  |
| `_widget_1683856445974` | 室主任（230522取消，但流程版本V26用到） | usergroup |  |
| `_widget_1677803834024` | 核价信息 | separator |  |
| `_widget_1677810182290` | 选择27.7核价管理信息 | linkfield |  |
| `_widget_1669789398113` | 核价单号 | text |  |
| `_widget_1669597630371` | 核价时间（22/11/30取消） | datetime |  |
| `_widget_1677803834040` | 27.7核价管理流程查询 | linkquery |  |
| `_widget_1737505642219` | 成本附件250122 | upload |  |
| `_widget_1737505642376` | 成本价250122 | textarea |  |
| `_widget_1737505642264` | 27.7核价管理流程（成本价） | linkquery |  |
| `_widget_1669789398145` | 核价配置要求的电机 | text |  |
| `_widget_1669789398148` | 核价配置要求的轴承 | text |  |
| `_widget_1669789398149` | 核价配置要求的主材材质 | text |  |
| `_widget_1669789398151` | 核价配置要求的衬板/筛板 | text |  |
| `_widget_1669789398152` | 特殊要求 | textarea |  |
| `_widget_1571965661782` | 客户信息 | separator |  |
| `_widget_1552369403178` | 客户类型 | radiogroup |  |
| `_widget_1575620563294` | 正式合同份数 | number |  |
| `_widget_1552369403180` | 公司性质* | text |  |
| `_widget_1552369403182` | 所属行业* | text |  |
| `_widget_1571980668231` | 规模及资金（万元）* | number |  |
| `_widget_1552369403185` | 客户关系* | text |  |
| `_widget_1574923502794` | 失信信息 | number |  |
| `_widget_1573546023205` | 诉讼纠纷 | number |  |
| `_widget_1573546023251` | 环保处罚 | number |  |
| `_widget_1573546023339` | 税务处罚 | number |  |
| `_widget_1573546023421` | 其它行政处罚 | number |  |
| `_widget_1666143568899` | 联系信息 | subform |  |
| `_widget_1666143568901` | 联系人 | text | 联系信息 |
| `_widget_1666143568902` | 上级领导 | text | 联系信息 |
| `_widget_1666143568903` | 手机号码 | text | 联系信息 |
| `_widget_1666143568904` | 职务 | text | 联系信息 |
| `_widget_1678428794483` | 邮箱or请示 | radiogroup | 联系信息 |
| `_widget_1666143568905` | 邮箱 | text | 联系信息 |
| `_widget_1678428794562` | 请示 | text | 联系信息 |
| `_widget_1666143568906` | 地址 | address | 联系信息 |
| `_widget_1571965661943` | 项目信息 | separator |  |
| `_widget_1574409968702` | 母公司或控股公司的情况及性质说明* | text |  |
| `_widget_1552447447285` | 项目名称及应用 | textarea |  |
| `_widget_1552369403189` | 报备时间 | datetime |  |
| `_widget_1552369403186` | 工资及保险情况* | text |  |
| `_widget_1571965661951` | 合同价格（元） | number |  |
| `_widget_1552369403191` | 交货期 | text |  |
| `_widget_1552445539881` | 是否有保函 | radiogroup |  |
| `_widget_1552445539906` | 保函类型 | radiogroup |  |
| `_widget_1616203849373` | 是否有重量要求 | radiogroup |  |
| `_widget_1601356599650` | 是否趁用呆滞设备 | radiogroup |  |
| `_widget_1577784147558` | 合同是否含智能化部分 | radiogroup |  |
| `_widget_1552445540017` | 合同签订依据及情况 | text |  |
| `_widget_1574409652548` | 参考合同号 | text |  |
| `_widget_1552435959889` | 付款方式 | text |  |
| `_widget_1574150406585` | 公司现状调查 | text |  |
| `_widget_1574150406569` | 项目报备与投标情况 | text |  |
| `_widget_1574150406601` | 针对销售情况的补充 | text |  |
| `_widget_1552453980743` | 现场测绘及要求 | text |  |
| `_widget_1574756606691` | 附件 | upload |  |
| `_widget_1619053749212` | 图片 | image |  |
| `_widget_1736576180989` | 风险信息 | separator |  |
| `_widget_1574150406495` | 合同条款审核意见 | textarea |  |
| `_widget_1736576180940` | 法务风险等级判断 | radiogroup |  |
| `_widget_1736576180942` | 法务风险等级文字描述 | text |  |
| `_widget_1736736740214` | 技术风险等级判断 | radiogroup |  |
| `_widget_1736736740216` | 技术风险等级文字描述 | text |  |
| `_widget_1736576180965` | 业务风险等级判断 | radiogroup |  |
| `_widget_1736576180968` | 业务风险等级文字描述 | text |  |
| `_widget_1736576180963` | 财务风险等级判断 | radiogroup |  |
| `_widget_1736576180967` | 财务风险等级文字描述 | text |  |
| `_widget_1737505642531` | 采购风险等级判断 | radiogroup |  |
| `_widget_1737505641998` | 采购风险等级文字描述 | text |  |
| `_widget_1736576181070` | 出口风险等级判断 | radiogroup |  |
| `_widget_1736576181072` | 出口风险等级文字描述 | text |  |
| `_widget_1736576181094` | 风险查看 | linkquery |  |
| `_widget_1574150406737` | 重点数据及信用等级 | text |  |
| `_widget_1574150406753` | 前期业务来往描述 | text |  |
| `_widget_1574150406769` | 核价报价补充 | text |  |
| `_widget_1571965661995` | 结论 | separator |  |
| `_widget_1733555512882` | 账期 | text |  |
| `_widget_1733555512985` | 账期查看（用于必填字段往后节点可见） | linkquery |  |
| `_widget_1571965662023` | 结论描述 | textarea |  |
| `_widget_1571965662256` | 是否反馈 | radiogroup |  |
| `_widget_1577171437278` | 成员多选 | usergroup |  |
| `_widget_1577171437265` | 反馈附件 | upload |  |
| `_widget_1619053749445` | 反馈图片 | image |  |
| `_widget_1675494030973` | 合同签订 | separator |  |
| `_widget_1673836407417` | 图纸编号 | combo |  |
| `_widget_1673848111184` | 关联查询 | linkquery |  |
| `_widget_1675494030989` | 合同明细 | linkquery |  |
| `_widget_1675495250350` | 合同评审意见执行情况 | textarea |  |
| `creator` | 提交人 | user |  |
| `createTime` | 提交时间 | datetime |  |
| `updateTime` | 更新时间 | datetime |  |