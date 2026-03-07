import { useState } from 'react'
import { Radio } from 'antd'
import { usePageTitle } from '@/hooks/usePageTitle'

export default function ApiDocsPage() {
  usePageTitle('API 文档')
  const [mode, setMode] = useState<'swagger' | 'redoc'>('swagger')

  const src = mode === 'swagger' ? '/docs' : '/redoc'

  return (
    <div className="h-[calc(100vh-120px)] flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">API 文档</h1>
          <p className="text-sm text-slate-500 mt-0.5">OpenAPI 接口文档，支持在线调试</p>
        </div>
        <Radio.Group value={mode} onChange={(e) => setMode(e.target.value)} buttonStyle="solid" size="small">
          <Radio.Button value="swagger">Swagger UI</Radio.Button>
          <Radio.Button value="redoc">ReDoc</Radio.Button>
        </Radio.Group>
      </div>
      <div className="flex-1 rounded-xl border border-slate-200 overflow-hidden bg-white shadow-sm">
        <iframe
          key={mode}
          src={src}
          className="w-full h-full border-0"
          title="API Documentation"
        />
      </div>
    </div>
  )
}
