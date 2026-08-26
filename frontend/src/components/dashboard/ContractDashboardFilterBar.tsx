/**
 * 合同管理仪表盘全局筛选 — 运算符 + 值控件（对齐简道云能力，项目主题样式）。
 */
import { DatePicker, Flex, Input, Select } from 'antd'
import type { Dayjs } from 'dayjs'
import DepartmentSelect from '@/components/DepartmentSelect'
import PersonField from '@/components/lowcode/fields/PersonField'
import DashboardFilterBox from '@/components/dashboard/DashboardFilterBox'
import DatePresetPicker from '@/components/dashboard/DatePresetPicker'
import {
  DATE_FILTER_OPS,
  REF_FILTER_OPS,
  TEXT_FILTER_OPS,
  isMultiRefOp,
  isMultiTextOp,
  isSingleRefOp,
  needsDateValue,
  needsRefValue,
  needsTextValue,
  type DateFilterOp,
  type RefFilterOp,
  type TextFilterOp,
} from '@/components/dashboard/contractDashboardFilterOps'
import {
  type DatePresetKey,
  resolveDatePreset,
} from '@/utils/jdyDatePresets'

const { RangePicker } = DatePicker

export interface ContractDashboardFilters {
  customerOp: TextFilterOp
  customerName: string
  customerNames: string[]
  cardDateOp: DateFilterOp
  cardDatePreset: DatePresetKey
  cardDateRange: [Dayjs, Dayjs]
  cardDateSingle?: Dayjs
  deptOp: RefFilterOp
  departmentIds: string[]
  assigneeOp: RefFilterOp
  assigneeId?: string
  assigneeIds: string[]
}

export const DEFAULT_CONTRACT_DASH_FILTERS: ContractDashboardFilters = {
  customerOp: 'contains',
  customerName: '',
  customerNames: [],
  cardDateOp: 'preset',
  cardDatePreset: 'thisYear',
  cardDateRange: resolveDatePreset('thisYear'),
  deptOp: 'in',
  departmentIds: [],
  assigneeOp: 'eq',
  assigneeId: undefined,
  assigneeIds: [],
}

export function contractFiltersToQuery(f: ContractDashboardFilters) {
  const q: Record<string, string> = {}

  q.customer_op = f.customerOp
  q.card_date_op = f.cardDateOp
  q.department_op = f.deptOp
  q.assignee_op = f.assigneeOp

  if (needsTextValue(f.customerOp)) {
    if (isMultiTextOp(f.customerOp)) {
      const vals = f.customerNames.map((s) => s.trim()).filter(Boolean)
      if (vals.length) q.customer_names = vals.join(',')
    } else if (f.customerName.trim()) {
      q.customer_name = f.customerName.trim()
    }
  }

  if (needsDateValue(f.cardDateOp)) {
    if (f.cardDateOp === 'preset') {
      const dr = resolveDatePreset(f.cardDatePreset)
      q.card_date_from = dr[0].format('YYYY-MM-DD')
      q.card_date_to = dr[1].format('YYYY-MM-DD')
    } else if (f.cardDateOp === 'between') {
      q.card_date_from = f.cardDateRange[0].format('YYYY-MM-DD')
      q.card_date_to = f.cardDateRange[1].format('YYYY-MM-DD')
    } else if (f.cardDateSingle) {
      q.card_date = f.cardDateSingle.format('YYYY-MM-DD')
    }
  }

  if (needsRefValue(f.deptOp) && f.departmentIds.length) {
    q.department_ids = f.departmentIds.join(',')
  }

  if (needsRefValue(f.assigneeOp)) {
    if (isMultiRefOp(f.assigneeOp) && f.assigneeIds.length) {
      q.assignee_ids = f.assigneeIds.join(',')
    } else if (isSingleRefOp(f.assigneeOp) && f.assigneeId) {
      q.assignee_id = f.assigneeId
    }
  }

  return q
}

interface Props {
  value: ContractDashboardFilters
  onChange: (next: ContractDashboardFilters) => void
}

