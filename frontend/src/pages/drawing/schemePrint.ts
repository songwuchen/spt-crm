/**
 * 方案管理打印：按 scheme_type 输出两套 A4 表格单据（对齐简道云在线表格打印版式）。
 * - requisition → 合同图纸（资料）领用申请
 * - install → 安装图通知单及设计卡
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

function projectLabel(v: unknown, labels: Labels): string {
  return collectIds(v).map((id) => labels.projects[id] || id).join('、')
}

function yesNoBoxes(value: unknown): string {
  const s = String(value ?? '')
  const yes = s === '是' || s === 'true' || s === '1'
  const no = s === '否' || s === 'false' || s === '0'
  return `<span class="chk">${yes ? '☑' : '☐'}是</span><span class="chk">${no ? '☑' : '☐'}否</span>`
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
    .idea { min-height: 22pt; height: 22pt; vertical-align: top; }
    .opin { min-height: 18pt; height: 18pt; vertical-align: top; }
    .final { min-height: 16pt; vertical-align: middle; }
    .matter { min-height: 16pt; vertical-align: top; }
    .chk { margin-right: 10pt; white-space: nowrap; }
    .foot {
      margin-top: 4pt;
      display: flex;
      justify-content: space-between;
      font-size: 9pt;
      line-height: 1.3;
    }
    .ops {
      margin-top: 3pt;
      font-size: 9pt;
      line-height: 1.35;
    }
    .ops b { font-size: 9.5pt; margin-right: 4pt; }
    .ops .op { margin: 0; }
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
        return [
          matCell(fields, 'scheme_material', r, 'industry_star', 'industry'),
          cell(names),
          matCell(fields, 'scheme_material', r, 'mesh_size_star', 'mesh_size'),
          matCell(fields, 'scheme_material', r, 'throughput_star', 'throughput'),
          matCell(fields, 'scheme_material', r, 'feed_size_star', 'feed_size'),
          matCell(fields, 'scheme_material', r, 'bulk_density_star', 'bulk_density'),
          matCell(fields, 'scheme_material', r, 'need_screening_eff_star', 'need_screening_eff'),
          matCell(fields, 'scheme_material', r, 'particle_dist_star', 'particle_dist'),
          matCell(fields, 'scheme_material', r, 'moisture_star', 'moisture'),
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
      cell(r.feed_size_2),
      cell(r.bulk_density_2),
      cell(
        detailColOptionLabel(fields, 'non_scheme_material', 'need_screening_eff_2', r.need_screening_eff_2)
        || r.need_screening_eff_2,
      ),
      cell(r.particle_dist_2),
      cell(r.moisture_2),
    ]),
  }
}

function materialDetailTableHtml(
  form: Record<string, unknown>,
  fields: FieldDefinition[],
): string {
  const { cells } = materialPrintRows(form, fields)
  const headers = [
    '行业', '物料名称', '筛孔尺寸', '处理量', '入料粒度',
    '堆密度', '要求筛分效率', '粒度分布', '水分',
  ]
  const head = `<tr>${headers.map((h) => `<td class="dh">${escHtml(h)}</td>`).join('')}</tr>`
  const body = (cells.length ? cells : [headers.map(() => '')]).map((cols) =>
    `<tr>${cols.map((c, i) => `<td class="${i === 1 ? 'dl' : ''}">${c}</td>`).join('')}</tr>`,
  ).join('')
  return `<table class="detail">${head}${body}</table>`
}

function approvalOpsHtml(steps?: WfFlowStep[] | null): string {
  const done = (steps || []).filter((s) =>
    s.action || s.opinion || ['approved', 'completed', 'rejected'].includes(s.status),
  )
  if (!done.length) return ''
  const lines = done.map((s) => {
    const when = s.completed_at ? dayjs(s.completed_at).format('YYYY-MM-DD HH:mm') : ''
    const act = s.status_text || s.action || s.status || ''
    const who = s.handler_name || (s.assignees || []).map((a) => a.name).filter(Boolean).join('、') || ''
    const op = s.opinion ? `：${s.opinion}` : ''
    return `<div class="op">${escHtml([s.node_name, who, when, act].filter(Boolean).join(' '))}${escHtml(op)}</div>`
  }).join('')
  return `<div class="ops"><b>审核意见：</b>${lines}</div>`
}

/** 标签 + 内容；默认内容占两格（比标签宽，对齐简道云「宽带」观感） */
function pair(label: string, value: unknown, labelSpan = 1, valueSpan = 2): string {
  return `<td class="lbl" colspan="${labelSpan}">${escHtml(label)}</td><td class="val" colspan="${valueSpan}">${cell(value)}</td>`
}

