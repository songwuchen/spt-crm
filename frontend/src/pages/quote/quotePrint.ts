/**
 * 报价管理：正式报价单打印（对齐河南威猛 Word 模板）。
 * 纵向 A4 → PDF 预览 / 浏览器打印。
 */
import dayjs from 'dayjs'
import { escHtml, printHtml } from '@/utils/printHtml'
import { htmlToPdfBlob, type HtmlToPdfMargins } from '@/utils/htmlToPdf'
import { openPdfPreview, setPdfPreviewLoading, closePdfPreview } from '@/components/PdfPreviewModal'
import { getPersonLabelMap } from '@/components/lowcode/fields/PersonField'
import { getCustomerLabelMap } from '@/components/lowcode/fields/CustomerField'
import type { FieldDefinition } from '@/types/lowcode'

const COMPANY = '河南威猛振动设备股份有限公司'
const DEFAULT_PAYMENT = '预付 30%，提货 60%，质保 10%一年付清。'
const VALIDITY_DAYS = 30
const LEAD_TIME_DAYS = 90

/** 纵向 A4 页边距（mm） */
export const QUOTE_PRINT_MARGINS: HtmlToPdfMargins = {
  top: 12,
  right: 15,
  bottom: 12,
  left: 15,
}

type PriceLine = {
  product_name?: string
  spec_model?: string
  unit?: string
  qty?: number | string
  unit_price?: number | string
  line_total?: number | string
  total_price?: number | string
  remark?: string
  remarks?: string
}

type QuoteLabels = {
  users: Record<string, string>
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

function personName(v: unknown, labels: QuoteLabels): string {
  if (v == null || v === '') return ''
  if (typeof v === 'object' && v && ('name' in v || 'real_name' in v)) {
    const o = v as { name?: string; real_name?: string }
    return o.real_name || o.name || ''
  }
  return collectIds(v).map((id) => plainPersonDisplayName(labels.users[id] || id)).join('、')
}

/** 打印用语：去掉客户编码括号，仅保留名称 */
export function plainCustomerDisplayName(label: string): string {
  let s = String(label || '').trim()
  s = s.replace(/\s*[（(][^）)]*[）)]\s*$/, '').trim()
  return s
}

function plainPersonDisplayName(label: string): string {
  const s = String(label || '').trim()
  const dot = s.indexOf(' · ')
  return dot >= 0 ? s.slice(0, dot).trim() : s
}

function customerName(v: unknown, labels: QuoteLabels): string {
  if (v == null || v === '') return ''
  if (typeof v === 'object' && v && 'name' in v) {
    return plainCustomerDisplayName(String((v as { name?: string }).name || ''))
  }
  const ids = collectIds(v)
  const fromLabels = ids
    .map((id) => labels.customers[id])
    .filter((x): x is string => Boolean(x))
  if (fromLabels.length) {
    return fromLabels.map(plainCustomerDisplayName).join('、')
  }
  const s = String(v).trim()
  if (s && !/^[0-9a-f-]{36}$/i.test(s)) return plainCustomerDisplayName(s)
  return ids.map((id) => plainCustomerDisplayName(id)).join('、')
}

