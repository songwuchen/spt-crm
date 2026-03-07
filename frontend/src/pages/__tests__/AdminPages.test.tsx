/**
 * Admin pages tests — UserList, RoleList
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { useAuthStore } from '@/stores/useAuthStore'
import type { UserInfo } from '@/api/types'

vi.mock('@/api/user', () => ({
  userApi: { list: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  roleApi: { list: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn(), updatePermissions: vi.fn() },
  permissionApi: { list: vi.fn() },
}))

vi.mock('@/api/department', () => ({
  departmentApi: { tree: vi.fn() },
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn() }
})

import UserList from '../admin/user/UserList'
import RoleList from '../admin/role/RoleList'
import { userApi, roleApi, permissionApi } from '@/api/user'
import { departmentApi } from '@/api/department'

const adminUser: UserInfo = {
  id: 'u-1', username: 'admin', real_name: 'Admin',
  roles: ['admin'], permissions: ['user:view', 'role:view', 'role:manage'],
  tenant_id: 't-1',
}

describe('UserList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useAuthStore.getState().setUser(adminUser)
    ;(userApi.list as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: {
        items: [
          { id: 'u-1', username: 'admin', real_name: '管理员', is_active: true, roles: ['admin'], departments: [] },
          { id: 'u-2', username: 'sales1', real_name: '销售甲', is_active: true, roles: ['sales'], departments: [] },
        ],
        total: 2,
      },
    })
    ;(roleApi.list as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [{ id: 'r-1', code: 'admin', name: '管理员' }] })
    ;(departmentApi.tree as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
  })

  it('renders page title', async () => {
    render(<UserList />)
    expect(screen.getByText('用户管理')).toBeInTheDocument()
  })

  it('loads and displays users', async () => {
    render(<UserList />)
    await waitFor(() => {
      expect(screen.getByText('管理员')).toBeInTheDocument()
      expect(screen.getByText('销售甲')).toBeInTheDocument()
    })
  })

  it('shows add user button', () => {
    render(<UserList />)
    expect(screen.getByText('新建用户')).toBeInTheDocument()
  })
})

describe('RoleList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useAuthStore.getState().setUser(adminUser)
    ;(roleApi.list as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: [
        { id: 'r-1', code: 'admin', name: '管理员', description: '系统管理员', is_system: true, permissions: ['customer:view', 'customer:edit'] },
        { id: 'r-2', code: 'sales', name: '销售', description: '销售人员', is_system: false, permissions: ['customer:view'] },
      ],
    })
    ;(permissionApi.list as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: [
        { id: 'p-1', code: 'customer:view', name: '查看客户', group_name: '客户' },
        { id: 'p-2', code: 'customer:edit', name: '编辑客户', group_name: '客户' },
      ],
    })
  })

  it('renders page title', async () => {
    render(<RoleList />)
    expect(screen.getByText('角色权限')).toBeInTheDocument()
  })

  it('loads and displays roles', async () => {
    render(<RoleList />)
    await waitFor(() => {
      expect(screen.getByText('管理员')).toBeInTheDocument()
      expect(screen.getByText('销售')).toBeInTheDocument()
    })
  })

  it('shows add role button', () => {
    render(<RoleList />)
    expect(screen.getByText('新建角色')).toBeInTheDocument()
  })
})
