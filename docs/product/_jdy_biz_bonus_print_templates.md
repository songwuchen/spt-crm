# 业务奖金流转单 — 打印模板对照

> 简道云 app=`56ca77ce1efc301d279b8a4d`  
> CRM 实现：`frontend/src/pages/bonus/bizBonusPrint.ts` → HTML → PDF 预览

## 简道云模板

| 模板 ID | 名称 | CRM mode |
|---------|------|----------|
| `20200418135646149` | 业务奖金流转单（A4） | `a4` |
| `20230624111634952` | 业务奖金流转单(三等分）A4横向1 | `triplicate_landscape`（默认） |
| `20200619105548018` | 业务奖金流转单(三等分）纵向 | `triplicate_portrait` |
| `20230624141143130` | 未命名模板（Word） | 未迁移（无 layout dump） |

适用表单：

- `biz_bonus_transfer` — 业务奖金流转单
- `biz_bonus_biz_initiate` — 业务奖金流转—业务发起

流程节点从「部门审批」起 `allowPrint=true` → CRM `node_actions.submit_print=true`。

## 使用入口

- 列表详情工具栏：**打印** 下拉三版式
- 审批抽屉：**打印**（部门审批、财务审核、总经理审批等节点，与「通过」分开操作）

## 版式说明

- **A4 纵向**：完整字段 + 合同/来款明细 + 审批意见 + 签字栏
- **三等分 A4 横向**：同内容复制 3 份，横向并排（财务留底常用）
- **三等分纵向**：同内容复制 3 份，纵向叠放

## 备注

简道云 print layout API 返回 404，CRM 按字段 slug 手工排版对齐业务口径；若客户 Word 模板有差异可再微调 CSS。
