import { PRICING_CHECKLIST_LINKS } from '@/constants/pricingChecklistLinks'

/** 生产卡「项目号选择251128」明细：选择安装图设计通知后带出的父级字段。 */
export const PROD_CARD_INSTALL_LINK_FIELD = 'prod_card_install'

export function prodCardInstallClearKeys(): string[] {
  return ['install_project_no']
}

export function linkFillClearKeys(fieldId: string, fillMode?: string): string[] {
  if (fillMode === 'prod_card_install') return prodCardInstallClearKeys()
  if (fillMode === 'pricing_checklist') return PRICING_CHECKLIST_LINKS[fieldId]?.dests || []
  return []
}
