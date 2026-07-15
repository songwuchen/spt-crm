// 动态表单渲染器 —— 按 FieldDefinition schema 渲染填报/只读表单。
// 移植/重写自 spt-lowcode FormRenderer,聚焦核心自足字段类型;人员/部门/附件等高级类型
// 暂以占位呈现(后续切片接入)。规则引擎(显隐/只读/必填)复用 RuleEngine。
import { useMemo } from 'react'
import {
  Row, Col, Input, InputNumber, DatePicker, Select, Radio, Checkbox, Switch,
  Button, Table, Typography, Tag, Empty,
} from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import type { FieldDefinition, FormRule, FieldState } from '@/types/lowcode'
import { computeFieldStates } from './RuleEngine'
import PersonField from './fields/PersonField'
import DeptField from './fields/DeptField'
import FileField from './fields/FileField'

const { TextArea } = Input
const { Text } = Typography

// 已完整支持的字段类型;其余类型以占位呈现。
const SUPPORTED = new Set([
  'text', 'textarea', 'number', 'amount', 'date', 'datetime',
  'select', 'multi_select', 'radio', 'checkbox', 'switch',
  'formula', 'auto_number', 'detail_table',
  'person', 'person_multi', 'department', 'department_multi', 'file', 'image',
])

// 这些类型自行渲染只读态(名称/URL 需异步解析),不走通用 ReadonlyValue。
const SELF_RENDER_READONLY = new Set([
  'detail_table', 'person', 'person_multi', 'department', 'department_multi', 'file', 'image',
])

const GROUP_TYPES = new Set(['tab_group', 'collapse_section'])

interface Props {
  fields: FieldDefinition[]
  rules?: FormRule[]
  mode?: 'edit' | 'readonly'
  value: Record<string, unknown>
  onChange?: (value: Record<string, unknown>) => void
}

export default function FormRenderer({ fields, rules = [], mode = 'edit', value, onChange }: Props) {
  const states = useMemo(() => computeFieldStates(fields, value, rules), [fields, value, rules])

  const setField = (id: string, v: unknown) => {
    onChange?.({ ...value, [id]: v })
  }

  const topFields = fields.filter((f) => !GROUP_TYPES.has(f.type))
  if (!topFields.length) return <Empty description="该表单暂无字段" />

  return (
    <Row gutter={16}>
      {topFields.map((field) => {
        const st = states[field.id]
        if (st && !st.visible) return null
        const span = field.span || 24
        // antd 24 栅格
        return (
          <Col span={span} key={field.id}>
            <FieldItem
              field={field}
              state={st}
              mode={mode}
              value={value[field.id]}
              allValues={value}
              onChange={(v) => setField(field.id, v)}
            />
          </Col>
        )
      })}
    </Row>
  )
}

function FieldItem({
  field, state, mode, value, allValues, onChange,
}: {
  field: FieldDefinition
  state?: FieldState
  mode: 'edit' | 'readonly'
  value: unknown
  allValues: Record<string, unknown>
  onChange: (v: unknown) => void
}) {
  const readonly = mode === 'readonly' || state?.readonly
  const required = state?.required
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ marginBottom: 4, fontSize: 13, color: 'rgba(0,0,0,0.75)' }}>
        {required && <span style={{ color: '#ff4d4f', marginRight: 4 }}>*</span>}
        {field.label}
        {field.description && (
          <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
            {field.description}
          </Text>
        )}
      </div>
      <FieldWidget field={field} readonly={!!readonly} value={value} allValues={allValues} onChange={onChange} />
    </div>
  )
}

function FieldWidget({
  field, readonly, value, allValues, onChange,
}: {
  field: FieldDefinition
  readonly: boolean
  value: unknown
  allValues: Record<string, unknown>
  onChange: (v: unknown) => void
}) {
  const opts = field.options || []
  const ph = field.placeholder

  if (!SUPPORTED.has(field.type)) {
    // 高级字段类型占位(后续切片接入): 只读展示已有值
    return (
      <div>
        {readonly ? <ReadonlyValue field={field} value={value} /> : (
          <Tag color="default">该字段类型「{field.type}」即将支持</Tag>
        )}
      </div>
    )
  }

  if (readonly && !SELF_RENDER_READONLY.has(field.type)) {
    return <ReadonlyValue field={field} value={value} />
  }

  switch (field.type) {
    case 'person':
    case 'person_multi':
      return <PersonField value={value} onChange={onChange} multi={field.type === 'person_multi'} readonly={readonly} placeholder={ph} />
    case 'department':
    case 'department_multi':
      return <DeptField value={value} onChange={onChange} multi={field.type === 'department_multi'} readonly={readonly} placeholder={ph} />
    case 'file':
      return <FileField value={value} onChange={onChange} readonly={readonly} />
    case 'image':
      return <FileField value={value} onChange={onChange} image readonly={readonly} />
    case 'text':
      return <Input value={value as string} placeholder={ph} onChange={(e) => onChange(e.target.value)} />
    case 'textarea':
      return <TextArea rows={3} value={value as string} placeholder={ph} onChange={(e) => onChange(e.target.value)} />
    case 'number':
      return <InputNumber style={{ width: '100%' }} value={value as number} placeholder={ph} onChange={(v) => onChange(v)} />
    case 'amount':
      return (
        <InputNumber
          style={{ width: '100%' }} value={value as number} placeholder={ph}
          precision={2} prefix="¥" min={0} onChange={(v) => onChange(v)}
        />
      )
    case 'date':
      return (
        <DatePicker
          style={{ width: '100%' }}
          value={value ? dayjs(value as string) : null}
          onChange={(d) => onChange(d ? d.format('YYYY-MM-DD') : null)}
        />
      )
    case 'datetime':
      return (
        <DatePicker
          style={{ width: '100%' }} showTime
          value={value ? dayjs(value as string) : null}
          onChange={(d) => onChange(d ? d.format('YYYY-MM-DD HH:mm:ss') : null)}
        />
      )
    case 'select':
      return (
        <Select
          style={{ width: '100%' }} allowClear value={(value as string) ?? undefined} placeholder={ph}
          options={opts} onChange={(v) => onChange(v)}
        />
      )
    case 'multi_select':
      return (
        <Select
          style={{ width: '100%' }} mode="multiple" allowClear value={(value as string[]) ?? []} placeholder={ph}
          options={opts} onChange={(v) => onChange(v)}
        />
      )
    case 'radio':
      return (
        <Radio.Group value={value} onChange={(e) => onChange(e.target.value)}>
          {opts.map((o) => <Radio key={o.value} value={o.value}>{o.label}</Radio>)}
        </Radio.Group>
      )
    case 'checkbox':
      return (
        <Checkbox.Group
          value={(value as string[]) ?? []}
          options={opts.map((o) => ({ label: o.label, value: o.value }))}
          onChange={(v) => onChange(v)}
        />
      )
    case 'switch':
      return <Switch checked={!!value} onChange={(v) => onChange(v)} />
    case 'formula':
    case 'auto_number':
      // 系统计算/生成字段: 只读展示(值由后端在提交时计算/生成)
      return <Input value={value == null ? '' : String(value)} disabled placeholder={field.type === 'auto_number' ? '提交后自动生成' : '自动计算'} />
    case 'detail_table':
      return <DetailTable field={field} readonly={readonly} value={value as Record<string, unknown>[]} onChange={onChange} />
    default:
      return <Input value={value as string} onChange={(e) => onChange(e.target.value)} />
  }
}

