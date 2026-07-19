/**
 * SettingsPage tests — tabs rendering, CRUD modals, feature toggles.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useAuthStore } from '@/stores/useAuthStore'
import type { UserInfo } from '@/api/types'

// ---- Mocks ----------------------------------------------------------------

vi.mock('@/api/settings', () => ({
  settingsApi: {
    listStages: vi.fn(),
    listMargins: vi.fn(),
    listAiPolicies: vi.fn(),
    listIntegrations: vi.fn(),
    listFeatures: vi.fn(),
    getAiBudget: vi.fn(),
    listApprovalPolicies: vi.fn(),
    updateStage: vi.fn(),
    createMargin: vi.fn(),
    createIntegration: vi.fn(),
    deleteIntegration: vi.fn(),
    updateFeature: vi.fn(),
    updateAiBudget: vi.fn(),
    createApprovalPolicy: vi.fn(),
    updateApprovalPolicy: vi.fn(),
    deleteApprovalPolicy: vi.fn(),
    listDocTemplates: vi.fn(),
    listEmailTemplates: vi.fn(),
    createDocTemplate: vi.fn(),
    updateDocTemplate: vi.fn(),
    deleteDocTemplate: vi.fn(),
    createEmailTemplate: vi.fn(),
    updateEmailTemplate: vi.fn(),
    deleteEmailTemplate: vi.fn(),
    getDocTemplate: vi.fn(),
    backupStats: vi.fn(),
    backupDownloadUrl: vi.fn(),
    auditVerify: vi.fn(),
    getPoolRules: vi.fn(),
    updatePoolRules: vi.fn(),
    getReportSchedules: vi.fn(),
    updateReportSchedules: vi.fn(),
    getUiSettings: vi.fn(),
    updateUiSettings: vi.fn(),
  },
}))

vi.mock('@/api/user', () => ({
  roleApi: { list: vi.fn() },
  userApi: { list: vi.fn() },
}))

vi.mock('@/api/client', () => ({
  default: { get: vi.fn() },
}))

vi.mock('@/utils/download', () => ({
  downloadFile: vi.fn(),
}))

import SettingsPage from '../admin/settings/SettingsPage'
import { settingsApi } from '@/api/settings'
import { roleApi } from '@/api/user'
import client from '@/api/client'

const adminUser: UserInfo = {
  id: 'u-1',
  username: 'admin',
  real_name: 'Admin',
  roles: ['admin'],
  permissions: ['admin:manage'],
  tenant_id: 't-1',
}

describe('SettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    act(() => {
      useAuthStore.getState().setUser(adminUser)
    })
    ;(settingsApi.listStages as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: [
        { id: 's-1', stage_code: 'S1', name: '线索确认', gate_rules_json: {} },
        { id: 's-2', stage_code: 'S2', name: '需求分析', gate_rules_json: {} },
      ],
    })
    ;(settingsApi.listMargins as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: [{ id: 'm-1', policy_code: 'default', redline_rate: 0.2, action: 'warn' }],
    })
    ;(settingsApi.listAiPolicies as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
    ;(settingsApi.listIntegrations as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
    ;(settingsApi.listFeatures as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: [
        { id: 'f-1', feature_code: 'ai_center', enabled: true },
        { id: 'f-2', feature_code: 'field_masking', enabled: false },
      ],
    })
    ;(settingsApi.getAiBudget as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { budget_cost: 1000, used_cost: 250, budget_tokens: 500000, used_tokens: 125000, hard_limit: false },
    })
    ;(settingsApi.listApprovalPolicies as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
    ;(settingsApi.listDocTemplates as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
    ;(settingsApi.listEmailTemplates as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
    ;(settingsApi.backupStats as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} })
    ;(settingsApi.backupDownloadUrl as ReturnType<typeof vi.fn>).mockReturnValue('/api/v1/admin/backup')
    ;(settingsApi.getPoolRules as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} })
    ;(settingsApi.getReportSchedules as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
    ;(settingsApi.getUiSettings as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { system_name: null, menu_aliases: {}, hidden_menus: [] } })
    ;(settingsApi.updateUiSettings as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { system_name: null, menu_aliases: {}, hidden_menus: [] } })
    ;(roleApi.list as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [{ id: 'r-1', code: 'admin', name: '管理员' }] })
    ;(client.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [{ id: 'u-1', name: 'Admin' }] })
  })

  it('renders stage gate tab and loads data', async () => {
    render(<SettingsPage />)
    await waitFor(() => {
      expect(settingsApi.listStages).toHaveBeenCalled()
    })
  })

  it('displays stage table with data', async () => {
    render(<SettingsPage />)
    await waitFor(() => {
      expect(screen.getByText('线索确认')).toBeInTheDocument()
      expect(screen.getByText('需求分析')).toBeInTheDocument()
    })
  })

  it('shows margin tab when clicked', async () => {
    const user = userEvent.setup()
    render(<SettingsPage />)
    await waitFor(() => expect(screen.getByText('线索确认')).toBeInTheDocument())

    const tabs = screen.getAllByText(/毛利红线/)
    await user.click(tabs[0])
    await waitFor(() => {
      expect(settingsApi.listMargins).toHaveBeenCalled()
    })
  })

  it('shows feature toggles tab when clicked', async () => {
    const user = userEvent.setup()
    render(<SettingsPage />)
    await waitFor(() => expect(screen.getByText('线索确认')).toBeInTheDocument())

    const tabs = screen.getAllByText(/功能开关/)
    await user.click(tabs[0])
    await waitFor(() => {
      expect(settingsApi.listFeatures).toHaveBeenCalled()
    })
  })

  it('shows AI usage tab when clicked', async () => {
    const user = userEvent.setup()
    render(<SettingsPage />)
    await waitFor(() => expect(screen.getByText('线索确认')).toBeInTheDocument())

    const tabs = screen.getAllByText(/AI用量/)
    await user.click(tabs[0])
    await waitFor(() => {
      expect(settingsApi.getAiBudget).toHaveBeenCalled()
    })
  })

  it('shows approval policies tab when clicked', async () => {
    const user = userEvent.setup()
    render(<SettingsPage />)
    await waitFor(() => expect(screen.getByText('线索确认')).toBeInTheDocument())

    const tabs = screen.getAllByText(/审批策略/)
    await user.click(tabs[0])
    await waitFor(() => {
      expect(settingsApi.listApprovalPolicies).toHaveBeenCalled()
    })
  })

  it('shows integration config tab when clicked', async () => {
    const user = userEvent.setup()
    render(<SettingsPage />)
    await waitFor(() => expect(screen.getByText('线索确认')).toBeInTheDocument())

    const tabs = screen.getAllByText(/集成配置/)
    await user.click(tabs[0])
    await waitFor(() => {
      expect(settingsApi.listIntegrations).toHaveBeenCalled()
    })
  })
})
