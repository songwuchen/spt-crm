/**
 * 合同外购件提前安排流程 — 系统打印（对齐简道云 table 模板 + 参考样张 WMGF202608121）。
 */
import dayjs from 'dayjs'
import { workflowApi } from '@/api/lowcodeWorkflow'
import { getPersonLabelMap } from '@/components/lowcode/fields/PersonField'
import { getDeptNameMap } from '@/components/lowcode/fields/DeptField'
import { getContractLabelMap } from '@/components/lowcode/fields/ContractField'
import { openPdfPreview, setPdfPreviewLoading, closePdfPreview } from '@/components/PdfPreviewModal'
import { escHtml, printHtml } from '@/utils/printHtml'
import { htmlToPdfBlob, type HtmlToPdfMargins } from '@/utils/htmlToPdf'
import type { FieldDefinition, WfFlowStep } from '@/types/lowcode'

const DOC_TITLE = '合同外购件提前安排流程'
const TEMPLATE_CODE = 'contract_outsource_early'

const PRINT_MARGINS: HtmlToPdfMargins = {
  top: 8,
  right: 10,
  bottom: 8,
  left: 10,
}

const EQUIP_COLS: { key: string; label: string }[] = [
  { key: 'designer', label: '设计员' },
  { key: 'product_name', label: '产品名称' },
  { key: 'spec_model', label: '规格型号' },
  { key: 'material', label: '材质' },
  { key: 'qty', label: '数量' },
  { key: 'brand', label: '品牌' },
  { key: 'color', label: '颜色' },
  { key: 'motor_junction_dir', label: '电机接线盒方向' },
  { key: 'nameplate_req', label: '铭牌要求' },
  { key: 'remark_2', label: '备注' },
  { key: 'random_docs_req', label: '随机资料要求' },
]

type Labels = {
  users: Record<string, string>
  depts: Record<string, string>
  contracts: Record<string, string>
}

function cell(v: unknown): string {
  const s = v == null || v === '' ? '' : String(v).trim()
  return s ? escHtml(s) : '&nbsp;'
}

function fmtDateTime(v: unknown): string {
  if (v == null || v === '') return ''
  const d = dayjs(String(v))
  return d.isValid() ? d.format('YYYY-MM-DD HH:mm:ss') : String(v)
}

