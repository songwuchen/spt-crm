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
    message.info('暂无文件实体，仅同步了简道云文件名（缺少 OSS 对象 key）')
    return
  }
  try {
    const url = await attachmentApi.getUrl(id, true, filename)
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

/**
 * 拉取附件二进制（页内 Word / Excel / PPT / 文本预览）。
 *
 * 必须经本服务 `proxy=1` 转发，不能直接 fetch 对象存储预签名 URL：
 * 预签名地址跨域，且常见 OSS CORS 为 `ACAO:*`，与 `credentials: include` 不兼容，
 * 会导致「无法加载预览」（图片用 img、下载用 a 标签不受 CORS 限制）。
 */
/** 简道云历史 OSS 虚拟附件（jdy-oss:）或 CRM 正式附件 */
export function isResolvableAttachmentId(id: string | undefined | null): boolean {
  return !!id && !isMetaOnlyAttachmentId(id)
}

export async function fetchAttachmentBlob(id: string, filename?: string): Promise<Blob> {
  const token = localStorage.getItem('access_token')
  const qs = new URLSearchParams({ inline: '1', proxy: '1' })
  if (filename) qs.set('filename', filename)
  const res = await fetch(
    `/api/v1/attachments/${encodeURIComponent(id)}/download?${qs}`,
    {
      credentials: 'omit',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    },
  )
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const ct = (res.headers.get('content-type') || '').toLowerCase()
  if (ct.includes('application/json')) {
    const body = await res.json().catch(() => null) as { message?: string } | null
    throw new Error(body?.message || '无法加载预览')
  }
  return res.blob()
}
