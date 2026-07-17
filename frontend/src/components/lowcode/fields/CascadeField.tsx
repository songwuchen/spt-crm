// 级联选择字段 —— 多级联动下拉,选项树由字段配置 props.cascade_options 提供。
// 值为路径数组 string[](各层级 value)。
import { Cascader } from 'antd'

export interface CascadeOption {
  label: string
  value: string
  children?: CascadeOption[]
}

// 按路径解析出各层级 label(用于只读展示)。找不到的层级回退显示原始 value。
export function cascadeLabels(options: CascadeOption[], path: string[]): string[] {
  const labels: string[] = []
  let level: CascadeOption[] = options
  for (const v of path) {
    const node = level.find((o) => o.value === v)
    if (!node) { labels.push(String(v)); level = []; continue }
    labels.push(node.label)
    level = node.children || []
  }
  return labels
}

interface Props {
  value?: string[] | null
  onChange?: (v: string[]) => void
  options?: CascadeOption[]
  readonly?: boolean
  placeholder?: string
  changeOnSelect?: boolean
}

export default function CascadeField({ value, onChange, options = [], readonly, placeholder, changeOnSelect = true }: Props) {
  const path = Array.isArray(value) ? value : []
  if (readonly) {
    const text = cascadeLabels(options, path).join(' / ')
    return <div style={{ paddingTop: 4 }}>{text || <span style={{ color: 'rgba(0,0,0,0.35)' }}>—</span>}</div>
  }
  return (
    <Cascader
      style={{ width: '100%' }}
      options={options as never}
      value={path}
      placeholder={placeholder || '请选择'}
      onChange={(v) => onChange?.((v as string[]) || [])}
      changeOnSelect={changeOnSelect}
      showSearch={{ filter: (input, opts) => opts.some((o) => String(o.label).toLowerCase().includes(input.toLowerCase())) }}
    />
  )
}
