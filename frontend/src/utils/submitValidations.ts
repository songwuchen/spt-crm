/** 审批节点提交校验（对齐简道云节点 validator / 后端 evaluate_submit_validations）。 */
import type { FieldDefinition } from '@/types/lowcode'
import { applySimpleFormulas } from '@/utils/lowcodeSimpleFormulas'

export type SubmitValidationRule = { formula: string; message?: string }

const FIELD_DIFF_EQ_ZERO_RE = /^\$([a-zA-Z0-9_]+)#\s*-\s*\$([a-zA-Z0-9_]+)#\s*==\s*0$/i

function toNum(v: unknown): number {
  if (v == null || v === '') return 0
  const n = Number(v)
  return Number.isFinite(n) ? n : 0
}

function amountsEqual(a: number, b: number, eps = 0.005): boolean {
  return Math.abs(a - b) <= eps
}

function evalRuleFormula(
  formula: string,
  values: Record<string, unknown>,
): boolean | null {
  const f = formula.trim()
  const diffZero = f.match(FIELD_DIFF_EQ_ZERO_RE)
  if (diffZero) {
    const left = toNum(values[diffZero[1]])
    const right = toNum(values[diffZero[2]])
    return amountsEqual(left, right)
  }
  return null
}

/** 返回第一条不满足规则的提示；全部通过返回 null。 */
export function evaluateSubmitValidations(
  rules: SubmitValidationRule[] | undefined,
  fields: FieldDefinition[],
  values: Record<string, unknown>,
): string | null {
  if (!rules?.length) return null
  const merged = applySimpleFormulas(fields, values)
  for (const rule of rules) {
    const formula = String(rule.formula || '').trim()
    if (!formula) continue
    const ok = evalRuleFormula(formula, merged)
    if (ok === null) continue
    if (!ok) {
      return (rule.message || '').trim() || '表单提交校验未通过'
    }
  }
  return null
}
