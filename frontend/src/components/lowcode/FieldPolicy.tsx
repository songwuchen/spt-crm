// 业务表单的「字段策略」：让原生字段(业务表内置列)也能被租户配置必填/条件显隐/只读/角色权限。
//
// 设计取舍：不把业务表单整体换成 FormRenderer —— 线索/客户等表单里有 RegionCascader、
// 产品明细子表、负责人远程搜索这类定制控件，换掉风险大收益小。改为「注入式」：
// 用 <FieldPolicyProvider> 包住表单，把每个 Form.Item 换成 <PolicyItem>，由 Provider 算出的
// 状态自动注入 required 校验规则、隐藏、以及只读。改造是机械的，可逐页推进。
//
// 规则在「原生值 + 扩展字段值」的合集上求值，所以条件可以跨两类字段互相引用
// （例如「国别=国外时显示扩展字段 报关方式」）。后端 field_permission.enforce_native_field_policy
// 用同一份 schema 和同一套规则引擎再算一遍 —— 前端只是 UX，后端才是权威边界。
import {
  cloneElement, createContext, isValidElement, useContext, useEffect, useMemo, useState,
  type ReactNode,
} from 'react'
import { Form } from 'antd'
import type { FormItemProps } from 'antd'
import { lowcodeApi } from '@/api/lowcode'
import { useAuthStore } from '@/stores/useAuthStore'
import type { FieldDefinition, FieldState, FormRule } from '@/types/lowcode'
import { computeFieldStates } from './RuleEngine'
import { deriveRolePerms } from './FormRenderer'

interface PolicyValue {
  loaded: boolean
  nativeFields: FieldDefinition[]
  customFields: FieldDefinition[]
  rules: FormRule[]
  states: Record<string, FieldState>
  /** 该字段的显示名（租户可覆盖），无覆盖时返回 undefined 让调用方用自己的默认值。 */
  labelOf: (fieldId: string) => string | undefined
}

const EMPTY: PolicyValue = {
  loaded: false, nativeFields: [], customFields: [], rules: [], states: {},
  labelOf: () => undefined,
}

const FieldPolicyContext = createContext<PolicyValue>(EMPTY)

export function useFieldPolicy() {
  return useContext(FieldPolicyContext)
}

/**
 * 拉取实体字段策略并按当前表单值算出各字段状态。
 * values 应包含原生字段值与扩展字段值（扩展字段值展开在同一层，与后端求值口径一致）。
 */
export function FieldPolicyProvider({
  entityType, values, children,
}: {
  entityType: string
  values: Record<string, unknown>
  children: ReactNode
}) {
  const [schema, setSchema] = useState<{
    native: FieldDefinition[]; custom: FieldDefinition[]; rules: FormRule[]
  }>({ native: [], custom: [], rules: [] })
  const [loaded, setLoaded] = useState(false)
  const userRoles = useAuthStore((s) => s.user?.roles) || []

  useEffect(() => {
    let alive = true
    lowcodeApi.entityFormSchema(entityType)
      .then((r) => {
        if (!alive) return
        setSchema({
          native: r.data.native_fields || [],
          custom: r.data.field_definitions || [],
          rules: r.data.rule_definitions || [],
        })
        setLoaded(true)
      })
      // 策略拉取失败时静默降级为「无策略」，表单仍可正常使用（后端仍会兜底校验）
      .catch(() => { if (alive) setLoaded(true) })
    return () => { alive = false }
  }, [entityType])

  const value = useMemo<PolicyValue>(() => {
    const all = [...schema.native, ...schema.custom]
    const states = computeFieldStates(all, values, schema.rules, deriveRolePerms(all, userRoles))
    // 只收租户真正改过的标签(label_override)。native 字段的 label 始终有目录默认值，
    // 若拿它覆盖业务表单的 JSX 标签，会在租户什么都没配时就把既有文案改掉。
    const labels = new Map(
      schema.native
        .filter((f) => typeof f.label_override === 'string' && f.label_override.trim())
        .map((f) => [f.id, f.label_override as string]),
    )
    return {
      loaded,
      nativeFields: schema.native,
      customFields: schema.custom,
      rules: schema.rules,
      states,
      labelOf: (fieldId: string) => labels.get(fieldId),
    }
  }, [schema, values, userRoles, loaded])

  return <FieldPolicyContext.Provider value={value}>{children}</FieldPolicyContext.Provider>
}

type PolicyItemProps = FormItemProps & {
  /** 原生字段 id，必须与后端 native_field_catalog 里的 id 一致（即业务表列名）。 */
  name: string
}

/**
 * 感知字段策略的 Form.Item：自动注入必填规则、按规则隐藏、只读时禁用输入控件。
 * 没有 Provider 或该字段无策略时，行为与原生 Form.Item 完全一致（可安全逐个替换）。
 */
export function PolicyItem({ name, rules, label, children, ...rest }: PolicyItemProps) {
  const policy = useFieldPolicy()
  const state = policy.states[name]

  // 策略还没加载完就先按「无策略」渲染，避免必填星号闪烁
  if (!policy.loaded || !state) {
    return <Form.Item name={name} rules={rules} label={label} {...rest}>{children}</Form.Item>
  }

  if (!state.visible) return null

  const overriddenLabel = policy.labelOf(name)
  const finalLabel = overriddenLabel ?? label
  const merged = [...(rules || [])]
  // 判重要看「是否已有一条真的在要求必填」，而不是「有没有 required 这个键」——
  // 否则调用方写 {required:false} 会把租户配的必填悄悄抑制掉
  if (state.required && !merged.some((r) => typeof r === 'object' && r !== null && (r as { required?: boolean }).required === true)) {
    merged.push({ required: true, message: `请填写${typeof finalLabel === 'string' ? finalLabel : ''}` })
  }

  return (
    <Form.Item name={name} rules={merged} label={finalLabel} {...rest}>
      {state.readonly && isValidElement(children)
        ? cloneElement(children as React.ReactElement<{ disabled?: boolean }>, { disabled: true })
        : children}
    </Form.Item>
  )
}
