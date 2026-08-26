/**
 * 合同技术协议评审 HTJSXY — 系统打印（1:1 对齐简道云「合同技术协议评审」表格模板）。
 */
import dayjs from 'dayjs'
import client from '@/api/client'
import type { ApiResponse } from '@/api/types'
import type { TechAgreementReview } from '@/api/techAgreementReview'
import { workflowApi } from '@/api/lowcodeWorkflow'
import { getPersonLabelMap } from '@/components/lowcode/fields/PersonField'
import { openPdfPreview, setPdfPreviewLoading, closePdfPreview } from '@/components/PdfPreviewModal'
import { TECH_AGREEMENT_STATUS } from '@/constants/techAgreementReview'
import { plainPersonDisplayName } from '@/utils/personOptionLabel'
import { escHtml, printHtml } from '@/utils/printHtml'
import { htmlToPdfBlob, type HtmlToPdfMargins } from '@/utils/htmlToPdf'
import type { WfFlowStep } from '@/types/lowcode'

const DOC_TITLE = '合同技术协议评审'

const PRINT_MARGINS: HtmlToPdfMargins = {
  top: 8,
  right: 10,
  bottom: 8,
  left: 10,
}

const STATUS_PRINT: Record<string, string> = {
  ...Object.fromEntries(TECH_AGREEMENT_STATUS.map((s) => [s.value, s.label])),
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

function printPersonName(name: unknown, id?: string | null, labels?: Record<string, string>): string {
  const fromMap = id && labels?.[id] ? labels[id] : ''
  return plainPersonDisplayName(name || fromMap)
}

function collectPersonIds(row: TechAgreementReview): string[] {
  const ids = new Set<string>()
  for (const k of ['applicant_id', 'owner_id']) {
    const v = (row as unknown as Record<string, unknown>)[k]
    if (v) ids.add(String(v))
  }
  return [...ids]
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

/** 简道云打印：无意见时显示「无」 */
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

/** 审批意见：按完成时间倒序（与简道云打印一致，最新在上） */
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
    const line = parts.join('  ')
    const dash = idx < sorted.length - 1 ? '<div class="op-sep"></div>' : ''
    return `<div class="op">${escHtml(line)}</div>${dash}`
  }).join('')
}

