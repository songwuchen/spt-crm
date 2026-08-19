# 简道云「售前服务通知流程」流程配置摘要

> 来源：jdy-wrapper data-hub configs → workflow_config。

- 节点数: **13**

## 节点列表

| # | flowId | name | type | 审批人摘要 |
|---|--------|------|------|------------|
| 0 | -1 | 流程结束 | flow | {"users": [], "departs": [], "roles": []} |
| 1 | 0 | 流程发起节点 | flow | {"users": [], "departs": [], "roles": []} |
| 2 | 2 | 总工审批 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 3 | 3 | 人员协调 | flow | departs:1 |
| 4 | 4 | 部门审批 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 5 | 5 | 流程分发 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 6 | 6 | 部门审批 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 7 | 7 | 生产审批 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 8 | 8 | 流程分发 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 9 | 9 | 抄送节点 | cc | {"users": [], "departs": [], "roles": []} |
| 10 | 10 | 抄送节点 | cc | {"users": [], "departs": [], "roles": []} |
| 11 | 14 | 韩利民 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 12 | 15 | 新疆威猛 | flow | departs:2 |

## 节点类型统计

- `flow`: 11
- `cc`: 2