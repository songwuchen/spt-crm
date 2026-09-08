import { useEffect, useState, useCallback } from 'react'
import { message } from 'antd'
import { attachmentApi } from '@/api/attachment'
import AttachmentPreviewModal from '@/components/AttachmentPreviewModal'
import {
  isPreviewable,
  isBrowserUnsupportedPreview,
  canOpenAttachmentPreview,
  isBlobPreviewKind,
  attachmentFileExt,
  WEBOFFICE_EXCEL_FALLBACK,
  WEBOFFICE_PPTX_FALLBACK,
} from '@/utils/attachmentPreview'
import {
  downloadAttachmentFile,
  fetchAttachmentBlob,
  resolveAttachmentUrl,
  type AttachmentFileRow,
} from '@/utils/attachmentDisplay'
import { shortAttachmentDisplayName } from '@/utils/attachmentDisplayName'
import { isMetaOnlyAttachmentId } from '@/utils/fileFieldValue'

type GalleryState = {
  items: AttachmentFileRow[]
  index: number
} | null

/** 通用附件预览弹层 + 下载；支持多图上一张/下一张 */
export function useAttachmentPreview() {
  const [gallery, setGallery] = useState<GalleryState>(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const [fileBlob, setFileBlob] = useState<Blob | null>(null)
  const [textContent, setTextContent] = useState('')
  const [loading, setLoading] = useState(false)

  const preview = gallery?.items[gallery.index] ?? null

  const closePreview = useCallback(() => {
    setGallery(null)
    setPreviewUrl('')
    setFileBlob(null)
    setTextContent('')
  }, [])

  const openItem = useCallback((item: AttachmentFileRow, items?: AttachmentFileRow[], index?: number) => {
    if (item.metaOnly || isMetaOnlyAttachmentId(item.id)) {
      message.info('暂无文件实体，仅同步了简道云文件名（缺少 OSS 对象 key）')
      return
    }
    if (!canOpenAttachmentPreview(item.name, item.content_type)) {
      void downloadAttachmentFile(item.id, item.name)
      return
    }
    const list = items?.length ? items : [item]
    const idx = index ?? list.findIndex((x) => x.id === item.id)
    setGallery({ items: list, index: idx >= 0 ? idx : 0 })
  }, [])

  const openPreview = useCallback((item: AttachmentFileRow) => {
    openItem(item)
  }, [openItem])

  const openGallery = useCallback((items: AttachmentFileRow[], index: number) => {
    const row = items[index]
    if (!row) return
    openItem(row, items, index)
  }, [openItem])

  const stepGallery = useCallback((delta: number) => {
    setGallery((g) => {
      if (!g || g.items.length <= 1) return g
      const next = (g.index + delta + g.items.length) % g.items.length
      return { ...g, index: next }
    })
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

    if (kind === 'weboffice') {
      const ext = attachmentFileExt(preview.name)
      const needFallbackBlob = WEBOFFICE_EXCEL_FALLBACK.has(ext) || WEBOFFICE_PPTX_FALLBACK.has(ext)
      let alive = true
      setLoading(true)
      setPreviewUrl('')
      setFileBlob(null)
      setTextContent('')
      void (async () => {
        try {
          if (needFallbackBlob) {
            const blob = await fetchAttachmentBlob(preview.id)
            if (alive) setFileBlob(blob)
          }
        } catch { /* ignore */ }
        finally {
          if (alive) setLoading(false)
        }
      })()
      return () => { alive = false }
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
      } catch (e) {
        if (alive) message.error((e as Error)?.message || '无法加载预览')
        if (alive) setGallery(null)
      } finally {
        if (alive) setLoading(false)
      }
    })()

    return () => { alive = false }
  }, [preview?.id, preview?.name, preview?.content_type])

  useEffect(() => {
    if (!gallery || gallery.items.length <= 1) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft') stepGallery(-1)
      if (e.key === 'ArrowRight') stepGallery(1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [gallery, stepGallery])

  const download = useCallback(async (item: AttachmentFileRow) => {
    await downloadAttachmentFile(item.id, item.name)
  }, [])

  const previewKind = preview
    ? (isBrowserUnsupportedPreview(preview.name, preview.content_type)
      ? 'unsupported'
      : (isPreviewable(preview.content_type, preview.name) || false))
    : false

  const galleryTotal = gallery?.items.length ?? 0
  const galleryIndex = gallery?.index ?? 0

  const previewModal = (
    <AttachmentPreviewModal
      open={!!preview}
      title={preview ? shortAttachmentDisplayName(preview.name, galleryIndex) : undefined}
      url={previewUrl}
      kind={previewKind}
      fileBlob={fileBlob}
      textContent={textContent}
      fileName={preview?.name}
      attachmentId={preview?.id}
      loading={!!preview && loading}
      onClose={closePreview}
      onDownload={preview ? () => downloadAttachmentFile(preview.id, preview.name) : undefined}
      galleryIndex={galleryTotal > 1 ? galleryIndex : undefined}
      galleryTotal={galleryTotal > 1 ? galleryTotal : undefined}
      onGalleryPrev={galleryTotal > 1 ? () => stepGallery(-1) : undefined}
      onGalleryNext={galleryTotal > 1 ? () => stepGallery(1) : undefined}
    />
  )

  return { openPreview, openGallery, download, closePreview, previewModal }
}
