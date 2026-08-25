/**
 * 业务奖金流转单打印 — 对齐简道云模板：
 * - 业务奖金流转单（A4）纵向
 * - 业务奖金流转单(三等分）A4横向1
 * - 业务奖金流转单(三等分）纵向
 */
import dayjs from 'dayjs'
import { escHtml, printHtml } from '@/utils/printHtml'
import { htmlToPdfBlob, type HtmlToPdfMargins } from '@/utils/htmlToPdf'
import { openPdfPreview, setPdfPreviewLoading, closePdfPreview } from '@/components/PdfPreviewModal'
import { getPersonLabelMap } from '@/components/lowcode/fields/PersonField'
import { getDeptNameMap } from '@/components/lowcode/fields/DeptField'
import { getContractLabelMap } from '@/components/lowcode/fields/ContractField'
import { amountToChineseUpper } from '@/pages/quote/quotePrint'
import type { FieldDefinition, WfFlowStep } from '@/types/lowcode'

export type BizBonusPrintMode = 'a4' | 'triplicate_landscape' | 'triplicate_portrait'

const COMPANY = '河南威猛振动设备股份有限公司'
const DOC_TITLE = '业务奖金流转单'

export const BIZ_BONUS_A4_MARGINS: HtmlToPdfMargins = {
  top: 10,
  right: 12,
  bottom: 10,
  left: 12,
}

export const BIZ_BONUS_TRIP_LANDSCAPE_MARGINS: HtmlToPdfMargins = {
  top: 4,
  right: 6,
  bottom: 4,
  left: 6,
}

export const BIZ_BONUS_TRIP_PORTRAIT_MARGINS: HtmlToPdfMargins = {
  top: 5,
  right: 8,
  bottom: 5,
  left: 8,
}

type Labels = {
  users: Record<string, string>
  depts: Record<string, string>
  contracts: Record<string, string>
}

type ContractLine = Record<string, unknown>
type PaymentLine = Record<string, unknown>
type PayStatusLine = Record<string, unknown>

const BONUS_TEMPLATE_CODES = new Set(['biz_bonus_transfer', 'biz_bonus_biz_initiate'])

const APPROVAL_ORDER = [
  '部门审批',
  '财务审核',
  '总经理审批',
  '财务登记',
  '财务核对',
] as const

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

function fmtDate(v: unknown): string {
  if (v == null || v === '') return ''
  const d = dayjs(String(v))
  return d.isValid() ? d.format('YYYY-MM-DD') : String(v)
}

