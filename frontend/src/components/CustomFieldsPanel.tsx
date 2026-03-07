import { useState, useEffect } from 'react'
import { Input, InputNumber, DatePicker, Select, Switch, Button, message } from 'antd'
import { settingsApi } from '@/api/settings'
import dayjs from 'dayjs'

interface FieldDef {
  id: string
  entity_type: string
  field_key: string
  field_label: string
  field_type: string
  options_json?: string[]
  required: boolean
  sort_order: number
  enabled: boolean
}

interface Props {
  entityType: string
  values: Record<string, unknown> | null | undefined
  onChange?: (values: Record<string, unknown>) => void
  readOnly?: boolean
}

export default function CustomFieldsPanel({ entityType, values, onChange, readOnly }: Props) {
  const [fields, setFields] = useState<FieldDef[]>([])
  const [localValues, setLocalValues] = useState<Record<string, unknown>>(values || {})

  useEffect(() => {
    settingsApi.listCustomFields({ entity_type: entityType })
      .then((r: any) => setFields((r.data || []).filter((f: FieldDef) => f.enabled)))
      .catch(() => {})
  }, [entityType])

  useEffect(() => {
    setLocalValues(values || {})
  }, [values])

  if (fields.length === 0) return null

  const handleChange = (key: string, val: unknown) => {
    const next = { ...localValues, [key]: val }
    setLocalValues(next)
    onChange?.(next)
  }

  return (
    <div className="space-y-3">
      <div className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">自定义字段</div>
      {fields.map((f) => {
        const val = localValues[f.field_key]
        return (
          <div key={f.id} className="flex items-start gap-3">
            <span className="text-sm text-slate-600 w-28 shrink-0 pt-1 text-right">
              {f.field_label}
              {f.required && <span className="text-red-500 ml-0.5">*</span>}
            </span>
            <div className="flex-1">
              {readOnly ? (
                <span className="text-sm text-slate-800">
                  {val != null ? (f.field_type === 'boolean' ? (val ? '是' : '否') : String(val)) : '-'}
                </span>
              ) : (
                <>
                  {f.field_type === 'text' && (
                    <Input size="small" value={(val as string) || ''} onChange={(e) => handleChange(f.field_key, e.target.value)} />
                  )}
                  {f.field_type === 'number' && (
                    <InputNumber size="small" className="w-full" value={val as number} onChange={(v) => handleChange(f.field_key, v)} />
                  )}
                  {f.field_type === 'date' && (
                    <DatePicker size="small" className="w-full" value={val ? dayjs(val as string) : null}
                      onChange={(d) => handleChange(f.field_key, d ? d.format('YYYY-MM-DD') : null)} />
                  )}
                  {f.field_type === 'select' && (
                    <Select size="small" className="w-full" value={val as string} allowClear
                      onChange={(v) => handleChange(f.field_key, v)}
                      options={(f.options_json || []).map((o) => ({ label: o, value: o }))} />
                  )}
                  {f.field_type === 'multiselect' && (
                    <Select size="small" className="w-full" mode="multiple" value={(val as string[]) || []}
                      onChange={(v) => handleChange(f.field_key, v)}
                      options={(f.options_json || []).map((o) => ({ label: o, value: o }))} />
                  )}
                  {f.field_type === 'boolean' && (
                    <Switch size="small" checked={!!val} onChange={(v) => handleChange(f.field_key, v)} />
                  )}
                </>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
