import { useEffect, useState, useCallback } from 'react'
import { message } from 'antd'
import { attachmentApi } from '@/api/attachment'
import AttachmentPreviewModal from '@/components/AttachmentPreviewModal'
import {
  isPreviewable,
  isBrowserUnsupportedPreview,
  canOpenAttachmentPreview,
  isBlobPreviewKind,
} from '@/utils/attachmentPreview'
import {
  downloadAttachmentFile,
  fetchAttachmentBlob,
  resolveAttachmentUrl,
  type AttachmentFileRow,
} from '@/utils/attachmentDisplay'
import { isMetaOnlyAttachmentId } from '@/utils/fileFieldValue'

/** 通用附件预览弹层 + 下载（对齐简道云 阅览/下载 节奏） */
export function useAttachmentPreview() {
  const [preview, setPreview] = useState<AttachmentFileRow | null>(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const [fileBlob, setFileBlob] = useState<Blob | null>(null)
  const [textContent, setTextContent] = useState('')
  const [loading, setLoading] = useState(false)

  const closePreview = useCallback(() => {
    setPreview(null)
    setPreviewUrl('')
    setFileBlob(null)
    setTextContent('')
  }, [])

  const openPreview = useCallback(async (item: AttachmentFileRow) => {
    if (item.metaOnly || isMetaOnlyAttachmentId(item.id)) {
      message.info('暂无文件实体，仅同步了简道云文件名')
      return
    }
    if (!canOpenAttachmentPreview(item.name, item.content_type)) {
      await downloadAttachmentFile(item.id, item.name)
      return
    }
    setPreview(item)
  }, [])

  useEffect(() => {
    if (!preview) {
      setPreviewUrl('')
      setFileBlob(null)
      setTextContent('')
      setLoading(false)
      return
    }

    const kind = isPreviewable(preview.content_type, preview.name)
    const unsupported = isBrowserUnsupportedPreview(preview.name, preview.content_type)

    if (unsupported || kind === false) {
      setPreviewUrl('')
      setFileBlob(null)
      setTextContent('')
      setLoading(false)
      return
    }

    let alive = true
    setLoading(true)
    setPreviewUrl('')
    setFileBlob(null)
    setTextContent('')

    void (async () => {
      try {
        if (isBlobPreviewKind(kind)) {
          const blob = await fetchAttachmentBlob(preview.id)
          if (!alive) return
          if (kind === 'text') {
            const text = await blob.text()
            setTextContent(text.slice(0, 500_000))
          } else {
            setFileBlob(blob)
          }
          return
        }
        const u = await attachmentApi.getUrl(preview.id, false)
        if (alive) setPreviewUrl(resolveAttachmentUrl(u))
      } catch {
        if (alive) message.error('无法加载预览')
        if (alive) setPreview(null)
      } finally {
        if (alive) setLoading(false)
      }
    })()

    return () => { alive = false }
  }, [preview])

  const download = useCallback(async (item: AttachmentFileRow) => {
    await downloadAttachmentFile(item.id, item.name)
  }, [])

  const previewKind = preview
    ? (isBrowserUnsupportedPreview(preview.name, preview.content_type)
      ? 'unsupported'
      : (isPreviewable(preview.content_type, preview.name) || false))
    : false

  const previewModal = (
    <AttachmentPreviewModal
      open={!!preview}
      title={preview?.name}
      url={previewUrl}
      kind={previewKind}
      fileBlob={fileBlob}
      textContent={textContent}
      fileName={preview?.name}
      loading={!!preview && loading}
      onClose={closePreview}
      onDownload={preview ? () => downloadAttachmentFile(preview.id, preview.name) : undefined}
    />
  )

  return { openPreview, download, closePreview, previewModal }
}
