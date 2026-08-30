// 扩展平台 → 表单数据列表: 某模板的填报记录(看/改/删 + 去填报)。
// 支持通用「明细展开」：主表字段 rowSpan 合并 + 明细子列分组表头（对齐简道云列表）。
import { useEffect, useState, useCallback, useMemo, useRef } from 'react'
import { useParams, useNavigate, useLocation, useSearchParams } from 'react-router-dom'
import {
  Button, Space, Tag, Modal, message, Popconfirm, Typography,
  Input, Select, Dropdown, Alert,
} from 'antd'
import type { MenuProps } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { ReactNode } from 'react'
import dayjs from 'dayjs'
import FillHeightTable from '@/components/list/FillHeightTable'
import ColumnConfigPanel from '@/components/list/ColumnConfigPanel'
import type { ColumnState, ColMeta } from '@/hooks/useListView'
import FormInstanceFilterPopover, {
  type FormFilterDsl,
} from '@/components/lowcode/FormInstanceFilterPopover'
import {
  expandFilterableFormFields,
  loadAppliedFilters,
  saveAppliedFilters,
} from '@/components/lowcode/formInstanceFilterUtils'
import {
  ArrowLeftOutlined, PlusOutlined, DownloadOutlined, DownOutlined,
  PrinterOutlined, EditOutlined, DeleteOutlined, SendOutlined, CopyOutlined,
  SearchOutlined, ReloadOutlined, PaperClipOutlined, ThunderboltOutlined,
  StopOutlined,
  BarChartOutlined,
} from '@ant-design/icons'
import { modalFullscreenProps } from '@/components/ModalFullscreenTitle'
import JdyRecordModalTitle from '@/components/lowcode/JdyRecordModalTitle'
import RecordDetailToolbar, { type RecordToolbarAction } from '@/components/lowcode/RecordDetailToolbar'
import RecordDetailBodyLayout from '@/components/lowcode/RecordDetailBodyLayout'
import RecordDetailSideDrawer from '@/components/lowcode/RecordDetailSideDrawer'
import { resolveRecordDisplayNo } from '@/utils/recordModalTitle'
import { lowcodeApi } from '@/api/lowcode'
import { workflowApi } from '@/api/lowcodeWorkflow'
import { attachmentApi } from '@/api/attachment'
import { downloadFile } from '@/utils/download'
import {
  isMetaOnlyAttachmentId,
  normalizeFileFieldValue,
} from '@/utils/fileFieldValue'
import type { FieldDefinition, FormRule, FormInstance, FormInstanceDetail, WfInstanceDetail } from '@/types/lowcode'
import FormRenderer, { findRequiredError, scrollToLcField, deriveRolePerms } from '@/components/lowcode/FormRenderer'
import WfFlowDynamics from '@/components/lowcode/WfFlowDynamics'
import FormInstanceSystemMeta from '@/components/lowcode/FormInstanceSystemMeta'
import { buildFormFieldLabels } from '@/utils/dataLogLabels'
import { isRegionManagerField, isSalespersonField, parsePersonFieldId } from '@/utils/salespersonRegion'
import WfActivateFlowModal from '@/components/lowcode/WfActivateFlowModal'
import { computeFieldStates } from '@/components/lowcode/RuleEngine'
import { fieldShowsTime } from '@/components/lowcode/dateField'
import { useAuthStore } from '@/stores/useAuthStore'
import {
  DRAWING_FORM_LAYOUT, applyDrawingFormLayout,
  resolveListExpandDetails, resolveListColumnIds,
  resolveListColumnWidths, resolveListColumnLabels, resolveListFullText,
  resolveListFixedRightKeys,
} from '@/constants/drawingFormLayout'
import { clampColWidth } from '@/components/list/columnResize'
import { getPersonLabelMap } from '@/components/lowcode/fields/PersonField'
import { getDeptNameMap } from '@/components/lowcode/fields/DeptField'
import { getProjectLabelMap } from '@/components/lowcode/fields/ProjectField'
import { getContractLabelMap } from '@/components/lowcode/fields/ContractField'
import { getCustomerLabelMap } from '@/components/lowcode/fields/CustomerField'
import { printSchemeInstance } from '@/pages/drawing/schemePrint'
import { resolveExpandDetailTablePageSize } from '@/utils/listDetailExpandPagination'
import { printQuoteInstance, isQuoteManagementForm } from '@/pages/quote/quotePrint'
import {
  defaultProdCardPrintMode,
  printProdCardInstance,
  type ProdCardPrintMode,
} from '@/pages/drawing/prodCardPrint'
import {
  BIZ_BONUS_PRINT_MODE_LABELS,
  defaultBizBonusPrintMode,
  isBizBonusForm,
  printBizBonusInstance,
  type BizBonusPrintMode,
} from '@/pages/bonus/bizBonusPrint'
import { recordListNo } from '@/utils/formInstanceListNo'
import { FORM_INSTANCE_STATUS } from '@/utils/lowcodeWorkflowLabels'
import {
  canUserActRevise, hasActiveReviseStep, resolveReviseTaskId,
} from '@/utils/reviseWorkflow'
import { canEndProcessInRecordView, isRunningProcessTerminate } from '@/utils/recordWorkflowToolbar'
import { useWfProcessDrawer } from '@/components/lowcode/WfProcessDrawer'

const { Title, Text } = Typography

const STATUS_TAG: Record<string, { color: string; text: string }> = Object.fromEntries(
  Object.entries(FORM_INSTANCE_STATUS).map(([k, v]) => [k, { color: v.color, text: v.text }]),
)

const STATUS_FILTER_OPTIONS = [
  { value: 'draft', label: '草稿' },
  { value: 'submitted', label: '已提交' },
  { value: 'running', label: '审批中' },
  { value: 'completed', label: '已通过' },
  { value: 'rejected', label: '已驳回' },
  { value: 'returned', label: '已退回' },
  { value: 'withdrawn', label: '已撤回' },
  { value: 'cancelled', label: '已作废' },
]

function renderCurrentNodeCell(rec: FormInstance): ReactNode {
  const name = (rec.current_node_name || '').trim()
  if (!name) return '—'
  return (
    <Text ellipsis={{ tooltip: name }} style={{ maxWidth: '100%' }}>
      {name}
    </Text>
  )
}

/** v3：客服申请完整列 + 多明细展开；旧 key 丢弃以免脏默认列 */
const COL_STORAGE_PREFIX = 'spt_formlist_cols_v3_'

function loadColState(storageKey: string): ColumnState {
  try {
    const s = localStorage.getItem(storageKey)
    return s ? JSON.parse(s) : { hidden: [], order: [], shown: [], widths: {} }
  } catch {
    return { hidden: [], order: [], shown: [], widths: {} }
  }
}

function applyListColumnResize<T extends object>(
  cols: ColumnsType<T>,
  widths: Record<string, number>,
): ColumnsType<T> {
  return cols.map((col) => {
    if (!col || typeof col !== 'object') return col
    if ('children' in col && Array.isArray((col as { children?: ColumnsType<T> }).children)) {
      return {
        ...col,
        children: applyListColumnResize((col as { children: ColumnsType<T> }).children, widths),
      }
    }
    const c = col as ColumnsType<T>[number] & { key?: string; dataIndex?: string; width?: number }
    const k = String(c.key ?? c.dataIndex ?? '')
    if (!k) return col
    const baseW = typeof c.width === 'number' ? c.width : 140
    const width = typeof widths[k] === 'number' ? widths[k] : baseW
    return {
      ...c,
      width,
      onHeaderCell: () => ({
        width,
        colKey: k,
        'data-col-key': k,
        'data-resizable': '1',
      }),
    }
  }) as ColumnsType<T>
}

function listFilterMemoryKey(templateCode?: string, id?: string) {
  return templateCode || id || 'unknown'
}

/** 列表不宜展开的重字段类型（file/image 以紧凑芯片展示，可进列） */
const LIST_EXCLUDE_TYPES = new Set([
  'formula', 'detail_table', 'rich_text', 'signature',
  'textarea', 'address', 'location', 'cascade', 'sub_table_data',
  'section', 'separator',
])

/** 列表优先展示的类型（同优先级按 schema 顺序） */
const LIST_PRIORITY = new Set([
  'auto_number', 'text', 'number', 'amount', 'date', 'datetime',
  'select', 'radio', 'checkbox', 'switch', 'person', 'department',
  'person_multi', 'department_multi', 'project', 'contract', 'customer',
  'file', 'image',
])

function isCompanionTextField(f: FieldDefinition): boolean {
  return /_text$|（文本）|\(文本\)$/.test(f.id) || /（文本）|\(文本\)|文本$/.test(f.label || '')
}

function isApproverOnlyField(f: FieldDefinition): boolean {
  return f.available_on_create === false && f.fill_stage === 'approver'
}

function isLowSignalListLabel(label?: string): boolean {
  if (!label) return false
  // 审批环节辅助判断、空链路字段等，默认不进扫视列
  return /^(是否需要|是否转|通知|抄送|会签|转交|流程判断|仓库判断)/.test(label)
}

/** 可进列表/列配置的字段池（含审批字段，便于用户调出） */
function filterListableFields(
  fields: FieldDefinition[],
  excludeIds?: Set<string>,
): FieldDefinition[] {
  return fields.filter((f) => {
    if (excludeIds?.has(f.id)) return false
    if (LIST_EXCLUDE_TYPES.has(f.type)) return false
    if (isCompanionTextField(f)) return false
    if (f.type === 'section' || f.type === 'separator') return false
    return true
  })
}

/**
 * 默认列表列：优先 layout.listColumns（简道云式扫视列）；
 * 否则启发式 —— 跳过审批-only / 低信息「是否*」，客户/合同/日期优先。
 */
