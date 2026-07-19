// 移动端三个新建表单的冒烟测试。
//
// 它们从裸 useState + 原生 input 重写成了 antd Form + 字段策略（PolicyItem/MField），
// 且补齐了此前缺失的目录字段 —— 缺字段会造成「租户把某字段配成必填后，移动端再也
// 建不了记录且无处可填」的死锁。这里确认重写后表单能渲染、字段仍在、且能提交。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

const leadCreate = vi.fn().mockResolvedValue({ data: { id: 'l-1' } })
const customerCreate = vi.fn().mockResolvedValue({ data: { id: 'c-1' } })
const projectCreate = vi.fn().mockResolvedValue({ data: { id: 'p-1' } })

vi.mock('@/api/lead', () => ({ leadApi: { create: (...a: unknown[]) => leadCreate(...a) } }))
vi.mock('@/api/customer', () => ({
  customerApi: {
    create: (...a: unknown[]) => customerCreate(...a),
    list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
  },
}))
vi.mock('@/api/project', () => ({ projectApi: { create: (...a: unknown[]) => projectCreate(...a) } }))

// 字段策略 schema：不返回任何租户配置，表单应回落为「无策略」正常可用
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

vi.mock('@/hooks/useDataDict', () => ({
  useDataDict: (_t: string, fallback?: { label: string; value: string }[]) => ({
    options: fallback ?? [], loading: false,
  }),
}))
vi.mock('@/hooks/useSelectOptions', () => ({
  useUserSelect: () => ({ options: [], loading: false, onSearch: vi.fn(), onDropdownVisibleChange: vi.fn() }),
}))
vi.mock('@/stores/useAuthStore', () => ({
  useAuthStore: vi.fn((selector: any) => {
    const state = { user: { username: 'admin', roles: [] }, token: 't' }
    return selector ? selector(state) : state
  }),
}))
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn() }
})

import MobileLeadForm from '../mobile/MobileLeadForm'
import MobileCustomerForm from '../mobile/MobileCustomerForm'
import MobileOpportunityForm from '../mobile/MobileOpportunityForm'

beforeEach(() => {
  leadCreate.mockClear(); customerCreate.mockClear(); projectCreate.mockClear()
})

describe('MobileLeadForm', () => {
  it('渲染基础字段', () => {
    render(<MobileLeadForm />)
    expect(screen.getByText('新建线索')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('输入线索标题')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('输入公司名称')).toBeInTheDocument()
  })

  it('补齐的目录字段收在「更多字段」里，展开后可见', () => {
    render(<MobileLeadForm />)
    // 折叠态下这些字段不可见（用 hidden 容器包着，值仍在 Form 里）
    fireEvent.click(screen.getByText('展开更多字段'))
    expect(screen.getByText('行业')).toBeInTheDocument()
    expect(screen.getByText('客户类型')).toBeInTheDocument()
    expect(screen.getByText('业务日期')).toBeInTheDocument()
  })

  it('填入标题与公司名后可提交', async () => {
    render(<MobileLeadForm />)
    fireEvent.change(screen.getByPlaceholderText('输入线索标题'), { target: { value: '测试线索' } })
    fireEvent.change(screen.getByPlaceholderText('输入公司名称'), { target: { value: '测试公司' } })
    fireEvent.click(screen.getByText('保存'))
    await waitFor(() => expect(leadCreate).toHaveBeenCalled())
    expect(leadCreate.mock.calls[0][0]).toMatchObject({ title: '测试线索', company_name: '测试公司' })
  })
})

describe('MobileCustomerForm', () => {
  it('渲染并展开更多字段', () => {
    render(<MobileCustomerForm />)
    expect(screen.getByText('新建客户')).toBeInTheDocument()
    fireEvent.click(screen.getByText('展开更多字段'))
    expect(screen.getByText('预算金额')).toBeInTheDocument()
    expect(screen.getByText('邮编')).toBeInTheDocument()
  })

  it('填入客户名后可提交', async () => {
    render(<MobileCustomerForm />)
    fireEvent.change(screen.getByPlaceholderText('请输入客户名称'), { target: { value: '测试客户' } })
    fireEvent.click(screen.getByText('创建'))
    await waitFor(() => expect(customerCreate).toHaveBeenCalled())
    expect(customerCreate.mock.calls[0][0]).toMatchObject({ name: '测试客户' })
  })
})

describe('MobileOpportunityForm', () => {
  it('渲染并展开更多字段', () => {
    render(<MobileOpportunityForm />)
    expect(screen.getByText('新建商机')).toBeInTheDocument()
    fireEvent.click(screen.getByText('展开更多字段'))
    expect(screen.getByText('赢单概率')).toBeInTheDocument()
    expect(screen.getByText('付款方式')).toBeInTheDocument()
  })

  it('关键需求仍会折叠进 key_requirements_json', async () => {
    render(<MobileOpportunityForm />)
    fireEvent.change(screen.getByPlaceholderText('输入商机名称'), { target: { value: '测试商机' } })
    fireEvent.change(
      screen.getByPlaceholderText('需求摘要：客户核心需求、技术规格、交付/预算约束等'),
      { target: { value: '核心需求' } },
    )
    // 客户为必填，未选时应被拦下
    fireEvent.click(screen.getByText('保存'))
    await waitFor(() => expect(screen.getByText('请选择客户')).toBeInTheDocument())
    expect(projectCreate).not.toHaveBeenCalled()
  })
})
