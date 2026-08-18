/** 全局 PDF 预览（对齐简道云：暗色遮罩 + 文件名 + 下载/关闭 + 内嵌 PDF 查看器）。 */
import { useEffect, useState } from 'react'
import { Button, Spin } from 'antd'
import { CloseOutlined, DownloadOutlined } from '@ant-design/icons'

export type PdfPreviewState = {
  blobUrl: string
  fileName: string
  blob?: Blob
  /** 当前份数序号，默认 1 */
  index?: number
  /** 总份数，默认 1 */
  total?: number
  loading?: boolean
} | null

type Listener = (s: PdfPreviewState) => void

const listeners = new Set<Listener>()
let current: PdfPreviewState = null

function emit(s: PdfPreviewState) {
  current = s
  listeners.forEach((fn) => fn(s))
}

export function subscribePdfPreview(fn: Listener): () => void {
  listeners.add(fn)
  fn(current)
  return () => { listeners.delete(fn) }
}

/** 打开预览；传入 Blob 会自动创建 object URL。 */
export function openPdfPreview(blob: Blob, fileName: string, opts?: { index?: number; total?: number }) {
  const name = fileName.replace(/\.pdf$/i, '') + '.pdf'
  const blobUrl = URL.createObjectURL(blob)
  const prev = current?.blobUrl
  emit({
    blobUrl,
    fileName: name,
    blob,
    index: opts?.index ?? 1,
    total: opts?.total ?? 1,
  })
  if (prev) {
    try { URL.revokeObjectURL(prev) } catch { /* ignore */ }
  }
}

export function setPdfPreviewLoading(loading: boolean, fileName = '生成中…') {
  if (loading) {
    emit({
      blobUrl: '',
      fileName: fileName.endsWith('.pdf') ? fileName : `${fileName}.pdf`,
      index: 1,
      total: 1,
      loading: true,
    })
    return
  }
  closePdfPreview()
}

export function closePdfPreview() {
  const prev = current?.blobUrl
  emit(null)
  if (prev) {
    try { URL.revokeObjectURL(prev) } catch { /* ignore */ }
  }
}

function downloadNamedPdf(blob: Blob, fileName: string) {
  const name = (fileName.replace(/\.pdf$/i, '') || 'download') + '.pdf'
  const file = new File([blob], name, { type: 'application/pdf' })
  const href = URL.createObjectURL(file)
  const a = document.createElement('a')
  a.href = href
  a.download = name
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  window.setTimeout(() => {
    try { URL.revokeObjectURL(href) } catch { /* ignore */ }
  }, 2000)
}

function downloadBlobUrl(url: string, fileName: string) {
  const a = document.createElement('a')
  a.href = url
  a.download = fileName
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

/** 挂在 App 根上即可，业务侧调用 openPdfPreview。 */
export function PdfPreviewHost() {
  const [state, setState] = useState<PdfPreviewState>(current)

  useEffect(() => subscribePdfPreview(setState), [])

  useEffect(() => {
    if (!state) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closePdfPreview()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [state])

  if (!state) return null

  const idx = state.index ?? 1
  const total = state.total ?? 1
  const title = `${idx}/${total} ${state.fileName}`

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1100,
        background: 'rgba(0,0,0,.72)',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <div
        style={{
          height: 48,
          flex: '0 0 auto',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
          padding: '0 16px',
          color: '#fff',
          background: 'rgba(0,0,0,.45)',
        }}
      >
        <div style={{ fontSize: 14, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {title}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
          <Button
            type="primary"
            icon={<DownloadOutlined />}
            disabled={!!state.loading || !state.blobUrl}
            onClick={() => {
              if (state.blob) downloadNamedPdf(state.blob, state.fileName)
              else if (state.blobUrl) downloadBlobUrl(state.blobUrl, state.fileName)
            }}
          >
            下载
          </Button>
          <Button
            type="text"
            icon={<CloseOutlined style={{ color: '#fff', fontSize: 16 }} />}
            onClick={closePdfPreview}
            aria-label="关闭"
            style={{ color: '#fff' }}
          />
        </div>
      </div>

      <div style={{ flex: 1, minHeight: 0, position: 'relative', background: '#525659' }}>
        {state.loading || !state.blobUrl ? (
          <div style={{
            position: 'absolute', inset: 0,
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            color: '#fff', gap: 12,
          }}>
            <Spin size="large" />
            <span style={{ fontSize: 14 }}>正在生成 PDF…</span>
          </div>
        ) : (
          <iframe
            title={state.fileName}
            src={`${state.blobUrl}#toolbar=0&navpanes=0`}
            style={{ width: '100%', height: '100%', border: 0, background: '#525659' }}
          />
        )}
      </div>
    </div>
  )
}