function fmtDate(v: unknown): string {
  if (v == null || v === '') return ''
  const d = dayjs(String(v))
  return d.isValid() ? d.format('YYYY-MM-DD') : String(v)
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

function personName(v: unknown, labels: Labels): string {
  return collectIds(v).map((id) => labels.users[id] || id).filter(Boolean).join('、')
}

function deptName(v: unknown, labels: Labels): string {
  return collectIds(v).map((id) => labels.depts[id] || id).filter(Boolean).join('、')
}

function contractLabel(v: unknown, labels: Labels): string {
  const id = collectIds(v)[0]
  if (!id) return ''
  return labels.contracts[id] || id
}

function detailRows(v: unknown): Record<string, unknown>[] {
  if (!Array.isArray(v)) return []
  return v.filter((r): r is Record<string, unknown> => !!r && typeof r === 'object')
}

function designersDisplay(form: Record<string, unknown>, labels: Labels): string {
  const parts = [
    personName(form.designer_multi, labels),
    personName(form.designer_single, labels),
    personName(form.design_assign, labels),
  ].filter(Boolean)
  return [...new Set(parts.join('、').split('、').filter(Boolean))].join('、')
}

function collectPersonIds(form: Record<string, unknown>): string[] {
  const ids = new Set<string>()
  for (const k of [
    'salesperson', 'transfer_dept_head', 'transfer_dept_heads',
    'designer_single', 'designer_multi', 'design_assign', 'purchaser_multi',
  ]) {
    collectIds(form[k]).forEach((id) => ids.add(id))
  }
  for (const row of detailRows(form.equipment_details)) {
    collectIds(row.designer).forEach((id) => ids.add(id))
  }
  return [...ids]
}

function collectDeptIds(form: Record<string, unknown>): string[] {
  const ids = new Set<string>()
  collectIds(form.department).forEach((id) => ids.add(id))
  collectIds(form.office).forEach((id) => ids.add(id))
  return [...ids]
}

function collectContractIds(form: Record<string, unknown>): string[] {
  return collectIds(form.contract_no)
}

function isPrintableStep(s: WfFlowStep): boolean {
  const name = (s.node_name || '').trim()
  if (s.node_type === 'end' || name === '结束') return false
  if (s.node_type === 'cc' || name === '抄送') return false
  if (s.is_current || s.status === 'running' || s.status === 'pending') return false
  return !!(
    s.action
    || (s.opinion && String(s.opinion).trim())
    || s.handler_name
    || s.status === 'completed'
    || s.status === 'approved'
    || s.node_type === 'start'
    || name === '流程发起'
    || name === '发起'
  )
}

function stepOpinion(s: WfFlowStep): string {
  const op = String(s.opinion ?? '').trim()
  if (op) return op
  const act = String(s.action ?? '').trim()
  const map: Record<string, string> = {
    approve: '同意',
    auto_approve: '同意',
    reject: '驳回',
    return: '退回',
    transfer: '转交',
    resubmit: '重新提交',
    submit: '提交',
  }
  if (act && map[act]) return map[act]
  if (s.status === 'rejected') return '驳回'
  if (s.status === 'completed' || s.status === 'approved') return '同意'
  const st = String(s.status_text || '').trim()
  if (st && st !== '已完成' && st !== '处理中') return st
  return ''
}

function approvalOpsHtml(steps?: WfFlowStep[] | null): string {
  const done = (steps || []).filter(isPrintableStep)
  if (!done.length) return '&nbsp;'
  const sorted = [...done].sort((a, b) => {
    const ta = a.completed_at || a.started_at || ''
    const tb = b.completed_at || b.started_at || ''
    return String(ta).localeCompare(String(tb))
  })
  return sorted.map((s) => {
    const when = s.completed_at ? dayjs(s.completed_at).format('YYYY-MM-DD HH:mm:ss') : ''
    const who = s.handler_name || (s.assignees || []).map((a) => a.name).filter(Boolean).join('、') || ''
    const opinion = stepOpinion(s)
    const node = String(s.node_name || '').trim()
    const tail = opinion && node && !`${opinion}${node}`.includes(node)
      ? `${opinion}${node}`
      : (opinion || node)
    return escHtml([who, when, tail].filter(Boolean).join('  '))
  }).join('  ')
}

function metaHead(opts: {
  submitter: string
  submitTime: string
  printTime: string
  serial: string
}): string {
  const item = (label: string, val: string) => (
    `<span class="meta-item"><span class="meta-lbl">${escHtml(label)}</span><span class="meta-val">${escHtml(val)}</span></span>`
  )
  return `<div class="meta-head">${[
    item('提交人', opts.submitter),
    item('提交时间', opts.submitTime),
    item('打印时间', opts.printTime),
    item('流水号', opts.serial),
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
      grid-template-columns: 1fr 1fr;
      gap: 2pt 8pt;
      margin: 0 0 4pt;
      font-size: 9.5pt;
      line-height: 1.35;
    }
    .meta-lbl { margin-right: 4pt; font-weight: 700; }
    table.form {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
      border: 1px solid var(--grid);
      margin-bottom: -1px;
    }
    table.form td, table.form th {
      border: 1px solid var(--grid);
      padding: 3pt 4pt;
      vertical-align: middle;
      word-break: break-word;
      line-height: 1.35;
      text-align: center;
      font-size: 9.5pt;
    }
    table.form td.lbl { width: 10%; font-weight: 700; background: #fafafa; }
    table.form td.val { width: 15%; }
    table.form td.val-left { text-align: left; vertical-align: top; }
    table.form td.approval-body { text-align: left; vertical-align: top; padding: 4pt 6pt; font-size: 9pt; line-height: 1.5; }
    table.equip th { font-weight: 700; background: #f5f5f5; font-size: 8.5pt; }
    table.equip td { font-size: 8.5pt; }
    @page { size: A4 portrait; margin: 8mm 10mm; }
  `
}

function printFileNameFromHtml(html: string): string {
  const m = html.match(/<title[^>]*>([^<]*)<\/title>/i)
  return (m?.[1] || DOC_TITLE).trim()
}

export function buildContractOutsourceEarlyPrintFileName(
  form: Record<string, unknown>,
  labels: Labels,
  printDate = dayjs(),
): string {
  const contract = contractLabel(form.contract_no, labels)
  const sales = personName(form.salesperson, labels)
  const dept = deptName(form.department, labels)
  const date = fmtDate(form.apply_datetime) || printDate.format('YYYY-MM-DD')
  const raw = [contract, sales, DOC_TITLE, date, dept].filter(Boolean).join('-')
  return raw.replace(/[\\/:*?"<>|]/g, '_').slice(0, 120)
}

function buildMainTable(form: Record<string, unknown>, labels: Labels): string {
  const purchasers = personName(form.purchaser_multi, labels)
  const designers = designersDisplay(form, labels)
  const businessDesc = String(form.business_desc ?? '').trim()
  const remark = String(form.remark ?? '').trim()
  return `<table class="form main-table">
    <tr>
      <td class="lbl">合同号</td><td class="val">${cell(contractLabel(form.contract_no, labels))}</td>
      <td class="lbl">业务员</td><td class="val">${cell(personName(form.salesperson, labels))}</td>
      <td class="lbl">部门</td><td class="val">${cell(deptName(form.department, labels))}</td>
      <td class="lbl">采购员（多选）</td><td class="val" colspan="3">${cell(purchasers)}</td>
    </tr>
    <tr>
      <td class="lbl">转交科室主任</td><td class="val">${cell(personName(form.transfer_dept_head, labels) || personName(form.transfer_dept_heads, labels))}</td>
      <td class="lbl">设计员</td><td class="val" colspan="7">${cell(designers)}</td>
    </tr>
    <tr>
      <td class="lbl">业务描述</td>
      <td class="val-left" colspan="9">${businessDesc ? escHtml(businessDesc).replace(/\n/g, '<br/>') : '&nbsp;'}</td>
    </tr>
    <tr>
      <td class="lbl">备注</td>
      <td class="val-left" colspan="9">${remark ? escHtml(remark).replace(/\n/g, '<br/>') : '&nbsp;'}</td>
    </tr>
  </table>`
}

function equipCell(row: Record<string, unknown>, key: string, labels: Labels): string {
  if (key === 'designer') return cell(personName(row.designer, labels))
  if (key === 'qty') {
    const n = row.qty
    if (n == null || n === '') return '&nbsp;'
    return cell(String(n))
  }
  return cell(row[key])
}

function buildEquipmentTable(form: Record<string, unknown>, labels: Labels, attachNames: string[]): string {
  const rows = detailRows(form.equipment_details)
  const head = EQUIP_COLS.map((c) => `<th>${escHtml(c.label)}</th>`).join('')
  const body = rows.length
    ? rows.map((row) => `<tr>${EQUIP_COLS.map((c) => `<td>${equipCell(row, c.key, labels)}</td>`).join('')}</tr>`).join('')
    : `<tr>${EQUIP_COLS.map(() => '<td>&nbsp;</td>').join('')}</tr>`
  const attach = attachNames.length ? escHtml(attachNames.join('、')) : '&nbsp;'
  return `<table class="form equip">
    <thead><tr>${head}</tr></thead>
    <tbody>${body}</tbody>
    <tr><td class="lbl">附件</td><td class="val-left" colspan="${EQUIP_COLS.length - 1}">${attach}</td></tr>
    <tr><td class="lbl">审批意见</td><td class="approval-body" colspan="${EQUIP_COLS.length - 1}">APPROVAL_PLACEHOLDER</td></tr>
  </table>`
}

function attachmentNamesFromForm(form: Record<string, unknown>): string[] {
  const raw = form.attachments
  if (!Array.isArray(raw)) return []
  return raw.map((item) => {
    if (!item || typeof item !== 'object') return ''
    const o = item as { name?: string; original_name?: string }
    return (o.name || o.original_name || '').trim()
  }).filter(Boolean)
}

export function buildContractOutsourceEarlyPrintHtml(opts: {
  formData: Record<string, unknown>
  flowSteps?: WfFlowStep[] | null
  labels: Labels
  initiatorName?: string | null
  startedAt?: string | null
  businessNo?: string | null
  attachmentNames?: string[]
  printDate?: dayjs.Dayjs
}): string {
  const form = opts.formData || {}
  const labels = opts.labels
  const printDate = opts.printDate || dayjs()
  const serial = String(form.serial_no || opts.businessNo || '').trim()
  const submitter = String(opts.initiatorName || personName(form.salesperson, labels) || '').trim()
  const submitTime = fmtDateTime(opts.startedAt || form.apply_datetime)
  const equipHtml = buildEquipmentTable(form, labels, opts.attachmentNames ?? attachmentNamesFromForm(form))
    .replace('APPROVAL_PLACEHOLDER', approvalOpsHtml(opts.flowSteps))
  const body = `
    <div class="print-head">
      <h1>${DOC_TITLE}</h1>
      ${metaHead({
        submitter,
        submitTime,
        printTime: printDate.format('YYYY-MM-DD HH:mm:ss'),
        serial,
      })}
    </div>
    ${buildMainTable(form, labels)}
    ${equipHtml}
  `
  const title = buildContractOutsourceEarlyPrintFileName(form, labels, printDate)
  return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>${escHtml(title)}</title>
<style>${printCss()}</style></head><body><div class="sheet">${body}</div></body></html>`
}

async function resolveLabels(form: Record<string, unknown>): Promise<Labels> {
  const personIds = collectPersonIds(form)
  const deptIds = collectDeptIds(form)
  const contractIds = collectContractIds(form)
  const [users, depts, contracts] = await Promise.all([
    personIds.length ? getPersonLabelMap(personIds) : Promise.resolve({}),
    deptIds.length ? getDeptNameMap(deptIds) : Promise.resolve({}),
    contractIds.length ? getContractLabelMap(contractIds) : Promise.resolve({}),
  ])
  return { users, depts, contracts }
}

export function isContractOutsourceEarlyForm(
  templateCode?: string | null,
  processName?: string | null,
): boolean {
  if (templateCode === TEMPLATE_CODE) return true
  const name = (processName || '').trim()
  return name.includes('合同外购件提前安排')
}

export async function printContractOutsourceEarlyInstance(opts: {
  formData: Record<string, unknown>
  fieldDefinitions?: FieldDefinition[]
  businessNo?: string | null
  formInstanceId?: string | null
  flowSteps?: WfFlowStep[] | null
  initiatorName?: string | null
  startedAt?: string | null
  legacyBrowserPrint?: boolean
}): Promise<void> {
  const form = opts.formData || {}
  let flowSteps = opts.flowSteps
  let initiatorName = opts.initiatorName
  let startedAt = opts.startedAt
  if (flowSteps === undefined && opts.formInstanceId) {
    try {
      const wf = opts.formInstanceId
        ? await workflowApi.byFormInstance({ form_instance_id: opts.formInstanceId })
        : null
      flowSteps = wf?.data?.flow_steps
      initiatorName = initiatorName ?? wf?.data?.initiator_name
      startedAt = startedAt ?? wf?.data?.started_at ?? wf?.data?.created_at
    } catch { /* optional */ }
  }
  const labels = await resolveLabels(form)
  const html = buildContractOutsourceEarlyPrintHtml({
    formData: form,
    flowSteps,
    labels,
    initiatorName,
    startedAt,
    businessNo: opts.businessNo,
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
