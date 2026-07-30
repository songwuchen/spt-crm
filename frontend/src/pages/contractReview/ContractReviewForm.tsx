import { useEffect, useState } from 'react'
import { Button, Form, Input, Space, Table, message, Select, Tag } from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'
import dayjs from 'dayjs'
import { contractReviewApi } from '@/api/contractReview'
import ContractReviewFields from '@/components/ContractReviewFields'
import AttachmentPanel from '@/components/AttachmentPanel'
import ContractSectionTitle from '@/components/ContractSectionTitle'
import { CONTRACT_REVIEW_STATUS, REVIEW_NATIVE_KEYS } from '@/constants/contractReview'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useAuthStore } from '@/stores/useAuthStore'
import { useCustomerSelect, useUserSelect } from '@/hooks/useSelectOptions'
import DepartmentSelect from '@/components/DepartmentSelect'

type ContactRow = {
  key: string
  contact_name?: string
  superior?: string
  mobile?: string
  title?: string
  email_or_ask?: string
  email?: string
  ask?: string
  address?: string
}

function newContact(): ContactRow {
  return { key: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}` }
}

export default function ContractReviewForm() {
  const { id } = useParams<{ id: string }>()
  const isEdit = !!id && id !== 'new'
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [contacts, setContacts] = useState<ContactRow[]>([newContact()])
  const [reviewId, setReviewId] = useState<string | undefined>(isEdit ? id : undefined)
  const customerSelect = useCustomerSelect()
  const ownerSelect = useUserSelect()
  const managerSelect = useUserSelect()
  const currentUser = useAuthStore((s) => s.user)
  usePageTitle(isEdit ? '编辑合同评审' : '新建合同评审')

  useEffect(() => {
    if (!isEdit) {
      form.setFieldsValue({
        status: 'draft',
        review_type: '合同评审',
        owner_id: currentUser?.id,
        owner_name: currentUser?.real_name || currentUser?.username,
        review_json: {},
      })
      if (currentUser) {
        ownerSelect.setInitialOption({
          label: currentUser.real_name || currentUser.username || '',
          value: currentUser.id,
        })
      }
      return
    }
    setLoading(true)
    contractReviewApi.get(id!).then((res) => {
      const d = res.data
      setReviewId(d.id)
      const rj = d.review_json || {}
      const contactList = Array.isArray(rj.contacts) ? rj.contacts as ContactRow[] : []
      setContacts(contactList.length
        ? contactList.map((c, i) => ({ ...c, key: c.key || `c-${i}` }))
        : [newContact()])
      form.setFieldsValue({
        ...d,
        reported_at: d.reported_at ? dayjs(d.reported_at) : undefined,
        review_json: { ...rj, contacts: undefined },
      })
      if (d.owner_id && d.owner_name) {
        ownerSelect.setInitialOption({ label: d.owner_name, value: d.owner_id })
      }
      if (d.region_manager_id && d.region_manager_name) {
        managerSelect.setInitialOption({ label: d.region_manager_name, value: d.region_manager_id })
      }
      if (d.customer_id && d.company_name) {
        customerSelect.setInitialOption({ label: d.company_name, value: d.customer_id })
      }
    }).catch(() => message.error('加载失败')).finally(() => setLoading(false))
  }, [id, isEdit]) // eslint-disable-line react-hooks/exhaustive-deps

  const buildPayload = (values: Record<string, unknown>) => {
    const review_json = {
      ...((values.review_json as Record<string, unknown>) || {}),
      contacts: contacts.map(({ key: _k, ...rest }) => rest),
    }
    const payload: Record<string, unknown> = { review_json }
    for (const k of REVIEW_NATIVE_KEYS) {
      if (k === 'review_json') continue
      if (values[k] !== undefined) payload[k] = values[k]
    }
    if (values.reported_at) {
      payload.reported_at = (values.reported_at as dayjs.Dayjs).toISOString()
    }
    return payload
  }

  const onFinish = async (values: Record<string, unknown>) => {
    setSaving(true)
    try {
      const payload = buildPayload(values)
      if (isEdit) {
        await contractReviewApi.update(id!, payload)
        message.success('已保存')
        navigate(`/contract-reviews/${id}`)
      } else {
        const res = await contractReviewApi.create(payload)
        message.success('已创建')
        navigate(`/contract-reviews/${res.data.id}`)
      }
    } catch {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="p-8 text-slate-400">加载中…</div>

  return (
    <div className="max-w-5xl mx-auto pb-8">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold m-0">{isEdit ? '编辑合同评审' : '新建合同评审'}</h2>
        <Space>
          <Button onClick={() => navigate(isEdit ? `/contract-reviews/${id}` : '/contract-reviews')}>取消</Button>
          <Button type="primary" loading={saving} onClick={() => form.submit()}>保存</Button>
        </Space>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-4">
        <Form form={form} layout="vertical" onFinish={onFinish} initialValues={{ review_json: {} }}>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-x-4 mb-2">
            <Form.Item name="status" label="状态">
              <Select options={[...CONTRACT_REVIEW_STATUS]} />
            </Form.Item>
            <Form.Item name="customer_id" label="关联客户">
              <Select
                allowClear showSearch filterOption={false}
                placeholder="搜索客户"
                options={customerSelect.options}
                loading={customerSelect.loading}
                onSearch={customerSelect.onSearch}
                onDropdownVisibleChange={customerSelect.onDropdownVisibleChange}
                onChange={(_v, opt) => {
                  const o = opt as { label?: string } | undefined
                  if (o?.label) form.setFieldValue('company_name', o.label)
                }}
              />
            </Form.Item>
            <Form.Item name="department_id" label="部门（选择）">
              <DepartmentSelect
                onChange={(v) => {
                  form.setFieldValue('department_id', v)
                }}
              />
            </Form.Item>
            <Form.Item name="owner_id" label="业务员（选择）" className="hidden">
              <Input />
            </Form.Item>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 mb-4">
            <Form.Item label="业务员（系统用户）">
              <Select
                allowClear showSearch filterOption={false}
                options={ownerSelect.options}
                loading={ownerSelect.loading}
                onSearch={ownerSelect.onSearch}
                onDropdownVisibleChange={ownerSelect.onDropdownVisibleChange}
                value={form.getFieldValue('owner_id')}
                onChange={(v, opt) => {
                  form.setFieldsValue({
                    owner_id: v,
                    owner_name: (opt as { label?: string } | undefined)?.label,
                  })
                }}
              />
            </Form.Item>
            <Form.Item label="区域经理/组长（系统用户）">
              <Select
                allowClear showSearch filterOption={false}
                options={managerSelect.options}
                loading={managerSelect.loading}
                onSearch={managerSelect.onSearch}
                onDropdownVisibleChange={managerSelect.onDropdownVisibleChange}
                value={form.getFieldValue('region_manager_id')}
                onChange={(v, opt) => {
                  form.setFieldsValue({
                    region_manager_id: v,
                    region_manager_name: (opt as { label?: string } | undefined)?.label,
                  })
                }}
              />
            </Form.Item>
          </div>

          <ContractReviewFields
            form={form}
            mode={isEdit ? 'edit' : 'create'}
            slots={{
              contacts: (
                <div>
                  <ContractSectionTitle title="联系信息" />
                  <Table
                    size="small"
                    pagination={false}
                    rowKey="key"
                    dataSource={contacts}
                    columns={[
                      {
                        title: '联系人', dataIndex: 'contact_name',
                        render: (v, r) => (
                          <Input value={v} onChange={(e) => setContacts((rows) =>
                            rows.map((x) => x.key === r.key ? { ...x, contact_name: e.target.value } : x))} />
                        ),
                      },
                      {
                        title: '上级领导', dataIndex: 'superior',
                        render: (v, r) => (
                          <Input value={v} onChange={(e) => setContacts((rows) =>
                            rows.map((x) => x.key === r.key ? { ...x, superior: e.target.value } : x))} />
                        ),
                      },
                      {
                        title: '手机', dataIndex: 'mobile', width: 130,
                        render: (v, r) => (
                          <Input value={v} onChange={(e) => setContacts((rows) =>
                            rows.map((x) => x.key === r.key ? { ...x, mobile: e.target.value } : x))} />
                        ),
                      },
                      {
                        title: '职务', dataIndex: 'title', width: 100,
                        render: (v, r) => (
                          <Input value={v} onChange={(e) => setContacts((rows) =>
                            rows.map((x) => x.key === r.key ? { ...x, title: e.target.value } : x))} />
                        ),
                      },
                      {
                        title: '邮箱', dataIndex: 'email',
                        render: (v, r) => (
                          <Input value={v} onChange={(e) => setContacts((rows) =>
                            rows.map((x) => x.key === r.key ? { ...x, email: e.target.value } : x))} />
                        ),
                      },
                      {
                        title: '', key: 'op', width: 48,
                        render: (_, r) => (
                          <Button type="text" danger icon={<DeleteOutlined />}
                            onClick={() => setContacts((rows) => rows.filter((x) => x.key !== r.key))} />
                        ),
                      },
                    ]}
                  />
                  <Button type="dashed" block className="mt-2" icon={<PlusOutlined />}
                    onClick={() => setContacts((rows) => [...rows, newContact()])}>
                    添加联系人
                  </Button>
                </div>
              ),
              review_files: reviewId ? (
                <div className="space-y-3">
                  <AttachmentPanel bizType="contract_review" bizId={reviewId} title="附件" />
                  <AttachmentPanel bizType="contract_review_image" bizId={reviewId} title="图片" accept="image/*" />
                </div>
              ) : (
                <div className="text-sm text-slate-400">保存后可上传附件/图片</div>
              ),
              feedback_files: reviewId ? (
                <div className="space-y-3">
                  <AttachmentPanel bizType="contract_review_feedback" bizId={reviewId} title="反馈附件" />
                  <AttachmentPanel bizType="contract_review_feedback_image" bizId={reviewId} title="反馈图片" accept="image/*" />
                </div>
              ) : (
                <div className="text-sm text-slate-400">保存后可上传反馈附件</div>
              ),
            }}
          />
        </Form>
      </div>

      <div className="flex justify-end gap-2 mt-2 mb-6">
        <Button onClick={() => navigate(isEdit ? `/contract-reviews/${id}` : '/contract-reviews')}>取消</Button>
        <Button type="primary" loading={saving} onClick={() => form.submit()}>保存</Button>
      </div>
    </div>
  )
}
