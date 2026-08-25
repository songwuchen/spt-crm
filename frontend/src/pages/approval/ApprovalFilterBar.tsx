import { useEffect, useMemo, useState } from 'react'
import { Input, Button, Popover, Select, DatePicker, Badge, Space } from 'antd'
import { FilterOutlined, DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import dayjs, { type Dayjs } from 'dayjs'
import PersonField from '@/components/lowcode/fields/PersonField'
import { fieldOption } from '@/components/lowcode/fieldTypeIcon'
import {
  FilterValueControl,
  defaultOp,
  opsForType,
} from '@/components/lowcode/FormInstanceFilterPopover'
import {
  type FormFilterDsl,
  type FormFilterRule,
  needsFilterValue,
  normalizeFilterDsl,
  ruleValid,
} from '@/components/lowcode/formInstanceFilterUtils'
import { workflowApi } from '@/api/lowcodeWorkflow'
import type { ApprovalListFilters, WfFilterOptions } from '@/api/unifiedApprovals'
import type { FieldDefinition } from '@/types/lowcode'

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

const FILTERABLE_TYPES = new Set([
  'text', 'textarea', 'auto_number', 'number', 'amount',
  'select', 'radio', 'date', 'datetime',
  'person', 'department', 'project', 'contract', 'customer',
])

export interface ApprovalFilterBarProps {
  filters: ApprovalListFilters
  options: WfFilterOptions
  onApply: (filters: ApprovalListFilters) => void
  onClear: () => void
  onKeywordSearch?: (keyword: string) => void
  extra?: React.ReactNode
}

function countActive(f: ApprovalListFilters): number {
  let n = 0
  if (f.keyword?.trim()) n++
  if (f.processDefinitionId) n++
  if (f.nodeName) n++
  if (f.initiatorId) n++
  if (f.createdFrom || f.createdTo) n++
  n += f.formFilters?.rules?.length || 0
  return n
}

export default function ApprovalFilterBar({
  filters,
  options,
  onApply,
  onClear,
  onKeywordSearch,
  extra,
}: ApprovalFilterBarProps) {
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState<ApprovalListFilters>(filters)
  const [keywordDraft, setKeywordDraft] = useState(filters.keyword || '')
  const [processFields, setProcessFields] = useState<FieldDefinition[]>([])
  const [fieldMatch, setFieldMatch] = useState<'all' | 'any'>('all')
  const [fieldRows, setFieldRows] = useState<FormFilterRule[]>([])

  const activeCount = countActive(filters)

  const filterFields = useMemo(
    () => processFields.filter((f) => FILTERABLE_TYPES.has(f.type)),
    [processFields],
  )

  const fieldOf = (id: string) => filterFields.find((f) => f.id === id)

  useEffect(() => {
    if (!draft.processDefinitionId) {
      setProcessFields([])
      return
    }
    workflowApi.filterOptions({ process_definition_id: draft.processDefinitionId })
      .then((r) => setProcessFields((r.data?.fields || []) as FieldDefinition[]))
      .catch(() => setProcessFields([]))
  }, [draft.processDefinitionId])

  const syncDraft = () => {
    setDraft(filters)
    setKeywordDraft(filters.keyword || '')
    const ff = normalizeFilterDsl(filters.formFilters || null)
    setFieldMatch(ff?.match || 'all')
    setFieldRows(ff?.rules?.map((r) => ({ ...r })) || [])
  }

  const applyDraft = () => {
    const cleanRules = fieldRows.filter(ruleValid)
    const formFilters: FormFilterDsl | undefined = cleanRules.length
      ? { match: fieldMatch, rules: cleanRules }
      : undefined
    const next: ApprovalListFilters = {
      ...draft,
      keyword: keywordDraft.trim() || undefined,
      formFilters,
    }
    onApply(next)
    setOpen(false)
  }

  const clearAll = () => {
    setDraft({})
    setKeywordDraft('')
    setFieldRows([])
    setFieldMatch('all')
    onClear()
    setOpen(false)
  }

  const addFieldRow = () => {
    const f = filterFields[0]
    if (!f) return
    setFieldRows((prev) => [...prev, { field: f.id, op: defaultOp(f.type), value: undefined }])
  }

  const patchFieldRow = (i: number, patch: Partial<FormFilterRule>) =>
    setFieldRows((prev) => prev.map((r, idx) => (idx === i ? { ...r, ...patch } : r)))

  const onFieldChange = (i: number, fieldId: string) => {
    const f = fieldOf(fieldId)
    patchFieldRow(i, { field: fieldId, op: defaultOp(f?.type || 'text'), value: undefined })
  }

  const dateRange: [Dayjs | null, Dayjs | null] | null =
    draft.createdFrom || draft.createdTo
      ? [
          draft.createdFrom ? dayjs(draft.createdFrom) : null,
          draft.createdTo ? dayjs(draft.createdTo) : null,
        ]
      : null

  const popoverContent = (
    <div className="w-[520px] max-w-[calc(100vw-32px)] space-y-3">
      <div>
        <div className="text-xs text-slate-500 mb-1">流程表单</div>
        <Select
          allowClear
          showSearch
          placeholder="请选择流程"
          className="w-full"
          optionFilterProp="label"
          value={draft.processDefinitionId}
          onChange={(v) => {
            setDraft((d) => ({ ...d, processDefinitionId: v || undefined }))
            setFieldRows([])
          }}
          options={options.processes.map((p) => ({ value: p.id, label: p.name }))}
        />
      </div>
      <div>
        <div className="text-xs text-slate-500 mb-1">当前节点</div>
        <Select
          allowClear
          showSearch
          placeholder="请选择"
          className="w-full"
          optionFilterProp="label"
          value={draft.nodeName}
          onChange={(v) => setDraft((d) => ({ ...d, nodeName: v || undefined }))}
          options={options.node_names.map((n) => ({ value: n, label: n }))}
        />
      </div>

      {draft.processDefinitionId && (
        <div>
          <div className="flex items-center gap-1 text-xs text-slate-500 mb-1">
            <span>字段筛选（符合以下</span>
            <Select
              size="small"
              variant="borderless"
              value={fieldMatch}
              popupMatchSelectWidth={false}
              options={[
                { value: 'all', label: '所有' },
                { value: 'any', label: '任一' },
              ]}
              onChange={setFieldMatch}
              className="min-w-[52px]"
            />
            <span>条件）</span>
          </div>
          {filterFields.length === 0 ? (
            <div className="text-xs text-slate-400 py-1">该流程无可筛字段，或正在加载…</div>
          ) : (
            <div className="space-y-2 max-h-[220px] overflow-auto">
              {fieldRows.map((row, i) => {
                const f = fieldOf(row.field)
                const ops = opsForType(f?.type || 'text')
                return (
                  <div key={i} className="flex items-center gap-1.5">
                    <Select
                      size="small"
                      showSearch
                      optionFilterProp="title"
                      style={{ width: 120, flexShrink: 0 }}
                      value={row.field || undefined}
                      placeholder="字段"
                      onChange={(v) => onFieldChange(i, v)}
                      options={filterFields.map((x) => fieldOption({ value: x.id, label: x.label, type: x.type }))}
                    />
                    <Select
                      size="small"
                      style={{ width: 88, flexShrink: 0 }}
                      value={row.op}
                      onChange={(v) => patchFieldRow(i, { op: v, value: undefined })}
                      options={ops.map((op) => ({ value: op, label: OP_LABELS[op] || op }))}
                    />
                    <div className="flex-1 min-w-0">
                      {needsFilterValue(row.op) ? (
                        <FilterValueControl
                          field={f}
                          op={row.op}
                          value={row.value}
                          onChange={(v) => patchFieldRow(i, { value: v })}
                        />
                      ) : (
                        <span className="text-xs text-slate-300">—</span>
                      )}
                    </div>
                    <Button
                      type="text"
                      size="small"
                      icon={<DeleteOutlined className="text-slate-400" />}
                      onClick={() => setFieldRows((prev) => prev.filter((_, idx) => idx !== i))}
                    />
                  </div>
                )
              })}
            </div>
          )}
          <Button
            type="link"
            size="small"
            icon={<PlusOutlined />}
            className="px-0 mt-1"
            disabled={!filterFields.length || fieldRows.length >= 10}
            onClick={addFieldRow}
          >
            添加字段筛选条件
          </Button>
        </div>
      )}

      <div>
        <div className="text-xs text-slate-500 mb-1">发起人</div>
        <PersonField
          value={draft.initiatorId}
          onChange={(v) => setDraft((d) => ({ ...d, initiatorId: (v as string) || undefined }))}
          placeholder="请选择发起人"
        />
      </div>
      <div>
        <div className="text-xs text-slate-500 mb-1">发起时间</div>
        <DatePicker.RangePicker
          className="w-full"
          value={dateRange as [Dayjs, Dayjs] | null}
          onChange={(v) => {
            setDraft((d) => ({
              ...d,
              createdFrom: v?.[0] ? v[0].startOf('day').toISOString() : undefined,
              createdTo: v?.[1] ? v[1].endOf('day').toISOString() : undefined,
            }))
          }}
        />
      </div>
      <div className="flex items-center gap-2 pt-1 border-t border-slate-100">
        <Button type="primary" onClick={applyDraft}>筛选</Button>
        <Button icon={<DeleteOutlined />} onClick={clearAll}>清空</Button>
      </div>
    </div>
  )

  return (
    <div className="mb-3 flex flex-wrap items-center gap-2 shrink-0">
      <Input.Search
        allowClear
        placeholder="搜索标题、单号、合同号等"
        className="max-w-xs"
        size="small"
        value={keywordDraft}
        onChange={(e) => setKeywordDraft(e.target.value)}
        onSearch={(v) => {
          const kw = v.trim()
          onApply({ ...filters, keyword: kw || undefined })
          onKeywordSearch?.(kw)
        }}
      />
      <Popover
        open={open}
        trigger="click"
        placement="bottomLeft"
        content={popoverContent}
        onOpenChange={(v) => {
          setOpen(v)
          if (v) syncDraft()
        }}
      >
        <Badge count={activeCount} size="small" offset={[-2, 2]}>
          <Button size="small" icon={<FilterOutlined />}>筛选</Button>
        </Badge>
      </Popover>
      {activeCount > 0 && (
        <Button size="small" type="link" onClick={clearAll}>清除筛选</Button>
      )}
      {extra && (
        <>
          <div className="flex-1" />
          <Space wrap>{extra}</Space>
        </>
      )}
    </div>
  )
}
