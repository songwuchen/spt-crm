/**
 * 表单数据列表筛选弹层（对齐简道云：所有/任一 + 行内字段/运算符/值 + 筛选/清空）。
 */
import { useEffect, useMemo, useState } from 'react'
import {
  Badge, Button, DatePicker, Input, InputNumber, Popover, Select,
} from 'antd'
import {
  ClearOutlined, DeleteOutlined, FilterOutlined, PlusOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import type { FieldDefinition } from '@/types/lowcode'
import { fieldOption } from '@/components/lowcode/fieldTypeIcon'
import DepartmentSelect from '@/components/DepartmentSelect'
import {
  type FormFilterDsl,
  type FormFilterRule,
  FILTERABLE_FIELD_TYPES,
  loadDraftFilters,
  needsFilterValue,
  normalizeDraftDsl,
  normalizeFilterDsl,
  ruleHasItem,
  ruleValid,
  saveDraftFilters,
} from '@/components/lowcode/formInstanceFilterUtils'

const { RangePicker } = DatePicker

export type { FormFilterDsl, FormFilterRule } from '@/components/lowcode/formInstanceFilterUtils'

const OP_LABELS: Record<string, string> = {
  eq: '等于',
  ne: '不等于',
  contains: '包含',
  not_contains: '不包含',
  in: '等于任意一个',
  between: '选择范围',
  gt: '大于',
  gte: '大于等于',
  lt: '小于',
  lte: '小于等于',
  before: '早于',
  after: '晚于',
  is_empty: '为空',
  is_not_empty: '不为空',
}

export function opsForType(type: string): string[] {
  if (type === 'date' || type === 'datetime') {
    return ['between', 'eq', 'before', 'after', 'is_empty', 'is_not_empty']
  }
  if (type === 'number' || type === 'amount') {
    return ['eq', 'ne', 'gt', 'gte', 'lt', 'lte', 'between', 'is_empty', 'is_not_empty']
  }
  if (type === 'select' || type === 'radio') {
    return ['eq', 'ne', 'in', 'is_empty', 'is_not_empty']
  }
  if (type === 'person' || type === 'department' || type === 'project'
    || type === 'contract' || type === 'customer') {
    return ['eq', 'in', 'contains', 'is_empty', 'is_not_empty']
  }
  return ['contains', 'not_contains', 'eq', 'ne', 'in', 'is_empty', 'is_not_empty']
}

export function defaultOp(type: string): string {
  if (type === 'date' || type === 'datetime') return 'between'
  if (type === 'select' || type === 'radio') return 'eq'
  if (type === 'number' || type === 'amount') return 'eq'
  return 'contains'
}

function needsValue(op: string): boolean {
  return needsFilterValue(op)
}

interface Props {
  fields: FieldDefinition[]
  value: FormFilterDsl | null
  onApply: (dsl: FormFilterDsl | null) => void
  /** 用于 localStorage 记忆；与列表页 templateCode/id 一致 */
  storageKey?: string
}

export default function FormInstanceFilterPopover({ fields, value, onApply, storageKey }: Props) {
  const [open, setOpen] = useState(false)
  const [match, setMatch] = useState<'all' | 'any'>('all')
  const [rows, setRows] = useState<FormFilterRule[]>([])

  const filterFields = useMemo(
    () => fields.filter((f) => FILTERABLE_FIELD_TYPES.has(f.type)),
    [fields],
  )

  const restoreRows = () => {
    const applied = normalizeFilterDsl(value)
    if (applied?.rules.length) {
      setMatch(applied.match)
      setRows(applied.rules.map((r) => ({ ...r })))
      return
    }
    if (storageKey) {
      const draft = loadDraftFilters(storageKey)
      if (draft?.rules.length) {
        setMatch(draft.match)
        setRows(draft.rules.map((r) => ({ ...r })))
        return
      }
    }
    setMatch('all')
    setRows([])
  }

  useEffect(() => {
    if (!open) return
    restoreRows()
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  const persistDraft = () => {
    if (!storageKey) return
    const draft = normalizeDraftDsl({ match, rules: rows })
    saveDraftFilters(storageKey, draft)
  }

  const handleOpenChange = (next: boolean) => {
    if (!next && open) {
      persistDraft()
    }
    setOpen(next)
  }

  const fieldOf = (id: string) => filterFields.find((f) => f.id === id)

  const addRow = () => {
    const f = filterFields[0]
    if (!f) return
    setRows((prev) => [...prev, { field: f.id, op: defaultOp(f.type), value: undefined }])
  }

  const removeRow = (i: number) => setRows((prev) => prev.filter((_, idx) => idx !== i))

  const patchRow = (i: number, patch: Partial<FormFilterRule>) =>
    setRows((prev) => prev.map((r, idx) => (idx === i ? { ...r, ...patch } : r)))

  const onFieldChange = (i: number, fieldId: string) => {
    const f = fieldOf(fieldId)
    patchRow(i, { field: fieldId, op: defaultOp(f?.type || 'text'), value: undefined })
  }

  const handleApply = () => {
    const clean = rows.filter(ruleValid)
    const applied = clean.length ? { match, rules: clean } : null
    onApply(applied)
    if (storageKey) {
      if (applied) saveDraftFilters(storageKey, null)
      else saveDraftFilters(storageKey, normalizeDraftDsl({ match, rules: rows.filter(ruleHasItem) }))
    }
    setOpen(false)
  }

  const handleClear = () => {
    setRows([])
    setMatch('all')
    if (storageKey) saveDraftFilters(storageKey, null)
    onApply(null)
    setOpen(false)
  }

  const activeCount = value?.rules?.length || 0
  const draftHint = useMemo(() => {
    if (activeCount || !storageKey) return 0
    return loadDraftFilters(storageKey)?.rules.length || 0
  }, [activeCount, storageKey, value])

  const content = (
    <div className="w-[560px] max-w-[calc(100vw-32px)]">
      <div className="flex items-center gap-1 px-4 pt-3 pb-2 text-sm text-slate-600">
        <span>筛选出符合以下</span>
        <Select
          size="small"
          variant="borderless"
          value={match}
          popupMatchSelectWidth={false}
          options={[
            { value: 'all', label: '所有' },
            { value: 'any', label: '任一' },
          ]}
          onChange={(v) => setMatch(v)}
          className="min-w-[56px] font-medium text-teal-600"
          style={{ color: '#0d9488' }}
        />
        <span>条件的数据</span>
      </div>

      <div className="px-4 pb-2">
        <Button
          type="link"
          size="small"
          icon={<PlusOutlined />}
          onClick={addRow}
          disabled={!filterFields.length || rows.length >= 10}
          className="px-0 text-teal-600"
        >
          添加过滤条件
        </Button>
      </div>

      <div className="px-4 pb-3 space-y-2 max-h-[320px] overflow-auto">
        {rows.map((row, i) => {
          const f = fieldOf(row.field)
          const ops = opsForType(f?.type || 'text')
          return (
            <div key={i} className="flex items-center gap-2">
              <Select
                size="middle"
                showSearch
                optionFilterProp="title"
                style={{ width: 140, flexShrink: 0 }}
                value={row.field || undefined}
                placeholder="选择字段"
                onChange={(v) => onFieldChange(i, v)}
                options={filterFields.map((x) => fieldOption({ value: x.id, label: x.label, type: x.type }))}
              />
              <Select
                size="middle"
                style={{ width: 120, flexShrink: 0 }}
                value={row.op}
                onChange={(v) => patchRow(i, { op: v, value: undefined })}
                options={ops.map((op) => ({ value: op, label: OP_LABELS[op] || op }))}
              />
              <div className="flex-1 min-w-0">
                <FilterValueControl
                  field={f}
                  op={row.op}
                  value={row.value}
                  onChange={(v) => patchRow(i, { value: v })}
                />
              </div>
              <Button
                type="text"
                size="small"
                icon={<DeleteOutlined className="text-slate-400" />}
                onClick={() => removeRow(i)}
              />
            </div>
          )
        })}
      </div>

      <div className="flex items-center gap-3 px-4 py-3 border-t border-slate-100">
        <Button type="primary" onClick={handleApply} className="bg-teal-600 hover:!bg-teal-500">
          筛选
        </Button>
        <Button type="text" icon={<ClearOutlined />} onClick={handleClear} className="text-slate-500">
          清空
        </Button>
      </div>
    </div>
  )

  return (
    <Popover
      open={open}
      onOpenChange={handleOpenChange}
      trigger="click"
      placement="bottomLeft"
      arrow={false}
      content={content}
      overlayInnerStyle={{ padding: 0 }}
    >
      <Badge count={activeCount || draftHint || 0} size="small">
        <Button icon={<FilterOutlined />}>筛选</Button>
      </Badge>
    </Popover>
  )
}

export function FilterValueControl({
  field, op, value, onChange,
}: {
  field?: FieldDefinition
  op: string
  value: unknown
  onChange: (v: unknown) => void
}) {
  if (!needsValue(op)) {
    return <span className="text-xs text-slate-300">（无需取值）</span>
  }
  const type = field?.type || 'text'
  const opts = field?.options || []

  if (op === 'between') {
    if (type === 'number' || type === 'amount') {
      const arr = (Array.isArray(value) ? value : [undefined, undefined]) as (number | undefined)[]
      return (
        <div className="flex items-center gap-1">
          <InputNumber size="middle" placeholder="最小" value={arr[0]} onChange={(v) => onChange([v, arr[1]])} style={{ width: '50%' }} />
          <span className="text-slate-300">~</span>
          <InputNumber size="middle" placeholder="最大" value={arr[1]} onChange={(v) => onChange([arr[0], v])} style={{ width: '50%' }} />
        </div>
      )
    }
    const arr = (Array.isArray(value) ? value : []) as string[]
    const showTime = type === 'datetime'
    return (
      <RangePicker
        size="middle"
        style={{ width: '100%' }}
        allowClear
        showTime={showTime ? { format: 'HH:mm' } : false}
        placeholder={['开始时间', '结束时间']}
        value={arr.length === 2 ? [dayjs(arr[0]), dayjs(arr[1])] : null}
        onChange={(d) => onChange(
          d && d[0] && d[1]
            ? [
                d[0].format(showTime ? 'YYYY-MM-DD HH:mm:ss' : 'YYYY-MM-DD'),
                d[1].format(showTime ? 'YYYY-MM-DD HH:mm:ss' : 'YYYY-MM-DD'),
              ]
            : undefined,
        )}
      />
    )
  }

  if (op === 'in') {
    if ((type === 'select' || type === 'radio') && opts.length) {
      return (
        <Select
          size="middle"
          mode="multiple"
          allowClear
          style={{ width: '100%' }}
          value={(value as string[]) || []}
          placeholder="请选择"
          onChange={onChange}
          options={opts.map((o) => ({ value: o.value, label: o.label }))}
        />
      )
    }
    // 文本类「等于任意一个」：单行输入 + 清除，多个值用逗号分隔（对齐简道云）
    const text = Array.isArray(value)
      ? (value as string[]).join(',')
      : (value == null ? '' : String(value))
    return (
      <Input
        size="middle"
        allowClear
        value={text}
        placeholder="多个值用逗号分隔"
        onChange={(e) => {
          const s = e.target.value
          if (!s) {
            onChange(undefined)
            return
          }
          const parts = s.split(/[,，]/).map((x) => x.trim()).filter(Boolean)
          onChange(parts.length ? parts : undefined)
        }}
      />
    )
  }

  if (type === 'number' || type === 'amount') {
    return <InputNumber size="middle" style={{ width: '100%' }} value={value as number} onChange={onChange} placeholder="请输入" />
  }
  if (type === 'date' || type === 'datetime') {
    const showTime = type === 'datetime'
    return (
      <DatePicker
        size="middle"
        style={{ width: '100%' }}
        allowClear
        showTime={showTime ? { format: 'HH:mm' } : false}
        value={value ? dayjs(value as string) : null}
        onChange={(d) => onChange(d ? d.format(showTime ? 'YYYY-MM-DD HH:mm:ss' : 'YYYY-MM-DD') : undefined)}
      />
    )
  }
  if ((type === 'select' || type === 'radio') && opts.length) {
    return (
      <Select
        size="middle"
        style={{ width: '100%' }}
        allowClear
        showSearch
        optionFilterProp="label"
        value={value as string}
        placeholder="请选择"
        onChange={onChange}
        options={opts.map((o) => ({ value: o.value, label: o.label }))}
      />
    )
  }
  if (type === 'department' || type === 'department_multi') {
    if (op === 'eq') {
      return (
        <DepartmentSelect
          allowClear
          placeholder="选择部门"
          value={typeof value === 'string' ? value : undefined}
          onChange={(v) => onChange(v || undefined)}
        />
      )
    }
    return (
      <Input
        size="middle"
        value={value as string}
        onChange={(e) => onChange(e.target.value)}
        placeholder="输入部门名称，如：砂石"
        allowClear
      />
    )
  }
  if (type === 'person' || type === 'person_multi') {
    return (
      <Input
        size="middle"
        value={value as string}
        onChange={(e) => onChange(e.target.value)}
        placeholder="输入姓名"
        allowClear
      />
    )
  }
  return (
    <Input
      size="middle"
      value={value as string}
      onChange={(e) => onChange(e.target.value)}
      placeholder="请输入"
      allowClear
    />
  )
}
