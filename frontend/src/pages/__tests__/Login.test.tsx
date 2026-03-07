import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Login from '../auth/Login'
import { useAuthStore } from '@/stores/useAuthStore'

// Mock authApi
vi.mock('@/api/auth', () => ({
  authApi: {
    login: vi.fn(),
  },
}))

import { authApi } from '@/api/auth'

describe('Login', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    act(() => {
      useAuthStore.getState().logout()
    })
  })

  it('renders login form with title', () => {
    render(<Login />)
    expect(screen.getByText(/SPT-CRM/)).toBeInTheDocument()
    expect(screen.getByText(/智能销售项目管理平台/)).toBeInTheDocument()
  })

  it('renders username and password inputs', () => {
    render(<Login />)
    expect(screen.getByPlaceholderText('用户名')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('密码')).toBeInTheDocument()
  })

  it('renders login button', () => {
    render(<Login />)
    // Ant Design Button may insert space between CJK characters
    const btn = screen.getByRole('button', { name: /登.*录/ })
    expect(btn).toBeInTheDocument()
  })

  it('shows demo credentials', () => {
    render(<Login />)
    expect(screen.getByText(/admin \/ admin123/)).toBeInTheDocument()
  })

  it('calls authApi.login on form submit', async () => {
    const user = userEvent.setup()
    const loginMock = authApi.login as ReturnType<typeof vi.fn>
    loginMock.mockResolvedValue({
      data: { access_token: 'token123', refresh_token: 'refresh456' },
    })

    render(<Login />)
    await user.type(screen.getByPlaceholderText('用户名'), 'admin')
    await user.type(screen.getByPlaceholderText('密码'), 'admin123')
    await user.click(screen.getByRole('button', { name: /登.*录/ }))

    expect(loginMock).toHaveBeenCalledWith({ username: 'admin', password: 'admin123' })
  })
})