export default function ContractDashboardFilterBar({ value, onChange }: Props) {
  const patch = (p: Partial<ContractDashboardFilters>) => onChange({ ...value, ...p })

  const customerValueControl = (() => {
    if (!needsTextValue(value.customerOp)) return null
    if (isMultiTextOp(value.customerOp)) {
      return (
        <Select
          mode="tags"
          variant="borderless"
          className="w-full"
          placeholder="输入后回车，可多个"
          value={value.customerNames}
          onChange={(v) => patch({ customerNames: v as string[] })}
          tokenSeparators={[',', '，']}
          open={false}
        />
      )
    }
    return (
      <Input
        variant="borderless"
        allowClear
        className="w-full"
        value={value.customerName}
        onChange={(e) => patch({ customerName: e.target.value })}
      />
    )
  })()

  const dateValueControl = (() => {
    if (!needsDateValue(value.cardDateOp)) return null
    if (value.cardDateOp === 'preset') {
      return (
        <DatePresetPicker
          preset={value.cardDatePreset}
          customRange={value.cardDateRange}
          onPreset={(key) => patch({
            cardDatePreset: key,
            cardDateRange: resolveDatePreset(key),
          })}
          onCustomRange={(range) => patch({
            cardDateOp: 'between',
            cardDateRange: range,
          })}
        />
      )
    }
    if (value.cardDateOp === 'between') {
      return (
        <RangePicker
          variant="borderless"
          className="w-full"
          allowClear={false}
          value={value.cardDateRange}
          onChange={(v) => {
            if (v?.[0] && v[1]) patch({ cardDateRange: [v[0], v[1]] })
          }}
        />
      )
    }
    return (
      <DatePicker
        variant="borderless"
        className="w-full"
        allowClear={false}
        value={value.cardDateSingle}
        onChange={(d) => patch({ cardDateSingle: d || undefined })}
      />
    )
  })()

  const deptValueControl = (() => {
    if (!needsRefValue(value.deptOp)) return null
    if (isMultiRefOp(value.deptOp)) {
      return (
        <DepartmentSelect
          multiple
          allowEmptyOption
          placeholder="选择部门"
          value={value.departmentIds}
          onChange={(v) => patch({ departmentIds: v || [] })}
        />
      )
    }
    return (
      <DepartmentSelect
        allowEmptyOption={value.deptOp === 'eq'}
        placeholder="选择部门"
        value={value.departmentIds[0]}
        onChange={(v) => patch({ departmentIds: v ? [v] : [] })}
      />
    )
  })()

  const assigneeValueControl = (() => {
    if (!needsRefValue(value.assigneeOp)) return null
    if (isMultiRefOp(value.assigneeOp)) {
      return (
        <PersonField
          multi
          placeholder="选择人员"
          value={value.assigneeIds}
          onChange={(v) => patch({ assigneeIds: (v as string[]) || [] })}
        />
      )
    }
    return (
      <PersonField
        placeholder="选择人员"
        value={value.assigneeId}
        onChange={(v) => patch({ assigneeId: (v as string) || undefined })}
      />
    )
  })()

  return (
    <Flex gap={12} wrap="wrap" align="stretch" className="w-full">
      <DashboardFilterBox
        label="客户名称"
        method={value.customerOp}
        methodOptions={TEXT_FILTER_OPS}
        hideValue={!needsTextValue(value.customerOp)}
        onMethodChange={(v) => patch({
          customerOp: v as TextFilterOp,
          customerName: '',
          customerNames: [],
        })}
      >
        {customerValueControl}
      </DashboardFilterBox>

      <DashboardFilterBox
        label="下卡日期"
        method={value.cardDateOp}
        methodOptions={DATE_FILTER_OPS}
        hideValue={!needsDateValue(value.cardDateOp)}
        onMethodChange={(v) => {
          const op = v as DateFilterOp
          patch({
            cardDateOp: op,
            cardDateSingle: value.cardDateRange[0],
            cardDateRange: resolveDatePreset(value.cardDatePreset),
          })
        }}
      >
        {dateValueControl}
      </DashboardFilterBox>

      <DashboardFilterBox
        label="部门"
        method={value.deptOp}
        methodOptions={REF_FILTER_OPS}
        hideValue={!needsRefValue(value.deptOp)}
        onMethodChange={(v) => patch({ deptOp: v as RefFilterOp, departmentIds: [] })}
      >
        {deptValueControl}
      </DashboardFilterBox>

      <DashboardFilterBox
        label="业务人员"
        method={value.assigneeOp}
        methodOptions={REF_FILTER_OPS}
        hideValue={!needsRefValue(value.assigneeOp)}
        onMethodChange={(v) => patch({
          assigneeOp: v as RefFilterOp,
          assigneeId: undefined,
          assigneeIds: [],
        })}
      >
        {assigneeValueControl}
      </DashboardFilterBox>
    </Flex>
  )
}
