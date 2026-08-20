/** 附件页内预览类型。低代码 FileField、AttachmentPanel 共用。 */
export type PreviewableKind =
  | 'image'
  | 'pdf'
  | 'word'
  | 'excel'
  | 'pptx'
  | 'text'
  | 'unsupported'

const IMAGE_EXT = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp', 'tif', 'tiff'])
const WORD_EXT = new Set(['docx'])
const EXCEL_EXT = new Set(['xlsx', 'xls'])
const PPT_EXT = new Set(['pptx'])
const TEXT_EXT = new Set(['txt', 'csv', 'md', 'log'])
const CAD_EXT = new Set([
  'dwg', 'dxf', 'dwt', 'dwf', 'step', 'stp', 'iges', 'igs',
  'sldprt', 'sldasm', 'slddrw', 'ipt', 'iam',
])

function fileExt(name?: string): string {
  return (name || '').split('.').pop()?.toLowerCase() || ''
}

/** 是否可在页内预览 */
export function isPreviewable(contentType?: string, name?: string): PreviewableKind | false {
  if (!contentType && !name) return false
  const ct = (contentType || '').toLowerCase()
  const ext = fileExt(name)
  if (ct.startsWith('image/') || IMAGE_EXT.has(ext)) return 'image'
  if (ct === 'application/pdf' || ext === 'pdf') return 'pdf'
  if (WORD_EXT.has(ext) || ct.includes('wordprocessingml')) return 'word'
  if (
    EXCEL_EXT.has(ext)
    || ct.includes('spreadsheetml')
    || ct === 'application/vnd.ms-excel'
  ) {
    return 'excel'
  }
  if (PPT_EXT.has(ext) || ct.includes('presentationml')) return 'pptx'
  if (TEXT_EXT.has(ext) || ct.startsWith('text/')) return 'text'
  return false
}

/** 是否应显示「阅览」入口（含 CAD 等暂不支持在线渲染的格式） */
export function canOpenAttachmentPreview(name?: string, contentType?: string): boolean {
  if (isPreviewable(contentType, name)) return true
  const ext = fileExt(name)
  if (!ext) return false
  return CAD_EXT.has(ext) || ['doc', 'ppt', 'pdf'].includes(ext)
    || IMAGE_EXT.has(ext) || WORD_EXT.has(ext) || EXCEL_EXT.has(ext) || PPT_EXT.has(ext)
    || ['zip', 'rar', '7z'].includes(ext)
}

/** 旧版 Office / CAD：可点阅览但页内无法渲染 */
export function isBrowserUnsupportedPreview(name?: string, contentType?: string): boolean {
  if (isPreviewable(contentType, name)) return false
  const ext = fileExt(name)
  return CAD_EXT.has(ext) || ['doc', 'ppt'].includes(ext)
}

/** 需要从服务端拉取 Blob 再渲染的预览类型 */
export function isBlobPreviewKind(kind: PreviewableKind | false): kind is 'word' | 'excel' | 'pptx' | 'text' {
  return kind === 'word' || kind === 'excel' || kind === 'pptx' || kind === 'text'
}
