# 简道云「安装图设计通知」流程配置摘要

> 来源：jdy-wrapper data-hub configs → workflow_config。

- 节点数: **21**

## 节点列表

| # | flowId | name | type | 审批人摘要 |
|---|--------|------|------|------------|
| 0 | -1 | 流程结束 | flow | {"users": [], "departs": [], "roles": []} |
| 1 | 0 | 流程发起节点 | flow | {"users": [], "departs": [], "roles": []} |
| 2 | 1 | 部门审批 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 3 | 5 | 设计指派安排 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 4 | 6 | 抄送设计指派1 | cc | {"users": [], "departs": [], "roles": []} |
| 5 | 7 | 总工审批 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 6 | 8 | 抄送订货人 | cc | {"users": [], "departs": [], "roles": []} |
| 7 | 9 | 周经理审批 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 8 | 10 | 转孙伟刘万涛 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 9 | 11 | 市场支持中心 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 10 | 12 | 抄送总经理 | cc | {"users": [], "departs": [], "roles": []} |
| 11 | 13 | 设计指派安排* | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 12 | 14 | 抄送设计指派2 | cc | {"users": [], "departs": [], "roles": []} |
| 13 | 15 | 抄送王东明 | cc | {"users": [], "departs": [], "roles": []} |
| 14 | 16 | 抄送组长 | cc | {"users": [], "departs": [], "roles": []} |
| 15 | 17 | 抄送李兴玉 | cc | {"users": [], "departs": [], "roles": []} |
| 16 | 18 | 抄送刘松潮 | cc | {"users": [], "departs": [], "roles": []} |
| 17 | 19 | 抄送樊磊 | cc | {"users": [], "departs": [], "roles": []} |
| 18 | 20 | 图纸领取 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 19 | 21 | 业务反馈 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |
| 20 | 22 | 工艺包装 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false} |

## 节点类型统计

- `flow`: 12
- `cc`: 9