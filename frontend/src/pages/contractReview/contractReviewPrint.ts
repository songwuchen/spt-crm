/**
 * 合同评审 — 系统打印（对齐简道云「系统打印」：全字段表格 + 审批意见）。
 */
import dayjs from 'dayjs'
import client from '@/api/client'
import type { ApiResponse } from '@/api/types'
import type { ContractReview } from '@/api/contractReview'
import { workflowApi } from '@/api/lowcodeWorkflow'
import { getPersonLabelMap } from '@/components/lowcode/fields/PersonField'
import { openPdfPreview, setPdfPreviewLoading, closePdfPreview } from '@/components/PdfPreviewModal'
import {
  CONTRACT_REVIEW_SECTIONS,
  CONTRACT_REVIEW_STATUS,
  readReviewFieldValue,
  reviewDepVisible,
  reviewSectionAllFields,
  type ReviewFieldDef,
} from '@/constants/contractReview'
import { plainPersonDisplayName } from '@/utils/personOptionLabel'
import { escHtml, printHtml } from '@/utils/printHtml'
import { htmlToPdfBlob, type HtmlToPdfMargins } from '@/utils/htmlToPdf'
import type { WfFlowStep } from '@/types/lowcode'

const DOC_TITLE = '合同评审'

const PRINT_MARGINS: HtmlToPdfMargins = {
  top: 8,
  right: 10,
  bottom: 8,
  left: 10,
}

const STATUS_PRINT: Record<string, string> = {
  ...Object.fromEntries(CONTRACT_REVIEW_STATUS.map((s) => [s.value, s.label])),
  submitted: '流转中',
  approved: '流转完成',
}

type AttachRow = { original_name: string }

function cell(v: unknown): string {
  const s = v == null || v === '' ? '' : String(v).trim()
  return s ? escHtml(s) : '&nbsp;'
}

function fmtDate(v: unknown): string {
  if (!v) return ''
  const d = dayjs(String(v))
  return d.isValid() ? d.format('YYYY-MM-DD') : String(v)
}

function fmtMoney(v: unknown): string {
  if (v == null || v === '') return ''
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  return n.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}

function kvRow(l1: string, v1: unknown, l2: string, v2: unknown): string {
  return `<tr class="kv-row">
    <td class="lbl">${escHtml(l1)}</td><td class="val">${cell(v1)}</td>
    <td class="lbl">${escHtml(l2)}</td><td class="val">${cell(v2)}</td>
  </tr>`
}

function spanRow(label: string, value: unknown): string {
  const s = value == null || value === '' ? '' : String(value).trim()
  const inner = s ? escHtml(s).replace(/\n/g, '<br/>') : '&nbsp;'
  return `<tr class="span-row">
    <td class="lbl">${escHtml(label)}</td>
    <td class="val-left" colspan="3">${inner}</td>
  </tr>`
}

function sectionRow(title: string): string {
  return `<tr class="section-row"><td class="section-title" colspan="4">${escHtml(title)}</td></tr>`
}

function attachRow(label: string, files: AttachRow[]): string {
  const inner = files.length
    ? files.map((f) => escHtml(f.original_name)).join(', ')
    : '&nbsp;'
  return `<tr class="span-row">
    <td class="lbl">${escHtml(label)}</td>
    <td class="val-left attach" colspan="3">${inner}</td>
  </tr>`
}

function metaHead(submitter: string, applyDate: string, serial: string): string {
  const item = (label: string, val: string) => (
    `<span class="meta-item"><span class="meta-lbl">${escHtml(label)}</span><span class="meta-val">${escHtml(val)}</span></span>`
  )
  return `<div class="meta-head">${[
    item('提交人', submitter),
    item('日期时间', applyDate),
    item('流水号', serial),
  ].join('')}</div>`
}

function isPrintableStep(s: WfFlowStep): boolean {
  const name = (s.node_name || '').trim()
  if (s.node_type === 'start' || name === '流程发起' || name === '发起') return false
  if (s.node_type === 'end' || name === '结束') return false
  if (s.node_type === 'cc') return false
  if (s.is_current || s.status === 'running' || s.status === 'pending') return false
  return !!(
    s.action
    || (s.opinion && String(s.opinion).trim())
    || s.handler_name
    || s.status === 'completed'
    || s.status === 'rejected'
    || s.status === 'approved'
  )
}