function pickListColumns(
  fields: FieldDefinition[],
  max = 8,
  excludeIds?: Set<string>,
  preferredIds?: string[],
): FieldDefinition[] {
  const listable = filterListableFields(fields, excludeIds)
  const byId = new Map(listable.map((f) => [f.id, f]))

  if (preferredIds?.length) {
    const picked = preferredIds
      .map((id) => byId.get(id))
      .filter((f): f is FieldDefinition => !!f)
    if (picked.length) return picked.slice(0, Math.max(max, preferredIds.length))
  }

  const bizPriority = new Set([
    'customer', 'contract', 'project', 'date', 'datetime',
    'auto_number', 'select', 'radio', 'checkbox', 'text', 'number', 'amount',
  ])
  const candidates = listable.filter((f) => {
    if (isApproverOnlyField(f)) return false
    if (isLowSignalListLabel(f.label)) return false
    return true
  })
  const preferred = candidates.filter((f) => LIST_PRIORITY.has(f.type))
  const rest = candidates.filter((f) => !LIST_PRIORITY.has(f.type))
  const sorted = [
    ...preferred.filter((f) => f.type === 'auto_number'),
    ...preferred.filter((f) => bizPriority.has(f.type)
      && f.type !== 'auto_number'
      && f.type !== 'person' && f.type !== 'department'
      && f.type !== 'person_multi' && f.type !== 'department_multi'),
    ...preferred.filter((f) => f.type === 'person' || f.type === 'department'
      || f.type === 'person_multi' || f.type === 'department_multi'),
    ...preferred.filter((f) => !bizPriority.has(f.type)
      && f.type !== 'person' && f.type !== 'department'
      && f.type !== 'person_multi' && f.type !== 'department_multi'),
    ...rest,
  ]
  return sorted.slice(0, max)
}

/** 明细表在列表中展示的子列（跳过已取消/重类型） */
const DETAIL_LIST_TYPES = new Set([
  'text', 'number', 'amount', 'select', 'radio', 'date', 'datetime',
  'checkbox', 'multi_select', 'contract', 'customer',
])

function pickDetailListColumns(detailField: FieldDefinition, max = 8): FieldDefinition[] {
  const cols = detailField.detail_table_columns || []
  return cols.filter((c) => {
    if (!DETAIL_LIST_TYPES.has(c.type)) return false
    if (/取消/.test(c.label || '')) return false
    return true
  }).slice(0, max)
}

/** 主记录 × 多明细行展开；行高取各明细行数最大值（对齐简道云） */
type DetailFlatRow = {
  key: string
  record: FormInstance
  detailIndex: number
  /** detailFieldId → 该行明细数据 */
  detailRows: Record<string, Record<string, unknown> | null>
  /** 兼容单明细：取第一个展开表的行 */
  detailRow: Record<string, unknown> | null
  /** 主字段单元格 rowSpan；非首行明细为 0 */
  rowSpan: number
}

function flattenInstancesByDetails(
  items: FormInstance[],
  detailFieldIds: string[],
): DetailFlatRow[] {
  const out: DetailFlatRow[] = []
  const ids = detailFieldIds.length ? detailFieldIds : ['_']
  for (const rec of items) {
    const arrays = ids.map((fid) => {
      const raw = rec.form_data?.[fid]
      return Array.isArray(raw) ? (raw as Record<string, unknown>[]) : []
    })
    const n = Math.max(1, ...arrays.map((a) => a.length))
    for (let i = 0; i < n; i++) {
      const detailRows: Record<string, Record<string, unknown> | null> = {}
      ids.forEach((fid, idx) => {
        if (fid === '_') return
        detailRows[fid] = arrays[idx][i] ?? null
      })
      const firstId = detailFieldIds[0]
      out.push({
        key: `${rec.id}:${i}`,
        record: rec,
        detailIndex: i,
        detailRows,
        detailRow: firstId ? (detailRows[firstId] ?? null) : null,
        rowSpan: i === 0 ? n : 0,
      })
    }
  }
  return out
}

/** 列表 API 每页主记录数（明细展开时表格 pageSize 可能临时抬高以展示全部 flat 行） */
const LIST_PAGE_SIZE = 20

type NameMaps = {
  users: Record<string, string>
  depts: Record<string, string>
  projects: Record<string, string>
  contracts: Record<string, string>
  customers: Record<string, string>
}

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

/** 简道云 linkfield 等对象上的可读 label（空对象返回 null） */
function refObjectLabel(v: unknown): string | null {
  if (!isPlainObject(v) || !Object.keys(v).length) return null
  const lab = String(v.label ?? v.name ?? v.real_name ?? '').trim()
  return lab || null
}

function collectIds(v: unknown): string[] {
  if (v == null || v === '') return []
  const idFromObj = (o: Record<string, unknown>): string[] => {
    if (!Object.keys(o).length) return []
    const id = o.id ?? o._id ?? o.value
    return id != null && id !== '' ? [String(id)] : []
  }
  if (Array.isArray(v)) {
    return v.flatMap((x) => {
      if (isPlainObject(x)) return idFromObj(x)
      return x != null && x !== '' ? [String(x)] : []
    })
  }
  if (isPlainObject(v)) return idFromObj(v)
  return [String(v)]
}

/** contract/customer/project 等引用字段列表展示 */
function resolveRefDisplay(v: unknown, map?: Record<string, string>): string {
  const direct = refObjectLabel(v)
  if (direct) return direct
  const ids = collectIds(v)
  if (!ids.length) return '—'
  const names = ids.map((id) => map?.[id] || id)
  // 简道云导入的 24 位 hex 合同 id 无法在 CRM 解析，勿展示 [object Object] / 乱码 id
  if (names.every((n) => /^[a-f0-9]{24}$/i.test(n))) return '—'
  return names.join('，')
}

function isEmptyRef(v: unknown): boolean {
  if (v == null || v === '') return true
  return isPlainObject(v) && !Object.keys(v).length
}

/** 生产卡列表「选择合同」列：否→drawing_no_query，是→contract_no_select；并兜底带出字段 */
function resolveProdCardContractPick(fd: Record<string, unknown> | undefined): unknown {
  if (!fd) return undefined
  const isSupp = String(fd.is_supplement || '').trim() === '是'
  const primary = isSupp ? fd.contract_no_select : fd.drawing_no_query
  if (!isEmptyRef(primary)) return primary
  const fallback = isSupp ? fd.yes_contract_no : fd.no_drawing_no
  if (fallback != null && String(fallback).trim()) return String(fallback)
  if (!isSupp && !isEmptyRef(fd.contract_no_select)) return fd.contract_no_select
  if (isSupp && !isEmptyRef(fd.drawing_no_query)) return fd.drawing_no_query
  return undefined
}

function renderProdCardContractCell(
  fd: Record<string, unknown> | undefined,
  maps?: NameMaps,
): ReactNode {
  const v = resolveProdCardContractPick(fd)
  if (v == null || v === '') return '—'
  return linkText(resolveRefDisplay(v, maps?.contracts))
}

function formatCellDateTime(v: unknown, withTime: boolean): string {
  const d = dayjs(String(v))
  if (!d.isValid()) return String(v)
  // ISO(含 Z/+00:00) 会按浏览器本地时区展示，避免列表里露出 2026-08-06T03:xx
  return d.format(withTime ? 'YYYY-MM-DD HH:mm' : 'YYYY-MM-DD')
}

const TAG_PALETTE = [
  'blue', 'cyan', 'geekblue', 'purple', 'magenta', 'orange', 'gold', 'green', 'lime',
] as const

function optionTagColor(label: string): string {
  if (/^(否|无|不是)/.test(label)) return 'gold'
  if (/^(是|有|需要)/.test(label)) return 'green'
  if (/紧急/.test(label)) return 'orange'
  if (/战略/.test(label)) return 'purple'
  if (/大客户|重点/.test(label)) return 'cyan'
  if (/客服/.test(label)) return 'green'
  if (/室主任|总工|经理/.test(label)) return 'orange'
  let h = 0
  for (let i = 0; i < label.length; i++) h = (h + label.charCodeAt(i)) % TAG_PALETTE.length
  return TAG_PALETTE[h]
}

function linkText(text: string): ReactNode {
  if (!text || text === '—') return '—'
  return <span className="text-primary cursor-default truncate inline-block max-w-full align-bottom" title={text}>{text}</span>
}

function joinLinks(parts: string[]): ReactNode {
  const clean = parts.filter(Boolean)
  if (!clean.length) return '—'
  const full = clean.join('，')
  return (
    <span className="truncate inline-block max-w-full align-bottom" title={full}>
      {clean.map((t, i) => (
        <span key={`${t}-${i}`}>
          {i > 0 ? '，' : ''}
          <span className="text-primary cursor-default">{t}</span>
        </span>
      ))}
    </span>
  )
}

function ListMediaCell({ value, image }: { value: unknown; image?: boolean }) {
  const atts = normalizeFileFieldValue(value)
  const [urls, setUrls] = useState<Record<string, string>>({})

  useEffect(() => {
    if (!image || !atts.length) return
    let alive = true
    ;(async () => {
      const next: Record<string, string> = {}
      for (const a of atts.slice(0, 3)) {
        if (a.metaOnly || isMetaOnlyAttachmentId(a.id)) continue
        try { next[a.id] = await attachmentApi.getUrl(a.id, false) } catch { /* ignore */ }
      }
      if (alive) setUrls(next)
    })()
    return () => { alive = false }
  }, [image, atts.map((a) => a.id).join(',')]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!atts.length) return <span>—</span>

  const open = async (id: string) => {
    if (isMetaOnlyAttachmentId(id)) {
      message.info('暂无文件实体，仅同步了简道云文件名')
      return
    }
    try {
      window.open(await attachmentApi.getUrl(id, !image), '_blank')
    } catch {
      message.error('获取文件地址失败')
    }
  }

  if (image) {
    return (
      <Space size={4} wrap>
        {atts.slice(0, 3).map((a) => (
          urls[a.id]
            ? (
              <img
                key={a.id}
                src={urls[a.id]}
                alt={a.name}
                title={a.name}
                onClick={() => open(a.id)}
                style={{
                  width: 36, height: 36, objectFit: 'cover', borderRadius: 4,
                  cursor: 'pointer', border: '1px solid #e2e8f0',
                }}
              />
            )
            : (
              <span
                key={a.id}
                className="inline-flex items-center justify-center text-slate-400 text-xs"
                style={{ width: 36, height: 36, border: '1px solid #e2e8f0', borderRadius: 4 }}
              >
                图
              </span>
            )
        ))}
        {atts.length > 3 ? <span className="text-slate-400 text-xs">+{atts.length - 3}</span> : null}
      </Space>
    )
  }

  return (
    <Space size={2} direction="vertical" className="max-w-full">
      {atts.slice(0, 3).map((a) => (
        <a key={a.id} className="text-xs truncate block max-w-full" onClick={() => open(a.id)} title={a.name}>
          <PaperClipOutlined className="mr-1 text-orange-500" />
          {a.name}
        </a>
      ))}
      {atts.length > 3 ? <span className="text-slate-400 text-xs">+{atts.length - 3} 个文件</span> : null}
    </Space>
  )
}

