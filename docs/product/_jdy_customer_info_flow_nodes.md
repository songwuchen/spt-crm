# 简道云「客户信息」流程配置摘要

> 来源：jdy-wrapper `GET /api/data-hub/forms/.../configs` → `workflow_config`。

- 节点数: **6**

## 拓扑

```
发起(0)
 ├─[外贸=是] → 外贸客户审批(2, 王玲玲) → 结束
 ├─[信息分发=是] → 信息分发(3, 对接人) → 跟进记录(4) → 结束
 │                              └→ 财务审批(1)
 └─[else] → 财务审批(1, 刘金花) → 结束
```

## 节点列表

| flowId | name | type | parents | 审批人 | 条件摘要 |
|--------|------|------|---------|--------|----------|
| -1 | 流程结束 | flow | [1, 2, 4] | - | `{"1": {}, "2": {}, "4": {"rel": "and", "cond": [], "isElse": false}}` |
| 0 | 流程发起节点 | flow | [] | - | `{}` |
| 1 | 财务审批 | flow | [0, 3] | 刘金花 | `{"0": {"isElse": true}, "3": {"rel": "and", "cond": [], "isElse": false}}` |
| 2 | 外贸客户审批 | flow | [0] | 王玲玲 | `{"0": {"rel": "and", "cond": [{"type": "text", "method": "eq", "value": ["是"]...` |
| 3 | 信息分发-客户 | flow | [0] | _widget_1667288061392 | `{"0": {"isElse": false, "rel": "and", "cond": [{"type": "text", "method": "eq...` |
| 4 | 跟进记录 | subflow | [3] | _widget_1667288061392 | `{"3": {"rel": "and", "cond": [], "isElse": false}}` |

## CRM 对齐

- 外贸字段 → `is_foreign_trade`
- 信息分发 → `need_info_distribute`
- 对接人 widget → `owner_id` (form_field_person)
- 财务 → 刘金花 (`finance_maint`)；外贸 → 王玲玲 (`export`)
- CRM 将「信息分发后并行跟进+财务」串行为：分发 → 跟进确认 → 财务
