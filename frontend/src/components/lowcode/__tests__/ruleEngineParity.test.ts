// 规则引擎前后端一致性用例（前端侧）。
// 与 backend/tests/test_rule_engine_parity.py 读同一份 shared/form_rule_parity_cases.json。
// 任一侧语义漂移都会在这里暴露 —— 漂移会导致「前端隐藏了该字段、后端仍报它必填」的死锁。
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'
import type { FieldDefinition, FieldPermission, FormRule } from '@/types/lowcode'
import { computeFieldStates } from '../RuleEngine'
import { validateRequired } from '../FormRenderer'

interface StateCase {
  name: string
  fields: FieldDefinition[]
  rules?: FormRule[]
  permissions?: FieldPermission[]
  values?: Record<string, unknown>
  expect: Record<string, Record<string, boolean>>
}
interface RequiredCase {
  name: string
  fields: FieldDefinition[]
  rules?: FormRule[]
  permissions?: FieldPermission[]
  values?: Record<string, unknown>
  expectError: boolean
}
interface OperatorCase {
  actual: unknown
  operator: string
  value: unknown
  expect: boolean
}

const cases = JSON.parse(
  readFileSync(resolve(__dirname, '../../../../../shared/form_rule_parity_cases.json'), 'utf-8'),
) as { states: StateCase[]; required: RequiredCase[]; operators: OperatorCase[] }

describe('rule engine parity — field states', () => {
  it.each(cases.states.map((c) => [c.name, c] as const))('%s', (_name, c) => {
    const states = computeFieldStates(c.fields, c.values || {}, c.rules || [], c.permissions)
    for (const [fieldId, expected] of Object.entries(c.expect)) {
      for (const [key, want] of Object.entries(expected)) {
        expect(states[fieldId][key as keyof typeof states[string]]).toBe(want)
      }
    }
  })
})

describe('rule engine parity — required validation', () => {
  it.each(cases.required.map((c) => [c.name, c] as const))('%s', (_name, c) => {
    const states = computeFieldStates(c.fields, c.values || {}, c.rules || [], c.permissions)
    const err = validateRequired(c.fields, states, c.values || {})
    expect(err !== null).toBe(c.expectError)
  })
})

describe('rule engine parity — operators', () => {
  it.each(cases.operators.map((c) => [`${JSON.stringify(c.actual)} ${c.operator} ${JSON.stringify(c.value)}`, c] as const))(
    '%s',
    (_name, c) => {
      // 借一条 visibility 规则把单个操作符的判定结果读出来
      const fields: FieldDefinition[] = [
        { id: 'f', type: 'text', label: 'F' } as FieldDefinition,
        { id: 't', type: 'text', label: 'T' } as FieldDefinition,
      ]
      const rules: FormRule[] = [{
        id: 'r1', type: 'visibility', target_field_id: 't',
        condition: { field: 'f', operator: c.operator, value: c.value },
        action: { visible: true },
      } as FormRule]
      const states = computeFieldStates(fields, { f: c.actual }, rules)
      expect(states.t.visible).toBe(c.expect)
    },
  )
})