function cellText(field: FieldDefinition, v: unknown, maps?: NameMaps): string {
  if (v == null || v === '') return '—'
  const opts = field.options || []
  const labelOf = (x: unknown) => opts.find((o) => o.value === x)?.label ?? String(x)
  if (field.type === 'date' || field.type === 'datetime') {
    return formatCellDateTime(v, fieldShowsTime(field))
  }
  if (field.type === 'select' || field.type === 'radio') return labelOf(v)
  if (field.type === 'checkbox' || field.type === 'multi_select') {
    if (Array.isArray(v)) return v.map(labelOf).join('，') || '—'
  }
  if (field.type === 'switch') return v ? '是' : '否'
  if (field.type === 'detail_table') return `${(v as unknown[]).length} 行`
  if (field.type === 'amount') return `¥${Number(v).toFixed(2)}`
  if (field.type === 'file' || field.type === 'image') {
    const atts = normalizeFileFieldValue(v)
    if (!atts.length) return '—'
    return atts.map((a) => a.name).join('，')
  }
  if (field.type === 'department' || field.type === 'department_multi') {
    if (typeof v === 'object' && v !== null && 'name' in (v as object) && !Array.isArray(v)) {
      return String((v as { name?: string }).name || '—')
    }
    const ids = collectIds(v)
    if (!ids.length) return '—'
    return ids.map((id) => maps?.depts[id] || id).join('，')
  }
  if (field.type === 'person' || field.type === 'person_multi') {
    if (typeof v === 'object' && v !== null && !Array.isArray(v)
      && ('name' in (v as object) || 'real_name' in (v as object))) {
      const o = v as { name?: string; real_name?: string }
      return String(o.real_name || o.name || '—')
    }
    const ids = collectIds(v)
    if (!ids.length) return '—'
    return ids.map((id) => maps?.users[id] || id).join('，')
  }
  if (field.type === 'project') {
    return resolveRefDisplay(v, maps?.projects)
  }
  if (field.type === 'contract') {
    return resolveRefDisplay(v, maps?.contracts)
  }
  if (field.type === 'customer') {
    return resolveRefDisplay(v, maps?.customers)
  }
  if (Array.isArray(v)) return v.map(labelOf).join('，')
  return String(v)
}

/** 简道云式单元格：选项 Tag、人员/部门蓝字、附件图标、图片缩略图 */
function cellNode(field: FieldDefinition, v: unknown, maps?: NameMaps): ReactNode {
  if (v == null || v === '') return '—'
  const opts = field.options || []
  const labelOf = (x: unknown) => opts.find((o) => o.value === x)?.label ?? String(x)

  if (field.type === 'file' || field.type === 'image') {
    return <ListMediaCell value={v} image={field.type === 'image' || /图片/.test(field.label || '')} />
  }
  if (field.type === 'select' || field.type === 'radio') {
    const lab = labelOf(v)
    return <Tag color={optionTagColor(lab)} style={{ marginInlineEnd: 0 }}>{lab}</Tag>
  }
  if (field.type === 'checkbox' || field.type === 'multi_select') {
    const arr = Array.isArray(v) ? v : [v]
    if (!arr.length) return '—'
    return (
      <Space size={[4, 4]} wrap>
        {arr.map((x, i) => {
          const lab = labelOf(x)
          return <Tag key={`${lab}-${i}`} color={optionTagColor(lab)}>{lab}</Tag>
        })}
      </Space>
    )
  }
  if (field.type === 'person' || field.type === 'person_multi') {
    if (typeof v === 'object' && v !== null && !Array.isArray(v)
      && ('name' in (v as object) || 'real_name' in (v as object))) {
      const o = v as { name?: string; real_name?: string }
      return linkText(String(o.real_name || o.name || '—'))
    }
    return joinLinks(collectIds(v).map((id) => maps?.users[id] || id))
  }
  if (field.type === 'department' || field.type === 'department_multi') {
    if (typeof v === 'object' && v !== null && 'name' in (v as object) && !Array.isArray(v)) {
      return linkText(String((v as { name?: string }).name || '—'))
    }
    return joinLinks(collectIds(v).map((id) => maps?.depts[id] || id))
  }
  if (field.type === 'customer') {
    return linkText(resolveRefDisplay(v, maps?.customers))
  }
  if (field.type === 'contract') {
    return linkText(resolveRefDisplay(v, maps?.contracts))
  }
  if (field.type === 'project') {
    return linkText(resolveRefDisplay(v, maps?.projects))
  }
  return cellText(field, v, maps)
}

type ViewRec = {
  fields: FieldDefinition[]
  value: Record<string, unknown>
  readonly: boolean
  id: string
  business_no?: string | null
  process_instance_id?: string | null
  rules: FormRule[]
  status?: string
  initiator_id?: string
  initiator_name?: string | null
  created_at?: string
  updated_at?: string | null
  retroactive_field_perms?: { field: string; access: string; node_name?: string }[]
}

