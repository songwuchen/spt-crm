// 业务表单的「字段策略」：让原生字段(业务表内置列)也能被租户配置必填/条件显隐/脱敏/只读/角色权限。
//
// 设计取舍：不把业务表单整体换成 FormRenderer —— 各业务表单里有 RegionCascader、明细子表、
// 远程搜索选择器这类定制控件，换掉风险大收益小。改为「注入式」：用 <FieldPolicyProvider>
// 包住表单，把每个 Form.Item 换成 <PolicyItem>，由 Provider 算出的状态自动注入必填校验、
// 隐藏与只读。改造是机械的，可逐页推进。
//
// 接一个新表单只要三步：
//   1. <FieldPolicyProvider entityType="xxx" form={form} customFieldValues={customFields}> 包住 <Form>
//   2. 原生字段的 <Form.Item name="col"> 改成 <PolicyItem name="col">
//   3. onFinish 开头调一次 customFieldsRef.current?.validate()
// 表单值的订阅、原生值与扩展值的合并，都在 Provider 内部完成，页面不必再自己接。
//
// 规则在「原生值 + 扩展字段值」的合集上求值，所以条件可以跨两类字段互相引用
// （例如「国别=国外时显示扩展字段 报关方式」）。后端 field_permission.enforce_native_field_policy
// 用同一份 schema 和同一套规则引擎再算一遍 —— 前端只是 UX，后端才是权威边界。
import {
  cloneElement, createContext, isValidElement, useContext, useEffect, useMemo, useState,
  type ReactNode,
} from 'react'
import { Form } from 'antd'
import type { FormInstance, FormItemProps } from 'antd'
import { lowcodeApi } from '@/api/lowcode'
import { useAuthStore } from '@/stores/useAuthStore'
import type { FieldDefinition, FieldState, FormRule } from '@/types/lowcode'
import { computeFieldStates } from './RuleEngine'
import { deriveRolePerms } from './FormRenderer'

/** 递归收集规则条件里引用到的字段 id（含 and/or 嵌套组）。 */
function collectRuleFieldIds(rules: FormRule[]): string[] {
  const out = new Set<string>()
  const walk = (node: unknown) => {
    if (!node || typeof node !== 'object') return
    const n = node as { field?: unknown; cond?: unknown[] }
    if (typeof n.field === 'string') out.add(n.field)
    if (Array.isArray(n.cond)) n.cond.forEach(walk)
  }
  for (const r of rules || []) walk(r.condition)
  return [...out]
}

interface PolicyValue {
  loaded: boolean
  /** 策略拉取失败（网络/鉴权/5xx）。此时应保留调用方自带的校验规则作兜底，
   *  否则客户端校验会整个消失，用户只能撞到服务端错误。 */
  failed: boolean
  nativeFields: FieldDefinition[]
  customFields: FieldDefinition[]
  rules: FormRule[]
  states: Record<string, FieldState>
  /** 原生字段的当前值，供扩展字段面板做跨字段规则求值。 */
  nativeValues: Record<string, unknown>
  /** 该字段的显示名 —— 仅当租户确实改过标签时才有值，否则返回 undefined 让调用方用自己的。 */
  labelOf: (fieldId: string) => string | undefined
}

const EMPTY: PolicyValue = {
  // 没有 Provider 时按「拉取失败」处理：调用方的规则原样生效，行为与改造前一致
  loaded: false, failed: true, nativeFields: [], customFields: [], rules: [], states: {},
  nativeValues: {}, labelOf: () => undefined,
}

const FieldPolicyContext = createContext<PolicyValue>(EMPTY)

export function useFieldPolicy() {
  return useContext(FieldPolicyContext)
}

