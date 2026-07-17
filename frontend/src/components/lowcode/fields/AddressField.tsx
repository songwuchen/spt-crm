// 地址字段 —— 复用 CRM 既有 RegionCascader(省/市/区县 + 行政区划编码)+ 可选详细地址行。
// 值形如 { province, city, district, regionCode, detail }，直接存 form_data JSONB。
import { Input } from 'antd'
import RegionCascader, { type RegionValue } from '@/components/RegionCascader'

export interface AddressValue extends RegionValue {
  detail?: string | null
}

export function formatAddress(v?: AddressValue | null): string {
  if (!v) return ''
  const region = [v.province, v.city, v.district].filter(Boolean).join(' ')
  return [region, v.detail].filter(Boolean).join(' ')
}

interface Props {
  value?: AddressValue | null
  onChange?: (v: AddressValue) => void
  readonly?: boolean
  placeholder?: string
  showDetail?: boolean // 是否显示详细地址输入行(字段 props.show_detail，默认 true)
}

export default function AddressField({ value, onChange, readonly, placeholder, showDetail = true }: Props) {
  const val: AddressValue = value || {}
  if (readonly) {
    const text = formatAddress(val)
    return <div style={{ paddingTop: 4 }}>{text || <span style={{ color: 'rgba(0,0,0,0.35)' }}>—</span>}</div>
  }
  return (
    <div className="space-y-2">
      <RegionCascader
        value={val}
        placeholder={placeholder || '选择省/市/区县'}
        onChange={(r) => onChange?.({ ...val, ...r })}
      />
      {showDetail && (
        <Input
          value={val.detail ?? ''}
          placeholder="详细地址(街道/门牌号)"
          onChange={(e) => onChange?.({ ...val, detail: e.target.value })}
        />
      )}
    </div>
  )
}
