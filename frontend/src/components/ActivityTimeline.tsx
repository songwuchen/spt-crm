import { useState, useEffect } from 'react'
import { Button, Modal, Input, Select, Spin, DatePicker, Upload, message } from 'antd'
import { PlusOutlined, UploadOutlined } from '@ant-design/icons'
import { activityApi } from '@/api/activity'
import { aiApi } from '@/api/ai'
import { contactApi } from '@/api/contact'
import { userApi } from '@/api/user'
import type { ActivityItem, Contact } from '@/api/types'
import AttachmentPanel from './AttachmentPanel'
import { useRemoteSelect } from '@/hooks/useRemoteSelect'
import VoiceInput from '@/components/VoiceInput'
import dayjs from 'dayjs'

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
  customerId?: string
}

export default function ActivityTimeline({ bizType, bizId, customerId }: Props) {
  const [items, setItems] = useState<ActivityItem[]>([])
  const [modal, setModal] = useState(false)
  const [form, setForm] = useState({
    activity_type: 'note', subject: '', content: '', contact_id: '', contact_name: '', next_follow_date: '',
  })
  const [mentionIds, setMentionIds] = useState<string[]>([])
  const mentionSelect = useRemoteSelect(async (kw) => {
    const r = await userApi.list({ pageNo: 1, pageSize: 50, keyword: kw })
    return (r.data?.items || []).map((u: any) => ({ label: u.real_name || u.username, value: u.id }))
  })
  const [contacts, setContacts] = useState<Contact[]>([])
  const [aiSummary, setAiSummary] = useState<{ summary: string; key_points: string[]; suggestion: string } | null>(null)
  const [summaryLoading, setSummaryLoading] = useState(false)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const fetchActivities = () => {
    activityApi.list(bizType, bizId).then((r) => setItems(r.data))
  }
  useEffect(() => { fetchActivities() }, [bizType, bizId])

  // Load contacts for customer-related entities
  useEffect(() => {
    const cid = customerId
    if (cid) {
      contactApi.list(cid).then((r) => setContacts(r.data || [])).catch(() => {})
    }
  }, [customerId])

  const handleCreate = async () => {
    const mentions = mentionIds.map((uid) => {
      const opt = mentionSelect.options.find((o) => o.value === uid)
      return { user_id: uid, user_name: opt?.label || '' }
    })
    try {
      await activityApi.create({
        biz_type: bizType, biz_id: bizId,
        activity_type: form.activity_type,
        subject: form.subject || undefined,
        content: form.content || undefined,
        contact_id: form.contact_id || undefined,
        contact_name: form.contact_name || undefined,
        next_follow_date: form.next_follow_date || undefined,
        mentions_json: mentions.length > 0 ? mentions : undefined,
      })
      message.success('记录已添加')
      setModal(false)
      setForm({ activity_type: 'note', subject: '', content: '', contact_id: '', contact_name: '', next_follow_date: '' })
      setMentionIds([])
      fetchActivities()
    } catch {
      message.error('添加记录失败')
    }
  }

  const handleContactSelect = (contactId: string) => {
    const c = contacts.find((x) => x.id === contactId)
    setForm({ ...form, contact_id: contactId, contact_name: c?.name || '' })
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <Button size="small" onClick={async () => {
          setSummaryLoading(true)
          setAiSummary(null)
          try {
            const res = await aiApi.summarizeActivities(bizType, bizId)
            setAiSummary(res.data)
          } catch { message.error('AI 总结失败') }
          finally { setSummaryLoading(false) }
        }}>
          <span className="material-symbols-outlined text-sm mr-1">auto_awesome</span>
          AI 总结
        </Button>
        <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => setModal(true)}>
          添加记录
        </Button>
      </div>

      {/* AI Summary Panel */}
      {summaryLoading && <div className="flex justify-center py-4 mb-4"><Spin tip="AI 分析中..." /></div>}
      {aiSummary && (
        <div className="mb-6 bg-gradient-to-br from-indigo-50 to-blue-50 rounded-xl border border-indigo-100 p-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="material-symbols-outlined text-indigo-500" style={{ fontSize: 18 }}>auto_awesome</span>
            <span className="text-xs font-bold uppercase tracking-wider text-indigo-500">AI 智能总结</span>
          </div>
          <p className="text-sm text-slate-700 mb-3">{aiSummary.summary}</p>
          {aiSummary.key_points?.length > 0 && (
            <div className="mb-3">
              <div className="text-[10px] font-bold uppercase text-indigo-400 mb-1">关键要点</div>
              <ul className="space-y-1">
                {aiSummary.key_points.map((p, i) => (
                  <li key={i} className="text-xs text-slate-600 flex items-start gap-2">
                    <span className="text-indigo-400 mt-0.5">•</span>{p}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {aiSummary.suggestion && (
            <div className="bg-white/60 rounded-lg px-3 py-2 text-xs text-slate-600">
              <span className="font-bold text-indigo-500">建议: </span>{aiSummary.suggestion}
            </div>
          )}
        </div>
      )}

      {items.length === 0 ? (
        <div className="text-center py-12 text-slate-400 text-sm">暂无互动记录</div>
      ) : (
        <div className="relative pl-8">
          {/* Timeline line */}
          <div className="absolute left-[13px] top-2 bottom-2 w-px bg-slate-200" />

          {items.map((item) => {
            const cfg = typeConfig[item.activity_type] || typeConfig.note
            const isExpanded = expandedId === item.id
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
                  <div className="mt-2 flex items-center justify-between">
                    <div className="flex items-center gap-3 flex-wrap">
                      <span className="text-xs text-slate-400">{item.created_by_name || '系统'}</span>
                      {(item as any).mentions_json?.length > 0 && (
                        <span className="inline-flex items-center gap-1 text-[10px] text-blue-500">
                          <span className="material-symbols-outlined" style={{ fontSize: 12 }}>alternate_email</span>
                          {(item as any).mentions_json.map((m: any) => m.user_name).join(', ')}
                        </span>
                      )}
                      {item.next_follow_date && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-amber-50 border border-amber-100 text-[10px] font-bold text-amber-600">
                          <span className="material-symbols-outlined" style={{ fontSize: 12 }}>event</span>
                          下次跟进: {item.next_follow_date}
                        </span>
                      )}
                    </div>
                    <button
                      onClick={() => setExpandedId(isExpanded ? null : item.id)}
                      className="text-xs text-slate-400 hover:text-primary"
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: 16 }}>
                        {isExpanded ? 'expand_less' : 'attach_file'}
                      </span>
                    </button>
                  </div>
                  {isExpanded && (
                    <div className="mt-3 pt-3 border-t border-slate-100">
                      <AttachmentPanel bizType="activity" bizId={item.id} />
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      <Modal title="添加互动记录" open={modal} onOk={handleCreate} onCancel={() => setModal(false)} width={520}>
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
            {contacts.length > 0 ? (
              <Select
                className="w-full"
                value={form.contact_id || undefined}
                onChange={handleContactSelect}
                allowClear
                onClear={() => setForm({ ...form, contact_id: '', contact_name: '' })}
                placeholder="选择联系人..."
                showSearch
                optionFilterProp="label"
                options={contacts.map((c) => ({
                  value: c.id,
                  label: `${c.name}${c.title ? ` (${c.title})` : ''}${c.phone ? ` ${c.phone}` : ''}`,
                }))}
              />
            ) : (
              <Input value={form.contact_name} onChange={(e) => setForm({ ...form, contact_name: e.target.value })} placeholder="联系人姓名..." />
            )}
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-sm font-medium text-slate-700">内容</label>
              <VoiceInput onResult={(text) => setForm((prev: typeof form) => ({ ...prev, content: (prev.content || '') + text }))} />
            </div>
            <TextArea rows={4} value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} placeholder="详细内容..." />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">@提及同事</label>
            <Select mode="multiple" className="w-full" placeholder="搜索并选择要@的同事"
              value={mentionIds} onChange={setMentionIds}
              showSearch filterOption={false}
              loading={mentionSelect.loading}
              options={mentionSelect.options}
              onSearch={mentionSelect.onSearch}
              onDropdownVisibleChange={mentionSelect.onDropdownVisibleChange}
            />
            <div className="text-xs text-slate-400 mt-0.5">被@的同事将收到通知</div>
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">下次跟进日期</label>
            <DatePicker
              className="w-full"
              value={form.next_follow_date ? dayjs(form.next_follow_date) : null}
              onChange={(d) => setForm({ ...form, next_follow_date: d ? d.format('YYYY-MM-DD') : '' })}
              placeholder="选择日期..."
            />
          </div>
        </div>
      </Modal>
    </div>
  )
}
