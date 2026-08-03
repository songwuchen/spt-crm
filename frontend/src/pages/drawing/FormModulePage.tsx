// 侧栏业务入口 → 低代码表单模块：ensure 内置模板后展示数据列表。
import { useEffect, useState } from 'react'
import { Alert, Spin } from 'antd'
import { lowcodeApi } from '@/api/lowcode'
import FormDataListPage from '@/pages/lowcode/FormDataListPage'
import { usePageTitle } from '@/hooks/usePageTitle'

export default function FormModulePage({
  templateCode,
  title,
  basePath,
}: {
  templateCode: string
  title: string
  /** 侧栏路由前缀，如 /drawing-requisitions；新增走 basePath/fill */
  basePath: string
}) {
  usePageTitle(title)
  const [templateId, setTemplateId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setTemplateId(null)
    setError(null)
    ;(async () => {
      try {
        const res = await lowcodeApi.ensureBuiltin(templateCode)
        if (!cancelled) setTemplateId(res.data.id)
      } catch (e: unknown) {
        const msg = (e as { response?: { data?: { message?: string } } })?.response?.data?.message
        if (!cancelled) setError(msg || '加载表单失败')
      }
    })()
    return () => { cancelled = true }
  }, [templateCode])

  if (error) {
    return (
      <Alert
        type="error"
        showIcon
        message={title}
        description={error}
        className="m-4"
      />
    )
  }
  if (!templateId) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-3 text-slate-500">
        <Spin size="large" />
        <span>正在准备「{title}」…</span>
      </div>
    )
  }
  return (
    <FormDataListPage
      templateId={templateId}
      moduleTitle={title}
      fillPath={`${basePath.replace(/\/$/, '')}/fill`}
      templateCode={templateCode}
    />
  )
}
