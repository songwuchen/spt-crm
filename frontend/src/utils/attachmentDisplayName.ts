/** 附件展示用短文件名（钉钉本地路径等过长名称折叠）。 */
export function shortAttachmentDisplayName(name: string, index?: number): string {
  const raw = (name || '').trim()
  if (!raw) return index != null ? `附件 ${index + 1}` : '附件'
  if (/^file___|^content:\/\/|^file:\/\//i.test(raw) || raw.includes('dingtalk')) {
    const seg = raw.split(/[/\\]/).filter(Boolean).pop() || ''
    if (seg && seg.length <= 36 && !seg.startsWith('file___')) return seg
    return index != null ? `图片 ${index + 1}` : '图片'
  }
  if (raw.length > 36) return `${raw.slice(0, 32)}…`
  return raw
}
