import { useEffect, useState } from 'react'
import { Modal, Button, Space } from 'antd'
import { DownloadOutlined, FullscreenOutlined, FullscreenExitOutlined } from '@ant-design/icons'
import OfficeFilePreview from '@/components/OfficeFilePreview'
import WebOfficeView from '@/components/WebOfficeView'
import type { PreviewableKind } from '@/utils/attachmentPreview'
import {
  attachmentFileExt,
  WEBOFFICE_EXCEL_FALLBACK,
  WEBOFFICE_PPTX_FALLBACK,
} from '@/utils/attachmentPreview'

type Props = {
  open: boolean
  title?: string
  url: string
  kind: PreviewableKind | false
  fileBlob?: Blob | null
  textContent?: string
  fileName?: string
  attachmentId?: string
  loading?: boolean
  onClose: () => void
  onDownload?: () => void
}

function pdfViewerSrc(url: string): string {
  if (!url) return url
  return `${url.split('#')[0]}#view=FitH&toolbar=1`
}

function unsupportedHint(fileName?: string): { title: string; detail: string } {
  const ext = (fileName || '').split('.').pop()?.toLowerCase() || ''
  const cad = new Set(['dwg', 'dxf', 'dwt', 'dwf', 'step', 'stp'])
  if (cad.has(ext)) {
    return {
      title: 'CAD 图纸暂不支持浏览器内直接预览',
      detail: '请下载后使用 AutoCAD、浩辰 CAD 或 DWG 查看器打开。',
    }
  }
  if (ext === 'doc') {
    return {
      title: '旧版 Word（.doc）暂无法在线阅览',
      detail: '请确认已开通阿里云 IMM，且文件存储在 OSS；或下载后用 Word / WPS 打开。',
    }
  }
  if (ext === 'ppt') {
    return {
      title: '旧版 PowerPoint（.ppt）暂无法在线阅览',
      detail: '请确认已开通阿里云 IMM；或下载后用 PowerPoint / WPS 打开。',
    }
  }
  return {
    title: '此格式暂不支持在线阅览',
    detail: '请下载到本地查看。',
  }
}

/** 页内预览附件；支持放大与全屏。 */
export default function AttachmentPreviewModal({
  open, title, url, kind, fileBlob, textContent, fileName, attachmentId,
  loading, onClose, onDownload,
}: Props) {
  const [fullscreen, setFullscreen] = useState(false)

  useEffect(() => {
    if (!open) setFullscreen(false)
  }, [open])

  const contentHeight = fullscreen
    ? 'calc(100vh - 108px)'
    : (kind === 'pdf' || kind === 'weboffice' ? 'min(88vh, 920px)' : 'min(82vh, 800px)')

  const officeKind = kind === 'word' || kind === 'excel' || kind === 'pptx' ? kind : null
  const hasOffice = !!(officeKind && fileBlob)
  const ext = attachmentFileExt(fileName)
  const webofficeFallbackKind = WEBOFFICE_EXCEL_FALLBACK.has(ext)
    ? 'excel' as const
    : (WEBOFFICE_PPTX_FALLBACK.has(ext) ? 'pptx' as const : null)

  const footer = (
    <Space>
      {kind && kind !== 'unsupported' && (
        <Button
          icon={fullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
          onClick={() => setFullscreen((v) => !v)}
          disabled={loading || (officeKind ? !hasOffice : (kind === 'weboffice' ? false : !url))}
        >
          {fullscreen ? '退出全屏' : '全屏'}
        </Button>
      )}
      {onDownload && (
        <Button type="primary" icon={<DownloadOutlined />} onClick={onDownload} disabled={loading}>
          下载
        </Button>
      )}
    </Space>
  )

  const hint = unsupportedHint(fileName)
  const wide = kind === 'pdf' || kind === 'weboffice' || officeKind || kind === 'text'

  return (
    <Modal
      title={title || '在线阅览'}
      open={open}
      onCancel={onClose}
      footer={footer}
      width={fullscreen ? '100vw' : (wide ? 'min(96vw, 1280px)' : 920)}
      centered={!fullscreen}
      destroyOnClose
      styles={{
        body: {
          padding: fullscreen ? 8 : 16,
          height: kind === 'unsupported' ? undefined : contentHeight,
          overflow: kind === 'unsupported' ? 'visible' : 'hidden',
        },
        content: fullscreen
          ? {
              height: '100vh',
              maxHeight: '100vh',
              margin: 0,
              borderRadius: 0,
              display: 'flex',
              flexDirection: 'column',
            }
          : undefined,
      }}
      style={fullscreen ? { top: 0, padding: 0, maxWidth: '100vw' } : { maxWidth: '96vw' }}
      wrapClassName={fullscreen ? 'attachment-preview-modal-fullscreen' : undefined}
    >
      {loading && kind !== 'weboffice' && (
        <div className="flex h-full min-h-[240px] items-center justify-center text-slate-400">加载中…</div>
      )}
      {!loading && kind === 'unsupported' && (
        <div className="py-10 px-6 text-center">
          <p className="text-base font-medium text-slate-800 mb-2">{hint.title}</p>
          <p className="text-sm text-slate-500 mb-0">{hint.detail}</p>
        </div>
      )}
      {!loading && kind === 'image' && url && (
        <div className="flex h-full items-center justify-center overflow-auto bg-slate-50/80">
          <img
            src={url}
            alt={title || '预览'}
            className="max-h-full max-w-full object-contain"
            style={{ maxHeight: contentHeight }}
          />
        </div>
      )}
      {!loading && kind === 'pdf' && url && (
        <iframe
          src={pdfViewerSrc(url)}
          title={title || 'PDF 预览'}
          className="h-full w-full rounded border-0 bg-[#525659]"
          style={{ height: contentHeight, minHeight: fullscreen ? 'calc(100vh - 108px)' : 520 }}
        />
      )}
      {!loading && officeKind && fileBlob && (
        <OfficeFilePreview kind={officeKind} blob={fileBlob} height={contentHeight} />
      )}
      {kind === 'weboffice' && attachmentId && (
        <WebOfficeView
          attachmentId={attachmentId}
          height={contentHeight}
          onDownload={onDownload}
          fallback={
            webofficeFallbackKind && fileBlob
              ? <OfficeFilePreview kind={webofficeFallbackKind} blob={fileBlob} height={contentHeight} />
              : undefined
          }
        />
      )}
      {!loading && kind === 'text' && textContent != null && (
        <pre
          className="h-full overflow-auto rounded border border-slate-100 bg-slate-50 p-4 text-[13px] leading-relaxed text-slate-800 whitespace-pre-wrap break-all"
          style={{ height: contentHeight, minHeight: 240, margin: 0 }}
        >
          {textContent || '（空文件）'}
        </pre>
      )}
    </Modal>
  )
}
