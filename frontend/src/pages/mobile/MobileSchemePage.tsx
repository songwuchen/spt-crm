// 移动端 → 方案管理：ensure 内置模板后列表 + 新建填报。
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { message } from 'antd'
import MobileIcon from '@/components/MobileIcon'
import { usePageTitle } from '@/hooks/usePageTitle'
import { lowcodeApi } from '@/api/lowcode'
import type { FormInstance } from '@/types/lowcode'

const STATUS_LABEL: Record<string, { text: string; cls: string }> = {
  draft: { text: '草稿', cls: 'bg-slate-100 text-slate-600' },
  submitted: { text: '已提交', cls: 'bg-blue-50 text-blue-600' },
  approving: { text: '审批中', cls: 'bg-amber-50 text-amber-600' },
  approved: { text: '已通过', cls: 'bg-emerald-50 text-emerald-600' },
  rejected: { text: '已驳回', cls: 'bg-red-50 text-red-600' },
  running: { text: '审批中', cls: 'bg-amber-50 text-amber-600' },
  completed: { text: '已完成', cls: 'bg-emerald-50 text-emerald-600' },
}

export default function MobileSchemePage() {
  usePageTitle('方案管理')
  const nav = useNavigate()
  const [templateId, setTemplateId] = useState<string | null>(null)
  const [items, setItems] = useState<FormInstance[]>([])
  const [loading, setLoading] = useState(true)

  const refresh = async (tid: string) => {
    const r = await lowcodeApi.listInstances({
      template_id: tid, pageNo: 1, pageSize: 50,
    })
    setItems(r.data.items || [])
  }

  useEffect(() => {
    (async () => {
      try {
        const res = await lowcodeApi.ensureBuiltin('scheme_management')
        setTemplateId(res.data.id)
        await refresh(res.data.id)
      } catch {
        message.error('加载方案管理失败')
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  const goFill = () => {
    if (!templateId) return
    nav(`/m/lowcode/forms/${templateId}/fill?code=scheme_management&returnTo=${encodeURIComponent('/m/solutions')}`)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <MobileIcon name="progress_activity" className="animate-spin text-primary" style={{ fontSize: 32 }} />
      </div>
    )
  }

  return (
    <div style={{ paddingBottom: 'calc(env(safe-area-inset-bottom) + 80px)' }}>
      <div className="flex items-center justify-between mb-4">
        <button onClick={() => nav(-1)} className="flex items-center text-primary bg-transparent border-0 cursor-pointer p-0">
          <MobileIcon name="arrow_back_ios" />
        </button>
        <h2 className="text-lg font-bold text-slate-900 flex-1 text-center">方案管理</h2>
        <button
          type="button"
          onClick={goFill}
          className="text-primary text-sm font-bold bg-transparent border-0 cursor-pointer p-0"
        >
          新建
        </button>
      </div>

      <div className="bg-primary/10 rounded-xl p-3 mb-4 text-sm text-primary/80">
        无合同号走前期/投标方案，有合同号走简易领图；点「新建」开始填报。
      </div>

      {items.length ? (
        <div className="space-y-3">
          {items.map((it) => {
            const st = STATUS_LABEL[it.status] || { text: it.status, cls: 'bg-slate-100 text-slate-500' }
            const fd = it.form_data || {}
            const schemeType = fd.scheme_type === 'requisition' ? '有合同号' : fd.scheme_type === 'install' ? '无合同号' : ''
            const title = (it.title || it.business_no || fd.customer_name || '方案单据') as string
            return (
              <div
                key={it.id}
                className="bg-white rounded-xl border border-slate-100 shadow-sm p-4"
                onClick={() => {
                  if (it.process_instance_id) {
                    nav(`/m/lowcode/approvals/${it.process_instance_id}`)
                  }
                }}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <h4 className="text-sm font-bold text-slate-900 truncate">{String(title)}</h4>
                    <div className="flex items-center gap-2 mt-1 text-sm text-slate-500">
                      {schemeType && <span>{schemeType}</span>}
                      {it.business_no && (
                        <>
                          {schemeType && <span className="text-slate-300">·</span>}
                          <span className="truncate">{it.business_no}</span>
                        </>
                      )}
                    </div>
                    <div className="text-[12px] text-slate-400 mt-1.5">
                      {it.created_at?.slice(0, 19).replace('T', ' ')}
                    </div>
                  </div>
                  <span className={`text-[12px] font-bold px-2 py-0.5 rounded-full shrink-0 ${st.cls}`}>
                    {st.text}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      ) : (
        <div className="text-center py-16">
          <MobileIcon name="lightbulb" className="text-slate-200 mb-2" style={{ fontSize: 48 }} />
          <p className="text-sm text-slate-400 mt-2">暂无方案单据</p>
          <button
            type="button"
            onClick={goFill}
            className="mt-4 px-4 h-10 rounded-lg bg-primary text-white text-sm font-bold border-0"
          >
            新建方案
          </button>
        </div>
      )}

      {items.length > 0 && (
        <div
          className="fixed left-0 right-0 z-30 p-3"
          style={{ bottom: 'calc(env(safe-area-inset-bottom) + 56px)' }}
        >
          <button
            type="button"
            onClick={goFill}
            className="w-full h-11 rounded-xl bg-primary text-white font-bold border-0 shadow-lg"
          >
            新建方案
          </button>
        </div>
      )}
    </div>
  )
}
