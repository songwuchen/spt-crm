import { Descriptions, Table, Tag, Collapse } from 'antd'

/**
 * DataView — 把任意 JSON（迁移自简道云的子表单、AI 结果、审计明细、配置等）
 * 渲染成人类可读的结构，而不是直接 JSON.stringify 甩给用户。
 *
 * - 对象        → Descriptions（中文标签）
 * - 对象数组    → Table（列=字段并集，表头中文化）
 * - 标量数组    → Tag 列表
 * - 标量        → 格式化文本（布尔→是/否、ISO 日期本地化、数字千分位）
 * - 内部字段    → 自动隐藏（_id / uuid / mongoId / 空值 / 未映射的 _widget_*）
 * - 兜底        → 可折叠的「原始数据」
 */

// ---- 字段中文标签字典 ----------------------------------------------------

// 简道云合同子表单（合同明细 / 收款计划）字段 → 中文（依据真实数据三角验证）
export const JDY_TERM_LABELS: Record<string, string> = {
  // 合同明细
  _widget_1561431500162: '类别',
  _widget_1561431500376: '名称',
  _widget_1561431500392: '规格型号',
  _widget_1561431500419: '单位',
  _widget_1561431500458: '数量',
  _widget_1561431500490: '单价',
  _widget_1561431500514: '金额',
  _widget_1561431500595: '备注',
  _widget_1565223122750: '技术标准',
  _widget_1621411268784: '是否新增',
  // 收款计划
  _widget_1561431500818: '款项性质',
  _widget_1561431500832: '付款比例',
  _widget_1561431500855: '金额',
  _widget_1661242797064: '到期日期',
  _widget_1665380027757: '说明',
  _widget_1665380028160: '是否提醒',
}

// 常见英文/拼音 key → 中文（AI 结果、风险、审计、配置等）
const COMMON_LABELS: Record<string, string> = {
  category: '类别', description: '描述', desc: '描述', severity: '严重程度',
  level: '等级', risk_level: '风险等级', mitigation: '缓解措施', risk: '风险',
  risks: '风险项', clause: '条款', clauses: '条款', detail: '明细', details: '明细',
  overall_assessment: '综合评估', overall_comment: '综合评价', comment: '评价',
  quality_score: '质量分', score: '评分', confidence: '置信度', impact: '影响',
  name: '名称', title: '标题', type: '类型', status: '状态', model: '模型',
  amount: '金额', price: '价格', quantity: '数量', qty: '数量', unit: '单位',
  total: '合计', count: '数量', date: '日期', time: '时间', remark: '备注',
  note: '备注', reason: '原因', summary: '摘要', suggestion: '建议',
  suggestions: '建议', recommendation: '建议', recommendations: '建议',
  action: '操作', source: '来源', evidence: '证据', field: '字段',
  old: '原值', new: '新值', value: '值', label: '标签', key: '键',
  rate: '比例', period: '周期', user_name: '操作人', created_at: '创建时间',
}

export function humanizeLabel(key: string): string {
  if (JDY_TERM_LABELS[key]) return JDY_TERM_LABELS[key]
  if (COMMON_LABELS[key]) return COMMON_LABELS[key]
  if (/^_widget_/.test(key)) return key // 未映射的简道云字段（极少，兜底原样）
  return key
}

// ---- 值的判定与格式化 ----------------------------------------------------

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const MONGO_RE = /^[0-9a-f]{24}$/i
const ISO_DT_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/

export function isInternalKey(key: string): boolean {
  return key === '_id' || key === '_state' || key.startsWith('__')
}

export function isInternalValue(v: unknown): boolean {
  if (v == null || v === '') return true
  if (typeof v === 'string' && (UUID_RE.test(v) || MONGO_RE.test(v))) return true
  return false
}

/** 金额：数字 → ¥千分位；脱敏串(***)/非数字 → 原样；空 → - */
export function formatMoney(v: unknown): string {
  if (v == null || v === '') return '-'
  const s = String(v).trim()
  const cleaned = s.replace(/,/g, '')
  const n = Number(cleaned)
  if (cleaned !== '' && Number.isFinite(n)) {
    return '¥' + n.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
  }
  return s
}

