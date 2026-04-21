import { useState, useEffect } from 'react'
import { Select, Button, Input, message, Popconfirm } from 'antd'
import { SaveOutlined, DeleteOutlined, StarOutlined } from '@ant-design/icons'
import client from '@/api/client'

interface SavedView {
  id: string; name: string; page: string; filters: Record<string, any>; is_default: boolean
}

interface Props {
  page: string
  currentFilters: Record<string, any>
  onApply: (filters: Record<string, any>) => void
}

export default function SavedViewSelect({ page, currentFilters, onApply }: Props) {
  const [views, setViews] = useState<SavedView[]>([])
  const [saveName, setSaveName] = useState('')
  const [saving, setSaving] = useState(false)
  const [showSave, setShowSave] = useState(false)

  const fetchViews = async () => {
    try {
      const res = await client.get('/api/v1/saved-views', { params: { page } }) as any
      setViews(res.data || [])
    } catch {
      // Non-critical — keep existing views
    }
  }

  useEffect(() => { fetchViews() }, [page])

  const handleSave = async () => {
    if (!saveName.trim()) { message.warning('请输入名称'); return }
    setSaving(true)
    try {
      await client.post('/api/v1/saved-views', { page, name: saveName.trim(), filters: currentFilters })
      message.success('视图已保存')
      setSaveName('')
      setShowSave(false)
      fetchViews()
    } catch {
      message.error('保存视图失败')
    } finally { setSaving(false) }
  }

  const handleDelete = async (id: string) => {
    try {
      await client.delete(`/api/v1/saved-views/${id}`)
      message.success('已删除')
      fetchViews()
    } catch {
      message.error('删除视图失败')
    }
  }

  return (
    <div className="flex items-center gap-2">
      {views.length > 0 && (
        <Select
          placeholder="快捷筛选"
          allowClear
          style={{ width: 150 }}
          onChange={(val) => {
            const v = views.find((v) => v.id === val)
            if (v) onApply(v.filters)
          }}
          options={views.map((v) => ({
            label: (
              <span className="flex items-center gap-1">
                {v.is_default && <StarOutlined className="text-amber-500" style={{ fontSize: 10 }} />}
                {v.name}
              </span>
            ),
            value: v.id,
          }))}
          dropdownRender={(menu) => (
            <div>
              {menu}
              <div className="border-t border-slate-100 p-1">
                {views.map((v) => (
                  <div key={v.id} className="flex items-center justify-between px-2 py-0.5">
                    <span className="text-sm text-slate-400 truncate">{v.name}</span>
                    <Popconfirm title="删除此视图？" onConfirm={() => handleDelete(v.id)} okText="确定" cancelText="取消">
                      <DeleteOutlined className="text-slate-300 hover:text-red-500 cursor-pointer" style={{ fontSize: 11 }} />
                    </Popconfirm>
                  </div>
                ))}
              </div>
            </div>
          )}
        />
      )}
      {showSave ? (
        <div className="flex items-center gap-1">
          <Input size="small" placeholder="视图名称" value={saveName}
            onChange={(e) => setSaveName(e.target.value)}
            onPressEnter={handleSave} style={{ width: 100 }} />
          <Button size="small" type="primary" loading={saving} onClick={handleSave}>保存</Button>
          <Button size="small" onClick={() => setShowSave(false)}>取消</Button>
        </div>
      ) : (
        <Button size="small" icon={<SaveOutlined />} onClick={() => setShowSave(true)}>保存视图</Button>
      )}
    </div>
  )
}