function stepOpinion(s: WfFlowStep): string {
  const op = String(s.opinion ?? '').trim()
  if (op) return op
  const act = String(s.action ?? '').trim()
  const map: Record<string, string> = {
    approve: '同意', auto_approve: '同意', reject: '驳回', auto_reject: '驳回',
    return: '退回', transfer: '转交', resubmit: '重新提交',
  }
  if (act && map[act]) return map[act]
  if (s.status === 'rejected') return '驳回'
  if (s.status === 'completed' || s.status === 'approved') return '同意'
  const st = String(s.status_text || '').trim()
  if (st && st !== '已完成' && st !== '处理中') return st
  return '无'
}

function approvalOpsHtml(steps?: WfFlowStep[] | null): string {
  const done = (steps || []).filter(isPrintableStep)
  if (!done.length) return '&nbsp;'
  const sorted = [...done].sort((a, b) => {
    const ta = a.completed_at || a.started_at || ''
    const tb = b.completed_at || b.started_at || ''
    return String(tb).localeCompare(String(ta))
  })
  return sorted.map((s, idx) => {
    const when = s.completed_at ? dayjs(s.completed_at).format('YYYY-MM-DD HH:mm') : ''
    const who = s.handler_name || (s.assignees || []).map((a) => a.name).filter(Boolean).join('、') || ''
    const parts = [s.node_name, who, when, stepOpinion(s)].filter((x) => x != null && String(x).trim())
    const dash = idx < sorted.length - 1 ? '<div class="op-sep"></div>' : ''
    return `<div class="op">${escHtml(parts.join('  '))}</div>${dash}`
  }).join('')
}

function printCss(): string {
  return `
    :root { --grid: #000; }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Microsoft YaHei","PingFang SC","SimHei","Heiti SC",sans-serif;
      color: #000;
      font-size: 10pt;
    }
    .sheet { width: 100%; }
    .print-head { page-break-inside: avoid; break-inside: avoid; margin-bottom: 6pt; }
    h1 {
      text-align: center;
      font-size: 17pt;
      font-weight: 700;
      margin: 0 0 6pt;
      letter-spacing: 0.5pt;
    }
    .meta-head {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      align-items: baseline;
      margin: 0 0 4pt;
      font-size: 10pt;
      line-height: 1.35;
    }
    .meta-item { white-space: nowrap; }
    .meta-item:nth-child(1) { justify-self: start; }
    .meta-item:nth-child(2) { justify-self: center; }
    .meta-item:nth-child(3) { justify-self: end; }
    .meta-lbl { margin-right: 4pt; font-weight: 700; }
    .meta-val { font-weight: 400; }
    table.form {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
      border: 1px solid var(--grid);
    }
    table.section-table,
    table.tail-table,
    table.approval-table {
      margin-bottom: 0;
    }
    table.section-table + table.section-table,
    table.section-table + table.tail-table,
    table.tail-table + table.approval-table {
      margin-top: -1px;
    }
    table.form td {
      border: 1px solid var(--grid);
      padding: 4pt 5pt;
      vertical-align: middle;
      word-break: break-word;
      line-height: 1.35;
    }
    table.form td.lbl { width: 18%; text-align: center; }
    table.form td.val { width: 32%; text-align: center; }
    table.form td.val-left { text-align: left; vertical-align: top; }
    table.form td.attach { color: #1677ff; }
    table.form tr.section-row td.section-title {
      text-align: center;
      font-weight: 700;
      background: #f5f5f5;
      padding: 5pt;
    }
    table.form tr.approval-row td.lbl.approval-side {
      width: 18%;
      text-align: center;
      vertical-align: middle;
    }
    table.form tr.approval-row td.approval-body {
      padding: 4pt 7pt 6pt;
      vertical-align: top;
    }
    .ops { font-size: 9.5pt; line-height: 1.45; }
    .ops .op,
    .approval-body .op {
      line-height: 1.45;
      word-break: break-word;
      white-space: pre-wrap;
      padding: 1pt 0 2pt;
      break-inside: avoid;
      page-break-inside: avoid;
    }
    .op-sep { border-top: 1px dashed #888; margin: 3pt 0; height: 0; }
    @page { size: A4 portrait; margin: 8mm 10mm; }
    @media print {
      .print-head { page-break-after: avoid; break-after: avoid; }
      table.section-table { page-break-inside: auto; break-inside: auto; }
      table.form tr.kv-row,
      table.form tr.section-row,
      table.form tr.approval-row { page-break-inside: avoid; break-inside: avoid; }
      table.form tr.span-row td.val-left { page-break-inside: auto; break-inside: auto; }
    }
  `
}

function printFileNameFromHtml(html: string): string {
  const m = html.match(/<title[^>]*>([^<]*)<\/title>/i)
  return (m?.[1] || DOC_TITLE).trim()
}

