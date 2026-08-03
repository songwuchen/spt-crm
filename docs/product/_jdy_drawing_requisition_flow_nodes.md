# 简道云「合同图纸（资料）领用申请」流程配置摘要

> 来源：jdy-wrapper data-hub configs → workflow_config。

- 节点数: **21**

## 节点列表

| # | flowId | name | type | 审批人摘要 |
|---|--------|------|------|------------|
| 0 | -1 | 流程结束 | flow | {"users": [], "departs": [], "roles": []} |
| 1 | 0 | 流程发起节点 | flow | {"users": [], "departs": [], "roles": []} |
| 2 | 1 | 设计主管审批 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 3 | 2 | 部门审批 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 4 | 3 | 总工审批 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 5 | 5 | 研究院安排 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 6 | 6 | 图纸领取 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 7 | 7 | 抄送订货人 | cc | {"users": [], "departs": [], "roles": []} |
| 8 | 8 | 研究院安排 | flow | departs:1 |
| 9 | 9 | 抄送节点 | cc | {"users": [], "departs": [], "roles": []} |
| 10 | 10 | 抄送李兴玉 | cc | {"users": [], "departs": [], "roles": []} |
| 11 | 11 | 抄送王东明 | cc | {"users": [], "departs": [], "roles": []} |
| 12 | 12 | 抄送周彦立 | cc | {"users": [], "departs": [], "roles": []} |
| 13 | 13 | 抄送刘松潮 | cc | {"users": [], "departs": [], "roles": []} |
| 14 | 14 | 抄送樊磊 | cc | {"users": [], "departs": [], "roles": []} |
| 15 | 15 | 抄送组长 | cc | {"users": [], "departs": [], "roles": []} |
| 16 | 16 | 市场支持中心 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 17 | 17 | 业务打分 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 18 | 18 | 总经理审批 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 19 | 19 | 企标委审批 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 20 | 20 | 工艺包装 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |

## 节点类型统计

- `flow`: 13
- `cc`: 8