function fmtMoney(v: unknown): string {
  const n = Number(v)
  if (!Number.isFinite(n)) return ''
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function personName(v: unknown, labels: Labels): string {
  if (v == null || v === '') return ''
  if (typeof v === 'object' && v && ('name' in v || 'real_name' in v)) {
    const o = v as { name?: string; real_name?: string }
    return o.real_name || o.name || ''
  }
  return collectIds(v).map((id) => labels.users[id] || id).join('、')
}

function deptName(v: unknown, labels: Labels): string {
  if (v == null || v === '') return ''
  return collectIds(v).map((id) => labels.depts[id] || id).join('、')
}

function detailRows(v: unknown): Record<string, unknown>[] {
  if (!Array.isArray(v)) return []
  return v.filter((r): r is Record<string, unknown> => !!r && typeof r === 'object')
}

function contractCell(row: ContractLine, key: string, alt: string): unknown {
  return row[key] ?? row[alt]
}

function paymentCell(row: PaymentLine, keys: string[]): unknown {
  for (const k of keys) {
    if (row[k] != null && row[k] !== '') return row[k]
  }
  return ''
}

function bonusNo(form: Record<string, unknown>, businessNo?: string | null): string {
  return String(form.bonus_no || businessNo || '').trim()
}

function amountChinese(form: Record<string, unknown>): string {
  const cn = String(form.amount_cn || '').trim()
  if (cn) return cn
  const n = Number(form.current_bonus)
  if (Number.isFinite(n) && n > 0) return amountToChineseUpper(n)
  return ''
}

function stepPrintOpinion(s: WfFlowStep): string {
  const op = String(s.opinion ?? '').trim()
  if (op) return op
  const act = String(s.action ?? '').trim()
  const byAction: Record<string, string> = {
    approve: '同意',
    auto_approve: '同意',
    reject: '驳回',
    return: '退回',
  }
  return byAction[act] || ''
}

function approvalNodePrintRank(nodeName: string): number {
  const n = (nodeName || '').trim()
  const idx = APPROVAL_ORDER.findIndex((key) => n.includes(key) || key.includes(n))
  return idx >= 0 ? idx : 100
}

function isPrintableApprovalStep(s: WfFlowStep): boolean {
  const name = (s.node_name || '').trim()
  if (s.node_type === 'start' || name === '流程发起' || name === '发起') return false
  if (s.node_type === 'end' || name === '结束') return false
  if (s.node_type === 'cc' || name === '抄送') return false
  if (s.is_current || s.status === 'running' || s.status === 'pending') return false
  return !!(
    s.action
    || (s.opinion && String(s.opinion).trim())
    || s.handler_name
    || s.status === 'completed'
    || s.status === 'approved'
  )
}

function approvalLines(steps?: WfFlowStep[] | null, compact = false): string[] {
  const list = (steps || []).filter(isPrintableApprovalStep)
  const sorted = [...list].sort((a, b) => {
    const ra = approvalNodePrintRank(a.node_name || '')
    const rb = approvalNodePrintRank(b.node_name || '')
    if (ra !== rb) return ra - rb
    const ta = a.completed_at || a.started_at || ''
    const tb = b.completed_at || b.started_at || ''
    return String(ta).localeCompare(String(tb))
  })
  return sorted.map((s) => {
    const who = s.handler_name || (s.assignees || []).map((a) => a.name).filter(Boolean).join('、') || ''
    const opinion = stepPrintOpinion(s)
    if (compact) {
      return `${s.node_name}：${[who, opinion].filter(Boolean).join(' ')}`
    }
    const when = s.completed_at ? dayjs(s.completed_at).format('YYYY-MM-DD HH:mm') : ''
    return [s.node_name, who, when, opinion].filter(Boolean).join('　')
  })
}

function gmApprovalText(form: Record<string, unknown>, steps?: WfFlowStep[] | null): string {
  const field = String(form.field_13 || form.field_14 || '').trim()
  if (field) return field
  const gm = (steps || []).find((s) => (s.node_name || '').includes('总经理'))
  if (gm) {
    const op = stepPrintOpinion(gm)
    if (op) return op
  }
  return ''
}

async function resolveLabels(form: Record<string, unknown>): Promise<Labels> {
  const userIds = [
    ...collectIds(form.salesperson),
    ...collectIds(form.field),
  ]
  const deptIds = collectIds(form.department)
  const contractIds = collectIds(form.drawing_no)
  const [users, depts, contracts] = await Promise.all([
    getPersonLabelMap(userIds),
    getDeptNameMap(deptIds),
    contractIds.length ? getContractLabelMap(contractIds) : Promise.resolve({}),
  ])
  return { users, depts, contracts }
}

function contractDrawingNo(form: Record<string, unknown>, labels: Labels): string {
  const raw = form.drawing_no
  if (raw == null || raw === '') return ''
  const id = collectIds(raw)[0]
  if (id && labels.contracts[id]) return labels.contracts[id]
  return String(raw)
}

function printCss(mode: BizBonusPrintMode): string {
  const compact = mode !== 'a4'
  const base = compact ? '7.2pt' : '10pt'
  return `
    * { box-sizing: border-box; }
    html, body { margin: 0; padding: 0; width: 100%; }
    body {
      font-family: "SimSun","Songti SC","STSong","Microsoft YaHei",serif;
      color: #000;
      font-size: ${base};
      line-height: 1.35;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }
    .sheet { width: 100%; }
    .tri-landscape { display: flex; flex-direction: row; width: 100%; min-height: 100%; }
    .tri-landscape .copy {
      flex: 1 1 33.33%;
      max-width: 33.34%;
      padding: 0 3mm;
      border-right: 1px dashed #888;
    }
    .tri-landscape .copy:last-child { border-right: none; }
    .tri-portrait { display: flex; flex-direction: column; width: 100%; }
    .tri-portrait .copy {
      flex: 1 1 33.33%;
      padding: 2mm 0;
      border-bottom: 1px dashed #888;
    }
    .tri-portrait .copy:last-child { border-bottom: none; }
    .slip { width: 100%; }
    .head { text-align: center; margin-bottom: ${compact ? '2mm' : '4mm'}; }
    .head .co { font-size: ${compact ? '8pt' : '11pt'}; font-weight: 600; letter-spacing: 0.5px; }
    .head .title { font-size: ${compact ? '9pt' : '14pt'}; font-weight: 700; margin-top: 1mm; }
    .meta {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 1mm 2mm;
      margin-bottom: 2mm;
    }
    .meta-2 { grid-template-columns: repeat(2, 1fr); }
    .meta span b { font-weight: 600; }
    table.grid {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
      margin: 1.5mm 0;
    }
    table.grid th, table.grid td {
      border: 1px solid #333;
      padding: 1mm 1.2mm;
      vertical-align: top;
      word-break: break-all;
    }
    table.grid th { background: #f5f5f5; font-weight: 600; text-align: center; }
    .money-row {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 1mm;
      margin: 1.5mm 0;
    }
    .money-row span b { font-weight: 600; }
    .bonus-highlight {
      margin: 2mm 0;
      padding: 1.5mm 2mm;
      border: 1px solid #333;
      font-size: ${compact ? '7.5pt' : '10.5pt'};
    }
    .bonus-highlight b { font-weight: 700; }
    .approve { margin-top: 2mm; }
    .approve .line { margin: 0.8mm 0; min-height: 1.2em; }
    .sign-row {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 2mm;
      margin-top: 3mm;
      text-align: center;
    }
    .sign-row .box {
      border-top: 1px solid #333;
      padding-top: 1mm;
      min-height: 8mm;
    }
    .foot {
      margin-top: 2mm;
      font-size: ${compact ? '6.5pt' : '8pt'};
      color: #444;
      text-align: right;
    }
  `
}

function contractTableHtml(lines: ContractLine[], compact: boolean): string {
  const rows = lines.slice(0, compact ? 2 : 6)
  const more = lines.length - rows.length
  const body = rows.map((r) => `<tr>
    <td>${escHtml(contractCell(r, 'field', 'field_2'))}</td>
    <td>${escHtml(contractCell(r, 'field_2', 'field_3'))}</td>
    <td>${escHtml(contractCell(r, 'field_3', 'field_4'))}</td>
    <td>${escHtml(contractCell(r, 'field_4', 'field_5'))}</td>
    <td>${escHtml(fmtMoney(contractCell(r, 'field_5', 'field_6')))}</td>
    <td>${escHtml(fmtMoney(contractCell(r, 'field_6', 'field_7')))}</td>
  </tr>`).join('')
  const tail = more > 0
    ? `<tr><td colspan="6" style="text-align:center;color:#666">… 另有 ${more} 行</td></tr>`
    : ''
  if (!rows.length) return ''
  return `<table class="grid"><thead><tr>
    <th>产品名称</th><th>规格</th><th>单位</th><th>数量</th><th>合同单价</th><th>合同总价</th>
  </tr></thead><tbody>${body}${tail}</tbody></table>`
}

function paymentTableHtml(lines: PaymentLine[], compact: boolean): string {
  const rows = lines.slice(0, compact ? 2 : 5)
  const more = lines.length - rows.length
  const body = rows.map((r) => `<tr>
    <td>${escHtml(paymentCell(r, ['field_7', 'field_8']))}</td>
    <td>${escHtml(paymentCell(r, ['field_8', 'field_9']))}</td>
    <td>${escHtml(fmtDate(paymentCell(r, ['field_9', 'field_10'])))}</td>
    <td>${escHtml(fmtMoney(paymentCell(r, ['field_10', 'field_11'])))}</td>
  </tr>`).join('')
  const tail = more > 0
    ? `<tr><td colspan="4" style="text-align:center;color:#666">… 另有 ${more} 行</td></tr>`
    : ''
  if (!rows.length) return ''
  return `<table class="grid"><thead><tr>
    <th>收款编号</th><th>来款形式</th><th>来款日期</th><th>来款金额</th>
  </tr></thead><tbody>${body}${tail}</tbody></table>`
}

function payStatusHtml(lines: PayStatusLine[], compact: boolean): string {
  if (!lines.length) return ''
  const rows = lines.slice(0, compact ? 2 : 4)
  const body = rows.map((r) => `<tr>
    <td>${escHtml(fmtDate(r.field_14 ?? r.field_5))}</td>
    <td>${escHtml(fmtMoney(r.field_15 ?? r.field_6))}</td>
    <td>${escHtml(r.field_16 ?? r.field_7)}</td>
  </tr>`).join('')
  return `<table class="grid"><thead><tr>
    <th>支付时间</th><th>金额</th><th>形式</th>
  </tr></thead><tbody>${body}</tbody></table>`
}

function buildSlipHtml(ctx: {
  form: Record<string, unknown>
  labels: Labels
  businessNo?: string | null
  steps?: WfFlowStep[] | null
  compact: boolean
}): string {
  const { form, labels, compact } = ctx
  const no = bonusNo(form, ctx.businessNo)
  const gm = gmApprovalText(form, ctx.steps)
  const approvals = approvalLines(ctx.steps, compact)
  const contractLines = detailRows(form.contract_lines)
  const paymentLines = detailRows(form.payment_lines)
  const payStatus = detailRows(form.payment_status)

  const meta = (items: [string, string][]) => items.map(([k, v]) =>
    `<span><b>${escHtml(k)}：</b>${escHtml(v || '—')}</span>`,
  ).join('')

  return `<div class="slip">
    <div class="head">
      <div class="co">${escHtml(COMPANY)}</div>
      <div class="title">${escHtml(DOC_TITLE)}</div>
    </div>
    <div class="meta">${meta([
      ['奖金编号', no],
      ['奖金日期', fmtDate(form.bonus_date)],
      ['图纸编号', contractDrawingNo(form, labels)],
      ['业务员', personName(form.salesperson, labels)],
      ['部门', deptName(form.department, labels)],
      ['单位名称', String(form.company_name || '')],
      ['签订日期', fmtDate(form.sign_date)],
      ['合同金额', fmtMoney(form.contract_amount)],
      ['付款方式', String(form.payment_method || '')],
    ])}</div>
    ${contractTableHtml(contractLines, compact)}
    ${paymentTableHtml(paymentLines, compact)}
    <div class="money-row">${[
      ['来款合计', fmtMoney(form.payment_total)],
      ['结算状态', String(form.settle_pct || form.settle_status || '')],
      ['已提比例', String(form.field_11 || form.drawn_ratio || '')],
      ['已提奖金', fmtMoney(form.drawn_bonus)],
    ].map(([k, v]) => `<span><b>${escHtml(k)}</b> ${escHtml(v || '—')}</span>`).join('')}</div>
    <div class="money-row">${[
      ['运费', fmtMoney(form.freight)],
      ['服务费', fmtMoney(form.service_fee)],
      ['招待费', fmtMoney(form.entertainment_fee)],
      ['返还款', fmtMoney(form.rebate)],
    ].map(([k, v]) => `<span><b>${escHtml(k)}</b> ${escHtml(v || '—')}</span>`).join('')}</div>
    <div class="bonus-highlight">
      <b>本次奖金金额：</b>${escHtml(fmtMoney(form.current_bonus))}
      &nbsp;&nbsp;<b>大写：</b>${escHtml(amountChinese(form))}
    </div>
    ${gm ? `<div class="approve"><div class="line"><b>总经理审批：</b>${escHtml(gm)}</div></div>` : ''}
    ${approvals.length ? `<div class="approve">${approvals.map((l) =>
      `<div class="line">${escHtml(l)}</div>`,
    ).join('')}</div>` : ''}
    ${payStatus.length ? `<div style="margin-top:2mm"><b>支付状态</b>${payStatusHtml(payStatus, compact)}</div>` : ''}
    ${String(form.remark || '').trim()
      ? `<div class="approve"><div class="line"><b>备注：</b>${escHtml(String(form.remark))}</div></div>`
      : ''}
    <div class="sign-row">
      <div class="box">部门审批</div>
      <div class="box">财务审核</div>
      <div class="box">总经理</div>
    </div>
    <div class="foot">打印时间 ${escHtml(dayjs().format('YYYY-MM-DD HH:mm'))}</div>
  </div>`
}

export function buildBizBonusPrintHtml(opts: {
  formData: Record<string, unknown>
  fieldDefinitions?: FieldDefinition[]
  businessNo?: string | null
  flowSteps?: WfFlowStep[] | null
  mode?: BizBonusPrintMode
  labels?: Labels
}): string {
  const mode = opts.mode || defaultBizBonusPrintMode()
  const form = opts.formData || {}
  const labels = opts.labels || { users: {}, depts: {}, contracts: {} }
  const compact = mode !== 'a4'
  const slip = buildSlipHtml({
    form,
    labels,
    businessNo: opts.businessNo,
    steps: opts.flowSteps,
    compact,
  })

  let body = ''
  if (mode === 'a4') {
    body = `<div class="sheet">${slip}</div>`
  } else if (mode === 'triplicate_landscape') {
    body = `<div class="sheet tri-landscape">${[1, 2, 3].map(() =>
      `<div class="copy">${slip}</div>`,
    ).join('')}</div>`
  } else {
    body = `<div class="sheet tri-portrait">${[1, 2, 3].map(() =>
      `<div class="copy">${slip}</div>`,
    ).join('')}</div>`
  }

  const orient = mode === 'triplicate_landscape' ? 'landscape' : 'portrait'
  const no = bonusNo(form, opts.businessNo)
  const docTitle = `${DOC_TITLE}${no ? `-${no}` : ''}`

  return `<!DOCTYPE html><html><head><meta charset="utf-8"/>
<title>${escHtml(docTitle)}</title>
<style>@page { size: A4 ${orient}; margin: 0; }${printCss(mode)}</style>
</head><body>${body}</body></html>`
}

function printFileNameFromHtml(html: string): string {
  const m = html.match(/<title[^>]*>([^<]*)<\/title>/i)
  return (m?.[1] || DOC_TITLE).trim()
}

export function defaultBizBonusPrintMode(): BizBonusPrintMode {
  return 'triplicate_landscape'
}

export function isBizBonusForm(
  templateCode?: string | null,
  formCode?: string | null,
  processName?: string | null,
): boolean {
  const code = String(templateCode || formCode || '').trim()
  if (BONUS_TEMPLATE_CODES.has(code)) return true
  const name = String(processName || '')
  return name.includes('业务奖金流转')
}

export function canPrintBizBonusDocument(
  fields?: FieldDefinition[] | null,
  formData?: Record<string, unknown> | null,
  templateCode?: string | null,
  processName?: string | null,
): boolean {
  if (isBizBonusForm(templateCode, undefined, processName)) return true
  const ids = new Set((fields || []).map((f) => f.id))
  return ids.has('bonus_no') && ids.has('current_bonus') && ids.has('payment_lines')
}

export function isBizBonusApproveAndPrintNode(nodeName?: string | null): boolean {
  const n = (nodeName || '').trim()
  return APPROVAL_ORDER.some((key) => n.includes(key) || key.includes(n))
}

export async function printBizBonusInstance(opts: {
  formData: Record<string, unknown>
  fieldDefinitions?: FieldDefinition[]
  businessNo?: string | null
  flowSteps?: WfFlowStep[] | null
  mode?: BizBonusPrintMode | null
  legacyBrowserPrint?: boolean
}): Promise<void> {
  const labels = await resolveLabels(opts.formData || {})
  const mode = opts.mode || defaultBizBonusPrintMode()
  const html = buildBizBonusPrintHtml({
    formData: opts.formData,
    fieldDefinitions: opts.fieldDefinitions,
    businessNo: opts.businessNo,
    flowSteps: opts.flowSteps,
    mode,
    labels,
  })
  const fileName = printFileNameFromHtml(html) || DOC_TITLE
  const orientation = mode === 'triplicate_landscape' ? 'landscape' : 'portrait'
  const margins = mode === 'a4'
    ? BIZ_BONUS_A4_MARGINS
    : mode === 'triplicate_portrait'
      ? BIZ_BONUS_TRIP_PORTRAIT_MARGINS
      : BIZ_BONUS_TRIP_LANDSCAPE_MARGINS

  if (opts.legacyBrowserPrint) {
    printHtml(html, { orientation, fileName })
    return
  }
  setPdfPreviewLoading(true, fileName)
  try {
    const { blob, fileName: pdfName } = await htmlToPdfBlob(html, {
      orientation,
      fileName,
      margins,
    })
    openPdfPreview(blob, pdfName)
  } catch {
    closePdfPreview()
    printHtml(html, { orientation, fileName })
  }
}

export const BIZ_BONUS_PRINT_MODE_LABELS: Record<BizBonusPrintMode, string> = {
  a4: '业务奖金流转单（A4）',
  triplicate_landscape: '三等分 A4 横向',
  triplicate_portrait: '三等分纵向',
}
