import { useEffect, useState } from 'react'
import { Drawer, Select, Input, InputNumber, DatePicker, Button, Radio, Empty } from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import type { SchemaField, FilterDsl, FilterRule } from '@/api/searchSchema'
import { OP_LABELS, valueKind, RELATIVE_OPTIONS } from './operators'
import { useRemoteSelect } from '@/hooks/useRemoteSelect'
import { userApi } from '@/api/user'
import { customerApi } from '@/api/customer'
import { departmentApi } from '@/api/department'

const { RangePicker } = DatePicker

interface Props {
  open: boolean
  onClose: () => void
  fields: SchemaField[]
  value: FilterDsl | null
  onApply: (dsl: FilterDsl | null) => void
}

interface Row {
  field: string
  op: string
  value?: unknown
}

const DATE_TYPES = ['date', 'datetime']

export default function AdvancedFilter({ open, onClose, fields, value, onApply }: Props) {
  const [match, setMatch] = useState<'all' | 'any'>('all')
  const [rows, setRows] = useState<Row[]>([])

  useEffect(() => {
    if (open) {
      setMatch(value?.match || 'all')
      setRows(value?.rules?.length ? value.rules.map((r) => ({ ...r })) : [])
    }
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  const fieldOf = (key: string) => fields.find((f) => f.key === key)

  const addRow = () => {
    const f = fields[0]
    if (!f) return
    setRows((prev) => [...prev, { field: f.key, op: f.operators[0], value: undefined }])
  }

  const removeRow = (i: number) => setRows((prev) => prev.filter((_, idx) => idx !== i))

  const patchRow = (i: number, patch: Partial<Row>) =>
    setRows((prev) => prev.map((r, idx) => (idx === i ? { ...r, ...patch } : r)))

  const onFieldChange = (i: number, key: string) => {
    const f = fieldOf(key)
    patchRow(i, { field: key, op: f?.operators[0] || 'eq', value: undefined })
  }

  const handleApply = () => {
    // 去掉无效行：需要值但没填的
    const clean = rows.filter((r) => {
      if (!r.field || !r.op) return false
      const kind = valueKind(r.op)
      if (kind === 'none') return true
      if (kind === 'pair') return Array.isArray(r.value) && r.value.length === 2 && r.value[0] != null && r.value[1] != null
      if (kind === 'list') return Array.isArray(r.value) ? r.value.length > 0 : !!r.value
      return r.value !== undefined && r.value !== null && r.value !== ''
    })
    onApply(clean.length ? { match, rules: clean as FilterRule[] } : null)
    onClose()
  }

  const handleClear = () => { setRows([]); onApply(null); onClose() }

  return (
    <Drawer
      title="高级筛选"
      open={open}
      onClose={onClose}
      width={560}
      footer={
        <div className="flex justify-between">
          <Button onClick={handleClear} danger type="text">清空条件</Button>
          <div className="flex gap-2">
            <Button onClick={onClose}>取消</Button>
            <Button type="primary" onClick={handleApply}>应用</Button>
          </div>
        </div>
      }
    >
      <div className="mb-4 flex items-center gap-2 text-sm">
        <span className="text-slate-500">满足</span>
        <Radio.Group size="small" value={match} onChange={(e) => setMatch(e.target.value)} optionType="button" buttonStyle="solid"
          options={[{ label: '全部条件 (且)', value: 'all' }, { label: '任一条件 (或)', value: 'any' }]} />
      </div>

      {rows.length === 0 && <Empty description="暂无条件" image={Empty.PRESENTED_IMAGE_SIMPLE} />}

      <div className="space-y-2">
        {rows.map((row, i) => {
          const f = fieldOf(row.field)
          return (
            <div key={i} className="flex items-start gap-2">
              <Select
                size="small" showSearch optionFilterProp="label" style={{ width: 130, flexShrink: 0 }}
                value={row.field}
                onChange={(v) => onFieldChange(i, v)}
                options={fields.map((x) => ({ value: x.key, label: x.label }))}
              />
              <Select
                size="small" style={{ width: 110, flexShrink: 0 }}
                value={row.op}
                onChange={(v) => patchRow(i, { op: v, value: undefined })}
                options={(f?.operators || []).map((op) => ({ value: op, label: OP_LABELS[op] || op }))}
              />
              <div className="flex-1 min-w-0">
                <ValueControl field={f} op={row.op} value={row.value} onChange={(v) => patchRow(i, { value: v })} />
              </div>
              <Button size="small" type="text" danger icon={<DeleteOutlined />} onClick={() => removeRow(i)} />
            </div>
          )
        })}
      </div>

      <Button className="mt-3" type="dashed" size="small" icon={<PlusOutlined />} onClick={addRow} block disabled={!fields.length}>
        添加条件
      </Button>
    </Drawer>
  )
}

function ValueControl({ field, op, value, onChange }: {
  field?: SchemaField; op: string; value: unknown; onChange: (v: unknown) => void
}) {
  if (!field) return null
  const kind = valueKind(op)
  if (kind === 'none') return <span className="text-xs text-slate-300">（无需取值）</span>

  const type = field.type

  if (op === 'relative') {
    return (
      <Select size="small" style={{ width: '100%' }} value={value as string} placeholder="选择时间"
        onChange={onChange} options={RELATIVE_OPTIONS} />
    )
  }

  // 人员/客户等关系字段：用搜索选择器（按名称搜，存 id）
  if ((type === 'people' || type === 'relation') && field.optionSource) {
    return (
      <OptionSelect source={field.optionSource} multiple={kind === 'list'} value={value} onChange={onChange} />
    )
  }

  if (kind === 'pair') {
    if (type === 'number') {
      const arr = (Array.isArray(value) ? value : [undefined, undefined]) as (number | undefined)[]
      return (
        <div className="flex items-center gap-1">
          <InputNumber size="small" placeholder="最小" value={arr[0]} onChange={(v) => onChange([v, arr[1]])} style={{ width: '50%' }} />
          <span className="text-slate-300">~</span>
          <InputNumber size="small" placeholder="最大" value={arr[1]} onChange={(v) => onChange([arr[0], v])} style={{ width: '50%' }} />
        </div>
      )
    }
    if (DATE_TYPES.includes(type)) {
      const arr = (Array.isArray(value) ? value : []) as string[]
      return (
        <RangePicker size="small" style={{ width: '100%' }}
          value={arr.length === 2 ? [dayjs(arr[0]), dayjs(arr[1])] : null}
          onChange={(d) => onChange(d && d[0] && d[1] ? [d[0].format('YYYY-MM-DD'), d[1].format('YYYY-MM-DD')] : undefined)} />
      )
    }
    const arr = (Array.isArray(value) ? value : ['', '']) as string[]
    return (
      <div className="flex items-center gap-1">
        <Input size="small" value={arr[0]} onChange={(e) => onChange([e.target.value, arr[1]])} />
        <span className="text-slate-300">~</span>
        <Input size="small" value={arr[1]} onChange={(e) => onChange([arr[0], e.target.value])} />
      </div>
    )
  }

  if (kind === 'list') {
    if (type === 'enum' && field.options) {
      return (
        <Select size="small" mode="multiple" style={{ width: '100%' }} value={(value as string[]) || []}
          placeholder="选择" onChange={onChange}
          options={field.options.map((o) => ({ value: o.value, label: o.label }))} />
      )
    }
    return (
      <Select size="small" mode="tags" style={{ width: '100%' }} value={(value as string[]) || []}
        placeholder="输入后回车，可多个" onChange={onChange} tokenSeparators={[',', '，', ' ']} />
    )
  }

  // single
  if (type === 'number') {
    return <InputNumber size="small" style={{ width: '100%' }} value={value as number} onChange={onChange} />
  }
  if (DATE_TYPES.includes(type)) {
    return (
      <DatePicker size="small" style={{ width: '100%' }}
        value={value ? dayjs(value as string) : null}
        onChange={(d) => onChange(d ? d.format('YYYY-MM-DD') : undefined)} />
    )
  }
  if (type === 'boolean') {
    return (
      <Select size="small" style={{ width: '100%' }} value={value as string} placeholder="选择" onChange={onChange}
        options={[{ value: 'true', label: '是' }, { value: 'false', label: '否' }]} />
    )
  }
  if (type === 'enum' && field.options) {
    return (
      <Select size="small" style={{ width: '100%' }} value={value as string} placeholder="选择" showSearch optionFilterProp="label"
        onChange={onChange} options={field.options.map((o) => ({ value: o.value, label: o.label }))} />
    )
  }
  return <Input size="small" value={value as string} onChange={(e) => onChange(e.target.value)} placeholder="输入值" />
}

/** 人员/客户搜索选择器：按名称搜索，值存 id（单选或多选）。 */
function OptionSelect({ source, multiple, value, onChange }: {
  source: string; multiple: boolean; value: unknown; onChange: (v: unknown) => void
}) {
  const sel = useRemoteSelect(async (kw) => {
    if (source === 'customers') {
      const r = await customerApi.list({ pageNo: 1, pageSize: 50, keyword: kw || undefined }) as any
      return (r.data?.items || []).map((c: any) => ({ label: c.name, value: c.id }))
    }
    if (source === 'departments') {
      const r = await departmentApi.tree() as any
      const flat: { label: string; value: string }[] = []
      const walk = (nodes: any[]) => (nodes || []).forEach((n) => {
        flat.push({ label: n.name, value: n.id })
        if (n.children) walk(n.children)
      })
      walk(r.data || [])
      const k = (kw || '').trim()
      return k ? flat.filter((o) => o.label.includes(k)) : flat
    }
    const r = await userApi.list({ pageNo: 1, pageSize: 50, keyword: kw || undefined }) as any
    return (r.data?.items || []).map((u: any) => ({ label: u.real_name || u.username, value: u.id }))
  })
  return (
    <Select
      size="small" style={{ width: '100%' }} showSearch filterOption={false}
      mode={multiple ? 'multiple' : undefined}
      value={value as any}
      placeholder={source === 'customers' ? '搜索客户' : source === 'departments' ? '搜索部门' : '搜索用户'}
      loading={sel.loading}
      options={sel.options}
      onSearch={sel.onSearch}
      onDropdownVisibleChange={sel.onDropdownVisibleChange}
      onChange={onChange}
    />
  )
}