function nativePersonName(row: Record<string, unknown>, fieldKey: string, labels: Record<string, string>): string {
  const nameKey = fieldKey.replace(/_id$/, '_name')
  const named = row[nameKey]
  if (named) return plainPersonDisplayName(named)
  const id = row[fieldKey]
  if (id && labels[String(id)]) return plainPersonDisplayName(labels[String(id)])
  return id ? String(id) : ''
}

function formatFieldValue(
  row: Record<string, unknown>,
  field: ReviewFieldDef,
  labels: Record<string, string>,
): string {
  const raw = readReviewFieldValue(row, field)
  if (raw == null || raw === '') return ''
  switch (field.widget) {
    case 'person':
      if (field.source === 'native') return nativePersonName(row, field.key, labels)
      if (typeof raw === 'string') return labels[raw] ? plainPersonDisplayName(labels[raw]) : raw
      return String(raw)
    case 'department':
      if (field.key === 'department_id') return String(row.department_name || raw)
      return String(raw)
    case 'person_multi': {
      const ids = Array.isArray(raw) ? raw : [raw]
      return ids.map((id) => labels[String(id)] || String(id)).filter(Boolean).join('、')
    }
    case 'date':
      return fmtDate(raw)
    case 'money':
      return fmtMoney(raw)
    case 'checkbox': {
      const arr = Array.isArray(raw) ? raw : [raw]
      return arr.map(String).join('、')
    }
    default:
      return String(raw)
  }
}

function isSpanField(field: ReviewFieldDef): boolean {
  return field.widget === 'textarea'
    || field.widget === 'person_multi'
    || field.key === 'project_title'
}

function visiblePrintFields(row: Record<string, unknown>): ReviewFieldDef[] {
  const out: ReviewFieldDef[] = []
  for (const sec of CONTRACT_REVIEW_SECTIONS) {
    for (const f of reviewSectionAllFields(sec)) {
      if (!reviewDepVisible(f.showWhen, row)) continue
      out.push(f)
    }
  }
  return out
}

function collectPersonIds(row: Record<string, unknown>): string[] {
  const ids = new Set<string>()
  for (const f of visiblePrintFields(row)) {
    const raw = readReviewFieldValue(row, f)
    if (f.widget === 'person' && raw) ids.add(String(raw))
    if (f.widget === 'person_multi' && Array.isArray(raw)) {
      raw.forEach((x) => { if (x) ids.add(String(x)) })
    }
    if (f.key === 'owner_id' && row.owner_id) ids.add(String(row.owner_id))
    if (f.key === 'region_manager_id' && row.region_manager_id) ids.add(String(row.region_manager_id))
  }
  return [...ids]
}

function contactsHtml(row: Record<string, unknown>): string {
  const rj = (row.review_json || {}) as Record<string, unknown>
  const contacts = Array.isArray(rj.contacts) ? rj.contacts as Record<string, unknown>[] : []
  if (!contacts.length) return ''
  const lines = contacts.map((c, i) => {
    const parts = [
      c.name, c.title, c.phone, c.email, c.remark,
    ].filter((x) => x != null && String(x).trim()).map(String)
    return `${i + 1}. ${parts.join(' / ')}`
  })
  return spanRow('联系人明细', lines.join('\n'))
}

function buildSectionTables(row: Record<string, unknown>, labels: Record<string, string>): string {
  const tables: string[] = []
  let pending: { label: string; value: string }[] = []

  const flushPairs = (rows: string[]) => {
    while (pending.length) {
      const a = pending.shift()!
      const b = pending.shift()
      rows.push(b ? kvRow(a.label, a.value, b.label, b.value) : kvRow(a.label, a.value, '', ''))
    }
  }

  for (const sec of CONTRACT_REVIEW_SECTIONS) {
    const fields = reviewSectionAllFields(sec).filter((f) => reviewDepVisible(f.showWhen, row))
    if (!fields.length) continue
    const rows: string[] = [sectionRow(sec.title)]
    for (const f of fields) {
      const value = formatFieldValue(row, f, labels)
      if (isSpanField(f)) {
        flushPairs(rows)
        rows.push(spanRow(f.label, value))
        continue
      }
      pending.push({ label: f.label, value })
      if (pending.length >= 2) flushPairs(rows)
    }
    flushPairs(rows)

    if (sec.afterSlot === 'contacts') {
      const c = contactsHtml(row)
      if (c) rows.push(c)
    }
    if (rows.length > 1) {
      tables.push(`<table class="form section-table">${rows.join('')}</table>`)
    }
  }
  return tables.join('\n')
}

