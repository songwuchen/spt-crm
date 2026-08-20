import { message } from 'antd'
import { attachmentApi } from '@/api/attachment'
import { isMetaOnlyAttachmentId } from '@/utils/fileFieldValue'

/** 通用附件行（业务附件面板 / 低代码 file·image 字段只读表） */
export type AttachmentFileRow = {
  id: string
  name: string
  metaOnly?: boolean
  content_type?: string
  file_size?: number
  uploader_name?: string
  created_at?: string
}

export function formatAttachmentSize(bytes?: number): string {
  if (bytes == null || bytes <= 0) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export function formatAttachmentTime(v?: string): string {
  if (!v) return '—'
  const d = new Date(v)
  return Number.isNaN(d.getTime()) ? v : d.toLocaleString('zh-CN')
}

export async function downloadAttachmentFile(id: string, filename?: string): Promise<void> {
  if (isMetaOnlyAttachmentId(id)) {
    message.info('暂无文件实体，仅同步了简道云文件名')
    return
  }
  try {
    const url = await attachmentApi.getUrl(id, true)
    const a = document.createElement('a')
    a.href = resolveAttachmentUrl(url)
    a.target = '_blank'
    a.rel = 'noreferrer'
    if (filename) a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  } catch {
    message.error('下载失败')
  }
}

/** 相对路径转绝对 URL（本地存储预览/下载链接） */
export function resolveAttachmentUrl(url: string): string {
  if (!url || url.startsWith('http://') || url.startsWith('https://') || url.startsWith('blob:')) {
    return url
  }
  return `${window.location.origin}${url.startsWith('/') ? '' : '/'}${url}`
}

/** 拉取附件二进制（页内 Word / 文本预览） */
export async function fetchAttachmentBlob(id: string): Promise<Blob> {
  const url = await attachmentApi.getUrl(id, false)
  const res = await fetch(resolveAttachmentUrl(url), { credentials: 'include' })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.blob()
}
