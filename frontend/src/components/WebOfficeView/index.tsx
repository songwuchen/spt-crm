/**
 * 阿里云 IMM WebOffice 预览（对齐 spt-lowcode）。
 * doc/ppt/wps/xlsx 等本地啃不动的格式走这里。
 */
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Button, Spin } from 'antd'
import { DownloadOutlined } from '@ant-design/icons'
import { attachmentApi } from '@/api/attachment'
import { loadWebOfficeSdk, type WebOfficeInstance } from './webofficeSdk'

const REFRESH_TIMEOUT = 25 * 60 * 1000

export default function WebOfficeView({
  attachmentId,
  noDownload = false,
  onDownload,
  fallback,
  height,
}: {
  attachmentId: string
  noDownload?: boolean
  onDownload?: () => void
  /** IMM 不可用时的退路（如 xlsx → 本地 excel 预览） */
  fallback?: ReactNode
  height: string
}) {
  const mountRef = useRef<HTMLDivElement>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    let ins: WebOfficeInstance | null = null

    void (async () => {
      try {
        const data = await attachmentApi.getWebOfficeToken(attachmentId, noDownload)
        if (cancelled) return
        if (!data.enabled || !data.url || !data.access_token) {
          const reason = data.reason
          setError(
            reason === 'not_configured'
              ? '未开通在线文档预览服务（IMM）'
              : reason === 'not_oss'
                ? '文件未存储在阿里云 OSS，无法使用在线预览'
                : '该文件类型暂不支持在线预览',
          )
          setLoading(false)
          return
        }
        const aliyun = await loadWebOfficeSdk()
        if (cancelled || !mountRef.current) return

        const cred = { access: data.access_token, refresh: data.refresh_token || '' }
        ins = aliyun.config({
          mount: mountRef.current,
          url: data.url,
          refreshToken: () => attachmentApi.refreshWebOfficeToken(cred.access, cred.refresh).then((r) => {
            cred.access = r.access_token || ''
            cred.refresh = r.refresh_token || ''
            return { token: cred.access, timeout: REFRESH_TIMEOUT }
          }),
        })
        ins.setToken({ token: cred.access, timeout: REFRESH_TIMEOUT })
        setLoading(false)
      } catch (e) {
        if (!cancelled) {
          setError((e as Error)?.message || '在线预览加载失败')
          setLoading(false)
        }
      }
    })()

    return () => {
      cancelled = true
      try { ins?.destroy?.() } catch { /* ignore */ }
    }
  }, [attachmentId, noDownload])

  if (error) {
    if (fallback) return <>{fallback}</>
    return (
      <div className="flex min-h-[240px] flex-col items-center justify-center px-6 py-10 text-center">
        <p className="mb-4 text-sm text-slate-600">{error}</p>
        {!noDownload && onDownload && (
          <Button type="primary" icon={<DownloadOutlined />} onClick={onDownload}>下载文件</Button>
        )}
      </div>
    )
  }

  return (
    <div className="relative overflow-hidden rounded border border-slate-100 bg-white" style={{ height, minHeight: 360 }}>
      {loading && (
        <div className="absolute inset-0 z-[1] flex items-center justify-center bg-white">
          <Spin size="large" />
        </div>
      )}
      <div ref={mountRef} style={{ height: '100%' }} />
    </div>
  )
}