/** 表头等宽：标签/值各 1 格，一行可排 6 组铺满 12 列 */
function pair1(label: string, value: unknown): string {
  return pair(label, value, 1, 1)
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
  const contractNo = contractLabel(form.contract_no, labels, form)
  const designer = personName(form.designer, labels)
  const transfer = optionLabel(fields, 'transfer_channel', form.transfer_channel)
  const drawingType = optionLabel(fields, 'drawing_type', form.drawing_type)
  const std = optionLabel(fields, 'involve_std_drawing', form.involve_std_drawing)
  const gm = form.need_gm_approval

  const body = `
    <h1>合同图纸（资料）领用申请</h1>
    <table class="form">
      ${colgroup12()}
      <tr>
        ${pair('订货人', orderPerson)}
        ${pair('销售部门', dept)}
        ${pair('申请人', applicant)}
        ${pair('下卡日期', cardDate)}
      </tr>
      <tr>
        ${pair('流水号', serial)}
        ${pair('合同号', contractNo)}
        ${pair('产品型号', form.product_model)}
        ${pair('设计人', designer)}
      </tr>
      <tr>
        ${pair('图纸传递途径', transfer)}
        ${pair('是否解密', form.need_decrypt != null ? optionLabel(fields, 'need_decrypt', form.need_decrypt) : '')}
        ${pair('图纸类型', drawingType)}
        ${pair('是否涉及企标图纸', std)}
      </tr>
      <tr>
        <td class="lbl" colspan="2">附件/图片名称</td>
        <td class="val-left" colspan="10">${cell(form.attachment_name)}</td>
      </tr>
      <tr>
        <td class="lbl" colspan="2">申请事由</td>
        <td class="val-left matter" colspan="10">${cell(form.apply_reason || form.apply_or_change)}</td>
      </tr>
      <tr>
        <td class="lbl" colspan="1">设计人</td>
        <td class="lbl" colspan="2">审核<span class="sub">（室主任签）</span></td>
        <td class="lbl" colspan="2">是否需要业务内勤请示总经理</td>
        <td class="lbl" colspan="2">标准化<span class="sub">（标准化室签）</span></td>
        <td class="lbl" colspan="2">审定<span class="sub">（总工助理签）</span></td>
        <td class="lbl" colspan="1">批准<span class="sub">（总工签）</span></td>
        <td class="lbl" colspan="1">工作量</td>
        <td class="lbl" colspan="1">实际交图日期</td>
      </tr>
      <tr>
        <td class="val sign" colspan="1">${cell(designer)}</td>
        <td class="val sign" colspan="2"></td>
        <td class="val sign" colspan="2">${yesNoBoxes(gm)}</td>
        <td class="val sign" colspan="2"></td>
        <td class="val sign" colspan="2"></td>
        <td class="val sign" colspan="1"></td>
        <td class="val sign" colspan="1"></td>
        <td class="val sign" colspan="1"></td>
      </tr>
      <tr>
        <td class="lbl" colspan="1">设计思路</td>
        <td class="val-left idea" colspan="11">${cell(form.design_idea)}</td>
      </tr>
      <tr>
        <td class="lbl" colspan="1">计算过程</td>
        <td class="val-left idea" colspan="11">${cell(form.calc_process)}</td>
      </tr>
      <tr>
        <td class="lbl" colspan="1">专工意见</td>
        <td class="val-left opin" colspan="5">${cell(form.expert_opinion)}</td>
        <td class="lbl" colspan="1">室主任意见</td>
        <td class="val-left opin" colspan="5">${cell(form.office_opinion)}</td>
      </tr>
      <tr>
        <td class="lbl" colspan="1">总工助理意见</td>
        <td class="val-left opin" colspan="5">${cell(form.assistant_opinion)}</td>
        <td class="lbl" colspan="1">总工意见</td>
        <td class="val-left opin" colspan="5">${cell(form.chief_opinion)}</td>
      </tr>
      <tr>
        <td class="lbl" colspan="1">最后结果</td>
        <td class="val-left final" colspan="11">${cell(form.final_result)}</td>
      </tr>
    </table>
    ${approvalOpsHtml(steps)}
    <div class="foot">
      <span>打印时间：${escHtml(dayjs().format('YYYY-MM-DD HH:mm:ss'))}</span>
      <span>流水号：${escHtml(serial)}</span>
    </div>`
  return wrapDoc('合同图纸（资料）领用申请', body)
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
    || (form.project_no != null ? String(form.project_no) : '')
    || (form.project_no_print != null ? String(form.project_no_print) : '')
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
  const designer = personName(form.design_assignees, labels)

  // 设备明细：一行一条，表单级字段（新项目/下图类型等）只在首行带出
  const schemeRows = detailRows(form.scheme_detail)
  const equipBody = (schemeRows.length ? schemeRows : [{}]).map((r, idx) => {
    const hasRev = r.has_attach_or_rev != null ? String(r.has_attach_or_rev) : ''
    return `<tr>
      <td class="val" colspan="1">${idx + 1}</td>
      <td class="val-left" colspan="2">${cell(r.equipment_name)}</td>
      <td class="val-left" colspan="3">${cell(r.design_req)}</td>
      <td class="val" colspan="1">${idx === 0 ? cell(form.is_new_project != null ? optionLabel(fields, 'is_new_project', form.is_new_project) : '') : ''}</td>
      <td class="val" colspan="1">${idx === 0 ? cell(issueType) : ''}</td>
      <td class="val" colspan="1">${idx === 0 ? cell(purpose) : ''}</td>
      <td class="val" colspan="1">${cell(hasRev)}</td>
      <td class="val" colspan="1">${idx === 0 ? cell(requireDate) : ''}</td>
      <td class="val" colspan="1">${idx === 0 ? cell(preDesigners) : ''}</td>
    </tr>`
  }).join('')

  const body = `
    <h1>安装图通知单及设计卡</h1>
    <table class="form">
      ${colgroup12()}
      <tr>
        ${pair1('项目号', projectNo)}
        ${pair1('订货人', orderPerson)}
        ${pair1('销售部门', dept)}
        ${pair1('申请人', applicant)}
        ${pair1('下卡日期', cardDate)}
        ${pair1('设计卡号', designCard)}
      </tr>
      <tr>
        <td class="lbl" colspan="1">序号</td>
        <td class="lbl" colspan="2">设备名称</td>
        <td class="lbl" colspan="3">设计要求</td>
        <td class="lbl" colspan="1">是否为新项目</td>
        <td class="lbl" colspan="1">下图类型</td>
        <td class="lbl" colspan="1">领图目的</td>
        <td class="lbl" colspan="1">是否修改</td>
        <td class="lbl" colspan="1">要求交图时间</td>
        <td class="lbl" colspan="1">前期现场设计人员</td>
      </tr>
      ${equipBody}
      <tr>
        <td class="lbl" colspan="2">申请事项/修改事项</td>
        <td class="val-left matter" colspan="10">${cell(applyChange || form.matter)}</td>
      </tr>
      <tr>
        <td class="lbl" colspan="2">备注（附件）</td>
        <td class="val-left" colspan="6">${cell(attachNames)}</td>
        <td class="lbl" colspan="1">注意</td>
        <td class="val-left" colspan="3">${cell(attention)}</td>
      </tr>
      <tr>
        <td class="lbl" colspan="12">原料参数</td>
      </tr>
      <tr>
        <td class="nest" colspan="12">${materialDetailTableHtml(form, fields)}</td>
      </tr>
      <tr>
        ${pair('产品型号', form.product_model)}
        ${pair('工艺位置', processPos)}
        ${pair('安装方式', installMethod)}
        ${pair('安装位置', installPos)}
      </tr>
      <tr>
        <td class="lbl" colspan="1">设计人</td>
        <td class="lbl" colspan="1">专工</td>
        <td class="lbl" colspan="2">审核<span class="sub">（室主任签）</span></td>
        <td class="lbl" colspan="2">标准化<span class="sub">（标准化室签）</span></td>
        <td class="lbl" colspan="2">审定<span class="sub">（总工助理签）</span></td>
        <td class="lbl" colspan="1">批准<span class="sub">（总工签）</span></td>
        <td class="lbl" colspan="1">工作量</td>
        <td class="lbl" colspan="2">实际交图日期</td>
      </tr>
      <tr>
        <td class="val sign" colspan="1">${cell(designer)}</td>
        <td class="val sign" colspan="1"></td>
        <td class="val sign" colspan="2"></td>
        <td class="val sign" colspan="2"></td>
        <td class="val sign" colspan="2"></td>
        <td class="val sign" colspan="1"></td>
        <td class="val sign" colspan="1"></td>
        <td class="val sign" colspan="2"></td>
      </tr>
      <tr>
        <td class="lbl" colspan="2">是否有参数表</td>
        <td class="val" colspan="4">${yesNoBoxes('')}</td>
        <td class="lbl" colspan="3">是否需要业务内勤请示总经理</td>
        <td class="val" colspan="3">${yesNoBoxes(form.need_gm_approval)}</td>
      </tr>
      <tr>
        <td class="lbl" colspan="1">设计思路</td>
        <td class="val-left idea" colspan="11">${cell(form.design_idea)}</td>
      </tr>
      <tr>
        <td class="lbl" colspan="1">计算过程</td>
        <td class="val-left idea" colspan="11">${cell(form.calc_process)}</td>
      </tr>
      <tr>
        <td class="lbl" colspan="1">专工意见</td>
        <td class="val-left opin" colspan="5">${cell(form.expert_opinion)}</td>
        <td class="lbl" colspan="1">室主任意见</td>
        <td class="val-left opin" colspan="5">${cell(form.office_opinion)}</td>
      </tr>
      <tr>
        <td class="lbl" colspan="1">审定意见</td>
        <td class="val-left opin" colspan="5">${cell(form.assistant_opinion)}</td>
        <td class="lbl" colspan="1">批准总工意见</td>
        <td class="val-left opin" colspan="5">${cell(form.chief_opinion)}</td>
      </tr>
      <tr>
        <td class="lbl" colspan="1">最后结果</td>
        <td class="val-left final" colspan="11">${cell(form.final_result)}</td>
      </tr>
    </table>
    ${approvalOpsHtml(steps)}
    <div class="foot">
      <span>打印时间：${escHtml(dayjs().format('YYYY-MM-DD HH:mm:ss'))}</span>
      <span>流水号：${escHtml(businessNo || '')}</span>
    </div>`
  return wrapDoc('安装图通知单及设计卡', body)
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
  const projectIds = collectIds(form.related_project)
  const contractIds = collectIds(form.contract_no)
  const [users, depts, projects, contracts] = await Promise.all([
    personIds.length ? getPersonLabelMap(personIds) : Promise.resolve({} as Record<string, string>),
    getDeptNameMap(),
    projectIds.length ? getProjectLabelMap(projectIds) : Promise.resolve({} as Record<string, string>),
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

export async function printSchemeInstance(opts: {
  formData: Record<string, unknown>
  fieldDefinitions: FieldDefinition[]
  businessNo?: string | null
  flowSteps?: WfFlowStep[] | null
}): Promise<void> {
  const form = opts.formData || {}
  const labels = await resolveLabels(form)
  const schemeType = String(form.scheme_type || '')
  const html = schemeType === 'install'
    ? buildInstallHtml({
      form, fields: opts.fieldDefinitions || [], labels,
      businessNo: opts.businessNo, steps: opts.flowSteps,
    })
    : buildRequisitionHtml({
      form, fields: opts.fieldDefinitions || [], labels,
      businessNo: opts.businessNo, steps: opts.flowSteps,
    })
  printHtml(html, { orientation: 'landscape' })
}
