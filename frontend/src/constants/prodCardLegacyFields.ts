/** 简道云流程已废弃、CRM 全程不展示的生产卡字段。 */
export const PROD_CARD_LEGACY_HIDDEN_FIELD_IDS = new Set(['f_0414'])

/** 生产卡明细子表：启用「快速填报」（对齐简道云 subform quick_fill） */
export const PROD_CARD_QUICK_FILL_FIELD_IDS = new Set(['std_room_fill'])

/** 生产卡明细子表：业务已废弃、不再展示的列 */
export const PROD_CARD_DROPPED_DETAIL_COLUMNS: Record<string, readonly string[]> = {
  std_room_fill: ['theoretical_weight'],
  elec_workshop_fill: ['theoretical_weight_2'],
}

/** 生产卡明细子表：左侧显示简道云同款「序号」列（仅 UI，不入库） */
export const PROD_CARD_DETAIL_ROW_INDEX_FIELD_IDS = new Set([
  'std_room_fill',
  'elec_workshop_fill',
])

export function prodCardDetailShowsRowIndex(fieldId: string): boolean {
  return PROD_CARD_DETAIL_ROW_INDEX_FIELD_IDS.has(fieldId)
}

export function filterProdCardLegacyFieldPerms<T extends { field: string }>(perms: T[]): T[] {
  return perms.filter((p) => !PROD_CARD_LEGACY_HIDDEN_FIELD_IDS.has(p.field))
}

export function pruneProdCardDetailColumns<T extends { id?: string }>(
  fieldId: string,
  cols: T[] | undefined,
): T[] | undefined {
  const drop = PROD_CARD_DROPPED_DETAIL_COLUMNS[fieldId]
  if (!drop?.length || !cols?.length) return cols
  const dropSet = new Set(drop)
  return cols.filter((c) => c?.id && !dropSet.has(c.id))
}
