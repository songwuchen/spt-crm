/** 简道云流程已废弃、CRM 全程不展示的生产卡字段。 */
export const PROD_CARD_LEGACY_HIDDEN_FIELD_IDS = new Set(['f_0414'])

/** 生产卡明细子表：启用「快速填报」（对齐简道云 subform quick_fill） */
export const PROD_CARD_QUICK_FILL_FIELD_IDS = new Set(['std_room_fill'])

export function filterProdCardLegacyFieldPerms<T extends { field: string }>(perms: T[]): T[] {
  return perms.filter((p) => !PROD_CARD_LEGACY_HIDDEN_FIELD_IDS.has(p.field))
}
