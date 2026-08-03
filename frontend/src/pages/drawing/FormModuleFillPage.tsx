// 侧栏图纸模块「新增」：URL 仍在 /drawing-*/fill，侧栏高亮不丢。
import { useEffect, useState } from 'react'
import { Alert, Spin } from 'antd'
import { lowcodeApi } from '@/api/lowcode'
import FormFillPage from '@/pages/lowcode/FormFillPage'
import { usePageTitle } from '@/hooks/usePageTitle'

export default function FormModuleFillPage({
  templateCode,
  listPath,
  title,
}: {
  templateCode: string
  listPath: string
  title: string
}) {
  usePageTitle(`${title} · 新增`)
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
    <FormFillPage
      templateId={templateId}
      returnTo={listPath}
      pageTitle={`新增 · ${title}`}
      templateCode={templateCode}
    />
  )
}
