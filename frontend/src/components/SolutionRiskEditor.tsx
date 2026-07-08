import { Button, Input, Select } from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'

const { TextArea } = Input

/**
 * Structured editor for a solution version's 风险清单 (risk_list_json).
 *
 * Saved as an array of { severity, description, mitigation } — the same shape
 * SolutionDetail renders in read mode — replacing the old raw-JSON textarea.
 */

export interface RiskRow {
  severity: string // 'H' | 'M' | 'L'
  description: string
  mitigation: string
}

export const SEVERITY_OPTIONS = [
  { value: 'H', label: '高' },
  { value: 'M', label: '中' },
  { value: 'L', label: '低' },
]

const SEVERITY_MAP: Record<string, string> = {
  H: 'H', M: 'M', L: 'L',
  HIGH: 'H', MEDIUM: 'M', MED: 'M', LOW: 'L',
  高: 'H', 中: 'M', 低: 'L',
}

const normalizeSeverity = (v: unknown): string => {
  const key = String(v ?? '').trim().toUpperCase()
  return SEVERITY_MAP[key] || SEVERITY_MAP[String(v ?? '').trim()] || 'M'
}

/** Best-effort coercion of arbitrary stored risk_list_json into RiskRow[]. */
export function normalizeRisks(value: unknown): RiskRow[] {
  let arr: unknown[] = []
  if (Array.isArray(value)) {
    arr = value
  } else if (value && typeof value === 'object') {
    const obj = value as Record<string, unknown>
    const wrapped = ['risks', 'items', 'list', 'data'].map((k) => obj[k]).find(Array.isArray)
    if (wrapped) arr = wrapped as unknown[]
  }
  return arr.map((r) => {
    const o = (r && typeof r === 'object' ? r : {}) as Record<string, unknown>
    return {
      severity: normalizeSeverity(o.severity ?? o.level),
      description: String(o.description ?? o.name ?? o.title ?? o.risk ?? ''),
      mitigation: o.mitigation != null ? String(o.mitigation) : '',
    }
  })
}

/** Drop empty risks; return the array to persist, or null when there is nothing. */
export function serializeRisks(risks: RiskRow[]): Array<Record<string, string>> | null {
  const cleaned = risks
    .filter((r) => r.description.trim() || r.mitigation.trim())
    .map((r) => {
      const out: Record<string, string> = { severity: r.severity || 'M', description: r.description.trim() }
      if (r.mitigation.trim()) out.mitigation = r.mitigation.trim()
      return out
    })
  return cleaned.length ? cleaned : null
}

interface Props {
  value: RiskRow[]
  onChange: (risks: RiskRow[]) => void
}

export default function SolutionRiskEditor({ value, onChange }: Props) {
  const risks = Array.isArray(value) ? value : []

  const update = (idx: number, patch: Partial<RiskRow>) =>
    onChange(risks.map((r, i) => (i === idx ? { ...r, ...patch } : r)))

  const remove = (idx: number) => onChange(risks.filter((_, i) => i !== idx))

  const add = () => onChange([...risks, { severity: 'M', description: '', mitigation: '' }])

  return (
    <div className="space-y-3">
      {risks.length === 0 && (
        <div className="text-center text-sm text-slate-400 py-6 bg-slate-50 rounded-lg border border-dashed border-slate-200">
          暂无风险项，点击下方“添加风险”开始填写。
        </div>
      )}

      {risks.map((risk, idx) => (
        <div key={idx} className="border border-slate-200 rounded-lg p-3 bg-white">
          <div className="flex items-center gap-2 mb-2">
            <span className="px-2 py-0.5 rounded text-[12px] font-bold bg-primary/10 text-primary">风险 {idx + 1}</span>
            <Select
              size="small"
              value={risk.severity}
              style={{ width: 90 }}
              onChange={(v) => update(idx, { severity: v })}
              options={SEVERITY_OPTIONS}
            />
            <div className="flex-1" />
            <Button danger size="small" type="text" icon={<DeleteOutlined />} onClick={() => remove(idx)} />
          </div>
          <div className="space-y-2">
            <div>
              <label className="text-[13px] font-bold text-slate-500 uppercase tracking-wider mb-1 block">风险描述 *</label>
              <Input
                value={risk.description}
                placeholder="如：交付排期受供货周期影响存在延期可能"
                onChange={(e) => update(idx, { description: e.target.value })}
              />
            </div>
            <div>
              <label className="text-[13px] font-bold text-slate-500 uppercase tracking-wider mb-1 block">缓解措施（选填）</label>
              <TextArea
                rows={2}
                value={risk.mitigation}
                placeholder="如：提前锁定关键物料库存并签订供货协议"
                onChange={(e) => update(idx, { mitigation: e.target.value })}
              />
            </div>
          </div>
        </div>
      ))}

      <Button block icon={<PlusOutlined />} type="dashed" onClick={add}>
        添加风险
      </Button>
    </div>
  )
}
