# 简道云「核价清单传递流程HJQD」流程配置摘要

> 菜单：中央研究院 / 研究院统计 / 核价清单 / 核价清单传递流程HJQD
> app=`584658417562f37a227fa805` entry=`667638539c1f73c42e4bcbff`
> 来源：jdy-wrapper data-hub configs → workflow_config。

- editable: `False`
- 节点数: **7**

## 节点列表

| # | flowId | name | type | 审批人摘要 |
|---|--------|------|------|------------|
| 0 | -1 | 流程结束节点 | flow | {"users": [], "departs": [], "roles": []}; approvalMethod=1, condition=ok, 有字段权限 |
| 1 | 0 | 流程发起节点 | flow | {"users": [], "departs": [], "roles": []}; approvalMethod=1, 有字段权限 |
| 2 | 1 | 财务 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false}; approvalMethod=1, condition=ok, 有字段权限 |
| 3 | 2 | 抄送申请人 | cc | {"users": [], "departs": [], "roles": []}; approvalMethod=1, condition=ok, 有字段权限 |
| 4 | 3 | 抄送申请人 | cc | {"users": [], "departs": [], "roles": []}; approvalMethod=1, condition=ok, 有字段权限 |
| 5 | 4 | 抄送申请人 | cc | {"users": [], "departs": [], "roles": []}; approvalMethod=1, condition=ok, 有字段权限 |
| 6 | 5 | 抄送申请人 | cc | {"users": [], "departs": [], "roles": []}; approvalMethod=1, condition=ok, 有字段权限 |

## 节点类型统计

- `cc`: 4
- `flow`: 3