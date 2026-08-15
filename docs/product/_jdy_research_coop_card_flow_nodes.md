# 简道云「中央研究院协同卡」流程配置摘要

> 菜单：中央研究院 / 中央研究院协同卡 / 中央研究院协同卡
> app=`584658417562f37a227fa805` entry=`63acddd2129b90000a2933f1`
> 来源：jdy-wrapper data-hub configs → workflow_config。

- editable: `False`
- 节点数: **8**

## 节点列表

| # | flowId | name | type | 审批人摘要 |
|---|--------|------|------|------------|
| 0 | -1 | 流程结束节点 | flow | {"users": [], "departs": [], "roles": []}; approvalMethod=1, condition=ok, 有字段权限 |
| 1 | 0 | 流程发起节点 | flow | {"users": [], "departs": [], "roles": []}; approvalMethod=1, 有字段权限 |
| 2 | 1 | 室主任 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false}; approvalMethod=1, condition=ok, 有字段权限 |
| 3 | 2 | 设计安排 | flow | users:5; approvalMethod=1, condition=ok, 有字段权限 |
| 4 | 3 | 抄送申请人 | cc | {"users": [], "departs": [], "roles": []}; approvalMethod=1, condition=ok, 有字段权限 |
| 5 | 4 | 室主任 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false}; approvalMethod=1, condition=ok, 有字段权限 |
| 6 | 5 | 转新乡、工艺包装 | flow | users:6; approvalMethod=1, condition=ok, 有字段权限 |
| 7 | 6 | 工艺包装 | flow | {"users": [], "departs": [], "roles": [], "hasDeptCascade": false}; approvalMethod=1, condition=ok, 有字段权限 |

## 节点类型统计

- `flow`: 7
- `cc`: 1