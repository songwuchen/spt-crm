import { useState, useEffect, useCallback } from 'react'
import { Select, Button, Input, Radio, Checkbox, message, Popconfirm, Modal } from 'antd'
import { SaveOutlined, DeleteOutlined, StarFilled, StarOutlined } from '@ant-design/icons'
import client from '@/api/client'
import type { ListViewController, ListViewPayload } from '@/hooks/useListView'

interface SavedView {
  id: string
  name: string
  filters: { advanced: unknown } | Record<string, unknown>
  columns: { hidden: string[]; order: string[] } | null
  sort_by: string | null
  sort_order: string | null
  visibility: string
  is_default: boolean
  is_owner: boolean
}

interface Props {
  page: string                 // 资源 key，用作视图归类
  view: ListViewController
  onApplied: () => void        // 应用视图后触发列表刷新
}

/** 保存视图：把「筛选 + 列 + 排序」存为命名视图，支持私有/租户共享、默认视图、应用/删除。 */
export default function ViewManager({ page, view, onApplied }: Props) {
  const [views, setViews] = useState<SavedView[]>([])
  const [selected, setSelected] = useState<string | undefined>(undefined)
  const [saveOpen, setSaveOpen] = useState(false)
  const [name, setName] = useState('')
  const [visibility, setVisibility] = useState<'private' | 'tenant'>('private')
  const [asDefault, setAsDefault] = useState(false)
  const [saving, setSaving] = useState(false)
  const [autoApplied, setAutoApplied] = useState(false)

  const fetchViews = useCallback(async () => {
    try {
      const res = await client.get('/api/v1/saved-views', { params: { page } }) as unknown as { data: SavedView[] }
      setViews(res.data || [])
      return res.data || []
    } catch {
      return []
    }
  }, [page])

  // 首次加载并自动应用默认视图
  useEffect(() => {
    fetchViews().then((list) => {
      if (autoApplied) return
      const def = list.find((v) => v.is_default)
      if (def) {
        setSelected(def.id)
        view.applyView(def)
        onApplied()
      }
      setAutoApplied(true)
    })
  }, [fetchViews]) // eslint-disable-line react-hooks/exhaustive-deps

  const apply = (id: string | undefined) => {
    setSelected(id)
    if (!id) return
    const v = views.find((x) => x.id === id)
    if (v) { view.applyView(v); onApplied() }
  }

  const handleSave = async () => {
    if (!name.trim()) { message.warning('请输入视图名称'); return }
    setSaving(true)
    try {
      const payload: ListViewPayload = view.currentPayload()
      await client.post('/api/v1/saved-views', {
        page, name: name.trim(),
        filters: payload.filters, columns: payload.columns,
        sort_by: payload.sort_by, sort_order: payload.sort_order,
        visibility, is_default: asDefault,
      })
      message.success('视图已保存')
      setSaveOpen(false); setName(''); setAsDefault(false); setVisibility('private')
      fetchViews()
    } catch {
      message.error('保存视图失败')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await client.delete(`/api/v1/saved-views/${id}`)
      message.success('已删除')
      if (selected === id) setSelected(undefined)
      fetchViews()
    } catch {
      message.error('删除失败')
    }
  }

  const setDefault = async (id: string) => {
    try {
      await client.put(`/api/v1/saved-views/${id}`, { is_default: true })
      fetchViews()
    } catch {
      message.error('操作失败')
    }
  }

  return (
    <div className="flex items-center gap-2">
      <Select
        placeholder="保存的视图" allowClear value={selected} style={{ width: 160 }}
        onChange={apply}
        options={views.map((v) => ({
          value: v.id,
          label: (
            <span className="flex items-center gap-1">
              {v.is_default && <StarFilled className="text-amber-500" style={{ fontSize: 10 }} />}
              {v.name}
              {v.visibility === 'tenant' && <span className="text-[12px] text-slate-400">(共享)</span>}
            </span>
          ),
        }))}
        dropdownRender={(menu) => (
          <div>
            {menu}
            {views.length > 0 && (
              <div className="border-t border-slate-100 p-1 max-h-40 overflow-auto">
                {views.map((v) => (
                  <div key={v.id} className="flex items-center justify-between px-2 py-0.5 gap-2">
                    <span className="text-xs text-slate-400 truncate flex-1">{v.name}</span>
                    {v.is_owner && (
                      <>
                        <span onClick={() => setDefault(v.id)} title="设为默认">
                          {v.is_default
                            ? <StarFilled className="text-amber-500 cursor-pointer" style={{ fontSize: 11 }} />
                            : <StarOutlined className="text-slate-300 hover:text-amber-500 cursor-pointer" style={{ fontSize: 11 }} />}
                        </span>
                        <Popconfirm title="删除此视图？" onConfirm={() => handleDelete(v.id)} okText="确定" cancelText="取消">
                          <DeleteOutlined className="text-slate-300 hover:text-red-500 cursor-pointer" style={{ fontSize: 11 }} />
                        </Popconfirm>
                      </>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      />
      <Button icon={<SaveOutlined />} onClick={() => setSaveOpen(true)}>保存视图</Button>

      <Modal title="保存为视图" open={saveOpen} onOk={handleSave} confirmLoading={saving} onCancel={() => setSaveOpen(false)} okText="保存" cancelText="取消" width={420}>
        <div className="space-y-4 py-2">
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">视图名称</label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="如：我的高价值客户" onPressEnter={handleSave} />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">可见范围</label>
            <Radio.Group value={visibility} onChange={(e) => setVisibility(e.target.value)}
              options={[{ label: '仅自己', value: 'private' }, { label: '本租户共享', value: 'tenant' }]} />
          </div>
          <Checkbox checked={asDefault} onChange={(e) => setAsDefault(e.target.checked)}>设为默认视图（打开列表时自动应用）</Checkbox>
          <p className="text-[12px] text-slate-400">将保存当前的高级筛选条件、列显隐与顺序、排序。</p>
        </div>
      </Modal>
    </div>
  )
}
