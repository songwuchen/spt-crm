import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { message } from 'antd'
import { projectApi } from '@/api/project'
import { customerApi } from '@/api/customer'
import { usePageTitle } from '@/hooks/usePageTitle'

export default function MobileOpportunityForm() {
  usePageTitle('新建商机')
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [customers, setCustomers] = useState<{ id: string; name: string }[]>([])
  const [form, setForm] = useState({
    name: '', customer_id: '', amount_expect: '', stage: 'S1', remark: '',
  })

  useEffect(() => {
    customerApi.list({ pageNo: 1, pageSize: 100 })
      .then(r => setCustomers((r.data?.items || []).map((c: any) => ({ id: c.id, name: c.name }))))
      .catch(() => {})
  }, [])

  const handleSubmit = async () => {
    if (!form.name.trim()) { message.warning('请输入商机名称'); return }
    if (!form.customer_id) { message.warning('请选择客户'); return }
    setLoading(true)
    try {
      const data: any = { name: form.name, customer_id: form.customer_id, stage: form.stage, remark: form.remark }
      if (form.amount_expect) data.amount_expect = parseFloat(form.amount_expect)
      await projectApi.create(data)
      message.success('商机已创建')
      navigate(-1)
    } catch { message.error('创建失败') }
    finally { setLoading(false) }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="bg-white px-4 pt-3 pb-2 border-b border-slate-100 flex items-center justify-between">
        <button onClick={() => navigate(-1)} className="text-primary font-bold text-sm">取消</button>
        <h1 className="text-base font-bold text-slate-900">新建商机</h1>
        <button onClick={handleSubmit} disabled={loading}
          className="text-primary font-bold text-sm disabled:opacity-50">
          {loading ? '提交中...' : '保存'}
        </button>
      </div>

      <div className="p-4 space-y-4">
        <div>
          <label className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1 block">商机名称 *</label>
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="输入商机名称" className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2.5 text-sm" />
        </div>
        <div>
          <label className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1 block">客户 *</label>
          <select value={form.customer_id} onChange={(e) => setForm({ ...form, customer_id: e.target.value })}
            className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2.5 text-sm">
            <option value="">请选择客户</option>
            {customers.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1 block">预期金额</label>
            <input value={form.amount_expect} onChange={(e) => setForm({ ...form, amount_expect: e.target.value })}
              placeholder="0.00" type="number" className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2.5 text-sm" />
          </div>
          <div>
            <label className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1 block">阶段</label>
            <select value={form.stage} onChange={(e) => setForm({ ...form, stage: e.target.value })}
              className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2.5 text-sm">
              <option value="S1">S1 线索确认</option>
              <option value="S2">S2 需求分析</option>
              <option value="S3">S3 方案报价</option>
            </select>
          </div>
        </div>
        <div>
          <label className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1 block">备注</label>
          <textarea value={form.remark} onChange={(e) => setForm({ ...form, remark: e.target.value })}
            placeholder="其他信息" rows={3}
            className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2.5 text-sm resize-none" />
        </div>
      </div>
    </div>
  )
}
