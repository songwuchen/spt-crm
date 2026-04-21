import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { message } from 'antd'
import { leadApi } from '@/api/lead'
import { usePageTitle } from '@/hooks/usePageTitle'

const sources = [
  { value: 'website', label: '官网' }, { value: 'referral', label: '转介绍' },
  { value: 'exhibition', label: '展会' }, { value: 'cold_call', label: '陌拜' },
  { value: 'advertising', label: '广告' }, { value: 'other', label: '其他' },
]

export default function MobileLeadForm() {
  usePageTitle('新建线索')
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState({
    title: '', company_name: '', contact_name: '', contact_phone: '', source: 'website', remark: '',
  })

  const handleSubmit = async () => {
    if (!form.title.trim()) { message.warning('请输入线索标题'); return }
    setLoading(true)
    try {
      await leadApi.create(form as any)
      message.success('线索已创建')
      navigate(-1)
    } catch { message.error('创建失败') }
    finally { setLoading(false) }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="bg-white px-4 pt-3 pb-2 border-b border-slate-100 flex items-center justify-between">
        <button onClick={() => navigate(-1)} className="text-primary font-bold text-sm">取消</button>
        <h1 className="text-base font-bold text-slate-900">新建线索</h1>
        <button onClick={handleSubmit} disabled={loading}
          className="text-primary font-bold text-sm disabled:opacity-50">
          {loading ? '提交中...' : '保存'}
        </button>
      </div>

      <div className="p-4 space-y-4">
        <div>
          <label className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-1 block">线索标题 *</label>
          <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })}
            placeholder="输入线索标题" className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2.5 text-sm" />
        </div>
        <div>
          <label className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-1 block">公司名称</label>
          <input value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })}
            placeholder="输入公司名称" className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2.5 text-sm" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-1 block">联系人</label>
            <input value={form.contact_name} onChange={(e) => setForm({ ...form, contact_name: e.target.value })}
              placeholder="姓名" className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2.5 text-sm" />
          </div>
          <div>
            <label className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-1 block">电话</label>
            <input value={form.contact_phone} onChange={(e) => setForm({ ...form, contact_phone: e.target.value })}
              placeholder="电话号码" className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2.5 text-sm" />
          </div>
        </div>
        <div>
          <label className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-1 block">来源</label>
          <select value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })}
            className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2.5 text-sm">
            {sources.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </div>
        <div>
          <label className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-1 block">备注</label>
          <textarea value={form.remark} onChange={(e) => setForm({ ...form, remark: e.target.value })}
            placeholder="其他信息" rows={3}
            className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2.5 text-sm resize-none" />
        </div>
      </div>
    </div>
  )
}