function ReadonlyValue({ field, value }: { field: FieldDefinition; value: unknown }) {
  const opts = field.options || []
  const labelOf = (v: unknown) => opts.find((o) => o.value === v)?.label ?? String(v ?? '')
  let display: React.ReactNode = ''
  if (value == null || value === '') display = <Text type="secondary">—</Text>
  else if (field.type === 'switch') display = value ? '是' : '否'
  else if (Array.isArray(value)) display = value.map(labelOf).join('，')
  else if (field.type === 'select' || field.type === 'radio') display = labelOf(value)
  else if (field.type === 'amount') display = `¥${Number(value).toFixed(2)}`
  else display = String(value)
  return <div style={{ paddingTop: 4, minHeight: 22 }}>{display}</div>
}

// ===== 明细子表 =====

function DetailTable({
  field, readonly, value, onChange,
}: {
  field: FieldDefinition
  readonly: boolean
  value: Record<string, unknown>[] | undefined
  onChange: (v: unknown) => void
}) {
  const rows = Array.isArray(value) ? value : []
  const cols = field.detail_table_columns || []

  const setCell = (rowIdx: number, colId: string, v: unknown) => {
    const next = rows.map((r, i) => (i === rowIdx ? { ...r, [colId]: v } : r))
    onChange(next)
  }
  const addRow = () => onChange([...rows, {}])
  const delRow = (idx: number) => onChange(rows.filter((_, i) => i !== idx))

  const columns = [
    ...cols.map((c) => ({
      title: (<span>{c.required && <span style={{ color: '#ff4d4f' }}>*</span>}{c.label}</span>),
      dataIndex: c.id,
      key: c.id,
      render: (_: unknown, _row: Record<string, unknown>, idx: number) => (
        <FieldWidget
          field={c} readonly={readonly}
          value={rows[idx]?.[c.id]} allValues={rows[idx] || {}}
          onChange={(v) => setCell(idx, c.id, v)}
        />
      ),
    })),
    ...(readonly ? [] : [{
      title: '操作', key: '__op', width: 70,
      render: (_: unknown, _row: Record<string, unknown>, idx: number) => (
        <Button type="text" danger size="small" icon={<DeleteOutlined />} onClick={() => delRow(idx)} />
      ),
    }]),
  ]

  return (
    <div>
      <Table
        size="small" rowKey={(_, i) => String(i)} pagination={false}
        dataSource={rows} columns={columns as never}
        locale={{ emptyText: '暂无明细' }}
      />
      {!readonly && (
        <Button type="dashed" block icon={<PlusOutlined />} style={{ marginTop: 8 }} onClick={addRow}>
          添加一行
        </Button>
      )}
    </div>
  )
}

// 客户端必填校验(即时反馈;后端仍会二次校验)。返回首个错误或 null。
export function validateRequired(
  fields: FieldDefinition[],
  states: Record<string, FieldState>,
  values: Record<string, unknown>,
): string | null {
  const empty = (v: unknown) => v == null || v === '' || (Array.isArray(v) && v.length === 0)
  for (const f of fields) {
    if (f.type === 'formula' || f.type === 'auto_number') continue
    const st = states[f.id]
    if (st && !st.visible) continue
    const req = st ? st.required : f.required
    if (req && empty(values[f.id])) return `「${f.label}」为必填项`
    if (f.type === 'detail_table') {
      const rows = values[f.id]
      const reqCols = (f.detail_table_columns || []).filter((c) => c.required)
      if (Array.isArray(rows) && reqCols.length) {
        for (let i = 0; i < rows.length; i++) {
          for (const c of reqCols) {
            if (empty((rows[i] as Record<string, unknown>)?.[c.id])) return `「${f.label}」第 ${i + 1} 行「${c.label}」为必填项`
          }
        }
      }
    }
  }
  return null
}
