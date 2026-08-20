// 扩展平台 → 表单数据列表: 某模板的填报记录(看/改/删 + 去填报)。
// 支持通用「明细展开」：主表字段 rowSpan 合并 + 明细子列分组表头（对齐简道云列表）。
import { useEffect, useState, useCallback, useMemo } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import {
  Button, Space, Tag, Modal, message, Popconfirm, Typography,
  Input, Select,
} from 'antd'
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
  loadAppliedFilters,
  saveAppliedFilters,
} from '@/components/lowcode/formInstanceFilterUtils'
import {
  ArrowLeftOutlined, PlusOutlined, DownloadOutlined,
  PrinterOutlined, EditOutlined, DeleteOutlined, SendOutlined,
  SearchOutlined, ReloadOutlined, PaperClipOutlined, ThunderboltOutlined,
} from '@ant-design/icons'
import ModalFullscreenTitle, { modalFullscreenProps } from '@/components/ModalFullscreenTitle'
import { lowcodeApi } from '@/api/lowcode'
import { workflowApi } from '@/api/lowcodeWorkflow'
import { attachmentApi } from '@/api/attachment'
import { downloadFile } from '@/utils/download'
import {
  isMetaOnlyAttachmentId,
  normalizeFileFieldValue,
} from '@/utils/fileFieldValue'
import type { FieldDefinition, FormRule, FormInstance, WfInstanceDetail } from '@/types/lowcode'
import FormRenderer, { findRequiredError, scrollToLcField, deriveRolePerms } from '@/components/lowcode/FormRenderer'
import WfFlowDynamics from '@/components/lowcode/WfFlowDynamics'
import { buildFormFieldLabels } from '@/utils/dataLogLabels'
import WfActivateFlowModal from '@/components/lowcode/WfActivateFlowModal'
import { computeFieldStates } from '@/components/lowcode/RuleEngine'
import { fieldShowsTime } from '@/components/lowcode/dateField'
import { useAuthStore } from '@/stores/useAuthStore'
import {
  DRAWING_FORM_LAYOUT, applyDrawingFormLayout,
  resolveListExpandDetails, resolveListColumnIds,
  resolveListColumnWidths, resolveListColumnLabels, resolveListFullText,
} from '@/constants/drawingFormLayout'
import { getPersonLabelMap } from '@/components/lowcode/fields/PersonField'
import { getDeptNameMap } from '@/components/lowcode/fields/DeptField'
import { getProjectLabelMap } from '@/components/lowcode/fields/ProjectField'
import { getContractLabelMap } from '@/components/lowcode/fields/ContractField'
import { getCustomerLabelMap } from '@/components/lowcode/fields/CustomerField'
import { printSchemeInstance } from '@/pages/drawing/schemePrint'

const { Title, Text } = Typography

const STATUS_TAG: Record<string, { color: string; text: string }> = {
  draft: { color: 'default', text: '草稿' },
  submitted: { color: 'blue', text: '已提交' },
  running: { color: 'gold', text: '审批中' },
  completed: { color: 'green', text: '已通过' },
  rejected: { color: 'red', text: '已驳回' },
  withdrawn: { color: 'default', text: '已撤回' },
}

const STATUS_FILTER_OPTIONS = [
  { value: 'draft', label: '草稿' },
  { value: 'submitted', label: '已提交' },
  { value: 'running', label: '审批中' },
  { value: 'completed', label: '已通过' },
  { value: 'rejected', label: '已驳回' },
  { value: 'withdrawn', label: '已撤回' },
]

/** v3：客服申请完整列 + 多明细展开；旧 key 丢弃以免脏默认列 */
const COL_STORAGE_PREFIX = 'spt_formlist_cols_v3_'

