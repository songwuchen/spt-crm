/** 附件页内预览类型。低代码 FileField、AttachmentPanel 共用。 */
export type PreviewableKind =
  | 'image'
  | 'pdf'
  | 'word'
  | 'excel'
  | 'pptx'
  | 'text'
  | 'video'
  | 'weboffice'
  | 'unsupported'

const IMAGE_EXT = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp', 'tif', 'tiff'])
const WORD_EXT = new Set(['docx'])
const EXCEL_EXT = new Set(['xlsx', 'xls', 'xlsm'])
const PPT_EXT = new Set(['pptx'])
const TEXT_EXT = new Set(['txt', 'csv', 'md', 'log'])
const VIDEO_EXT = new Set(['mp4', 'mov', 'webm', 'm4v', 'mkv', 'avi', 'wmv', 'flv', 'mpeg', 'mpg', '3gp'])
const CAD_EXT = new Set([
  'dwg', 'dxf', 'dwt', 'dwf', 'step', 'stp', 'iges', 'igs',
  'sldprt', 'sldasm', 'slddrw', 'ipt', 'iam',
])

/** 与后端 weboffice_service.needs_weboffice 对齐：本地啃不动 → IMM */
const WEBOFFICE_EXT = new Set([
  'doc', 'dot', 'dotx', 'docm', 'dotm', 'rtf', 'wps', 'wpt',
  'ppt', 'pptx', 'pptm', 'pps', 'ppsx', 'ppsm', 'potx', 'potm', 'dpt', 'dps',
  'xls', 'xlsx', 'xlsm', 'et', 'xlt', 'xltx', 'xltm',
])

/** IMM 失败时可退回本地 Office 渲染 */
export const WEBOFFICE_EXCEL_FALLBACK = new Set(['xls', 'xlsx', 'xlsm'])
export const WEBOFFICE_PPTX_FALLBACK = new Set(['pptx'])

function fileExt(name?: string): string {
  return (name || '').split('.').pop()?.toLowerCase() || ''
}

export function needsWebOfficePreview(name?: string, contentType?: string): boolean {
  const ext = fileExt(name)
  if (WEBOFFICE_EXT.has(ext)) return true
  const ct = (contentType || '').toLowerCase()
  return (
    ct === 'application/msword'
    || ct === 'application/vnd.ms-powerpoint'
    || ct.includes('presentationml')
    || ct === 'application/vnd.ms-excel'
    || ct.includes('spreadsheetml')
  )
}

/** 是否可在页内预览 */
export function isPreviewable(contentType?: string, name?: string): PreviewableKind | false {
  if (!contentType && !name) return false
  const ct = (contentType || '').toLowerCase()
  const ext = fileExt(name)
  if (ct.startsWith('image/') || IMAGE_EXT.has(ext)) return 'image'
  if (ct.startsWith('video/') || VIDEO_EXT.has(ext)) return 'video'
  if (ct === 'application/pdf' || ext === 'pdf') return 'pdf'
  // IMM 优先（含 .doc / ppt / xlsx…）；docx 仍本地
  if (needsWebOfficePreview(name, contentType) && !WORD_EXT.has(ext) && !TEXT_EXT.has(ext)) {
    // csv/txt 已在 TEXT；docx 不走 weboffice
    if (ext === 'docx') return 'word'
    return 'weboffice'
  }
  if (WORD_EXT.has(ext) || ct.includes('wordprocessingml')) return 'word'
  if (EXCEL_EXT.has(ext) || ct.includes('spreadsheetml') || ct === 'application/vnd.ms-excel') {
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

/** CAD 等：可点阅览但页内无法渲染 */
export function isBrowserUnsupportedPreview(name?: string, contentType?: string): boolean {
  if (isPreviewable(contentType, name)) return false
  const ext = fileExt(name)
  return CAD_EXT.has(ext)
}

/** 需要从服务端拉取 Blob 再渲染的预览类型 */
export function isBlobPreviewKind(kind: PreviewableKind | false): kind is 'word' | 'excel' | 'pptx' | 'text' {
  return kind === 'word' || kind === 'excel' || kind === 'pptx' || kind === 'text'
}

export function attachmentFileExt(name?: string): string {
  return fileExt(name)
}
