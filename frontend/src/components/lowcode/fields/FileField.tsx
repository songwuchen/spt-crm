// 附件/图片字段(file / image)。对齐简道云：虚线选择区 +「选择」+ 拖拽/粘贴 + 页内预览。
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Image, Modal, Popover, QRCode, Tooltip, message } from 'antd'
import {
  CloseCircleFilled, EyeOutlined, PaperClipOutlined, PictureOutlined, QrcodeOutlined,
} from '@ant-design/icons'
import { attachmentApi } from '@/api/attachment'
import AttachmentPreviewModal from '@/components/AttachmentPreviewModal'
import {
  isMetaOnlyAttachmentId,
  normalizeFileFieldValue,
  type FileFieldAtt,
} from '@/utils/fileFieldValue'
import { isPreviewable } from '@/utils/attachmentPreview'
import JdyUploadZone, { jdyMaxBytes } from '@/components/lowcode/fields/JdyUploadZone'

type Att = FileFieldAtt

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export default function FileField({
  value, onChange, image, readonly, downloadDenied, compact, displayMode = 'full', maxCount,
}: {
  value: unknown
  onChange: (v: unknown) => void
  image?: boolean
  readonly?: boolean
  downloadDenied?: boolean
  compact?: boolean
  /** 明细表单元格：简道云 Popover 内上传，单元格横排缩略图 */
  displayMode?: 'full' | 'popover'
  /** 最多几张（来自字段 props.max_file_count） */
  maxCount?: number
}) {
  const inCellPopover = displayMode === 'popover'
  const atts: Att[] = normalizeFileFieldValue(value)
  const attsRef = useRef(atts)
  attsRef.current = atts
  const [urls, setUrls] = useState<Record<string, string>>({})

  const [uploading, setUploading] = useState(false)
  const [qrOpen, setQrOpen] = useState(false)
  const [imagePreview, setImagePreview] = useState<{ url: string; name: string } | null>(null)
  const [docPreview, setDocPreview] = useState<{ id: string; name: string; kind: 'image' | 'pdf' } | null>(null)
  const [docPreviewUrl, setDocPreviewUrl] = useState('')
  const [docPreviewLoading, setDocPreviewLoading] = useState(false)
  const [popoverOpen, setPopoverOpen] = useState(false)
  const maxBytes = jdyMaxBytes(image)

  useEffect(() => {
    if (downloadDenied) return
    let alive = true
    ;(async () => {
      const next: Record<string, string> = { ...urls }
      for (const a of atts) {
        if (a.metaOnly || isMetaOnlyAttachmentId(a.id)) continue
        if (next[a.id]) continue
        const kind = isPreviewable(undefined, a.name)
        if (!image && kind !== 'image' && !inCellPopover) continue
        try { next[a.id] = await attachmentApi.getUrl(a.id, false) } catch { /* ignore */ }
      }
      if (alive) setUrls(next)
    })()
    return () => { alive = false }
  }, [image, inCellPopover, downloadDenied, JSON.stringify(atts.map((a) => a.id))]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!docPreview) {
      setDocPreviewUrl('')
      setDocPreviewLoading(false)
      return
    }
    let alive = true
    setDocPreviewLoading(true)
    setDocPreviewUrl('')
    attachmentApi.getUrl(docPreview.id, false)
      .then((u) => { if (alive) setDocPreviewUrl(u) })
      .catch(() => { if (alive) message.error('无法加载预览') })
      .finally(() => { if (alive) setDocPreviewLoading(false) })
    return () => { alive = false }
  }, [docPreview])

  const openFile = async (id: string, download = false) => {
    if (downloadDenied) {
      message.warning('无权限查看附件')
      return
    }
    if (isMetaOnlyAttachmentId(id)) {
      message.info('暂无文件实体，仅同步了简道云文件名')
      return
    }
    try {
      const u = await attachmentApi.getUrl(id, download)
      window.open(u, '_blank')
    } catch {
      message.error('获取文件地址失败')
    }
  }

  const openPreview = async (a: Att) => {
    if (downloadDenied) {
      message.warning('无权限查看附件')
      return
    }
    if (isMetaOnlyAttachmentId(a.id)) {
      message.info('暂无文件实体，仅同步了简道云文件名')
      return
    }
    const kind = isPreviewable(undefined, a.name)
    if (!kind) {
      await openFile(a.id, false)
      return
    }
    if (kind === 'image') {
      let url = urls[a.id]
      if (!url) {
        try {
          url = await attachmentApi.getUrl(a.id, false)
          setUrls((prev) => ({ ...prev, [a.id]: url }))
        } catch {
          message.error('无法加载预览')
          return
        }
      }
      setImagePreview({ url, name: a.name })
      return
    }
    setDocPreview({ id: a.id, name: a.name, kind: 'pdf' })
  }

  const uploadOne = async (file: File) => {
    if (downloadDenied) {
      message.warning('无权限上传附件')
      return
    }
    if (image && !file.type.startsWith('image/')) {
      message.warning('请选择图片文件')
      return
    }
    if (file.size > maxBytes) {
      message.warning(image ? '单张图片不能超过 20MB' : '单个文件不能超过 50MB')
      return
    }
    if (maxCount != null && attsRef.current.length >= maxCount) {
      message.warning(`最多上传 ${maxCount} 个文件`)
      return
    }
    setUploading(true)
    try {
      const res = await attachmentApi.upload(file)
      const next = [...attsRef.current, { id: res.data.id, name: file.name || (image ? '粘贴图片.png' : '粘贴文件') }]
      attsRef.current = next
      onChange(next)
    } catch (e) {
      message.error('上传失败: ' + ((e as Error).message || '未知错误'))
    } finally {
      setUploading(false)
    }
  }

  const uploadMany = async (files: File[]) => {
    if (!files.length) return
    for (const f of files) await uploadOne(f)
  }

  const removeAtt = (id: string) => onChange(atts.filter((x) => x.id !== id))

  const renderThumb = (a: Att, size: number) => {
    const url = urls[a.id]
    if (!url) {
      return <PaperClipOutlined className="text-slate-400" />
    }
    return (
      <Image
        src={url}
        alt={a.name}
        width={size}
        height={size}
        className="cursor-pointer rounded object-cover"
        preview={false}
        onClick={() => openPreview(a)}
      />
    )
  }

  const renderFileRow = (a: Att, editable: boolean) => {
    const previewable = !!isPreviewable(undefined, a.name)
    return (
      <li key={a.id} className="flex min-h-9 items-center gap-2 px-2 py-1.5 text-[13px] text-slate-700">
        {(image || isPreviewable(undefined, a.name) === 'image') && urls[a.id]
          ? renderThumb(a, compact ? 32 : 40)
          : <PaperClipOutlined className="text-slate-400" />}
        <a
          className="min-w-0 flex-1 truncate text-slate-700 hover:text-teal-600"
          onClick={() => (previewable ? openPreview(a) : openFile(a.id, !image))}
        >
          {a.name}
        </a>
        {previewable && (
          <Tooltip title="预览">
            <EyeOutlined
              className="shrink-0 cursor-pointer text-slate-400 hover:text-teal-600"
              onClick={() => openPreview(a)}
            />
          </Tooltip>
        )}
        {editable && (
          <CloseCircleFilled
            className="shrink-0 cursor-pointer text-slate-300 hover:text-rose-500"
            onClick={() => removeAtt(a.id)}
          />
        )}
      </li>
    )
  }

  const imageLightbox = imagePreview ? (
    <Image
      wrapperStyle={{ display: 'none' }}
      src={imagePreview.url}
      preview={{
        visible: true,
        src: imagePreview.url,
        onVisibleChange: (v) => { if (!v) setImagePreview(null) },
      }}
    />
  ) : null

  const docLightbox = (
    <AttachmentPreviewModal
      open={!!docPreview}
      title={docPreview?.name}
      url={docPreviewUrl}
      kind={docPreview?.kind || false}
      loading={docPreviewLoading}
      onClose={() => setDocPreview(null)}
    />
  )

  const renderCellThumbs = (maxVisible = 8, size = 24) => {
    if (!atts.length) {
      return image ? (
        <PictureOutlined className="shrink-0 text-base text-slate-400" />
      ) : (
        <PaperClipOutlined className="shrink-0 text-slate-400" />
      )
    }
    const visible = atts.slice(0, maxVisible)
    const extra = atts.length - visible.length
    return (
      <>
        {visible.map((a) => (
          urls[a.id] ? (
            <Image
              key={a.id}
              src={urls[a.id]}
              alt={a.name}
              width={size}
              height={size}
              className="shrink-0 rounded object-cover"
              preview={false}
            />
          ) : (
            <span key={a.id} className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded bg-slate-100">
              <PaperClipOutlined className="text-[11px] text-slate-400" />
            </span>
          )
        ))}
        {extra > 0 && (
          <span className="shrink-0 text-[11px] text-slate-500">+{extra}</span>
        )}
      </>
    )
  }

  const cellTriggerShell = (children: ReactNode) => (
    <div
      role="button"
      tabIndex={0}
      className="flex min-h-9 min-w-[120px] max-w-[320px] cursor-pointer items-center gap-1.5 rounded border border-slate-200 bg-white px-1.5 py-1 text-left outline-none hover:border-teal-400"
    >
      <div className="flex min-w-0 flex-1 flex-wrap items-center gap-1">
        {children}
      </div>
      {image && atts.length > 0 ? (
        <PictureOutlined className="shrink-0 text-base text-slate-300" />
      ) : null}
    </div>
  )

  if (downloadDenied) {
    return <div className="pt-1 text-slate-400 text-sm">无权限查看附件</div>
  }

  if (readonly && inCellPopover) {
    if (!atts.length) return <TextPlaceholder />
    return (
      <>
        {cellTriggerShell(
          atts.map((a) => (
            <div key={a.id} className="shrink-0 cursor-pointer" onClick={() => openPreview(a)}>
              {urls[a.id] ? (
                <Image src={urls[a.id]} alt={a.name} width={24} height={24} className="rounded object-cover" preview={false} />
              ) : (
                <PaperClipOutlined className="text-slate-400" />
              )}
            </div>
          )),
        )}
        {imageLightbox}
        {docLightbox}
      </>
    )
  }

  if (readonly) {
    if (!atts.length) return <div className="pt-1 text-slate-400">—</div>
    if (image) {
      return (
        <>
          <div className="flex flex-wrap gap-2 pt-1">
            {atts.map((a) => (
              <div key={a.id} onClick={() => openPreview(a)} className="cursor-pointer">
                {urls[a.id] ? (
                  <Image
                    src={urls[a.id]}
                    alt={a.name}
                    width={72}
                    height={72}
                    className="rounded object-cover"
                    preview={false}
                  />
                ) : (
                  <div className="flex h-[72px] w-[72px] items-center justify-center rounded bg-slate-100 text-slate-400">
                    <PaperClipOutlined />
                  </div>
                )}
              </div>
            ))}
          </div>
          {imageLightbox}
          {docLightbox}
        </>
      )
    }
    return (
      <>
        <ul className="space-y-1 pt-1">
          {atts.map((a) => renderFileRow(a, false))}
        </ul>
        {imageLightbox}
        {docLightbox}
      </>
    )
  }

  const editorPanel = (
    <div className="w-[min(360px,calc(100vw-32px))] py-0.5" onClick={(e) => e.stopPropagation()} onMouseDown={(e) => e.stopPropagation()}>
      <JdyUploadZone
        image={image}
        inCellPopover={inCellPopover}
        uploading={uploading}
        onFiles={uploadMany}
        extraRight={image ? (
          <Tooltip title="手机扫码上传">
            <button
              type="button"
              className="flex size-full min-h-10 min-w-10 items-center justify-center rounded border border-dashed border-slate-300 bg-white text-slate-600 hover:border-teal-400 hover:text-teal-600"
              onClick={(e) => {
                e.stopPropagation()
                setQrOpen(true)
              }}
              aria-label="扫码上传"
            >
              <QrcodeOutlined className="text-lg" />
            </button>
          </Tooltip>
        ) : undefined}
      />
      {atts.length > 0 && (
        <ul className="mt-2 max-h-40 divide-y divide-slate-100 overflow-y-auto rounded border border-slate-100">
          {atts.map((a) => renderFileRow(a, true))}
        </ul>
      )}
    </div>
  )

  if (inCellPopover) {
    const trigger = cellTriggerShell(renderCellThumbs())
    return (
      <>
        <Popover
          open={popoverOpen}
          onOpenChange={setPopoverOpen}
          content={editorPanel}
          trigger="click"
          placement="bottomLeft"
          destroyOnHidden
        >
          {trigger}
        </Popover>
        {imageLightbox}
        {docLightbox}
        <Modal
          title="手机扫码上传"
          open={qrOpen}
          onCancel={() => setQrOpen(false)}
          footer={null}
          centered
          width={360}
        >
          <div className="flex flex-col items-center gap-3 py-2 text-center">
            <QRCode value={typeof window !== 'undefined' ? window.location.href : 'spt-crm'} size={168} />
            <p className="m-0 text-[13px] text-slate-500">请用手机浏览器打开本页后选择或拍摄图片上传。</p>
          </div>
        </Modal>
      </>
    )
  }

  return (
    <div className="min-w-0 max-w-full overflow-hidden">
      <JdyUploadZone
        image={image}
        compact={compact}
        uploading={uploading}
        onFiles={uploadMany}
        extraRight={!compact && image ? (
          <Tooltip title="手机扫码上传">
            <button
              type="button"
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded border border-dashed border-slate-300 bg-white text-slate-600 hover:border-teal-400 hover:text-teal-600"
              onClick={(e) => {
                e.stopPropagation()
                setQrOpen(true)
              }}
              aria-label="扫码上传"
            >
              <QrcodeOutlined className="text-lg" />
            </button>
          </Tooltip>
        ) : undefined}
      />

      {atts.length > 0 && (
        <ul className="mt-2 space-y-1.5">
          {atts.map((a) => renderFileRow(a, true))}
        </ul>
      )}

      {imageLightbox}
      {docLightbox}

      <Modal
        title="手机扫码上传"
        open={qrOpen}
        onCancel={() => setQrOpen(false)}
        footer={null}
        centered
        width={360}
      >
        <div className="flex flex-col items-center gap-3 py-2 text-center">
          <QRCode value={typeof window !== 'undefined' ? window.location.href : 'spt-crm'} size={168} />
          <p className="m-0 text-[13px] text-slate-500">
            请用手机浏览器打开本页后选择或拍摄图片上传。
          </p>
          <p className="m-0 text-[12px] text-slate-400">
            电脑端也可直接拖拽、粘贴或点击「选择」（单张 {formatSize(jdyMaxBytes(true))} 以内）。
          </p>
        </div>
      </Modal>
    </div>
  )
}

function TextPlaceholder() {
  return <span className="text-[13px] text-slate-400">—</span>
}
