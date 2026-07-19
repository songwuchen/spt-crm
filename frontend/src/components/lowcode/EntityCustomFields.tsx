// 业务实体扩展字段面板: 加载该实体(customer/lead/...)的扩展字段 schema(系统表单模板),
// 用 FormRenderer 渲染。统一自定义字段到表单引擎;值仍存业务表 custom_fields_json。
// 可替代旧 CustomFieldsPanel,支持全部富字段类型(人员/部门/日期/金额/明细/公式等)。
import { forwardRef, useEffect, useImperativeHandle, useMemo, useState } from 'react'
import { Divider, Typography } from 'antd'
import { lowcodeApi } from '@/api/lowcode'
import { useAuthStore } from '@/stores/useAuthStore'
import type { FieldDefinition, FormRule } from '@/types/lowcode'
import { computeFieldStates } from './RuleEngine'
import FormRenderer, { deriveRolePerms, validateRequired } from './FormRenderer'

const { Text } = Typography

interface Props {
  entityType: string
  value?: Record<string, unknown>
  values?: Record<string, unknown>   // 兼容旧 CustomFieldsPanel 的 values 命名(可作别名直接替换)
  onChange?: (v: Record<string, unknown>) => void
  readOnly?: boolean
  title?: string
  /** 同一表单里原生字段的当前值。规则条件可引用原生字段(如「国别=国外时显示该扩展字段」)，
   *  不传则这类跨字段条件会因取不到值而判定为不成立。 */
  contextValues?: Record<string, unknown>
}

export interface EntityCustomFieldsRef {
  /** 校验扩展字段必填(含条件必填,跳过被规则隐藏的字段)。通过返回 null,否则返回首个错误文案。 */
  validate: () => string | null
}

/**
 * 业务表单里这样用，可在提交前拦住扩展字段的必填：
 *   const cfRef = useRef<EntityCustomFieldsRef>(null)
 *   const err = cfRef.current?.validate(); if (err) { message.error(err); return }
 */
const EntityCustomFields = forwardRef<EntityCustomFieldsRef, Props>(function EntityCustomFields(
  { entityType, value, values, onChange, readOnly, title = '扩展字段', contextValues }, ref,
) {
  const val = value ?? values
  const [fields, setFields] = useState<FieldDefinition[]>([])
  const [rules, setRules] = useState<FormRule[]>([])
  const [loaded, setLoaded] = useState(false)
  const userRoles = useAuthStore((s) => s.user?.roles) || []

  useEffect(() => {
    let alive = true
    lowcodeApi.entityFields(entityType)
      .then((r) => {
        if (!alive) return
        setFields(r.data.field_definitions || [])
        setRules(r.data.rule_definitions || [])
        setLoaded(true)
      })
      .catch(() => { if (alive) setLoaded(true) })
    return () => { alive = false }
  }, [entityType])

  // 与 FormRenderer 内部同口径地推导字段状态，供必填校验跳过「被规则隐藏」的字段。
  // 规则可能引用同一表单里的原生字段，故并入 contextValues 后再求值。
  const ruleValues = useMemo(
    () => ({ ...(contextValues || {}), ...(val || {}) }),
    [contextValues, val],
  )
  const states = useMemo(
    () => computeFieldStates(fields, ruleValues, rules, deriveRolePerms(fields, userRoles)),
    [fields, ruleValues, rules, userRoles],
  )

  useImperativeHandle(ref, () => ({
    validate: () => (readOnly ? null : validateRequired(fields, states, val || {})),
  }), [readOnly, fields, states, val])

  // 无扩展字段时不渲染(避免在业务表单里留空块)
  if (!loaded || fields.length === 0) return null

  return (
    <div>
      <Divider orientation="left" style={{ margin: '8px 0 16px' }}>
        <Text type="secondary" style={{ fontSize: 13 }}>{title}</Text>
      </Divider>
      <FormRenderer
        fields={fields}
        rules={rules}
        mode={readOnly ? 'readonly' : 'edit'}
        value={val || {}}
        ruleContext={contextValues}
        onChange={(v) => onChange?.(v)}
      />
    </div>
  )
})

export default EntityCustomFields
