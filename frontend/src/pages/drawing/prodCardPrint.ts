/**
 * 生产卡/补充流程打印：HTML → PDF 预览（对齐客户 Word 模板）。
 * - 生产通知单：WMGF…生产通知单模板.docx（横向 A4）
 * - 生产补充卡：WMGF…补充…模板.docx（纵向 A4）
 * 接入方式对齐安装图 / 领用：htmlToPdfBlob + PdfPreviewModal。
 */
import dayjs from 'dayjs'
import { printHtml, escHtml } from '@/utils/printHtml'
import { htmlToPdfBlob, type HtmlToPdfMargins } from '@/utils/htmlToPdf'
import { openPdfPreview, setPdfPreviewLoading, closePdfPreview } from '@/components/PdfPreviewModal'
import { fetchProdCardContractFill } from '@/components/lowcode/fields/ContractField'
import { getPersonLabelMap } from '@/components/lowcode/fields/PersonField'
import { getDeptNameMap } from '@/components/lowcode/fields/DeptField'
import type { FieldDefinition, WfFlowStep } from '@/types/lowcode'

export type ProdCardPrintMode = 'notice' | 'supplement'

type Labels = {
  users: Record<string, string>
  depts: Record<string, string>
}

/** 生产通知单：横向 297×210，边距对齐 Word */
export const PROD_NOTICE_PRINT_MARGINS: HtmlToPdfMargins = {
  top: 5,
  right: 10,
  bottom: 10,
  left: 10,
}

