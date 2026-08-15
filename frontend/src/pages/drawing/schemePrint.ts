/**
 * 图纸类打印：输出两套 A4 表格单据（对齐简道云在线表格打印版式）。
 * - 方案管理有合同号 / 合同图纸领用 → 合同图纸（资料）领用申请
 * - 方案管理无合同号 / 安装图设计通知 → 安装图通知单及设计卡
 *
 * 版式要点（对照简道云截图）：
 * - 横向 A4；整页一张表铺满；12 列栅格，标签窄、内容宽
 * - 字号约 10.5pt，靠压签字/意见区行高塞进一页，而不是缩小字体
 */
import dayjs from 'dayjs'
import { printHtml, escHtml } from '@/utils/printHtml'
import { getPersonLabelMap } from '@/components/lowcode/fields/PersonField'
import { getDeptNameMap } from '@/components/lowcode/fields/DeptField'
import { getProjectLabelMap } from '@/components/lowcode/fields/ProjectField'
import { getContractLabelMap } from '@/components/lowcode/fields/ContractField'
import type { FieldDefinition, WfFlowStep } from '@/types/lowcode'

type Labels = {
  users: Record<string, string>
  depts: Record<string, string>
  projects: Record<string, string>
  contracts: Record<string, string>
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

function contractLabel(v: unknown, labels: Labels, form: Record<string, unknown>): string {
  if (typeof form.contract_no === 'string' && form.contract_no && !collectIds(v).length) {
    return form.contract_no
  }
  const ids = collectIds(v)
  if (!ids.length) return form.contract_no != null ? String(form.contract_no) : ''
  return ids.map((id) => labels.contracts[id] || id).join('、')
}

/** 标签「图纸编号（合同号）」→ 仅图纸编号；无括号则原样 */
function drawingNoOnly(label: string): string {
  const s = String(label || '').trim()
  if (!s) return ''
  const m = s.match(/^(.+?)\s*[（(]/)
  if (m?.[1]?.trim()) return m[1].trim()
  return s.replace(/\s+/g, ' ')
}

/** 打印「合同号」列与 PDF 文件名：只用图纸编号，不带 QQ 等业务合同号 */
function printDrawingNo(v: unknown, labels: Labels, form: Record<string, unknown>): string {
  const fromField = form.drawing_no != null && String(form.drawing_no).trim()
    ? String(form.drawing_no).trim()
    : ''
  if (fromField && !/^[0-9a-f-]{36}$/i.test(fromField)) return fromField
  return drawingNoOnly(contractLabel(v, labels, form))
}

function projectLabel(v: unknown, labels: Labels): string {
  return collectIds(v).map((id) => labels.projects[id] || id).join('、')
}

function yesNoStack(value: unknown): string {
  const s = String(value ?? '')
  const yes = s === '是' || s === 'true' || s === '1'
  const no = s === '否' || s === 'false' || s === '0'
  return `<div class="chk-stack"><div>${yes ? '☑' : '☐'}是</div><div>${no ? '☑' : '☐'}否</div></div>`
}

function metaLine(items: [string, string][]): string {
  return `<div class="meta">${items.map(([k, v]) => `<span><b>${escHtml(k)}：</b>${escHtml(v || '')}</span>`).join('')}</div>`
}

function cell(v: unknown): string {
  return escHtml(v == null || v === '' ? '' : String(v))
}

function printCss(): string {
  return `
    * { box-sizing: border-box; }
    html, body { margin: 0; padding: 0; width: 100%; }
    body {
      font-family: "SimSun","Songti SC","STSong","Microsoft YaHei",serif;
      color: #000;
      font-size: 10.5pt;
      line-height: 1.25;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }
    .sheet { width: 100%; padding: 0; }
    h1 {
      text-align: center;
      font-size: 14pt;
      font-weight: 700;
      letter-spacing: 0.3em;
      margin: 0 0 3pt;
      line-height: 1.15;
    }
    /* 12 列栅格：标签窄、内容宽，横向铺满 */
    table.form {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }
    table.form col { width: 8.333%; }
    table.form td {
      border: 1px solid #000;
      padding: 2pt 3pt;
      vertical-align: middle;
      word-break: break-word;
      overflow-wrap: anywhere;
    }
    .lbl {
      font-weight: 700;
      text-align: center;
      line-height: 1.2;
      font-size: 9pt;
    }
    .lbl .sub {
      font-weight: 400;
      font-size: 8pt;
      display: block;
      line-height: 1.1;
    }
    .val { text-align: center; font-size: 10.5pt; }
    .val-left { text-align: left; font-size: 10.5pt; }
    .sign { height: 18pt; vertical-align: top; }
    /* 安装图签字区：签字列加宽、是否列收窄、填写行加高 */
    table.sign-block {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }
    table.sign-block td {
      border: 1px solid #000;
      padding: 2pt 2pt;
      vertical-align: middle;
      word-break: break-word;
      overflow-wrap: anywhere;
    }
    table.sign-block tr.sign-head td { height: auto; }
    table.sign-block tr.sign-body td {
      height: 36pt;
      min-height: 36pt;
      vertical-align: top;
    }
    table.sign-block tr.sign-body td.yn {
      height: 36pt;
      vertical-align: middle;
    }
    .idea { min-height: 56pt; height: 56pt; vertical-align: top; }
    .opin { min-height: 32pt; height: 32pt; vertical-align: top; }
    .result { min-height: 36pt; height: 36pt; vertical-align: top; }
    .matter { min-height: 16pt; vertical-align: top; }
    .chk-stack { text-align: center; line-height: 1.35; font-size: 10pt; }
    /* 是否勾选列：只够 ☐是/☐否，标签允许多行挤窄 */
    .lbl.yn { font-size: 8pt; line-height: 1.15; padding: 1pt 1pt; }
    .val.yn { padding: 1pt 1pt; }
    .meta {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 2pt 10pt;
      font-size: 10.5pt;
      margin: 0 0 3pt;
      line-height: 1.35;
    }
    .meta b { font-weight: 700; }
    /* 表下审批区：无表格边框，左标签 + 小字记录 + 右打印信息 */
    .approval-foot {
      display: flex;
      align-items: flex-start;
      gap: 6pt 10pt;
      width: 100%;
      margin-top: 4pt;
      border: none;
    }
    .approval-foot .approval-label {
      flex: 0 0 auto;
      font-size: 10.5pt;
      line-height: 1.4;
      white-space: nowrap;
    }
    .approval-foot .ops { flex: 1; min-width: 0; }
    .approval-foot .foot-side {
      flex: 0 0 auto;
      text-align: right;
      font-size: 10.5pt;
      line-height: 1.55;
      white-space: nowrap;
    }
    /* 审批记录：偏小、像流水日志 */
    .ops {
      font-size: 8pt;
      line-height: 1.35;
      text-align: left;
      color: #333;
    }
    .ops .op {
      display: block;
      width: max-content;
      max-width: 100%;
      padding: 1pt 0 2pt;
      border-bottom: 1px dotted #888;
      white-space: nowrap;
    }
    .ops .op:last-child { border-bottom: none; padding-bottom: 0; }
    /* 子表明细（设备/原料）：多行扩展，表头+数据行 */
    table.detail {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }
    table.detail td {
      border: 1px solid #000;
      padding: 2pt 2pt;
      vertical-align: middle;
      word-break: break-word;
      overflow-wrap: anywhere;
      font-size: 9pt;
      text-align: center;
    }
    table.detail td.dh {
      font-weight: 700;
      font-size: 8pt;
      line-height: 1.15;
    }
    table.detail td.dl { text-align: left; }
    td.nest { padding: 0 !important; border: 1px solid #000; }
    /* 对齐简道云：横向 A4 */
    @page { size: A4 landscape; margin: 6mm 8mm; }
    @media print {
      html, body { width: 100%; }
      .sheet { width: 100%; }
    }
  `
}

function wrapDoc(title: string, body: string): string {
  return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>${escHtml(title)}</title>
  <style>${printCss()}</style></head><body><div class="sheet">${body}</div></body></html>`
}

/** 打印另存 PDF 文件名：去掉非法字符与空白 */
function sanitizePrintFileName(name: string, fallback: string): string {
  const s = name.replace(/[\\/:*?"<>|]/g, '').replace(/\s+/g, '').trim()
  return s || fallback
}

/** 文件名用图纸编号（不用括号内的 QQ 合同号） */
function contractNoForFileName(
  form: Record<string, unknown>,
  labels: Labels,
): string {
  return printDrawingNo(form.contract_no, labels, form)
}

function requisitionPrintFileName(opts: {
  form: Record<string, unknown>
  labels: Labels
  orderPerson: string
  cardDate: string
}): string {
  const no = contractNoForFileName(opts.form, opts.labels)
  const date = opts.cardDate || fmtDate(opts.form.apply_datetime) || dayjs().format('YYYY-MM-DD')
  return sanitizePrintFileName(
    `${no}${opts.orderPerson}合同资料领用${date}`,
    '合同图纸资料领用申请',
  )
}

function installPrintFileName(opts: {
  designCardNo: string
  orderPerson: string
}): string {
  return sanitizePrintFileName(
    `${opts.designCardNo}${opts.orderPerson}`,
    '安装图通知单及设计卡',
  )
}

function colgroup12(): string {
  return `<colgroup>${Array.from({ length: 12 }, () => '<col>').join('')}</colgroup>`
}

function detailRows(rows: unknown): Record<string, unknown>[] {
  if (!Array.isArray(rows) || !rows.length) return []
  return rows.filter((r): r is Record<string, unknown> => !!r && typeof r === 'object')
}

function detailColOptionLabel(
  fields: FieldDefinition[],
  tableId: string,
  colId: string,
  value: unknown,
): string {
  if (value == null || value === '') return ''
  const table = fields.find((f) => f.id === tableId)
  const col = table?.detail_table_columns?.find((c) => c.id === colId)
  const opts = col?.options || []
  if (Array.isArray(value)) {
    return value.map((v) => {
      const o = opts.find((x) => x.value === v)
      return o?.label || String(v)
    }).join('、')
  }
  const o = opts.find((x) => x.value === value)
  return o?.label || String(value)
}

function matCell(
  fields: FieldDefinition[],
  tableId: string,
  row: Record<string, unknown>,
  starKey: string,
  plainKey: string,
): string {
  const raw = row[starKey] != null && row[starKey] !== '' ? row[starKey] : row[plainKey]
  const labeled = detailColOptionLabel(fields, tableId, starKey, raw)
    || detailColOptionLabel(fields, tableId, plainKey, raw)
  return cell(labeled || raw)
}

/** 出方案图物料 / 非出方案图物料 → 统一打印行 */
function materialPrintRows(
  form: Record<string, unknown>,
  fields: FieldDefinition[],
  extras: { productModel: string; processPos: string; installMethod: string; installPos: string },
): { tableId: string; rows: Record<string, unknown>[]; cells: string[][] } {
  const scheme = detailRows(form.scheme_material)
  if (scheme.length) {
    return {
      tableId: 'scheme_material',
      rows: scheme,
      cells: scheme.map((r) => {
        const names = Array.isArray(r.material_names)
          ? (r.material_names as unknown[]).map(String).join('、')
          : (r.material_name || r.material_names || '')
        const eff = matCell(fields, 'scheme_material', r, 'screening_eff_star', 'screening_eff')
          || matCell(fields, 'scheme_material', r, 'need_screening_eff_star', 'need_screening_eff')
        return [
          matCell(fields, 'scheme_material', r, 'industry_star', 'industry'),
          cell(names),
          matCell(fields, 'scheme_material', r, 'mesh_size_star', 'mesh_size'),
          matCell(fields, 'scheme_material', r, 'throughput_star', 'throughput'),
          cell(extras.productModel),
          matCell(fields, 'scheme_material', r, 'feed_size_star', 'feed_size'),
          matCell(fields, 'scheme_material', r, 'bulk_density_star', 'bulk_density'),
          cell(extras.processPos),
          eff,
          matCell(fields, 'scheme_material', r, 'particle_dist_star', 'particle_dist'),
          matCell(fields, 'scheme_material', r, 'moisture_star', 'moisture'),
          cell(extras.installMethod),
          cell(extras.installPos),
        ]
      }),
    }
  }
  const non = detailRows(form.non_scheme_material)
  return {
    tableId: 'non_scheme_material',
    rows: non,
    cells: non.map((r) => [
      cell(detailColOptionLabel(fields, 'non_scheme_material', 'industry_2', r.industry_2) || r.industry_2),
      cell(r.material_name_2),
      cell(r.mesh_size_2),
      cell(r.throughput_2),
      cell(extras.productModel),
      cell(r.feed_size_2),
      cell(r.bulk_density_2),
      cell(extras.processPos),
      cell(
        detailColOptionLabel(fields, 'non_scheme_material', 'need_screening_eff_2', r.need_screening_eff_2)
        || r.need_screening_eff_2,
      ),
      cell(r.particle_dist_2),
      cell(r.moisture_2),
      cell(extras.installMethod),
      cell(extras.installPos),
    ]),
  }
}

function materialDetailTableHtml(
  form: Record<string, unknown>,
  fields: FieldDefinition[],
  extras: { productModel: string; processPos: string; installMethod: string; installPos: string },
): string {
  const { cells } = materialPrintRows(form, fields, extras)
  const headers = [
    '行业', '物料名称', '筛孔尺寸', '处理量', '产品型号', '入料粒度', '堆密度',
    '工艺位置', '要求筛分效率', '粒度分布', '水分', '安装方式', '安装位置',
  ]
  const head = `<tr>${headers.map((h) => `<td class="dh">${escHtml(h)}</td>`).join('')}</tr>`
  const body = (cells.length ? cells : [headers.map(() => '')]).map((cols) =>
    `<tr>${cols.map((c, i) => `<td class="${i === 1 ? 'dl' : ''}">${c}</td>`).join('')}</tr>`,
  ).join('')
  return `<table class="detail">${head}${body}</table>`
}

function approvalOpsHtml(steps?: WfFlowStep[] | null): string {
  const done = (steps || []).filter((s) =>
    s.action || s.opinion || s.handler_name
    || ['approved', 'completed', 'rejected', 'running', 'pending'].includes(s.status),
  )
  if (!done.length) return ''
  // flow_steps 已是最新在前（与简道云一致）
  const rows = done.map((s) => {
    const when = s.completed_at ? dayjs(s.completed_at).format('YYYY-MM-DD HH:mm') : ''
    const act = s.status_text || s.action || s.status || ''
    const who = s.handler_name || (s.assignees || []).map((a) => a.name).filter(Boolean).join('、') || ''
    const line = [s.node_name, who, when, act].filter(Boolean).join('  ')
    return `<div class="op">${escHtml(line)}</div>`
  }).join('')
  return `<div class="ops">${rows}</div>`
}

/**
 * 流程动态按「最新在前」；截到指定节点（含该节点），其后节点不进入打印。
 * 未出现目标节点时原样返回（流程尚未走到总工）。
 */
function stepsThroughNode(
  steps: WfFlowStep[] | null | undefined,
  nodeNameIncludes: string,
): WfFlowStep[] {
  const list = steps || []
  if (!list.length) return []
  const chrono = [...list].reverse()
  const cut = chrono.findIndex((s) => (s.node_name || '').includes(nodeNameIncludes))
  if (cut < 0) return list
  return chrono.slice(0, cut + 1).reverse()
}

/** 表下审批意见区（非表格）：标签 + 小字记录 + 打印时间/流水号 */
function approvalFootHtml(
  steps: WfFlowStep[] | null | undefined,
  form: Record<string, unknown>,
  businessNo?: string | null,
): string {
  const ops = approvalOpsHtml(steps) || (form.final_result != null && form.final_result !== ''
    ? `<div class="ops"><div class="op">${cell(form.final_result)}</div></div>`
    : '<div class="ops"></div>')
  const printAt = dayjs().format('YYYY-MM-DD HH:mm:ss')
  const serial = businessNo || ''
  return `<div class="approval-foot">
    <div class="approval-label">审批意见：</div>
    ${ops}
    <div class="foot-side"><div>打印时间：${escHtml(printAt)}</div><div>流水号：${escHtml(serial)}</div></div>
  </div>`
}

function buildRequisitionHtml(ctx: {
  form: Record<string, unknown>
  fields: FieldDefinition[]
  labels: Labels
  businessNo?: string | null
  steps?: WfFlowStep[] | null
}): string {
  const { form, fields, labels, businessNo, steps } = ctx
  const orderPerson = personName(form.order_person, labels)
  const dept = deptName(form.department, labels)
  const applicant = personName(form.applicant, labels)
  const cardDate = fmtDate(form.order_date || form.apply_datetime)
  const serial = businessNo || ''
  const contractNo = printDrawingNo(form.contract_no, labels, form)
  const transfer = optionLabel(fields, 'transfer_channel', form.transfer_channel)
  const drawingType = optionLabel(fields, 'drawing_type', form.drawing_type)
  const std = optionLabel(fields, 'involve_std_drawing', form.involve_std_drawing)
  const decrypt = form.need_decrypt != null
    ? (optionLabel(fields, 'need_decrypt', form.need_decrypt) || String(form.need_decrypt))
    : ''
  const approvalFoot = approvalFootHtml(
    stepsThroughNode(steps, '总工审批'),
    form,
    serial,
  )

  const body = `
    <h1>合同图纸（资料）领用申请</h1>
    ${metaLine([
      ['订货人', orderPerson],
      ['销售部门', dept],
      ['申请人', applicant],
      ['下卡日期', cardDate],
      ['流水号', serial],
    ])}
    <table class="form">
      ${colgroup12()}
      <tr>
        <td class="lbl" colspan="1">合同号</td>
        <td class="lbl" colspan="1">产品型号</td>
        <td class="lbl" colspan="1">设计人</td>
        <td class="lbl" colspan="2">图纸传递路径</td>
        <td class="lbl" colspan="1">是否解密</td>
        <td class="lbl" colspan="1">图纸类型</td>
        <td class="lbl" colspan="2">是否涉及企标图纸</td>
        <td class="lbl" colspan="3">附件/图片名称</td>
      </tr>
      <tr>
        <td class="val" colspan="1">${cell(contractNo)}</td>
        <td class="val" colspan="1">${cell(form.product_model)}</td>
        <td class="val" colspan="1"></td>
        <td class="val" colspan="2">${cell(transfer)}</td>
        <td class="val" colspan="1">${cell(decrypt)}</td>
        <td class="val" colspan="1">${cell(drawingType)}</td>
        <td class="val" colspan="2">${cell(std)}</td>
        <td class="val-left" colspan="3">${cell(form.attachment_name)}</td>
      </tr>
      <tr>
        <td class="lbl" colspan="1">申请事由</td>
        <td class="val-left matter" colspan="11">${cell(form.apply_reason || form.apply_or_change)}</td>
      </tr>
      <tr>
        <td class="nest" colspan="12">
          <table class="sign-block">
            <colgroup>
              <col style="width:10%">
              <col style="width:14%">
              <col style="width:8%">
              <col style="width:14%">
              <col style="width:14%">
              <col style="width:12%">
              <col style="width:10%">
              <col style="width:18%">
            </colgroup>
            <tr class="sign-head">
              <td class="lbl">设计人</td>
              <td class="lbl">审核<span class="sub">（室主任签）</span></td>
              <td class="lbl yn">是否需要业务内勤请示总经理</td>
              <td class="lbl">标准化<span class="sub">（标准化室签）</span></td>
              <td class="lbl">审定<span class="sub">（总工助理签）</span></td>
              <td class="lbl">批准<span class="sub">（总工签）</span></td>
              <td class="lbl">工作量</td>
              <td class="lbl">实际交图日期</td>
            </tr>
            <tr class="sign-body">
              <td class="val"></td>
              <td class="val"></td>
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
        <td class="lbl" colspan="1">设计思路</td>
        <td class="val-left idea" colspan="11"></td>
      </tr>
      <tr>
        <td class="lbl" colspan="1">计算过程</td>
        <td class="val-left idea" colspan="11"></td>
      </tr>
      <tr>
        <td class="lbl" colspan="1">专工意见</td>
        <td class="val-left opin" colspan="5"></td>
        <td class="lbl" colspan="1">室主任意见</td>
        <td class="val-left opin" colspan="5"></td>
      </tr>
      <tr>
        <td class="lbl" colspan="1">总工助理意见</td>
        <td class="val-left opin" colspan="5"></td>
        <td class="lbl" colspan="1">总工意见</td>
        <td class="val-left opin" colspan="5"></td>
      </tr>
      <tr>
        <td class="lbl" colspan="1">最后结果</td>
        <td class="val-left result" colspan="11"></td>
      </tr>
    </table>
    ${approvalFoot}`
  const fileTitle = requisitionPrintFileName({ form, labels, orderPerson, cardDate })
  return wrapDoc(fileTitle, body)
}

function buildInstallHtml(ctx: {
  form: Record<string, unknown>
  fields: FieldDefinition[]
  labels: Labels
  businessNo?: string | null
  steps?: WfFlowStep[] | null
}): string {
  const { form, fields, labels, businessNo, steps } = ctx
  const projectNo = projectLabel(form.related_project, labels)
    || projectLabel(form.project_no, labels)
    || (form.project_no_print != null ? String(form.project_no_print) : '')
    || (form.project_no != null && !/^[0-9a-f-]{36}$/i.test(String(form.project_no))
      ? String(form.project_no) : '')
  const orderPerson = personName(form.order_person, labels)
  const dept = deptName(form.department, labels)
  const applicant = personName(form.applicant, labels)
  const cardDate = fmtDate(form.card_date || form.order_date || form.apply_datetime)
  const designCard = form.design_card_no != null ? String(form.design_card_no) : ''
  const issueType = optionLabel(fields, 'drawing_issue_type', form.drawing_issue_type)
  const purpose = optionLabel(fields, 'pickup_purpose', form.pickup_purpose)
  const preDesigners = personName(form.pre_designers, labels)
  const requireDate = fmtDate(form.require_draw_date)
  const applyChange = form.apply_or_change != null ? String(form.apply_or_change) : ''
  const attachNames = form.attachment_names != null ? String(form.attachment_names) : ''
  const attention = form.attention != null ? String(form.attention) : ''
  const installPos = optionLabel(fields, 'install_position', form.install_position)
  const installMethod = optionLabel(fields, 'install_method', form.install_method)
  const envRows = detailRows(form.install_env)
  const processPos = envRows.map((r) => r.process_position).filter((v) => v != null && v !== '').join('、')
  // 设备明细：一行一条；表单级字段（新项目/下图类型等）只在首行带出
  const schemeRows = detailRows(form.scheme_detail)
  const equipBody = (schemeRows.length ? schemeRows : [{}]).map((r, idx) => {
    const pricing = r.need_pricing != null
      ? (detailColOptionLabel(fields, 'scheme_detail', 'need_pricing', r.need_pricing) || String(r.need_pricing))
      : ''
    return `<tr>
      <td class="val" colspan="1">${idx + 1}</td>
      <td class="val-left" colspan="2">${cell(r.equipment_name)}</td>
      <td class="val-left" colspan="3">${cell(r.design_req)}</td>
      <td class="val" colspan="1">${idx === 0 ? cell(form.is_new_project != null ? optionLabel(fields, 'is_new_project', form.is_new_project) : '') : ''}</td>
      <td class="val" colspan="1">${idx === 0 ? cell(issueType) : ''}</td>
      <td class="val" colspan="1">${idx === 0 ? cell(purpose) : ''}</td>
      <td class="val" colspan="1">${cell(pricing)}</td>
      <td class="val" colspan="1">${idx === 0 ? cell(requireDate) : ''}</td>
      <td class="val" colspan="1">${idx === 0 ? cell(preDesigners) : ''}</td>
    </tr>`
  }).join('')
  const approvalFoot = approvalFootHtml(
    stepsThroughNode(steps, '总工审批'),
    form,
    businessNo,
  )
  const productModel = form.product_model != null ? String(form.product_model) : ''

  const body = `
    <h1>安装图通知单及设计卡</h1>
    ${metaLine([
      ['项目号', projectNo],
      ['订货人', orderPerson],
      ['销售部门', dept],
      ['申请人', applicant],
      ['下卡日期', cardDate],
      ['设计卡号', designCard],
    ])}
    <table class="form">
      ${colgroup12()}
      <tr>
        <td class="lbl" colspan="1">序号</td>
        <td class="lbl" colspan="2">设备名称</td>
        <td class="lbl" colspan="3">设计要求</td>
        <td class="lbl" colspan="1">是否为新项目</td>
        <td class="lbl" colspan="1">下图类型</td>
        <td class="lbl" colspan="1">领图目的</td>
        <td class="lbl" colspan="1">是否核价</td>
        <td class="lbl" colspan="1">要求交图时间</td>
        <td class="lbl" colspan="1">前期沟通设计人员</td>
      </tr>
      ${equipBody}
      <tr>
        <td class="lbl" colspan="2">申请事由/修改事项</td>
        <td class="val-left matter" colspan="5">${cell(applyChange || form.matter)}</td>
        <td class="lbl" colspan="1">备注（附件）</td>
        <td class="val-left matter" colspan="4">${cell(attachNames)}</td>
      </tr>
      <tr>
        <td class="lbl" colspan="1">注意</td>
        <td class="val-left" colspan="11">${cell(attention)}</td>
      </tr>
      <tr>
        <td class="lbl" colspan="12">原料参数</td>
      </tr>
      <tr>
        <td class="nest" colspan="12">${materialDetailTableHtml(form, fields, {
          productModel, processPos, installMethod, installPos,
        })}</td>
      </tr>
      <tr>
        <td class="nest" colspan="12">
          <table class="sign-block">
            <colgroup>
              <col style="width:11%">
              <col style="width:11%">
              <col style="width:12%">
              <col style="width:6%">
              <col style="width:7%">
              <col style="width:12%">
              <col style="width:12%">
              <col style="width:12%">
              <col style="width:8%">
              <col style="width:9%">
            </colgroup>
            <tr class="sign-head">
              <td class="lbl">设计人</td>
              <td class="lbl">专工</td>
              <td class="lbl">审核<span class="sub">（室主任签）</span></td>
              <td class="lbl yn">是否有参数表</td>
              <td class="lbl yn">是否需要业务内勤请示总经理</td>
              <td class="lbl">标准化<span class="sub">（标准化室签）</span></td>
              <td class="lbl">审定<span class="sub">（总工助理签）</span></td>
              <td class="lbl">批准<span class="sub">（总工签）</span></td>
              <td class="lbl">工作量</td>
              <td class="lbl">实际交图日期</td>
            </tr>
            <tr class="sign-body">
              <td class="val"></td>
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
        <td class="lbl" colspan="1">设计思路</td>
        <td class="val-left idea" colspan="11"></td>
      </tr>
      <tr>
        <td class="lbl" colspan="1">计算过程</td>
        <td class="val-left idea" colspan="11"></td>
      </tr>
      <tr>
        <td class="lbl" colspan="1">专工意见</td>
        <td class="val-left opin" colspan="5"></td>
        <td class="lbl" colspan="1">室主任意见</td>
        <td class="val-left opin" colspan="5"></td>
      </tr>
      <tr>
        <td class="lbl" colspan="1">审定意见</td>
        <td class="val-left opin" colspan="5"></td>
        <td class="lbl" colspan="1">批准总工意见</td>
        <td class="val-left opin" colspan="5"></td>
      </tr>
      <tr>
        <td class="lbl" colspan="1">最后结果</td>
        <td class="val-left result" colspan="11"></td>
      </tr>
    </table>
    ${approvalFoot}`
  const fileTitle = installPrintFileName({ designCardNo: designCard, orderPerson })
  return wrapDoc(fileTitle, body)
}

async function resolveLabels(
  form: Record<string, unknown>,
): Promise<Labels> {
  const personIds = [
    ...collectIds(form.applicant),
    ...collectIds(form.order_person),
    ...collectIds(form.designer),
    ...collectIds(form.design_assignees),
    ...collectIds(form.pre_designers),
    ...collectIds(form.transfer_packaging_users),
    ...collectIds(form.transfer_sw_lwt),
  ]
  const projectIds = [
    ...collectIds(form.related_project),
    ...collectIds(form.project_no),
  ]
  const contractIds = collectIds(form.contract_no)
  const [users, depts, projects, contracts] = await Promise.all([
    personIds.length ? getPersonLabelMap(personIds) : Promise.resolve({} as Record<string, string>),
    getDeptNameMap(),
    projectIds.length ? getProjectLabelMap(projectIds, 'code') : Promise.resolve({} as Record<string, string>),
    contractIds.length ? getContractLabelMap(contractIds) : Promise.resolve({} as Record<string, string>),
  ])
  return { users, depts, projects, contracts }
}

/** 是否方案管理单据（审批详情里据此露出打印） */
export function isSchemeManagementForm(
  fields?: FieldDefinition[] | null,
  formData?: Record<string, unknown> | null,
  processName?: string | null,
): boolean {
  if (fields?.some((f) => f.id === 'scheme_type')) return true
  const st = formData?.scheme_type
  if (st != null && st !== '') return true
  if (processName && /方案管理/.test(processName)) return true
  return false
}

/** 是否合同图纸领用（独立 builtin，打印版式与方案管理「有合同号」相同） */
export function isDrawingRequisitionForm(
  fields?: FieldDefinition[] | null,
  formData?: Record<string, unknown> | null,
  processName?: string | null,
): boolean {
  if (isSchemeManagementForm(fields, formData, processName)) return false
  if (isInstallDrawingNoticeForm(fields, formData, processName)) return false
  if (processName && /(合同图纸|图纸领用|资料[）)]领用)/.test(processName)) return true
  const ids = new Set((fields || []).map((f) => f.id))
  if (ids.has('transfer_channel') && ids.has('drawing_type') && ids.has('involve_std_drawing')) {
    return true
  }
  return false
}

/** 是否安装图设计通知（独立 builtin，打印版式与方案管理「无合同号」相同） */
export function isInstallDrawingNoticeForm(
  fields?: FieldDefinition[] | null,
  formData?: Record<string, unknown> | null,
  processName?: string | null,
): boolean {
  if (isSchemeManagementForm(fields, formData, processName)) return false
  if (processName && /安装图设计通知/.test(processName)) return true
  const ids = new Set((fields || []).map((f) => f.id))
  if (
    ids.has('project_no')
    && ids.has('design_card_no')
    && ids.has('drawing_issue_type')
    && !ids.has('scheme_type')
    && !ids.has('transfer_channel')
  ) {
    return true
  }
  return false
}

/** 方案管理 / 合同图纸领用 / 安装图设计通知：可打印对应单据 */
export function canPrintDrawingDocument(
  fields?: FieldDefinition[] | null,
  formData?: Record<string, unknown> | null,
  processName?: string | null,
): boolean {
  return isSchemeManagementForm(fields, formData, processName)
    || isDrawingRequisitionForm(fields, formData, processName)
    || isInstallDrawingNoticeForm(fields, formData, processName)
}

export async function printSchemeInstance(opts: {
  formData: Record<string, unknown>
  fieldDefinitions: FieldDefinition[]
  businessNo?: string | null
  flowSteps?: WfFlowStep[] | null
}): Promise<void> {
  const form = opts.formData || {}
  const fields = opts.fieldDefinitions || []
  const labels = await resolveLabels(form)
  const schemeType = String(form.scheme_type || '')
  const serial = (form.serial_no != null && form.serial_no !== '' ? String(form.serial_no) : '')
    || (opts.businessNo && opts.businessNo !== String(form.design_card_no || '')
      ? String(opts.businessNo)
      : '')
  // 方案管理无合同号 / 独立安装图设计通知 → 安装图通知单；其余 → 领用单
  const useInstall = schemeType === 'install'
    || isInstallDrawingNoticeForm(fields, form)
  const html = useInstall
    ? buildInstallHtml({
      form, fields, labels,
      businessNo: serial, steps: opts.flowSteps,
    })
    : buildRequisitionHtml({
      form, fields, labels,
      businessNo: serial, steps: opts.flowSteps,
    })
  const m = html.match(/<title[^>]*>([^<]*)<\/title>/i)
  const fileName = (m?.[1] || '')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .trim()
  printHtml(html, { orientation: 'landscape', fileName: fileName || undefined })
}
