// 移动端 → 表单填报: 列出已发布的自定义表单, 点选进入填报。
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { message } from 'antd'
import MobileIcon from '@/components/MobileIcon'
import { usePageTitle } from '@/hooks/usePageTitle'
import { lowcodeApi } from '@/api/lowcode'
import type { FormTemplate } from '@/types/lowcode'

export default function MobileLowcodeForms() {
  usePageTitle('表单填报')
  const nav = useNavigate()
  const [items, setItems] = useState<FormTemplate[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    lowcodeApi.listTemplates({ pageNo: 1, pageSize: 100, published_only: true })
      .then((r) => setItems(r.data.items || []))
      .catch(() => message.error('加载失败'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return <div className="flex items-center justify-center h-64"><MobileIcon name="progress_activity" className="animate-spin text-primary" style={{ fontSize: 32 }} /></div>
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <button onClick={() => nav(-1)} className="flex items-center text-primary bg-transparent border-0 cursor-pointer p-0"><MobileIcon name="arrow_back_ios" /></button>
        <h2 className="text-lg font-bold text-slate-900 flex-1 text-center">表单填报</h2>
        <div className="w-10" />
      </div>
      {items.length ? (
        <div className="space-y-3">
          {items.map((t) => (
            <div key={t.id} onClick={() => nav(`/m/lowcode/forms/${t.id}/fill`)}
              className="bg-white rounded-xl border border-slate-100 shadow-sm p-4 cursor-pointer active:bg-slate-50 transition-colors flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                <MobileIcon name="assignment" className="text-primary" style={{ fontSize: 20 }} />
              </div>
              <div className="flex-1 min-w-0">
                <h4 className="text-sm font-bold text-slate-900 truncate">{t.name}</h4>
                {t.description && <div className="text-sm text-slate-400 truncate mt-0.5">{t.description}</div>}
              </div>
              <MobileIcon name="chevron_right" className="text-slate-300 shrink-0" style={{ fontSize: 16 }} />
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-16"><MobileIcon name="assignment" className="text-slate-200 mb-2" style={{ fontSize: 48 }} /><p className="text-sm text-slate-400 mt-2">暂无已发布表单</p></div>
      )}
    </div>
  )
}