function buildTailTable(statusLabel: string, opts: {
  costFiles?: AttachRow[]
  reviewFiles?: AttachRow[]
  reviewImages?: AttachRow[]
  feedbackFiles?: AttachRow[]
  feedbackImages?: AttachRow[]
}): string {
  return `<table class="form tail-table">
    ${attachRow('成本附件', opts.costFiles || [])}
    ${attachRow('附件', opts.reviewFiles || [])}
    ${attachRow('图片', opts.reviewImages || [])}
    ${attachRow('反馈附件', opts.feedbackFiles || [])}
    ${attachRow('反馈图片', opts.feedbackImages || [])}
    ${kvRow('流程状态', statusLabel, '', '')}
  </table>`
}

function buildApprovalTable(flowSteps?: WfFlowStep[] | null): string {
  const ops = approvalOpsHtml(flowSteps)
  return `<table class="form approval-table">
    <tr class="approval-row">
      <td class="lbl approval-side">审批意见</td>
      <td class="val-left approval-body" colspan="3"><div class="ops">${ops}</div></td>
    </tr>
  </table>`
}

async function fetchAttachments(bizType: string, bizId: string): Promise<AttachRow[]> {
  try {
    const res = await client.get<unknown, ApiResponse<Array<{ original_name: string }>>>(
      '/api/v1/attachments/by_biz',
      { params: { biz_type: bizType, biz_id: bizId }, headers: { 'X-Silent-Error': '1' } },
    )
    return res.data || []
  } catch {
    return []
  }
}

export function buildContractReviewPrintHtml(opts: {
  row: ContractReview
  flowSteps?: WfFlowStep[] | null
  costFiles?: AttachRow[]
  reviewFiles?: AttachRow[]
  reviewImages?: AttachRow[]
  feedbackFiles?: AttachRow[]
  feedbackImages?: AttachRow[]
  personLabels?: Record<string, string>
}): string {
  const row = opts.row as unknown as Record<string, unknown>
  const labels = opts.personLabels || {}
  const submitter = plainPersonDisplayName(row.created_by_name || row.owner_name || '')
  const applyDate = fmtDate(row.created_at)
  const statusLabel = STATUS_PRINT[String(row.status || '')] || String(row.status || '')

  const body = `
    <div class="print-head">
      <h1>${DOC_TITLE}</h1>
      ${metaHead(submitter, applyDate, String(row.review_code || ''))}
    </div>
    ${buildSectionTables(row, labels)}
    ${buildTailTable(statusLabel, opts)}
    ${buildApprovalTable(opts.flowSteps)}
  `

  const title = `${DOC_TITLE}-${String(row.review_code || '')}`
  return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>${escHtml(title)}</title>
<style>${printCss()}</style></head><body><div class="sheet">${body}</div></body></html>`
}

export async function printContractReview(opts: {
  row: ContractReview
  flowSteps?: WfFlowStep[] | null
  legacyBrowserPrint?: boolean
}): Promise<void> {
  const rowRec = opts.row as unknown as Record<string, unknown>
  const personIds = collectPersonIds(rowRec)
  const [
    personLabels,
    costFiles,
    reviewFiles,
    reviewImages,
    feedbackFiles,
    feedbackImages,
    wfRes,
  ] = await Promise.all([
    personIds.length ? getPersonLabelMap(personIds) : Promise.resolve({}),
    fetchAttachments('contract_review_cost', opts.row.id),
    fetchAttachments('contract_review', opts.row.id),
    fetchAttachments('contract_review_image', opts.row.id),
    fetchAttachments('contract_review_feedback', opts.row.id),
    fetchAttachments('contract_review_feedback_image', opts.row.id),
    opts.flowSteps !== undefined
      ? Promise.resolve(null)
      : workflowApi.byBiz({ biz_type: 'contract_review', biz_id: opts.row.id }).catch(() => null),
  ])
  const flowSteps = opts.flowSteps ?? wfRes?.data?.flow_steps ?? null
  const html = buildContractReviewPrintHtml({
    row: opts.row,
    flowSteps,
    costFiles,
    reviewFiles,
    reviewImages,
    feedbackFiles,
    feedbackImages,
    personLabels,
  })
  const fileName = printFileNameFromHtml(html) || DOC_TITLE
  if (opts.legacyBrowserPrint) {
    printHtml(html, { orientation: 'portrait', fileName })
    return
  }
  setPdfPreviewLoading(true, fileName)
  try {
    const { blob, fileName: pdfName } = await htmlToPdfBlob(html, {
      orientation: 'portrait',
      fileName,
      margins: PRINT_MARGINS,
    })
    openPdfPreview(blob, pdfName)
  } catch {
    closePdfPreview()
    printHtml(html, { orientation: 'portrait', fileName })
  }
}

export function isContractReviewBiz(bizType?: string | null): boolean {
  return bizType === 'contract_review'
}
