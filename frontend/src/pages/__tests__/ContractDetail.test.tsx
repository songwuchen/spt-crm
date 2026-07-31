/**
 * ContractDetail page tests — rendering, version info, signing workflow.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import { useAuthStore } from '@/stores/useAuthStore'
import type { UserInfo } from '@/api/types'

// ---- Mocks ----------------------------------------------------------------

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => vi.fn(),
    useParams: () => ({ id: 'proj-1', cid: 'c-1' }),
  }
})

vi.mock('@/api/contract', () => ({
  contractApi: {
    get: vi.fn(),
    getVersion: vi.fn(),
    newVersion: vi.fn(),
    sign: vi.fn(),
    renew: vi.fn(),
    related: vi.fn().mockResolvedValue({ data: null }),
    update: vi.fn(),
    updateVersion: vi.fn(),
  },
}))

vi.mock('@/api/approval', () => ({
  approvalApi: {
    submit: vi.fn(),
    list: vi.fn(),
  },
}))

vi.mock('@/api/user', () => ({
  userApi: { list: vi.fn() },
}))

vi.mock('@/api/ai', () => ({
  aiApi: { analyze: vi.fn() },
}))

vi.mock('@/api/payment', () => ({
  paymentApi: {
    listPlans: vi.fn().mockResolvedValue({ data: [] }),
    listMilestones: vi.fn().mockResolvedValue({ data: [] }),
    bulkCreatePlans: vi.fn(),
  },
}))

vi.mock('@/api/delivery', () => ({
  deliveryApi: {
    listMilestones: vi.fn().mockResolvedValue({ data: [] }),
  },
}))

vi.mock('@/api/activity', () => ({
  activityApi: {
    list: vi.fn().mockResolvedValue({ data: [] }),
    create: vi.fn().mockResolvedValue({ data: {} }),
    togglePin: vi.fn().mockResolvedValue({ data: {} }),
    delete: vi.fn().mockResolvedValue({ data: null }),
  },
}))

vi.mock('@/api/attachment', () => ({
  attachmentApi: {
    list: vi.fn().mockResolvedValue({ data: [] }),
    upload: vi.fn().mockResolvedValue({ data: {} }),
    delete: vi.fn().mockResolvedValue({ data: null }),
  },
}))

vi.mock('@/api/lowcode', () => ({
  lowcodeApi: {
    entityFormSchema: vi.fn().mockResolvedValue({
      data: { native_fields: [], field_definitions: [], rule_definitions: [] },
    }),
    entityFields: vi.fn().mockResolvedValue({
      data: { field_definitions: [], rule_definitions: [] },
    }),
  },
}))

vi.mock('@/components/VoiceInput', () => ({
  default: () => null,
}))

vi.mock('@/components/AttachmentPanel', () => ({
  default: () => <div data-testid="attachment-panel">AttachmentPanel</div>,
}))

vi.mock('@/components/ContractAttachmentSlots', () => ({
  default: () => <div data-testid="contract-attachment-slots" />,
}))

vi.mock('@/components/ai/AiAnalysisButton', () => ({
  default: () => null,
}))

vi.mock('@/components/ContractRegistrationFields', () => ({
  default: () => null,
  DATE_KEYS: new Set<string>(),
}))

// 明细表编辑器列很多，真实渲染会把每个用例拖到 ~8s，CI 15s 超时易踩线
vi.mock('@/components/ContractTerms', async () => {
  const actual = await vi.importActual<typeof import('@/components/ContractTerms')>('@/components/ContractTerms')
  return {
    ...actual,
    LineItemsEditor: () => <div data-testid="line-items-editor" />,
    PaymentTermsEditor: () => <div data-testid="payment-terms-editor" />,
    PaymentTermsView: () => <div data-testid="payment-terms-view" />,
    ClauseTermsView: () => <div data-testid="clause-terms-view" />,
    ContractSubtableTitle: ({ fallback }: { fallback: string }) => <div>{fallback}</div>,
  }
})

vi.mock('@/components/lowcode/FieldPolicy', () => ({
  FieldPolicyProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useFieldPolicy: () => ({
    loaded: true, failed: false, nativeFields: [], customFields: [], rules: [],
    states: {}, nativeValues: {}, labelOf: () => undefined,
  }),
}))

vi.mock('@/api/client', () => ({
  default: {
    get: vi.fn().mockResolvedValue({ data: [] }),
    post: vi.fn().mockResolvedValue({ data: {} }),
    put: vi.fn().mockResolvedValue({ data: {} }),
    delete: vi.fn().mockResolvedValue({ data: null }),
  },
}))

vi.mock('@/components/SignaturePad', () => ({
  default: ({ onSave, onCancel }: { onSave: (url: string) => void; onCancel: () => void }) => (
    <div data-testid="signature-pad">
      <button onClick={() => onSave('data:image/png;base64,test')}>Save</button>
      <button onClick={onCancel}>Cancel</button>
    </div>
  ),
}))

import ContractDetail from '../opportunity/ContractDetail'
import { contractApi } from '@/api/contract'
import { approvalApi } from '@/api/approval'
import { userApi } from '@/api/user'

const adminUser: UserInfo = {
  id: 'u-1',
  username: 'admin',
  real_name: 'Admin',
  roles: ['admin'],
  permissions: ['contract:view', 'contract:edit'],
  tenant_id: 't-1',
}

const mockContract = {
  id: 'c-1',
  project_id: 'proj-1',
  contract_no: 'CT-2026-001',
  status: 'draft',
  amount_total: 500000,
  current_version_no: 1,
  signed_date: null,
  end_date: '2027-03-10',
  payment_terms_json: [
    { kind: '预付款', ratio: 30, amount: 150000 },
    { kind: '尾款', ratio: 70, amount: 350000 },
  ],
  delivery_terms_json: null,
  created_by_name: 'Admin',
  created_at: '2026-03-10T00:00:00',
  versions: [
    {
      id: 'cv-1',
      version_no: 1,
      title: 'Initial Version',
      status: 'draft',
      risk_level: 'M',
      key_clauses_json: null,
      created_at: '2026-03-10T00:00:00',
    },
  ],
}

describe('ContractDetail', { timeout: 15000 }, () => {
  beforeEach(() => {
    vi.clearAllMocks()
    act(() => {
      useAuthStore.getState().setUser(adminUser)
    })
    ;(contractApi.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: mockContract })
    ;(approvalApi.list as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { items: [], total: 0 } })
    ;(userApi.list as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { items: [], total: 0 } })
  })

  it('renders contract number after loading', async () => {
    render(<ContractDetail />)
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /CT-2026-001/ })).toBeInTheDocument()
    })
  })

  it('fetches contract on mount', async () => {
    render(<ContractDetail />)
    await waitFor(() => {
      expect(contractApi.get).toHaveBeenCalledWith('c-1')
    })
  })

  it('shows signing workflow stepper', async () => {
    render(<ContractDetail />)
    await waitFor(() => {
      expect(screen.getByText('签章流程')).toBeInTheDocument()
      // 状态标签现在也显示「草稿」（原为原始码 draft），故用 getAllByText
      expect(screen.getAllByText('草稿').length).toBeGreaterThan(0)
      expect(screen.getByText('审批')).toBeInTheDocument()
      expect(screen.getByText('签章')).toBeInTheDocument()
      expect(screen.getByText('生效')).toBeInTheDocument()
    })
  })

  it('shows contract amount', async () => {
    render(<ContractDetail />)
    await waitFor(() => {
      expect(screen.getByText(/¥500,000/)).toBeInTheDocument()
    })
  })

  it('shows draft actions (submit approval + sign)', async () => {
    render(<ContractDetail />)
    await waitFor(() => {
      expect(screen.getByText('提交审批')).toBeInTheDocument()
      expect(screen.getByText('签署合同')).toBeInTheDocument()
    })
  })

  it('shows version selector', async () => {
    render(<ContractDetail />)
    await waitFor(() => {
      expect(screen.getByText('版本')).toBeInTheDocument()
    })
  })

  it('shows payment terms', async () => {
    render(<ContractDetail />)
    await waitFor(() => {
      // UI 文案已对齐简道云为「收款计划」（原「付款条款」）
      expect(screen.getAllByText('收款计划').length).toBeGreaterThan(0)
    })
  })

  it('shows attachment and AI tabs', async () => {
    render(<ContractDetail />)
    await waitFor(() => {
      expect(screen.getByRole('tab', { name: /合同附件/ })).toBeInTheDocument()
      expect(screen.getByRole('tab', { name: /AI条款分析/ })).toBeInTheDocument()
    })
  })

  it('hides approval/sign buttons for signed contract', async () => {
    const signedContract = { ...mockContract, status: 'signed', signed_date: '2026-03-10' }
    ;(contractApi.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: signedContract })
    render(<ContractDetail />)
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /CT-2026-001/ })).toBeInTheDocument()
    })
    expect(screen.queryByText('提交审批')).not.toBeInTheDocument()
    expect(screen.queryByText('签署合同')).not.toBeInTheDocument()
    expect(screen.getByText('发起续约')).toBeInTheDocument()
  })
})
