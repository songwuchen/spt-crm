/** 基础资料表下拉（读本库 FormInstance：应用领域 / 应用物料 / 物料名称） */
import { useEffect, useState } from 'react'
import { Select } from 'antd'
import { lowcodeApi } from '@/api/lowcode'

export type BaseLookupFormCode = 'application_field' | 'application_material' | 'material_name'

/** 解析 options_source：`form:material_name:name` → material_name */
export function parseFormOptionsSource(source?: string | null): BaseLookupFormCode | null {
  if (!source || !source.startsWith('form:')) return null
  const parts = source.split(':')
  const code = parts[1]?.trim()
  if (code === 'application_field' || code === 'application_material' || code === 'material_name') {
    return code
  }
  return null
}

export default function BaseFormLookupField({
  formCode,
  value,
  onChange,
  multiple = false,
  readonly = false,
  placeholder = '请选择',
}: {
  formCode: BaseLookupFormCode
  value?: unknown
  onChange?: (v: unknown) => void
  multiple?: boolean
  readonly?: boolean
  placeholder?: string
}) {
  const [options, setOptions] = useState<{ label: string; value: string }[]>([])
  const [loading, setLoading] = useState(false)

  const load = async (kw?: string) => {
    setLoading(true)
    try {
      const r = await lowcodeApi.baseLookups({
        type: formCode,
        keyword: kw || undefined,
        limit: 200,
      })
      const items = r.data || []
      setOptions(items.map((it) => ({ value: it.name, label: it.label || it.name })))
    } catch {
      /* ignore */
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formCode])

  // 回显：已有值不在当前页选项中时注入
  useEffect(() => {
    const inject = (vals: string[]) => {
      if (!vals.length) return
      setOptions((prev) => {
        const missing = vals.filter((v) => v && !prev.some((o) => o.value === v))
        if (!missing.length) return prev
        return [...missing.map((v) => ({ value: v, label: v })), ...prev]
      })
    }
    if (multiple) {
      const arr = Array.isArray(value) ? value.map(String) : []
      inject(arr)
    } else {
      const v = value != null && value !== '' ? String(value) : ''
      if (v) inject([v])
    }
  }, [value, multiple])

  if (readonly) {
    const text = multiple
      ? (Array.isArray(value) ? value.map(String).join('，') : '')
      : (value != null && value !== '' ? String(value) : '')
    return <span>{text || '—'}</span>
  }

  if (multiple) {
    const arr = Array.isArray(value) ? (value as string[]) : []
    return (
      <Select
        style={{ width: '100%', minWidth: 160 }}
        mode="multiple"
        allowClear
        showSearch
        filterOption={false}
        placeholder={placeholder}
        value={arr}
        loading={loading}
        options={options}
        onSearch={(kw) => void load(kw)}
        onDropdownVisibleChange={(open) => { if (open && options.length === 0) void load() }}
        onChange={(v) => onChange?.(v)}
        maxTagCount="responsive"
      />
    )
  }

  return (
    <Select
      style={{ width: '100%' }}
      allowClear
      showSearch
      filterOption={false}
      placeholder={placeholder}
      value={(value as string) || undefined}
      loading={loading}
      options={options}
      onSearch={(kw) => void load(kw)}
      onDropdownVisibleChange={(open) => { if (open && options.length === 0) void load() }}
      onChange={(v) => onChange?.((v as string | undefined) || undefined)}
    />
  )
}
