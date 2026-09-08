import { describe, expect, it } from 'vitest'
import { shortAttachmentDisplayName } from './attachmentDisplayName'

describe('shortAttachmentDisplayName', () => {
  it('shortens dingtalk local paths', () => {
    const raw = 'file___com.dingtalk.hmos_data_storage/file/photo.jpg'
    expect(shortAttachmentDisplayName(raw)).toBe('photo.jpg')
  })

  it('falls back to indexed label for opaque paths', () => {
    expect(shortAttachmentDisplayName('file___com.dingtalk.hmos_data_storage', 2)).toBe('图片 3')
  })

  it('truncates very long normal names', () => {
    const long = 'a'.repeat(40)
    expect(shortAttachmentDisplayName(long).endsWith('…')).toBe(true)
  })
})
