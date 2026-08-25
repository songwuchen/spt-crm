import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import PermissionGuard from '../PermissionGuard'
import { useAuthStore } from '@/stores/useAuthStore'
import type { UserInfo } from '@/api/types'

vi.mock('@/hooks/useWorkflowFormTemplateCodes', () => ({
  useWorkflowFormTemplateCodes: () => ({
    codes: new Set<string>(),
    loaded: true,
    hasFormView: false,
  }),
  clearWorkflowFormTemplateCodesCache: vi.fn(),
}))

const adminUser: UserInfo = {
  id: 'u-1',
  username: 'admin',
  real_name: 'Admin',
  roles: ['admin'],
  permissions: ['customer:view', 'customer:edit'],
  tenant_id: 't-1',
}

function renderGuard(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

describe('PermissionGuard', () => {
  beforeEach(() => {
    act(() => {
      useAuthStore.getState().logout()
    })
  })

  it('renders children when user has permission', () => {
    act(() => {
      useAuthStore.getState().setUser(adminUser)
    })
    renderGuard(
      <PermissionGuard permission="customer:view">
        <div>Protected Content</div>
      </PermissionGuard>
    )
    expect(screen.getByText('Protected Content')).toBeInTheDocument()
  })

  it('shows no-permission page when user lacks permission', () => {
    act(() => {
      useAuthStore.getState().setUser(adminUser)
    })
    renderGuard(
      <PermissionGuard permission="admin:manage">
        <div>Protected Content</div>
      </PermissionGuard>
    )
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
    expect(screen.getByText('403')).toBeInTheDocument()
  })

  it('shows no-permission page when no user logged in', () => {
    renderGuard(
      <PermissionGuard permission="customer:view">
        <div>Protected Content</div>
      </PermissionGuard>
    )
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
  })
})
