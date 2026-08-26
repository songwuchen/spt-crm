import { PRICING_CHECKLIST_LINKS } from '@/constants/pricingChecklistLinks'

/** 生产卡「项目号选择251128」明细：选择安装图设计通知后带出的父级字段。 */
export const PROD_CARD_INSTALL_LINK_FIELD = 'prod_card_install'

export function prodCardInstallClearKeys(): string[] {
  return ['install_project_no']
}

/** 选合同后自动带出/清空：是否有安装图项目号 + 项目号选择251128 */
export function prodCardInstallAutoFillClearKeys(): string[] {
  return ['has_install_project', 'f_251128', ...prodCardInstallClearKeys()]
}

export function linkFillClearKeys(fieldId: string, fillMode?: string): string[] {
  if (fillMode === 'prod_card_install') return prodCardInstallClearKeys()
  if (fillMode === 'pricing_checklist') return PRICING_CHECKLIST_LINKS[fieldId]?.dests || []
  return []
}
