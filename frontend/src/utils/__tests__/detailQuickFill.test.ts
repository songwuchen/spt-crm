import { describe, expect, it } from 'vitest'
import { columnsToFieldSpecs } from '@/components/ContractTerms'
import { FALLBACK_LINE_COLUMNS } from '@/constants/contractDetailTables'
import {
  applyPasteToGrid,
  coerceCellValue,
  getPasteableFields,
  gridToRows,
  parseClipboardText,
  validateQuickFillRows,
  detailColumnsToQuickFillSpecs,
} from '@/utils/detailQuickFill'

const fields = columnsToFieldSpecs(FALLBACK_LINE_COLUMNS)

describe('detailQuickFill', () => {
  it('明细列排除人员/附件等不宜粘贴类型', () => {
    const specs = detailColumnsToQuickFillSpecs([
      { id: 'a', type: 'text', label: '物料代码' },
      { id: 'b', type: 'person', label: '设计人' },
      { id: 'c', type: 'number', label: '数量' },
    ] as never)
    expect(specs.map((s) => s.key)).toEqual(['a', 'c'])
  })

  it('排除计算列', () => {
    const pasteable = getPasteableFields(fields)
    expect(pasteable.map((f) => f.key)).not.toContain('amount')
    expect(pasteable.map((f) => f.key)).not.toContain('fx_amount')
    expect(pasteable.map((f) => f.key)).toContain('name')
  })

  it('解析 Excel 制表符粘贴', () => {
    expect(parseClipboardText('A\tB\n1\t2')).toEqual([['A', 'B'], ['1', '2']])
  })

  it('下拉/单选按 label 匹配', () => {
    const fx = fields.find((f) => f.key === 'is_fx')!
    expect(coerceCellValue(fx, '是')).toBe('是')
    const pt = fields.find((f) => f.key === 'product_type')!
    expect(coerceCellValue(pt, '复频筛')).toBe('复频筛')
  })

  it('网格转行并过滤空行', () => {
    const pasteable = getPasteableFields(fields)
    const rows = gridToRows([
      ['否', '复频筛', '筛机A', 'GF-1', '台', '2', '10000', '', ''],
      ['', '', '', '', '', '', '', '', ''],
    ], pasteable)
    expect(rows).toHaveLength(1)
    expect(rows[0].name).toBe('筛机A')
    expect(rows[0].qty).toBe(2)
    expect(rows[0].price).toBe(10000)
  })

  it('粘贴覆盖网格指定起点', () => {
    const grid = [['', ''], ['', '']]
    const next = applyPasteToGrid(grid, [['X', 'Y']], 1, 0)
    expect(next[1]).toEqual(['X', 'Y'])
  })

  it('校验未知选项', () => {
    const rows = [{ product_type: '不存在的产品' }]
    const issues = validateQuickFillRows(rows, fields)
    expect(issues.some((i) => i.field === 'product_type')).toBe(true)
  })
})
