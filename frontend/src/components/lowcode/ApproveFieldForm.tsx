/** 审批节点可填业务字段表单（对齐简道云 optAuth）。 */
import { useEffect, useState } from 'react'
import { Input, Radio, Space, Typography } from 'antd'
import type { WfCurrentTask, WfFieldPerm } from '@/types/lowcode'
import PersonField from '@/components/lowcode/fields/PersonField'

const { Text } = Typography

const RISK_OPTS = [
  { value: '高', label: '高' },
  { value: '中', label: '中' },
  { value: '低', label: '低' },
]
const YES_NO_OPTS = [
  { value: '是', label: '是' },
  { value: '否', label: '否' },
]

function isEmpty(v: unknown): boolean {
  if (v == null) return true
  if (typeof v === 'string' && !v.trim()) return true
  if (Array.isArray(v) && v.length === 0) return true
  return false
}

export function missingRequiredFields(
  fieldPerms: WfFieldPerm[] | undefined,
  values: Record<string, unknown>,
): string[] {
  return (fieldPerms || [])
    .filter((p) => p.access === 'required' && isEmpty(values[p.field]))
    .map((p) => p.field)
}

function FieldLabel({ label, required, error }: { label: string; required?: boolean; error?: boolean }) {
  return (
    <Text style={{ fontSize: 12, color: error ? '#cf1322' : undefined }}>
      {label}
      {required ? <span style={{ color: '#cf1322', marginLeft: 2 }}>*</span> : null}
    </Text>
  )
}

export default function ApproveFieldForm({
  currentTask,
  values,
  onChange,
  showTitle = true,
  highlightMissing = false,
}: {
  currentTask: WfCurrentTask
  values: Record<string, unknown>
  onChange: (next: Record<string, unknown>) => void
  /** 外层已有「本节点填写」标题时传 false，避免重复 */
  showTitle?: boolean
  /** 点击通过后高亮未填必填项 */
  highlightMissing?: boolean
}) {
  const metaById = Object.fromEntries((currentTask.field_meta || []).map((m) => [m.id, m]))
  const perms = currentTask.field_perms || []
  const [localHighlight, setLocalHighlight] = useState(highlightMissing)
  useEffect(() => { setLocalHighlight(highlightMissing) }, [highlightMissing])

  if (!perms.length) return null

  const setField = (id: string, v: unknown) => {
    onChange({ ...values, [id]: v })
  }

  const missing = new Set(
    localHighlight ? missingRequiredFields(perms, values) : [],
  )

  return (
    <div style={{ marginBottom: showTitle ? 12 : 0 }}>
      {showTitle && (
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
          本节点填写（{currentTask.node_name || '审批'}）
        </Text>
      )}
      <Space direction="vertical" style={{ width: '100%' }} size="small">
        {perms.map((p) => {
          const meta = metaById[p.field] || { id: p.field, label: p.field, type: 'text' as const }
          const required = p.access === 'required'
          const err = missing.has(p.field)
          const t = meta.type || 'text'
          const val = values[p.field]
          const status = err ? 'error' as const : undefined

          if (t === 'person' || t === 'user' || t === 'person_multi') {
            return (
              <div key={p.field} className={err ? 'approve-field-error' : undefined}>
                <FieldLabel label={meta.label} required={required} error={err} />
                <div style={{ marginTop: 4 }}>
                  <PersonField
                    value={val}
                    onChange={(v) => setField(p.field, v)}
                    multi={t === 'person_multi'}
                    placeholder={`请选择${meta.label}`}
                  />
                </div>
                {err && <Text type="danger" style={{ fontSize: 12 }}>请选择{meta.label}</Text>}
              </div>
            )
          }
          if (t === 'risk') {
            return (
              <div key={p.field}>
                <FieldLabel label={meta.label} required={required} error={err} />
                <Radio.Group
                  value={val as string | undefined}
                  options={RISK_OPTS}
                  onChange={(e) => setField(p.field, e.target.value)}
                  style={{ display: 'block', marginTop: 4 }}
                />
                {err && <Text type="danger" style={{ fontSize: 12 }}>请选择{meta.label}</Text>}
              </div>
            )
          }
          if (t === 'yes_no') {
            return (
              <div key={p.field}>
                <FieldLabel label={meta.label} required={required} error={err} />
                <Radio.Group
                  value={val as string | undefined}
                  options={YES_NO_OPTS}
                  onChange={(e) => setField(p.field, e.target.value)}
                  style={{ display: 'block', marginTop: 4 }}
                />
                {err && <Text type="danger" style={{ fontSize: 12 }}>请选择{meta.label}</Text>}
              </div>
            )
          }
          if (t === 'textarea') {
            return (
              <div key={p.field}>
                <FieldLabel label={meta.label} required={required} error={err} />
                <Input.TextArea
                  rows={2}
                  status={status}
                  value={(val as string) ?? ''}
                  onChange={(e) => setField(p.field, e.target.value)}
                  style={{ marginTop: 4 }}
                  placeholder={required ? `请填写${meta.label}` : undefined}
                />
                {err && <Text type="danger" style={{ fontSize: 12 }}>请填写{meta.label}</Text>}
              </div>
            )
          }
          return (
            <div key={p.field}>
              <FieldLabel label={meta.label} required={required} error={err} />
              <Input
                size="small"
                status={status}
                value={(val as string) ?? ''}
                onChange={(e) => setField(p.field, e.target.value)}
                style={{ marginTop: 4 }}
                placeholder={required ? `请填写${meta.label}` : undefined}
              />
              {err && <Text type="danger" style={{ fontSize: 12 }}>请填写{meta.label}</Text>}
            </div>
          )
        })}
      </Space>
      <style>{`
        .approve-field-error .ant-select-selector {
          border-color: #ff4d4f !important;
        }
      `}</style>
    </div>
  )
}