export function FieldPolicyProvider({
  entityType, form, customFieldValues, children,
}: {
  entityType: string
  /** 业务表单实例；Provider 内部订阅它的全部值用于规则求值。 */
  form: FormInstance
  /** 扩展字段当前值（存于业务表 custom_fields_json）。 */
  customFieldValues?: Record<string, unknown>
  children: ReactNode
}) {
  const [schema, setSchema] = useState<{
    native: FieldDefinition[]; custom: FieldDefinition[]; rules: FormRule[]
  }>({ native: [], custom: [], rules: [] })
  const [loaded, setLoaded] = useState(false)
  const [failed, setFailed] = useState(false)
  const userRoles = useAuthStore((s) => s.user?.roles) || []
  const watched = Form.useWatch([], form) as Record<string, unknown> | undefined

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
      // 拉取失败时降级为「无策略」，并标记 failed 让 PolicyItem 保留调用方自带的规则
      .catch(() => { if (alive) { setFailed(true); setLoaded(true) } })
    return () => { alive = false }
  }, [entityType])

  // 只有「规则条件真正引用到的字段」的值变化才需要重算状态。Form.useWatch([]) 每次击键
  // 都会返回新对象，若直接用它做依赖，18 个字段的表单每敲一个字符就重跑一遍显隐不动点
  // 求解并刷新 context，导致所有 PolicyItem 连带重渲染。
  const ruleFieldIds = useMemo(() => collectRuleFieldIds(schema.rules), [schema.rules])
  const relevantKey = useMemo(() => {
    if (!ruleFieldIds.length) return ''
    const w = watched || {}
    return JSON.stringify(ruleFieldIds.map((id) => w[id] ?? null))
  }, [ruleFieldIds, watched])

  const value = useMemo<PolicyValue>(() => {
    const nativeValues = watched || {}
    const all = [...schema.native, ...schema.custom]
    const merged = { ...nativeValues, ...(customFieldValues || {}) }
    const states = computeFieldStates(all, merged, schema.rules, deriveRolePerms(all, userRoles))
    // 只收租户真正改过的标签(label_override)。native 字段的 label 始终有目录默认值，
    // 若拿它覆盖业务表单的 JSX 标签，会在租户什么都没配时就把既有文案改掉。
    const labels = new Map(
      schema.native
        .filter((f) => typeof f.label_override === 'string' && f.label_override.trim())
        .map((f) => [f.id, f.label_override as string]),
    )
    return {
      loaded,
      failed,
      nativeFields: schema.native,
      customFields: schema.custom,
      rules: schema.rules,
      states,
      nativeValues,
      labelOf: (fieldId: string) => labels.get(fieldId),
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [schema, relevantKey, customFieldValues, userRoles, loaded, failed])

  return <FieldPolicyContext.Provider value={value}>{children}</FieldPolicyContext.Provider>
}

type PolicyItemProps = FormItemProps & {
  /** 原生字段 id，必须与后端 native_field_catalog 里的 id 一致（即业务表列名）。 */
  name: string
}

/**
 * 感知字段策略的 Form.Item：自动注入必填规则、按规则隐藏、只读/脱敏时禁用输入控件。
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

  const finalLabel = policy.labelOf(name) ?? label
  // 策略已知时它说了算：调用方 JSX 里硬编码的 {required:true} 只是「策略拉不到时的兜底」，
  // 不能压过租户在设计器里「关掉必填」的配置 —— 否则后端放行了、前端还拦着。
  // 反过来，策略未加载或拉取失败时保留调用方规则，避免客户端校验整个消失。
  const isRequiredRule = (r: unknown) =>
    typeof r === 'object' && r !== null && (r as { required?: boolean }).required === true
  const merged = policy.failed ? [...(rules || [])] : (rules || []).filter((r) => !isRequiredRule(r))
  // 脱敏字段不注入必填：用户看不到明文，无从填写。
  if (state.required && !state.masked) {
    merged.push({ required: true, message: `请填写${typeof finalLabel === 'string' ? finalLabel : ''}` })
  }

  // 脱敏字段一律禁用输入：后端已把值换成 "***"，让它可编辑等于允许把 "***" 存回真实列
  const disabled = state.readonly || state.masked
  return (
    <Form.Item name={name} rules={merged} label={finalLabel} {...rest}>
      {disabled && isValidElement(children)
        ? cloneElement(children as React.ReactElement<{ disabled?: boolean }>, { disabled: true })
        : children}
    </Form.Item>
  )
}
