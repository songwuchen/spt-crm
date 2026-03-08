import { useState, useRef, useEffect } from 'react'
import { Input, Select, message } from 'antd'

interface EditableCellProps {
  value: string | undefined
  onSave: (val: string) => Promise<void>
  type?: 'text' | 'select'
  options?: { label: string; value: string }[]
  placeholder?: string
}

export default function EditableCell({ value, onSave, type = 'text', options, placeholder }: EditableCellProps) {
  const [editing, setEditing] = useState(false)
  const [val, setVal] = useState(value || '')
  const [saving, setSaving] = useState(false)
  const inputRef = useRef<any>(null)

  useEffect(() => { setVal(value || '') }, [value])
  useEffect(() => { if (editing && inputRef.current) inputRef.current.focus() }, [editing])

  const handleSave = async () => {
    if (val === (value || '')) { setEditing(false); return }
    setSaving(true)
    try {
      await onSave(val)
      setEditing(false)
    } catch {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  if (!editing) {
    return (
      <span
        className="cursor-pointer hover:bg-slate-50 px-1 py-0.5 rounded transition-colors inline-block min-w-[40px] border border-transparent hover:border-slate-200"
        onClick={() => setEditing(true)}
        title="点击编辑"
      >
        {value || <span className="text-slate-300">-</span>}
      </span>
    )
  }

  if (type === 'select') {
    return (
      <Select
        size="small"
        value={val || undefined}
        onChange={(v) => { setVal(v); }}
        onBlur={() => { handleSave() }}
        options={options}
        placeholder={placeholder}
        style={{ width: '100%', minWidth: 80 }}
        autoFocus
        open
        onSelect={(v) => { setVal(v); setTimeout(() => handleSave(), 0) }}
      />
    )
  }

  return (
    <Input
      ref={inputRef}
      size="small"
      value={val}
      onChange={(e) => setVal(e.target.value)}
      onBlur={handleSave}
      onPressEnter={handleSave}
      disabled={saving}
      placeholder={placeholder}
      style={{ width: '100%', minWidth: 80 }}
    />
  )
}
