# 简道云「迅焊公司合同评审」流程配置摘要

> 来源：jdy-wrapper data-hub configs → workflow_config。

- 节点数: **19**

## 节点列表

| # | flowId | name | type | 审批人摘要 |
|---|--------|------|------|------------|
| 0 | -1 | 流程结束 | flow | {"users": [], "departs": [], "roles": []} |
| 1 | 0 | 流程发起节点 | flow | {"users": [], "departs": [], "roles": []} |
| 2 | 1 | 业务部门审批2 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 3 | 3 | 法务审批 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 4 | 5 | 总经理审批 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 5 | 6 | 财务意见 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 6 | 7 | 抄送相关人 | cc | {"users": [], "departs": [], "roles": []} |
| 7 | 10 | 抄送业务员 | cc | {"users": [], "departs": [], "roles": []} |
| 8 | 11 | 设计审批 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 9 | 12 | 信息反馈 | flow | users:2, departs:76 |
| 10 | 15 | 抄送李莉 | cc | {"users": [], "departs": [], "roles": []} |
| 11 | 21 | 财务总监意见 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 12 | 22 | 发起人 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 13 | 23 | 生产审批 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 14 | 24 | 采购审批 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 15 | 25 | 质检审批 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 16 | 27 | 抄送迅焊 | cc | {"users": [], "departs": [], "roles": []} |
| 17 | 28 | 设计审批1 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 18 | 29 | 法务主管审批 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |

## 节点类型统计

- `flow`: 15
- `cc`: 4