import { describe, expect, it } from 'vitest'
import {
  isPreviewable,
  isBrowserUnsupportedPreview,
  needsWebOfficePreview,
} from '@/utils/attachmentPreview'

describe('attachmentPreview IMM weboffice', () => {
  it('routes .doc to weboffice', () => {
    expect(needsWebOfficePreview('a.doc')).toBe(true)
    expect(isPreviewable('application/msword', 'x.doc')).toBe('weboffice')
    expect(isBrowserUnsupportedPreview('x.doc')).toBe(false)
  })

  it('keeps .docx as client word preview', () => {
    expect(needsWebOfficePreview('a.docx')).toBe(false)
    expect(isPreviewable(undefined, 'a.docx')).toBe('word')
  })

  it('routes pptx/xlsx to weboffice', () => {
    expect(isPreviewable(undefined, 'a.pptx')).toBe('weboffice')
    expect(isPreviewable(undefined, 'a.xlsx')).toBe('weboffice')
  })

  it('routes mp4/webm to video preview', () => {
    expect(isPreviewable('video/mp4', 'clip.mp4')).toBe('video')
    expect(isPreviewable(undefined, 'demo.webm')).toBe('video')
    expect(isPreviewable(undefined, 'a.mov')).toBe('video')
  })
})
