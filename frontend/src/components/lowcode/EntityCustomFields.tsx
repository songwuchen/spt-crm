// 业务实体扩展字段面板: 加载该实体(customer/lead/...)的扩展字段 schema(系统表单模板),
// 用 FormRenderer 渲染。统一自定义字段到表单引擎;值仍存业务表 custom_fields_json。
// 可替代旧 CustomFieldsPanel,支持全部富字段类型(人员/部门/日期/金额/明细/公式等)。
import { useEffect, useState } from 'react'
import { Divider, Typography } from 'antd'
import { lowcodeApi } from '@/api/lowcode'
import type { FieldDefinition } from '@/types/lowcode'
import FormRenderer from './FormRenderer'

const { Text } = Typography

interface Props {
  entityType: string
  value?: Record<string, unknown>
  onChange?: (v: Record<string, unknown>) => void
  readOnly?: boolean
  title?: string
}

export default function EntityCustomFields({ entityType, value, onChange, readOnly, title = '扩展字段' }: Props) {
  const [fields, setFields] = useState<FieldDefinition[]>([])
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    let alive = true
    lowcodeApi.entityFields(entityType)
      .then((r) => { if (alive) { setFields(r.data.field_definitions || []); setLoaded(true) } })
      .catch(() => { if (alive) setLoaded(true) })
    return () => { alive = false }
  }, [entityType])

  // 无扩展字段时不渲染(避免在业务表单里留空块)
  if (!loaded || fields.length === 0) return null

  return (
    <div>
      <Divider orientation="left" style={{ margin: '8px 0 16px' }}>
        <Text type="secondary" style={{ fontSize: 13 }}>{title}</Text>
      </Divider>
      <FormRenderer
        fields={fields}
        mode={readOnly ? 'readonly' : 'edit'}
        value={value || {}}
        onChange={(v) => onChange?.(v)}
      />
    </div>
  )
}
