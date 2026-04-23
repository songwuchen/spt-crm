import { useMemo } from 'react'
import { Cascader } from 'antd'
import regionsData from '@/data/china-regions.json'

interface RegionNode {
  code: string
  name: string
  children?: RegionNode[]
}

interface CascaderOption {
  value: string
  label: string
  children?: CascaderOption[]
}

export interface RegionValue {
  province?: string | null
  city?: string | null
  district?: string | null
}

interface Props {
  value?: RegionValue
  onChange?: (v: RegionValue) => void
  placeholder?: string
  disabled?: boolean
  allowClear?: boolean
}

function toCascaderOptions(nodes: RegionNode[]): CascaderOption[] {
  return nodes.map((n) => ({
    value: n.name,
    label: n.name,
    children: n.children ? toCascaderOptions(n.children) : undefined,
  }))
}

// Names are unique at each level across the dataset, so we use name-as-value. This
// keeps what we persist human-readable and avoids needing a code->name lookup on load.
let cachedOptions: CascaderOption[] | null = null
function getOptions(): CascaderOption[] {
  if (!cachedOptions) {
    cachedOptions = toCascaderOptions(regionsData as RegionNode[])
  }
  return cachedOptions
}

export default function RegionCascader({ value, onChange, placeholder = '选择省/市/区县', disabled, allowClear = true }: Props) {
  const options = useMemo(getOptions, [])

  const cascaderValue = useMemo(() => {
    const parts: string[] = []
    if (value?.province) parts.push(value.province)
    if (value?.city) parts.push(value.city)
    if (value?.district) parts.push(value.district)
    return parts.length > 0 ? parts : undefined
  }, [value?.province, value?.city, value?.district])

  return (
    <Cascader
      options={options}
      value={cascaderValue}
      onChange={(v) => {
        const arr = (v as string[] | undefined) || []
        onChange?.({
          province: arr[0] || null,
          city: arr[1] || null,
          district: arr[2] || null,
        })
      }}
      placeholder={placeholder}
      disabled={disabled}
      allowClear={allowClear}
      showSearch={{
        filter: (input, path) => path.some((o) => (o.label as string)?.toLowerCase().includes(input.toLowerCase())),
      }}
      changeOnSelect
      style={{ width: '100%' }}
    />
  )
}
