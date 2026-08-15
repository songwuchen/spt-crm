/** 按模块数据范围：与后端 data_scope_modules.SCOPE_MODULE_DEFS 对齐 */

export type ScopeModuleDef = { key: string; label: string; group: string }

export const SCOPE_MODULES: ScopeModuleDef[] = [
  { key: 'customer', label: '客户', group: '主数据' },
  { key: 'lead', label: '线索', group: '销售' },
  { key: 'project', label: '商机', group: '销售' },
  { key: 'quote', label: '报价', group: '销售' },
  { key: 'contract', label: '合同', group: '销售' },
  { key: 'solution', label: '方案', group: '销售' },
  { key: 'tender', label: '标书', group: '销售' },
  { key: 'order', label: '订单', group: '销售' },
  { key: 'delivery', label: '交付', group: '履约' },
  { key: 'payment', label: '回款', group: '履约' },
  { key: 'change', label: '变更', group: '履约' },
  { key: 'service', label: '工单', group: '售后与协作' },
  { key: 'task', label: '任务', group: '售后与协作' },
]

export const SCOPE_MODULE_GROUPS: string[] = [
  ...new Set(SCOPE_MODULES.map((m) => m.group)),
]