export default function FormDataListPage({
  templateId: propId,
  moduleTitle,
  fillPath: fillPathProp,
  templateCode,
  dashboardPath,
  legacySchemeList,
}: {
  /** 侧栏模块传入；缺省则从路由 /lowcode/forms/:id/data 取 */
  templateId?: string
  moduleTitle?: string
  /** 侧栏模块显式指定「新增」路径，避免落到 /lowcode/forms/... 导致菜单高亮错乱 */
  fillPath?: string
  /** 内置模块 code，用于图纸表单分区布局 */
  templateCode?: string
  /** 可选仪表盘入口（如收款登记仪表盘） */
  dashboardPath?: string
  /** 旧版合并方案管理列表：新建走拆分菜单 */
  legacySchemeList?: boolean
} = {}) {
  const { id: paramId = '' } = useParams()
  const id = propId || paramId
  const nav = useNavigate()
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const deepInstanceId = searchParams.get('instance')
  const reviseTaskId = searchParams.get('reviseTask')
  const deepOpenedRef = useRef<string | null>(null)
  const userRoles = useAuthStore((s) => s.user?.roles) || []
  const hasPermission = useAuthStore((s) => s.hasPermission)
  const canActivateFlow = hasPermission('workflow:activate') || hasPermission('workflow:manage')
  const [name, setName] = useState('')
  const [schemaFields, setSchemaFields] = useState<FieldDefinition[]>([])

  /** 列表筛选：业务字段 + 明细子表可筛列 + 系统字段（提交人） */
  const filterFields = useMemo<FieldDefinition[]>(() => [
    { id: '__sys_initiator', type: 'person', label: '提交人' },
    ...expandFilterableFormFields(schemaFields),
  ], [schemaFields])
  /** 列配置可选的全部可列表字段 */
  const [allColFields, setAllColFields] = useState<FieldDefinition[]>([])
  /** 默认可见列 id（listColumns / 启发式）；其余为 optIn */
  const [defaultColIds, setDefaultColIds] = useState<string[]>([])
  const [rules, setRules] = useState<FormRule[]>([])
  const [items, setItems] = useState<FormInstance[]>([])
  const [total, setTotal] = useState(0)
  const [pageNo, setPageNo] = useState(1)
  const [loading, setLoading] = useState(false)
  const [keywordInput, setKeywordInput] = useState('')
  const [keyword, setKeyword] = useState('')
  const [statusFilter, setStatusFilter] = useState<string | undefined>()
  const colStorageKey = COL_STORAGE_PREFIX + listFilterMemoryKey(templateCode, id)
  const filterMemoryKey = listFilterMemoryKey(templateCode, id)
  const [fieldFilters, setFieldFilters] = useState<FormFilterDsl | null>(
    () => loadAppliedFilters(filterMemoryKey),
  )
  const [colState, setColStateRaw] = useState<ColumnState>(() => loadColState(colStorageKey))
  const [viewRec, setViewRec] = useState<ViewRec | null>(null)
  const [viewPresentation, setViewPresentation] = useState<'modal' | 'drawer'>('modal')
  const [modalFullscreen, setModalFullscreen] = useState(false)
  const [serialPreviews, setSerialPreviews] = useState<Record<string, string>>({})
  const userId = useAuthStore((s) => s.user?.id)
  const [wfDetail, setWfDetail] = useState<WfInstanceDetail | null>(null)
  const { openWith: openWfDrawer, node: wfDrawerNode } = useWfProcessDrawer(() => {
    load()
    if (viewRec?.id) void loadWorkflow(viewRec.id)
  })
  const effectiveReviseTaskId = useMemo(
    () => resolveReviseTaskId(wfDetail, { urlTaskId: reviseTaskId, userId }),
    [wfDetail, reviseTaskId, userId],
  )
  const canActRevise = canUserActRevise(wfDetail, effectiveReviseTaskId, userId)
  const isReviseFlow = Boolean(effectiveReviseTaskId && canActRevise)
  const canOpenReviseDrawer = Boolean(
    wfDetail?.id
    && hasActiveReviseStep(wfDetail)
    && (viewRec?.status === 'returned' || viewRec?.status === 'rejected' || viewRec?.status === 'withdrawn')
    && !isReviseFlow
    && userId
    && (wfDetail.initiator_id === userId || canActRevise),
  )
  const [wfCommenting, setWfCommenting] = useState(false)
  const [activateOpen, setActivateOpen] = useState(false)
  const [nameMaps, setNameMaps] = useState<NameMaps>({
    users: {}, depts: {}, projects: {}, contracts: {}, customers: {},
  })
  const isModule = Boolean(propId)
  const fillPath = fillPathProp
    || (isModule ? `${location.pathname.replace(/\/$/, '')}/fill` : `/lowcode/forms/${id}/fill`)
  const drawingLayout = templateCode ? DRAWING_FORM_LAYOUT[templateCode] : undefined
  const listColLabels = useMemo(() => resolveListColumnLabels(templateCode) || {}, [templateCode])
  const listFieldTitle = (f: FieldDefinition) => listColLabels[f.id] || f.label
  const expandDetails = useMemo(
    () => resolveListExpandDetails(schemaFields, templateCode),
    [schemaFields, templateCode],
  )
  const expandDetail = expandDetails[0]
  const detailColGroups = useMemo(() => {
    const max = drawingLayout?.listDetailMaxCols ?? 8
    return expandDetails.map((df) => ({
      field: df,
      cols: pickDetailListColumns(df, max),
    }))
  }, [expandDetails, drawingLayout])
  const flatRows = useMemo(
    () => (expandDetails.length
      ? flattenInstancesByDetails(items, expandDetails.map((d) => d.id))
      : null),
    [expandDetails, items],
  )
  /** 明细展开时抬高 Ant Table pageSize，避免同一 API 页明细被误切成 20 行 */
  const tablePageSize = useMemo(
    () => resolveExpandDetailTablePageSize(
      LIST_PAGE_SIZE,
      expandDetails.length ? (flatRows?.length ?? 0) : null,
    ),
    [expandDetails.length, flatRows?.length],
  )

  // 切换模板时重载列配置与筛选记忆
  useEffect(() => {
    setColStateRaw(loadColState(colStorageKey))
    setFieldFilters(loadAppliedFilters(filterMemoryKey))
  }, [colStorageKey, filterMemoryKey])

  const setColState = useCallback((cs: ColumnState) => {
    setColStateRaw(cs)
    try { localStorage.setItem(colStorageKey, JSON.stringify(cs)) } catch { /* ignore */ }
  }, [colStorageKey])

  const resetColumns = useCallback(() => {
    setColState({ hidden: [], order: [], shown: [], widths: {} })
  }, [setColState])

  const defaultColIdSet = useMemo(() => new Set(defaultColIds), [defaultColIds])

  const colFields = useMemo(() => {
    const hidden = new Set(colState.hidden || [])
    const shown = new Set(colState.shown || [])
    const byId = new Map(allColFields.map((f) => [f.id, f]))
    // 默认列在前，再按用户 order，最后补其余可列表字段
    const baseOrder = [
      ...defaultColIds.filter((k) => byId.has(k)),
      ...allColFields.map((f) => f.id).filter((k) => !defaultColIdSet.has(k)),
    ]
    const orderedIds = [
      ...(colState.order || []).filter((k) => byId.has(k)),
      ...baseOrder.filter((k) => !(colState.order || []).includes(k)),
    ]
    return orderedIds.map((k) => byId.get(k)!).filter((f) => {
      if (!f) return false
      if (!defaultColIdSet.has(f.id)) return shown.has(f.id)
      return !hidden.has(f.id)
    })
  }, [allColFields, colState, defaultColIds, defaultColIdSet])

  const colMeta: ColMeta[] = useMemo(
    () => allColFields.map((f) => ({
      key: f.id,
      title: listColLabels[f.id] || f.label,
      optIn: !defaultColIdSet.has(f.id),
    })),
    [allColFields, defaultColIdSet, listColLabels],
  )

  const buildQueryParams = useCallback((pageOverride?: number) => {
    const params: Record<string, unknown> = {
      template_id: id,
      pageNo: pageOverride ?? pageNo,
      pageSize: LIST_PAGE_SIZE,
    }
    if (keyword) params.keyword = keyword
    if (statusFilter) params.status = statusFilter
    if (fieldFilters?.rules?.length) params.filters = JSON.stringify(fieldFilters)
    return params
  }, [id, pageNo, keyword, statusFilter, fieldFilters])

  const load = useCallback(async () => {
    if (!id) return
    setLoading(true)
    try {
      const res = await lowcodeApi.listInstances(buildQueryParams())
      setItems(res.data.items)
      setTotal(res.data.total)
    } finally { setLoading(false) }
  }, [id, buildQueryParams])

  useEffect(() => {
    if (!id) return
    (async () => {
      const tpl = await lowcodeApi.getTemplate(id)
      setName(tpl.data.name)
      try {
        const ver = await lowcodeApi.publishedVersion(id)
        const fs = (ver.data.field_definitions as FieldDefinition[]) || []
        setSchemaFields(fs)
        const expands = resolveListExpandDetails(fs, templateCode)
        const exclude = expands.length ? new Set(expands.map((d) => d.id)) : undefined
        const preferred = resolveListColumnIds(templateCode)
        const defaults = pickListColumns(
          fs,
          expands.length ? 10 : 8,
          exclude,
          preferred,
        )
        // 左侧固定「流水号」列已展示 serial_no；设计卡号等其它 auto_number 仍应出现在业务列
        const defaultIds = defaults
          .filter((f) => f.id !== 'serial_no')
          .map((f) => f.id)
        setDefaultColIds(defaultIds.length ? defaultIds : defaults.map((f) => f.id))
        setAllColFields(filterListableFields(fs, exclude))
        setRules((ver.data.rule_definitions as FormRule[]) || [])
      } catch { /* 未发布 */ }
    })()
  }, [id, templateCode])

  // 搜索框防抖 → 同步 keyword；keyword 变化时回到第 1 页
  useEffect(() => {
    const t = window.setTimeout(() => setKeyword(keywordInput.trim()), 350)
    return () => window.clearTimeout(t)
  }, [keywordInput])

  useEffect(() => { setPageNo(1) }, [keyword])

  useEffect(() => { load() }, [load])

  // 审批修订待办深链：/shipment-notices?instance=...&reviseTask=...&edit=1
  useEffect(() => {
    if (!id || !deepInstanceId) return
    if (deepOpenedRef.current === deepInstanceId) return
    deepOpenedRef.current = deepInstanceId
    const editMode = searchParams.get('edit') === '1' || !!reviseTaskId
    void openView(deepInstanceId, !editMode)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, deepInstanceId, reviseTaskId])

  // 退回/驳回/撤回后的修订待办：自动进入编辑并露出底部「保存并重新提交」
  useEffect(() => {
    if (!viewRec?.id || !isReviseFlow || !viewRec.readonly) return
    setViewRec((s) => (s ? { ...s, readonly: false } : s))
  }, [viewRec?.id, isReviseFlow, viewRec?.readonly])

  const applyFieldFilters = (dsl: FormFilterDsl | null) => {
    setFieldFilters(dsl)
    saveAppliedFilters(filterMemoryKey, dsl)
    setPageNo(1)
  }

  const buildExportUrl = useCallback((mode: 'filtered' | 'all') => {
    const q = new URLSearchParams({ template_id: id || '' })
    if (mode === 'filtered') {
      if (keyword) q.set('keyword', keyword)
      if (statusFilter) q.set('status', statusFilter)
      if (fieldFilters?.rules?.length) q.set('filters', JSON.stringify(fieldFilters))
    }
    return `/api/v1/lc/form-instances/export?${q.toString()}`
  }, [id, keyword, statusFilter, fieldFilters])

  const runExport = useCallback((mode: 'filtered' | 'all') => {
    const label = mode === 'filtered' ? '筛选后的数据' : '全部数据'
    void downloadFile(buildExportUrl(mode), `${name || '表单数据'}_${label}.xlsx`).catch((err: unknown) => {
      const msg = err instanceof Error ? err.message : '导出失败'
      message.error(msg)
    })
  }, [buildExportUrl, name])

  const exportMenuItems = useMemo<MenuProps['items']>(() => [
    {
      key: 'filtered',
      label: '筛选后的数据',
      disabled: total === 0,
      onClick: () => runExport('filtered'),
    },
    {
      key: 'all',
      label: '全部数据',
      onClick: () => runExport('all'),
    },
  ], [runExport, total])

  // 列表里 person/department/project/contract/customer 存的是 id，需解析成显示名
  useEffect(() => {
    if (!items.length || !colFields.length) return
    const personIds: string[] = []
    const deptIds: string[] = []
    const projectIds: string[] = []
    const contractIds: string[] = []
    const customerIds: string[] = []
    const detailFlatCols = detailColGroups.flatMap((g) => g.cols)
    const mapFields = [...colFields, ...detailFlatCols]
    const needDept = mapFields.some((f) => f.type === 'department' || f.type === 'department_multi')
    for (const f of mapFields) {
      if (f.type === 'person' || f.type === 'person_multi') {
        for (const row of items) personIds.push(...collectIds(row.form_data?.[f.id]))
      }
      if (f.type === 'department' || f.type === 'department_multi') {
        for (const row of items) deptIds.push(...collectIds(row.form_data?.[f.id]))
      }
      if (f.type === 'project') {
        for (const row of items) projectIds.push(...collectIds(row.form_data?.[f.id]))
      }
      if (f.type === 'contract') {
        for (const row of items) {
          if (templateCode === 'prod_card_supplement' && f.id === 'contract_no_select') {
            contractIds.push(...collectIds(resolveProdCardContractPick(row.form_data)))
          } else {
            contractIds.push(...collectIds(row.form_data?.[f.id]))
          }
          for (const g of detailColGroups) {
            const details = Array.isArray(row.form_data?.[g.field.id])
              ? (row.form_data![g.field.id] as Record<string, unknown>[])
              : []
            if (g.cols.some((d) => d.id === f.id)) {
              for (const d of details) contractIds.push(...collectIds(d?.[f.id]))
            }
          }
        }
      }
      if (f.type === 'customer') {
        for (const row of items) customerIds.push(...collectIds(row.form_data?.[f.id]))
      }
    }
    let alive = true
    ;(async () => {
      const projectLabelMode = mapFields.some(
        (f) => f.type === 'project' && !!(f.props as { prefer_code?: boolean } | undefined)?.prefer_code,
      ) ? 'code' as const : 'default' as const
      const [users, depts, projects, contracts, customers] = await Promise.all([
        personIds.length ? getPersonLabelMap(personIds) : Promise.resolve({}),
        needDept ? getDeptNameMap(deptIds) : Promise.resolve({}),
        projectIds.length ? getProjectLabelMap(projectIds, projectLabelMode) : Promise.resolve({}),
        contractIds.length ? getContractLabelMap(contractIds) : Promise.resolve({}),
        customerIds.length ? getCustomerLabelMap(customerIds) : Promise.resolve({}),
      ])
      if (!alive) return
      setNameMaps({ users, depts, projects, contracts, customers })
    })()
    return () => { alive = false }
  }, [items, colFields, detailColGroups, templateCode])

  const renderListFieldCell = useCallback((
    f: FieldDefinition,
    row: FormInstance | DetailFlatRow,
  ): ReactNode => {
    const rec = 'record' in row ? row.record : row
    const fd = rec.form_data
    if (templateCode === 'prod_card_supplement' && f.id === 'contract_no_select') {
      return renderProdCardContractCell(fd, nameMaps)
    }
    return cellNode(f, fd?.[f.id], nameMaps)
  }, [templateCode, nameMaps])

  const loadWorkflow = async (recId: string, _processInstanceId?: string | null) => {
    try {
      // 始终按 form_instance 取最新有效流程（避免 form.process_instance_id 指向旧实例）
      const res = await workflowApi.byFormInstance({ form_instance_id: recId })
      setWfDetail(res.data || null)
    } catch {
      setWfDetail(null)
    }
  }

  const openView = async (
    recId: string,
    readonly: boolean,
    opts?: { presentation?: 'modal' | 'drawer' },
  ) => {
    const res = await lowcodeApi.getInstance(recId)
    const detailRules = (res.data.rule_definitions as FormRule[] | undefined)
    setViewRec({
      fields: res.data.field_definitions,
      value: res.data.form_data,
      readonly,
      id: recId,
      business_no: res.data.business_no,
      process_instance_id: res.data.process_instance_id,
      rules: detailRules?.length ? detailRules : rules,
      status: res.data.status,
      initiator_id: res.data.initiator_id,
      initiator_name: res.data.initiator_name,
      created_at: res.data.created_at,
      updated_at: res.data.updated_at,
      retroactive_field_perms: (res.data as FormInstanceDetail).retroactive_field_perms,
    })
    if (opts?.presentation) setViewPresentation(opts.presentation)
    setWfDetail(null)
    await loadWorkflow(recId, res.data.process_instance_id)
  }

  const closeView = () => {
    setViewRec(null)
    setViewPresentation('modal')
    setWfDetail(null)
    setSerialPreviews({})
    setModalFullscreen(false)
    if (searchParams.has('instance') || searchParams.has('reviseTask') || searchParams.has('edit')) {
      const next = new URLSearchParams(searchParams)
      next.delete('instance')
      next.delete('reviseTask')
      next.delete('edit')
      setSearchParams(next, { replace: true })
      deepOpenedRef.current = null
    }
  }

  const [navBusy, setNavBusy] = useState(false)

  const viewNavIndex = useMemo(() => {
    if (!viewRec) return -1
    return items.findIndex((r) => r.id === viewRec.id)
  }, [items, viewRec])

  const viewNavGlobalIndex = viewNavIndex >= 0
    ? (pageNo - 1) * LIST_PAGE_SIZE + viewNavIndex
    : -1

  const goViewRelative = async (delta: -1 | 1) => {
    if (!viewRec || navBusy || !id) return
    const idx = items.findIndex((r) => r.id === viewRec.id)
    if (idx >= 0) {
      const nextIdx = idx + delta
      if (nextIdx >= 0 && nextIdx < items.length) {
        setNavBusy(true)
        try {
          await openView(items[nextIdx].id, true)
        } finally {
          setNavBusy(false)
        }
        return
      }
    }
    const targetPage = pageNo + delta
    const maxPage = Math.max(1, Math.ceil(total / LIST_PAGE_SIZE) || 1)
    if (targetPage < 1 || targetPage > maxPage) return
    setNavBusy(true)
    try {
      const res = await lowcodeApi.listInstances(buildQueryParams(targetPage))
      const nextItems = res.data.items || []
      setPageNo(targetPage)
      setItems(nextItems)
      setTotal(res.data.total)
      const pick = delta > 0 ? nextItems[0] : nextItems[nextItems.length - 1]
      if (pick) await openView(pick.id, true)
    } finally {
      setNavBusy(false)
    }
  }

  // 编辑弹窗：选部门 → 回填部门编号
  useEffect(() => {
    if (!viewRec || viewRec.readonly) return
    if (!viewRec.fields.some((f) => f.id === 'dept_code')) return
    const raw = viewRec.value?.department
    const deptId = raw == null || raw === ''
      ? ''
      : (typeof raw === 'object' && raw !== null && 'id' in (raw as object)
        ? String((raw as { id?: string }).id || '')
        : String(raw))
    if (!deptId) return
    let alive = true
    ;(async () => {
      try {
        const r = await lowcodeApi.lookupDeptCode(deptId)
        const code = (r.data?.dept_code || '').trim()
        if (!alive || !code) return
        setViewRec((s) => {
          if (!s || s.value?.dept_code === code) return s
          return { ...s, value: { ...s.value, dept_code: code } }
        })
      } catch { /* ignore */ }
    })()
    return () => { alive = false }
  }, [viewRec?.readonly, viewRec?.value?.department, viewRec?.fields])

  // 编辑弹窗：选业务员 → 回填区域经理/组长
  useEffect(() => {
    if (!viewRec || viewRec.readonly) return
    const salesField = viewRec.fields.find(isSalespersonField)
    const regionField = viewRec.fields.find(isRegionManagerField)
    if (!salesField || !regionField) return
    const sid = parsePersonFieldId(viewRec.value?.[salesField.id])
    if (!sid) return
    let alive = true
    ;(async () => {
      try {
        const r = await lowcodeApi.lookupSalespersonRegion(sid)
        const mid = (r.data?.region_manager_id || '').trim()
        if (!alive || !mid) return
        setViewRec((s) => {
          if (!s || s.value?.[regionField.id] === mid) return s
          return { ...s, value: { ...s.value, [regionField.id]: mid } }
        })
      } catch { /* ignore */ }
    })()
    return () => { alive = false }
  }, [
    viewRec?.readonly,
    viewRec?.fields,
    viewRec?.value?.sales_person,
    viewRec?.value?.salesperson,
    viewRec?.value?.owner_id,
    viewRec?.value?.no_sales_person,
    viewRec?.value?.yes_sales_person,
  ])

  // 编辑弹窗：流水号预览
  useEffect(() => {
    if (!viewRec || viewRec.readonly || !id) return
    if (!viewRec.fields.some((f) => f.type === 'auto_number')) return
    const t = setTimeout(() => {
      lowcodeApi.peekSerials(id, viewRec.value || {}).then((res) => {
        setSerialPreviews(res.data || {})
      }).catch(() => { /* ignore */ })
    }, 200)
    return () => clearTimeout(t)
  }, [id, viewRec?.readonly, viewRec?.value, viewRec?.fields])

  const saveEdit = async () => {
    if (!viewRec) return
    // 存草稿不校验必填（与 FormFillPage 一致）；提交审批才走 findRequiredError
    try {
      await lowcodeApi.updateInstance(viewRec.id, { form_data: viewRec.value })
      message.success('已保存')
      closeView()
      load()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg || '保存失败')
    }
  }

  const submitDraft = async () => {
    if (!viewRec) return
    if (isReviseFlow) {
      message.info('当前为退回/驳回修订，请使用「保存并重新提交」')
      return
    }
    if ((viewRec.status === 'returned' || viewRec.status === 'rejected') && wfDetail?.id) {
      message.warning('流程仍有关联修订待办，请使用「保存并重新提交」')
      return
    }
    const displayFields = drawingLayout
      ? applyDrawingFormLayout(templateCode, viewRec.fields)
      : viewRec.fields
    const states = computeFieldStates(
      displayFields, viewRec.value, viewRec.rules,
      deriveRolePerms(displayFields, userRoles),
    )
    const e = findRequiredError(displayFields, states, viewRec.value, viewRec.rules)
    if (e) {
      message.error(e.message)
      scrollToLcField(e.fieldId)
      return
    }
    try {
      await lowcodeApi.submitInstance(viewRec.id, { form_data: viewRec.value })
      message.success('已提交审批')
      closeView()
      load()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg || '提交失败')
    }
  }

  const saveReviseDraft = async () => {
    if (!viewRec) return
    try {
      await lowcodeApi.updateInstance(viewRec.id, { form_data: viewRec.value })
      message.success('已暂存')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg || '暂存失败')
    }
  }

  const resubmitRevise = async () => {
    if (!viewRec || !effectiveReviseTaskId) return
    const displayFields = drawingLayout
      ? applyDrawingFormLayout(templateCode, viewRec.fields)
      : viewRec.fields
    const states = computeFieldStates(
      displayFields, viewRec.value, viewRec.rules,
      deriveRolePerms(displayFields, userRoles),
    )
    const e = findRequiredError(displayFields, states, viewRec.value, viewRec.rules)
    if (e) {
      message.error(e.message)
      scrollToLcField(e.fieldId)
      return
    }
    try {
      await lowcodeApi.updateInstance(viewRec.id, { form_data: viewRec.value })
      await workflowApi.act(effectiveReviseTaskId, { action: 'resubmit' })
      message.success('已重新提交')
      closeView()
      load()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg || '重新提交失败')
    }
  }

  const handleEndProcess = () => {
    if (!wfDetail?.id) return
    const terminating = isRunningProcessTerminate(wfDetail)
    Modal.confirm({
      title: '确认结束流程？',
      content: terminating
        ? '结束后流程将终止，当前全部待办关闭，单据将变为已驳回。此操作不可撤销。'
        : '结束后将关闭「修改并重新提交」等待办。如需再走审批，可重新发起或激活流程。',
      okText: '结束流程',
      okType: 'danger',
      onOk: async () => {
        try {
          if (
            !terminating
            && effectiveReviseTaskId
            && canUserActRevise(wfDetail, effectiveReviseTaskId, userId)
          ) {
            await workflowApi.endProcessByTask(effectiveReviseTaskId)
          } else {
            await workflowApi.endProcess(wfDetail.id)
          }
          message.success('已结束流程')
          closeView()
          load()
        } catch (err: unknown) {
          const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
          message.error(msg || '结束流程失败')
        }
      },
    })
  }

  const handleWfComment = async (content: string) => {
    if (!wfDetail?.id) return
    setWfCommenting(true)
    try {
      await workflowApi.comment(wfDetail.id, content)
      message.success('评论已发表')
      await loadWorkflow(viewRec!.id, wfDetail.id)
    } catch {
      message.error('发表评论失败')
    } finally {
      setWfCommenting(false)
    }
  }

  const del = async (recId: string) => {
    try {
      await lowcodeApi.deleteInstance(recId)
      message.success('已删除')
      if (viewRec?.id === recId) closeView()
      load()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg || '删除失败')
    }
  }

  const canPrintScheme = templateCode === 'scheme_management'
    || templateCode === 'drawing_requisition'
    || templateCode === 'install_drawing_notice'
    || templateCode === 'cs_drawing_request'
  const canPrintProdCard = templateCode === 'prod_card_supplement'
  const canPrintQuote = isQuoteManagementForm(templateCode)
  const canPrintBonus = isBizBonusForm(templateCode)
  const postCompleteEditable = templateCode === 'drawing_requisition'
    || templateCode === 'install_drawing_notice'
    || templateCode === 'cs_drawing_request'
    || templateCode === 'prod_card_supplement'
  /** 列表弹窗内可编辑（审批中/已通过也允许，走 form-instances PUT） */
  const canEditRecord = (_status?: string | null) => true
  const canResubmitRecord = (status?: string | null) =>
    status === 'draft' || status === 'rejected' || status === 'returned'
  /** 有 form_data:delete 且为收款登记时，对齐简道云财务权限组可删已走流程单据 */
  const canForceDeleteAfterFlow =
    templateCode === 'payment_registration' && hasPermission('form_data:delete')
  /** 流程一旦发起默认不可删；收款登记财务删除权限除外 */
  const canDeleteRecord = (rec: ViewRec | null) => {
    if (!rec || !hasPermission('form_data:delete')) return false
    if (canForceDeleteAfterFlow) return true
    return !rec.process_instance_id && !wfDetail?.id
  }

  /** 通过后编辑：露出审批才填字段（设计单分派/科室/下单日期/附件等） */
  const includeApproverFieldsOnEdit = Boolean(
    viewRec
    && !viewRec.readonly
    && postCompleteEditable,
  )

  const handlePrint = async (recId: string, prodMode?: ProdCardPrintMode, bonusMode?: BizBonusPrintMode) => {
    try {
      const res = await lowcodeApi.getInstance(recId)
      let flowSteps: WfInstanceDetail['flow_steps'] | undefined
      try {
        if (res.data.process_instance_id) {
          const wf = await workflowApi.instance(res.data.process_instance_id)
          flowSteps = wf.data?.flow_steps
        } else {
          const wf = await workflowApi.byFormInstance({ form_instance_id: recId })
          flowSteps = wf.data?.flow_steps
        }
      } catch { /* 无流程也可打印 */ }
      const formData = res.data.form_data || {}
      if (canPrintQuote) {
        await printQuoteInstance({
          formData,
          fieldDefinitions: res.data.field_definitions || [],
          businessNo: res.data.business_no,
        })
        return
      }
      if (canPrintBonus) {
        await printBizBonusInstance({
          formData,
          fieldDefinitions: res.data.field_definitions || [],
          businessNo: res.data.business_no,
          flowSteps,
          mode: bonusMode || defaultBizBonusPrintMode(),
        })
        return
      }
      if (canPrintProdCard) {
        await printProdCardInstance({
          formData,
          fieldDefinitions: res.data.field_definitions || [],
          businessNo: res.data.business_no,
          flowSteps,
          mode: prodMode || defaultProdCardPrintMode(formData),
        })
        return
      }
      await printSchemeInstance({
        formData,
        fieldDefinitions: res.data.field_definitions || [],
        businessNo: res.data.business_no,
        flowSteps,
      })
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg || '打印失败')
    }
  }

  const enterEdit = () => {
    setViewRec((s) => (s ? { ...s, readonly: false } : s))
  }

  const handleCopyRecordLink = () => {
    if (!viewRec) return
    const url = new URL(window.location.href)
    url.searchParams.set('instance', viewRec.id)
    void navigator.clipboard.writeText(url.toString()).then(
      () => message.success('链接已复制'),
      () => message.error('复制链接失败'),
    )
  }

  const handleCopyRecord = async () => {
    if (!viewRec || !id) return
    try {
      const res = await lowcodeApi.getInstance(viewRec.id)
      const fd = { ...(res.data.form_data || {}) }
      delete fd.serial_no
      const created = await lowcodeApi.createInstance({
        template_id: id,
        form_data: fd,
        as_draft: true,
      })
      message.success('已复制为新草稿')
      await openView(created.data.id, false)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg || '复制失败')
    }
  }

  const viewRecordTitle = useMemo(() => {
    if (!viewRec) return '查看记录'
    return resolveRecordDisplayNo({
      businessNo: viewRec.business_no,
      formData: viewRec.value,
      fallback: viewRec.readonly ? '查看记录' : '编辑记录',
    })
  }, [viewRec])

  const canEndProcess = canEndProcessInRecordView(wfDetail, userId, effectiveReviseTaskId, {
    canManageWorkflow: hasPermission('workflow:activate') || hasPermission('workflow:manage'),
    canDeleteFormData: hasPermission('form_data:delete'),
  })

  const recordToolbarActions = useMemo((): RecordToolbarAction[] => {
    if (!viewRec) return []
    const actions: RecordToolbarAction[] = []

    if (canPrintQuote || canPrintScheme) {
      actions.push({
        key: 'print',
        label: '打印',
        icon: <PrinterOutlined />,
        onClick: () => { void handlePrint(viewRec.id) },
      })
    }
    if (canPrintProdCard) {
      actions.push({
        key: 'print-prod',
        label: '打印',
        icon: <PrinterOutlined />,
        render: () => (
          <Dropdown
            menu={{
              items: [
                {
                  key: 'notice',
                  label: '生产通知单',
                  onClick: () => { void handlePrint(viewRec.id, 'notice') },
                },
                {
                  key: 'supplement',
                  label: '生产补充卡',
                  onClick: () => { void handlePrint(viewRec.id, 'supplement') },
                },
              ],
            }}
            trigger={['click']}
          >
            <Button type="text" icon={<PrinterOutlined />}>
              打印 <DownOutlined />
            </Button>
          </Dropdown>
        ),
      })
    }
    if (canPrintBonus) {
      actions.push({
        key: 'print-bonus',
        label: '打印',
        icon: <PrinterOutlined />,
        render: () => (
          <Dropdown
            menu={{
              items: (Object.entries(BIZ_BONUS_PRINT_MODE_LABELS) as [BizBonusPrintMode, string][]).map(
                ([key, label]) => ({
                  key,
                  label,
                  onClick: () => { void handlePrint(viewRec.id, undefined, key) },
                }),
              ),
            }}
            trigger={['click']}
          >
            <Button type="text" icon={<PrinterOutlined />}>
              打印 <DownOutlined />
            </Button>
          </Dropdown>
        ),
      })
    }
    actions.push({
      key: 'copy',
      label: '复制',
      icon: <CopyOutlined />,
      onClick: () => { void handleCopyRecord() },
    })
    if (canEditRecord(viewRec.status) && viewRec.readonly && !isReviseFlow) {
      actions.push({
        key: 'edit',
        label: '编辑',
        icon: <EditOutlined />,
        onClick: enterEdit,
      })
    }
    if (canOpenReviseDrawer && !isReviseFlow) {
      actions.push({
        key: 'revise',
        label: '修改并重新提交',
        icon: <SendOutlined />,
        onClick: () => openWfDrawer(wfDetail!.id, effectiveReviseTaskId),
      })
    }
    if (canResubmitRecord(viewRec.status) && !isReviseFlow && !wfDetail?.id) {
      actions.push({
        key: 'submit',
        label: '提交审批',
        icon: <SendOutlined />,
        onClick: submitDraft,
      })
    }
    if (canActivateFlow && wfDetail?.can_activate && wfDetail.id) {
      actions.push({
        key: 'activate',
        label: '激活流程',
        icon: <ThunderboltOutlined />,
        onClick: () => setActivateOpen(true),
      })
    }
    if (canEndProcess) {
      actions.push({
        key: 'end-process',
        label: '结束流程',
        icon: <StopOutlined />,
        danger: true,
        onClick: handleEndProcess,
      })
    }
    if (canDeleteRecord(viewRec)) {
      actions.push({
        key: 'delete',
        label: '删除',
        icon: <DeleteOutlined />,
        danger: true,
        render: () => (
          <Popconfirm title="确认删除该记录?" onConfirm={() => del(viewRec.id)}>
            <Button type="text" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        ),
      })
    }
    return actions
  // eslint-disable-next-line react-hooks/exhaustive-deps -- handlePrint 等稳定引用省略
  }, [
    viewRec, isReviseFlow, canOpenReviseDrawer, wfDetail, effectiveReviseTaskId,
    canActivateFlow, canPrintQuote, canPrintScheme, canPrintProdCard, canPrintBonus,
    canEndProcess,
  ])

  // 列表操作列只保留「查看」；打印/编辑/删除放到详情工具栏（对齐简道云）
  const renderOps = (r: FormInstance) => (
    <Space size={0}>
      <Button size="small" type="link" onClick={() => openView(r.id, true, { presentation: 'modal' })}>查看</Button>
      {canEditRecord(r.status) && (
        <Button size="small" type="link" onClick={() => openView(r.id, false, { presentation: 'modal' })}>编辑</Button>
      )}
    </Space>
  )

  const listColWidths = useMemo(() => resolveListColumnWidths(templateCode) || {}, [templateCode])
  const listFullText = useMemo(() => resolveListFullText(templateCode), [templateCode])
  const listFixedRightKeys = useMemo(() => resolveListFixedRightKeys(templateCode), [templateCode])

  const fixRight = useCallback((key: string): 'right' | undefined => {
    if (listFixedRightKeys) {
      return listFixedRightKeys.includes(key) ? 'right' : undefined
    }
    if (key === 'initiator_name') return 'right'
    if (key === 'created_at') return listFullText ? undefined : 'right'
    if (key === 'status' || key === 'current_node_name' || key === 'op') return 'right'
    return undefined
  }, [listFixedRightKeys, listFullText])

  const colWidth = (f: FieldDefinition) => {
    if (listColWidths[f.id]) return listColWidths[f.id]
    if (f.type === 'file' || f.type === 'image') return 140
    if (f.type === 'datetime' || f.type === 'date') return listFullText ? 170 : 130
    if (f.type === 'person' || f.type === 'department'
      || f.type === 'person_multi' || f.type === 'department_multi') {
      return listFullText ? 160 : 110
    }
    if (f.type === 'customer' || f.type === 'contract') return listFullText ? 220 : 160
    if (f.type === 'textarea' || /要求|备注|路线|事由|名称/.test(f.label || '')) {
      return listFullText ? 240 : 180
    }
    return listFullText ? 160 : 140
  }

  /** 列内裁剪防串列；悬停 title 看全文（对齐简道云：加宽 + 不盖住邻列） */
  const cellEllipsis = (f: FieldDefinition) => {
    if (f.type === 'file' || f.type === 'image') return false
    return { showTitle: true } as const
  }

  const listNoCol = {
    title: '流水号',
    key: 'business_no',
    width: listColWidths.serial_no ?? (listFullText ? 168 : 140),
    ellipsis: { showTitle: true } as const,
    fixed: 'left' as const,
    render: (_: unknown, row: FormInstance | DetailFlatRow) => {
      const rec = expandDetails.length ? (row as DetailFlatRow).record : (row as FormInstance)
      const no = recordListNo(rec, schemaFields)
      return (
        <a className="font-mono text-primary" title={no} onClick={() => openView(rec.id, true, { presentation: 'modal' })}>
          {no}
        </a>
      )
    },
  }

  const detailGroupCols = detailColGroups.map(({ field: df, cols }) => ({
    title: df.label || '明细',
    key: `__detail_${df.id}`,
    children: cols.map((c) => ({
      title: c.label,
      key: `${df.id}.${c.id}`,
      ellipsis: { showTitle: true } as const,
      width: c.type === 'number' || c.type === 'amount' ? 90
        : c.type === 'datetime' || c.type === 'date' ? (listFullText ? 170 : 120)
          : (listFullText ? 160 : 130),
      render: (_: unknown, row: FormInstance | DetailFlatRow) => {
        const dr = (row as DetailFlatRow).detailRows?.[df.id]
          ?? ((df.id === expandDetail?.id) ? (row as DetailFlatRow).detailRow : null)
        return cellNode(c, dr?.[c.id], nameMaps)
      },
    })),
  }))

  const detailColsCount = detailColGroups.reduce((n, g) => n + g.cols.length, 0)

  const columns: ColumnsType<FormInstance | DetailFlatRow> = expandDetails.length && flatRows
    ? [
        {
          ...listNoCol,
          onCell: (row: FormInstance | DetailFlatRow) => ({
            rowSpan: (row as DetailFlatRow).rowSpan,
          }),
        },
        ...colFields.map((f) => ({
          title: listFieldTitle(f),
          key: f.id,
          ellipsis: cellEllipsis(f),
          width: colWidth(f),
          onCell: (row: FormInstance | DetailFlatRow) => ({
            rowSpan: (row as DetailFlatRow).rowSpan,
          }),
          render: (_: unknown, row: FormInstance | DetailFlatRow) =>
            renderListFieldCell(f, row),
        })),
        ...detailGroupCols,
        {
          title: '提交人', key: 'initiator_name', width: 100,
          onCell: (row) => ({ rowSpan: (row as DetailFlatRow).rowSpan }),
          render: (_: unknown, row) => {
            const r = (row as DetailFlatRow).record
            return r.initiator_name || '—'
          },
        },
        {
          // 明细 rowSpan 时禁用 fixed：Ant Design 固定列与合并单元格行高不同步
          title: '提交时间', key: 'created_at', width: listFullText ? 178 : 160,
          ellipsis: { showTitle: true } as const,
          onCell: (row) => ({ rowSpan: (row as DetailFlatRow).rowSpan }),
          render: (_: unknown, row) => {
            const v = (row as DetailFlatRow).record.created_at
            return v ? formatCellDateTime(v, true) : '—'
          },
        },
        ...(listFullText ? [{
          title: '更新时间',
          key: 'updated_at',
          width: 178,
          ellipsis: { showTitle: true } as const,
          onCell: (row: FormInstance | DetailFlatRow) => ({
            rowSpan: (row as DetailFlatRow).rowSpan,
          }),
          render: (_: unknown, row: FormInstance | DetailFlatRow) => {
            const r = (row as DetailFlatRow).record
            const v = r.updated_at || r.created_at
            return v ? formatCellDateTime(v, true) : '—'
          },
        }] : []),
        {
          // 明细 rowSpan 时禁用 fixed：Ant Design 固定列与合并单元格行高不同步，会叠字/错位
          title: '流程状态', key: 'status', width: 100,
          onCell: (row) => ({ rowSpan: (row as DetailFlatRow).rowSpan }),
          render: (_: unknown, row) => {
            const s = (row as DetailFlatRow).record.status || ''
            const t = STATUS_TAG[s] || { color: 'default', text: s }
            return <Tag color={t.color}>{t.text}</Tag>
          },
        },
        {
          title: '当前节点', key: 'current_node_name', width: 120,
          ellipsis: { showTitle: true } as const,
          onCell: (row) => ({ rowSpan: (row as DetailFlatRow).rowSpan }),
          render: (_: unknown, row) => renderCurrentNodeCell((row as DetailFlatRow).record),
        },
        {
          title: '操作', key: 'op', width: 72,
          onCell: (row) => ({ rowSpan: (row as DetailFlatRow).rowSpan }),
          render: (_: unknown, row) => renderOps((row as DetailFlatRow).record),
        },
      ]
    : [
        ...(templateCode === 'contract_drawing_map' ? [] : [listNoCol]),
        // 通用填报入口保留标题；侧栏业务模块以业务列为主（对齐简道云数据管理）
        ...(!isModule ? [
          {
            title: '标题', dataIndex: 'title', key: 'title', width: 160,
            ellipsis: { showTitle: true } as const,
            render: (v: string) => v || '—',
          },
        ] : []),
        ...colFields.map((f) => ({
          title: listFieldTitle(f), key: f.id,
          ellipsis: cellEllipsis(f),
          width: colWidth(f),
          render: (_: unknown, r: FormInstance | DetailFlatRow) =>
            renderListFieldCell(f, r),
        })),
        {
          title: '提交人', dataIndex: 'initiator_name', key: 'initiator_name',
          width: 100, fixed: fixRight('initiator_name'),
          ellipsis: { showTitle: true } as const,
          render: (v: string | null | undefined) => v || '—',
        },
        {
          title: '提交时间', dataIndex: 'created_at', key: 'created_at',
          width: listFullText ? 178 : 160,
          ellipsis: { showTitle: true } as const,
          fixed: fixRight('created_at'),
          render: (v: string) => (v ? formatCellDateTime(v, true) : '—'),
        },
        ...(listFullText ? [{
          title: '更新时间',
          key: 'updated_at',
          width: 178,
          ellipsis: { showTitle: true } as const,
          render: (_: unknown, r: FormInstance | DetailFlatRow) => {
            const v = (r as FormInstance).updated_at
              || (r as FormInstance).created_at
            return v ? formatCellDateTime(v, true) : '—'
          },
        }] : []),
        {
          title: '流程状态', dataIndex: 'status', key: 'status', width: 100, fixed: fixRight('status'),
          render: (s: string) => {
            const t = STATUS_TAG[s] || { color: 'default', text: s }
            return <Tag color={t.color}>{t.text}</Tag>
          },
        },
        {
          title: '当前节点', dataIndex: 'current_node_name', key: 'current_node_name',
          width: 120, fixed: fixRight('current_node_name'),
          ellipsis: { showTitle: true } as const,
          render: (_: unknown, r: FormInstance | DetailFlatRow) =>
            renderCurrentNodeCell(('record' in r ? r.record : r) as FormInstance),
        },
        {
          title: '操作', key: 'op', width: 72, fixed: fixRight('op'),
          render: (_: unknown, r: FormInstance | DetailFlatRow) => renderOps(r as FormInstance),
        },
      ]

  const onColumnWidthChange = useCallback((colKey: string, width: number) => {
    setColState((prev) => ({
      ...prev,
      widths: { ...(prev.widths || {}), [colKey]: clampColWidth(width) },
    }))
  }, [setColState])

  const tableColumns = useMemo(
    () => applyListColumnResize(columns, colState.widths || {}),
    [columns, colState.widths],
  )

  const tableScrollX = useMemo(() => {
    const biz = colFields.reduce((n, f) => n + colWidth(f), 0)
    const detail = detailColsCount ? 120 * detailColsCount + 80 : 0
    // 序号/标题余量 + 提交人 + 流程状态 + 当前节点 + 提交时间(+更新时间) + 操作
    const fixed = listFullText
      ? 120 + 100 + 100 + 120 + 178 + 178 + 72
      : 140 + 100 + 100 + 120 + 160 + 72
    return Math.max(1200, biz + detail + fixed + 40)
  }, [colFields, detailColsCount, listFullText, listColWidths])

  const showFlowPane = !!viewRec
  const layoutMaxW = drawingLayout?.contentMaxWidth ?? 0
  const modalWidth = showFlowPane
    ? Math.max(1100, layoutMaxW + 300)
    : (layoutMaxW || (drawingLayout ? 960 : 780))
  const fsProps = modalFullscreenProps(modalFullscreen, modalWidth)
  const contentMaxH = modalFullscreen
    ? 'calc(100vh - 200px)'
    : (viewPresentation === 'drawer' ? 'calc(100vh - 220px)' : '70vh')
  const displayFields = viewRec
    ? (drawingLayout ? applyDrawingFormLayout(templateCode, viewRec.fields) : viewRec.fields)
    : []

  const recordDetailFooter = viewRec && isReviseFlow
    ? [
        <Button key="c" onClick={closeView}>取消</Button>,
        <Button key="s" onClick={saveReviseDraft}>存草稿</Button>,
        <Button key="rs" type="primary" onClick={resubmitRevise}>保存并重新提交</Button>,
      ]
    : viewRec && canOpenReviseDrawer
      ? null
      : viewRec && !viewRec.readonly && canEditRecord(viewRec.status)
      ? [
          <Button key="c" onClick={closeView}>取消</Button>,
          <Button
            key="s"
            type={canResubmitRecord(viewRec.status) ? 'default' : 'primary'}
            onClick={saveEdit}
          >
            {canResubmitRecord(viewRec.status) ? '存草稿' : '保存'}
          </Button>,
          ...(canResubmitRecord(viewRec.status) && !wfDetail?.id
            ? [
                <Button key="sub" type="primary" onClick={submitDraft}>
                  提交审批
                </Button>,
              ]
            : []),
        ]
      : null

  const recordDetailInner = viewRec ? (
    <div className={`flex flex-col min-h-0${modalFullscreen ? ' flex-1' : ''}`}>
      <RecordDetailToolbar
        actions={recordToolbarActions}
        onCopyLink={handleCopyRecordLink}
        nav={{
          index: viewNavGlobalIndex,
          total,
          disabled: navBusy,
          onPrev: () => { void goViewRelative(-1) },
          onNext: () => { void goViewRelative(1) },
        }}
      />
      <RecordDetailBodyLayout
        fillHeight={modalFullscreen}
        contentMaxH={contentMaxH}
        showSide={showFlowPane}
        main={(
          <>
            <FormRenderer
              fields={displayFields}
              rules={viewRec.rules}
              mode={viewRec.readonly ? 'readonly' : 'edit'}
              value={viewRec.value}
              onChange={(v) => setViewRec((s) => (s ? { ...s, value: v } : s))}
              serialPreviews={serialPreviews}
              includeApproverFields={includeApproverFieldsOnEdit}
              retroactiveFieldPerms={viewRec.retroactive_field_perms}
              gridLayout={modalFullscreen || viewPresentation === 'drawer' ? 'adaptive' : 'default'}
            />
            <FormInstanceSystemMeta
              initiatorName={viewRec.initiator_name}
              createdAt={viewRec.created_at}
              updatedAt={viewRec.updated_at}
              status={viewRec.status}
              flowSteps={wfDetail?.flow_steps}
            />
          </>
        )}
        side={(
          <WfFlowDynamics
            fillParent={modalFullscreen}
            steps={wfDetail?.flow_steps || []}
            comments={wfDetail?.comments || []}
            onSubmitComment={wfDetail ? handleWfComment : undefined}
            commenting={wfCommenting}
            dataLog={viewRec ? {
              resourceType: 'form_instance',
              resourceId: viewRec.id,
              fieldLabels: buildFormFieldLabels(viewRec.fields),
              alsoResources: wfDetail?.id
                ? [{ resourceType: 'wf_process_instance', resourceId: wfDetail.id }]
                : undefined,
            } : undefined}
          />
        )}
      />
    </div>
  ) : null

  const schemeCreateMenu: MenuProps['items'] = legacySchemeList ? [
    { key: 'drawing-requisition', label: '合同图纸领用', onClick: () => nav('/drawing-requisitions/fill') },
    { key: 'install-notice', label: '安装图设计通知', onClick: () => nav('/install-drawing-notices/fill') },
    { key: 'presale-notice', label: '售前服务通知', onClick: () => nav('/presale-service-notices/fill') },
  ] : undefined

  return (
    <div>
      {legacySchemeList && (
        <Alert
          type="info"
          showIcon
          className="mb-4"
          message="方案管理已拆分为独立表单"
          description="本页仅保留历史合并单据查询。新建请从左侧「方案管理」子菜单选择：合同图纸领用、安装图设计通知或售前服务通知。"
        />
      )}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }} className="shrink-0">
        <Space>
          {!isModule && (
            <Button icon={<ArrowLeftOutlined />} onClick={() => nav('/lowcode/forms')}>返回</Button>
          )}
          <Title level={4} style={{ margin: 0 }}>{moduleTitle || name}{isModule ? '' : ' · 数据'}</Title>
        </Space>
        <Space>
          {dashboardPath && (
            <Button icon={<BarChartOutlined />} onClick={() => nav(dashboardPath)}>仪表盘</Button>
          )}
          <Dropdown menu={{ items: exportMenuItems }} trigger={['click']}>
            <Button icon={<DownloadOutlined />}>
              导出 <DownOutlined className="text-xs" />
            </Button>
          </Dropdown>
          {legacySchemeList ? (
            <Dropdown menu={{ items: schemeCreateMenu }} trigger={['click']}>
              <Button type="primary" icon={<PlusOutlined />}>
                新建 <DownOutlined />
              </Button>
            </Dropdown>
          ) : (
            <Button type="primary" icon={<PlusOutlined />} onClick={() => nav(fillPath)}>新增</Button>
          )}
        </Space>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-3 mb-4 shrink-0">
        <div className="flex gap-2 flex-wrap items-center">
          <Input
            allowClear
            prefix={<SearchOutlined className="text-slate-400" />}
            placeholder="搜索数据"
            value={keywordInput}
            style={{ width: 240 }}
            onChange={(e) => setKeywordInput(e.target.value)}
            onPressEnter={() => {
              const next = keywordInput.trim()
              setKeyword(next)
              setPageNo(1)
            }}
          />
          <Select
            allowClear
            placeholder="全部状态"
            style={{ width: 130 }}
            value={statusFilter}
            options={STATUS_FILTER_OPTIONS}
            onChange={(v) => { setStatusFilter(v); setPageNo(1) }}
          />
          <FormInstanceFilterPopover
            fields={filterFields}
            value={fieldFilters}
            onApply={applyFieldFilters}
            storageKey={filterMemoryKey}
          />
          <Button icon={<ReloadOutlined />} onClick={() => load()}>刷新</Button>
          {colMeta.length > 0 && (
            <ColumnConfigPanel
              allMeta={colMeta}
              colState={colState}
              onChange={setColState}
              onReset={resetColumns}
            />
          )}
        </div>
      </div>

      <FillHeightTable
          rowKey={expandDetails.length ? 'key' : 'id'}
          loading={loading}
          columns={tableColumns}
          onColumnWidthChange={onColumnWidthChange}
          dataSource={(flatRows || items) as (FormInstance | DetailFlatRow)[]}
          size="small"
          scroll={{ x: tableScrollX }}
          pagination={{
            current: pageNo,
            total,
            pageSize: tablePageSize,
            onChange: setPageNo,
            showSizeChanger: false,
            showTotal: (t) => `共 ${t} 条`,
          }}
        />

      <Modal
        className="spt-jdy-record-modal"
        closable={false}
        title={(
          <JdyRecordModalTitle
            variant="modal"
            title={viewRecordTitle}
            editing={Boolean(viewRec && !viewRec.readonly)}
            fullscreen={modalFullscreen}
            onToggleFullscreen={() => setModalFullscreen((v) => !v)}
            onOpenInSidebar={() => setViewPresentation('drawer')}
            onClose={closeView}
          />
        )}
        open={!!viewRec && viewPresentation === 'modal'}
        width={fsProps.width}
        style={fsProps.style}
        wrapClassName={fsProps.wrapClassName}
        styles={fsProps.styles}
        onCancel={closeView}
        footer={recordDetailFooter}
        destroyOnClose
      >
        {recordDetailInner}
      </Modal>
      <RecordDetailSideDrawer
        open={!!viewRec && viewPresentation === 'drawer'}
        title={viewRecordTitle}
        editing={Boolean(viewRec && !viewRec.readonly)}
        fullscreen={modalFullscreen}
        onToggleFullscreen={() => setModalFullscreen((v) => !v)}
        onClose={closeView}
        onOpenInModal={() => setViewPresentation('modal')}
        footer={recordDetailFooter}
      >
        {recordDetailInner}
      </RecordDetailSideDrawer>
      <WfActivateFlowModal
        open={activateOpen}
        instanceId={wfDetail?.id}
        nodes={wfDetail?.activate_nodes}
        onClose={() => setActivateOpen(false)}
        onDone={() => {
          if (viewRec?.id) {
            void loadWorkflow(viewRec.id, wfDetail?.id)
          }
          void load()
        }}
      />
      {wfDrawerNode}
    </div>
  )
}
