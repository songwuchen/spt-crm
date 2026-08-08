# 简道云「核价管理流程」流程配置摘要

> 来源：jdy-wrapper data-hub configs → workflow_config。产品名 CRM 侧为「报价管理」。

- 节点数: **20**

## 节点列表

| # | flowId | name | type | 审批人摘要 |
|---|--------|------|------|------------|
| 0 | -1 | 流程结束 | flow | {"users": [], "departs": [], "roles": []} |
| 1 | 0 | 流程发起节点 | flow | {"users": [], "departs": [], "roles": []} |
| 2 | 1 | 部门审批 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 3 | 2 | 财务核价 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 4 | 6 | 通知销售经理 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 5 | 7 | 通知尚高华 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 6 | 8 | 抄送发起人 | cc | {"users": [], "departs": [], "roles": []} |
| 7 | 10 | 王玲玲审批 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 8 | 11 | 经理审批 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 9 | 12 | 热能 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 10 | 13 | 国际营销中心 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 11 | 14 | 冶金装备销售事业部 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 12 | 15 | 采购 | flow | departs:1 |
| 13 | 16 | 通知矿山工程装备销售 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 14 | 17 | 赵亚芳 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 15 | 18 | 经理审批 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 16 | 19 | 王玲玲审批 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 17 | 20 | 部门审批 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 18 | 21 | 抄送 | cc | {"users": [], "departs": [], "roles": []} |
| 19 | 22 | 袁文俊 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |

## 节点类型统计

- `flow`: 18
- `cc`: 2