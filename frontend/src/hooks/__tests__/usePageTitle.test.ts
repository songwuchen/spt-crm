import { describe, it, expect, afterEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { usePageTitle } from '../usePageTitle'

describe('usePageTitle', () => {
  afterEach(() => {
    document.title = ''
  })

  it('sets title with app name suffix', () => {
    renderHook(() => usePageTitle('商机详情'))
    expect(document.title).toBe('商机详情 - SPT-CRM')
  })

  it('sets app name only when no title provided', () => {
    renderHook(() => usePageTitle())
    expect(document.title).toBe('SPT-CRM')
  })

  it('sets app name only when title is undefined', () => {
    renderHook(() => usePageTitle(undefined))
    expect(document.title).toBe('SPT-CRM')
  })

  it('resets title on unmount', () => {
    const { unmount } = renderHook(() => usePageTitle('测试'))
    expect(document.title).toBe('测试 - SPT-CRM')
    unmount()
    expect(document.title).toBe('SPT-CRM')
  })

  it('updates title when value changes', () => {
    const { rerender } = renderHook(({ title }) => usePageTitle(title), {
      initialProps: { title: '页面A' as string | undefined },
    })
    expect(document.title).toBe('页面A - SPT-CRM')

    rerender({ title: '页面B' })
    expect(document.title).toBe('页面B - SPT-CRM')
  })
})
