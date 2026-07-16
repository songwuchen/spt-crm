import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { message } from 'antd'
import { customerApi } from '@/api/customer'
import { usePageTitle } from '@/hooks/usePageTitle'
import RegionCascader from '@/components/RegionCascader'
import type { RegionValue } from '@/components/RegionCascader'

export default function MobileCustomerForm() {
  usePageTitle('新建客户')
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState({
    name: '', short_name: '', industry: '', source: '', level: 'C',
  })
  const [region, setRegion] = useState<RegionValue>({})

  const update = (field: string, value: string) => setForm(prev => ({ ...prev, [field]: value }))

  const handleSubmit = async () => {
    if (!form.name.trim()) { message.error('请输入客户名称'); return }
    setLoading(true)
    try {
      await customerApi.create({
        name: form.name.trim(),
        short_name: form.short_name || undefined,
        industry: form.industry || undefined,
        province: region.province || undefined,
        city: region.city || undefined,
        district: region.district || undefined,
        region_code: region.regionCode || undefined,
        source: form.source || undefined,
        level: form.level || undefined,
      })
      message.success('客户创建成功')
      navigate('/m/customers')
    } catch { message.error('创建失败') } finally { setLoading(false) }
  }

  const industries = ['电子制造', '汽车零部件', '机械装备', '航空航天', '医疗器械', '半导体', '新能源', '其他']

  return (
    <div>
      <h1 className="text-xl font-extrabold text-slate-900 mb-4">新建客户</h1>

      <div className="space-y-3">
        <div>
          <label className="text-sm font-bold text-slate-500 mb-1 block">客户名称 *</label>
          <input className="w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm"
            placeholder="请输入客户名称" value={form.name} onChange={e => update('name', e.target.value)} />
        </div>
        <div>
          <label className="text-sm font-bold text-slate-500 mb-1 block">简称</label>
          <input className="w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm"
            placeholder="简称" value={form.short_name} onChange={e => update('short_name', e.target.value)} />
        </div>
        <div>
          <label className="text-sm font-bold text-slate-500 mb-1 block">行业</label>
          <select className="w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm bg-white"
            value={form.industry} onChange={e => update('industry', e.target.value)}>
            <option value="">请选择</option>
            {industries.map(i => <option key={i} value={i}>{i}</option>)}
          </select>
        </div>
        <div>
          <label className="text-sm font-bold text-slate-500 mb-1 block">地区</label>
          <RegionCascader value={region} onChange={setRegion} placeholder="选择省/市/区县" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-sm font-bold text-slate-500 mb-1 block">来源</label>
            <select className="w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm bg-white"
              value={form.source} onChange={e => update('source', e.target.value)}>
              <option value="">请选择</option>
              {['referral', 'website', 'exhibition', 'cold_call', 'ad', 'other'].map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-sm font-bold text-slate-500 mb-1 block">级别</label>
            <select className="w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm bg-white"
              value={form.level} onChange={e => update('level', e.target.value)}>
              {['A', 'B', 'C', 'D'].map(l => <option key={l} value={l}>{l}</option>)}
            </select>
          </div>
        </div>
      </div>

      <div className="mt-6 flex gap-3">
        <button onClick={() => navigate(-1)}
          className="flex-1 py-2.5 border border-slate-200 rounded-lg text-sm font-bold text-slate-600 bg-white">
          取消
        </button>
        <button onClick={handleSubmit} disabled={loading}
          className="flex-1 py-2.5 rounded-lg text-sm font-bold text-white bg-primary disabled:opacity-50">
          {loading ? '保存中...' : '创建'}
        </button>
      </div>
    </div>
  )
}