export function formatScalar(v: unknown): string {
  if (v == null || v === '') return '-'
  if (typeof v === 'boolean') return v ? '是' : '否'
  if (typeof v === 'number') return v.toLocaleString('zh-CN', { maximumFractionDigits: 4 })
  const s = String(v)
  if (ISO_DT_RE.test(s)) {
    const d = new Date(s)
    if (!isNaN(d.getTime())) {
      const hasTime = !/T00:00/.test(s)
      return hasTime
        ? d.toLocaleString('zh-CN', { hour12: false }).replace(/:\d{2}$/, '')
        : d.toLocaleDateString('zh-CN')
    }
  }
  return s
}

// ---- 递归渲染组件 --------------------------------------------------------

interface Props {
  value: unknown
  depth?: number
  /** 标量数组是否用 Tag 渲染（默认 true） */
  tags?: boolean
}

export default function DataView({ value, depth = 0, tags = true }: Props): React.ReactElement {
  if (value == null || value === '') return <span className="text-slate-400">-</span>

  // 标量
  if (typeof value !== 'object') {
    return <span className="text-slate-700 whitespace-pre-wrap break-words">{formatScalar(value)}</span>
  }

  // 防御：递归过深则折叠原始数据
  if (depth > 4) return <RawJson value={value} />

  // 数组
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-slate-400">-</span>
    const allObjects = value.every((it) => it && typeof it === 'object' && !Array.isArray(it))
    if (allObjects) {
      return <ObjectArrayTable rows={value as Record<string, unknown>[]} depth={depth} />
    }
    // 标量/混合数组
    return (
      <div className="flex flex-wrap gap-1">
        {value.map((it, i) =>
          it && typeof it === 'object' ? (
            <div key={i} className="w-full"><DataView value={it} depth={depth + 1} /></div>
          ) : tags ? (
            <Tag key={i} className="m-0">{formatScalar(it)}</Tag>
          ) : (
            <span key={i} className="text-slate-700">{formatScalar(it)}{i < value.length - 1 ? '、' : ''}</span>
          )
        )}
      </div>
    )
  }

  // 对象
  const entries = Object.entries(value as Record<string, unknown>).filter(
    ([k, v]) => !isInternalKey(k) && !isInternalValue(v)
  )
  if (entries.length === 0) return <span className="text-slate-400">-</span>

  return (
    <Descriptions size="small" column={1} bordered className="bg-white">
      {entries.map(([k, v]) => (
        <Descriptions.Item key={k} label={humanizeLabel(k)}>
          <DataView value={v} depth={depth + 1} />
        </Descriptions.Item>
      ))}
    </Descriptions>
  )
}

function ObjectArrayTable({ rows, depth }: { rows: Record<string, unknown>[]; depth: number }) {
  // 列 = 各行 key 并集，去掉内部 key / 全部为内部值的列，保持首次出现顺序
  const keys: string[] = []
  for (const row of rows) {
    for (const k of Object.keys(row)) {
      if (!isInternalKey(k) && !keys.includes(k)) keys.push(k)
    }
  }
  const cols = keys
    .filter((k) => rows.some((r) => !isInternalValue(r[k])))
    .map((k) => ({
      title: humanizeLabel(k),
      dataIndex: k,
      key: k,
      render: (v: unknown) => <DataView value={v} depth={depth + 1} />,
    }))

  const keyMap = new WeakMap<object, string>()
  rows.forEach((r, i) => keyMap.set(r, String(r._id ?? r.id ?? i)))

  return (
    <Table
      size="small"
      rowKey={(r) => keyMap.get(r as object) ?? '0'}
      dataSource={rows}
      columns={cols}
      pagination={false}
      scroll={{ x: 'max-content' }}
    />
  )
}

function RawJson({ value }: { value: unknown }) {
  return (
    <Collapse
      ghost
      size="small"
      items={[
        {
          key: 'raw',
          label: <span className="text-xs text-slate-400">原始数据</span>,
          children: (
            <pre className="text-xs text-slate-500 whitespace-pre-wrap break-words max-h-60 overflow-auto m-0">
              {JSON.stringify(value, null, 2)}
            </pre>
          ),
        },
      ]}
    />
  )
}