function loadColState(storageKey: string): ColumnState {
  try {
    const s = localStorage.getItem(storageKey)
    return s ? JSON.parse(s) : { hidden: [], order: [], shown: [] }
  } catch {
    return { hidden: [], order: [], shown: [] }
  }
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

/** 列表「流水号」：只用 serial_no / 真正的流水号，绝不拿设计卡号顶替 */
function recordListNo(r: FormInstance, fields: FieldDefinition[]): string {
  const data = r.form_data || {}
  if (data.serial_no != null && data.serial_no !== '') return String(data.serial_no)
  const serialField = fields.find((f) => f.id === 'serial_no')
    || fields.find((f) => f.type === 'auto_number' && /流水号/.test(f.label || '') && !/设计卡/.test(f.label || ''))
  if (serialField) {
    const v = data[serialField.id]
    if (v != null && v !== '') return String(v)
  }
  // business_no 若与设计卡号/图纸编号相同，说明历史误把合同号写入业务编号
  if (r.business_no) {
    const card = data.design_card_no
    const drawing = data.drawing_no
    const biz = String(r.business_no)
    if (card != null && card !== '' && biz === String(card)) return '—'
    if (drawing != null && drawing !== '' && biz === String(drawing)) return '—'
    return r.business_no
  }
  return '—'
}

type NameMaps = {
  users: Record<string, string>
  depts: Record<string, string>
  projects: Record<string, string>
  contracts: Record<string, string>
  customers: Record<string, string>
}

function collectIds(v: unknown): string[] {
  if (v == null || v === '') return []
  if (Array.isArray(v)) {
    return v.flatMap((x) => {
      if (typeof x === 'object' && x && 'id' in x) return [String((x as { id: string }).id)]
      return x != null && x !== '' ? [String(x)] : []
    })
  }
  if (typeof v === 'object' && v && 'id' in v) return [String((v as { id: string }).id)]
  return [String(v)]
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
    const ids = collectIds(v)
    if (!ids.length) return '—'
    return ids.map((id) => maps?.projects[id] || id).join('，')
  }
  if (field.type === 'contract') {
    const ids = collectIds(v)
    if (!ids.length) return '—'
    return ids.map((id) => maps?.contracts[id] || id).join('，')
  }
  if (field.type === 'customer') {
    const ids = collectIds(v)
    if (!ids.length) return '—'
    return ids.map((id) => maps?.customers[id] || id).join('，')
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
    return joinLinks(collectIds(v).map((id) => maps?.customers[id] || id))
  }
  if (field.type === 'contract') {
    return joinLinks(collectIds(v).map((id) => maps?.contracts[id] || id))
  }
  if (field.type === 'project') {
    return joinLinks(collectIds(v).map((id) => maps?.projects[id] || id))
  }
  return cellText(field, v, maps)
}

type ViewRec = {
  fields: FieldDefinition[]
  value: Record<string, unknown>
  readonly: boolean
  id: string
  process_instance_id?: string | null
  rules: FormRule[]
  status?: string
}

