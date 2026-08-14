// 附件/图片字段(file / image)。对齐简道云：虚线选择区 +「选择」+ 拖拽/粘贴提示 + 大小限制。
import { useEffect, useRef, useState } from 'react'
import { Modal, QRCode, Spin, Tooltip, message } from 'antd'
import {
  CloseCircleFilled, PaperClipOutlined, QrcodeOutlined,
} from '@ant-design/icons'
import { attachmentApi } from '@/api/attachment'
import {
  isMetaOnlyAttachmentId,
  normalizeFileFieldValue,
  type FileFieldAtt,
} from '@/utils/fileFieldValue'

type Att = FileFieldAtt

const FILE_MAX = 50 * 1024 * 1024
const IMAGE_MAX = 20 * 1024 * 1024

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

/** 截图/复制文件多在 items 里，files 可能为空 */
function filesFromClipboard(data: DataTransfer | null | undefined): File[] {
  if (!data) return []
  const out: File[] = []
  const seen = new Set<string>()
  const push = (f: File | null) => {
    if (!f) return
    const key = `${f.name}|${f.size}|${f.type}|${f.lastModified}`
    if (seen.has(key)) return
    seen.add(key)
    out.push(f)
  }
  if (data.items?.length) {
    for (const item of Array.from(data.items)) {
      if (item.kind === 'file') push(item.getAsFile())
    }
  }
  if (!out.length && data.files?.length) {
    for (const f of Array.from(data.files)) push(f)
  }
  return out
}

export default function FileField({
  value, onChange, image, readonly, downloadDenied,
}: {
  value: unknown
  onChange: (v: unknown) => void
  image?: boolean
  readonly?: boolean
  downloadDenied?: boolean
}) {
  const atts: Att[] = normalizeFileFieldValue(value)
  const attsRef = useRef(atts)
  attsRef.current = atts
  const [urls, setUrls] = useState<Record<string, string>>({})
  const [uploading, setUploading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [focused, setFocused] = useState(false)
  const [qrOpen, setQrOpen] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const zoneRef = useRef<HTMLDivElement>(null)
  const maxBytes = image ? IMAGE_MAX : FILE_MAX
  const hint = image
    ? '拖拽或单击后粘贴图片，单张20MB以内'
    : '拖拽或单击后粘贴文件，单个50MB以内'

  useEffect(() => {
    if (!image || downloadDenied) return
    let alive = true
    ;(async () => {
      const next: Record<string, string> = {}
      for (const a of atts) {
        if (a.metaOnly || isMetaOnlyAttachmentId(a.id)) continue
        if (urls[a.id]) { next[a.id] = urls[a.id]; continue }
        try { next[a.id] = await attachmentApi.getUrl(a.id, false) } catch { /* ignore */ }
      }
      if (alive) setUrls(next)
    })()
    return () => { alive = false }
  }, [image, downloadDenied, JSON.stringify(atts.map((a) => a.id))]) // eslint-disable-line react-hooks/exhaustive-deps

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

  // 聚焦虚线区后，窗口级监听粘贴（截图走 items，比 div.onPaste 更稳）
  useEffect(() => {
    if (!focused || readonly || downloadDenied) return
    const onPaste = (e: ClipboardEvent) => {
      const files = filesFromClipboard(e.clipboardData)
      if (!files.length) return
      e.preventDefault()
      e.stopPropagation()
      void uploadMany(files)
    }
    window.addEventListener('paste', onPaste, true)
    return () => window.removeEventListener('paste', onPaste, true)
    // uploadMany 经 attsRef，无需列入依赖
  }, [focused, readonly, downloadDenied, image]) // eslint-disable-line react-hooks/exhaustive-deps

  if (downloadDenied) {
    return <div className="pt-1 text-slate-400 text-sm">无权限查看附件</div>
  }

  if (readonly) {
    if (!atts.length) return <div className="pt-1 text-slate-400">—</div>
    if (image) {
      return (
        <div className="flex flex-wrap gap-2 pt-1">
          {atts.map((a) => (
            <img
              key={a.id}
              src={urls[a.id]}
              alt={a.name}
              className="h-[72px] w-[72px] cursor-pointer rounded object-cover"
              onClick={() => openFile(a.id)}
            />
          ))}
        </div>
      )
    }
    return (
      <div className="space-y-1 pt-1">
        {atts.map((a) => (
          <div key={a.id}>
            <a onClick={() => openFile(a.id, true)} className="text-sm">
              <PaperClipOutlined /> {a.name}
            </a>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="w-full">
      <div className="flex items-stretch gap-2">
        <div
          ref={zoneRef}
          tabIndex={0}
          role="button"
          className={[
            'flex min-h-[40px] flex-1 cursor-text items-center gap-2 rounded border border-dashed px-3 py-2 outline-none transition-colors',
            dragOver || focused
              ? 'border-teal-500 bg-teal-50/60 ring-2 ring-teal-200'
              : 'border-slate-300 bg-white hover:border-teal-400',
          ].join(' ')}
          onClick={() => {
            // 单击区域：聚焦以便 Ctrl+V，不弹文件框（对齐简道云「单击后粘贴」）
            zoneRef.current?.focus()
          }}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              inputRef.current?.click()
            }
          }}
          onDragEnter={(e) => { e.preventDefault(); setDragOver(true) }}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragOver(false)
            void uploadMany(Array.from(e.dataTransfer.files || []))
          }}
        >
          <span
            className="shrink-0 cursor-pointer text-[13px] font-medium text-teal-600 hover:text-teal-700"
            onMouseDown={(e) => e.preventDefault()}
            onClick={(e) => {
              e.stopPropagation()
              inputRef.current?.click()
            }}
          >
            选择
          </span>
          <span className="min-w-0 flex-1 truncate text-[12px] text-slate-400">
            {focused ? (image ? '已选中，可 Ctrl+V 粘贴图片' : '已选中，可 Ctrl+V 粘贴文件') : hint}
          </span>
          {uploading && <Spin size="small" />}
          <input
            ref={inputRef}
            type="file"
            className="hidden"
            multiple
            accept={image ? 'image/*' : undefined}
            onChange={(e) => {
              const files = e.target.files
              if (files?.length) void uploadMany(Array.from(files))
              e.target.value = ''
            }}
          />
        </div>
        {image && (
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
        )}
      </div>

      {atts.length > 0 && (
        <ul className="mt-2 space-y-1.5">
          {atts.map((a) => (
            <li key={a.id} className="flex items-center gap-2 text-[13px] text-slate-700">
              {image && urls[a.id] ? (
                <img
                  src={urls[a.id]}
                  alt={a.name}
                  className="h-10 w-10 cursor-pointer rounded object-cover"
                  onClick={() => openFile(a.id)}
                />
              ) : (
                <PaperClipOutlined className="text-slate-400" />
              )}
              <a
                className="min-w-0 flex-1 truncate text-slate-700 hover:text-teal-600"
                onClick={() => openFile(a.id, !image)}
              >
                {a.name}
              </a>
              <CloseCircleFilled
                className="shrink-0 cursor-pointer text-slate-300 hover:text-rose-500"
                onClick={() => onChange(atts.filter((x) => x.id !== a.id))}
              />
            </li>
          ))}
        </ul>
      )}

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
            电脑端也可直接拖拽、粘贴或点击「选择」（单张 {formatSize(IMAGE_MAX)} 以内）。
          </p>
        </div>
      </Modal>
    </div>
  )
}
