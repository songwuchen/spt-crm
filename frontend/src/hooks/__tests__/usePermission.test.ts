import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { usePermission } from '../usePermission'
import { useAuthStore } from '@/stores/useAuthStore'
import type { UserInfo } from '@/api/types'

const mockUser: UserInfo = {
  id: 'u-1',
  username: 'test',
  real_name: 'Test User',
  roles: ['admin'],
  permissions: ['customer:view', 'customer:edit', 'project:view'],
  tenant_id: 't-1',
}

describe('usePermission', () => {
  beforeEach(() => {
    act(() => {
      useAuthStore.getState().logout()
    })
  })

  it('returns false when no user is logged in', () => {
    const { result } = renderHook(() => usePermission())
    expect(result.current.hasPermission('customer:view')).toBe(false)
  })

  it('returns true when user has permission', () => {
    act(() => {
      useAuthStore.getState().setUser(mockUser)
    })
    const { result } = renderHook(() => usePermission())
    expect(result.current.hasPermission('customer:view')).toBe(true)
    expect(result.current.hasPermission('customer:edit')).toBe(true)
    expect(result.current.hasPermission('project:view')).toBe(true)
  })

  it('returns false when user lacks permission', () => {
    act(() => {
      useAuthStore.getState().setUser(mockUser)
    })
    const { result } = renderHook(() => usePermission())
    expect(result.current.hasPermission('project:delete')).toBe(false)
    expect(result.current.hasPermission('admin:manage')).toBe(false)
  })
})
