import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { message } from 'antd'
import { quoteApi } from '@/api/quote'
import { contractApi } from '@/api/contract'
import { usePageTitle } from '@/hooks/usePageTitle'

interface VersionInfo {
  id: string; version_no: number; title?: string; status: string
  price_total?: number; tax_rate?: number; margin_rate?: number
  discount_total?: number; delivery_promise_date?: string; validity_days?: number
}

interface LineItem {
  id: string; line_no: number; item_type?: string; item_code?: string
  item_name?: string; spec?: string; qty?: number; unit?: string
  unit_price?: number; line_total?: number; cost_est?: number
}

const itemTypeLabels: Record<string, string> = {
  standard: '标准', custom: '定制', service: '服务', spare: '备件',
}

// 成本/毛利/折扣无权限时被后端脱敏为 "***"，渲染前识别以避免显示 "NaN"。
const isMasked = (v: unknown): boolean => typeof v === 'string' && !Number.isFinite(Number(v))
const fmtMoney = (v: unknown): string => (v == null ? '-' : isMasked(v) ? '***' : `¥${Number(v).toLocaleString()}`)
const fmtPct = (v: unknown): string => (v == null ? '-' : isMasked(v) ? '***' : `${(Number(v) * 100).toFixed(1)}%`)

export default function MobileQuoteDetail() {
  usePageTitle('报价详情')
  const { id: projectId, qid } = useParams<{ id: string; qid: string }>()
  const navigate = useNavigate()
  const [quote, setQuote] = useState<any>(null)
  const [versions, setVersions] = useState<VersionInfo[]>([])
  const [currentVersion, setCurrentVersion] = useState<VersionInfo | null>(null)
  const [lines, setLines] = useState<LineItem[]>([])
  const [selectedVersionId, setSelectedVersionId] = useState('')
  const [tab, setTab] = useState<'lines' | 'info'>('lines')
  const [contractLoading, setContractLoading] = useState(false)

  const fetchQuote = async () => {
    try {
      const res = await quoteApi.get(qid!)
      const d = res.data
      setQuote(d)
      setVersions(d.versions || [])
      setCurrentVersion(d.current_version || null)
      setLines(d.lines || [])
      if (d.current_version) setSelectedVersionId(d.current_version.id)
    } catch { message.error('加载失败') }
  }

  const fetchVersion = async (vid: string) => {
    const res = await quoteApi.getVersion(vid)
    setCurrentVersion(res.data)
    setLines(res.data.lines || [])
    setSelectedVersionId(vid)
  }

  useEffect(() => { fetchQuote() }, [qid])

  const handleGenerateContract = async () => {
    setContractLoading(true)
    try {
      const res = await contractApi.fromQuote(qid!)
      message.success('合同已生成')
      navigate(`/m/opportunities/${projectId}`)
    } catch { message.error('生成失败') }
    finally { setContractLoading(false) }
  }

  if (!quote) return <div className="text-center py-12 text-slate-400">加载中...</div>

  const lineTotal = lines.reduce((s, l) => s + (l.line_total || 0), 0)

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <div className="bg-white px-4 pt-3 pb-2 border-b border-slate-100">
        <div className="flex items-center gap-2 mb-2">
          <button onClick={() => navigate(-1)} className="text-slate-400">
            <span className="material-symbols-outlined" style={{ fontSize: 20 }}>arrow_back</span>
          </button>
          <div className="flex-1 min-w-0">
            <h1 className="text-base font-extrabold text-slate-900 truncate">{quote.quote_no}</h1>
          </div>
          <span className={`px-2 py-0.5 rounded text-[12px] font-bold ${
            quote.status === 'approved' ? 'bg-emerald-50 text-emerald-600 border border-emerald-200' :
            quote.status === 'rejected' ? 'bg-red-50 text-red-600 border border-red-200' :
            'bg-blue-50 text-blue-600 border border-blue-200'
          }`}>{quote.status}</span>
        </div>

        {/* Version Selector */}
        {versions.length > 1 && (
          <div className="flex gap-1.5 overflow-x-auto pb-1">
            {versions.map((v) => (
              <button key={v.id} onClick={() => fetchVersion(v.id)}
                className={`shrink-0 px-2.5 py-1 rounded-full text-[12px] font-bold transition-colors ${
                  selectedVersionId === v.id ? 'bg-primary text-white' : 'bg-slate-100 text-slate-600'
                }`}>
                V{v.version_no}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* KPI Cards */}
      {currentVersion && (
        <div className="px-4 pt-3">
          <div className="grid grid-cols-3 gap-2">
            <div className="bg-gradient-to-br from-primary/10 to-blue-50 rounded-xl p-3 text-center border border-primary/10">
              <div className="text-sm font-black text-slate-900">
                {currentVersion.price_total != null ? `¥${(Number(currentVersion.price_total) / 10000).toFixed(1)}万` : '-'}
              </div>
              <div className="text-[12px] text-slate-500 font-bold">总价</div>
            </div>
            <div className="bg-gradient-to-br from-emerald-50 to-green-50 rounded-xl p-3 text-center border border-emerald-100">
              <div className="text-sm font-black text-emerald-600">
                {fmtPct(currentVersion.margin_rate)}
              </div>
              <div className="text-[12px] text-slate-500 font-bold">毛利率</div>
            </div>
            <div className="bg-gradient-to-br from-amber-50 to-yellow-50 rounded-xl p-3 text-center border border-amber-100">
              <div className="text-sm font-black text-amber-600">
                {currentVersion.validity_days ?? '-'}天
              </div>
              <div className="text-[12px] text-slate-500 font-bold">有效期</div>
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="px-4 pt-3">
        <div className="flex gap-1 bg-slate-100 rounded-lg p-1 mb-3">
          {(['lines', 'info'] as const).map((t) => (
            <button key={t} onClick={() => setTab(t)}
              className={`flex-1 py-2 rounded-md text-sm font-bold transition-colors ${
                tab === t ? 'bg-white text-primary shadow-sm' : 'text-slate-500'
              }`}>
              {t === 'lines' ? `行项目 (${lines.length})` : '版本信息'}
            </button>
          ))}
        </div>
      </div>

      {/* Line Items */}
      {tab === 'lines' && (
        <div className="px-4 space-y-2 pb-28">
          {lines.length === 0 ? (
            <div className="text-center py-8 text-slate-400 text-sm">暂无行项目</div>
          ) : (
            <>
              {lines.map((l) => (
                <div key={l.id} className="bg-white rounded-xl border border-slate-100 shadow-sm p-3">
                  <div className="flex items-start justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <span className="text-[12px] text-slate-400 font-mono">#{l.line_no}</span>
                      {l.item_type && (
                        <span className="text-[12px] px-1.5 py-0.5 bg-slate-100 text-slate-500 rounded font-bold">
                          {itemTypeLabels[l.item_type] || l.item_type}
                        </span>
                      )}
                    </div>
                    <span className="text-sm font-black text-slate-900">
                      {l.line_total != null ? `¥${Number(l.line_total).toLocaleString()}` : '-'}
                    </span>
                  </div>
                  <p className="text-sm font-bold text-slate-800 mb-1">{l.item_name || '-'}</p>
                  {l.spec && <p className="text-sm text-slate-500 mb-1">{l.spec}</p>}
                  <div className="flex items-center gap-3 text-[12px] text-slate-400">
                    {l.qty != null && <span>数量: {l.qty} {l.unit || ''}</span>}
                    {l.unit_price != null && <span>单价: ¥{Number(l.unit_price).toLocaleString()}</span>}
                    {l.cost_est != null && <span>成本: {fmtMoney(l.cost_est)}</span>}
                  </div>
                </div>
              ))}
              <div className="bg-primary/5 rounded-xl border border-primary/10 p-3 flex justify-between items-center">
                <span className="text-sm font-bold text-slate-500">行合计</span>
                <span className="text-lg font-black text-slate-900">¥{lineTotal.toLocaleString()}</span>
              </div>
            </>
          )}
        </div>
      )}

      {/* Version Info */}
      {tab === 'info' && currentVersion && (
        <div className="px-4 pb-28">
          <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-4 space-y-3">
            <div className="flex justify-between">
              <span className="text-sm text-slate-400">版本</span>
              <span className="text-sm font-bold text-slate-700">V{currentVersion.version_no} {currentVersion.title || ''}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-slate-400">状态</span>
              <span className="text-sm text-slate-700">{currentVersion.status}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-slate-400">总价</span>
              <span className="text-sm font-bold text-slate-800">
                {currentVersion.price_total != null ? `¥${Number(currentVersion.price_total).toLocaleString()}` : '-'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-slate-400">税率</span>
              <span className="text-sm text-slate-700">
                {currentVersion.tax_rate != null ? `${(Number(currentVersion.tax_rate) * 100).toFixed(1)}%` : '-'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-slate-400">毛利率</span>
              <span className="text-sm text-slate-700">
                {fmtPct(currentVersion.margin_rate)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-slate-400">折扣</span>
              <span className="text-sm text-slate-700">
                {fmtMoney(currentVersion.discount_total)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-slate-400">交期承诺</span>
              <span className="text-sm text-slate-700">{currentVersion.delivery_promise_date || '-'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-slate-400">有效天数</span>
              <span className="text-sm text-slate-700">{currentVersion.validity_days ?? '-'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-slate-400">创建人</span>
              <span className="text-sm text-slate-700">{quote.created_by_name || '-'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-slate-400">创建时间</span>
              <span className="text-sm text-slate-500">
                {quote.created_at ? new Date(quote.created_at).toLocaleString('zh-CN') : '-'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Bottom Actions */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-slate-100 px-4 py-3 flex gap-2">
        <button onClick={() => navigate(`/m/opportunities/${projectId}`)}
          className="flex-1 py-2.5 bg-slate-100 rounded-lg text-sm font-bold text-slate-600">
          返回商机
        </button>
        <button onClick={handleGenerateContract} disabled={contractLoading}
          className="flex-1 py-2.5 bg-primary text-white rounded-lg text-sm font-bold disabled:opacity-50">
          {contractLoading ? '生成中...' : '生成合同'}
        </button>
      </div>
    </div>
  )
}
