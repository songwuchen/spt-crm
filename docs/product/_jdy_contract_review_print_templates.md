# 合同评审 — 简道云打印模板对照

> 核对来源：`docs/product/_jdy_contract_review_edit_raw.json`（entry `5de0b58e8edfae0006cb571a`）

| 项 | 值 |
|---|---|
| 应用 | 销售中心 `5de0b3e85600ec0006f420f2` |
| 表单 | 260810-合同评审 `5de0b58e8edfae0006cb571a` |
| 流水号规则 | `HTPS` + `yyyyMMdd` + 5 位月序 |

## printList

| 模板 ID | 名称 | 说明 |
|---------|------|------|
| `system` | **系统打印** | 简道云默认系统打印（按表单可见字段排版） |

**与技术协议 HTJSXY 不同**：合同评审**没有**类似 `20230517112920525` 的自定义 table 打印模板；流程节点 `printIds` 亦为空，权限组仅配置「系统打印 / 批量打印」。

## CRM 对齐策略

- 版式：A4 竖版表格 + 表头（提交人 / 日期 / 流水号）+ 各业务分区字段 + **审批意见**（倒序、虚线分隔、无意见显示「无」）。
- 字段：按 `CONTRACT_REVIEW_SECTIONS` 与 `reviewDepVisible` 规则，与详情只读一致。
- 附件：成本附件、附件/图片、反馈附件/图片。
- 子表：联系人明细（合同评审）。

## layout API

尝试拉取 `print/system` 返回 404（系统打印无独立 layout 配置端点）；字段顺序以表单 `edit_raw.content.items` 为准。