export default function FormDataListPage({
  templateId: propId,
  moduleTitle,
  fillPath: fillPathProp,
  templateCode,
}: {
  /** 侧栏模块传入；缺省则从路由 /lowcode/forms/:id/data 取 */
  templateId?: string
  moduleTitle?: string
  /** 侧栏模块显式指定「新增」路径，避免落到 /lowcode/forms/... 导致菜单高亮错乱 */
  fillPath?: string
  /** 内置模块 code，用于图纸表单分区布局 */
  templateCode?: string
} = {}) {
  const { id: paramId = '' } = useParams()
  const id = propId || paramId
  const nav = useNavigate()
  const location = useLocation()
  const userRoles = useAuthStore((s) => s.user?.roles) || []
  const hasPermission = useAuthStore((s) => s.hasPermission)
  const canActivateFlow = hasPermission('workflow:activate') || hasPermission('workflow:manage')
  const [name, setName] = useState('')
  const [schemaFields, setSchemaFields] = useState<FieldDefinition[]>([])
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
  const [modalFullscreen, setModalFullscreen] = useState(false)
  const [serialPreviews, setSerialPreviews] = useState<Record<string, string>>({})
  const [wfDetail, setWfDetail] = useState<WfInstanceDetail | null>(null)
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
    setColState({ hidden: [], order: [], shown: [] })
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

  const buildQueryParams = useCallback(() => {
    const params: Record<string, unknown> = { template_id: id, pageNo, pageSize: 20 }
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

  const applyFieldFilters = (dsl: FormFilterDsl | null) => {
    setFieldFilters(dsl)
    saveAppliedFilters(filterMemoryKey, dsl)
    setPageNo(1)
  }

  const exportUrl = useMemo(() => {
    const q = new URLSearchParams({ template_id: id || '' })
    if (keyword) q.set('keyword', keyword)
    if (statusFilter) q.set('status', statusFilter)
    if (fieldFilters?.rules?.length) q.set('filters', JSON.stringify(fieldFilters))
    return `/api/v1/lc/form-instances/export?${q.toString()}`
  }, [id, keyword, statusFilter, fieldFilters])

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
          contractIds.push(...collectIds(row.form_data?.[f.id]))
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
  }, [items, colFields, detailColGroups])

  const loadWorkflow = async (recId: string, processInstanceId?: string | null) => {
    try {
      if (processInstanceId) {
        const res = await workflowApi.instance(processInstanceId)
        setWfDetail(res.data || null)
        return
      }
      const res = await workflowApi.byFormInstance({ form_instance_id: recId })
      setWfDetail(res.data || null)
    } catch {
      setWfDetail(null)
    }
  }

  const openView = async (recId: string, readonly: boolean) => {
    const res = await lowcodeApi.getInstance(recId)
    const detailRules = (res.data.rule_definitions as FormRule[] | undefined)
    setViewRec({
      fields: res.data.field_definitions,
      value: res.data.form_data,
      readonly,
      id: recId,
      process_instance_id: res.data.process_instance_id,
      rules: detailRules?.length ? detailRules : rules,
      status: res.data.status,
    })
    setWfDetail(null)
    await loadWorkflow(recId, res.data.process_instance_id)
  }

  const closeView = () => {
    setViewRec(null)
    setWfDetail(null)
    setSerialPreviews({})
    setModalFullscreen(false)
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
    const salesField = viewRec.fields.find((f) =>
      f.type === 'person' && (f.id === 'sales_person' || f.id === 'salesperson' || f.id === 'owner_id'
        || f.label === '业务员'),
    )
    const regionField = viewRec.fields.find((f) =>
      f.type === 'person' && (f.id === 'region_manager' || f.id === 'region_manager_id'
        || (f.label || '').includes('区域经理')),
    )
    if (!salesField || !regionField) return
    const raw = viewRec.value?.[salesField.id]
    const sid = raw == null || raw === ''
      ? ''
      : (typeof raw === 'object' && raw !== null && 'id' in (raw as object)
        ? String((raw as { id?: string }).id || '')
        : String(raw))
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
  }, [viewRec?.readonly, viewRec?.fields, viewRec?.value?.sales_person, viewRec?.value?.salesperson, viewRec?.value?.owner_id])

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
  /** 草稿/驳回可改；合同图纸领用、安装图设计通知流程通过后也可改内容（审批中仍锁） */
  const postCompleteEditable = templateCode === 'drawing_requisition'
    || templateCode === 'install_drawing_notice'
  const canEditRecord = (status?: string | null) =>
    status === 'draft' || status === 'rejected'
    || (postCompleteEditable && status === 'completed')
  const canResubmitRecord = (status?: string | null) =>
    status === 'draft' || status === 'rejected'
  /** 流程一旦发起（含审批中/已结束），不允许直接删除单据 */
  const canDeleteRecord = (rec: ViewRec | null) =>
    Boolean(rec) && !rec?.process_instance_id && !wfDetail?.id

  const handlePrint = async (recId: string) => {
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
      await printSchemeInstance({
        formData: res.data.form_data || {},
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

  // 列表操作列只保留「查看」；打印/编辑/删除放到详情工具栏（对齐简道云）
  const renderOps = (r: FormInstance) => (
    <Button size="small" type="link" onClick={() => openView(r.id, true)}>查看</Button>
  )

  const listColWidths = useMemo(() => resolveListColumnWidths(templateCode) || {}, [templateCode])
  const listFullText = useMemo(() => resolveListFullText(templateCode), [templateCode])

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
    width: listFullText ? 120 : 140,
    ellipsis: { showTitle: true } as const,
    fixed: 'left' as const,
    render: (_: unknown, row: FormInstance | DetailFlatRow) => {
      const rec = expandDetails.length ? (row as DetailFlatRow).record : (row as FormInstance)
      const no = recordListNo(rec, schemaFields)
      return (
        <a className="font-mono text-primary" title={no} onClick={() => openView(rec.id, true)}>
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
            cellNode(f, (row as DetailFlatRow).record.form_data?.[f.id], nameMaps),
        })),
        ...detailGroupCols,
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
          title: '操作', key: 'op', width: 72,
          onCell: (row) => ({ rowSpan: (row as DetailFlatRow).rowSpan }),
          render: (_: unknown, row) => renderOps((row as DetailFlatRow).record),
        },
      ]
    : [
        listNoCol,
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
            cellNode(f, (r as FormInstance).form_data?.[f.id], nameMaps),
        })),
        {
          title: '流程状态', dataIndex: 'status', key: 'status', width: 100, fixed: 'right' as const,
          render: (s: string) => {
            const t = STATUS_TAG[s] || { color: 'default', text: s }
            return <Tag color={t.color}>{t.text}</Tag>
          },
        },
        {
          title: '提交时间', dataIndex: 'created_at', key: 'created_at',
          width: listFullText ? 178 : 160,
          ellipsis: { showTitle: true } as const,
          fixed: listFullText ? undefined : ('right' as const),
          render: (v: string) => (v ? formatCellDateTime(v, true) : '—'),
        },
        ...(listFullText ? [{
          title: '更新时间',
          key: 'updated_at',
          width: 178,
          ellipsis: { showTitle: true } as const,
          render: (_: unknown, r: FormInstance | DetailFlatRow) => {
            const v = (r as FormInstance & { updated_at?: string }).updated_at
              || (r as FormInstance).created_at
            return v ? formatCellDateTime(v, true) : '—'
          },
        }] : []),
        {
          title: '操作', key: 'op', width: 72, fixed: 'right' as const,
          render: (_: unknown, r: FormInstance | DetailFlatRow) => renderOps(r as FormInstance),
        },
      ]

  const tableScrollX = useMemo(() => {
    const biz = colFields.reduce((n, f) => n + colWidth(f), 0)
    const detail = detailColsCount ? 120 * detailColsCount + 80 : 0
    const fixed = listFullText ? 120 + 100 + 178 + 178 + 72 : 140 + 90 + 160 + 72
    return Math.max(1200, biz + detail + fixed + 40)
  }, [colFields, detailColsCount, listFullText, listColWidths])

  const showFlowPane = !!viewRec
  const layoutMaxW = drawingLayout?.contentMaxWidth ?? 0
  const modalWidth = showFlowPane
    ? Math.max(1100, layoutMaxW + 300)
    : (layoutMaxW || (drawingLayout ? 960 : 780))
  const fsProps = modalFullscreenProps(modalFullscreen, modalWidth)
  const contentMaxH = modalFullscreen ? 'calc(100vh - 200px)' : '70vh'
  const displayFields = viewRec
    ? (drawingLayout ? applyDrawingFormLayout(templateCode, viewRec.fields) : viewRec.fields)
    : []

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }} className="shrink-0">
        <Space>
          {!isModule && (
            <Button icon={<ArrowLeftOutlined />} onClick={() => nav('/lowcode/forms')}>返回</Button>
          )}
          <Title level={4} style={{ margin: 0 }}>{moduleTitle || name}{isModule ? '' : ' · 数据'}</Title>
        </Space>
        <Space>
          <Button icon={<DownloadOutlined />} disabled={total === 0}
            onClick={() => {
              void downloadFile(exportUrl, `${name || '表单数据'}.xlsx`).catch((err: unknown) => {
                const msg = err instanceof Error ? err.message : '导出失败'
                message.error(msg)
              })
            }}>
            导出
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => nav(fillPath)}>新增</Button>
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
            fields={schemaFields}
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
          columns={columns}
          dataSource={(flatRows || items) as (FormInstance | DetailFlatRow)[]}
          size="small"
          scroll={{ x: tableScrollX }}
          pagination={{
            current: pageNo,
            total,
            pageSize: 20,
            onChange: setPageNo,
            showSizeChanger: false,
            showTotal: (t) => `共 ${t} 条`,
          }}
        />

      <Modal
        title={(
          <ModalFullscreenTitle
            title={viewRec?.readonly ? '查看记录' : '编辑记录'}
            fullscreen={modalFullscreen}
            onToggle={() => setModalFullscreen((v) => !v)}
          />
        )}
        open={!!viewRec}
        width={fsProps.width}
        style={fsProps.style}
        wrapClassName={fsProps.wrapClassName}
        styles={fsProps.styles}
        onCancel={closeView}
        footer={
          viewRec && !viewRec.readonly && canEditRecord(viewRec.status)
            ? [
                <Button key="c" onClick={closeView}>取消</Button>,
                <Button
                  key="s"
                  type={canResubmitRecord(viewRec.status) ? 'default' : 'primary'}
                  onClick={saveEdit}
                >
                  {canResubmitRecord(viewRec.status) ? '存草稿' : '保存'}
                </Button>,
                ...(canResubmitRecord(viewRec.status)
                  ? [
                      <Button key="sub" type="primary" onClick={submitDraft}>
                        提交审批
                      </Button>,
                    ]
                  : []),
              ]
            : [<Button key="c" onClick={closeView}>关闭</Button>]
        }
        destroyOnClose
      >
        {viewRec && (
          <div className={modalFullscreen ? 'flex flex-col flex-1 min-h-0' : undefined}>
            {/* 详情工具栏：打印 / 编辑 / 提交审批 / 删除（对齐简道云） */}
            <div
              className="flex items-center gap-1 mb-3 px-1 py-1 border-b border-slate-100 shrink-0"
              style={{ marginTop: -4 }}
            >
              {canPrintScheme && (
                <Button
                  type="text"
                  icon={<PrinterOutlined />}
                  onClick={() => handlePrint(viewRec.id)}
                >
                  打印
                </Button>
              )}
              {canEditRecord(viewRec.status) && viewRec.readonly && (
                <Button type="text" icon={<EditOutlined />} onClick={enterEdit}>
                  编辑
                </Button>
              )}
              {canResubmitRecord(viewRec.status) && (
                <Button type="text" icon={<SendOutlined />} onClick={submitDraft}>
                  提交审批
                </Button>
              )}
              {canActivateFlow && wfDetail?.can_activate && wfDetail.id && (
                <Button
                  type="text"
                  icon={<ThunderboltOutlined />}
                  onClick={() => setActivateOpen(true)}
                >
                  激活流程
                </Button>
              )}
              {canDeleteRecord(viewRec) && (
                <Popconfirm title="确认删除该记录?" onConfirm={() => del(viewRec.id)}>
                  <Button type="text" danger icon={<DeleteOutlined />}>
                    删除
                  </Button>
                </Popconfirm>
              )}
            </div>
            <div className="flex gap-0 flex-1 min-h-0" style={{ minHeight: modalFullscreen ? undefined : 480 }}>
              <div className="flex-1 overflow-y-auto pr-3" style={{ maxHeight: contentMaxH }}>
                <FormRenderer
                  fields={displayFields}
                  rules={viewRec.rules}
                  mode={viewRec.readonly ? 'readonly' : 'edit'}
                  value={viewRec.value}
                  onChange={(v) => setViewRec((s) => (s ? { ...s, value: v } : s))}
                  serialPreviews={serialPreviews}
                />
              </div>
              {showFlowPane && (
                <div
                  className="w-[300px] shrink-0 overflow-hidden rounded-md border border-slate-200"
                  style={{ maxHeight: contentMaxH, height: modalFullscreen ? contentMaxH : undefined }}
                >
                  <WfFlowDynamics
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
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>
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
    </div>
  )
}