function parseNum(v: unknown): number | null {
  if (v == null || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

function fmtMoney(v: number | null): string {
  if (v == null) return ''
  return v.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function equipmentLabel(line: PriceLine): string {
  const parts = [line.product_name, line.spec_model].map((s) => String(s || '').trim()).filter(Boolean)
  return parts.join(' ') || ''
}

function lineRemark(line: PriceLine): string {
  return String(line.remark || line.remarks || '').trim()
}

function lineUnitPrice(line: PriceLine): number | null {
  return parseNum(line.unit_price)
}

function lineTotal(line: PriceLine): number | null {
  const direct = parseNum(line.line_total ?? line.total_price)
  if (direct != null) return direct
  const qty = parseNum(line.qty)
  const up = lineUnitPrice(line)
  if (qty != null && up != null) return qty * up
  return null
}

/** 金额大写（人民币，含「整」） */
export function amountToChineseUpper(amount: number): string {
  if (!Number.isFinite(amount) || amount < 0) return ''
  if (amount === 0) return '零元整'
  const CN_NUM = ['零', '壹', '贰', '叁', '肆', '伍', '陆', '柒', '捌', '玖']
  const CN_UNIT = ['', '拾', '佰', '仟']
  const CN_BIG = ['', '万', '亿']

  const convertSection = (n: number): string => {
    if (n === 0) return ''
    let s = ''
    let zero = false
    for (let i = 0; i < 4; i += 1) {
      const d = Math.floor(n / (10 ** (3 - i))) % 10
      if (d === 0) {
        zero = s.length > 0
      } else {
        if (zero) s += CN_NUM[0]
        s += CN_NUM[d] + CN_UNIT[3 - i]
        zero = false
      }
    }
    return s
  }

  const fixed = Math.round(amount * 100)
  const intPart = Math.floor(fixed / 100)
  const dec = fixed % 100
  const jiao = Math.floor(dec / 10)
  const fen = dec % 10

  let result = ''
  let rest = intPart
  let bigIdx = 0
  while (rest > 0) {
    const section = rest % 10000
    if (section > 0) {
      const sec = convertSection(section)
      result = sec + CN_BIG[bigIdx] + result
    }
    rest = Math.floor(rest / 10000)
    bigIdx += 1
  }
  result = (result || CN_NUM[0]) + '元'
  if (jiao === 0 && fen === 0) {
    result += '整'
  } else {
    if (jiao > 0) result += CN_NUM[jiao] + '角'
    else if (fen > 0) result += '零'
    if (fen > 0) result += CN_NUM[fen] + '分'
  }
  return result
}

async function resolveQuoteLabels(form: Record<string, unknown>): Promise<QuoteLabels> {
  const userIds = collectIds(form.sales_person)
  const custIds = collectIds(form.customer_name)
  const [users, customers] = await Promise.all([
    getPersonLabelMap(userIds),
    getCustomerLabelMap(custIds),
  ])
  return { users, customers }
}

function printFileNameFromHtml(html: string): string {
  const m = html.match(/<title[^>]*>([^<]*)<\/title>/i)
  return (m?.[1] || '报价单').trim()
}

export function buildQuotePrintHtml(opts: {
  formData: Record<string, unknown>
  fieldDefinitions?: FieldDefinition[]
  businessNo?: string | null
  labels?: QuoteLabels
  printDate?: dayjs.Dayjs
}): string {
  const form = opts.formData || {}
  const labels = opts.labels || { users: {}, customers: {} }
  const now = opts.printDate || dayjs()
  const serial = String(form.serial_no || opts.businessNo || '').trim()
  const contact = personName(form.sales_person, labels)
  const recipient = customerName(form.customer_name, labels)
  const remark = String(form.special_reminder || '').trim()
  const lines = (Array.isArray(form.price_lines) ? form.price_lines : []) as PriceLine[]

  const rowHtml = lines.map((line) => {
    const up = lineUnitPrice(line)
    const lt = lineTotal(line)
    const qty = parseNum(line.qty)
    return `<tr>
      <td class="c-name">${escHtml(equipmentLabel(line))}</td>
      <td class="c-num">${qty != null ? escHtml(qty) : ''}</td>
      <td class="c-unit">${escHtml(line.unit || '')}</td>
      <td class="c-money">${up != null ? escHtml(fmtMoney(up)) : ''}</td>
      <td class="c-money">${lt != null ? escHtml(fmtMoney(lt)) : ''}</td>
      <td class="c-remark">${escHtml(lineRemark(line))}</td>
    </tr>`
  }).join('')

  const minRows = Math.max(6, lines.length)
  const blankRows = minRows - lines.length
  const blankHtml = blankRows > 0
    ? Array.from({ length: blankRows }, () => '<tr><td>&nbsp;</td><td></td><td></td><td></td><td></td><td></td></tr>').join('')
    : ''

  const grandTotal = lines.reduce((sum, line) => {
    const lt = lineTotal(line)
    return lt != null ? sum + lt : sum
  }, 0)
  const hasTotal = grandTotal > 0
  const totalUpper = hasTotal ? amountToChineseUpper(grandTotal) : ''
  const totalNum = hasTotal ? fmtMoney(grandTotal) : ''

  const dateShort = now.format('YYYY/M/D')
  const dateLong = `${now.format('YYYY')} 年 ${now.format('M')} 月 ${now.format('D')} 日`
  const title = serial ? `报价单 ${serial}` : '报价单'

  return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>${escHtml(title)}</title>
<style>
  @page { size: A4 portrait; margin: 12mm 15mm; }
  * { box-sizing: border-box; }
  body {
    font-family: "SimSun", "Songti SC", "Microsoft YaHei", serif;
    font-size: 12pt;
    color: #000;
    margin: 0;
    line-height: 1.45;
  }
  .sheet { width: 100%; }
  .head { display: flex; align-items: flex-start; margin-bottom: 6mm; }
  .head-mark {
    width: 22mm; height: 22mm; border: 1px solid #999; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    font-size: 9pt; color: #666; text-align: center; line-height: 1.2;
  }
  .head-title {
    flex: 1; text-align: center; font-size: 22pt; font-weight: 700;
    letter-spacing: 2px; padding-top: 2mm;
  }
  table.meta-grid {
    width: 100%; border-collapse: collapse; margin-bottom: 3mm; font-size: 11pt;
    table-layout: fixed;
  }
  table.meta-grid td {
    width: 50%; vertical-align: bottom; padding: 0 3mm 2mm 0;
  }
  table.meta-grid td.right { padding-right: 0; padding-left: 3mm; }
  table.meta-grid .pair { display: flex; align-items: flex-end; gap: 0; }
  table.meta-grid .lbl { white-space: nowrap; flex-shrink: 0; letter-spacing: 0; }
  table.meta-grid .val {
    flex: 1; border-bottom: 1px solid #000; min-height: 1.25em;
    padding: 0 1mm 0.5mm; margin-left: 0.5mm;
  }
  .to-line {
    display: flex; align-items: baseline; margin-bottom: 2mm; font-size: 11pt;
  }
  .to-line .lbl { white-space: nowrap; flex-shrink: 0; }
  .to-line .val { flex: 1; padding: 0; margin-left: 0; }
  .salute { margin: 0 0 2mm; font-size: 11pt; line-height: 1.6; }
  .doc-title { text-align: center; font-size: 16pt; font-weight: 700; margin: 2mm 0 3mm; letter-spacing: 8px; }
  table.lines { width: 100%; border-collapse: collapse; font-size: 11pt; }
  table.lines th, table.lines td { border: 1px solid #000; padding: 2mm 1.5mm; text-align: center; vertical-align: middle; }
  table.lines th { font-weight: 700; background: #fff; }
  table.lines .c-name { text-align: left; min-width: 36mm; }
  table.lines .c-num { width: 14mm; }
  table.lines .c-unit { width: 14mm; }
  table.lines .c-money { width: 22mm; text-align: right; padding-right: 2mm; }
  table.lines .c-remark { text-align: left; min-width: 24mm; }
  table.lines tr.total td { font-weight: 700; text-align: left; }
  table.lines tr.total .sum-label { text-align: center; }
  table.lines tr.total .sum-upper { text-align: left; padding-left: 3mm; }
  table.lines tr.total .sum-num { text-align: right; padding-right: 2mm; white-space: nowrap; }
  .terms { margin-top: 3mm; font-size: 11pt; line-height: 1.7; }
  .terms .row { display: flex; gap: 2mm; }
  .terms .lbl { white-space: nowrap; }
  .terms .val { flex: 1; border-bottom: 1px solid #000; min-height: 5mm; }
  .sign { margin-top: 10mm; text-align: right; font-size: 12pt; line-height: 1.8; }
</style></head><body><div class="sheet">
  <div class="head">
    <div class="head-mark">二维码<br/>LOGO</div>
    <div class="head-title">${escHtml(COMPANY)}</div>
  </div>
  <table class="meta-grid">
    <tr>
      <td>
        <div class="pair">
          <span class="lbl">发件人：</span>
          <span class="val">${escHtml(COMPANY)}</span>
        </div>
      </td>
      <td class="right">
        <div class="pair">
          <span class="lbl">日&nbsp;期：</span>
          <span class="val">${escHtml(dateShort)}</span>
        </div>
      </td>
    </tr>
    <tr>
      <td>
        <div class="pair">
          <span class="lbl">关&nbsp;于：</span>
          <span class="val">报价</span>
        </div>
      </td>
      <td class="right">
        <div class="pair">
          <span class="lbl">页&nbsp;数：</span>
          <span class="val">1</span>
        </div>
      </td>
    </tr>
    <tr>
      <td>
        <div class="pair">
          <span class="lbl">联系人：</span>
          <span class="val">${escHtml(contact)}</span>
        </div>
      </td>
      <td class="right">
        <div class="pair">
          <span class="lbl">电&nbsp;话：</span>
          <span class="val"></span>
        </div>
      </td>
    </tr>
  </table>
  <div class="to-line">
    <span class="lbl">致：</span>
    <span class="val">${escHtml(recipient)}</span>
  </div>
  <p class="salute">&nbsp;&nbsp;您好：首先感谢贵公司对我公司业务的信任和支持，现将您垂询的设备备件报价如下：</p>
  <div class="doc-title">报&nbsp;&nbsp;价&nbsp;&nbsp;单</div>
  <table class="lines">
    <thead><tr>
      <th>设备名称</th><th>数量</th><th>单位</th><th>单价/元</th><th>总价/元</th><th>备注</th>
    </tr></thead>
    <tbody>
      ${rowHtml}${blankHtml}
      <tr class="total">
        <td colspan="2" class="sum-label">合&nbsp;&nbsp;计</td>
        <td colspan="2" class="sum-upper">大写：${escHtml(totalUpper)}</td>
        <td colspan="2" class="sum-num">¥：${escHtml(totalNum)}&nbsp;元</td>
      </tr>
    </tbody>
  </table>
  <div class="terms">
    <div class="row"><span class="lbl">备注：</span><span class="val">${escHtml(remark).replace(/\n/g, '<br/>')}</span></div>
    <div>报价有效期：自报价之日起 ${VALIDITY_DAYS} 天。</div>
    <div>工&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;期：${LEAD_TIME_DAYS} 天。</div>
    <div>付款方式：${escHtml(DEFAULT_PAYMENT)}</div>
  </div>
  <div class="sign">
    <div>${escHtml(COMPANY)}</div>
    <div>${escHtml(dateLong)}</div>
  </div>
</div></body></html>`
}

export async function printQuoteInstance(opts: {
  formData: Record<string, unknown>
  fieldDefinitions?: FieldDefinition[]
  businessNo?: string | null
  legacyBrowserPrint?: boolean
}): Promise<void> {
  const labels = await resolveQuoteLabels(opts.formData || {})
  const html = buildQuotePrintHtml({
    formData: opts.formData,
    fieldDefinitions: opts.fieldDefinitions,
    businessNo: opts.businessNo,
    labels,
  })
  const fileName = printFileNameFromHtml(html) || '报价单'
  if (opts.legacyBrowserPrint) {
    printHtml(html, { orientation: 'portrait', fileName })
    return
  }
  setPdfPreviewLoading(true, fileName)
  try {
    const { blob, fileName: pdfName } = await htmlToPdfBlob(html, {
      orientation: 'portrait',
      fileName,
      margins: QUOTE_PRINT_MARGINS,
    })
    openPdfPreview(blob, pdfName)
  } catch {
    closePdfPreview()
    printHtml(html, { orientation: 'portrait', fileName })
  }
}

export function isQuoteManagementForm(
  templateCode?: string | null,
  formCode?: string | null,
): boolean {
  return templateCode === 'quote_management' || formCode === 'quote_management'
}
