/** 附件是否可在页内预览（图片 / PDF）。低代码 FileField、AttachmentPanel 共用。 */
export type PreviewableKind = 'image' | 'pdf'

export function isPreviewable(contentType?: string, name?: string): PreviewableKind | false {
  if (!contentType && !name) return false
  const ct = (contentType || '').toLowerCase()
  const ext = (name || '').split('.').pop()?.toLowerCase()
  if (ct.startsWith('image/') || ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp'].includes(ext || '')) {
    return 'image'
  }
  if (ct === 'application/pdf' || ext === 'pdf') return 'pdf'
  return false
}
