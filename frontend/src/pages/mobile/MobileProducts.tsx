import { useState, useEffect } from 'react'
import { productApi } from '@/api/product'
import { usePageTitle } from '@/hooks/usePageTitle'

interface Product {
  id: string; product_code: string; name: string; spec?: string
  unit_price?: number; unit?: string; is_active: boolean; usage_count: number
}

export default function MobileProducts() {
  usePageTitle('产品目录')
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [keyword, setKeyword] = useState('')
  const [filterActive, setFilterActive] = useState<boolean | undefined>(true)

  const fetchProducts = () => {
    setLoading(true)
    productApi.list({ pageNo: 1, pageSize: 100, keyword: keyword || undefined, is_active: filterActive })
      .then((r: any) => setProducts(r.data?.items || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchProducts() }, [filterActive])

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="bg-white px-4 pt-3 pb-2 border-b border-slate-100">
        <h1 className="text-lg font-bold text-slate-900">产品目录</h1>
      </div>

      {/* Search & Filter */}
      <div className="bg-white px-4 py-2 border-b border-slate-100 flex gap-2">
        <div className="flex-1 relative">
          <span className="material-symbols-outlined absolute left-2.5 top-2 text-slate-400" style={{ fontSize: 18 }}>search</span>
          <input value={keyword} onChange={(e) => setKeyword(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && fetchProducts()}
            placeholder="搜索产品" className="w-full bg-slate-50 border border-slate-200 rounded-lg pl-8 pr-3 py-2 text-sm" />
        </div>
        <div className="flex gap-1">
          {[
            { label: '在售', value: true },
            { label: '全部', value: undefined },
          ].map((f) => (
            <button key={String(f.value)} onClick={() => setFilterActive(f.value)}
              className={`px-3 py-2 rounded-lg text-sm font-bold ${
                filterActive === f.value ? 'bg-primary text-white' : 'bg-slate-100 text-slate-600'
              }`}>{f.label}</button>
          ))}
        </div>
      </div>

      {/* Product List */}
      <div className="p-4 space-y-2 pb-20">
        {loading && <div className="text-center py-8 text-slate-400 text-sm">加载中...</div>}
        {!loading && products.length === 0 && (
          <div className="text-center py-8 text-slate-400 text-sm">暂无产品</div>
        )}
        {products.map((p) => (
          <div key={p.id} className="bg-white rounded-xl border border-slate-100 shadow-sm p-3">
            <div className="flex items-start justify-between mb-1">
              <div className="flex-1 min-w-0">
                <span className="text-sm font-bold text-slate-800 block truncate">{p.name}</span>
                <span className="text-[10px] font-mono text-slate-400">{p.product_code}</span>
              </div>
              <div className="text-right shrink-0 ml-2">
                {p.unit_price != null ? (
                  <span className="text-sm font-black text-slate-900">¥{Number(p.unit_price).toLocaleString()}</span>
                ) : <span className="text-sm text-slate-400">-</span>}
                {p.unit && <span className="text-[10px] text-slate-400">/{p.unit}</span>}
              </div>
            </div>
            {p.spec && <p className="text-sm text-slate-500 mb-1 truncate">{p.spec}</p>}
            <div className="flex items-center gap-2 text-[10px]">
              <span className={`px-1.5 py-0.5 rounded font-bold ${p.is_active ? 'bg-emerald-50 text-emerald-600' : 'bg-slate-100 text-slate-500'}`}>
                {p.is_active ? '在售' : '停售'}
              </span>
              {p.usage_count > 0 && (
                <span className="text-primary font-bold">引用 {p.usage_count} 次</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
