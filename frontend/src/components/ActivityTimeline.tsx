import { useState, useEffect } from 'react'
import { Button, Modal, Input, Select, message } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { activityApi } from '@/api/activity'
import type { ActivityItem } from '@/api/types'

const { TextArea } = Input

const typeConfig: Record<string, { label: string; icon: string; color: string }> = {
  call: { label: '电话', icon: 'call', color: '#3b82f6' },
  visit: { label: '拜访', icon: 'directions_walk', color: '#10b981' },
  meeting: { label: '会议', icon: 'groups', color: '#8b5cf6' },
  email: { label: '邮件', icon: 'mail', color: '#f59e0b' },
  note: { label: '备注', icon: 'edit_note', color: '#64748b' },
  stage_change: { label: '阶段变更', icon: 'swap_horiz', color: '#ef4444' },
  system: { label: '系统', icon: 'info', color: '#94a3b8' },
}

interface Props {
  bizType: string
  bizId: string
}

export default function ActivityTimeline({ bizType, bizId }: Props) {
  const [items, setItems] = useState<ActivityItem[]>([])
  const [modal, setModal] = useState(false)
  const [form, setForm] = useState({ activity_type: 'note', subject: '', content: '', contact_name: '' })

  const fetch = () => {
    activityApi.list(bizType, bizId).then((r) => setItems(r.data))
  }
  useEffect(() => { fetch() }, [bizType, bizId])

  const handleCreate = async () => {
    await activityApi.create({ biz_type: bizType, biz_id: bizId, ...form })
    message.success('记录已添加')
    setModal(false)
    setForm({ activity_type: 'note', subject: '', content: '', contact_name: '' })
    fetch()
  }

  return (
    <div>
      <div className="flex justify-end mb-4">
        <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => setModal(true)}>
          添加记录
        </Button>
      </div>

      {items.length === 0 ? (
        <div className="text-center py-12 text-slate-400 text-sm">暂无互动记录</div>
      ) : (
        <div className="relative pl-8">
          {/* Timeline line */}
          <div className="absolute left-[13px] top-2 bottom-2 w-px bg-slate-200" />

          {items.map((item) => {
            const cfg = typeConfig[item.activity_type] || typeConfig.note
            return (
              <div key={item.id} className="relative mb-6 last:mb-0">
                {/* Dot */}
                <div
                  className="absolute -left-8 top-1 w-[26px] h-[26px] rounded-full flex items-center justify-center border-2 border-white shadow-sm"
                  style={{ background: cfg.color }}
                >
                  <span className="material-symbols-outlined text-white" style={{ fontSize: 14 }}>{cfg.icon}</span>
                </div>

                {/* Card */}
                <div className="bg-white rounded-lg border border-slate-200 p-4 shadow-sm hover:shadow-md transition-shadow">
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <span
                        className="inline-flex px-2 py-0.5 rounded text-[10px] font-bold uppercase text-white"
                        style={{ background: cfg.color }}
                      >
                        {cfg.label}
                      </span>
                      {item.subject && (
                        <span className="text-sm font-bold text-slate-800">{item.subject}</span>
                      )}
                    </div>
                    <div className="flex items-center gap-3 text-xs text-slate-400">
                      {item.contact_name && (
                        <span className="flex items-center gap-1">
                          <span className="material-symbols-outlined text-xs">person</span>
                          {item.contact_name}
                        </span>
                      )}
                      <span>{item.created_at ? new Date(item.created_at).toLocaleString('zh-CN') : ''}</span>
                    </div>
                  </div>
                  {item.content && (
                    <p className="text-sm text-slate-600 mt-2 whitespace-pre-wrap leading-relaxed">{item.content}</p>
                  )}
                  <div className="mt-2 text-xs text-slate-400">
                    {item.created_by_name || '系统'}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      <Modal title="添加互动记录" open={modal} onOk={handleCreate} onCancel={() => setModal(false)}>
        <div className="space-y-4 py-2">
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">类型</label>
            <Select className="w-full" value={form.activity_type} onChange={(v) => setForm({ ...form, activity_type: v })}
              options={Object.entries(typeConfig).filter(([k]) => k !== 'stage_change' && k !== 'system').map(([k, v]) => ({ value: k, label: v.label }))} />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">主题</label>
            <Input value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} placeholder="简要主题..." />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">联系人</label>
            <Input value={form.contact_name} onChange={(e) => setForm({ ...form, contact_name: e.target.value })} placeholder="联系人姓名..." />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">内容</label>
            <TextArea rows={4} value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} placeholder="详细内容..." />
          </div>
        </div>
      </Modal>
    </div>
  )
}
