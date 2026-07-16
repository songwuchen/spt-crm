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
  code: string
  children?: CascaderOption[]
}

export interface RegionValue {
  province?: string | null
  city?: string | null
  district?: string | null
  /** 最深选中层级的行政区划编码(GB/T 2260)，用于层级前缀过滤与稳定标识 */
  regionCode?: string | null
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
    code: n.code,
    children: n.children ? toCascaderOptions(n.children) : undefined,
  }))
}

// 以名称作为 value（各层级名称在数据集中唯一），保证持久化值可读、回填时无需 code->name 反查；
// 同时把行政区划 code 挂在 option 上，onChange 时从 selectedOptions 读取叶子 code 一并回传。
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
      onChange={(v, selectedOptions) => {
        const arr = (v as string[] | undefined) || []
        const opts = (selectedOptions as CascaderOption[] | undefined) || []
        const leaf = opts.length > 0 ? opts[opts.length - 1] : undefined
        onChange?.({
          province: arr[0] || null,
          city: arr[1] || null,
          district: arr[2] || null,
          regionCode: leaf?.code || null,
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
