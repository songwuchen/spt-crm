import { describe, expect, it } from 'vitest'
import type { FieldDefinition, WfRoute } from '@/types/lowcode'
import {
  condHumanLabel, routeEdgeLabel, truncateLabel, edgeStroke,
} from '@/utils/wfCanvasEdgeLabel'

const fields: FieldDefinition[] = [
  { id: 'field_2', label: '区域经理/组长', type: 'person' },
  { id: 'field_3', label: '是否是小萌', type: 'radio', options: [
    { label: '是', value: '是' }, { label: '否', value: '否' },
  ] },
  { id: 'field', label: '所属部门', type: 'department' },
]

describe('wfCanvasEdgeLabel', () => {
  it('translates region not-empty like JDY', () => {
    const text = condHumanLabel(
      { rel: 'and', cond: [{ field: 'field_2', operator: 'is_not_empty' }] },
      fields,
    )
    expect(text).toBe('区域经理/组长不为空')
  })

  it('joins and-conditions with 且', () => {
    const text = condHumanLabel({
      rel: 'and',
      cond: [
        { field: 'field_3', operator: 'in', value: ['否'] },
        { field: 'field_2', operator: 'is_not_empty' },
      ],
    }, fields)
    expect(text).toBe('是否是小萌=否 且 区域经理/组长不为空')
  })

  it('truncates long labels but keeps full title', () => {
    const long = '所属部门属于新疆域基和国际贸易等特别长的部门名单以及其它'
    const { text, title } = truncateLabel(long, 24)
    expect(text.length).toBeLessThanOrEqual(24)
    expect(title).toBe(long)
  })

  it('labels start exclusive else as else', () => {
    const routes: WfRoute[] = [
      {
        id: 'r1', source: 'start', target: 'n22', exclusive_group: 'ex_start',
        condition: { rel: 'and', cond: [{ field: 'field_2', operator: 'is_not_empty' }] },
      },
      { id: 'r2', source: 'start', target: 'n1', exclusive_group: 'ex_start' },
    ]
    const lab = routeEdgeLabel(routes[1], routes, fields)
    expect(lab?.text).toBe('else')
    expect(edgeStroke(routes[0])).toBe('#7c3aed')
    expect(edgeStroke(routes[1])).toBe('#94a3b8')
  })
})
