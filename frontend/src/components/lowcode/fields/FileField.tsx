// 附件/图片字段(file / image)。对齐简道云：虚线选择区 +「选择」+ 拖拽/粘贴提示 + 大小限制。
import { useEffect, useRef, useState } from 'react'
import { Modal, QRCode, Tooltip, message } from 'antd'
import {
  CloseCircleFilled, PaperClipOutlined, QrcodeOutlined,
} from '@ant-design/icons'
import { attachmentApi } from '@/api/attachment'
import {
  isMetaOnlyAttachmentId,
  normalizeFileFieldValue,
  type FileFieldAtt,
} from '@/utils/fileFieldValue'
import JdyUploadZone, { jdyMaxBytes } from '@/components/lowcode/fields/JdyUploadZone'

type Att = FileFieldAtt

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
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
  const [qrOpen, setQrOpen] = useState(false)
  const maxBytes = jdyMaxBytes(image)

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
      <JdyUploadZone
        image={image}
        uploading={uploading}
        onFiles={uploadMany}
        extraRight={image ? (
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
            电脑端也可直接拖拽、粘贴或点击「选择」（单张 {formatSize(jdyMaxBytes(true))} 以内）。
          </p>
        </div>
      </Modal>
    </div>
  )
}