/** 生产补充卡：纵向 210×297 */
export const PROD_SUPPLEMENT_PRINT_MARGINS: HtmlToPdfMargins = {
  top: 5.5,
  right: 9,
  bottom: 10,
  left: 10,
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

function fmtDate(v: unknown): string {
  if (v == null || v === '') return ''
  const d = dayjs(String(v))
  return d.isValid() ? d.format('YYYY-MM-DD') : String(v)
}

function flowInitiateDate(
  steps?: WfFlowStep[] | null,
  form?: Record<string, unknown>,
): string {
  for (const s of steps || []) {
    const name = (s.node_name || '').trim()
    if (s.node_type === 'start' || name === '流程发起' || name === '发起') {
      if (s.completed_at) return fmtDate(s.completed_at)
      if (s.started_at) return fmtDate(s.started_at)
    }
  }
  const times = (steps || [])
    .map((s) => s.started_at || s.completed_at)
    .filter(Boolean)
    .sort()
  if (times.length) return fmtDate(times[0])
  return fmtDate(form?.card_date || form?.apply_datetime)
}

function optionLabel(fields: FieldDefinition[], fieldId: string, value: unknown): string {
  if (value == null || value === '') return ''
  const fd = fields.find((f) => f.id === fieldId)
  const opts = fd?.options || []
  if (Array.isArray(value)) {
    return value.map((v) => {
      const o = opts.find((x) => x.value === v)
      return o?.label || String(v)
    }).join('、')
  }
  const o = opts.find((x) => x.value === value)
  return o?.label || String(value)
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

function cell(v: unknown): string {
  return escHtml(v == null || v === '' ? '' : String(v))
}

function detailRows(rows: unknown): Record<string, unknown>[] {
  if (!Array.isArray(rows) || !rows.length) return []
  return rows.filter((r): r is Record<string, unknown> => !!r && typeof r === 'object')
}

function attachmentLabel(form: Record<string, unknown>, ...keys: string[]): string {
  for (const k of keys) {
    const v = form[k]
    if (typeof v === 'string' && v.trim()) return v.trim()
    if (Array.isArray(v) && v.length) {
      const names = v.map((x) => {
        if (typeof x === 'string') return x
        if (x && typeof x === 'object') {
          const o = x as { name?: string; file_name?: string; filename?: string }
          return o.name || o.file_name || o.filename || ''
        }
        return ''
      }).filter(Boolean)
      if (names.length) return names.join('、')
    }
  }
  return ''
}

function yesNoStack(value: unknown): string {
  const s = String(value ?? '').trim()
  const yes = s === '是' || s === 'true' || s === '1'
  const no = s === '否' || s === 'false' || s === '0'
  return `<span class="chk-stack"><span>是${yes ? '☑' : '☐'}</span><span>否${no ? '☑' : '☐'}</span></span>`
}

function sanitizePrintFileName(name: string, fallback: string): string {
  const s = name.replace(/[\\/:*?"<>|]/g, '').replace(/\s+/g, '').trim()
  return s || fallback
}

function metaLine(items: [string, string][]): string {
  // 一行均分：每项占等宽 flex
  return `<div class="meta meta-even">${items.map(([k, v]) =>
    `<span class="meta-item"><b>${escHtml(k)}：</b>${escHtml(v || '')}</span>`,
  ).join('')}</div>`
}

function isSupplementForm(form: Record<string, unknown>): boolean {
  return String(form.is_supplement ?? '').trim() === '是'
}

/** 默认打印类型：补充→补充卡，否则通知单 */
export function defaultProdCardPrintMode(form: Record<string, unknown>): ProdCardPrintMode {
  return isSupplementForm(form) ? 'supplement' : 'notice'
}

/** 生产通知单「图纸编号」：否→drawing_no_query 带出 no_drawing_no（WMGF 图纸号） */
function noticeDrawingNo(form: Record<string, unknown>): string {
  const fromQuery = String(form.no_drawing_no ?? '').trim()
  if (fromQuery) return fromQuery
  return String(form.drawing_no ?? '').trim()
}

/**
 * 生产补充卡「图纸编号」：是→contract_no_select 带出 yes_contract_no（WMGF 合同号）。
 * 不得使用 no_drawing_no（设计卡 KS 号，与补充单选合同语义不一致）。
 */
export function supplementDrawingNo(form: Record<string, unknown>): string {
  const contract = String(form.yes_contract_no ?? '').trim()
  if (contract) return contract
  return String(form.drawing_no ?? '').trim()
}

/** 打印前补齐补充单合同号（库内只存 contract_no_select 引用，yes_contract_no 不落库） */
async function enrichSupplementFormForPrint(
  form: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  if (!isSupplementForm(form)) return form
  const contractIds = collectIds(form.contract_no_select)
  if (!contractIds.length) return form
  try {
    const pack = await fetchProdCardContractFill(contractIds[0], 'contract_no_select')
    const yes = String(pack.fill?.yes_contract_no ?? '').trim()
    if (yes) return { ...form, yes_contract_no: yes }
  } catch {
    /* 打印不因带出失败中断 */
  }
  return form
}

/** 生产补充卡 PDF 文件名前缀：对齐 Word「WMGF…补充…」，补充流程优先合同号。 */
export function supplementPrintPrefix(form: Record<string, unknown>, businessNo?: string | null): string {
  const prefix = supplementDrawingNo(form)
  if (prefix) return prefix
  return processNo(form, businessNo)
}

function salesPerson(form: Record<string, unknown>, labels: Labels): string {
  return personName(form.no_sales_person, labels)
    || personName(form.yes_sales_person, labels)
    || ''
}

function processNo(form: Record<string, unknown>, businessNo?: string | null): string {
  const sn = form.serial_no != null && String(form.serial_no).trim()
    ? String(form.serial_no).trim()
    : ''
  return sn || (businessNo ? String(businessNo) : '')
}

function stepPrintOpinion(s: WfFlowStep): string {
  const op = String(s.opinion ?? '').trim()
  if (op) return op
  const act = String(s.action ?? '').trim()
  const byAction: Record<string, string> = {
    approve: '同意',
    auto_approve: '同意',
    reject: '驳回',
    auto_reject: '驳回',
    return: '退回',
    transfer: '转交',
    resubmit: '重新提交',
  }
  if (act && byAction[act]) return byAction[act]
  if (s.status === 'rejected') return '驳回'
  if (s.status === 'completed' || s.status === 'approved') return '同意'
  const st = String(s.status_text || '').trim()
  if (st && st !== '已完成' && st !== '处理中') return st
  return ''
}

function isPrintableApprovalStep(s: WfFlowStep): boolean {
  const name = (s.node_name || '').trim()
  if (s.node_type === 'start' || name === '流程发起' || name === '发起') return false
  if (s.node_type === 'end' || name === '结束') return false
  if (s.node_type === 'cc') return false
  // 通知生产（抄送/系统）不进入打印意见区
  if (name.includes('通知生产')) return false
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

const PROD_CARD_APPROVAL_ORDER = [
  '财务核价',
  '法务审核',
  '部门审批',
  '业务员确认',
  '区域经理',
  '研管办',
  '安排设计',
  '设计指派',
] as const

function approvalNodePrintRank(nodeName: string): number {
  const n = (nodeName || '').trim()
  const idx = PROD_CARD_APPROVAL_ORDER.findIndex(
    (key) => n.includes(key) || key.includes(n),
  )
  return idx >= 0 ? idx : 100
}

function approvalLines(steps?: WfFlowStep[] | null): string[] {
  const list = (steps || []).filter(isPrintableApprovalStep)
  const sorted = [...list].sort((a, b) => {
    const ra = approvalNodePrintRank(a.node_name || '')
    const rb = approvalNodePrintRank(b.node_name || '')
    if (ra !== rb) return ra - rb
    const ta = a.completed_at || a.started_at || ''
    const tb = b.completed_at || b.started_at || ''
    return String(tb).localeCompare(String(ta))
  })
  return sorted.map((s) => {
    const when = s.completed_at ? dayjs(s.completed_at).format('YYYY-MM-DD  HH:mm') : ''
    const who = s.handler_name || (s.assignees || []).map((a) => a.name).filter(Boolean).join('、') || ''
    const opinion = stepPrintOpinion(s)
    return [s.node_name, who, when, opinion].filter(Boolean).join('   ')
  })
}

function printCss(variant: 'notice' | 'supplement'): string {
  const grid = '#666'
  return `
    * { box-sizing: border-box; }
    html, body { margin: 0; padding: 0; width: 100%; }
    body {
      font-family: "SimSun","Songti SC","STSong","Microsoft YaHei",serif;
      color: #000;
      font-size: ${variant === 'notice' ? '9.5pt' : '10.5pt'};
      line-height: 1.25;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }
    .sheet { width: 100%; padding: 0; --grid: ${grid}; }
    h1, .lbl, .meta b, .approval-label, table.equip td.eh, table.kv td.kl {
      font-family: "SimHei","Heiti SC","STHeiti","Microsoft YaHei","PingFang SC",sans-serif;
      font-weight: 700;
    }
    h1 {
      text-align: center;
      font-size: ${variant === 'notice' ? '16pt' : '18pt'};
      letter-spacing: 0.35em;
      margin: 0 0 4pt;
      line-height: 1.15;
    }
    .meta {
      display: flex;
      flex-wrap: nowrap;
      gap: 2pt 6pt;
      margin: 0 0 4pt;
      font-size: ${variant === 'notice' ? '9pt' : '10pt'};
      line-height: 1.35;
      width: 100%;
    }
    .meta.meta-even .meta-item {
      flex: 1 1 0;
      min-width: 0;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    table.form, table.equip, table.kv, table.sign-block {
      width: 100%;
      border-collapse: collapse;
      border-spacing: 0;
      table-layout: fixed;
      border: 1px solid var(--grid);
    }
    table.form td, table.equip td, table.kv td, table.sign-block td {
      border: 1px solid var(--grid);
      padding: 2pt 3pt;
      vertical-align: middle;
      word-break: break-word;
      overflow-wrap: anywhere;
    }
    .lbl, .eh, .kl {
      text-align: center;
      font-size: ${variant === 'notice' ? '8.5pt' : '9.5pt'};
      line-height: 1.2;
    }
    .lbl .sub {
      font-family: "SimSun","Songti SC","STSong",serif;
      font-weight: 400;
      font-size: 8pt;
      display: block;
      line-height: 1.1;
    }
    .val { text-align: center; }
    .val-left { text-align: left; }
    table.equip td.ec { text-align: center; }
    table.equip td.el { text-align: left; font-size: 9pt; }
    table.sign-block tr.sign-body td {
      height: 28pt;
      min-height: 28pt;
      vertical-align: top;
    }
    .idea { min-height: 22pt; vertical-align: top; text-align: left; }
    .idea-tall { min-height: 48pt; height: 48pt; vertical-align: top; text-align: left; }
    .chk-stack {
      display: inline-flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      line-height: 1.2;
      font-size: 9pt;
      gap: 1pt;
    }
    .approval-foot { margin-top: 6pt; }
    .approval-head {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12pt;
      margin-bottom: 2pt;
    }
    .approval-label {
      font-size: 10.5pt;
      margin: 0;
    }
    .ops { font-size: 9.5pt; line-height: 1.45; }
    .op { margin: 1pt 0; }
    .print-at {
      font-size: 9.5pt;
      text-align: right;
      white-space: nowrap;
      flex-shrink: 0;
    }
    table.kv td.kl { width: 22%; white-space: nowrap; }
    table.kv td.kvv { text-align: left; }
    table.kv tr.tall td { min-height: 28pt; height: 28pt; vertical-align: top; }
    table.kv td.kl-span {
      vertical-align: middle;
      font-family: "SimHei","Heiti SC","STHeiti","Microsoft YaHei","PingFang SC",sans-serif;
      font-weight: 700;
      text-align: center;
    }
  `
}

function wrapDoc(title: string, body: string, variant: 'notice' | 'supplement'): string {
  return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>${escHtml(title)}</title>
  <style>${printCss(variant)}</style></head><body><div class="sheet ${variant}">${body}</div></body></html>`
}

function buildEquipTable(form: Record<string, unknown>): string {
  const rows = detailRows(form.prod_card_line_items)
  const body = (rows.length ? rows : [{}]).map((r, idx) => `<tr>
    <td class="ec">${rows.length ? idx + 1 : ''}</td>
    <td class="el">${cell(r.product_name_3)}</td>
    <td class="el">${cell(r.spec_model_3)}</td>
    <td class="ec">${cell(r.qty_3)}</td>
    <td class="ec">${cell(r.unit_3)}</td>
    <td class="el">${cell(r.tech_params_line)}</td>
    <td class="el">${cell(r.electric_control)}</td>
    <td class="el">${cell(r.field_3)}</td>
  </tr>`).join('')
  return `<table class="equip">
    <colgroup>
      <col style="width:4%"><col style="width:16%"><col style="width:12%"><col style="width:5%">
      <col style="width:5%"><col style="width:30%"><col style="width:14%"><col style="width:14%">
    </colgroup>
    <tr>
      <td class="eh">序号</td>
      <td class="eh">设备名称</td>
      <td class="eh">规格型号</td>
      <td class="eh">数量</td>
      <td class="eh">单位</td>
      <td class="eh">技术参数及要求</td>
      <td class="eh">电控装置</td>
      <td class="eh">备注</td>
    </tr>
    ${body}
  </table>`
}

function buildNoticeHtml(ctx: {
  form: Record<string, unknown>
  fields: FieldDefinition[]
  labels: Labels
  businessNo?: string | null
  steps?: WfFlowStep[] | null
}): string {
  const { form, fields, labels, businessNo, steps } = ctx
  const draw = noticeDrawingNo(form)
  const sales = salesPerson(form, labels)
  const flowNo = processNo(form, businessNo)
  const submitter = personName(form.submitter, labels)
  const cardDate = flowInitiateDate(steps, form)
  const delivery = fmtDate(form.contract_delivery_date)
  const projectName = form.project_name != null ? String(form.project_name) : ''
  const unit = form.yes_customer_name != null ? String(form.yes_customer_name) : ''
  const reminder = form.special_reminder != null
    ? String(form.special_reminder)
    : (form.special_reminder_multi != null ? String(form.special_reminder_multi) : '')
  const installNo = form.install_project_no != null ? String(form.install_project_no) : ''
  const packaging = form.packaging_req != null ? String(form.packaging_req) : ''
  const paint = form.paint_req != null ? String(form.paint_req) : ''
  const isExport = optionLabel(fields, 'is_export_equipment', form.is_export_equipment)
    || (form.is_export_equipment != null ? String(form.is_export_equipment) : '')
  const hasIntel = optionLabel(fields, 'has_intelligence', form.has_intelligence)
    || (form.has_intelligence != null ? String(form.has_intelligence) : '')
  const smartPts = form.smart_points != null ? String(form.smart_points) : ''
  const techParams = form.tech_params != null ? String(form.tech_params) : ''
  const warranty = form.no_warranty_period != null ? String(form.no_warranty_period) : ''
  const remark = form.remark_prod_card != null ? String(form.remark_prod_card) : ''
  const needDispatch = optionLabel(fields, 'need_dispatch', form.need_dispatch)
  const hasTechReview = optionLabel(fields, 'has_contract_tech_review', form.has_contract_tech_review)
  const techReviewSn = form.contract_tech_review_sn != null ? String(form.contract_tech_review_sn) : ''
  const turnkey = optionLabel(fields, 'is_turnkey', form.is_turnkey)
  const ops = approvalLines(steps)
  const printAt = dayjs().format('YYYY-MM-DD  HH:mm:ss')

  const body = `
    <h1>生产通知单</h1>
    ${metaLine([
      ['图纸编号', draw],
      ['业务员', sales],
      ['流程编号', flowNo],
      ['提交人', submitter],
      ['下卡日期', cardDate],
      ['交货期', delivery],
    ])}
    <table class="form">
      <colgroup>${Array.from({ length: 12 }, () => '<col>').join('')}</colgroup>
      <tr>
        <td class="lbl" colspan="1">项目 / 名称</td>
        <td class="val-left" colspan="2">${cell(projectName || '无')}</td>
        <td class="lbl" colspan="1">单位名称</td>
        <td class="val-left" colspan="3">${cell(unit)}</td>
        <td class="lbl" colspan="1">特别提醒</td>
        <td class="val-left" colspan="2">${cell(reminder)}</td>
        <td class="lbl" colspan="1">安装图项目号</td>
        <td class="val" colspan="1">${cell(installNo)}</td>
      </tr>
      <tr>
        <td colspan="12" style="padding:0;border:none">${buildEquipTable(form)}</td>
      </tr>
      <tr>
        <td class="lbl" colspan="1">包装要求</td>
        <td class="lbl" colspan="1">油漆要求</td>
        <td class="lbl" colspan="1">设备是否出口</td>
        <td class="lbl" colspan="1">是否含智能化</td>
        <td class="lbl" colspan="1">智能点</td>
        <td class="lbl" colspan="4">技术参数及要求</td>
        <td class="lbl" colspan="1">质保期限</td>
        <td class="lbl" colspan="2">备注</td>
      </tr>
      <tr>
        <td class="val" colspan="1">${cell(packaging)}</td>
        <td class="val" colspan="1">${cell(paint)}</td>
        <td class="val" colspan="1">${cell(isExport)}</td>
        <td class="val" colspan="1">${cell(hasIntel)}</td>
        <td class="val" colspan="1">${cell(smartPts)}</td>
        <td class="val-left" colspan="4">${cell(techParams)}</td>
        <td class="val" colspan="1">${cell(warranty)}</td>
        <td class="val-left" colspan="2">${cell(remark)}</td>
      </tr>
      <tr>
        <td class="lbl" colspan="2">是否需要公司派人</td>
        <td class="val-left" colspan="2">${cell(needDispatch)}</td>
        <td class="lbl" colspan="2">是否有合同技术协议评审</td>
        <td class="val" colspan="1">${cell(hasTechReview)}</td>
        <td class="lbl" colspan="2">合同技术协议评审流水号</td>
        <td class="val" colspan="1">${cell(techReviewSn)}</td>
        <td class="lbl" colspan="1">是否为交钥匙工程</td>
        <td class="val" colspan="1">${cell(turnkey)}</td>
      </tr>
      <tr>
        <td colspan="12" style="padding:0">
          <table class="sign-block" style="border:none">
            <colgroup>
              <col style="width:9%"><col style="width:14%"><col style="width:8%"><col style="width:11%">
              <col style="width:10%"><col style="width:14%"><col style="width:10%"><col style="width:14%"><col style="width:10%">
            </colgroup>
            <tr class="sign-head">
              <td class="lbl">设计<span class="sub">（主设签）</span></td>
              <td class="lbl">审核<span class="sub">（室主任签）</span></td>
              <td class="lbl yn">是否有参数表</td>
              <td class="lbl yn">是否有三维<span class="sub">（无三维请说明原因）</span></td>
              <td class="lbl">标准化<span class="sub">（标准化室签）</span></td>
              <td class="lbl">审定<span class="sub">（总工助理签）</span></td>
              <td class="lbl">批准<span class="sub">（总工签）</span></td>
              <td class="lbl">图纸设计工作量</td>
              <td class="lbl">交图时间</td>
            </tr>
            <tr class="sign-body">
              <td class="val"></td>
              <td class="val"></td>
              <td class="val yn">${yesNoStack('')}</td>
              <td class="val yn">${yesNoStack('')}</td>
              <td class="val"></td>
              <td class="val"></td>
              <td class="val"></td>
              <td class="val"></td>
              <td class="val"></td>
            </tr>
          </table>
        </td>
      </tr>
      <tr>
        <td class="lbl idea" colspan="1">无三维原因</td>
        <td class="val-left idea" colspan="11"></td>
      </tr>
      <tr>
        <td class="lbl idea-tall" colspan="1">设计思路描述</td>
        <td class="val-left idea-tall" colspan="11"></td>
      </tr>
      <tr>
        <td class="lbl idea" colspan="1">交图路径</td>
        <td class="val-left idea" colspan="11"></td>
      </tr>
    </table>
    <div class="approval-foot">
      <div class="approval-head">
        <div class="approval-label">审批意见</div>
        <div class="print-at">打印时间：  ${escHtml(printAt)}</div>
      </div>
      <div class="ops">${ops.map((l) => `<div class="op">${escHtml(l)}</div>`).join('') || '<div class="op"></div>'}</div>
    </div>`

  const fileTitle = sanitizePrintFileName(
    `${draw || flowNo}生产通知单${cardDate || dayjs().format('YYYY-MM-DD')}`,
    '生产通知单',
  )
  return wrapDoc(fileTitle, body, 'notice')
}

function buildSupplementHtml(ctx: {
  form: Record<string, unknown>
  fields: FieldDefinition[]
  labels: Labels
  businessNo?: string | null
  steps?: WfFlowStep[] | null
}): string {
  const { form, fields, labels, businessNo, steps } = ctx
  const draw = supplementDrawingNo(form)
  const flowNo = processNo(form, businessNo)
  const sales = salesPerson(form, labels)
  const dept = deptName(form.department, labels)
  const unit = form.yes_customer_name != null ? String(form.yes_customer_name) : ''
  const desc = form.description != null ? String(form.description) : ''
  const paintSup = form.paint_req_supplement != null ? String(form.paint_req_supplement) : ''
  const needDispatch = optionLabel(fields, 'need_dispatch', form.need_dispatch)
  const isSup = optionLabel(fields, 'is_supplement', form.is_supplement) || '是'
  const installNo = form.install_project_no != null ? String(form.install_project_no) : ''
  const hasTech = optionLabel(fields, 'has_tech_agreement', form.has_tech_agreement)
  const attach = attachmentLabel(form, 'attachments')
  const images = attachmentLabel(form, 'images')
  const designers = personName(form.design_assignees, labels)
  const transferPkg = personName(form.transfer_packaging_users, labels)
  const cardDate = flowInitiateDate(steps, form)
  const submitter = personName(form.submitter, labels)
  const hasTechReview = optionLabel(fields, 'has_contract_tech_review', form.has_contract_tech_review)
  const techReviewSn = form.contract_tech_review_sn != null ? String(form.contract_tech_review_sn) : ''
  const ops = approvalLines(steps)
  const printAt = dayjs().format('YYYY-MM-DD  HH:mm:ss')

  const kv = (label: string, value: string, tall = false) =>
    `<tr class="${tall ? 'tall' : ''}"><td class="kl">${escHtml(label)}</td><td class="kvv" colspan="3">${cell(value)}</td></tr>`

  const opLines = ops.length ? ops : ['']
  const approvalRows = opLines.map((line, idx) => {
    const labelCell = idx === 0
      ? `<td class="kl kl-span" rowspan="${opLines.length}">审批意见：</td>`
      : ''
    return `<tr class="tall">${labelCell}<td class="kvv" colspan="3">${escHtml(line)}</td></tr>`
  }).join('')

  const body = `
    <h1>生产补充卡</h1>
    <table class="kv">
      <colgroup>
        <col style="width:22%"><col style="width:28%"><col style="width:22%"><col style="width:28%">
      </colgroup>
      <tr>
        <td class="kl">图纸编号：</td>
        <td class="kvv">${cell(draw)}</td>
        <td class="kl">流程编号：</td>
        <td class="kvv">${cell(flowNo)}</td>
      </tr>
      <tr>
        <td class="kl">业务人员：</td>
        <td class="kvv">${cell(sales)}</td>
        <td class="kl">所在部门：</td>
        <td class="kvv">${cell(dept)}</td>
      </tr>
      ${kv('单位名称：', unit)}
      ${kv('说明：', desc, true)}
      ${kv('油漆要求（补充）：', paintSup, true)}
      ${kv('是否需要公司派人：', needDispatch)}
      ${kv('是否为补充：', isSup)}
      ${kv('安装图项目号：', installNo)}
      ${kv('是否有技术协议：', hasTech)}
      ${kv('附件：', attach)}
      ${kv('图片：', images)}
      <tr>
        <td class="kl">设计指派：</td>
        <td class="kvv">${cell(designers)}</td>
        <td class="kl">转新乡、包装：</td>
        <td class="kvv">${cell(transferPkg)}</td>
      </tr>
      ${approvalRows}
      <tr>
        <td class="kl">下卡日期：</td>
        <td class="kvv">${cell(cardDate)}</td>
        <td class="kl">提交人：</td>
        <td class="kvv">${cell(submitter)}</td>
      </tr>
      <tr>
        <td class="kl">打印时间：</td>
        <td class="kvv" colspan="3">${escHtml(printAt)}</td>
      </tr>
      ${kv('是否有合同技术协议评审', hasTechReview)}
      ${kv('合同技术协议评审流水号', techReviewSn)}
    </table>`

  const fileTitle = sanitizePrintFileName(
    `${supplementPrintPrefix(form, businessNo)}补充${cardDate || dayjs().format('YYYY-MM-DD')}`,
    '生产补充卡',
  )
  return wrapDoc(fileTitle, body, 'supplement')
}

async function resolveLabels(form: Record<string, unknown>): Promise<Labels> {
  const personIds = [
    ...collectIds(form.submitter),
    ...collectIds(form.no_sales_person),
    ...collectIds(form.yes_sales_person),
    ...collectIds(form.design_assignees),
    ...collectIds(form.transfer_packaging_users),
    ...collectIds(form.region_manager),
  ]
  const [users, depts] = await Promise.all([
    personIds.length ? getPersonLabelMap(personIds) : Promise.resolve({} as Record<string, string>),
    getDeptNameMap(),
  ])
  return { users, depts }
}

export function isProdCardSupplementForm(
  fields?: FieldDefinition[] | null,
  formData?: Record<string, unknown> | null,
  processName?: string | null,
): boolean {
  if (processName && /生产卡/.test(processName)) return true
  const ids = new Set((fields || []).map((f) => f.id))
  if (ids.has('is_supplement') && (ids.has('prod_card_line_items') || ids.has('paint_req_supplement'))) {
    return true
  }
  if (formData && ('is_supplement' in formData) && ('prod_card_line_items' in formData || 'paint_req_supplement' in formData)) {
    return true
  }
  return false
}

/** 研管办安排 / 设计指派：通过时可顺带打印 */
export function isProdCardApproveAndPrintNode(nodeName?: string | null): boolean {
  const name = (nodeName || '').trim()
  return name.includes('安排设计')
    || name.includes('设计指派')
    || name === '研管办安排'
}

function printFileNameFromHtml(html: string): string {
  const m = html.match(/<title[^>]*>([^<]*)<\/title>/i)
  return (m?.[1] || '')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .trim()
}

export type ProdCardPrintInjectApproval = {
  node_name?: string | null
  handler_name?: string | null
  opinion?: string | null
  action?: string | null
}

function mergeInjectedApprovalStep(
  steps: WfFlowStep[] | null | undefined,
  inj?: ProdCardPrintInjectApproval | null,
): WfFlowStep[] {
  const list = [...(steps || [])]
  if (!inj) return list
  const opinion = String(inj.opinion ?? '').trim()
  if (!opinion) return list
  const nodeName = String(inj.node_name ?? '').trim()
  const handler = String(inj.handler_name ?? '').trim()
  const action = String(inj.action ?? 'approve').trim() || 'approve'
  const now = new Date().toISOString()
  const matchIdx = list.findIndex((s) => {
    const n = (s.node_name || '').trim()
    if (nodeName) return n === nodeName || n.includes(nodeName) || nodeName.includes(n)
    return !!(s.is_current || s.status === 'running' || s.status === 'pending')
  })
  if (matchIdx >= 0) {
    const prev = list[matchIdx]
    list[matchIdx] = {
      ...prev,
      is_current: false,
      status: 'completed',
      status_text: prev.status_text || '已完成',
      action: action || prev.action || 'approve',
      opinion,
      handler_name: handler || prev.handler_name || null,
      completed_at: prev.completed_at || now,
    }
    return list
  }
  list.push({
    node_instance_id: `print-inject-${Date.now()}`,
    node_name: nodeName || '安排设计',
    node_type: 'approve',
    status: 'completed',
    status_text: '已完成',
    action,
    opinion,
    handler_name: handler || null,
    completed_at: now,
  })
  return list
}

/** 生成生产卡打印 PDF 并打开预览 */
export async function printProdCardInstance(opts: {
  formData: Record<string, unknown>
  fieldDefinitions: FieldDefinition[]
  businessNo?: string | null
  flowSteps?: WfFlowStep[] | null
  /** notice=生产通知单；supplement=生产补充卡；默认按 is_supplement */
  mode?: ProdCardPrintMode | null
  injectApproval?: ProdCardPrintInjectApproval | null
  legacyBrowserPrint?: boolean
}): Promise<void> {
  const rawForm = opts.formData || {}
  const mode = opts.mode || defaultProdCardPrintMode(rawForm)
  const form = mode === 'supplement'
    ? await enrichSupplementFormForPrint(rawForm)
    : rawForm
  const fields = opts.fieldDefinitions || []
  const labels = await resolveLabels(form)
  const flowSteps = mergeInjectedApprovalStep(opts.flowSteps, opts.injectApproval)
  const ctx = {
    form,
    fields,
    labels,
    businessNo: opts.businessNo,
    steps: flowSteps,
  }
  const html = mode === 'supplement' ? buildSupplementHtml(ctx) : buildNoticeHtml(ctx)
  const fileName = printFileNameFromHtml(html) || (mode === 'supplement' ? '生产补充卡' : '生产通知单')
  const orientation = mode === 'supplement' ? 'portrait' : 'landscape'
  const margins = mode === 'supplement' ? PROD_SUPPLEMENT_PRINT_MARGINS : PROD_NOTICE_PRINT_MARGINS

  if (opts.legacyBrowserPrint) {
    printHtml(html, { orientation, fileName: fileName || undefined })
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
    printHtml(html, { orientation, fileName: fileName || undefined })
  }
}
