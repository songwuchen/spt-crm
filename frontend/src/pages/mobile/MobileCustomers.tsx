import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Input, Spin } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { customerApi } from '@/api/customer'
import type { Customer } from '@/api/types'
import { usePageTitle } from '@/hooks/usePageTitle'
import PullToRefresh from '@/components/PullToRefresh'

const levelColors: Record<string, string> = {
  A: 'bg-red-100 text-red-700', B: 'bg-amber-100 text-amber-700',
  C: 'bg-blue-100 text-blue-700', D: 'bg-slate-100 text-slate-600',
}

export default function MobileCustomers() {
  usePageTitle('客户')
  const [data, setData] = useState<Customer[]>([])
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')
  const navigate = useNavigate()

  const fetchData = async (kw = keyword) => {
    setLoading(true)
    try {
      const res = await customerApi.list({ pageNo: 1, pageSize: 50, keyword: kw || undefined })
      setData(res.data.items)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  return (
    <PullToRefresh onRefresh={() => fetchData()}>
    <div>
      <h1 className="text-lg font-extrabold text-slate-900 mb-3">客户</h1>

      {/* Search */}
      <Input
        placeholder="搜索客户名称..."
        prefix={<SearchOutlined className="text-slate-400" />}
        value={keyword}
        onChange={(e) => setKeyword(e.target.value)}
        onPressEnter={() => fetchData(keyword)}
        allowClear
        className="rounded-xl mb-3"
        style={{ background: '#f1f5f9', borderColor: 'transparent' }}
      />

      {/* Card List */}
      {loading ? (
        <div className="flex justify-center mt-10"><Spin /></div>
      ) : (
        <div className="space-y-2">
          {data.map((c) => (
            <div
              key={c.id}
              onClick={() => navigate(`/m/customers/${c.id}`)}
              className="bg-white rounded-xl border border-slate-100 shadow-sm p-3 flex items-center gap-3 active:bg-slate-50 cursor-pointer"
            >
              <div className="w-10 h-10 rounded-lg bg-slate-100 border border-slate-200 flex items-center justify-center text-sm font-bold text-slate-600 shrink-0">
                {c.name.slice(0, 2)}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-bold text-slate-900 truncate">{c.name}</div>
                <div className="text-xs text-slate-500 truncate">
                  {[c.industry, c.region].filter(Boolean).join(' · ') || '-'}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {c.level && (
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-black ${levelColors[c.level] || levelColors.D}`}>
                    {c.level}
                  </span>
                )}
                <span className={`w-2 h-2 rounded-full ${c.status === 'active' ? 'bg-emerald-500' : 'bg-slate-300'}`} />
              </div>
            </div>
          ))}
          {data.length === 0 && !loading && (
            <div className="text-center text-sm text-slate-400 py-10">暂无客户数据</div>
          )}
        </div>
      )}
    </div>
    </PullToRefresh>
  )
}