function kvRow(l1: string, v1: unknown, l2: string, v2: unknown): string {
  return `<tr>
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

function attachRow(label: string, files: AttachRow[]): string {
  const inner = files.length
    ? files.map((f) => escHtml(f.original_name)).join(', ')
    : '&nbsp;'
  return `<tr class="span-row">
    <td class="lbl">${escHtml(label)}</td>
    <td class="val-left attach" colspan="3">${inner}</td>
  </tr>`
}

function metaHead(applicant: string, applyDate: string, serial: string): string {
  const item = (label: string, val: string) => (
    `<span class="meta-item"><span class="meta-lbl">${escHtml(label)}</span><span class="meta-val">${escHtml(val)}</span></span>`
  )
  return `<div class="meta-head">${[
    item('申请人', applicant),
    item('日期时间', applyDate),
    item('流水号', serial),
  ].join('')}</div>`
}

function printCss(): string {
  return `
    :root { --grid: #000; }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Microsoft YaHei","PingFang SC","SimHei","Heiti SC",sans-serif;
      color: #000;
      font-size: 10.5pt;
    }
    .sheet { width: 100%; }
    h1 {
      text-align: center;
      font-size: 18pt;
      font-weight: 700;
      margin: 0 0 8pt;
      letter-spacing: 0.5pt;
    }
    .meta-head {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      align-items: baseline;
      margin: 0 0 6pt;
      padding: 0;
      font-size: 10.5pt;
      line-height: 1.4;
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
    table.form td {
      border: 1px solid var(--grid);
      padding: 5pt 6pt;
      vertical-align: middle;
      word-break: break-word;
      line-height: 1.4;
    }
    table.form td.lbl {
      width: 18%;
      text-align: center;
      vertical-align: middle;
    }
    table.form td.val {
      width: 32%;
      text-align: center;
    }
    table.form td.val-left {
      text-align: left;
      vertical-align: top;
    }
    table.form tr.span-row td.lbl {
      vertical-align: middle;
    }
    table.form td.attach {
      color: #1677ff;
    }
    table.form tr.approval-row td.lbl.approval-side {
      width: 18%;
      text-align: center;
      vertical-align: middle;
    }
    table.form tr.approval-row td.approval-body {
      padding: 5pt 8pt 8pt;
      vertical-align: top;
    }
    .op {
      line-height: 1.55;
      word-break: break-word;
      white-space: pre-wrap;
      padding: 1pt 0;
    }
    .op-sep {
      border-top: 1px dashed #888;
      margin: 3pt 0;
      height: 0;
      line-height: 0;
      font-size: 0;
    }
    @page { size: A4 portrait; margin: 8mm 10mm; }
    @media print {
      table.form tr.approval-row { page-break-inside: avoid; }
    }
  `
}

function printFileNameFromHtml(html: string): string {
  const m = html.match(/<title[^>]*>([^<]*)<\/title>/i)
  return (m?.[1] || DOC_TITLE).trim()
}

export function buildTechAgreementReviewPrintHtml(opts: {
  row: TechAgreementReview
  flowSteps?: WfFlowStep[] | null
  drawingFiles?: AttachRow[]
  agreementFiles?: AttachRow[]
  personLabels?: Record<string, string>
}): string {
  const row = opts.row
  const labels = opts.personLabels || {}
  const statusLabel = STATUS_PRINT[row.status] || row.status || ''
  const applyDate = fmtDate(row.apply_at)
  const applicant = printPersonName(row.applicant_name, row.applicant_id, labels)
  const owner = printPersonName(row.owner_name, row.owner_id, labels)

  const body = `
    <h1>${DOC_TITLE}</h1>
    ${metaHead(applicant, applyDate, row.review_code || '')}
    <table class="form">
      ${kvRow('业务员', owner, '是否有重量要求', row.has_weight_req)}
      ${kvRow('业务部门', row.department_name, '是否趁用呆滞设备', row.use_idle_equip)}
      ${kvRow('公司名称', row.company_name, '合同是否含智能化部分', row.has_smart)}
      ${kvRow('所属行业', row.industry, '是否核价', row.need_pricing)}
      ${kvRow('参考合同号', row.ref_contract_no, '合同签订依据及情况', row.sign_basis)}
      ${kvRow('前期沟通人', row.pre_contact, '流程状态', statusLabel)}
      ${spanRow('项目名称及应用', row.project_title)}
      ${attachRow('认可图（附件）', opts.drawingFiles || [])}
      ${attachRow('技术协议（附件）', opts.agreementFiles || [])}
      ${spanRow('备注', row.remark)}
      <tr class="approval-row">
        <td class="lbl approval-side">审批意见</td>
        <td class="val-left approval-body" colspan="3">${approvalOpsHtml(opts.flowSteps)}</td>
      </tr>
    </table>
  `

  const title = `${DOC_TITLE}-${row.review_code || ''}`
  return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>${escHtml(title)}</title>
<style>${printCss()}</style></head><body><div class="sheet">${body}</div></body></html>`
}

export async function printTechAgreementReview(opts: {
  row: TechAgreementReview
  flowSteps?: WfFlowStep[] | null
  legacyBrowserPrint?: boolean
}): Promise<void> {
  const personIds = collectPersonIds(opts.row)
  const [personLabels, drawingFiles, agreementFiles, wfRes] = await Promise.all([
    personIds.length ? getPersonLabelMap(personIds) : Promise.resolve({}),
    fetchAttachments('tech_agreement_review_drawing', opts.row.id),
    fetchAttachments('tech_agreement_review', opts.row.id),
    opts.flowSteps !== undefined
      ? Promise.resolve(null)
      : workflowApi.byBiz({ biz_type: 'tech_agreement_review', biz_id: opts.row.id }).catch(() => null),
  ])
  const flowSteps = opts.flowSteps ?? wfRes?.data?.flow_steps ?? null
  const html = buildTechAgreementReviewPrintHtml({
    row: opts.row,
    flowSteps,
    drawingFiles,
    agreementFiles,
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

export function isTechAgreementReviewBiz(bizType?: string | null): boolean {
  return bizType === 'tech_agreement_review'
}
