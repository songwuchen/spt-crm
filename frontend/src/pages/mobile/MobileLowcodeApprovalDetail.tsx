// 移动端 → 扩展平台审批详情: 表单内容(只读) + 流程轨迹 + 处理(通过/驳回/评论)。
import { useEffect, useState } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { Input, message } from 'antd'
import MobileIcon from '@/components/MobileIcon'
import { usePageTitle } from '@/hooks/usePageTitle'
import { workflowApi } from '@/api/lowcodeWorkflow'
import { lowcodeApi } from '@/api/lowcode'
import type { WfInstanceDetail, FieldDefinition } from '@/types/lowcode'
import FormRenderer from '@/components/lowcode/FormRenderer'
import { WF_ACTION_TEXT as ACTION_TXT, WF_STATUS as PSTATUS } from '@/utils/lowcodeWorkflowLabels'

export default function MobileLowcodeApprovalDetail() {
  usePageTitle('审批详情')
  const { id = '' } = useParams()
  const [sp] = useSearchParams()
  const taskId = sp.get('task')
  const nav = useNavigate()
  const [detail, setDetail] = useState<WfInstanceDetail | null>(null)
  const [fields, setFields] = useState<FieldDefinition[]>([])
  const [formData, setFormData] = useState<Record<string, unknown>>({})
  const [opinion, setOpinion] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    (async () => {
      try {
        const d = await workflowApi.instance(id)
        setDetail(d.data)
        if (d.data.form_instance_id) {
          const fi = await lowcodeApi.getInstance(d.data.form_instance_id)
          setFields(fi.data.field_definitions); setFormData(fi.data.form_data)
        }
      } catch { message.error('加载失败') } finally { setLoading(false) }
    })()
  }, [id])

  const act = async (action: string) => {
    if (!taskId) return
    setBusy(true)
    try {
      await workflowApi.act(taskId, { action, opinion })
      message.success('已处理'); nav('/m/lowcode/approvals')
    } catch { message.error('处理失败') } finally { setBusy(false) }
  }

  if (loading) return <div className="flex items-center justify-center h-64"><MobileIcon name="progress_activity" className="animate-spin text-primary" style={{ fontSize: 32 }} /></div>
  if (!detail) return null
  const st = PSTATUS[detail.status] || { cls: 'bg-slate-100 text-slate-500', text: detail.status }
  const canAct = !!taskId && detail.status === 'running'

  return (
    <div className={canAct ? 'pb-24' : ''}>
      <div className="flex items-center justify-between mb-4">
        <button onClick={() => nav(-1)} className="flex items-center text-primary bg-transparent border-0 cursor-pointer p-0"><MobileIcon name="arrow_back_ios" /></button>
        <h2 className="text-lg font-bold text-slate-900 flex-1 text-center">审批详情</h2>
        <div className="w-10" />
      </div>

      <div className="bg-white rounded-xl border border-slate-100 p-4 mb-3">
        <div className="flex items-center justify-between gap-2">
          <h4 className="text-base font-bold text-slate-900 truncate">{detail.title || '(无标题)'}</h4>
          <span className={`text-[12px] font-bold px-2 py-0.5 rounded-full shrink-0 ${st.cls}`}>{st.text}</span>
        </div>
      </div>

      {fields.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-100 p-4 mb-3">
          <div className="text-sm font-bold text-slate-500 mb-2">表单内容</div>
          <FormRenderer fields={fields} mode="readonly" value={formData} applyFieldPerms={false} />
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-100 p-4">
        <div className="text-sm font-bold text-slate-500 mb-3">流程轨迹</div>
        <div className="space-y-3">
          {(detail.timeline || []).map((t, i) => (
            <div key={i} className="flex gap-3">
              <div className="flex flex-col items-center">
                <div className="w-2 h-2 rounded-full bg-primary mt-1.5" />
                {i < (detail.timeline || []).length - 1 && <div className="flex-1 w-px bg-slate-200 my-1" />}
              </div>
              <div className="flex-1 pb-1">
                <div className="text-sm text-slate-900"><b>{ACTION_TXT[t.action] || t.action}</b> · {t.actor_name || t.actor_id}</div>
                {t.opinion && <div className="text-sm text-slate-500 mt-0.5">意见: {t.opinion}</div>}
                <div className="text-[12px] text-slate-400 mt-0.5">{t.at?.slice(0, 19).replace('T', ' ')}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {canAct && (
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-slate-100 p-3" style={{ paddingBottom: 'calc(env(safe-area-inset-bottom) + 12px)' }}>
          <Input.TextArea rows={2} placeholder="审批意见(可选)" value={opinion} onChange={(e) => setOpinion(e.target.value)} style={{ marginBottom: 8 }} />
          <div className="flex gap-2">
            <button onClick={() => act('reject')} disabled={busy} className="flex-1 h-11 rounded-xl bg-red-50 text-red-600 font-bold border-0 disabled:opacity-60">驳回</button>
            <button onClick={() => act('approve')} disabled={busy} className="flex-1 h-11 rounded-xl bg-primary text-white font-bold border-0 disabled:opacity-60">通过</button>
          </div>
        </div>
      )}
    </div>
  )
}
